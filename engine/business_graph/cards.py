"""
第 5 步：模块卡片 · 边界（"不负责什么"）· 模块间关系
（README5 §3.1 第 5 步）

三件事
------
1. **模块卡片**：把前面几步的产物组装成 README4 §3.2 要求的卡片字段，
   每个字段都带自己的置信度（``business_rules`` 等是 verified，``objective`` 是 unconfirmed）。
2. **"不负责什么"**：README4 称之为"最重要的字段"，也是最有记忆点的教学点。
   用三条规则生成（全部可解释）：
   - **同级承担**：同域内其他功能点承担的能力 → 本模块"不负责"；
   - **上游前置**：在本模块入口**之前**发生的校验/判断 → 归上游，本模块不负责；
   - **越界耦合**：本功能点也写了别的域的状态 → 标"边界待教师确认"。
3. **模块间关系**：从调用图聚合到功能点粒度，分 ``calls`` / ``reads`` / ``writes`` / ``uses``，
   每条关系带调用次数与行号证据。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .. import lexicon
from .capabilities import Capability
from .domains import Domain
from .facts import Fact, KIND_GUARD, KIND_RAISE, KIND_RULE, KIND_STATE
from .units import Unit, edge_target, edge_line, edge_type


# ------------------------------------------------------------
# 卡片
# ------------------------------------------------------------

@dataclass
class ModuleCard:
    """业务模块卡片（README4 §3.2 / README5 §4.2）。"""
    module_id: str
    name_cn: str
    level: int
    parent_id: Optional[str]
    entity: str = ""
    entity_cn: str = ""
    verb_class: str = ""
    verb_cn: str = ""
    objective: str = ""
    objective_confidence: str = "unconfirmed"
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    business_rules: List[Fact] = field(default_factory=list)
    state_changes: List[Fact] = field(default_factory=list)
    exceptions: List[Fact] = field(default_factory=list)
    preconditions: List[Fact] = field(default_factory=list)
    upstream_modules: List[str] = field(default_factory=list)
    downstream_modules: List[str] = field(default_factory=list)
    does_not: List[str] = field(default_factory=list)
    does_not_confidence: str = "inferred"
    members: List[dict] = field(default_factory=list)
    evidence: List[dict] = field(default_factory=list)
    confidence: str = "inferred"
    review_status: str = "needs_review"
    source: str = "auto"

    def to_dict(self) -> dict:
        return {
            "module_id": self.module_id,
            "name_cn": self.name_cn,
            "level": self.level,
            "parent_id": self.parent_id,
            "entity": self.entity,
            "entity_cn": self.entity_cn,
            "verb_class": self.verb_class,
            "verb_cn": self.verb_cn,
            "objective": self.objective,
            "objective_confidence": self.objective_confidence,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "business_rules": [f.to_dict() for f in self.business_rules],
            "state_changes": [f.to_dict() for f in self.state_changes],
            "exceptions": [f.to_dict() for f in self.exceptions],
            "preconditions": [f.to_dict() for f in self.preconditions],
            "upstream_modules": self.upstream_modules,
            "downstream_modules": self.downstream_modules,
            "does_not": self.does_not,
            "does_not_confidence": self.does_not_confidence,
            "members": self.members,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "review_status": self.review_status,
            "source": self.source,
        }


# ------------------------------------------------------------
# 关系
# ------------------------------------------------------------

@dataclass
class ModuleRelation:
    """模块间关系（verified，来自调用图）。"""
    from_module: str
    to_module: str
    type: str            # calls | reads | writes | uses
    count: int = 1
    evidence: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "from": self.from_module,
            "to": self.to_module,
            "type": self.type,
            "count": self.count,
            "evidence": self.evidence,
            "confidence": "verified",
        }


def _capability_of_symbol(capabilities: Sequence[Capability]) -> Dict[str, str]:
    """``函数名 -> capability_id``（同名冲突时取第一个，保持稳定）。"""
    index: Dict[str, str] = {}
    for cap in sorted(capabilities, key=lambda c: c.capability_id):
        for member in cap.members:
            index.setdefault(member.symbol, cap.capability_id)
    return index


def build_relations(
    capabilities: Sequence[Capability],
    call_graph=None,
    state_analysis=None,
) -> Tuple[List[ModuleRelation], Dict[str, List[str]], Dict[str, List[str]]]:
    """第 5 步（关系）：把调用图聚合到功能点粒度。

    Returns:
        ``(relations, downstream_by_cap, upstream_by_cap)``
    """
    symbol_to_cap = _capability_of_symbol(capabilities)
    member_by_symbol: Dict[str, object] = {}
    for cap in capabilities:
        for member in cap.members:
            member_by_symbol.setdefault(member.symbol, member)

    downstream: Dict[str, Set[str]] = {}
    upstream: Dict[str, Set[str]] = {}
    edge_counts: Dict[Tuple[str, str], int] = {}
    edge_evidence: Dict[Tuple[str, str], List[dict]] = {}

    def _add(src_cap: str, dst_cap: str, line: int, file: str, kind: str = "calls") -> None:
        if not src_cap or not dst_cap or src_cap == dst_cap:
            return
        key = (src_cap, dst_cap)
        edge_counts[key] = edge_counts.get(key, 0) + 1
        bucket = edge_evidence.setdefault(key, [])
        if len(bucket) < 3:
            bucket.append({"file": file, "start_line": line, "end_line": line, "type": kind})
        downstream.setdefault(src_cap, set()).add(dst_cap)
        upstream.setdefault(dst_cap, set()).add(src_cap)

    if call_graph is not None:
        for node_id in sorted(getattr(call_graph, "nodes", {}) or {}):
            node = call_graph.nodes[node_id]
            src_symbol = getattr(node, "name", "")
            src_cap = symbol_to_cap.get(src_symbol, "")
            if not src_cap:
                continue
            file_rel = getattr(node, "filepath", "") or ""
            for call in sorted((getattr(node, "calls", []) or []), key=edge_target):
                target = edge_target(call)
                if not target:
                    continue
                dst_symbol = target.split(".")[-1]
                dst_cap = symbol_to_cap.get(dst_symbol, "")
                line = edge_line(call)
                _add(src_cap, dst_cap, line, file_rel, edge_type(call))

    # 兜底：没有调用图时，用方法的 calls_out（同一文件内的调用）
    if not call_graph:
        for cap in sorted(capabilities, key=lambda c: c.capability_id):
            for member in cap.members:
                dst_cap = None
                for symbol, cid in sorted(symbol_to_cap.items()):
                    if symbol in (member.calls_out if hasattr(member, "calls_out") else []):
                        dst_cap = cid
                        break
                if dst_cap:
                    _add(cap.capability_id, dst_cap, member.start_line, member.file)

    relations: List[ModuleRelation] = []
    for (src, dst), count in sorted(edge_counts.items()):
        relations.append(ModuleRelation(
            from_module=src,
            to_module=dst,
            type="calls",
            count=count,
            evidence=edge_evidence.get((src, dst), []),
        ))

    downstream_list = {k: sorted(v) for k, v in sorted(downstream.items())}
    upstream_list = {k: sorted(v) for k, v in sorted(upstream.items())}
    return relations, downstream_list, upstream_list


def _inputs_of(cap: Capability) -> List[str]:
    """启发式输入清单：状态读取 + 成员函数里出现的参数名（来自 docstring/签名不可得，故只给状态）。"""
    reads: List[str] = []
    for member in cap.members:
        for attr in member.state_reads:
            if attr not in reads:
                reads.append(attr)
    return reads[:6]


def _outputs_of(cap: Capability) -> List[str]:
    """启发式输出清单：状态写入目标。"""
    writes: List[str] = []
    for member in cap.members:
        for attr in member.state_writes:
            if attr not in writes:
                writes.append(attr)
    return writes[:6]


def _generate_does_not(
    cap: Capability,
    sibling_names: Sequence[str],
    preconditions: Sequence[Fact],
    cross_domain_writes: Sequence[str],
) -> List[str]:
    """生成"不负责什么"（README5 §3.1 的三条规则）。"""
    items: List[str] = []

    # 规则 1：同级承担 —— 同域的其他功能点做的事，不是我的职责
    for name in list(sibling_names)[:2]:
        items.append(f"不负责「{name}」所承担的能力")

    # 规则 2：上游前置 —— 在本模块入口之前发生的校验归上游
    for fact in list(preconditions)[:2]:
        code = fact.code if len(fact.code) <= 48 else fact.code[:47] + "…"
        items.append(f"不负责前置判断 `{code}`（在进入本功能前已完成）")

    # 规则 3：越界耦合 —— 写了别的域的状态，说明边界可能模糊，交教师确认
    for attr in list(cross_domain_writes)[:2]:
        items.append(f"当前实现会写入其它业务域的「{attr}」，边界待教师确认")

    # 去重保序
    seen: Set[str] = set()
    result: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result[:4]


def build_cards(
    domains: Sequence[Domain],
    capabilities: Sequence[Capability],
    facts: Sequence[Fact],
    units: Sequence[Unit],
    relations: Sequence[ModuleRelation],
    downstream_by_cap: Dict[str, List[str]],
    upstream_by_cap: Dict[str, List[str]],
    hierarchy_by_domain: Dict[str, str],
) -> Tuple[Dict[str, ModuleCard], Dict[str, ModuleCard]]:
    """第 5 步（卡片）：生成一级域卡片与二级功能点卡片。

    Returns:
        ``(domain_cards, capability_cards)``，两个 dict 的键分别是
        ``domain_id`` / ``capability_id``。
    """
    facts_by_cap: Dict[str, List[Fact]] = {}
    for fact in facts:
        facts_by_cap.setdefault(fact.capability_id, []).append(fact)

    caps_by_domain: Dict[str, List[Capability]] = {}
    for cap in capabilities:
        caps_by_domain.setdefault(cap.parent_id, []).append(cap)

    # 状态属性 -> 拥有它的域（用于越界耦合判定）
    state_owner: Dict[str, str] = {}
    for domain in domains:
        for cap in caps_by_domain.get(domain.domain_id, []):
            for member in cap.members:
                for attr in member.state_writes:
                    state_owner.setdefault(attr, domain.domain_id)

    capability_cards: Dict[str, ModuleCard] = {}
    for cap in sorted(capabilities, key=lambda c: c.capability_id):
        domain_id = cap.parent_id
        cap_facts = facts_by_cap.get(cap.capability_id, [])
        rules = [f for f in cap_facts if f.kind == KIND_RULE]
        guards = [f for f in cap_facts if f.kind == KIND_GUARD]
        raises = [f for f in cap_facts if f.kind == KIND_RAISE]
        states = [f for f in cap_facts if f.kind == KIND_STATE]

        # 规则 2：上游前置 = 本功能点的成员函数里、位于入口方法之前的守卫条件
        domain_caps = sorted(caps_by_domain.get(domain_id, []), key=lambda c: c.capability_id)
        sibling_names = [c.name_cn for c in domain_caps if c.capability_id != cap.capability_id]

        cross_writes = sorted({
            attr for member in cap.members for attr in member.state_writes
            if state_owner.get(attr, domain_id) != domain_id
        })

        does_not = _generate_does_not(cap, sibling_names, guards, cross_writes)

        # objective：有 docstring 就用，没有就留空（**不编**）
        objective = ""
        objective_conf = "unconfirmed"
        for member in cap.members:
            if member.role == "entry":
                doc = ""
                for unit in units:
                    for method in unit.methods:
                        if method.symbol == member.symbol and method.file == member.file:
                            doc = method.docstring
                            break
                if doc:
                    objective = doc[:60]
                    objective_conf = "from_docstring"
                    break

        evidence = [
            {"file": m.file, "start_line": m.start_line, "end_line": m.end_line,
             "signal": f"member:{m.role}"}
            for m in sorted(cap.members, key=lambda m: (m.file, m.start_line))[:4]
        ]

        capability_cards[cap.capability_id] = ModuleCard(
            module_id=cap.capability_id,
            name_cn=cap.name_cn,
            level=2,
            parent_id=domain_id,
            entity=cap.entity,
            entity_cn=cap.entity_cn,
            verb_class=cap.verb_class,
            verb_cn=cap.verb_cn,
            objective=objective,
            objective_confidence=objective_conf,
            inputs=_inputs_of(cap),
            outputs=_outputs_of(cap),
            business_rules=rules,
            state_changes=states,
            exceptions=raises,
            preconditions=guards,
            upstream_modules=upstream_by_cap.get(cap.capability_id, []),
            downstream_modules=downstream_by_cap.get(cap.capability_id, []),
            does_not=does_not,
            members=[m.to_dict() for m in sorted(cap.members, key=lambda m: (m.file, m.start_line))],
            evidence=evidence,
            confidence=cap.confidence,
        )

    domain_cards: Dict[str, ModuleCard] = {}
    for domain in sorted(domains, key=lambda d: d.domain_id):
        domain_caps = sorted(caps_by_domain.get(domain.domain_id, []), key=lambda c: c.capability_id)
        # 一级卡片的规则/状态/异常取本域所有功能点的并集（去重按 fact_id）
        cap_facts = [f for cap in domain_caps for f in facts_by_cap.get(cap.capability_id, [])]
        uniq: Dict[str, Fact] = {}
        for fact in cap_facts:
            uniq.setdefault(fact.fact_id, fact)

        all_in = []
        all_out = []
        for cap in domain_caps:
            for attr in _inputs_of(cap):
                if attr not in all_in:
                    all_in.append(attr)
            for attr in _outputs_of(cap):
                if attr not in all_out:
                    all_out.append(attr)

        domain_cards[domain.domain_id] = ModuleCard(
            module_id=domain.domain_id,
            name_cn=domain.name_cn,
            level=1,
            parent_id=None,
            objective="",
            objective_confidence="unconfirmed",
            inputs=all_in[:8],
            outputs=all_out[:8],
            business_rules=[f for f in sorted(uniq.values(), key=lambda f: f.fact_id) if f.kind == KIND_RULE][:8],
            state_changes=[f for f in sorted(uniq.values(), key=lambda f: f.fact_id) if f.kind == KIND_STATE][:8],
            exceptions=[f for f in sorted(uniq.values(), key=lambda f: f.fact_id) if f.kind == KIND_RAISE][:8],
            preconditions=[f for f in sorted(uniq.values(), key=lambda f: f.fact_id) if f.kind == KIND_GUARD][:8],
            does_not=[],
            does_not_confidence="unconfirmed",
            members=[{"symbol": c.capability_id, "role": "capability", "name_cn": c.name_cn} for c in domain_caps],
            evidence=[e.to_dict() for e in domain.evidence],
            confidence=domain.confidence,
            review_status="needs_review",
        )

    return domain_cards, capability_cards
