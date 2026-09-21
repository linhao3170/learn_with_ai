"""
Generate full analysis data for frontend demo.

Runs the complete deep analysis pipeline on the lab safety sample project
and outputs JSON that the frontend DeepAnalysisView can consume.

Usage:
    python scripts/generate_deep_data.py

Output:
    frontend/public/demo/deep_analysis.json (full data)
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.project_analyzer.project_parser import ProjectParser
from engine.deep_analyzer import DeepAnalyzer


def main():
    sample_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "sample_projects", "lab_safety_assistant"
    )

    print("Parsing project...")
    parser = ProjectParser()
    project_info = parser.parse_project(sample_path)

    print("Running deep analysis (all 6 components)...")
    da = DeepAnalyzer(max_flows=10, max_flow_depth=6)
    result = da.analyze(project_info)

    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "frontend", "public", "demo"
    )
    os.makedirs(output_dir, exist_ok=True)

    data = result.to_dict()
    data["project"] = {
        "name": project_info.project_name,
        "total_files": project_info.total_files,
        "total_lines": project_info.total_lines,
        "total_classes": project_info.total_classes,
        "total_functions": project_info.total_functions,
    }

    output_path = os.path.join(output_dir, "deep_analysis.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Done! Output: {output_path}")
    print(f"  Call graph nodes: {len(result.call_graph.nodes) if result.call_graph else 0}")
    print(f"  Business flows: {len(result.business_flows)}")
    print(f"  Design patterns: {len(result.design_patterns.patterns) if result.design_patterns else 0}")
    print(
        "  Key implementations: "
        f"{len(result.key_implementations.implementations) if result.key_implementations else 0}"
    )
    print(f"  Architecture nodes: {len(result.architecture.nodes) if result.architecture else 0}")


if __name__ == "__main__":
    main()
