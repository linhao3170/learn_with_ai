"""
Business flow extractor.

Starting from entry-point methods, traverse the project call graph to extract
complete cross-module business flows. Each flow is a sequence of call steps
with evidence (line numbers, module boundaries, state changes).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple
from collections import deque

from .project_call_graph import ProjectCallGraph, CallNode


@dataclass
class FlowStep:
    """A single step in a business flow."""
    step_id: str
    node_id: str
    module_name: str
    class_name: Optional[str]
    method_name: str
    step_order: int
    depth: int
    call_type: str
    line_number: int
    tags: List[str] = field(default_factory=list)
    is_module_boundary: bool = False
    is_state_change: bool = False
    is_validation: bool = False
    description: str = ""


@dataclass
class BusinessFlow:
    """A complete business flow extracted from the call graph."""
    flow_id: str
    name: str
    description: str
    entry_node: str
    steps: List[FlowStep] = field(default_factory=list)
    modules_involved: List[str] = field(default_factory=list)
    cross_module_count: int = 0
    has_validation: bool = False
    has_state_change: bool = False
    complexity_score: float = 0.0
    business_importance: float = 0.0

    def to_dict(self) -> dict:
        return {
            "flow_id": self.flow_id,
            "name": self.name,
            "description": self.description,
            "entry_node": self.entry_node,
            "steps": [
                {
                    "step_id": s.step_id,
                    "node_id": s.node_id,
                    "module": s.module_name,
                    "class": s.class_name,
                    "method": s.method_name,
                    "order": s.step_order,
                    "depth": s.depth,
                    "call_type": s.call_type,
                    "line": s.line_number,
                    "tags": s.tags,
                    "is_module_boundary": s.is_module_boundary,
                    "is_state_change": s.is_state_change,
                    "is_validation": s.is_validation,
                    "description": s.description,
                }
                for s in self.steps
            ],
            "modules_involved": self.modules_involved,
            "cross_module_count": self.cross_module_count,
            "has_validation": self.has_validation,
            "has_state_change": self.has_state_change,
            "complexity_score": round(self.complexity_score, 2),
            "business_importance": round(self.business_importance, 2),
        }


class FlowExtractor:
    """Extract business flows from a project call graph."""

    def __init__(self, call_graph: ProjectCallGraph, state_tracker_result=None):
        self.graph = call_graph
        self.state = state_tracker_result  # optional StateAnalysis
        self.flows: List[BusinessFlow] = []

    def _is_state_change(self, node: CallNode) -> bool:
        """Check if a method mutates state. Uses state_tracker when available."""
        if self.state and node.class_name and node.kind == "method":
            cs = self.state.get_class_state(node.module_name, node.class_name)
            if cs:
                writes = cs.method_writes.get(node.name, [])
                dict_writes = cs.method_dict_writes.get(node.name, [])
                if writes or dict_writes:
                    return True
        # Fallback to tags
        return any(t in node.tags for t in ["update", "creation", "state_change", "deletion"])

    def _is_validation(self, node: CallNode) -> bool:
        """Check if a method does validation."""
        if "validation" in node.tags:
            return True
        # Heuristic: method name suggests checking/validation
        name = node.name.lower()
        return any(kw in name for kw in ["check", "verify", "validate", "conflict", "permission"])

    def extract_flows(self, max_flows: int = 10, max_depth: int = 6) -> List[BusinessFlow]:
        """Extract the most important business flows."""
        entry_points = self._find_business_entry_points()

        flows = []
        for i, entry_id in enumerate(entry_points):
            flow = self._extract_single_flow(
                flow_id=f"flow_{i+1}",
                entry_node_id=entry_id,
                max_depth=max_depth,
            )
            if flow and len(flow.steps) >= 2:
                flows.append(flow)

        self._score_flows(flows)
        flows.sort(key=lambda f: f.business_importance, reverse=True)

        self.flows = flows[:max_flows]
        return self.flows

    def _find_business_entry_points(self) -> List[str]:
        """Find likely business operation entry points."""
        candidates = []

        business_verbs = {
            "create", "add", "register", "approve", "reject", "cancel",
            "perform", "submit", "process", "complete", "close", "assign",
            "borrow", "return", "deactivate", "initialize", "login",
            "checkout", "place", "send", "generate", "calculate",
        }

        for nid, node in self.graph.nodes.items():
            if not node.is_entry_point:
                continue
            if node.name.startswith("_"):
                continue
            if not node.calls:
                continue

            name_lower = node.name.lower()
            has_business_verb = any(verb in name_lower for verb in business_verbs)
            has_doc = bool(node.docstring)
            orchestration = len(node.calls)

            score = 0
            if has_business_verb:
                score += 3
            if has_doc:
                score += 1
            score += min(orchestration, 5)

            if score >= 2:
                candidates.append((nid, score))

        candidates.sort(key=lambda x: x[1], reverse=True)
        return [nid for nid, _ in candidates]

    def _extract_single_flow(self, flow_id: str, entry_node_id: str,
                             max_depth: int = 6) -> Optional[BusinessFlow]:
        """Extract a single business flow via BFS from an entry point."""
        entry_node = self.graph.get_node(entry_node_id)
        if not entry_node:
            return None

        steps: List[FlowStep] = []
        visited: Set[str] = set()
        modules_set: Set[str] = set()
        cross_module_count = 0

        queue = deque()
        step_counter = 0

        # Entry step
        step_counter += 1
        entry_step = FlowStep(
            step_id=f"s{step_counter}",
            node_id=entry_node_id,
            module_name=entry_node.module_name,
            class_name=entry_node.class_name,
            method_name=entry_node.name,
            step_order=step_counter,
            depth=0,
            call_type="entry",
            line_number=entry_node.start_line,
            tags=list(entry_node.tags),
            is_module_boundary=False,
            is_state_change=self._is_state_change(entry_node),
            is_validation=self._is_validation(entry_node),
            description=self._generate_step_description(entry_node),
        )
        steps.append(entry_step)
        visited.add(entry_node_id)
        modules_set.add(entry_node.module_name)

        for edge in entry_node.calls:
            queue.append((
                edge.to_node, 1, entry_node.module_name,
                edge.call_type, edge.line_number, step_counter,
            ))

        # BFS
        while queue:
            node_id, depth, parent_mod, call_type, line_no, parent_order = queue.popleft()

            if depth > max_depth:
                continue
            if node_id in visited:
                continue

            node = self.graph.get_node(node_id)
            if not node:
                continue

            if depth > 3 and node.name.startswith("_") and len(node.calls) == 0:
                continue

            visited.add(node_id)
            step_counter += 1

            is_boundary = node.module_name != parent_mod
            if is_boundary:
                cross_module_count += 1

            modules_set.add(node.module_name)

            step = FlowStep(
                step_id=f"s{step_counter}",
                node_id=node_id,
                module_name=node.module_name,
                class_name=node.class_name,
                method_name=node.name,
                step_order=step_counter,
                depth=depth,
                call_type=call_type,
                line_number=line_no,
                tags=list(node.tags),
                is_module_boundary=is_boundary,
                is_state_change=self._is_state_change(node),
                is_validation=self._is_validation(node),
                description=self._generate_step_description(node),
            )
            steps.append(step)

            for edge in node.calls:
                if edge.to_node not in visited:
                    queue.append((
                        edge.to_node, depth + 1, node.module_name,
                        edge.call_type, edge.line_number, step_counter,
                    ))

        flow = BusinessFlow(
            flow_id=flow_id,
            name=self._generate_flow_name(entry_node, steps),
            description=self._generate_flow_description(entry_node, steps),
            entry_node=entry_node_id,
            steps=steps,
            modules_involved=sorted(modules_set),
            cross_module_count=cross_module_count,
            has_validation=any(s.is_validation for s in steps),
            has_state_change=any(s.is_state_change for s in steps),
        )

        return flow

    def _generate_step_description(self, node: CallNode) -> str:
        if node.docstring:
            first_line = node.docstring.strip().split("\n")[0].strip()
            if len(first_line) > 80:
                first_line = first_line[:77] + "..."
            return first_line
        return node.name

    def _generate_flow_name(self, entry_node: CallNode, steps: List[FlowStep]) -> str:
        name_patterns = {
            "create": "Create / Submit",
            "register": "Registration",
            "approve": "Approval",
            "reject": "Rejection",
            "cancel": "Cancellation",
            "perform": "Execution",
            "add": "Addition",
            "borrow": "Borrow",
            "return": "Return",
            "close": "Completion / Close",
            "assign": "Assignment",
            "login": "Login / Authentication",
            "initialize": "Initialization",
            "deactivate": "Deactivation",
        }

        name_lower = entry_node.name.lower()
        prefix = entry_node.class_name + " " if entry_node.class_name else ""

        for keyword, label in name_patterns.items():
            if keyword in name_lower:
                return f"{prefix}{label} Flow"

        return f"{prefix}{entry_node.name} Flow"

    def _generate_flow_description(self, entry_node: CallNode, steps: List[FlowStep]) -> str:
        mod_count = len(set(s.module_name for s in steps))
        step_count = len(steps)
        state_steps = [s for s in steps if s.is_state_change]
        val_steps = [s for s in steps if s.is_validation]

        parts = []
        if entry_node.docstring:
            first_line = entry_node.docstring.strip().split("\n")[0].strip()
            parts.append(first_line)

        parts.append(
            f"Crosses {mod_count} module(s) with {step_count} steps, "
            f"{len(state_steps)} state change(s), {len(val_steps)} validation(s)."
        )

        return " ".join(parts)

    def _score_flows(self, flows: List[BusinessFlow]):
        """Score each flow by business importance."""
        for flow in flows:
            score = 0.0
            score += min(len(flow.steps) * 0.5, 5.0)
            score += flow.cross_module_count * 2.0

            state_count = sum(1 for s in flow.steps if s.is_state_change)
            score += state_count * 1.5

            val_count = sum(1 for s in flow.steps if s.is_validation)
            score += val_count * 1.0

            entry = self.graph.get_node(flow.entry_node)
            if entry and entry.docstring:
                score += 1.0

            flow.complexity_score = min(len(flow.steps) * 0.5, 10.0)
            flow.business_importance = score
