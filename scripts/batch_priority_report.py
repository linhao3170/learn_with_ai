"""Run BLPS on several local projects and create a manual-review template.

The script deliberately does not invent accuracy numbers.  It records what
the engine extracted and leaves the correctness/error columns blank for a
teacher or reviewer to fill after checking the referenced code.

Example::

    python scripts/batch_priority_report.py \
      sample_projects/lab_safety_assistant \
      validation/flask/examples/tutorial \
      --output validation/batch_priority_review.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.deep_analyzer import DeepAnalyzer
from engine.project_analyzer.project_parser import ProjectParser


def analyze_path(project_path: Path) -> Dict[str, Any]:
    parser = ProjectParser()
    info = parser.parse_project(str(project_path))
    result = DeepAnalyzer().analyze(info)
    priority = result.business_priority.to_dict()
    summary = priority.get("summary", {})
    top_node = (priority.get("node_scores") or [{}])[0]
    top_flow = (priority.get("flow_scores") or [{}])[0]
    return {
        "project": info.project_name,
        "path": str(project_path),
        "files": info.total_files,
        "lines": info.total_lines,
        "nodes": summary.get("total_nodes", 0),
        "flows": summary.get("total_flows", 0),
        "top_node": top_node.get("node_id", ""),
        "top_flow": top_flow.get("name", ""),
        "review_gaps": summary.get("review_gap_count", 0),
        "evidence_completeness": summary.get("evidence_completeness", 0),
        "status": "ok",
    }


def render_markdown(rows: List[Dict[str, Any]]) -> str:
    lines = [
        "# BLPS 多项目实测候选报告",
        "",
        "> 本表只记录引擎抽取结果；正确数、错误数和错误率必须由人工核对代码后填写。",
        "",
        "## 抽取结果",
        "",
        "| 项目 | 文件 | 行数 | 节点 | 流程 | 最高优先级节点 | 最高优先级流程 | 待审核提示 | 证据完整度 | 状态 |",
        "|---|---:|---:|---:|---:|---|---|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['project']} | {row['files']} | {row['lines']} | {row['nodes']} | {row['flows']} "
            f"| `{row['top_node'] or '-'}` | {row['top_flow'] or '-'} | {row['review_gaps']} "
            f"| {float(row['evidence_completeness']) * 100:.1f}% | {row['status']} |"
        )

    lines += [
        "",
        "## 人工核对记录（必须填写）",
        "",
        "| 项目 | 抽查事实数 | 错误数 | 错误率 | 主要错误类型 | 核对人/日期 |",
        "|---|---:|---:|---:|---|---|",
    ]
    for row in rows:
        lines.append(f"| {row['project']} | 待填写 | 待填写 | 待填写 | 待填写 | 待填写 |")

    lines += [
        "",
        "## 使用规则",
        "",
        "1. 先保留原始 JSON，再按事实 ID 逐条核对；",
        "2. 把错误按动态调用、模块边界、状态追踪、语义推断等类型归档；",
        "3. 只有填完人工核对记录后，才可以把错误率写入申报书；",
        "4. BLPS 分数用于确定讲解/审核顺序，不作为准确率。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="批量生成 BLPS 多项目人工核对模板")
    parser.add_argument("projects", nargs="+", help="项目目录，可传多个")
    parser.add_argument("--output", required=True, help="Markdown 输出路径")
    parser.add_argument("--json-output", help="可选，保存原始汇总 JSON")
    args = parser.parse_args()

    rows: List[Dict[str, Any]] = []
    for raw_path in args.projects:
        project_path = Path(raw_path).resolve()
        if not project_path.is_dir():
            rows.append({"project": project_path.name, "path": str(project_path), "status": "missing", "files": 0, "lines": 0, "nodes": 0, "flows": 0, "top_node": "", "top_flow": "", "review_gaps": 0, "evidence_completeness": 0})
            continue
        try:
            rows.append(analyze_path(project_path))
        except Exception as exc:  # keep the batch useful when one project is malformed
            rows.append({"project": project_path.name, "path": str(project_path), "status": f"error: {type(exc).__name__}", "files": 0, "lines": 0, "nodes": 0, "flows": 0, "top_node": "", "top_flow": "", "review_gaps": 0, "evidence_completeness": 0})

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_markdown(rows), encoding="utf-8")
    if args.json_output:
        json_output = Path(args.json_output)
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"多项目 BLPS 报告已导出: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
