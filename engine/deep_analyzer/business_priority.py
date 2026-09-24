"""
Evidence-aware business logic priority scoring.

This module answers a practical product question:
"Which parts of a project should a teacher explain first, and which flows
deserve a review before they become teaching material?"

The score is deliberately a ranking signal, not a truth oracle.  Structural
facts still come from the AST-based call graph and state tracker.  The
algorithm combines those facts into a reproducible priority score that can be
shown in the product and exported with the evidence references.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass
class NodePriority:
    """Priority and supporting metrics for one callable node."""

    node_id: str
    module: str
    method: str
    location: str
    score: float
    metrics: Dict[str, float]
    reasons: List[str] = field(default_factory=list)
    flow_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "module": self.module,
            "method": self.method,
            "location": self.location,
            "score": round(self.score, 2),
            "metrics": {key: round(value, 4) for key, value in self.metrics.items()},
            "reasons": self.reasons,
            "flow_ids": self.flow_ids,
            # The score is inferred from verified structural signals.
            "confidence": "inferred",
        }


@dataclass
class FlowPriority:
    """Priority and review risk for one extracted business flow."""

    flow_id: str
    name: str
    priority_score: float
    review_risk: float
    metrics: Dict[str, float]
    top_nodes: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "flow_id": self.flow_id,
            "name": self.name,
            "priority_score": round(self.priority_score, 2),
            "review_risk": round(self.review_risk, 2),
            "metrics": {key: round(value, 4) for key, value in self.metrics.items()},
            "top_nodes": self.top_nodes,
            "reasons": self.reasons,
            "confidence": "inferred",
        }


@dataclass
class BusinessPriorityResult:
    """Serializable output of :class:`BusinessPriorityAnalyzer`."""

    algorithm: Dict[str, object] = field(default_factory=dict)
    node_scores: List[NodePriority] = field(default_factory=list)
    flow_scores: List[FlowPriority] = field(default_factory=list)
    evidence_gaps: List[dict] = field(default_factory=list)
    summary: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "algorithm": self.algorithm,
            "node_scores": [item.to_dict() for item in self.node_scores],
            "flow_scores": [item.to_dict() for item in self.flow_scores],
            "evidence_gaps": self.evidence_gaps,
            "summary": self.summary,
        }


class BusinessPriorityAnalyzer:
    """Rank business logic by combining several observable graph signals.

    The default weights are intentionally explicit and versioned.  They are
    not trained model parameters; changing them changes the ranking, so the
    weights are included in every serialized result for reproducibility.
    """

    VERSION = "BLPS-1.0"
    NODE_WEIGHTS = {
        "centrality": 0.35,
        "flow_reachability": 0.25,
        "state_mutation": 0.20,
        "boundary_role": 0.10,
        "evidence_completeness": 0.10,
    }
    FLOW_WEIGHTS = {
        "business_importance": 0.45,
        "state_ratio": 0.20,
        "validation_ratio": 0.15,
        "boundary_ratio": 0.10,
        "evidence_completeness": 0.10,
    }

    def __init__(self, max_nodes: int = 20, max_flows: int = 10, max_gaps: int = 20):
        self.max_nodes = max_nodes
        self.max_flows = max_flows
        self.max_gaps = max_gaps

    def analyze(self, call_graph, state_analysis=None, business_flows=None) -> BusinessPriorityResult:
        """Analyze a graph and its extracted flows.

        Args:
            call_graph: ``ProjectCallGraph`` instance.
            state_analysis: optional ``StateAnalysis`` instance.
            business_flows: iterable of ``BusinessFlow`` instances.
        """
        flows = list(business_flows or [])
        node_ids = list(call_graph.nodes.keys())
        if not node_ids:
            return BusinessPriorityResult(
                algorithm=self._algorithm_metadata(),
                summary={"total_nodes": 0, "total_flows": len(flows)},
            )

        pagerank = self._weighted_pagerank(call_graph)
        flow_stats = self._collect_flow_stats(flows)
        max_flow_weight = max(flow_stats["total_importance"], 1.0)

        node_items: List[NodePriority] = []
        node_lookup: Dict[str, NodePriority] = {}
        for node_id in node_ids:
            node = call_graph.nodes[node_id]
            out_edges = [edge for edge in node.calls if edge.to_node in call_graph.nodes]
            in_edges = [edge for edge in node.called_by if edge.from_node in call_graph.nodes]
            cross_edges = [
                edge
                for edge in out_edges + in_edges
                if self._module_of(edge.from_node) != self._module_of(edge.to_node)
            ]

            flow_weight = flow_stats["node_importance"].get(node_id, 0.0)
            flow_reachability = min(1.0, flow_weight / max_flow_weight)
            state_mutation = 1.0 if self._is_state_writer(node, state_analysis) else 0.0
            total_degree = len(out_edges) + len(in_edges)
            boundary_role = min(1.0, len(cross_edges) / max(1, total_degree))
            evidence_completeness = self._node_evidence_completeness(node, out_edges)
            centrality = self._normalize_pagerank(pagerank.get(node_id, 0.0), pagerank.values())

            metrics = {
                "centrality": centrality,
                "flow_reachability": flow_reachability,
                "state_mutation": state_mutation,
                "boundary_role": boundary_role,
                "evidence_completeness": evidence_completeness,
            }
            score = 100.0 * sum(self.NODE_WEIGHTS[key] * metrics[key] for key in self.NODE_WEIGHTS)
            reasons = self._node_reasons(metrics)
            item = NodePriority(
                node_id=node_id,
                module=node.module_name,
                method=node.name,
                location=self._location(node.filepath, node.start_line),
                score=score,
                metrics=metrics,
                reasons=reasons,
                flow_ids=sorted(flow_stats["node_flows"].get(node_id, set())),
            )
            node_items.append(item)
            node_lookup[node_id] = item

        node_items.sort(key=lambda item: (-item.score, item.node_id))

        flow_items: List[FlowPriority] = []
        gaps: List[dict] = []
        max_importance = max(flow_stats["flow_weights"].values(), default=1.0)
        for flow in flows:
            steps = list(getattr(flow, "steps", []) or [])
            step_count = len(steps)
            state_ratio = sum(bool(getattr(step, "is_state_change", False)) for step in steps) / max(1, step_count)
            validation_ratio = sum(bool(getattr(step, "is_validation", False)) for step in steps) / max(1, step_count)
            boundary_ratio = min(
                1.0,
                float(getattr(flow, "cross_module_count", 0)) / max(1, step_count - 1),
            )
            evidence_ratio = sum(self._step_has_location(step) for step in steps) / max(1, step_count)
            raw_importance = max(0.0, float(getattr(flow, "business_importance", 0.0)))
            operational_factor = flow_stats["operational_factors"].get(
                getattr(flow, "flow_id", ""), 1.0
            )
            adjusted_importance = flow_stats["flow_weights"].get(
                getattr(flow, "flow_id", ""), raw_importance * operational_factor
            )
            importance = min(1.0, adjusted_importance / max(1.0, max_importance))
            metrics = {
                "business_importance": importance,
                "raw_business_importance": raw_importance,
                "operational_factor": operational_factor,
                "state_ratio": state_ratio,
                "validation_ratio": validation_ratio,
                "boundary_ratio": boundary_ratio,
                "evidence_completeness": evidence_ratio,
            }
            priority_score = 100.0 * sum(self.FLOW_WEIGHTS[key] * metrics[key] for key in self.FLOW_WEIGHTS)
            state_without_validation = 1.0 if state_ratio > 0 and validation_ratio == 0 else 0.0
            review_risk = 100.0 * (0.65 * state_without_validation + 0.35 * (1.0 - evidence_ratio))
            flow_node_ids = [getattr(step, "node_id", "") for step in steps if getattr(step, "node_id", "")]
            ranked_nodes = sorted(
                flow_node_ids,
                key=lambda node_id: node_lookup.get(node_id, NodePriority("", "", "", "", 0, {})).score,
                reverse=True,
            )
            reasons = self._flow_reasons(metrics, state_without_validation)
            flow_item = FlowPriority(
                flow_id=getattr(flow, "flow_id", ""),
                name=getattr(flow, "name", ""),
                priority_score=priority_score,
                review_risk=review_risk,
                metrics=metrics,
                top_nodes=ranked_nodes[:5],
                reasons=reasons,
            )
            flow_items.append(flow_item)

            flow_location = self._flow_location(flow, call_graph)
            if state_without_validation:
                gaps.append({
                    "type": "state_change_without_validation",
                    "severity": "high",
                    "flow_id": flow_item.flow_id,
                    "title": "状态变更流程缺少显式校验步骤",
                    "description": "该流程包含状态写入，但当前提取结果没有发现校验步骤，建议教师先审核边界条件。",
                    "location": flow_location,
                })
            if evidence_ratio < 1.0:
                gaps.append({
                    "type": "incomplete_location_evidence",
                    "severity": "medium",
                    "flow_id": flow_item.flow_id,
                    "title": "流程中存在缺少行号的步骤",
                    "description": "该流程可以排序展示，但缺失位置证据的步骤不应直接进入教师答案库。",
                    "location": flow_location,
                })

        flow_items.sort(key=lambda item: (-item.priority_score, item.flow_id))
        gaps = self._deduplicate_gaps(gaps)[: self.max_gaps]

        evidence_values = [item.metrics["evidence_completeness"] for item in node_items]
        summary = {
            "total_nodes": len(node_items),
            "total_flows": len(flow_items),
            "top_node": node_items[0].node_id if node_items else None,
            "top_flow": flow_items[0].flow_id if flow_items else None,
            "high_priority_flow_count": sum(item.priority_score >= 60 for item in flow_items),
            "review_gap_count": len(gaps),
            "evidence_completeness": round(sum(evidence_values) / max(1, len(evidence_values)), 4),
        }

        return BusinessPriorityResult(
            algorithm=self._algorithm_metadata(),
            node_scores=node_items[: self.max_nodes],
            flow_scores=flow_items[: self.max_flows],
            evidence_gaps=gaps,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Graph metrics
    # ------------------------------------------------------------------

    def _weighted_pagerank(self, graph, damping: float = 0.85, max_iter: int = 100, tolerance: float = 1e-9) -> Dict[str, float]:
        """Compute deterministic weighted PageRank without third-party deps."""
        node_ids = list(graph.nodes.keys())
        n = len(node_ids)
        if n == 0:
            return {}

        outgoing: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
        incoming: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
        out_totals: Dict[str, float] = defaultdict(float)
        for edge in graph.edges:
            if edge.from_node not in graph.nodes or edge.to_node not in graph.nodes:
                continue
            cross = self._module_of(edge.from_node) != self._module_of(edge.to_node)
            weight = max(1.0, float(getattr(edge, "call_count", 1))) * (1.2 if cross else 1.0)
            outgoing[edge.from_node].append((edge.to_node, weight))
            incoming[edge.to_node].append((edge.from_node, weight))
            out_totals[edge.from_node] += weight

        score = {node_id: 1.0 / n for node_id in node_ids}
        for _ in range(max_iter):
            dangling_mass = sum(score[node_id] for node_id in node_ids if not outgoing[node_id])
            next_score = {}
            for node_id in node_ids:
                value = (1.0 - damping) / n + damping * dangling_mass / n
                for source, weight in incoming[node_id]:
                    value += damping * score[source] * weight / max(out_totals[source], 1e-12)
                next_score[node_id] = value
            delta = sum(abs(next_score[node_id] - score[node_id]) for node_id in node_ids)
            score = next_score
            if delta < tolerance:
                break
        return score

    @staticmethod
    def _normalize_pagerank(value: float, values: Iterable[float]) -> float:
        maximum = max(values, default=0.0)
        return value / maximum if maximum > 0 else 0.0

    # ------------------------------------------------------------------
    # Feature extraction
    # ------------------------------------------------------------------

    def _collect_flow_stats(self, flows) -> dict:
        node_importance: Dict[str, float] = defaultdict(float)
        node_flows: Dict[str, set] = defaultdict(set)
        flow_weights: Dict[str, float] = {}
        operational_factors: Dict[str, float] = {}
        total_importance = 0.0
        for flow in flows:
            raw_importance = max(0.0, float(getattr(flow, "business_importance", 0.0)))
            flow_id = getattr(flow, "flow_id", "")
            operational_factor = self._operational_factor(flow)
            importance = raw_importance * operational_factor
            flow_weights[flow_id] = importance
            operational_factors[flow_id] = operational_factor
            total_importance += importance
            for step in getattr(flow, "steps", []) or []:
                node_id = getattr(step, "node_id", "")
                if not node_id:
                    continue
                node_importance[node_id] += importance
                node_flows[node_id].add(getattr(flow, "flow_id", ""))
        return {
            "node_importance": node_importance,
            "node_flows": node_flows,
            "flow_weights": flow_weights,
            "operational_factors": operational_factors,
            "total_importance": total_importance,
        }

    @staticmethod
    def _operational_factor(flow) -> float:
        """Downweight setup/sample-data flows in the teaching priority.

        Initialization is still retained in the result and can be reviewed;
        it simply should not outrank a user-facing business operation only
        because it calls many managers while seeding demo data.

        P0-06：判定逻辑已抽到 ``engine/flow_filter.py``，与
        ``ProjectAnalyzer.core_flows`` 和 ``TrainingGenerator`` 第 3 关共用同一实现，
        避免三处对"哪条流程最重要"给出互相矛盾的结论。
        """
        from ..flow_filter import is_lifecycle_flow, LIFECYCLE_FACTOR

        return LIFECYCLE_FACTOR if is_lifecycle_flow(flow) else 1.0

    @staticmethod
    def _is_state_writer(node, state_analysis) -> bool:
        if state_analysis is not None and getattr(node, "class_name", None):
            checker = getattr(state_analysis, "is_state_writer", None)
            if checker and checker(node.module_name, node.class_name, node.name):
                return True
        return any(tag in (getattr(node, "tags", []) or []) for tag in ("update", "creation", "state_change", "deletion"))

    @staticmethod
    def _node_evidence_completeness(node, out_edges) -> float:
        node_evidence = 1.0 if getattr(node, "filepath", "") and getattr(node, "start_line", 0) > 0 else 0.0
        if not out_edges:
            return node_evidence
        edge_evidence = sum(getattr(edge, "line_number", 0) > 0 for edge in out_edges) / len(out_edges)
        return 0.7 * node_evidence + 0.3 * edge_evidence

    @staticmethod
    def _step_has_location(step) -> float:
        return 1.0 if getattr(step, "line_number", 0) > 0 else 0.0

    @staticmethod
    def _node_reasons(metrics: Dict[str, float]) -> List[str]:
        reasons = []
        if metrics["centrality"] >= 0.6:
            reasons.append("调用图结构中心")
        if metrics["flow_reachability"] >= 0.35:
            reasons.append("参与高重要度业务流程")
        if metrics["state_mutation"]:
            reasons.append("会改变业务状态")
        if metrics["boundary_role"] >= 0.4:
            reasons.append("位于跨模块边界")
        if metrics["evidence_completeness"] < 1.0:
            reasons.append("部分位置证据待补")
        return reasons or ["结构信号较弱，作为辅助节点"]

    @staticmethod
    def _flow_reasons(metrics: Dict[str, float], state_without_validation: float) -> List[str]:
        reasons = []
        if metrics.get("operational_factor", 1.0) < 1.0:
            reasons.append("生命周期/样例数据流程已降权")
        if metrics["business_importance"] >= 0.6:
            reasons.append("业务重要度高")
        if metrics["boundary_ratio"] >= 0.4:
            reasons.append("跨模块协作明显")
        if metrics["state_ratio"] > 0:
            reasons.append("包含状态变更")
        if metrics["validation_ratio"] > 0:
            reasons.append("存在校验步骤")
        if state_without_validation:
            reasons.append("状态变更但未发现显式校验")
        if metrics["evidence_completeness"] < 1.0:
            reasons.append("存在缺少行号的步骤")
        return reasons or ["可作为一般流程讲解"]

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _module_of(node_id: str) -> str:
        return node_id.split(":", 1)[0]

    @staticmethod
    def _location(filepath: str, line: int) -> str:
        if not filepath:
            return ""
        return f"{filepath}:{line}" if line else filepath

    @classmethod
    def _flow_location(cls, flow, call_graph=None) -> str:
        entry_node = None
        if call_graph is not None:
            entry_node = call_graph.nodes.get(getattr(flow, "entry_node", ""))
        if entry_node is not None:
            return cls._location(entry_node.filepath, entry_node.start_line)
        for step in getattr(flow, "steps", []) or []:
            line = getattr(step, "line_number", 0)
            if line:
                return f"{getattr(step, 'module_name', '')}:{line}"
        return ""

    @staticmethod
    def _deduplicate_gaps(gaps: Sequence[dict]) -> List[dict]:
        seen = set()
        result = []
        for gap in gaps:
            key = (gap.get("type"), gap.get("flow_id"))
            if key in seen:
                continue
            seen.add(key)
            result.append(gap)
        return result

    @classmethod
    def _algorithm_metadata(cls) -> dict:
        return {
            "name": "Evidence-aware Business Logic Priority Score",
            "version": cls.VERSION,
            "purpose": "为教师确定核心讲解路径和审核顺序，不替代事实判定",
            "node_weights": cls.NODE_WEIGHTS,
            "flow_weights": cls.FLOW_WEIGHTS,
            "setup_flow_factor": 0.2,
            "setup_detection": "entry_node/name contains initialize, bootstrap, seed, sample_data or setup",
            "formula": "S_node=100*(0.35*C+0.25*R+0.20*M+0.10*B+0.10*E)",
            "pagerank": "PR(v)=(1-d)/N+d*sum(PR(u)*w_uv/sum(w_ux)); cross-module edge weight=1.2",
            "caveat": "score 是可复现的排序信号；verified 事实仍以 AST、状态追踪和行号证据为准",
        }


__all__ = ["BusinessPriorityAnalyzer", "BusinessPriorityResult", "NodePriority", "FlowPriority"]
