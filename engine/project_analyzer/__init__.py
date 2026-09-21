"""
项目级业务逻辑分析器

从项目（多文件/多模块）级别分析业务结构，
包括模块识别、职责推断、依赖关系、核心流程提取、训练题生成。
"""

from .project_parser import ProjectParser, ProjectInfo
from .module_analyzer import ModuleAnalyzer, ModuleInfo
from .training_generator import TrainingGenerator, TrainingSet
from .main import ProjectAnalyzer, ProjectAnalysisResult

__all__ = [
    "ProjectAnalyzer",
    "ProjectAnalysisResult",
    "ProjectParser",
    "ProjectInfo",
    "ModuleAnalyzer",
    "ModuleInfo",
    "TrainingGenerator",
    "TrainingSet",
]
