"""
Project analysis service.

Wraps the existing ProjectAnalyzer (project-level analysis) and DeepAnalyzer
(deep business analysis) into a single API-friendly call.

The pipeline:
  1. ProjectAnalyzer.analyze() — modules, dependencies, core flows, training
  2. DeepAnalyzer — call graph, state tracking, key implementations, etc.

Returns a dict that matches the frontend's expected data shape
(same structure as frontend/public/demo/project_analysis.json).
"""

from __future__ import annotations

from pathlib import Path

from engine.project_analyzer import ProjectAnalyzer
from engine.project_analyzer.project_parser import ProjectParser
from engine.deep_analyzer.deep_analysis import DeepAnalyzer


def analyze_project(project_path: str) -> dict:
    """Run the full analysis pipeline on a project directory."""
    path = Path(project_path)
    if not path.exists():
        raise FileNotFoundError(f"Project path not found: {project_path}")
    if not path.is_dir():
        raise ValueError(f"Not a directory: {project_path}")

    # Step 1: Project-level analysis (modules, flows, training questions)
    project_analyzer = ProjectAnalyzer()
    result_obj = project_analyzer.analyze(str(path))
    result = result_obj.to_dict()

    # Step 2: Deep analysis (call graph, state, key implementations...)
    parser = ProjectParser()
    project_info = parser.parse_project(str(path))

    deep_analyzer = DeepAnalyzer(max_flows=10, max_flow_depth=6)
    deep_result = deep_analyzer.analyze(project_info)
    result["deep_analysis"] = deep_result.to_dict()

    return result
