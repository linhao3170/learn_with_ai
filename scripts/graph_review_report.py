"""
业务图谱核对结果统计器（README §18 优先级 2 的验收工具）

它解决什么问题
--------------
优先级 2 要求「报告第 6 节的『人工判定』列被填满，并算出两个独立的数字：
业务图谱**划分**错误率、模块**命名**不当率」（README §18）。
`validate_business_graph.py` 只**生成**那张空表（并刻意不填判定），
**仓库里原本没有任何东西能把填好的表读回来算这两个数字** —— 本脚本补这个缺口。

口径（照抄 README §17.4 / §18，不另立一套）
-------------------------------------------
- **业务图谱划分错误率 = `划分错误` 的行数 / 总行数**；
- **模块命名不当率 = `命名不当` 的行数 / 总行数**；
- 分母是**总行数**（含 `无法判定` 的行）——不许悄悄把没判的那部分从分母里拿掉；
- **域**与**二级功能点**两个分母不同，**必须分开报、不许相加**
  （README §17.4：`划分错误 / 总域数` 才是「业务图谱划分错误率」，
  它和「事实错误率」不是一回事，不能混着报）；
- 本脚本**不判、不猜、不代填**：遇到空值只如实报「未填」，遇到非法取值只如实报错。

退出码（可直接当验收命令用）
----------------------------
- ``0`` = 全部行都已填且取值合法（验收通过）；
- ``1`` = 有未填 / 非法取值 / 表格结构被破坏；
- ``2`` = 找不到「## 6. 人工核对模板」这一节（多半是输入文件不对）。

用法
----
    python scripts/graph_review_report.py
    python scripts/graph_review_report.py --input validation/business_graph_validation.md --verbose
    python scripts/graph_review_report.py --output validation/business_graph_review_summary.md
    python scripts/graph_review_report.py --json-output validation/business_graph_review.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # pragma: no cover
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

DEFAULT_INPUT = "validation/business_graph_validation.md"

#: 判定词（README 第 6 节原文，四选一，不是「对/错」二分）
VERDICTS = ("正确", "命名不当", "划分错误", "无法判定")

#: 两种表的列数（domain_id/系统命名/角色/置信度/子节点/聚类依据/人工判定/备注）
COLUMN_COUNT = 8

SECTION_MARKER = "## 6. 人工核对模板"
PROJECT_MARKER = "### 6.x "
DOMAIN_TABLE_MARKER = "#### 一级业务域"
CAPABILITY_TABLE_MARKER = "#### 二级功能点"


class Row:
    """一行待人工判定的记录。"""

    def __init__(self, project: str, kind: str, item_id: str, name: str, verdict: str, note: str, line_no: int):
        self.project = project
        self.kind = kind          # "domain" / "capability"
        self.item_id = item_id
        self.name = name
        self.verdict = verdict    # 原始文本（可能是空的）
        self.note = note
        self.line_no = line_no

    @property
    def filled(self) -> bool:
        return bool(self.verdict)

    @property
    def valid(self) -> bool:
        return self.verdict in VERDICTS


def _strip_marker(text: str) -> str:
    return text.replace("`", "").strip()


def parse_rows(text: str) -> Tuple[List[Row], List[str], List[str]]:
    """解析第 6 节。

    :returns: ``(rows, malformed, projects)``；``malformed`` 是"列数不对"的行说明
        （表格被手工编辑破坏时会出现 —— 这正是要报出来的东西）。
    """
    if SECTION_MARKER not in text:
        return [], [], []
    section = text.split(SECTION_MARKER, 1)[1]
    #: 第 6 节在**整个文件**里的起始行号（报错要能直接跳到那一行去修）
    section_start_line = text[: text.index(SECTION_MARKER)].count("\n") + 1

    rows: List[Row] = []
    malformed: List[str] = []
    projects: List[str] = []
    project = ""
    kind = ""

    for offset, raw in enumerate(section.splitlines()):
        line = raw.rstrip()
        if line.startswith(PROJECT_MARKER):
            project = _strip_marker(line[len(PROJECT_MARKER):].split("（")[0])
            if project and project not in projects:
                projects.append(project)
            kind = ""
            continue
        if line.startswith(DOMAIN_TABLE_MARKER):
            kind = "domain"
            continue
        if line.startswith(CAPABILITY_TABLE_MARKER):
            kind = "capability"
            continue
        if not kind or not line.startswith("|"):
            continue

        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        first = cells[0] if cells else ""
        if not first.startswith("`"):
            continue  # 表头 / 分隔行
        if len(cells) != COLUMN_COUNT:
            malformed.append(
                f"文件第 {section_start_line + offset + 1} 行（`{_strip_marker(first)}`）"
                f"列数是 {len(cells)}，应为 {COLUMN_COUNT} —— 手工编辑时可能多写或少写了 `|`"
            )
            continue

        rows.append(
            Row(
                project=project,
                kind=kind,
                item_id=_strip_marker(first),
                name=cells[1],
                verdict=cells[COLUMN_COUNT - 2],
                note=cells[COLUMN_COUNT - 1],
                line_no=section_start_line + offset + 1,
            )
        )

    return rows, malformed, projects


def summarize(rows: List[Row]) -> Dict[str, Any]:
    """按「项目 × 表类型」与「表类型合计」统计。"""
    def _bucket(items: List[Row]) -> Dict[str, Any]:
        counts = {verdict: 0 for verdict in VERDICTS}
        unfilled: List[str] = []
        invalid: List[str] = []
        for row in items:
            if not row.filled:
                unfilled.append(row.item_id)
            elif row.valid:
                counts[row.verdict] += 1
            else:
                invalid.append(f"{row.item_id}={row.verdict!r}")
        total = len(items)
        decided = total - counts["无法判定"]
        return {
            "total": total,
            "filled": total - len(unfilled),
            "unfilled_ids": unfilled,
            "invalid": invalid,
            "counts": counts,
            # 口径固定：分母 = 总行数（README §18）
            "division_error_rate": (counts["划分错误"] / total) if total else None,
            "naming_error_rate": (counts["命名不当"] / total) if total else None,
            # 参考值（**不是** README 口径，只用于回答"排除判不了的那些之后呢"）
            "division_error_rate_excluding_undecided": (
                counts["划分错误"] / decided if decided else None
            ),
        }

    per_project: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        per_project.setdefault(row.project, {"domain": [], "capability": []})[row.kind].append(row)

    return {
        "per_project": {
            project: {kind: _bucket(items) for kind, items in kinds.items()}
            for project, kinds in sorted(per_project.items())
        },
        "overall": {
            kind: _bucket([row for row in rows if row.kind == kind])
            for kind in ("domain", "capability")
        },
    }


def _pct(value: Optional[float]) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def _render_bucket(label: str, bucket: Dict[str, Any]) -> List[str]:
    counts = bucket["counts"]
    lines = [
        f"- **{label}**：共 {bucket['total']} 行 ｜ 已填 {bucket['filled']} ｜ 未填 {len(bucket['unfilled_ids'])}",
        f"  - `正确` {counts['正确']} ｜ `命名不当` {counts['命名不当']} ｜ "
        f"`划分错误` {counts['划分错误']} ｜ `无法判定` {counts['无法判定']}",
        f"  - **划分错误率（口径：划分错误 / 总行数）**：{_pct(bucket['division_error_rate'])}"
        f"（{counts['划分错误']} / {bucket['total']}）",
        f"  - **命名不当率（口径：命名不当 / 总行数）**：{_pct(bucket['naming_error_rate'])}"
        f"（{counts['命名不当']} / {bucket['total']}）",
    ]
    if bucket["total"] and counts["无法判定"]:
        lines.append(
            f"  - 参考（**不是** README 口径，仅用于回答「排除判不了的那些之后呢」）："
            f"划分错误率 {_pct(bucket['division_error_rate_excluding_undecided'])}"
            f"（{counts['划分错误']} / {bucket['total'] - counts['无法判定']}）"
        )
    return lines


def render_report(summary: Dict[str, Any], malformed: List[str], verbose: bool) -> str:
    lines: List[str] = [
        "# 业务图谱核对结果统计",
        "",
        "> 由 `python scripts/graph_review_report.py` 生成。**本报告不产生任何新判断**，",
        "> 它只是把 `validation/business_graph_validation.md` 第 6 节里**人填的**那一列读回来统计。",
        "",
        "## 口径（照抄 README §17.4 / §18）",
        "",
        "- **业务图谱划分错误率 = `划分错误` 的行数 / 总行数**；",
        "- **模块命名不当率 = `命名不当` 的行数 / 总行数**；",
        "- 分母是**总行数**（含 `无法判定`）；**域**与**二级功能点**两个分母不同，",
        "  **必须分开报、不许相加**，也不要和「事实错误率」混报；",
        "- 自造样本 `sample_projects/lab_safety_assistant` **不参与**（README §13.2）。",
        "",
        "## 合计",
        "",
    ]
    lines.extend(_render_bucket("一级业务域", summary["overall"]["domain"]))
    lines.append("")
    lines.extend(_render_bucket("二级功能点", summary["overall"]["capability"]))
    lines.append("")
    lines.append("## 分项目")
    lines.append("")
    for project, kinds in summary["per_project"].items():
        lines.append(f"### `{project}`")
        lines.append("")
        lines.extend(_render_bucket("一级业务域", kinds["domain"]))
        lines.append("")
        lines.extend(_render_bucket("二级功能点", kinds["capability"]))
        lines.append("")

    unfilled = summary["overall"]["domain"]["unfilled_ids"] + summary["overall"]["capability"]["unfilled_ids"]
    if unfilled:
        lines.append("## 还没填的行")
        lines.append("")
        shown = unfilled if verbose else unfilled[:20]
        lines.append("、".join(f"`{item}`" for item in shown))
        if len(unfilled) > len(shown):
            lines.append("")
            lines.append(f"（只列前 20 个，共 {len(unfilled)} 个未填；加 `--verbose` 看全部）")
        lines.append("")

    if malformed:
        lines.append("## ⚠️ 表格结构问题（必须修）")
        lines.append("")
        for item in malformed[:20]:
            lines.append(f"- {item}")
        lines.append("")

    invalid = summary["overall"]["domain"]["invalid"] + summary["overall"]["capability"]["invalid"]
    if invalid:
        lines.append("## ⚠️ 取值不在四个判定词里的行（必须改）")
        lines.append("")
        lines.append("、".join(invalid[:20]))
        lines.append("")
        lines.append(f"允许的取值只有：{' / '.join(f'`{v}`' for v in VERDICTS)}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="统计人工核对结果（划分错误率 / 命名不当率）")
    parser.add_argument("--input", default=DEFAULT_INPUT, help=f"核对模板路径（默认 {DEFAULT_INPUT}）")
    parser.add_argument("--output", default=None, help="把统计报告写成 Markdown")
    parser.add_argument("--json-output", default=None, help="把统计结果写成 JSON（供引用/留档）")
    parser.add_argument("--verbose", action="store_true", help="列出全部未填行")
    args = parser.parse_args()

    in_path = REPO_ROOT / args.input
    if not in_path.is_file():
        print(f"[错误] 找不到输入文件：{args.input}")
        return 2
    text = in_path.read_text(encoding="utf-8")
    if SECTION_MARKER not in text:
        print(f"[错误] {args.input} 里没有「{SECTION_MARKER}」这一节。")
        print("       （是不是把 --input 指到了别的文件？先跑：")
        print("        python scripts/validate_business_graph.py --output validation/business_graph_validation.md "
              "--json-output validation/business_graph_metrics.json --emit-review）")
        return 2

    rows, malformed, projects = parse_rows(text)
    if not rows:
        print(f"[错误] 第 6 节里一行待判定记录都没解析到（表格结构可能被破坏了）")
        return 2

    summary = summarize(rows)
    report = render_report(summary, malformed, args.verbose)
    print(report)

    if args.output:
        out_path = REPO_ROOT / args.output
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(f"已写入：{args.output}")

    if args.json_output:
        payload = {
            "input": args.input,
            "projects": projects,
            "verdicts": list(VERDICTS),
            "rates_denominator": "total_rows（README §18 口径）",
            "summary": summary,
            "malformed": malformed,
        }
        json_path = REPO_ROOT / args.json_output
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已写入：{args.json_output}")

    unfilled_total = len(summary["overall"]["domain"]["unfilled_ids"]) + len(
        summary["overall"]["capability"]["unfilled_ids"]
    )
    invalid_total = len(summary["overall"]["domain"]["invalid"]) + len(summary["overall"]["capability"]["invalid"])

    print()
    if malformed or invalid_total or unfilled_total:
        print("验收：未通过 ✗")
        if malformed:
            print(f"  · 表格结构问题 {len(malformed)} 处（手工编辑时多半多写/少写了 `|`）")
        if invalid_total:
            print(f"  · 取值不在四个判定词里的行 {invalid_total} 处")
        if unfilled_total:
            print(f"  · 还没填的行 {unfilled_total} 处（README §18 要求判定列被填满）")
        return 1
    print("验收：通过 ✓（判定列已填满，取值全部合法）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
