"""
Module architecture analyzer.

Takes the module dependency graph and produces a layered architecture view
suitable for visualization. Modules are assigned to layers based on their
role and dependency direction, and edges are classified by type.

Architecture layers (top to bottom):
  - Presentation/Orchestration layer: entry points, coordinators
  - Business/Core layer: core business logic
  - Support layer: utilities, helpers, peripheral modules
  - Infrastructure layer: data access, external services
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple

from .dependency_strength import DependencyStrengthResult, ModuleDepNode


@dataclass
class ArchitectureNode:
    """A module in the architecture diagram."""
    module_id: str
    display_name: str
    layer: str              # "orchestration" | "business" | "support" | "infrastructure"
    role: str               # orchestrator | core | peripheral
    x: float = 0.0          # suggested x position
    y: float = 0.0          # suggested y position (by layer)
    width: float = 180.0
    height: float = 80.0
    method_count: int = 0
    entry_points: List[str] = field(default_factory=list)
    responsibilities: List[str] = field(default_factory=list)


@dataclass
class ArchitectureEdge:
    """A dependency edge in the architecture diagram."""
    from_module: str
    to_module: str
    edge_type: str          # "orchestration" | "data_flow" | "utility"
    strength: float = 0.0
    call_count: int = 0
    label: str = ""


@dataclass
class ArchitectureResult:
    """Complete module architecture analysis."""
    nodes: Dict[str, ArchitectureNode] = field(default_factory=dict)
    edges: List[ArchitectureEdge] = field(default_factory=list)
    layers: List[str] = field(default_factory=list)
    layout: dict = field(default_factory=dict)  # layout metadata for frontend

    def to_dict(self) -> dict:
        return {
            "nodes": {
                nid: {
                    "module_id": n.module_id,
                    "display_name": n.display_name,
                    "layer": n.layer,
                    "role": n.role,
                    "x": round(n.x, 1),
                    "y": round(n.y, 1),
                    "width": n.width,
                    "height": n.height,
                    "method_count": n.method_count,
                    "entry_points": n.entry_points,
                    "responsibilities": n.responsibilities,
                }
                for nid, n in self.nodes.items()
            },
            "edges": [
                {
                    "from": e.from_module,
                    "to": e.to_module,
                    "type": e.edge_type,
                    "strength": round(e.strength, 3),
                    "call_count": e.call_count,
                    "label": e.label,
                }
                for e in self.edges
            ],
            "layers": self.layers,
            "layout": self.layout,
        }


LAYER_NAMES = ["orchestration", "business", "support", "infrastructure"]


class ModuleArchitectureAnalyzer:
    """
    Analyze module architecture and produce a layered diagram.

    Assigns modules to layers based on dependency direction and role,
    then computes a simple layout for visualization.
    """

    def __init__(self, dep_result: DependencyStrengthResult):
        self.dep = dep_result
        self.result = ArchitectureResult(layers=LAYER_NAMES)

    def analyze(self) -> ArchitectureResult:
        """Run the full architecture analysis."""
        self._assign_layers()
        self._classify_edges()
        self._compute_layout()
        return self.result

    def _assign_layers(self):
        """Assign each module to a layer based on role and dependencies."""
        for name, mod in self.dep.modules.items():
            layer = self._determine_layer(mod)
            display_name = self._generate_display_name(name, mod)
            responsibilities = self._generate_responsibilities(name, mod)

            node = ArchitectureNode(
                module_id=name,
                display_name=display_name,
                layer=layer,
                role=mod.role,
                method_count=mod.internal_nodes,
                entry_points=mod.entry_points,
                responsibilities=responsibilities,
            )
            self.result.nodes[name] = node

    def _determine_layer(self, mod: ModuleDepNode) -> str:
        """Determine which layer a module belongs to."""
        # Orchestrators (high fan_out, low fan_in) go to top layer
        if mod.role == "orchestrator":
            return "orchestration"

        # Core modules with high fan_in are business layer
        if mod.role == "core":
            return "business"

        # Intermediate modules go to business or support based on dependencies
        if mod.role == "intermediate":
            if mod.fan_in >= mod.fan_out:
                return "business"
            return "support"

        # Peripheral modules go to support layer
        if mod.role == "peripheral":
            return "support"

        return "support"

    def _generate_display_name(self, module_id: str, mod: ModuleDepNode) -> str:
        """Generate a human-readable display name for a module."""
        # Convert snake_case to Title Case
        name = module_id.replace("_", " ").title()
        return name

    def _generate_responsibilities(self, module_id: str, mod: ModuleDepNode) -> List[str]:
        """Generate brief responsibility tags based on module name."""
        name_lower = module_id.lower()
        tags = []

        keyword_map = [
            ("app", ["System Entry", "Orchestration"]),
            ("main", ["Main Entry", "Coordination"]),
            ("user", ["User Management", "Authentication"]),
            ("auth", ["Authentication", "Authorization"]),
            ("reservation", ["Booking", "Scheduling"]),
            ("booking", ["Booking", "Scheduling"]),
            ("order", ["Order Processing"]),
            ("equipment", ["Equipment Tracking", "Inventory"]),
            ("device", ["Device Management"]),
            ("safety", ["Safety Checks", "Compliance"]),
            ("check", ["Validation", "Verification"]),
            ("report", ["Reporting", "Analytics"]),
            ("notification", ["Notifications", "Alerts"]),
            ("db", ["Data Storage"]),
            ("database", ["Data Storage"]),
            ("repository", ["Data Access"]),
            ("util", ["Utilities"]),
            ("helper", ["Helpers"]),
            ("api", ["API Layer", "Endpoints"]),
            ("route", ["Routing", "Endpoints"]),
            ("controller", ["Request Handling"]),
            ("service", ["Business Logic"]),
            ("manager", ["Management"]),
        ]

        for keyword, kws in keyword_map:
            if keyword in name_lower:
                tags.extend(kws)
                if len(tags) >= 4:
                    break

        if not tags:
            tags = ["Business Logic"]

        # Deduplicate while preserving order
        seen = set()
        result = []
        for t in tags:
            if t not in seen:
                seen.add(t)
                result.append(t)
        return result[:4]

    def _classify_edges(self):
        """Classify each dependency edge by type."""
        for edge in self.dep.sorted_edges:
            from_node = self.dep.modules.get(edge.from_module)
            to_node = self.dep.modules.get(edge.to_module)

            if not from_node or not to_node:
                continue

            # Determine edge type
            if from_node.role == "orchestrator":
                edge_type = "orchestration"
                label = "coordinates"
            elif edge.strength >= 0.5:
                edge_type = "data_flow"
                label = "strong dependency"
            else:
                edge_type = "utility"
                label = "uses"

            arch_edge = ArchitectureEdge(
                from_module=edge.from_module,
                to_module=edge.to_module,
                edge_type=edge_type,
                strength=edge.strength,
                call_count=edge.call_count,
                label=label,
            )
            self.result.edges.append(arch_edge)

    def _compute_layout(self):
        """
        Compute a simple layered layout.

        Modules are placed in rows by layer, distributed evenly across
        the row width. This gives the frontend a starting position that
        can be refined by the visualization library.
        """
        # Group modules by layer
        layer_modules: Dict[str, List[str]] = {}
        for layer in LAYER_NAMES:
            layer_modules[layer] = []

        for name, node in self.result.nodes.items():
            layer_modules[node.layer].append(name)

        # Remove empty layers
        active_layers = [l for l in LAYER_NAMES if layer_modules[l]]
        self.result.layers = active_layers

        row_height = 120.0
        col_width = 220.0
        top_margin = 40.0
        left_margin = 40.0

        # Place modules in rows
        max_cols = 0
        for layer_idx, layer in enumerate(active_layers):
            modules_in_layer = layer_modules[layer]
            n = len(modules_in_layer)
            max_cols = max(max_cols, n)
            y = top_margin + layer_idx * row_height

            for i, mod_name in enumerate(modules_in_layer):
                # Center the row
                row_width = n * col_width
                total_width = max(n * col_width, 400)
                start_x = left_margin + (total_width - row_width) / 2
                x = start_x + i * col_width

                self.result.nodes[mod_name].x = x
                self.result.nodes[mod_name].y = y

        # Layout metadata
        self.result.layout = {
            "layer_count": len(active_layers),
            "max_modules_per_layer": max_cols,
            "row_height": row_height,
            "column_width": col_width,
            "total_height": len(active_layers) * row_height + top_margin * 2,
            "total_width": max_cols * col_width + left_margin * 2,
        }
