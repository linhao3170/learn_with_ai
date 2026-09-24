"""
Test script for the deep analyzer modules.

Runs the full deep analysis pipeline on the lab_safety_assistant sample project
and prints a summary of results for quick verification.

Output (P0-15): this script OWNS ``validation/results/deep_analysis_test.json``
(debug/report shape: ``{project, call_graph, flows, state_analysis, ...}``).
It must NOT write ``deep_analysis.json`` -- that canonical DeepAnalysisResult
artifact belongs to ``scripts/generate_deep_data.py``. Two scripts writing the
same path silently overwrote each other's (differently shaped) output.
"""

import sys
import os
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.project_analyzer.project_parser import ProjectParser
from engine.deep_analyzer import (
    DeepAnalyzer,
)


def main():
    sample_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "sample_projects", "lab_safety_assistant"
    )

    print("=" * 70)
    print("Deep Analyzer Test: lab_safety_assistant")
    print("=" * 70)

    # Step 1: Parse project
    print("\n[1/2] Parsing project...")
    parser = ProjectParser()
    project_info = parser.parse_project(sample_path)
    print(f"  Files: {project_info.total_files}")
    print(f"  Lines: {project_info.total_lines}")
    print(f"  Classes: {project_info.total_classes}")
    print(f"  Functions: {project_info.total_functions}")

    # Step 2: Run full deep analysis pipeline
    print("\n[2/2] Running deep analysis pipeline...")
    analyzer = DeepAnalyzer()
    analysis_result = analyzer.analyze(project_info)

    cg = analysis_result.call_graph
    flows = analysis_result.business_flows
    state_result = analysis_result.state_analysis
    dep_result = analysis_result.dependency_strength
    ki_result = analysis_result.key_implementations

    print(f"  Call graph nodes: {len(cg.nodes)}")
    print(f"  Call graph edges: {len(cg.edges)}")
    print(f"  Business flows: {len(flows)}")
    print(f"  Key implementations: {len(ki_result.implementations) if ki_result else 0}")

    # Show cross-module calls
    cross_module = []
    for edge in cg.edges:
        from_mod = edge.from_node.split(":")[0]
        to_mod = edge.to_node.split(":")[0]
        if from_mod != to_mod:
            cross_module.append(edge)
    print(f"  Cross-module edges: {len(cross_module)}")
    if cross_module:
        print("  Cross-module call examples:")
        for edge in cross_module[:8]:
            print(f"    {edge.from_node}  --[{edge.call_type}]-->  {edge.to_node}")

    # Show entry points
    print(f"\n  Top entry points (by outgoing call count):")
    entry_sorted = sorted(
        cg.entry_points,
        key=lambda nid: len(cg.get_node(nid).calls) if cg.get_node(nid) else 0,
        reverse=True,
    )
    for nid in entry_sorted[:8]:
        node = cg.get_node(nid)
        if node:
            print(f"    {nid}  (calls: {len(node.calls)}, tags: {','.join(node.tags)})")

    # Show state analysis summary
    print(f"\n  State analysis summary:")
    print(f"  Classes analyzed: {len(state_result.classes)}")
    for key, cs in state_result.classes.items():
        print()
        print(f"  Class: {key}")
        if cs.state_attributes:
            print(f"    State attributes: {', '.join(list(cs.state_attributes)[:5])}")
        if cs.dict_like_attrs:
            print(f"    Dict-like attrs: {', '.join(list(cs.dict_like_attrs)[:5])}")
        if cs.class_constants:
            print(f"    Class constants: {', '.join(list(cs.class_constants)[:5])}")
        writers = [m for m, w in cs.method_writes.items() if w]
        dict_writers = [m for m, w in cs.method_dict_writes.items() if w]
        all_writers = sorted(set(writers + dict_writers))
        readers = [
            m for m, r in cs.method_reads.items()
            if r and m not in all_writers and not m.startswith("_")
        ]
        if all_writers:
            print(f"    State-writing methods ({len(all_writers)}): {', '.join(all_writers[:5])}")
        if readers:
            print(f"    Pure query methods ({len(readers)}): {', '.join(readers[:5])}")

    # Show business flows
    print(f"\n  Business flows summary:")
    for i, flow in enumerate(flows[:6]):
        print(f"\n  Flow {i+1}: {flow.name}")
        print(f"    Importance: {flow.business_importance}")
        print(f"    Modules: {', '.join(flow.modules_involved)}")
        print(f"    Cross-module calls: {flow.cross_module_count}")
        print(f"    Steps ({len(flow.steps)}):")
        for step in flow.steps[:5]:
            indent = "  " * (step.depth + 2)
            boundary = " [CROSS-MODULE]" if step.is_module_boundary else ""
            state = " [STATE_CHANGE]" if step.is_state_change else ""
            val = " [VALIDATION]" if step.is_validation else ""
            mod_short = step.module_name.split("_")[0][:6]
            print(f"{indent}{step.method_name}  ({mod_short}){boundary}{state}{val}")

    # Show key implementations
    if ki_result and ki_result.implementations:
        print(f"\n  Key implementations summary:")
        for i, impl in enumerate(ki_result.implementations[:3]):
            print(f"\n  #{i+1}: {impl.method_name} (score: {impl.importance_score})")
            print(f"    Module: {impl.module_name}")
            print(f"    Lines: {impl.start_line}-{impl.end_line}")
            if impl.design_characteristics:
                print(f"    Design characteristics:")
                for char in impl.design_characteristics[:3]:
                    conf_icon = "[OK]" if char["confidence"] == "verified" else "[?]"
                    print(f"      {conf_icon} {char['label']} ({char['evidence']})")
            if impl.algorithm_hints:
                ah = impl.algorithm_hints
                conf_icon = "[OK]" if ah.get("confidence") == "verified" else "[?]"
                print(f"    Algorithm: {conf_icon} {ah.get('detected', 'N/A')}")

    # Show dependency strength
    print(f"\n[Bonus] Module dependency strength...")
    print(f"  Modules: {len(dep_result.modules)}")
    print(f"  Edges: {len(dep_result.edges)}")
    for mod_name, mod_node in list(dep_result.modules.items())[:8]:
        print(f"    {mod_name}: role={mod_node.role}, fan_in={mod_node.fan_in}, fan_out={mod_node.fan_out}, centrality={mod_node.centrality:.1f}")
    print(f"  Strongest dependencies:")
    for edge in dep_result.sorted_edges[:4]:
        print(f"    {edge.from_module} -> {edge.to_module}: strength={edge.strength:.2f}, calls={edge.call_count}, methods={edge.unique_methods}")

    # Save full JSON for debugging
    # P0-16: 引擎产物写到 validation/results/，不再污染 frontend/public/（Web 根目录）
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation", "results",
    )
    os.makedirs(output_dir, exist_ok=True)

    output = {
        "project": {
            "name": project_info.project_name,
            "files": project_info.total_files,
            "lines": project_info.total_lines,
        },
        "call_graph": cg.to_dict(),
        "flows": [f.to_dict() for f in flows],
        "state_analysis": state_result.to_dict(),
        "dependency_strength": dep_result.to_dict(),
        "key_implementations": ki_result.to_dict() if ki_result else {},
        "business_priority": (
            analysis_result.business_priority.to_dict()
            if analysis_result.business_priority else {}
        ),
    }

    # P0-15: this script OWNS validation/results/deep_analysis_test.json (debug shape:
    # {project, call_graph, flows, ...}); generate_deep_data.py owns the canonical deep_analysis.json.
    output_path = os.path.join(output_dir, "deep_analysis_test.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nFull analysis saved to: {output_path}")

    print("\n" + "=" * 70)
    print("Test complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
