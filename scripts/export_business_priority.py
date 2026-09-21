"""Export the evidence-aware business priority result as a reviewable report.

Examples::

    python scripts/export_business_priority.py \
        --input frontend/public/demo/project_analysis.json \
        --output validation/business_priority_report.md

The script accepts either the complete project-analysis JSON or the raw
``deep_analysis.json``.  It never recomputes a score: the report is a view of
the exact result produced by ``BusinessPriorityAnalyzer``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict


def _load_priority(path: Path) -> tuple[Dict[str, Any], str]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if isinstance(payload.get("project"), dict):
        project_name = payload["project"].get("name", "unknown_project")
    else:
        project_name = payload.get("project_name", "unknown_project")

    if isinstance(payload.get("business_priority"), dict):
        return payload["business_priority"], project_name

    # Project-level JSON stores it below deep_analysis; the standalone deep
    # analysis artifact stores the same object at the top level.
    deep = payload.get("deep_analysis")
    if isinstance(deep, dict) and isinstance(deep.get("business_priority"), dict):
        return deep["business_priority"], project_name

    raise ValueError(f"No business_priority result found in {path}")


def _fmt_score(value: Any) -> str:
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "-"


def render_markdown(priority: Dict[str, Any], project_name: str) -> str:
    algorithm = priority.get("algorithm", {})
    summary = priority.get("summary", {})
    nodes = priority.get("node_scores", [])
    flows = priority.get("flow_scores", [])
    gaps = priority.get("evidence_gaps", [])

    lines = [
        f"# {project_name} · 业务优先级报告",
        "",
        "> 这是一份用于确定教学顺序和人工审核顺序的排序报告，不是代码正确率报告。",
        "",
        f"- 算法：{algorithm.get('name', 'Business Priority')}（{algorithm.get('version', '-')}）",
        f"- 节点数：{summary.get('total_nodes', 0)}",
        f"- 流程数：{summary.get('total_flows', 0)}",
        f"- 平均位置证据完整度：{float(summary.get('evidence_completeness', 0)) * 100:.1f}%",
        f"- 待审核提示：{summary.get('review_gap_count', 0)}",
        "",
        "## 核心节点（Top 10）",
        "",
        "| 排名 | 方法 | 模块 | 分数 | 代码位置 | 原因 |",
        "|---:|---|---|---:|---|---|",
    ]
    for index, node in enumerate(nodes[:10], 1):
        reasons = "、".join(node.get("reasons", [])) or "-"
        lines.append(
            f"| {index} | `{node.get('method', '-')}` | {node.get('module', '-')} "
            f"| {_fmt_score(node.get('score'))} | `{node.get('location', '-')}` | {reasons} |"
        )

    lines += ["", "## 业务流程优先级", "", "| 流程 | 优先级 | 审核提示 | 原因 |", "|---|---:|---:|---|"]
    for flow in flows:
        reasons = "、".join(flow.get("reasons", [])) or "-"
        lines.append(
            f"| {flow.get('name', '-')} | {_fmt_score(flow.get('priority_score'))} "
            f"| {_fmt_score(flow.get('review_risk'))} | {reasons} |"
        )

    lines += ["", "## 证据缺口（需要教师先看）", ""]
    if gaps:
        lines += ["| 严重度 | 类型 | 流程 | 位置 | 说明 |", "|---|---|---|---|---|"]
        for gap in gaps:
            lines.append(
                f"| {gap.get('severity', '-')} | {gap.get('type', '-')} | {gap.get('flow_id', '-')} "
                f"| `{gap.get('location', '-')}` | {gap.get('description', '-')} |"
            )
    else:
        lines.append("当前结果没有需要额外提示的证据缺口；仍应抽样复核。")

    lines += [
        "",
        "## 算法口径",
        "",
        f"- 节点评分：`{algorithm.get('formula', '-')}`",
        f"- 加权 PageRank：`{algorithm.get('pagerank', '-')}`",
        f"- 约束：{algorithm.get('caveat', '分数只用于排序，事实仍以代码证据为准。')}",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="导出 BLPS 业务优先级报告")
    parser.add_argument("--input", required=True, help="项目分析 JSON 或 deep_analysis JSON")
    parser.add_argument("--output", required=True, help="输出 Markdown 路径")
    args = parser.parse_args()

    priority, project_name = _load_priority(Path(args.input))
    report = render_markdown(priority, project_name)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(f"业务优先级报告已导出: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
