"""
Deep business logic analyzer

Provides project-level call graph, flow extraction, state tracking,
and dependency strength analysis on top of basic AST parsing.
"""

from .project_call_graph import ProjectCallGraph, build_project_call_graph
from .flow_extractor import FlowExtractor, BusinessFlow
from .state_tracker import StateTracker
from .dependency_strength import DependencyStrengthAnalyzer
from .deep_analysis import DeepAnalyzer, DeepAnalysisResult
from .module_architecture import ModuleArchitectureAnalyzer, ArchitectureResult
from .design_pattern_detector import DesignPatternDetector, DesignPatternResult
from .business_priority import (
    BusinessPriorityAnalyzer,
    BusinessPriorityResult,
    NodePriority,
    FlowPriority,
)

__all__ = [
    "ProjectCallGraph",
    "build_project_call_graph",
    "FlowExtractor",
    "BusinessFlow",
    "StateTracker",
    "DependencyStrengthAnalyzer",
    "DeepAnalyzer",
    "DeepAnalysisResult",
    "DesignPatternDetector",
    "DesignPatternResult",
    "BusinessPriorityAnalyzer",
    "BusinessPriorityResult",
    "NodePriority",
    "FlowPriority",
]
