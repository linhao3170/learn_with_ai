"""
验收报告生成器（README 阶段 0 · 让「最近一次测试总数」只有一个来源）

为什么需要它
------------
README 里手抄了 13 个不同的「最近一次测试总数」、共 108 处（`14/14` 10 处、
`99/99` 13 处、`40/40` 13 处…），其中 4 个已淘汰的值（`13/13` / `31/31` /
`41/41` / `71/71`）仍留在正文 13 处。后果是**同一份文档里同一个脚本有两个数字**
（§17.1 `14/14` vs §17.2 `13/13`）—— 这不是笔误，是"数字靠人手抄"这个做法本身
必然的产物。

本脚本把数字从人手里拿走：

1. **在同一个进程内**逐个跑验收脚本（不启动子进程、不用管道捕获输出 ——
   沙箱下管道捕获原生程序输出会被拒绝，见 README §19.5，做法与
   ``verify_sprint0.py`` 一致）；
2. 把每个脚本的**屏幕输出**解析成结构化结果，写进
   ``validation/acceptance_latest.json``（机器读）与
   ``validation/acceptance_latest.md``（人读）；
3. 文档以后只允许写「见验收报告」，**不许手抄数字**；
   ``scripts/verify_docs.py`` 会检查文档里的数字与这份报告是否一致。

默认只跑「只读组」
------------------
默认组（``engine``）里的脚本**不写任何仓库产物**，只读快照与源码。以下三组默认
跑不了或不该自动跑，都带明写的原因，不会被静默跳过：

| 组 | 为什么默认不跑 |
|---|---|
| ``backend`` | 需要 8000 端口上的 uvicorn（`test_logic_platform_api.py`） |
| ``node`` | 需要 node + jsdom/走查 bundle（`browser_clickthrough.mjs`）；`vite build` 另有 `spawn EPERM`（§19.5） |
| ``manual`` | 要么**会覆盖人工填过的判定**（`validate_business_graph.py --emit-review`），要么退出码是验收语义而非失败（`graph_review_report.py` 未填即 1，§20.3 ⑤） |
| ``order-trap`` | 旧管线冒烟**会覆盖学生快照**（§19.5 顺序陷阱），必须按「产物脚本 → 验收 → 冒烟 → 再跑一次产物脚本」的顺序人工执行 |

用法
----
    python scripts/build_acceptance_report.py                 # 只读组，写两份报告
    python scripts/build_acceptance_report.py --list           # 只列出会跑什么，不跑
    python scripts/build_acceptance_report.py --only verify_sprint0
    python scripts/build_acceptance_report.py --with-backend   # 需要后端已启动
    python scripts/build_acceptance_report.py --with-order-trap

**完整验收（推荐口径，17 条全跑）**：:

    python scripts/build_acceptance_report.py --with-backend --with-node

`--with-node` 会跑 4 条走查：两个项目（自造样本 + 真实第三方）× 在线 / 离线。
它需要后端在 8000 端口在线、以及 `.smoke-dist` 走查 bundle 已构建
（`vite build --config vite.smoke.config.js`，改了 `.vue` 必须重建）。

退出码：0 = 跑到的检查全部通过；1 = 有失败项（与其它验收脚本一致）。
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as _dt
import importlib
import io
import inspect
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import traceback
from dataclasses import dataclass, field
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # pragma: no cover
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

REPORT_VERSION = "1.0"
DEFAULT_JSON = "validation/acceptance_latest.json"
DEFAULT_MD = "validation/acceptance_latest.md"

DEMO_PROJECT = "sample_projects/lab_safety_assistant"
THIRD_PARTY_PROJECT = "validation/python_dotenv"

#: 走查的 ``--project`` 要的是**项目 id**（会被拼进 `/api/projects/<id>/...`、
#: 并和 DOM 文本比对），不是目录路径 —— 传 `validation/python_dotenv` 会让
#: 按 id 的断言和快照路径全部落空。所以这里单独取目录名。
DEMO_PROJECT_ID = Path(DEMO_PROJECT).name
THIRD_PARTY_PROJECT_ID = Path(THIRD_PARTY_PROJECT).name


# ============================================================
# 检查清单（唯一来源：文档不再自己抄数字）
# ============================================================

@dataclass(frozen=True)
class Check:
    """一个验收脚本条目。

    ``metrics`` 是「非 X/Y 形式但仍要被文档引用的数字」的正则抓取（例如
    `扫描 62 个 .py 文件`、`引擎命中 0 条`）。抓到的值同样进报告，
    ``verify_docs.py`` 会拿它核对文档里写死的那些整数。

    ``kind`` 决定**怎么跑**，必须显式写出来，不许靠猜：

    - ``"python"``（默认）：``module`` 是 Python 模块，``main()`` 在**本进程内**跑；
    - ``"node"``：``script`` 是**外部运行时**命令（argv[0] 必须是 node），
      走 ``run_node()`` 起子进程。这类条目 ``module`` 留空 ——
      以前 ``module`` 一空就必然报 ERROR（"没有 Python 模块"），
      结果 `--with-node` 加进来只会得到一条假失败，把走查 109/55 条断言挡在报告之外。
    """

    id: str
    title: str
    script: str
    module: str
    argvs: tuple[tuple[str, ...], ...] = ((),)
    group: str = "engine"
    metrics: tuple[tuple[str, str], ...] = ()
    note: str = ""
    kind: str = "python"


#: ``(key, 正则)`` —— 一律取第 1 个捕获组，且取**最后一次**匹配（脚本结尾打印的是最终值）
SCAN_ENGINE_FILES = ("engine_scanned_files", r"\[引擎\] 扫描 (\d+) 个")
ENGINE_HITS = ("engine_hits", r"引擎命中[:：]\s*(\d+)")
FRONTEND_SCANNED = ("frontend_scanned_files", r"\[前端\] 扫描 (\d+) 个")
FRONTEND_HITS = ("frontend_hits", r"前端命中[:：]\s*(\d+)")

ENGINE_CHECKS: tuple[Check, ...] = (
    Check(
        id="verify_sprint0",
        title="Sprint 0 总验收（A1–A11）",
        script="scripts/verify_sprint0.py",
        module="scripts.verify_sprint0",
    ),
    Check(
        id="business_graph",
        title="业务图谱引擎测试（4 个项目 + 种子合并）",
        script="scripts/test_business_graph.py",
        module="scripts.test_business_graph",
        note="该脚本不打印总计，报告里的合计由各项目 `N/M 项通过` 逐行相加",
    ),
    Check(
        id="design_rubric",
        title="设计层六维评审",
        script="scripts/test_design_rubric.py",
        module="scripts.test_design_rubric",
    ),
    Check(
        id="design_seed",
        title="教师设计任务种子",
        script="scripts/test_design_seed.py",
        module="scripts.test_design_seed",
    ),
    Check(
        id="teaching_coverage",
        title="阶段一「项目认知」覆盖度比对器",
        script="scripts/test_teaching_coverage.py",
        module="scripts.test_teaching_coverage",
    ),
    Check(
        id="teaching_card_coverage",
        title="阶段二「模块卡片学习」事实覆盖比对器",
        script="scripts/test_teaching_card_coverage.py",
        module="scripts.test_teaching_card_coverage",
    ),
    Check(
        id="training_questions",
        title="训练题第 2/3/4 关「一关多题」",
        script="scripts/test_training_questions.py",
        module="scripts.test_training_questions",
    ),
    Check(
        id="logic_platform",
        title="业务逻辑分析平台自测（用已建快照，不现场重跑分析）",
        script="scripts/test_logic_platform.py",
        module="scripts.test_logic_platform",
        note="不加 --live：现场重跑分析很慢，且它不是验收口径",
    ),
    Check(
        id="determinism_same_process",
        title="确定性：同进程双跑逐字段一致",
        script="scripts/check_determinism.py",
        module="scripts.check_determinism",
    ),
    Check(
        id="determinism_cross_process",
        title="确定性：跨进程逐字节一致（不同 PYTHONHASHSEED）",
        script="scripts/check_determinism.py --cross-process",
        module="scripts.check_determinism",
        argvs=(("--cross-process",),),
        note="同进程双跑查不出 `set` 迭代顺序那一类问题（§19.2 ⑳）",
    ),
    Check(
        id="hardcoding",
        title="硬编码业务词审计（引擎 + 前端）",
        script="scripts/audit_hardcoding.py --include-frontend",
        module="scripts.audit_hardcoding",
        argvs=(("--include-frontend",),),
        metrics=(SCAN_ENGINE_FILES, ENGINE_HITS, FRONTEND_SCANNED, FRONTEND_HITS),
    ),
    Check(
        id="contract_demo",
        title=f"契约校验（{Path(DEMO_PROJECT).name}，自造样本）",
        script=f"scripts/validate_contract.py --project {DEMO_PROJECT}",
        module="scripts.validate_contract",
        argvs=(("--project", DEMO_PROJECT),),
    ),
    Check(
        id="contract_third_party",
        title=f"契约校验（{Path(THIRD_PARTY_PROJECT).name}，第三方项目）",
        script=f"scripts/validate_contract.py --project {THIRD_PARTY_PROJECT}",
        module="scripts.validate_contract",
        argvs=(("--project", THIRD_PARTY_PROJECT),),
    ),
)

BACKEND_CHECKS: tuple[Check, ...] = (
    Check(
        id="logic_platform_api",
        title="业务逻辑分析平台接口自测（13 个路由）",
        script="scripts/test_logic_platform_api.py",
        module="scripts.test_logic_platform_api",
        group="backend",
        note="需要 8000 端口上的 uvicorn；且改过后端代码必须先重启（§19.5）",
    ),
)

NODE_CHECKS: tuple[Check, ...] = (
    Check(
        id="browser_clickthrough",
        title=f"端到端点击流走查 · 在线（{DEMO_PROJECT_ID}，自造样本）",
        script=f"node scripts/browser_clickthrough.mjs --project {DEMO_PROJECT_ID}",
        module="",
        group="node",
        kind="node",
        note="需要后端 + 走查 bundle（`.smoke-dist`，改了 .vue 必须重建，§19.5）",
    ),
    Check(
        id="browser_clickthrough_third_party",
        title=f"端到端点击流走查 · 在线（{THIRD_PARTY_PROJECT_ID}，真实第三方）",
        script=f"node scripts/browser_clickthrough.mjs --project {THIRD_PARTY_PROJECT_ID}",
        module="",
        group="node",
        kind="node",
        note="换一个真实第三方项目跑同一套断言：证明走查不是只对着自造样本能过",
    ),
    Check(
        id="browser_clickthrough_offline",
        title=f"端到端点击流走查 · 离线降级（{DEMO_PROJECT_ID}）",
        script=f"node scripts/browser_clickthrough.mjs --project {DEMO_PROJECT_ID} --offline",
        module="",
        group="node",
        kind="node",
        note="`--offline` 把 /api 指向死端口，验证离线降级与「如实报不可用」，不是在线路径的重复",
    ),
    Check(
        id="browser_clickthrough_offline_third_party",
        title=f"端到端点击流走查 · 离线降级（{THIRD_PARTY_PROJECT_ID}）",
        script=f"node scripts/browser_clickthrough.mjs --project {THIRD_PARTY_PROJECT_ID} --offline",
        module="",
        group="node",
        kind="node",
        note="离线快照按项目分目录，只跑一个项目会漏掉快照缺失",
    ),
)

MANUAL_CHECKS: tuple[Check, ...] = (
    Check(
        id="business_graph_validation",
        title="第三方项目图谱验证报告 + 人工核对模板",
        script=(
            "scripts/validate_business_graph.py --output validation/business_graph_validation.md "
            "--json-output validation/business_graph_metrics.json --emit-review"
        ),
        module="scripts.validate_business_graph",
        group="manual",
        note="⚠️ --emit-review 会**覆盖**人工判定列（§20.3 ①：要重跑就先跑再填）",
    ),
    Check(
        id="graph_review_report",
        title="人工核对结果统计器（划分错误率 / 命名不当率）",
        script="scripts/graph_review_report.py",
        module="scripts.graph_review_report",
        group="manual",
        note="判定列未填时**退出码 1 是验收语义**，不是失败运行（§0.3 注）",
    ),
    Check(
        id="domain_review_worksheet",
        title="域核对工作纸生成器",
        script="scripts/export_domain_review_worksheet.py",
        module="scripts.export_domain_review_worksheet",
        group="manual",
        note="覆盖写 `validation/graph_review_worksheet.md`",
    ),
)

ORDER_TRAP_CHECKS: tuple[Check, ...] = (
    Check(
        id="old_pipeline_smoke_project",
        title="旧管线冒烟：项目分析器",
        script="scripts/test_project_analyzer.py",
        module="scripts.test_project_analyzer",
        group="order-trap",
        note="会重写 `frontend/public/demo/project_analysis.json`，跑完必须重跑产物脚本（§19.5）",
    ),
    Check(
        id="old_pipeline_smoke_deep",
        title="旧管线冒烟：深度分析",
        script="scripts/test_deep_analyzer.py",
        module="scripts.test_deep_analyzer",
        group="order-trap",
        note="与上一条同一类顺序陷阱",
    ),
    Check(
        id="old_pipeline_smoke_full",
        title="旧管线冒烟：全引擎",
        script="scripts/test_full_engine.py",
        module="scripts.test_full_engine",
        group="order-trap",
        note="与上一条同一类顺序陷阱",
    ),
)

ALL_CHECKS: tuple[Check, ...] = (
    ENGINE_CHECKS + BACKEND_CHECKS + NODE_CHECKS + MANUAL_CHECKS + ORDER_TRAP_CHECKS
)


# ============================================================
# 输出捕获（进程内，不用管道）
# ============================================================

class _Capture(io.StringIO):
    """既能当 StringIO 用，又能接住 `sys.stdout.reconfigure(...)`。

    有几个脚本在入口处调用 ``sys.stdout.reconfigure(encoding="utf-8")``，
    用裸 ``StringIO`` 接会 ``AttributeError``（§19.5 已记录同一个坑）。
    """

    def reconfigure(self, **_kwargs) -> None:  # noqa: D401 - 故意什么都不做
        return None

    def isatty(self) -> bool:  # pragma: no cover - 只为让脚本里的 isatty 分支走"非终端"
        return False


@dataclass
class RunResult:
    check: Check
    argv: tuple[str, ...]
    exit_code: int
    output: str
    total: int | None = None
    passed: int | None = None
    total_source: str = ""
    metrics: dict[str, int] = field(default_factory=dict)
    error: str = ""

    @property
    def status(self) -> str:
        if self.error:
            return "error"
        if self.exit_code != 0:
            return "fail"
        if self.total is not None and self.passed is not None and self.passed < self.total:
            return "fail"
        return "pass"

    @property
    def total_label(self) -> str:
        if self.total is None:
            return "—"
        return f"{self.passed}/{self.total}"


_TOTAL_PATTERNS: tuple[tuple[str, str], ...] = (
    ("合计", r"合计\s*(\d+)\s*/\s*(\d+)\s*项"),
    ("结果", r"结果[:：]\s*(\d+)\s*/\s*(\d+)\s*项"),
    ("小结", r"[:：]\s*(\d+)\s*/\s*(\d+)\s*项通过"),
)
_PER_LINE_TOTAL = re.compile(r"(\d+)\s*/\s*(\d+)\s*项通过")
_MARKER_TOTAL = re.compile(r"^\s*\[(PASS|FAIL)\]", re.M)


def parse_totals(output: str) -> tuple[int | None, int | None, str]:
    """从脚本屏幕输出里解析「通过/总数」。

    口径（照抄脚本自己的打印，不另立一套）：

    1. 先找总结行：``合计 N/M 项`` / ``结果：N/M 项`` / ``…：N/M 项通过``；
    2. 找不到就把逐行 ``N/M 项通过`` **相加** —— `test_business_graph.py` 只在
       每个项目与种子合并处分别打印，总计 161 是相加得来的；
    3. 还找不到就数 ``[PASS]`` / ``[FAIL]`` 行（`validate_contract.py` 与
       `test_logic_platform.py` 是这种格式）；
    4. 都没有（例如 `check_determinism.py` 只打印「全部一致」、
       `audit_hardcoding.py` 只打印扫描数与命中数）→ 总计留空，
       只用退出码与 metrics 表达结果。
    """
    for key, pattern in _TOTAL_PATTERNS:
        found = list(re.finditer(pattern, output))
        if found:
            passed, total = found[-1].groups()
            return int(passed), int(total), key

    per_line = _PER_LINE_TOTAL.findall(output)
    if per_line:
        passed = sum(int(p) for p, _ in per_line)
        total = sum(int(t) for _, t in per_line)
        if total:
            return passed, total, "逐行相加"

    markers = _MARKER_TOTAL.findall(output)
    if markers:
        passed = sum(1 for mark in markers if mark == "PASS")
        return passed, len(markers), "标记计数（[PASS]/[FAIL] 行）"

    return None, None, ""


def parse_metrics(output: str, patterns: tuple[tuple[str, str], ...]) -> dict[str, int]:
    metrics: dict[str, int] = {}
    for key, pattern in patterns:
        found = re.findall(pattern, output)
        if found:
            metrics[key] = int(found[-1])
    return metrics


def run_node(check: Check, argv: tuple[str, ...]) -> RunResult:
    """跑**外部运行时**的检查（目前只有 node 走查）。

    三条硬约束，都是踩过的坑：

    1. **不用管道捕获输出**：本仓库记录过 `vite build` 的 `spawn EPERM`
       （§19.5）——受限环境下子进程的管道 stdio 会直接失败。所以子进程的
       stdout/stderr **重定向到一个临时文件**由父进程读，不走 PIPE。
    2. **cwd 必须是仓库根**：走查要读 `.smoke-dist` 与 `frontend/public/demo/...`，
       相对路径是相对仓库根写的。
    3. **必须显式 UTF-8**：走查输出全中文，Windows 默认代码页会把汇总行解成乱码，
       `合计 N/M 项通过` 一旦解错就数不出总数（这个脚本的 stdout 已经在别处踩过一次）。
    """
    if not argv:
        # node 条目**天然没有 argvs**：Python 条目靠 `module` + `argvs` 在进程内
        # 调 main()，而 node 条目唯一的命令来源就是 `script` 那一行。
        # 所以这里从 script 解析出 argv，而不是把"空 argv"当成配置错误。
        argv = tuple(shlex.split(check.script))
    if not argv:
        return RunResult(
            check=check, argv=(), exit_code=1, output="",
            error=f"{check.id}：kind=node 且 script 解析不出命令（条目配置错了）",
        )

    handle, log_path = tempfile.mkstemp(prefix="lwai_acceptance_", suffix=".log")
    os.close(handle)
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["NO_COLOR"] = "1"
    exit_code = 1
    error = ""
    try:
        with open(log_path, "wb") as sink:
            completed = subprocess.run(
                list(argv),
                cwd=str(REPO_ROOT),
                stdin=subprocess.DEVNULL,
                stdout=sink,
                stderr=subprocess.STDOUT,
                check=False,
                env=env,
            )
            exit_code = completed.returncode
        output = Path(log_path).read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        output = ""
        error = f"找不到外部运行时 `{argv[0]}`：这台机器没装它（条目本身没跑）"
    except Exception:
        output = ""
        error = traceback.format_exc(limit=6)
    finally:
        try:
            os.unlink(log_path)
        except OSError:  # pragma: no cover - 临时文件删不掉不该影响验收结论
            pass

    passed, total, source = parse_totals(output)
    return RunResult(
        check=check,
        argv=argv,
        exit_code=exit_code,
        output=output,
        total=total,
        passed=passed,
        total_source=source,
        metrics=parse_metrics(output, check.metrics),
        error=error,
    )


def run_one(check: Check, argv: tuple[str, ...]) -> RunResult:
    """跑一个条目：``kind="node"`` 走子进程，其余在**当前进程内**跑。"""
    if check.kind != "python":
        return run_node(check, argv)

    if not check.module:
        return RunResult(
            check=check,
            argv=argv,
            exit_code=1,
            output="",
            error=(
                f"kind=python 但没写 module（条目 {check.id} 配置错了）——"
                "跨语言条目必须显式写 kind=\"node\" 才会走子进程路径"
            ),
        )

    capture = _Capture()
    old_argv = sys.argv
    exit_code = 1
    error = ""
    try:
        module = importlib.import_module(check.module)
        entry = getattr(module, "main", None)
        if entry is None:
            raise AttributeError(f"{check.module} 没有 main() 入口")
        sys.argv = [check.script, *argv]
        with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
            try:
                # 有些脚本的 main() 收 argv（如 audit_hardcoding），有些不收；
                # 统一改成"能收就传"。
                params = [
                    p
                    for p in inspect.signature(entry).parameters.values()
                    if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
                ]
                result = entry(list(argv)) if params else entry()
                exit_code = 0 if result is None else int(result)
            except SystemExit as exc:  # 脚本自己 raise SystemExit(main())
                code = exc.code
                exit_code = 0 if code is None else int(code) if isinstance(code, int) else 1
            except Exception:  # pragma: no cover - 出错要如实记下来，不能算通过
                exit_code = 1
                error = traceback.format_exc(limit=6)
    except Exception:  # pragma: no cover - 导入失败同样如实记录
        exit_code = 1
        error = traceback.format_exc(limit=6)
    finally:
        sys.argv = old_argv

    output = capture.getvalue()
    passed, total, source = parse_totals(output)
    return RunResult(
        check=check,
        argv=argv,
        exit_code=exit_code,
        output=output,
        total=total,
        passed=passed,
        total_source=source,
        metrics=parse_metrics(output, check.metrics),
        error=error,
    )


def run_check(check: Check) -> list[RunResult]:
    return [run_one(check, argv) for argv in check.argvs]


# ============================================================
# 报告渲染
# ============================================================

def app_version() -> str:
    """后端应用版本 —— 文档里的版本号必须只有这一个来源。"""
    main_py = REPO_ROOT / "backend" / "app" / "main.py"
    if not main_py.is_file():
        return ""
    match = re.search(r'version\s*=\s*"([^"]+)"', main_py.read_text(encoding="utf-8"))
    return match.group(1) if match else ""


def tail(text: str, lines: int = 12) -> str:
    kept = [line for line in text.strip().splitlines() if line.strip()]
    return "\n".join(kept[-lines:])


def build_payload(results: list[RunResult], skipped: list[tuple[Check, str]]) -> dict:
    checks = []
    for res in results:
        checks.append(
            {
                "id": res.check.id,
                "title": res.check.title,
                "script": res.check.script,
                "argv": list(res.argv),
                "group": res.check.group,
                "exit_code": res.exit_code,
                "status": res.status,
                "total": res.total,
                "passed": res.passed,
                "total_source": res.total_source,
                "metrics": res.metrics,
                "output_tail": tail(res.output),
                "error": res.error.strip().splitlines()[-1] if res.error else "",
                "note": res.check.note,
            }
        )
    ran = len(checks)
    passed = sum(1 for c in checks if c["status"] == "pass")
    payload = {
        "report_version": REPORT_VERSION,
        "generated_at": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "python": sys.version.split()[0],
        "app_version": app_version(),
        "generator": "scripts/build_acceptance_report.py",
        "summary": {
            "ran": ran,
            "passed": passed,
            "failed": ran - passed,
            "skipped": len(skipped),
        },
        "checks": checks,
        "skipped": [
            {
                "id": c.id,
                "title": c.title,
                "script": c.script,
                "group": c.group,
                "reason": reason,
            }
            for c, reason in skipped
        ],
    }
    return payload


def render_markdown(payload: dict) -> str:
    lines = [
        "<!-- 机器生成，请勿手改：python scripts/build_acceptance_report.py -->",
        "",
        "# 验收报告（最近一次实跑）",
        "",
        f"- 生成时间：{payload['generated_at']}（Python {payload['python']}）",
        f"- 后端应用版本：`{payload['app_version']}`（来源 `backend/app/main.py`，本报告是文档引用版本号的唯一来源）",
        f"- 结果：**{payload['summary']['passed']}/{payload['summary']['ran']} 个脚本通过**，"
        f"跳过 {payload['summary']['skipped']} 个（原因见下表）",
        "",
        "> 文档里**不许**手抄下表的数字；只能写「见 `validation/acceptance_latest.md`」。",
        "> `scripts/verify_docs.py` 会核对这条纪律。",
        "",
        "| 脚本 | 结果 | 合计 | 证据来源 | 备注 |",
        "|---|---|---|---|---|",
    ]
    for c in payload["checks"]:
        mark = {"pass": "✅", "fail": "❌", "error": "💥"}[c["status"]]
        total = "—" if c["total"] is None else f"**{c['passed']}/{c['total']}**"
        extra = c["note"]
        if c["metrics"]:
            metric_text = "、".join(f"`{k}={v}`" for k, v in c["metrics"].items())
            extra = f"{extra}（{metric_text}）" if extra else metric_text
        lines.append(
            f"| `{c['script']}` | {mark} exit {c['exit_code']} | {total} | "
            f"{c['total_source'] or '—'} | {extra or '—'} |"
        )
    if payload["skipped"]:
        lines += [
            "",
            "## 本次未跑（不是通过，也不是失败）",
            "",
            "| 脚本 | 组 | 为什么没跑 |",
            "|---|---|---|",
        ]
        for s in payload["skipped"]:
            lines.append(f"| `{s['script']}` | `{s['group']}` | {s['reason']} |")
    lines += [
        "",
        "## 怎么复现",
        "",
        "```bash",
        "python scripts/build_acceptance_report.py",
        "python scripts/verify_docs.py     # 核对文档里的数字与本报告是否一致",
        "```",
        "",
    ]
    return "\n".join(lines)


# ============================================================
# 入口
# ============================================================

def select_checks(args: argparse.Namespace) -> tuple[list[Check], list[tuple[Check, str]]]:
    groups = {"engine"}
    if args.with_backend:
        groups.add("backend")
    if args.with_node:
        groups.add("node")
    if args.with_manual:
        groups.add("manual")
    if args.with_order_trap:
        groups.add("order-trap")

    skipped: list[tuple[Check, str]] = []
    selected: list[Check] = []
    for check in ALL_CHECKS:
        if args.only and check.id not in args.only:
            continue
        if args.only:
            selected.append(check)
            continue
        if check.group in groups:
            selected.append(check)
        else:
            reason = {
                "backend": "需要 8000 端口上的后端（加 --with-backend）",
                "node": "需要后端在线 + 走查 bundle `.smoke-dist`（加 --with-node）",
                "manual": check.note or "人工/覆盖写工具，需人工按顺序执行（加 --with-manual）",
                "order-trap": check.note or "顺序陷阱，需人工按顺序执行（加 --with-order-trap）",
            }.get(check.group, "不在本次范围内")
            skipped.append((check, reason))
    return selected, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="跑验收脚本 → 产出 validation/acceptance_latest.json/.md（文档数字的唯一来源）",
    )
    parser.add_argument("--only", action="append", default=None, help="只跑指定 id（可重复）")
    parser.add_argument("--list", action="store_true", help="只列出会跑什么，不执行")
    parser.add_argument("--json-output", default=DEFAULT_JSON, help=f"JSON 输出路径（默认 {DEFAULT_JSON}）")
    parser.add_argument("--md-output", default=DEFAULT_MD, help=f"Markdown 输出路径（默认 {DEFAULT_MD}）")
    parser.add_argument("--with-backend", action="store_true", help="也跑需要后端的检查")
    parser.add_argument("--with-node", action="store_true",
                        help="也跑 4 条 node 走查（后端在线 + .smoke-dist 已构建）")
    parser.add_argument("--with-manual", action="store_true", help="也跑人工/覆盖写工具（⚠️ 会覆盖产物）")
    parser.add_argument("--with-order-trap", action="store_true", help="也跑旧管线冒烟（⚠️ 会覆盖学生快照）")
    parser.add_argument("--no-write", action="store_true", help="只打印，不写报告文件")
    parser.add_argument("--quiet", action="store_true", help="不打印子脚本输出尾部")
    args = parser.parse_args(argv)

    selected, skipped = select_checks(args)

    if args.list:
        print("本次会跑：")
        for check in selected:
            print(f"  [{check.group}] {check.id:<26} {check.script}")
        print("\n本次不跑：")
        for check, reason in skipped:
            print(f"  [{check.group}] {check.id:<26} {reason}")
        return 0

    print("=" * 78)
    print("验收报告生成（Python 条目在进程内运行；node 条目起子进程并用临时文件接输出，不走管道）")
    print("=" * 78)

    results: list[RunResult] = []
    for check in selected:
        print(f"\n>>> {check.id} · {check.title}")
        for res in run_check(check):
            results.append(res)
            mark = {"pass": "PASS", "fail": "FAIL", "error": "ERROR"}[res.status]
            argv_text = " ".join(res.argv)
            print(f"    [{mark}] exit {res.exit_code}  合计 {res.total_label}"
                  + (f"  ({argv_text})" if argv_text else ""))
            if res.metrics:
                print("            " + "、".join(f"{k}={v}" for k, v in res.metrics.items()))
            if res.status != "pass" and not args.quiet:
                for line in tail(res.output, 8).splitlines():
                    print(f"            | {line}")
                if res.error:
                    print(f"            ! {res.error.strip().splitlines()[-1]}")

    payload = build_payload(results, skipped)

    print()
    print("=" * 78)
    for c in payload["checks"]:
        mark = {"pass": "PASS", "fail": "FAIL", "error": "ERROR"}[c["status"]]
        print(f"[{mark:<5}] {c['id']:<26} {c['passed']}/{c['total']}"
              if c["total"] is not None else f"[{mark:<5}] {c['id']:<26} —")
    print("-" * 78)
    print(f"合计 {payload['summary']['passed']}/{payload['summary']['ran']} 个脚本通过"
          f"，跳过 {payload['summary']['skipped']} 个")
    print("=" * 78)

    if args.no_write:
        print("\n（--no-write：未写报告文件）")
        return 1 if payload["summary"]["failed"] else 0

    json_path = REPO_ROOT / args.json_output
    md_path = REPO_ROOT / args.md_output
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(f"\n报告已写入：{args.json_output}（机器读）、{args.md_output}（人读）")
    print("文档引用数字时只写「见验收报告」，不要手抄 —— scripts/verify_docs.py 会核对。")

    return 1 if payload["summary"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
