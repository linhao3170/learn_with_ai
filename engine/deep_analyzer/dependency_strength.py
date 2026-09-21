"""
Module dependency strength analyzer.

Goes beyond import-level dependencies to calculate real coupling strength
based on actual method calls between modules.

Metrics:
- Call count: how many times module A calls module B
- Unique methods: how many distinct methods in B are called by A
- Call depth: how deep the cross-module calls go
- Directionality: A -> B is different from B -> A
- Core/leaf classification: which modules are central vs peripheral
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple

from .project_call_graph import ProjectCallGraph


@dataclass
class ModuleDepEdge:
    """A directed dependency edge between two modules."""
    from_module: str
    to_module: str
    call_count: int = 0          # total number of calls
    unique_methods: int = 0     # number of distinct target methods called
    cross_module_calls: List[dict] = field(default_factory=list)  # detail
    strength: float = 0.0       # normalized 0-1 strength score


@dataclass
class ModuleDepNode:
    """A module in the dependency graph."""
    module_name: str
    out_edges: List[str] = field(default_factory=list)   # modules it depends on
    in_edges: List[str] = field(default_factory=list)    # modules that depend on it
    fan_out: int = 0      # how many modules it calls
    fan_in: int = 0       # how many modules call it
    centrality: float = 0.0  # page-rank-like centrality
    role: str = "intermediate"  # "core" | "peripheral" | "intermediate" | "orchestrator"
    internal_nodes: int = 0     # number of functions/methods in module
    entry_points: List[str] = field(default_factory=list)


@dataclass
class DependencyStrengthResult:
    """Complete module dependency analysis."""
    modules: Dict[str, ModuleDepNode] = field(default_factory=dict)
    edges: Dict[Tuple[str, str], ModuleDepEdge] = field(default_factory=dict)
    # Sorted by strength
    sorted_edges: List[ModuleDepEdge] = field(default_factory=list)
    # Core-periphery ordering
    core_modules: List[str] = field(default_factory=list)
    peripheral_modules: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "modules": {
                name: {
                    "module": name,
                    "fan_out": node.fan_out,
                    "fan_in": node.fan_in,
                    "centrality": round(node.centrality, 3),
                    "role": node.role,
                    "internal_nodes": node.internal_nodes,
                    "depends_on": node.out_edges,
                    "depended_by": node.in_edges,
                    "entry_points": node.entry_points,
                }
                for name, node in self.modules.items()
            },
            "edges": [
                {
                    "from": edge.from_module,
                    "to": edge.to_module,
                    "call_count": edge.call_count,
                    "unique_methods": edge.unique_methods,
                    "strength": round(edge.strength, 3),
                    "details": edge.cross_module_calls[:10],  # top 10
                }
                for edge in self.sorted_edges
            ],
            "core_modules": self.core_modules,
            "peripheral_modules": self.peripheral_modules,
            "summary": {
                "total_modules": len(self.modules),
                "total_edges": len(self.edges),
            },
        }


class DependencyStrengthAnalyzer:
    """Analyze module-level dependency strength from call graph."""

    def __init__(self, call_graph: ProjectCallGraph):
        self.graph = call_graph
        self.result = DependencyStrengthResult()
        # Modules that are typically noise and not real business modules
        self.noise_modules = {"__init__", "__main__", "setup", "conftest",
                              "test", "tests"}

    def _is_noise_module(self, module_name: str) -> bool:
        """Check if a module is likely noise (not a business module)."""
        base = module_name.split(".")[-1]
        if base in self.noise_modules:
            return True
        if base.startswith("test_") or base.endswith("_test.py"):
            return True
        return False

    def analyze(self) -> DependencyStrengthResult:
        """Run the full analysis."""
        self._collect_module_nodes()
        self._collect_cross_module_edges()
        self._calculate_strength()
        self._calculate_centrality()
        self._classify_modules()
        self._sort_edges()
        return self.result

    def _collect_module_nodes(self):
        """Create a ModuleDepNode for each module in the call graph."""
        for mod_name, node_ids in self.graph.module_nodes.items():
            if self._is_noise_module(mod_name):
                continue
            node = ModuleDepNode(
                module_name=mod_name,
                internal_nodes=len(node_ids),
            )
            # Collect entry points for this module
            for nid in node_ids:
                n = self.graph.get_node(nid)
                if n and n.is_entry_point:
                    node.entry_points.append(nid)
            self.result.modules[mod_name] = node

    def _collect_cross_module_edges(self):
        """Find all cross-module call edges and aggregate them."""
        edges: Dict[Tuple[str, str], ModuleDepEdge] = {}
        target_methods: Dict[Tuple[str, str], Set[str]] = {}

        for edge in self.graph.edges:
            from_node = self.graph.get_node(edge.from_node)
            to_node = self.graph.get_node(edge.to_node)
            if not from_node or not to_node:
                continue

            from_mod = from_node.module_name
            to_mod = to_node.module_name

            # Only count cross-module
            if from_mod == to_mod:
                continue

            # Skip noise modules
            if self._is_noise_module(from_mod) or self._is_noise_module(to_mod):
                continue

            key = (from_mod, to_mod)

            if key not in edges:
                edges[key] = ModuleDepEdge(
                    from_module=from_mod,
                    to_module=to_mod,
                )
                target_methods[key] = set()

            edges[key].call_count += edge.call_count
            target_methods[key].add(edge.to_node)
            edges[key].cross_module_calls.append({
                "from_method": edge.from_node,
                "to_method": edge.to_node,
                "call_type": edge.call_type,
                "line": edge.line_number,
                "count": edge.call_count,
            })

        # Fill in unique method counts
        for key, edge in edges.items():
            edge.unique_methods = len(target_methods[key])

        self.result.edges = edges

        # Update module in/out edges
        for (from_mod, to_mod), edge in edges.items():
            if from_mod in self.result.modules:
                if to_mod not in self.result.modules[from_mod].out_edges:
                    self.result.modules[from_mod].out_edges.append(to_mod)
                self.result.modules[from_mod].fan_out = len(
                    self.result.modules[from_mod].out_edges
                )
            if to_mod in self.result.modules:
                if from_mod not in self.result.modules[to_mod].in_edges:
                    self.result.modules[to_mod].in_edges.append(from_mod)
                self.result.modules[to_mod].fan_in = len(
                    self.result.modules[to_mod].in_edges
                )

    def _calculate_strength(self):
        """Normalize edge strengths to 0-1 range."""
        if not self.result.edges:
            return

        max_calls = max(e.call_count for e in self.result.edges.values())
        if max_calls == 0:
            max_calls = 1

        for edge in self.result.edges.values():
            # Combine call count and unique methods into a strength score
            call_score = min(edge.call_count / max_calls, 1.0)
            method_score = min(edge.unique_methods / 5.0, 1.0)  # 5+ methods = max
            edge.strength = round(call_score * 0.6 + method_score * 0.4, 3)

    def _calculate_centrality(self):
        """
        Simple centrality: weighted combination of fan_in and fan_out.

        Modules with high fan_in are depended upon (core utilities).
        Modules with high fan_out are orchestrators.
        """
        if not self.result.modules:
            return

        max_fan_in = max(m.fan_in for m in self.result.modules.values()) or 1
        max_fan_out = max(m.fan_out for m in self.result.modules.values()) or 1

        for name, mod in self.result.modules.items():
            in_score = mod.fan_in / max_fan_in
            out_score = mod.fan_out / max_fan_out
            # Centrality: being depended on = more central
            # Orchestrating also matters
            mod.centrality = round(in_score * 0.7 + out_score * 0.3, 3)

    def _classify_modules(self):
        """
        Classify each module into a role:
        - core: high fan_in, depended upon by many
        - orchestrator: high fan_out, coordinates many modules
        - peripheral: low fan_in and low fan_out
        - intermediate: moderate both
        """
        if not self.result.modules:
            return

        # Sort by centrality
        sorted_by_centrality = sorted(
            self.result.modules.values(),
            key=lambda m: m.centrality,
            reverse=True,
        )

        n = len(sorted_by_centrality)
        for i, mod in enumerate(sorted_by_centrality):
            if n <= 2:
                mod.role = "intermediate"
            elif i == 0 and mod.fan_out >= 2:
                mod.role = "orchestrator"
            elif mod.centrality >= 0.6:
                mod.role = "core"
            elif mod.centrality <= 0.2:
                mod.role = "peripheral"
            else:
                mod.role = "intermediate"

            # Additional: high fan_out but low fan_in = orchestrator
            if mod.fan_out >= 2 and mod.fan_in <= 1:
                mod.role = "orchestrator"

        self.result.core_modules = [
            m.module_name for m in sorted_by_centrality
            if m.role in ("core", "orchestrator")
        ]
        self.result.peripheral_modules = [
            m.module_name for m in sorted_by_centrality
            if m.role == "peripheral"
        ]

    def _sort_edges(self):
        """Sort edges by strength descending."""
        self.result.sorted_edges = sorted(
            self.result.edges.values(),
            key=lambda e: e.strength,
            reverse=True,
        )
