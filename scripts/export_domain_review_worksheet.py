"""
域核对工作纸生成器（README §18 优先级 2 的配套材料）

为什么需要它
------------
优先级 2「人工核对业务图谱」是**唯一**能产出「准确率」的途径，而它只能由人填
（`scripts/validate_business_graph.py` 生成的模板里，「人工判定」列刻意留空）。
但人填的时候要回答的问题是：

    「这一堆函数，在业务上到底是不是同一个模块？」

回答它必须看到**真实函数与行号**，而不是只看到「系统命名 + 聚类依据」两列。
`validation/business_graph_validation.md` 是给"填判定"用的**表**（它必须保持紧凑），
本脚本生成的是给"判断"用的**工作纸**：每个域一张小卡片，把这个域实际包含的能力点、
成员函数、文件与行号、以及聚类依据摊开。

⚠️ 纪律
--------
- **本脚本不填任何判定、也不改任何结论**（与 `validate_business_graph.py` 同一条纪律）；
- 只覆盖**真实第三方项目**：自造样本 `sample_projects/lab_safety_assistant` 被刻意跳过
  （README §13.2 / §17.4：不许在自造样本上报告准确率）；
- 项目清单与「哪些是自造样本」**复用 `validate_business_graph.py` 的同一份定义**，
  不在这里另写一份 —— 否则两边迟早不一致。

用法
----
    python scripts/export_domain_review_worksheet.py
    python scripts/export_domain_review_worksheet.py --output validation/graph_review_worksheet.md
    python scripts/export_domain_review_worksheet.py --project validation/python_dotenv

    # 试点模式：只做一个项目的一级域，产出"填判定 + 记引擎问题"的小纸
    python scripts/export_domain_review_worksheet.py --pilot validation/python_dotenv

输出**逐字节可复现**（无时间戳、无 set 迭代顺序依赖）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # pragma: no cover
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

#: 项目清单与「自造样本」定义都复用验证脚本里的那一份（唯一实现）
from validate_business_graph import DEFAULT_PROJECTS, SELF_MADE  # noqa: E402

DEFAULT_OUTPUT = "validation/graph_review_worksheet.md"

#: 试点模式产出的文件名模板（`{project}` 用项目目录名替换）
PILOT_OUTPUT = "validation/pilot_review_{project}.md"

#: 四个判定词 —— 与核对模板、统计器保持同一份口径
VERDICTS = ("正确", "命名不当", "划分错误", "无法判定")

#: 信号名 → 人话（只在图例里解释一次；**不是业务词**，是引擎自己的信号名）
SIGNAL_HELP = {
    "directory": "所在目录 / 包名（只有目录足够小才配当域）",
    "docstring": "文件级中文 docstring（最强信号，等于作者原话）",
    "identifier_root": "类名 / 文件名的词根（真实第三方项目主要靠它）",
    "shared_state": "两个单元写同一个状态对象",
    "call_community": "调用图社区（调用密集的单元归到一起）",
    "merge": "并查集合并动作（把若干单元并进同一个域）",
}


def _graph_of(project: str) -> Dict[str, Any]:
    from engine.project_analyzer import ProjectAnalyzer
    from engine.parser import clear_ast_cache

    clear_ast_cache()
    contract = ProjectAnalyzer().analyze(str(REPO_ROOT / project)).to_dict()
    return contract.get("business_graph") or {}


def _render_evidence(evidence: Sequence[Dict[str, Any]], limit: int = 8) -> str:
    """聚类依据：`信号=取值（来源）`，按原顺序（引擎已确定性排序）。"""
    parts: List[str] = []
    for item in list(evidence or [])[:limit]:
        signal = str(item.get("signal") or "")
        value = str(item.get("value") or "")
        detail = str(item.get("detail") or "")
        text = f"`{signal}={value}`"
        if detail and detail != value:
            text += f"（{detail}）"
        parts.append(text)
    if len(evidence or []) > limit:
        parts.append(f"…共 {len(evidence)} 条")
    return "、".join(parts) if parts else "—"


def _member_text(member: Dict[str, Any]) -> str:
    symbol = str(member.get("symbol") or "?")
    file = str(member.get("file") or "?")
    start = member.get("start_line")
    end = member.get("end_line")
    location = f"{file}:{start}" if start == end or not end else f"{file}:{start}-{end}"
    return f"`{symbol}` — `{location}`"


def render_project(project: str, graph: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    domains = list(graph.get("domains") or [])
    capabilities = list(graph.get("capabilities") or [])

    lines.append(f"## `{project}`")
    lines.append("")
    lines.append(
        f"- 规模：域 **{len(domains)}** 个 / 功能点 **{len(capabilities)}** 个 / "
        f"级别 **{graph.get('level')}** / 图谱状态 `{graph.get('status')}`"
    )
    lines.append(f"- `source_hash`：`{graph.get('source_hash')}`")
    lines.append("")

    caps_by_domain: Dict[str, List[Dict[str, Any]]] = {}
    for cap in capabilities:
        caps_by_domain.setdefault(str(cap.get("parent_id") or ""), []).append(cap)

    for index, domain in enumerate(domains, start=1):
        domain_id = str(domain.get("domain_id") or "")
        name = str(domain.get("name_cn") or "")
        role = str(domain.get("role") or "")
        confidence = str(domain.get("confidence") or "")
        name_status = str(domain.get("name_status") or "")
        units = list(domain.get("units") or [])
        children = list(domain.get("children") or [])
        own_caps = caps_by_domain.get(domain_id, [])

        lines.append(f"### {index}. `{domain_id}` · **{name}**")
        lines.append("")
        lines.append(
            f"- 角色 `{role}` ｜ 置信度 `{confidence}` ｜ 命名词根来源 `{name_status}` ｜ "
            f"单元 {len(units)} 个 ｜ 子能力点 {len(children)} 个"
        )
        lines.append(f"- 聚类依据：{_render_evidence(domain.get('evidence') or [])}")

        files: List[str] = []
        for cap in own_caps:
            for member in cap.get("members") or []:
                file = str(member.get("file") or "")
                if file and file not in files:
                    files.append(file)
        lines.append(
            "- 涉及文件："
            + ("、".join(f"`{f}`" for f in sorted(files)) if files else "—（该域没有可定位的成员）")
        )
        lines.append("")

        if not own_caps:
            lines.append("> ⚠️ 这个域**没有子能力点** —— 判「划分错误（不该存在）」还是「正确」时，"
                         "请先看它上面的单元（该域只有一级展示）。")
            lines.append("")
            continue

        lines.append("| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |")
        lines.append("|---|---|---|---|---|")
        for cap in own_caps:
            members = " ；".join(_member_text(m) for m in (cap.get("members") or [])) or "—"
            verb = f"{cap.get('verb_class') or ''}/{cap.get('entity') or ''}"
            lines.append(
                f"| `{cap.get('capability_id')}` | {cap.get('name_cn') or ''} | `{verb}` | "
                f"`{cap.get('confidence') or ''}` | {members} |"
            )
        lines.append("")

    return lines


def render_report(projects: Sequence[str]) -> str:
    lines: List[str] = [
        "# 业务图谱 · 域核对工作纸",
        "",
        "> 由 `python scripts/export_domain_review_worksheet.py` 生成，**可重复执行、逐字节可复现**。",
        "",
        "## 这张纸怎么用",
        "",
        "1. 打开 `validation/business_graph_validation.md` 的第 6 节（那才是**填判定**的地方）；",
        "2. 每判一个域之前，先在本纸里找到同一个 `domain_id`，看三样东西：",
        "   **成员函数到底有哪些**（在哪个文件、第几行）、**聚类依据是什么**、**涉及哪些文件**；",
        "3. 需要看真实代码时，用 `文件:行` 去 `validation/<project>/...` 里翻，",
        "   或在前端「业务图谱」页签里点开证据（有行号跳转）；",
        "4. 判定词只有四个：`正确` / `命名不当` / `划分错误` / `无法判定`",
        "   （口径见 `business_graph_validation.md` 第 6 节；`无法判定` 是合法答案，不要为了填满而猜）。",
        "",
        "> ⚠️ **本纸不填任何判定，也不改任何结论。** 它只是把判断材料摊开。",
        "> ⚠️ 自造样本 `sample_projects/lab_safety_assistant` **刻意不在本纸里** ——",
        "> 启发式规则就是照着它调的，它不能用来报告准确率（README §13.2）。",
        "",
        "**信号名对照**（聚类依据里那些 `信号=取值`）：",
        "",
    ]
    for signal in sorted(SIGNAL_HELP):
        lines.append(f"- `{signal}` — {SIGNAL_HELP[signal]}")
    lines.append("")

    for project in projects:
        graph = _graph_of(project)
        if not graph:
            lines.append(f"## `{project}`")
            lines.append("")
            lines.append("> ⚠️ 该项目图谱为空，已跳过。")
            lines.append("")
            continue
        lines.extend(render_project(project, graph))
        lines.append("---")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_pilot(project: str, graph: Dict[str, Any]) -> str:
    """试点核对纸：一个项目的一级域 + 填判定表 + 引擎问题记录区。

    **为什么要有试点模式**：正式的 184 行核对属于"引擎冻结之后"才做的事
    （判定绑定 `source_hash`，引擎一改就可能作废，见 README §6.1 与 §18 优先级 2）。
    但在那之前值得先做一次小试点，因为它产出的是**三样不随哈希失效的东西**：

    1. 校准工期（每行要花多久）；
    2. 验证四个判定词在实际代码上好不好用；
    3. **把发现的引擎问题列成清单** —— 它直接就是"完善系统功能"的输入项。

    ⚠️ 试点**不是正式统计**：正式数字只认 `validation/business_graph_validation.md`
    第 6 节填满之后由 `scripts/graph_review_report.py` 算出来的那一份。
    """
    name = Path(project).name
    domains = list(graph.get("domains") or [])

    lines: List[str] = [
        f"# 试点核对纸 · `{project}`（一级域 {len(domains)} 行）",
        "",
        "> 由 `python scripts/export_domain_review_worksheet.py --pilot "
        f"{project}` 生成，**可重复执行、逐字节可复现**。",
        "",
        "## 这份纸是干什么的（先读这三条）",
        "",
        "1. **它不是正式统计。** 正式数字只认 `validation/business_graph_validation.md` 第 6 节"
        "填满后由 `scripts/graph_review_report.py` 算出来的那一份；本纸只有"
        f" `{name}` 一个项目、且只做一级域。",
        "2. **它的目的有三个**：① 校准「每行要花多久」，好推算 184 行的真实工期；",
        "   ② 验证四个判定词在实际代码上好不好用（不好用就现在改口径，别等填完 184 行）；",
        "   ③ **把发现的引擎问题记下来** —— 引擎还会改，但「哪里改得不对」这份清单不会作废。",
        "3. **判定绑定 `source_hash`**，所以引擎一改、正式核对就得重做 ——"
        " 这正是把正式核对放到「引擎冻结之后」的理由（README §6.1 / §18 优先级 2）。",
        "",
        f"本纸对应的图谱：`{project}` ｜ `source_hash` = `{graph.get('source_hash')}`",
        "（**重跑本纸时看一眼这行**：哈希变了说明引擎/代码变过，之前的判断要重新审视。）",
        "",
        "## 一、填判定（只有这 6 列要你写）",
        "",
        f"判定词只有四个：{' / '.join(f'`{v}`' for v in VERDICTS)}"
        "（`无法判定` 是合法答案，不要为了填满而猜）。",
        "**备注列写一句话理由** —— 它会在两处派上用场：答辩被追问时是答案，",
        "汇总成「引擎问题清单」时是证据。",
        "",
        "| domain_id | 系统命名 | 角色 | 置信度 | 人工判定 | 备注（一句话理由） |",
        "|---|---|---|---|---|---|",
    ]
    for domain in domains:
        lines.append(
            f"| `{domain.get('domain_id')}` | {domain.get('name_cn') or ''} | "
            f"`{domain.get('role') or ''}` | `{domain.get('confidence') or ''}` |  |  |"
        )
    lines.append("")
    lines.append("> 每一行的判断材料在下面第二节（按 `domain_id` 一一对应）。")
    lines.append("")

    lines.append("## 二、判断材料（每个域一张卡片）")
    lines.append("")
    body = render_project(project, graph)
    # 去掉 render_project 自己的项目标题与项目级摘要（本纸开头已经说过一次了）
    lines.extend(
        line
        for line in body
        if not line.startswith(f"## `{project}`")
        and not line.startswith("- 规模：")
        and not line.startswith("- `source_hash`：")
    )
    lines.append("")

    lines.append("## 三、引擎问题清单（试点最值钱的产出）")
    lines.append("")
    lines.append("判的过程中凡是让你犹豫、或者明显不对的地方，按这个格式记一行：")
    lines.append("")
    lines.append("```text")
    lines.append("| 现象（一句话） | 证据（domain_id / 能力点 / 文件:行） | 我期望它怎样 | 严重度 |")
    lines.append("|---|---|---|---|")
    lines.append("| 例：两个明显不同的业务被并成一个域 | d_xxx；成员 foo.py:12、bar.py:40 | 应该拆成两个域 | 高 |")
    lines.append("```")
    lines.append("")
    lines.append("**严重度只填三个值**：`高`（影响划分对不对）/ `中`（影响命名或粒度）/ `低`（观感问题）。")
    lines.append("")
    lines.append("> 这份清单的意义：**引擎还会继续改，但「哪里改得不对」不会作废。**")
    lines.append("> 正式核对（184 行）应该排在这些改动做完、引擎冻结之后。")
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="生成「域核对工作纸」（人工核对用的判断材料）")
    parser.add_argument("--project", action="append", default=None,
                        help="项目目录（可重复）；默认为验证脚本里的项目清单，且自动跳过自造样本")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help=f"输出路径（默认 {DEFAULT_OUTPUT}）")
    parser.add_argument("--pilot", default=None,
                        help="试点模式：只做这一个项目的一级域，产出「填判定 + 记引擎问题」的小纸")
    args = parser.parse_args()

    if args.pilot:
        project = args.pilot
        if project in SELF_MADE:
            print(f"[错误] {project} 是自造样本，不参与准确率核对（README §13.2）")
            return 1
        graph = _graph_of(project)
        if not graph:
            print(f"[错误] {project} 的图谱为空")
            return 1
        report = render_pilot(project, graph)
        rel = PILOT_OUTPUT.format(project=Path(project).name)
        out_path = REPO_ROOT / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print("=" * 72)
        print("试点核对纸生成（只做一级域；正式统计仍看 business_graph_validation.md）")
        print("=" * 72)
        print(f"  · {project}：一级域 {len(graph.get('domains') or [])} 行")
        print()
        print(f"已写入：{rel}（{len(report.encode('utf-8'))} 字节）")
        print("填完之后：把「三、引擎问题清单」贴给我，我据此整理引擎待改项")
        return 0

    projects = [p for p in (args.project or DEFAULT_PROJECTS) if p not in SELF_MADE]
    if not projects:
        print("没有可核对的项目（自造样本不参与准确率核对）")
        return 1

    print("=" * 72)
    print("域核对工作纸生成（供人工判定时对照；本脚本不填任何判定）")
    print("=" * 72)
    for project in projects:
        print(f"  · {project}")

    report = render_report(projects)
    out_path = REPO_ROOT / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    print()
    print(f"已写入：{args.output}（{len(report.encode('utf-8'))} 字节）")
    print("下一步：对照本纸，填 validation/business_graph_validation.md 第 6 节的「人工判定」列")
    print("填完用：python scripts/graph_review_report.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
