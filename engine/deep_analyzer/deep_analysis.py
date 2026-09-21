"""
Unified deep analysis facade.

Integrates call graph, state tracking, flow extraction, and dependency
strength analysis into a single pipeline that can be dropped into the
project-level analyzer.

This replaces the old keyword-based module/flow analysis with data derived
from actual code structure and call relationships.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional

from .project_call_graph import ProjectCallGraph, build_project_call_graph
from .flow_extractor import FlowExtractor, BusinessFlow
from .state_tracker import StateTracker, StateAnalysis
from .dependency_strength import (
    DependencyStrengthAnalyzer,
    DependencyStrengthResult,
)
from .module_architecture import ModuleArchitectureAnalyzer, ArchitectureResult
from .key_implementation import KeyImplementationAnalyzer, KeyImplementationResult
from .design_pattern_detector import DesignPatternDetector, DesignPatternResult
from .business_priority import BusinessPriorityAnalyzer, BusinessPriorityResult


@dataclass
class DeepAnalysisResult:
    """
    Unified deep analysis result.

    Contains all deep-analysis artifacts plus convenience accessors for
    common use cases (module list, flow list, etc.).
    """
    call_graph: Optional[ProjectCallGraph] = None
    state_analysis: Optional[StateAnalysis] = None
    dependency_strength: Optional[DependencyStrengthResult] = None
    business_flows: List[BusinessFlow] = field(default_factory=list)
    architecture: Optional[ArchitectureResult] = None
    key_implementations: Optional[KeyImplementationResult] = None
    design_patterns: Optional[DesignPatternResult] = None
    # Evidence-aware ranking of core business logic for teaching/review.
    business_priority: Optional[BusinessPriorityResult] = None

    # ---- Convenience accessors ----

    @property
    def modules(self) -> List[dict]:
        """Return module summary list (sorted by centrality)."""
        if not self.dependency_strength:
            return []
        mods = self.dependency_strength.modules
        sorted_mods = sorted(
            mods.values(),
            key=lambda m: m.centrality,
            reverse=True,
        )
        result = []
        for mod in sorted_mods:
            result.append({
                "module_id": mod.module_name,
                "name": mod.module_name,
                "role": mod.role,
                "fan_in": mod.fan_in,
                "fan_out": mod.fan_out,
                "centrality": mod.centrality,
                "internal_nodes": mod.internal_nodes,
                "entry_points": mod.entry_points,
                "depends_on": mod.out_edges,
                "depended_by": mod.in_edges,
            })
        return result

    @property
    def module_dependencies(self) -> List[dict]:
        """Return module dependency edges sorted by strength."""
        if not self.dependency_strength:
            return []
        return [
            {
                "from": edge.from_module,
                "to": edge.to_module,
                "call_count": edge.call_count,
                "unique_methods": edge.unique_methods,
                "strength": edge.strength,
            }
            for edge in self.dependency_strength.sorted_edges
        ]

    @property
    def core_modules(self) -> List[str]:
        if self.dependency_strength:
            return self.dependency_strength.core_modules
        return []

    @property
    def peripheral_modules(self) -> List[str]:
        if self.dependency_strength:
            return self.dependency_strength.peripheral_modules
        return []

    @property
    def architecture_layers(self) -> List[dict]:
        """Return architecture layers with modules grouped by layer."""
        if not self.architecture:
            return []
        layers = {}
        for name, node in self.architecture.nodes.items():
            if node.layer not in layers:
                layers[node.layer] = []
            layers[node.layer].append(name)
        return [
            {"layer": layer, "modules": layers.get(layer, [])}
            for layer in self.architecture.layers
        ]

    def to_dict(self) -> dict:
        """Serialize the full result."""
        return {
            "call_graph": self.call_graph.to_dict() if self.call_graph else {},
            "state_analysis": self.state_analysis.to_dict() if self.state_analysis else {},
            "dependency_strength": (
                self.dependency_strength.to_dict()
                if self.dependency_strength else {}
            ),
            "business_flows": [f.to_dict() for f in self.business_flows],
            "architecture": self.architecture.to_dict() if self.architecture else {},
            "key_implementations": (
                self.key_implementations.to_dict()
                if self.key_implementations else {}
            ),
            "design_patterns": (
                self.design_patterns.to_dict()
                if self.design_patterns else {}
            ),
            "business_priority": (
                self.business_priority.to_dict()
                if self.business_priority else {}
            ),
        }


class DeepAnalyzer:
    """
    Unified deep analysis engine.

    Runs the full pipeline: call graph -> state tracking -> flow extraction
    -> dependency strength, and returns a unified result.
    """

    def __init__(self, max_flows: int = 10, max_flow_depth: int = 6):
        self.max_flows = max_flows
        self.max_flow_depth = max_flow_depth

    def analyze(self, project_info) -> DeepAnalysisResult:
        """
        Run the full deep analysis pipeline on a parsed project.

        Args:
            project_info: ProjectInfo from project_parser

        Returns:
            DeepAnalysisResult with all analysis artifacts
        """
        result = DeepAnalysisResult()

        # Step 1: Build project-level call graph
        result.call_graph = build_project_call_graph(project_info)

        # Step 1b: Detect design patterns
        dp_detector = DesignPatternDetector()
        result.design_patterns = dp_detector.detect_from_project(project_info)

        # Step 2: State change analysis
        tracker = StateTracker()
        result.state_analysis = tracker.analyze_project(project_info)

        # Step 3: Extract business flows (with state info)
        extractor = FlowExtractor(result.call_graph, result.state_analysis)
        result.business_flows = extractor.extract_flows(
            max_flows=self.max_flows,
            max_depth=self.max_flow_depth,
        )

        # Step 4: Module dependency strength
        dep_analyzer = DependencyStrengthAnalyzer(result.call_graph)
        result.dependency_strength = dep_analyzer.analyze()

        # Step 5: Module architecture view (layered diagram)
        arch_analyzer = ModuleArchitectureAnalyzer(result.dependency_strength)
        result.architecture = arch_analyzer.analyze()

        # Step 6: Key implementation analysis
        ki_analyzer = KeyImplementationAnalyzer(
            result.call_graph, result.state_analysis, result.design_patterns
        )
        result.key_implementations = ki_analyzer.analyze(max_results=10)

        # Step 7: Rank the business logic that deserves teaching/review first.
        # This is a reproducible ranking layer; it does not replace AST facts.
        priority_analyzer = BusinessPriorityAnalyzer()
        result.business_priority = priority_analyzer.analyze(
            result.call_graph,
            result.state_analysis,
            result.business_flows,
        )

        return result
