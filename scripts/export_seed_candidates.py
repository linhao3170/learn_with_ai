"""WO-05 · `python_dotenv` 教师种子备料：候选清单 + 逐项源码证据

这份脚本**只产候选、不落盘**。它做两件事：

1. ``python scripts/export_seed_candidates.py``
   打印「人工确认用的候选清单」。每条候选都带**逐项源码证据**（``文件:行号``），
   证据指向被分析项目里的真实文件与真实行号 —— 人可以顺着行号自己去看。

2. ``python scripts/export_seed_candidates.py --check``
   把「每条候选必须有能指到东西的证据」变成**机器检查**，检查对象有两层：

   - **候选表自检**：候选表里每条候选至少一条证据；每条证据都能解析成
     ``文件:行号``（或 ``文件:起-止``），且该文件存在、行号落在文件范围内、
     被指向的那一段不是空白；候选声明的 ``domain_id`` 必须真的出现在自动图谱里、
     ``related_flow`` 必须真的是该项目的一条真实流程名、``cluster`` 必须是
     ``clusters.json`` 的 key。
   - **已落盘种子自检**：``validation/python_dotenv/business_graph.seed.json`` 与
     ``engine/lexicon/design_tasks.seed.json`` 里 ``python_dotenv`` 那一段 ——
     每条内容条目都必须有 ``_evidence`` 条目、每条证据都必须能指到东西、
     引用到的 key 必须真的存在、``(verb_class, entity)`` 必须两两不重复、
     种子里**不许出现候选表里没有的条目**（没有出处的条目一律打回）。

为什么必须有这一层
------------------
``docs/02`` §9.1 第 ③ 条：**绝不许**让 LLM 生成 ``must_have`` 之后当成评分基准。
所以本脚本的立场是：AI 只交「候选 + 出处」，
``review_status = "confirmed"`` / ``objective_confidence = "confirmed"`` 这两个标记
**只能由人在逐条确认之后写上**。候选清单的每一节都如实标注当前有没有人确认。

用法
----
    python scripts/export_seed_candidates.py
    python scripts/export_seed_candidates.py --check
    python scripts/export_seed_candidates.py --project validation/python_dotenv

退出码：``--check`` 有问题时 1，否则 0。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # pragma: no cover
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_PROJECT = "validation/python_dotenv"

#: 种子图谱文件名（放在被分析的项目目录里，见 docs/02 §8.8）
SEED_GRAPH_NAME = "business_graph.seed.json"
#: 教师设计任务种子（lexicon 内，按 project_id 分段）
SEED_TASKS_NAME = "design_tasks.seed.json"

#: 域目标「已确认」的显式标记（不在 LOCKABLE_FIELDS 里，必须显式写，见 docs/02 §8.8）
CONFIRMED = "confirmed"
#: 「没人确认」的标记。⚠️ 必须用 ``engine/teaching/coverage.py`` 的 ``_UNCONFIRMED_TOKENS``
#: 里真实存在的取值（'' / unconfirmed / unknown / none / null / 未标注 / 待确认）：
#: 那个判定是**白名单**，写一个不在名单里的自造标记（例如 pending_human_review）
#: 会被它当成「已确认」，于是没人确认的域目标会悄悄参与比对 —— 那正是本单最不能出的事。
PENDING = "待确认"


def _ev(file: str, lines: str, what: str) -> Dict[str, str]:
    """一条源码证据：项目内相对路径 + 行号（``N`` 或 ``起-止``）+ 它证明了什么。"""
    return {"file": file, "lines": lines, "what": what}


def _ev_text(item: Dict[str, str]) -> str:
    """证据的展示/落盘文本：``文件:行号（它证明了什么）``。"""
    return f"{item['file']}:{item['lines']}（{item['what']}）"


# ===========================================================================
# 候选表：本轮的 AI 起草结果，**必须由人逐条确认后才允许落盘**
# ===========================================================================
#
# 纪律：这里的每一条都带着「它凭什么是这条」的源码出处。凑不出出处的条目不许写进来
# （宁可候选清单短一点，也不要编）。域候选只覆盖「引擎从代码里切出来的一级域」，
# 用 domain_id 与自动结果对齐；候选中文名与目标文本是**提案**，不是结论。

CANDIDATES: Dict[str, Dict[str, Any]] = {
    "python_dotenv": {
        "project": "validation/python_dotenv",
        "domain_candidates": [
            {
                "domain_id": "d_binding",
                "auto_name_cn": "Binding",
                "name_cn": ".env 语法解析",
                "role": "core",
                "objective": (
                    "把 .env 文本切成「键 = 值」绑定：既给出键与值，也留住每一行的原文与行号，"
                    "好让写回时没有改动的行能原样保留"
                ),
                "evidence": [
                    _ev("parser.py", "37-46", "Original（string / line）与 Binding（key / value / original / error）两个命名元组"),
                    _ev("parser.py", "14-34", "词法正则：注释、export 前缀、单/双引号值、转义序列"),
                    _ev("parser.py", "114-141", "parse_key / parse_unquoted_value / parse_value：三种取值写法"),
                    _ev("parser.py", "144-178", "parse_binding：读一条绑定，读不动就整行标 error"),
                    _ev("parser.py", "181-184", "parse_stream：把整个流逐条产出绑定"),
                ],
            },
            {
                "domain_id": "d_atom",
                "auto_name_cn": "Atom",
                "name_cn": "变量插值（POSIX 展开）",
                "role": "core",
                "objective": (
                    "把值里的 ${NAME} 与 ${NAME:-默认值} 拆成字面量与变量两类原子再求值："
                    ".env 里写的不是死字符串，最终值取决于当时的变量表"
                ),
                "evidence": [
                    _ev("variables.py", "5-15", "_posix_variable 正则：${name} 与 ${name:-default} 两种写法"),
                    _ev("variables.py", "18-26", "Atom 抽象基类：resolve(env) 是唯一的求值入口"),
                    _ev("variables.py", "48-67", "Variable.resolve：名字取不到就用默认值，默认值也没有则空串"),
                    _ev("variables.py", "70-86", "parse_variables：按正则把值切成 Literal / Variable"),
                    _ev("main.py", "294-316", "resolve_variables：override 决定环境变量与自己解析出的值谁优先"),
                ],
            },
            {
                "domain_id": "d_dot_env",
                "auto_name_cn": "系统装配（main）",
                "name_cn": "配置文件读取与回写",
                "role": "orchestrator",
                "objective": (
                    "对外提供一组文件级操作：找到 .env、读成键值表、按需载入进程环境变量，"
                    "以及改写 / 删除单个键 —— 改写走「临时文件 + 原子替换」，不跟随符号链接"
                ),
                "evidence": [
                    _ev("main.py", "75-95", "DotEnv.dict / parse：读成有序键值表，interpolate 打开时做插值"),
                    _ev("main.py", "97-110", "set_as_environment_variables：写进 os.environ，override=False 时不覆盖既有值"),
                    _ev("main.py", "138-190", "rewrite：临时文件 + os.replace，保留原文件权限位，默认不跟随符号链接"),
                    _ev("main.py", "193-250", "set_key：新增或更新一个键"),
                    _ev("main.py", "253-291", "unset_key：删除一个键"),
                    _ev("main.py", "319-385", "_walk_to_root + find_dotenv：从当前目录逐级向上找 .env"),
                    _ev("main.py", "388-472", "load_dotenv / dotenv_values：两个对外读取入口"),
                ],
            },
            {
                "domain_id": "d_cli",
                "auto_name_cn": "系统装配（cli）",
                "name_cn": "命令行工具（dotenv 命令）",
                "role": "orchestrator",
                "objective": (
                    "把「列 / 查 / 写 / 删 / 带环境跑命令」暴露成 dotenv 子命令："
                    "命令行只是同一套读写能力的入口，自己不实现文件格式"
                ),
                "evidence": [
                    _ev("cli.py", "24-35", "enumerate_env：默认取当前工作目录下的 .env"),
                    _ev("cli.py", "62-64", "cli：-f / -q / -e 三个全局选项进 ctx.obj"),
                    _ev("cli.py", "83-109", "list：四种输出格式 simple / json / shell / export"),
                    _ev("cli.py", "112-148", "set 与 get 两个子命令"),
                    _ev("cli.py", "151-167", "unset 子命令：删不掉就以退出码 1 结束"),
                    _ev("cli.py", "170-201", "run：带上 .env 的变量去跑一条外部命令"),
                    _ev("cli.py", "204-247", "run_command：win32 走 Popen，其它平台走 os.execvpe"),
                ],
            },
            {
                "domain_id": "d_i_python_dot_env",
                "auto_name_cn": "I Python Dot Env",
                "name_cn": "IPython 魔法命令（%dotenv）",
                "role": "core",
                "objective": (
                    "在 IPython / Jupyter 里注册一个 %dotenv 魔法命令：复用同一套「找 .env + 载入」逻辑，"
                    "让交互式环境也能一行加载配置"
                ),
                "evidence": [
                    _ev("ipython.py", "11-45", "IPythonDotEnv.dotenv：-o / -v / dotenv_path 三个参数，找不到文件就打印提示并返回"),
                    _ev("ipython.py", "48-50", "load_ipython_extension：注册魔法命令"),
                    _ev("__init__.py", "6-9", "包入口转发 load_ipython_extension"),
                ],
            },
            {
                "domain_id": "d_init",
                "auto_name_cn": "系统装配（__init__）",
                "name_cn": "包装配与对外接口",
                "role": "orchestrator",
                "objective": (
                    "把包内实现收敛成一组对外符号（load_dotenv / dotenv_values / get_key / set_key / "
                    "unset_key / find_dotenv），并从这里同时暴露 IPython 扩展与命令行字符串拼接"
                ),
                "evidence": [
                    _ev("__init__.py", "3", "从 .main 收进六个对外函数"),
                    _ev("__init__.py", "42-51", "__all__：对外符号的唯一清单"),
                    _ev("__init__.py", "12-39", "get_cli_string：把参数拼成一条 dotenv 命令"),
                    _ev("__main__.py", "1-6", "python -m dotenv 的入口"),
                ],
            },
        ],
        # 二级功能点（capability）级卡片**本轮不提候选**：自动切出来的那些桶是按
        # 「动词类别」切的（好几张都叫「查询/读取操作」，还有「其他能力（待归类：…）」），
        # 它们不是业务能力，给它们编目标就是编业务含义。理由写进候选清单的诚实边界一节。
        "capability_candidates": [],
        "capability_skip_reason": (
            "本项目的二级功能点是按「动词类别桶」自动切出来的（24 张里有 8 张名为「查询/读取操作」、"
            "4 张名为「其他能力（待归类：…）」），它们描述的是「一批同类函数」而不是一项业务能力。"
            "给这种桶写业务目标等于编业务含义（docs/00-index.md §3.4 禁止事项第 1 条），"
            "所以本轮**只为 6 个一级域提候选**，二级卡片继续用自动结果并如实标注 source: auto。"
        ),
        "task_candidates": [
            {
                "task_id": "dt_python_dotenv_L2_module_split",
                "type": "module_split",
                "level": "L2",
                "must_have": [
                    {
                        "key": "mh_parse_line",
                        "name_cn": "解析 .env 语法",
                        "aliases": ["解析 .env", "键值解析", ".env 解析", "语法解析"],
                        "cluster": "integrity",
                        "verb_class": "serialize",
                        "verb_cn": "解析与还原",
                        "entity": "value",
                        "entity_cn": "数据项",
                        "related_flow": "",
                        "evidence": [
                            _ev("parser.py", "144-178", "parse_binding：把一行文本读成 (key, value, original, error)"),
                            _ev("parser.py", "181-184", "parse_stream：逐行产出绑定，是解析的唯一入口"),
                            _ev("parser.py", "25-34", "单双引号与转义的处理规则都写在词法正则里"),
                        ],
                    },
                    {
                        "key": "mh_query_config",
                        "name_cn": "读取 .env 配置",
                        "aliases": ["读取配置", ".env 读取", "读取键值表", "加载配置项"],
                        "cluster": "inquiry",
                        "verb_class": "query",
                        "verb_cn": "查询与读取",
                        "entity": "config",
                        "entity_cn": "配置",
                        "related_flow": "list_values Flow",
                        "evidence": [
                            _ev("main.py", "438-472", "dotenv_values：把 .env 读成 dict（值可以是 None）"),
                            _ev("main.py", "75-95", "DotEnv.dict / DotEnv.parse：读取结果带进程内缓存"),
                            _ev("cli.py", "93-109", "list_values：读出来之后按 simple / json / shell / export 渲染"),
                        ],
                    },
                    {
                        "key": "mh_interpolate_value",
                        "name_cn": "变量插值",
                        "aliases": ["变量展开", "变量替换", "默认值回退", "POSIX 变量展开"],
                        "cluster": "inquiry",
                        "verb_class": "query",
                        "verb_cn": "求值与解析",
                        "entity": "value",
                        "entity_cn": "数据项",
                        "related_flow": "DotEnv set_as_environment_variables Flow",
                        "evidence": [
                            _ev("variables.py", "5-15", "只认 ${NAME} 与 ${NAME:-默认值} 两种写法"),
                            _ev("variables.py", "48-67", "Variable.resolve：先查环境表，取不到用默认值，再取不到给空串"),
                            _ev("main.py", "294-316", "resolve_variables：override 为真时环境变量优先，否则已解析出的值优先"),
                        ],
                    },
                    {
                        "key": "mh_find_env_file",
                        "name_cn": "查找 .env 文件位置",
                        "aliases": ["定位 .env", "查找配置文件", "向上查找 .env", "搜索 .env"],
                        "cluster": "inquiry",
                        "verb_class": "query",
                        "verb_cn": "查找与定位",
                        "entity": "file",
                        "entity_cn": "文件",
                        "related_flow": "IPythonDotEnv dotenv Flow",
                        "evidence": [
                            _ev("main.py", "337-385", "find_dotenv：按交互式 / 调试器 / 冻结等情形决定起点目录"),
                            _ev("main.py", "319-334", "_walk_to_root：从起点目录逐级向上到根"),
                            _ev("main.py", "475-487", "_is_file_or_fifo：普通文件或 FIFO 都算「找到了」"),
                        ],
                    },
                    {
                        "key": "mh_configure_env",
                        "name_cn": "载入进程环境变量",
                        "aliases": ["设置环境变量", "写入环境变量", "环境变量注入", "加载到 env"],
                        "cluster": "infrastructure",
                        "verb_class": "configure",
                        "verb_cn": "配置与装配",
                        "entity": "config",
                        "entity_cn": "配置",
                        "related_flow": "DotEnv set_as_environment_variables Flow",
                        "evidence": [
                            _ev("main.py", "388-435", "load_dotenv：本库最常用的入口，读完就写进进程环境"),
                            _ev("main.py", "97-110", "set_as_environment_variables：值为 None 的键不写入；override=False 时不覆盖已有值"),
                            _ev("main.py", "22-29", "_load_dotenv_disabled：PYTHON_DOTENV_DISABLED 为真值时整个加载直接关掉"),
                        ],
                    },
                    {
                        "key": "mh_update_value",
                        "name_cn": "写入或更新键值",
                        "aliases": ["设置键值", "修改配置项", "更新 .env 键", "新增键值"],
                        "cluster": "lifecycle",
                        "verb_class": "update",
                        "verb_cn": "更新与修改",
                        "entity": "value",
                        "entity_cn": "数据项",
                        "related_flow": "set_value Flow",
                        "evidence": [
                            _ev("main.py", "193-250", "set_key：按 quote_mode 决定加不加引号，再整文件重写"),
                            _ev("main.py", "211-216", "quote_mode 只认 always / auto / never，其它值直接报错"),
                            _ev("cli.py", "112-131", "set_value：命令行的写入口，失败以退出码 1 结束"),
                        ],
                    },
                    {
                        "key": "mh_delete_value",
                        "name_cn": "删除键值",
                        "aliases": ["移除键值", "删除配置项", "删除 .env 键", "unset 键"],
                        "cluster": "lifecycle",
                        "verb_class": "delete",
                        "verb_cn": "删除与移除",
                        "entity": "value",
                        "entity_cn": "数据项",
                        "related_flow": "unset Flow",
                        "evidence": [
                            _ev("main.py", "253-291", "unset_key：文件不存在或键不存在都返回 (None, key)，并留下告警日志"),
                            _ev("cli.py", "151-167", "unset：命令行的删入口，删不掉退出码 1"),
                        ],
                    },
                    {
                        "key": "mh_rewrite_file",
                        "name_cn": "回写文件并保住未改动的行",
                        "aliases": ["改写 .env", "重写文件", "原子替换文件", "保留原文件格式"],
                        "cluster": "lifecycle",
                        "verb_class": "update",
                        "verb_cn": "回写与替换",
                        "entity": "file",
                        "entity_cn": "文件",
                        "related_flow": "set_value Flow",
                        "evidence": [
                            _ev("main.py", "138-190", "rewrite：写到临时文件再 os.replace；成功才落盘，出错删临时文件"),
                            _ev("main.py", "150-155", "落盘前把原文件的权限位记下来，替换后 os.chmod 还原"),
                            _ev("main.py", "236-248", "未命中的行用 mapping.original.string 原样写回，缺尾换行时补一个"),
                        ],
                    },
                ],
                "required_relations": [
                    {
                        "from_key": "mh_query_config",
                        "to_key": "mh_interpolate_value",
                        "reason_cn": (
                            "读出来的值还是原文，要经过 ${VAR} 展开才是最终值：读取依赖插值"
                            "（代码事实：main.py:82-85 DotEnv.dict() 调用 resolve_variables）"
                        ),
                        "evidence": [
                            _ev("main.py", "82-88", "dict()：interpolate 打开时才走 resolve_variables，否则直接 OrderedDict(raw_values)"),
                            _ev("main.py", "393", "load_dotenv(interpolate=True)：默认就是要插值的"),
                        ],
                    },
                    {
                        "from_key": "mh_update_value",
                        "to_key": "mh_parse_line",
                        "reason_cn": (
                            "改一个键不是就地改一行，而是把原文件逐行重新解析一遍再重写："
                            "写键依赖解析（代码事实：main.py:238 set_key 里 for mapping in parse_stream(source)）"
                        ),
                        "evidence": [
                            _ev("main.py", "238-244", "set_key 用 parse_stream 逐行读原文，命中的行换成新行、其余原样写回"),
                            _ev("main.py", "279-283", "unset_key 同样先 parse_stream 再决定哪些行留下"),
                        ],
                    },
                ],
                "required_edge_cases": [
                    {
                        "text": "文件不存在",
                        "why_cn": "文件不存在时整个库必须还能用：读退化成空表、删只告警、找按参数决定抛错还是返回空串",
                        "evidence": [
                            _ev("main.py", "159-161", "rewrite：FileNotFoundError 时改用空流，等于从零新建"),
                            _ev("main.py", "270-272", "unset_key：文件不存在就告警并返回 None"),
                            _ev("main.py", "382-385", "find_dotenv：找不到时按 raise_error_if_not_found 抛 IOError 或返回空串"),
                        ],
                    },
                    {
                        "text": "没有值",
                        "why_cn": "「只有键名没有等号」是 .env 的合法写法，必须与「键不存在」区分开",
                        "evidence": [
                            _ev("parser.py", "158-162", "没有 = 号时 value 记为 None（而不是空串）"),
                            _ev("main.py", "107-108", "值为 None 的键不写进 os.environ"),
                            _ev("main.py", "448-450", "dotenv_values 文档：foo=bar 得 'bar'，只写 foo 得 None"),
                        ],
                    },
                ],
                "forbidden_merges": [
                    {
                        "a": "mh_configure_env",
                        "b": "mh_query_config",
                        "reason_cn": (
                            "一个是「把值写进进程全局环境」的副作用操作，一个是「把 .env 读成一张表」的纯查询："
                            "变化原因不同（加载与覆盖策略变了不该动读取逻辑），合并之后任何一次「只想读一下 .env」"
                            "都会顺带改进程环境"
                        ),
                        "evidence": [
                            _ev("main.py", "97-110", "set_as_environment_variables：真的写 os.environ"),
                            _ev("main.py", "75-95", "dict()/parse()：只读文件，不碰环境"),
                        ],
                    },
                ],
                "acceptable_alternatives": [
                    {
                        "alternative_id": "alt_parse_standalone",
                        "name_cn": "解析独立成模块",
                        "separate_keys": ["mh_parse_line", "mh_query_config"],
                        "evidence": [
                            _ev("parser.py", "144-184", "解析器自成一份：只依赖正则与流，不认识 dict、也不认识文件系统"),
                        ],
                    },
                    {
                        "alternative_id": "alt_parse_merged",
                        "name_cn": "解析并入读取",
                        "merge_keys": ["mh_parse_line", "mh_query_config"],
                        "evidence": [
                            _ev("main.py", "91-95", "DotEnv.parse 只做一层 for 循环转手调 parse_stream，样式上确实贴近「读取」"),
                        ],
                    },
                ],
                # 权重刻意不写：唯一来源是 engine/lexicon/design_dimensions.json，
                # 在这里再写一份等于出现第二份定义（docs/02 §9.2）。
                "notes": [
                    "题干与场景刻意不写：用 engine/lexicon/design_tasks.json 里 module_split 的模板，避免出现第二份题干定义。",
                    "8 项必备能力、2 条必备依赖、2 个必备边界、1 条禁止合并、2 条可接受替代结构、6 条域目标 —— 全部需要人逐条确认。",
                ],
            }
        ],
    }
}


# ===========================================================================
# 证据字符串解析与校验
# ===========================================================================

_ANNOT_SPLIT_RE = re.compile(r"[（(]")
_SPEC_HEAD_RE = re.compile(r"^(?P<file>[^:：]+?\.py)\s*[:：]\s*(?P<rest>.+)$")
_RANGE_RE = re.compile(r"^(?P<a>\d+)\s*(?:[-–~]\s*(?P<b>\d+))?$")


def parse_evidence_string(raw: str) -> Tuple[List[Tuple[str, int, int]], str]:
    """把 ``文件:行号（说明）`` 解析成 ``[(文件, 起, 止), ...]``。

    支持这些写法（与仓库里已有的两份种子一致）：

    - ``main.py:388-435（load_dotenv）``
    - ``__init__.py:3``
    - ``equipment_manager.py:84、:98（借出 / 归还时的状态回写）``

    :returns: ``(片段列表, 错误信息)``；解析失败时片段为空、错误信息非空。
    """
    text = str(raw or "").strip()
    if not text:
        return [], "证据字符串为空"
    # 丢掉第一个括号之后的说明文字（说明不参与行号解析）
    text = _ANNOT_SPLIT_RE.split(text, maxsplit=1)[0].strip()
    if not text:
        return [], f"证据里只有说明、没有 文件:行号：{raw!r}"

    spans: List[Tuple[str, int, int]] = []
    current_file = ""
    for token in re.split(r"[、,，;；]\s*", text):
        token = token.strip()
        if not token:
            continue
        head = _SPEC_HEAD_RE.match(token)
        if head:
            current_file = head.group("file").strip().replace("\\", "/")
            rest = head.group("rest").strip()
        elif token[0] in ":：":
            if not current_file:
                return [], f"行号片段 {token!r} 之前没有出现文件名：{raw!r}"
            rest = token[1:].strip()
        else:
            return [], f"无法解析的证据片段 {token!r}：{raw!r}"

        found = _RANGE_RE.match(rest)
        if not found:
            return [], f"无法解析的行号 {rest!r}（应为 N 或 N-M）：{raw!r}"
        start = int(found.group("a"))
        end = int(found.group("b") or found.group("a"))
        if end < start:
            return [], f"行号区间倒置（{start}-{end}）：{raw!r}"
        spans.append((current_file, start, end))

    if not spans:
        return [], f"没有解析出任何 文件:行号：{raw!r}"
    return spans, ""


def _project_lines(project_dir: Path, file_rel: str) -> Tuple[Optional[List[str]], str]:
    """读项目内的一个源文件；返回 ``(行列表, 错误)``。"""
    if not file_rel or file_rel.startswith("/") or ".." in file_rel.split("/"):
        return None, f"证据路径必须是项目内相对路径：{file_rel!r}"
    path = project_dir / file_rel
    if not path.is_file():
        return None, f"证据指向的文件不存在：{file_rel}"
    try:
        return path.read_text(encoding="utf-8").splitlines(), ""
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"读不了证据文件 {file_rel}：{type(exc).__name__}"


def check_evidence_text(project_dir: Path, raw: str) -> List[str]:
    """校验一条证据字符串：能解析、文件在、行号在范围内、指向的不是空白。"""
    spans, error = parse_evidence_string(raw)
    if error:
        return [error]
    problems: List[str] = []
    for file_rel, start, end in spans:
        lines, read_error = _project_lines(project_dir, file_rel)
        if read_error:
            problems.append(read_error)
            continue
        assert lines is not None
        total = len(lines)
        if start < 1 or end > total or total == 0:
            problems.append(
                f"行号超出文件范围：{file_rel}:{start}-{end}（该文件共 {total} 行）"
            )
            continue
        if not any(lines[index].strip() for index in range(start - 1, end)):
            problems.append(f"指向的全是空行：{file_rel}:{start}-{end}")
    return problems


# ===========================================================================
# 候选表自检
# ===========================================================================

def _load_json(path: Path) -> Tuple[Optional[dict], str]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return None, f"文件不存在：{path}"
    except (OSError, ValueError) as exc:
        return None, f"读不了 / 解析不了 {path}：{type(exc).__name__}: {exc}"
    return (data if isinstance(data, dict) else None), ""


def _clusters() -> List[str]:
    data = _load_json(REPO_ROOT / "engine" / "lexicon" / "clusters.json")[0] or {}
    return sorted(str(key) for key in (data.get("clusters") or {}))


class Checker:
    """极简检查器：只记「通过 / 失败」，失败时打印原因。"""

    def __init__(self) -> None:
        self.rows: List[Tuple[str, bool, str]] = []

    def check(self, name: str, problems: Sequence[str], note: str = "") -> None:
        self.rows.append((name, not problems, note or ""))
        mark = "PASS" if not problems else "FAIL"
        print(f"  [{mark}] {name}" + (f"  — {note}" if note else ""))
        for problem in problems:
            print(f"         · {problem}")

    @property
    def failed(self) -> int:
        return sum(1 for _, ok, _ in self.rows if not ok)

    @property
    def total(self) -> int:
        return len(self.rows)


def check_candidates(entry: Dict[str, Any], project_dir: Path, graph: Dict[str, Any]) -> List[str]:
    """候选表自检：证据能指到东西、domain_id / flow / cluster 都真的存在。"""
    problems: List[str] = []
    domain_ids = {str(item.get("domain_id")) for item in graph.get("domains") or []}
    flow_names = {str(item.get("name_cn")) for item in graph.get("flows") or []}
    clusters = set(_clusters())

    for item in entry.get("domain_candidates") or []:
        domain_id = str(item.get("domain_id") or "")
        if domain_id not in domain_ids:
            problems.append(f"域候选 {domain_id} 不在自动图谱的域清单里（自动结果里没有这个域）")
        if not str(item.get("objective") or "").strip():
            problems.append(f"域候选 {domain_id} 的 objective 为空（宁可不出候选，也不要给空目标）")
        evidence = item.get("evidence") or []
        if not evidence:
            problems.append(f"域候选 {domain_id} 没有任何源码证据")
        for raw in evidence:
            for problem in check_evidence_text(project_dir, _ev_text(raw)):
                problems.append(f"域候选 {domain_id}：{problem}")

    for task in entry.get("task_candidates") or []:
        task_id = str(task.get("task_id") or "")
        must_have = task.get("must_have") or []
        keys = [str(item.get("key") or "") for item in must_have]
        if len(set(keys)) != len(keys):
            problems.append(f"{task_id}：must_have 的 key 有重复")
        pairs = [(str(item.get("verb_class") or ""), str(item.get("entity") or "")) for item in must_have]
        if len(set(pairs)) != len(pairs):
            duplicated = sorted({pair for pair in pairs if pairs.count(pair) > 1})
            problems.append(f"{task_id}：(verb_class, entity) 重复 {duplicated}")
        for item in must_have:
            key = str(item.get("key") or "")
            if str(item.get("cluster") or "") not in clusters:
                problems.append(f"{task_id}/{key}：cluster {item.get('cluster')!r} 不是 clusters.json 的 key")
            flow = str(item.get("related_flow") or "")
            if flow and flow not in flow_names:
                problems.append(f"{task_id}/{key}：related_flow {flow!r} 不是该项目的真实流程名")
            if not item.get("evidence"):
                problems.append(f"{task_id}/{key}：没有任何源码证据")
            for raw in item.get("evidence") or []:
                for problem in check_evidence_text(project_dir, _ev_text(raw)):
                    problems.append(f"{task_id}/{key}：{problem}")

        for item in task.get("required_relations") or []:
            for field in ("from_key", "to_key"):
                if str(item.get(field) or "") not in keys:
                    problems.append(f"{task_id}：必备依赖的 {field}={item.get(field)!r} 不在 must_have 里")
            if not item.get("evidence"):
                problems.append(f"{task_id}：必备依赖 {item.get('from_key')}→{item.get('to_key')} 没有证据")
            for raw in item.get("evidence") or []:
                for problem in check_evidence_text(project_dir, _ev_text(raw)):
                    problems.append(f"{task_id}：必备依赖证据 {problem}")

        for item in task.get("required_edge_cases") or []:
            text = str(item.get("text") or "")
            if not text.strip():
                problems.append(f"{task_id}：必备边界文本为空")
            if not item.get("evidence"):
                problems.append(f"{task_id}：必备边界 {text!r} 没有证据")
            for raw in item.get("evidence") or []:
                for problem in check_evidence_text(project_dir, _ev_text(raw)):
                    problems.append(f"{task_id}：必备边界 {text!r} 证据 {problem}")

        for item in task.get("forbidden_merges") or []:
            for field in ("a", "b"):
                if str(item.get(field) or "") not in keys:
                    problems.append(f"{task_id}：禁止合并的 {field}={item.get(field)!r} 不在 must_have 里")
            if not item.get("evidence"):
                problems.append(f"{task_id}：禁止合并项没有证据")
            for raw in item.get("evidence") or []:
                for problem in check_evidence_text(project_dir, _ev_text(raw)):
                    problems.append(f"{task_id}：禁止合并证据 {problem}")

        for item in task.get("acceptable_alternatives") or []:
            referenced = [str(key) for key in (item.get("merge_keys") or item.get("separate_keys") or [])]
            for key in referenced:
                if key not in keys:
                    problems.append(f"{task_id}：替代结构 {item.get('alternative_id')} 引用了不存在的 key {key!r}")
            if not item.get("evidence"):
                problems.append(f"{task_id}：替代结构 {item.get('alternative_id')} 没有证据")
            for raw in item.get("evidence") or []:
                for problem in check_evidence_text(project_dir, _ev_text(raw)):
                    problems.append(f"{task_id}：替代结构证据 {problem}")

    return problems


# ===========================================================================
# 已落盘种子的证据回指自检
# ===========================================================================

def check_graph_seed(seed_path: Path, project_dir: Path, entry: Dict[str, Any]) -> List[str]:
    """校验 ``business_graph.seed.json``：条目有证据、证据能指到东西、域都存在。"""
    problems: List[str] = []
    if not seed_path.is_file():
        print(f"  [SKIP] 种子图谱还没落盘：{seed_path}")
        return problems

    data, error = _load_json(seed_path)
    if error:
        return [error]
    assert data is not None

    evidence = data.get("_evidence") or {}
    candidate_ids = {str(item.get("domain_id")) for item in entry.get("domain_candidates") or []}
    candidate_ids |= {str(item.get("capability_id")) for item in entry.get("capability_candidates") or []}
    if not isinstance(evidence, dict):
        return ["顶层 _evidence 必须是一个对象"]

    nodes: Dict[str, Dict[str, Any]] = {}
    for item in data.get("domains") or []:
        if isinstance(item, dict) and item.get("domain_id"):
            nodes[str(item["domain_id"])] = item
    for key, item in (data.get("module_cards") or {}).items():
        if isinstance(item, dict):
            nodes.setdefault(str(key), item)

    for node_id in sorted(nodes):
        raw = evidence.get(node_id)
        if not raw:
            problems.append(f"{node_id} 没有 _evidence 条目（无出处的条目不许落盘）")
            continue
        if node_id not in candidate_ids:
            problems.append(
                f"{node_id} 不在候选表里（要么删掉，要么把它加进 scripts/export_seed_candidates.py 并给出源码证据）"
            )
        for text in raw if isinstance(raw, list) else [raw]:
            for problem in check_evidence_text(project_dir, str(text)):
                problems.append(f"{node_id}：{problem}")

    for node_id, card in sorted((data.get("module_cards") or {}).items()):
        if not isinstance(card, dict):
            continue
        if not str(card.get("objective") or "").strip():
            problems.append(f"module_cards[{node_id}] 的 objective 为空（域目标填在空里等于没填）")
        confidence = str(card.get("objective_confidence") or "")
        if not confidence:
            problems.append(
                f"module_cards[{node_id}] 没有显式写 objective_confidence"
                "（它不在 LOCKABLE_FIELDS 里，写成空串等于没填，见 docs/02 §8.8）"
            )
        elif confidence not in (CONFIRMED, PENDING):
            problems.append(f"module_cards[{node_id}] 的 objective_confidence={confidence!r} 不是 {CONFIRMED} / {PENDING}")

    return problems


def _seed_task_keys(task: Dict[str, Any]) -> List[str]:
    return [str(item.get("key") or "") for item in task.get("must_have") or [] if isinstance(item, dict)]


def check_task_seed(
    seed_path: Path,
    project_dir: Path,
    project_id: str,
    entry: Dict[str, Any],
) -> List[str]:
    """校验 ``design_tasks.seed.json`` 里该项目那一段。"""
    problems: List[str] = []
    if not seed_path.is_file():
        print(f"  [SKIP] 设计任务种子还没落盘：{seed_path}")
        return problems

    data, error = _load_json(seed_path)
    if error:
        return [error]
    assert data is not None

    seeds = (data.get("tasks") or {}).get(project_id)
    if not seeds:
        print(f"  [SKIP] {SEED_TASKS_NAME} 里还没有 {project_id} 那一段")
        return problems

    candidate_tasks = {str(item.get("task_id")): item for item in entry.get("task_candidates") or []}

    for seed in seeds:
        task_id = str(seed.get("task_id") or "")
        candidate = candidate_tasks.get(task_id)
        if candidate is None:
            problems.append(f"任务 {task_id} 不在候选表里（没有出处的任务不许落盘）")
            continue

        must_have_keys = _seed_task_keys(seed)
        candidate_keys = [str(item.get("key")) for item in candidate.get("must_have") or []]
        for key in must_have_keys:
            if key not in candidate_keys:
                problems.append(f"{task_id}：must_have 里的 {key} 不在候选表里（没有出处的条目不许落盘）")

        pairs = [(str(item.get("verb_class") or ""), str(item.get("entity") or "")) for item in seed.get("must_have") or []]
        if len(set(pairs)) != len(pairs):
            problems.append(f"{task_id}：(verb_class, entity) 有重复 {sorted({p for p in pairs if pairs.count(p) > 1})}")

        clusters = set(_clusters())
        for item in seed.get("must_have") or []:
            if str(item.get("cluster") or "") not in clusters:
                problems.append(f"{task_id}/{item.get('key')}：cluster {item.get('cluster')!r} 不是 clusters.json 的 key")

        evidence = seed.get("_evidence") or {}
        if not isinstance(evidence, dict):
            problems.append(f"{task_id}：_evidence 必须是一个对象")
            evidence = {}
        for key in must_have_keys:
            raw = evidence.get(key)
            if not raw:
                problems.append(f"{task_id}/{key} 没有 _evidence 条目（无出处的 must_have 不许落盘）")
                continue
            for text in raw if isinstance(raw, list) else [raw]:
                for problem in check_evidence_text(project_dir, str(text)):
                    problems.append(f"{task_id}/{key}：{problem}")

        # 额外三类内容的证据
        extra = seed.get("_evidence_other") or {}
        expected_extra: List[Tuple[str, List[str]]] = []
        for item in seed.get("required_relations") or []:
            expected_extra.append((f"relation:{item.get('from_key')}->{item.get('to_key')}", []))
        for text in seed.get("required_edge_cases") or []:
            expected_extra.append((f"edge_case:{text}", []))
        for item in seed.get("forbidden_merges") or []:
            expected_extra.append((f"forbidden:{item.get('a')}+{item.get('b')}", []))
        for item in seed.get("acceptable_alternatives") or []:
            expected_extra.append((f"alternative:{item.get('alternative_id')}", []))
        for label, _ in expected_extra:
            raw = extra.get(label)
            if not raw:
                problems.append(f"{task_id}/{label} 没有 _evidence_other 条目（无出处的条目不许落盘）")
                continue
            for text in raw if isinstance(raw, list) else [raw]:
                for problem in check_evidence_text(project_dir, str(text)):
                    problems.append(f"{task_id}/{label}：{problem}")

        referenced = set()
        for item in seed.get("required_relations") or []:
            referenced.add(str(item.get("from_key")))
            referenced.add(str(item.get("to_key")))
        for item in seed.get("forbidden_merges") or []:
            referenced.add(str(item.get("a")))
            referenced.add(str(item.get("b")))
        for item in seed.get("acceptable_alternatives") or []:
            referenced.update(str(key) for key in (item.get("merge_keys") or item.get("separate_keys") or []))
        dangling = sorted(referenced - set(must_have_keys))
        if dangling:
            problems.append(f"{task_id}：三份清单引用了不存在的 key {dangling}")

        status = str(seed.get("review_status") or "")
        if status == CONFIRMED and not str(seed.get("reviewed_by") or "").strip():
            problems.append(f"{task_id}：标了 confirmed 却没有 reviewed_by（谁来确认的必须写下来）")

    return problems


# ===========================================================================
# 候选清单打印
# ===========================================================================

def _confirmation_status(entry: Dict[str, Any], project_dir: Path, project_id: str) -> Tuple[str, List[str]]:
    """如实报告：这两份种子文件当前有没有人确认过。"""
    lines: List[str] = []
    any_confirmed = False

    graph_path = project_dir / SEED_GRAPH_NAME
    if graph_path.is_file():
        data = _load_json(graph_path)[0] or {}
        cards = data.get("module_cards") or {}
        confirmed = [key for key, card in cards.items() if isinstance(card, dict) and str(card.get("objective_confidence")) == CONFIRMED]
        pending = [key for key, card in cards.items() if isinstance(card, dict) and str(card.get("objective_confidence")) != CONFIRMED]
        reviewer = str(data.get("reviewed_by") or "").strip()
        any_confirmed = any_confirmed or bool(confirmed)
        lines.append(f"  · 种子图谱：已确认 {len(confirmed)} 条 / 未确认 {len(pending)} 条；reviewed_by = {reviewer or '（空）'}")
    else:
        lines.append("  · 种子图谱：还没落盘")

    seed_tasks = _load_json(REPO_ROOT / "engine" / "lexicon" / SEED_TASKS_NAME)[0] or {}
    seeds = (seed_tasks.get("tasks") or {}).get(project_id) or []
    if seeds:
        for seed in seeds:
            status = str(seed.get("review_status") or "")
            reviewer = str(seed.get("reviewed_by") or "").strip()
            any_confirmed = any_confirmed or status == CONFIRMED
            lines.append(
                f"  · 设计任务种子 {seed.get('task_id')}：review_status = {status or '（空）'}；"
                f"reviewed_by = {reviewer or '（空）'}"
            )
    else:
        lines.append("  · 设计任务种子：还没落盘")

    return ("已有人确认" if any_confirmed else "⚠️ 无人确认"), lines


def print_candidates(project_id: str, entry: Dict[str, Any], project_dir: Path, graph: Dict[str, Any]) -> None:
    """打印候选清单（人工确认用）。"""
    print("=" * 78)
    print(f"教师种子候选清单（人工确认用） · 项目 {project_id}")
    print("=" * 78)
    print(f"项目路径          ：{entry.get('project')}")
    print(f"自动图谱          ：{len(graph.get('domains') or [])} 个一级域 / "
          f"{len([k for k in (graph.get('module_cards') or {}) if k.startswith('c_')])} 个二级功能点 / "
          f"{len(graph.get('flows') or [])} 条流程")
    print(f"图谱 source_hash  ：{graph.get('source_hash')}")
    print()
    print("⚠️ 纪律（docs/02 §9.1 第 ③ 条）：下面每一条都是 **AI 起草的候选**，逐条带源码出处。")
    print("   最终 must_have 与域目标由**人逐条确认后**才允许落盘；")
    print("   确认之前不许写 objective_confidence / review_status = \"confirmed\"。")
    print()

    status, status_lines = _confirmation_status(entry, project_dir, project_id)
    print(f"当前确认状态：{status}")
    for line in status_lines:
        print(line)
    print()

    print("-" * 78)
    print("一、一级业务域候选 → validation/python_dotenv/business_graph.seed.json")
    print("-" * 78)
    for index, item in enumerate(entry.get("domain_candidates") or [], start=1):
        print(f"[{index}] {item['domain_id']}（自动域名：{item.get('auto_name_cn')}；role={item.get('role')}）")
        print(f"    候选中文名：{item.get('name_cn')}")
        print(f"    候选目标　：{item.get('objective')}")
        print("    源码证据　：")
        for raw in item.get("evidence") or []:
            print(f"      · {_ev_text(raw)}")
        print()

    skip_reason = str(entry.get("capability_skip_reason") or "")
    if skip_reason:
        print("-" * 78)
        print("二、二级功能点候选 → 本轮不提（诚实边界）")
        print("-" * 78)
        print(f"    {skip_reason}")
        print()

    print("-" * 78)
    print(f"三、设计任务候选 → engine/lexicon/{SEED_TASKS_NAME} 的 {project_id} 段")
    print("-" * 78)
    for task in entry.get("task_candidates") or []:
        print(f"任务 {task.get('task_id')}（type={task.get('type')} / level={task.get('level')}）")
        print(f"  必备能力 {len(task.get('must_have') or [])} 项：")
        for item in task.get("must_have") or []:
            print(f"    · {item.get('key')}｜{item.get('name_cn')}｜cluster={item.get('cluster')}｜"
                  f"({item.get('verb_class')}, {item.get('entity')})｜flow={item.get('related_flow') or '（无）'}")
            print(f"        别名：{'、'.join(item.get('aliases') or [])}")
            for raw in item.get("evidence") or []:
                print(f"        证据：{_ev_text(raw)}")
        print(f"  必备依赖 {len(task.get('required_relations') or [])} 条：")
        for item in task.get("required_relations") or []:
            print(f"    · {item.get('from_key')} → {item.get('to_key')}：{item.get('reason_cn')}")
            for raw in item.get("evidence") or []:
                print(f"        证据：{_ev_text(raw)}")
        print(f"  必备边界 {len(task.get('required_edge_cases') or [])} 个（子串匹配，学生文本里出现才算命中）：")
        for item in task.get("required_edge_cases") or []:
            print(f"    · {item.get('text')!r}：{item.get('why_cn')}")
            for raw in item.get("evidence") or []:
                print(f"        证据：{_ev_text(raw)}")
        print(f"  禁止合并项 {len(task.get('forbidden_merges') or [])} 条：")
        for item in task.get("forbidden_merges") or []:
            print(f"    · {item.get('a')} ✕ {item.get('b')}：{item.get('reason_cn')}")
            for raw in item.get("evidence") or []:
                print(f"        证据：{_ev_text(raw)}")
        print(f"  可接受替代结构 {len(task.get('acceptable_alternatives') or [])} 条：")
        for item in task.get("acceptable_alternatives") or []:
            keys = item.get("merge_keys") or item.get("separate_keys")
            print(f"    · {item.get('alternative_id')}（{item.get('name_cn')}）：{keys}")
            for raw in item.get("evidence") or []:
                print(f"        证据：{_ev_text(raw)}")
        for note in task.get("notes") or []:
            print(f"  注意：{note}")
        print()

    print("=" * 78)
    print(f"人工确认状态：{status}")
    if status != "已有人确认":
        print("→ 本轮**没有任何人确认过**这份候选清单。")
        print("→ 正确交付是「候选清单 + 明确标注无人确认」，不许把 AI 起草的条目标成 confirmed。")
    print("自检：python scripts/export_seed_candidates.py --check")
    print("=" * 78)


# ===========================================================================
# 入口
# ===========================================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="教师种子备料：候选清单 + 逐项源码证据（WO-05）")
    parser.add_argument("--project", default=DEFAULT_PROJECT, help=f"被分析的项目目录（默认 {DEFAULT_PROJECT}）")
    parser.add_argument("--check", action="store_true", help="做证据回指自检（候选表 + 已落盘的种子）")
    args = parser.parse_args()

    project_rel = str(args.project).replace("\\", "/").strip("/")
    project_dir = (REPO_ROOT / project_rel).resolve()
    project_id = project_dir.name

    entry = CANDIDATES.get(project_id)
    if entry is None:
        print(f"候选表里没有 {project_id} 这一项（脚本里 CANDIDATES 只有 {sorted(CANDIDATES)}）")
        return 1
    if not project_dir.is_dir():
        print(f"项目目录不存在：{project_dir}")
        return 1

    from engine.project_analyzer import ProjectAnalyzer

    graph = ProjectAnalyzer().analyze(str(project_dir)).to_dict().get("business_graph") or {}

    if not args.check:
        print_candidates(project_id, entry, project_dir, graph)
        return 0

    print("=" * 78)
    print(f"证据回指自检（WO-05） · 项目 {project_id}")
    print("=" * 78)
    checker = Checker()

    candidate_problems = check_candidates(entry, project_dir, graph)
    evidence_count = sum(len(item.get("evidence") or []) for item in entry.get("domain_candidates") or [])
    for task in entry.get("task_candidates") or []:
        evidence_count += sum(len(item.get("evidence") or []) for item in task.get("must_have") or [])
        evidence_count += sum(len(item.get("evidence") or []) for item in task.get("required_relations") or [])
        evidence_count += sum(len(item.get("evidence") or []) for item in task.get("required_edge_cases") or [])
        evidence_count += sum(len(item.get("evidence") or []) for item in task.get("forbidden_merges") or [])
        evidence_count += sum(len(item.get("evidence") or []) for item in task.get("acceptable_alternatives") or [])
    checker.check(
        "候选表：每条候选都带能指到真实位置的证据",
        candidate_problems,
        f"{len(entry.get('domain_candidates') or [])} 条域候选 + "
        f"{sum(len(t.get('must_have') or []) for t in entry.get('task_candidates') or [])} 条必备能力候选、"
        f"共 {evidence_count} 条证据",
    )

    checker.check(
        f"种子图谱：{SEED_GRAPH_NAME} 每条条目都有能指到真实位置的 _evidence",
        check_graph_seed(project_dir / SEED_GRAPH_NAME, project_dir, entry),
    )
    checker.check(
        f"设计任务种子：{SEED_TASKS_NAME} 里 {project_id} 那一段同上",
        check_task_seed(REPO_ROOT / "engine" / "lexicon" / SEED_TASKS_NAME, project_dir, project_id, entry),
    )

    print()
    print(f"证据回指自检：{'全部通过' if not checker.failed else f'失败 {checker.failed} 项'}（共 {checker.total} 项）")
    print("=" * 78)
    return 1 if checker.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
