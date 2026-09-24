"""
Project analysis service.

Wraps the existing ProjectAnalyzer (project-level analysis) into a single
API-friendly call.

P0-14（README5 §1.2-⑧）
----------------------
这里**曾经**在 ``ProjectAnalyzer().analyze()`` 之后又跑了一次
``ProjectParser().parse_project()`` + ``DeepAnalyzer().analyze()``，
再用第二次的结果覆盖 ``result["deep_analysis"]``。

那是纯浪费：``ProjectAnalyzer`` 内部已经跑过同一套 ``DeepAnalyzer``
（同样的 ``max_flows=10, max_flow_depth=6``），输出与第二次完全一致。
代价是整条深度分析管线跑两遍（约 2× 时间），
并且让"两套模块识别结果"同时存在，是隐患。

现在只调用一次 ``ProjectAnalyzer``，输出契约不变。
"""

from __future__ import annotations

from pathlib import Path

from engine.project_analyzer import ProjectAnalyzer


def analyze_project(project_path: str) -> dict:
    """Run the full analysis pipeline on a project directory.

    Returns the same JSON contract as before:
    ``project_name / project_path / overview / modules / dependencies /
    core_flows / training / deep_analysis``.
    """
    path = Path(project_path)
    if not path.exists():
        raise FileNotFoundError(f"Project path not found: {project_path}")
    if not path.is_dir():
        raise ValueError(f"Not a directory: {project_path}")

    project_analyzer = ProjectAnalyzer()
    result_obj = project_analyzer.analyze(str(path))
    return result_obj.to_dict()
