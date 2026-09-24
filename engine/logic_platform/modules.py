"""业务板块提取（业务逻辑分析平台的第 2 步）

「业务板块」= 项目的一级业务域（``domains``），板块下面是二级功能点
（``capabilities``），功能点下面是真实函数（``members``，带 ``file`` + 行号）。

**无论项目大小，这一步都会产出板块** —— 这是需求里的硬要求：
大小只决定「展开多少」，不决定「有没有」。

三条纪律
--------
1. **核心度排序复用既有实现，不另写一套。**
   ``engine/design/task_builder.py`` 的 ``_capability_entries`` / ``_importance``
   已经在做「哪些能力最重要」这件事（给设计题挑必备能力用）。
   本模块**直接复用**它们，而不是再写一个排序 ——
   「同一个不变量只允许有一个实现」（README §2.2 铁律 4）。
   代价是引用了两个下划线私有函数；这是刻意的取舍：与其复制逻辑，
   不如让两处共用同一份排序，将来调权重只需改一个地方。

2. **不许隐藏板块。** orchestrator / support 域也照样展示，
   只是打上 ``is_core=False`` 标签。README §3.1 的诚实降级精神是一样的：
   少给内容可以，假装没有不行。

3. **截断必须显式。** 超出本级预算、没有沉浸式课程的能力点，
   会带 ``walkthrough_state="beyond_budget"`` 与中文 ``reason``，
   前端必须原样显示。

成员行号从哪来
--------------
``task_builder._capability_entries`` 里的 ``members`` 是**计数**（int），
不是列表 —— 它只服务排序。所以成员明细（``symbol`` / ``file`` /
``start_line`` / ``end_line`` / ``role``）从 **图谱原始数据**
``capabilities[].members`` 取，那份才是 ``Capability.to_dict()`` 的完整序列化。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..design import task_builder as _task_builder
from . import tiering

ALGORITHM_VERSION = "sections-1.0"

#: 板块级别：一级业务域
LEVEL_SECTION = 1
#: 能力级别：二级功能点
LEVEL_CAPABILITY = 2


def _as_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _member_dicts(capability: Dict[str, Any]) -> List[Dict[str, Any]]:
    """取能力点的成员函数（带 file + 行号），按 ``(file, start_line, symbol)`` 稳定排序。

    排序是硬要求：确定性测试逐字节比对输出，任何 ``set`` 遍历顺序都会让它变。
    """
    members = capability.get("members")
    if not isinstance(members, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in members:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "symbol": str(item.get("symbol") or ""),
                "role": str(item.get("role") or ""),
                "file": str(item.get("file") or ""),
                "start_line": int(item.get("start_line") or 0),
                "end_line": int(item.get("end_line") or 0),
                "is_public": bool(item.get("is_public", True)),
                "state_writes": [str(x) for x in (item.get("state_writes") or [])],
                "state_reads": [str(x) for x in (item.get("state_reads") or [])],
            }
        )
    out.sort(key=lambda m: (m["file"], m["start_line"], m["symbol"]))
    return out


def _capability_evidence(members: List[Dict[str, Any]], limit: int = 4) -> List[Dict[str, Any]]:
    """能力点的证据 = 成员函数的文件与行区间（与 ``cards.py`` 的能力卡证据同构）。"""
    evidence: List[Dict[str, Any]] = []
    for member in members[:limit]:
        if not member["file"] or not member["start_line"]:
            continue
        evidence.append(
            {
                "file": member["file"],
                "start_line": member["start_line"],
                "end_line": member["end_line"] or member["start_line"],
                "symbol": member["symbol"],
                "signal": f"member:{member['role']}",
            }
        )
    return evidence


def _importance_reasons(entry: Dict[str, Any], flow_name: str) -> List[str]:
    """把排序元组翻译成中文理由 —— 让"为什么它排在前面"可解释，而不是一个黑箱分数。"""
    reasons: List[str] = []
    flow_count = int(entry.get("flow_count") or 0)
    if flow_count:
        label = f"（如「{flow_name}」）" if flow_name else ""
        reasons.append(f"参与 {flow_count} 条业务流程{label}")
    boundary = int(entry.get("exceptions") or 0) + int(entry.get("guards") or 0) + int(entry.get("rules") or 0)
    if boundary:
        reasons.append(
            f"含 {boundary} 条业务边界事实"
            f"（异常 {int(entry.get('exceptions') or 0)} / 前置判断 {int(entry.get('guards') or 0)}"
            f" / 业务规则 {int(entry.get('rules') or 0)}）"
        )
    state_writes = int(entry.get("state_writes") or 0)
    if state_writes:
        reasons.append(f"写入 {state_writes} 个状态字段")
    members = int(entry.get("members") or 0)
    if members:
        reasons.append(f"由 {members} 个函数构成")
    if not reasons:
        reasons.append("未参与已知流程，也没有边界事实 —— 核心度排序靠后")
    return reasons


@dataclass
class SectionCapability:
    """二级功能点（板块内的一个可点击项）。"""

    capability_id: str = ""
    name_cn: str = ""
    name_status: str = ""
    parent_id: str = ""
    entity: str = ""
    entity_cn: str = ""
    verb_class: str = ""
    verb_cn: str = ""
    cluster: str = ""
    confidence: str = "inferred"
    members: List[Dict[str, Any]] = field(default_factory=list)
    member_confidence: str = "verified"
    card: Dict[str, Any] = field(default_factory=dict)
    evidence: List[Dict[str, Any]] = field(default_factory=list)

    is_core: bool = False
    importance: List[int] = field(default_factory=list)
    importance_reasons: List[str] = field(default_factory=list)
    flow_count: int = 0
    rule_count: int = 0
    guard_count: int = 0
    exception_count: int = 0
    state_write_count: int = 0

    walkthrough_state: str = "beyond_budget"  # available | beyond_budget
    walkthrough_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "capability_id": self.capability_id,
            "name_cn": self.name_cn,
            "name_status": self.name_status,
            "parent_id": self.parent_id,
            "level": LEVEL_CAPABILITY,
            "entity": self.entity,
            "entity_cn": self.entity_cn,
            "verb_class": self.verb_class,
            "verb_cn": self.verb_cn,
            "cluster": self.cluster,
            "confidence": self.confidence,
            "member_confidence": self.member_confidence,
            "members": [dict(m) for m in self.members],
            "card": dict(self.card),
            "evidence": [dict(e) for e in self.evidence],
            "is_core": self.is_core,
            "importance": list(self.importance),
            "importance_reasons": list(self.importance_reasons),
            "counts": {
                "members": len(self.members),
                "flows": self.flow_count,
                "rules": self.rule_count,
                "guards": self.guard_count,
                "exceptions": self.exception_count,
                "state_writes": self.state_write_count,
            },
            "walkthrough": {
                "state": self.walkthrough_state,
                "available": self.walkthrough_state == "available",
                "reason": self.walkthrough_reason,
            },
        }


@dataclass
class Section:
    """一级业务域 = 一个业务板块。"""

    section_id: str = ""
    name_cn: str = ""
    name_status: str = ""
    role: str = ""
    confidence: str = "inferred"
    is_core: bool = True
    objective: str = ""
    objective_confidence: str = ""
    does_not: List[str] = field(default_factory=list)
    review_status: str = ""
    source: str = ""
    card: Dict[str, Any] = field(default_factory=dict)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    capabilities: List[SectionCapability] = field(default_factory=list)

    walkthrough_count: int = 0
    walkthrough_total: int = 0

    def to_dict(self) -> dict:
        return {
            "section_id": self.section_id,
            "name_cn": self.name_cn,
            "name_status": self.name_status,
            "role": self.role,
            "level": LEVEL_SECTION,
            "confidence": self.confidence,
            "is_core": self.is_core,
            "objective": self.objective,
            "objective_confidence": self.objective_confidence,
            "does_not": list(self.does_not),
            "review_status": self.review_status,
            "source": self.source,
            "card": dict(self.card),
            "evidence": [dict(e) for e in self.evidence],
            "capabilities": [c.to_dict() for c in self.capabilities],
            "counts": {
                "capabilities": len(self.capabilities),
                "members": sum(len(c.members) for c in self.capabilities),
                "walkthrough_available": self.walkthrough_count,
                "walkthrough_total": self.walkthrough_total,
            },
        }


@dataclass
class SectionBoard:
    """整个板块看板（含预算与截断说明）。"""

    project_id: str = ""
    project_name: str = ""
    level: str = ""
    sections: List[Section] = field(default_factory=list)
    budget: Dict[str, Any] = field(default_factory=dict)
    counts: Dict[str, Any] = field(default_factory=dict)
    source_hash: str = ""
    caveats: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "board_version": ALGORITHM_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "project_id": self.project_id,
            "project_name": self.project_name,
            "level": self.level,
            "sections": [s.to_dict() for s in self.sections],
            "budget": dict(self.budget),
            "counts": dict(self.counts),
            "source_hash": self.source_hash,
            "caveats": list(self.caveats),
        }


def build_sections(
    project_id: str,
    project_name: str,
    graph: Optional[Dict[str, Any]],
    tier: Dict[str, Any],
) -> SectionBoard:
    """从业务图谱产出版块看板。

    等级只影响 :func:`_apply_walkthrough_budget` 里的预算，不影响板块与证据本身。
    """
    graph = _as_dict(graph)
    board = SectionBoard(
        project_id=str(project_id or ""),
        project_name=str(project_name or ""),
        level=str(graph.get("level") or ""),
        source_hash=str(graph.get("source_hash") or ""),
    )

    if not graph or str(graph.get("status") or "") == "failed":
        board.caveats.append(
            "业务图谱不可用：本次不产出版块。平台不会在缺图谱时伪造板块结构，"
            "请先重建图谱（scripts/build_demo_snapshots.py）。"
        )
        board.counts = {"sections": 0, "capabilities": 0, "members": 0, "walkthrough_available": 0}
        board.budget = {
            "section_budget": tiering.effective_budget(tier, "section_budget", 0),
            "capability_budget": tiering.effective_budget(tier, "capability_budget", 0),
            "walkthrough_budget": tiering.effective_budget(tier, "walkthrough_capability_budget", 0),
        }
        return board

    cards = graph.get("module_cards") or {}
    cards = cards if isinstance(cards, dict) else {}

    # ---- 核心度排序：复用 design/task_builder 的既有实现 ----
    entries = {str(e.get("key")): e for e in _task_builder._capability_entries(graph)}

    capabilities_by_domain: Dict[str, List[SectionCapability]] = {}
    all_capabilities: List[SectionCapability] = []

    for capability in sorted(
        (c for c in (graph.get("capabilities") or []) if isinstance(c, dict)),
        key=lambda c: str(c.get("capability_id") or ""),
    ):
        capability_id = str(capability.get("capability_id") or "")
        if not capability_id:
            continue
        parent_id = str(capability.get("parent_id") or "")
        members = _member_dicts(capability)
        entry = entries.get(capability_id)

        item = SectionCapability(
            capability_id=capability_id,
            name_cn=str(capability.get("name_cn") or ""),
            name_status=str(capability.get("name_status") or ""),
            parent_id=parent_id,
            entity=str(capability.get("entity") or ""),
            entity_cn=str(capability.get("entity_cn") or ""),
            verb_class=str(capability.get("verb_class") or ""),
            verb_cn=str(capability.get("verb_cn") or ""),
            cluster=str(capability.get("cluster") or ""),
            confidence=str(capability.get("confidence") or "inferred"),
            members=members,
            card=_as_dict(cards.get(capability_id)),
            evidence=_capability_evidence(members),
            is_core=entry is not None,
        )
        if entry is not None:
            item.importance = [int(v) for v in _task_builder._importance(entry)]
            item.importance_reasons = _importance_reasons(entry, str(entry.get("related_flow") or ""))
            item.flow_count = int(entry.get("flow_count") or 0)
            item.rule_count = int(entry.get("rules") or 0)
            item.guard_count = int(entry.get("guards") or 0)
            item.exception_count = int(entry.get("exceptions") or 0)
            item.state_write_count = int(entry.get("state_writes") or 0)
        else:
            item.importance = [0, 0, 0, len(members)]
            item.importance_reasons = [
                "所属域被判为编排/支撑域（role 非 core），不进入核心度排序"
            ]

        capabilities_by_domain.setdefault(parent_id, []).append(item)
        all_capabilities.append(item)

    # ---- 板块：所有域都展示，core 优先 ----
    sections: List[Section] = []
    for domain in sorted(
        (d for d in (graph.get("domains") or []) if isinstance(d, dict)),
        key=lambda d: str(d.get("domain_id") or ""),
    ):
        domain_id = str(domain.get("domain_id") or "")
        card = _as_dict(cards.get(domain_id))
        role = str(domain.get("role") or "")
        section = Section(
            section_id=domain_id,
            name_cn=str(domain.get("name_cn") or ""),
            name_status=str(domain.get("name_status") or ""),
            role=role,
            confidence=str(domain.get("confidence") or "inferred"),
            is_core=role.strip().lower() not in ("orchestrator", "support"),
            objective=str(card.get("objective") or ""),
            objective_confidence=str(card.get("objective_confidence") or ""),
            does_not=[str(x) for x in (card.get("does_not") or [])],
            review_status=str(card.get("review_status") or domain.get("review_status") or ""),
            source=str(card.get("source") or domain.get("source") or ""),
            card=card,
            evidence=[dict(e) for e in (domain.get("evidence") or []) if isinstance(e, dict)],
            capabilities=capabilities_by_domain.get(domain_id, []),
        )
        # 域内能力点按核心度降序（与 task_builder 同口径），保证顺序稳定
        section.capabilities.sort(
            key=lambda c: (tuple(-v for v in c.importance), c.capability_id)
        )
        sections.append(section)

    # 核心域在前，然后按 (重要性之和降序, section_id 升序) —— 全序，确定性
    sections.sort(
        key=lambda s: (
            0 if s.is_core else 1,
            -sum(c.importance[0] + c.importance[1] for c in s.capabilities),
            s.section_id,
        )
    )

    # ---- 应用预算 ----
    board.budget = _apply_budgets(sections, all_capabilities, tier)

    board.sections = sections
    # 计数分「全部」与「本次展示」两组 —— 截断必须可见（不美化数据）
    shown_sections = sections[: board.budget["section_budget"]["shown"]]
    shown_capabilities = [c for s in shown_sections for c in s.capabilities]
    board.counts = {
        "sections": len(sections),
        "sections_shown": len(shown_sections),
        "core_sections": sum(1 for s in sections if s.is_core),
        "capabilities": len(all_capabilities),
        "capabilities_shown": len(shown_capabilities),
        "core_capabilities": sum(1 for c in all_capabilities if c.is_core),
        "members": sum(len(c.members) for c in all_capabilities),
        "members_shown": sum(len(c.members) for c in shown_capabilities),
        "walkthrough_available": sum(
            1 for c in shown_capabilities if c.walkthrough_state == "available"
        ),
        "walkthrough_requested": len(shown_capabilities),
    }
    board.caveats = [
        "板块（一级业务域）与能力点（二级功能点）由引擎按命名/调用/状态聚类推断，"
        "置信度为 inferred；成员函数的文件与行号来自 AST，为 verified。",
        "「核心度排序」复用设计层挑必备能力的同一份实现（design/task_builder.py），"
        "是**讲解顺序的参考信号**，不是「系统识别出了真实核心业务」——见 README §13.1 表述纪律。",
        tiering.TIER_CAVEAT,
    ]

    # 板块级预算说明
    section_budget = board.budget["section_budget"]
    if section_budget["truncated"]:
        board.caveats.append(
            f"本级策略最多展示 {section_budget['budget']} 个板块，"
            f"实际有 {section_budget['total']} 个 —— 超出的板块未在本次展示（不是没有）。"
        )
    # 能力点级预算说明 —— 少了这一条，被整个丢掉的能力点就"看不见"了，
    # 而"截断必须可见"是本平台的硬纪律（不美化数据）。
    capability_budget = board.budget["capability_budget"]
    if capability_budget["truncated"]:
        board.caveats.append(
            f"本级策略最多展示 {capability_budget['budget']} 个能力点，"
            f"实际有 {capability_budget['total']} 个 —— 有 "
            f"{capability_budget['total'] - capability_budget['shown']} 个能力点本次未展示"
            "（它们的代码与事实仍在图谱里，只是不在本次界面预算内）。"
        )
    # 课程预算说明（板块级）
    walkthrough_budget = board.budget.get("walkthrough_budget") or {}
    if walkthrough_budget.get("budget") is not None and walkthrough_budget.get("truncated"):
        board.caveats.append(
            f"本级策略只为最多 {walkthrough_budget['budget']} 个能力点生成沉浸式课程"
            f"（候选池 {walkthrough_budget['total']} 个，来源："
            f"{walkthrough_budget.get('eligible_pool')}）—— 其余能力点的板块分析照常可看。"
        )
    return board


def _apply_budgets(
    sections: List[Section],
    all_capabilities: List[SectionCapability],
    tier: Dict[str, Any],
) -> Dict[str, Any]:
    """把分级预算施加到板块与能力点上，并**显式标记截断**。

    选择口径
    --------
    - ``walkthrough_selection == "all"``：所有能力点都按核心度排序后取前 N 个；
    - ``"core_ranked"``：只从**核心域**的能力点里按核心度取前 N 个
      （编排/支撑域的样板代码不值得生成一课，但它们的板块分析照常展示）。
    """
    # 1. 板块预算：超出预算的板块整个不展示（并在 caveats 里说明）
    total_sections = len(sections)
    section_budget = tiering.effective_budget(tier, "section_budget", total_sections)
    visible = sections[: section_budget["shown"]] if section_budget["budget"] is not None else sections

    # 2. 能力点预算：按板块顺序累计
    cap_total = sum(len(s.capabilities) for s in visible)
    cap_budget = tiering.effective_budget(tier, "capability_budget", cap_total)
    running = 0
    for section in visible:
        kept: List[SectionCapability] = []
        for capability in section.capabilities:
            if cap_budget["budget"] is not None and running >= int(cap_budget["budget"]):
                break
            kept.append(capability)
            running += 1
        section.capabilities = kept

    # 3. 沉浸式课程预算
    pool = [c for s in visible for c in s.capabilities]
    if str(tier.get("walkthrough_selection") or "all") == "core_ranked":
        pool = [c for c in pool if c.is_core]
    pool.sort(key=lambda c: (tuple(-v for v in c.importance), c.capability_id))

    wt_total = len(pool)
    wt_budget = tiering.effective_budget(tier, "walkthrough_capability_budget", wt_total)
    chosen = {c.capability_id for c in pool[: wt_budget["shown"]]}

    label = str(tier.get("tier_label") or "")
    for capability in pool:
        if capability.capability_id in chosen:
            capability.walkthrough_state = "available"
            capability.walkthrough_reason = (
                f"进入本级（{label}）沉浸式课程预算：核心度排名靠前。"
            )
        else:
            capability.walkthrough_state = "beyond_budget"
            capability.walkthrough_reason = (
                f"超出本级（{label}）沉浸式课程预算（最多 "
                f"{wt_budget['budget']} 个能力点），本次未生成课程。"
                "板块分析与证据仍然完整可看。"
            )
    # 未进入 pool 的（非核心域、被核心优先策略排除）也要有明确理由
    for section in visible:
        for capability in section.capabilities:
            if capability.walkthrough_state == "beyond_budget" and not capability.walkthrough_reason:
                capability.walkthrough_reason = (
                    f"本级（{label}）采用核心优先策略，该能力点所属域不是核心域，本次不生成课程。"
                )

    for section in visible:
        section.walkthrough_total = len(section.capabilities)
        section.walkthrough_count = sum(
            1 for c in section.capabilities if c.walkthrough_state == "available"
        )

    # 板块被截断时，未展示的板块不作处理（它们整个不出现）
    return {
        "tier_label": label,
        "walkthrough_selection": str(tier.get("walkthrough_selection") or "all"),
        "section_budget": section_budget,
        "capability_budget": cap_budget,
        "walkthrough_budget": {
            **wt_budget,
            "total": wt_total,
            "eligible_pool": "core_capabilities_only"
            if str(tier.get("walkthrough_selection") or "all") == "core_ranked"
            else "all_capabilities",
        },
        "segments_per_lesson_cap": tier.get("segments_per_lesson_cap"),
        "statements_per_segment_cap": tier.get("statements_per_segment_cap"),
        "analysis_depth": tier.get("analysis_depth"),
    }
