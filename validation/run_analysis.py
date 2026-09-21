"""
Validation analysis runner.

Usage:
    python run_analysis.py <project_path> [output_name]

Runs the full deep analysis pipeline on a given project and saves
the results as JSON for manual verification.
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.project_analyzer.project_parser import ProjectParser
from engine.deep_analyzer import (
    build_project_call_graph,
    FlowExtractor,
    StateTracker,
    DependencyStrengthAnalyzer,
)


def analyze(project_path: str, output_path: str) -> dict:
    """Run full analysis and save to output_path. Returns the result dict."""
    project_name = os.path.basename(project_path.rstrip("\\").rstrip("/"))

    print("=" * 70)
    print(f"Analyzing: {project_name}")
    print(f"Path: {project_path}")
    print("=" * 70)

    # Step 1: Parse project
    print("\n[1/5] Parsing project...")
    parser = ProjectParser()
    project_info = parser.parse_project(project_path)
    print(f"  Files: {project_info.total_files}")
    print(f"  Lines: {project_info.total_lines}")
    print(f"  Classes: {project_info.total_classes}")
    print(f"  Functions: {project_info.total_functions}")

    # Step 2: Build call graph
    print("\n[2/5] Building call graph...")
    cg = build_project_call_graph(project_info)
    print(f"  Nodes: {len(cg.nodes)}")
    print(f"  Edges: {len(cg.edges)}")
    print(f"  Entry points: {len(cg.entry_points)}")

    # Step 3: State tracking
    print("\n[3/5] State change analysis...")
    tracker = StateTracker()
    state_result = tracker.analyze_project(project_info)
    print(f"  Classes analyzed: {len(state_result.classes)}")
    total_state_attrs = sum(len(cs.state_attributes) for cs in state_result.classes.values())
    print(f"  Total state attributes: {total_state_attrs}")

    # Step 4: Extract business flows
    print("\n[4/5] Extracting business flows...")
    extractor = FlowExtractor(cg, state_result)
    flows = extractor.extract_flows(max_flows=10, max_depth=6)
    print(f"  Flows found: {len(flows)}")
    for i, flow in enumerate(flows[:5]):
        print(f"    {i+1}. {flow.name}  (importance={flow.business_importance}, "
              f"modules={len(flow.modules_involved)}, steps={len(flow.steps)})")

    # Step 5: Dependency strength
    print("\n[5/5] Module dependency analysis...")
    dep_analyzer = DependencyStrengthAnalyzer(cg)
    dep_result = dep_analyzer.analyze()
    print(f"  Modules: {len(dep_result.modules)}")
    for name, mod in dep_result.modules.items():
        print(f"    {name}: role={mod.role}, fan_in={mod.fan_in}, fan_out={mod.fan_out}")

    # Build output
    output = {
        "project": {
            "name": project_name,
            "path": project_path,
            "files": project_info.total_files,
            "lines": project_info.total_lines,
            "classes": project_info.total_classes,
            "functions": project_info.total_functions,
        },
        "call_graph": cg.to_dict(),
        "state_analysis": state_result.to_dict(),
        "flows": [f.to_dict() for f in flows],
        "dependency_strength": dep_result.to_dict(),
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nFull analysis saved to: {output_path}")
    print("=" * 70)
    return output


def main():
    if len(sys.argv) < 2:
        print("Usage: python run_analysis.py <project_path> [output_name]")
        print()
        print("Examples:")
        print("  python run_analysis.py python_dotenv")
        print("  python run_analysis.py ../flask flask_result.json")
        sys.exit(1)

    project_path = sys.argv[1]
    if not os.path.isabs(project_path):
        project_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), project_path)

    if len(sys.argv) >= 3:
        output_name = sys.argv[2]
    else:
        output_name = os.path.basename(project_path.rstrip("\\").rstrip("/")) + "_analysis.json"

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", output_name)
    analyze(project_path, output_path)


if __name__ == "__main__":
    main()
