"""复杂度分级（README5 §3.3）

**级别怎么定（这是关键决定）**
------------------------------
README4 §四 对四个级别的定义**本来就是结构性的**：

| 级别 | README4 的原话 |
|---|---|
| L1 | 1–5 个一级模块；只有一条主流程；状态变化较少；没有复杂权限和外部系统 |
| L2 | 5–10 个一级模块；存在多个二级模块；有用户、数据和基础状态；存在跨模块调用 |
| L3 | 10–25 个模块；多角色；多条业务流程；状态流转明显；存在权限、审批、异常和回滚 |
| L4 | 25 个以上模块；多个外部系统；多角色协作；跨领域业务 |

所以**级别按这些结构条件判定**（模块数 + 二级模块数 + 角色数 + 审批/权限证据 + 流程数），
``complexity_raw`` 只作为**跨项目比较的辅助分**同时输出。

为什么不用 raw 直接切阈值：第一版就是这么干的，结果 784 行的教学样本
（5 个域、29 个功能点）被判成 **L4**、1112 行的 python-dotenv 被判成 **L3** ——
"复杂分支多"被当成了"业务复杂"，这与 README4 的定义是两回事。

**阈值与门限依然标注为待校准**（README5 §3.3）。级别判定的依据会写进 ``level_basis``，
让教师能一眼看到"为什么是 L2"，并且可以手动覆盖。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .. import lexicon
from .capabilities import Capability
from .domains import Domain
from .facts import KIND_GUARD, KIND_RAISE, KIND_RULE, Fact

ALGORITHM_VERSION = "complexity-1.1"

#: 七维权重（README5 §3.3）—— 用于复杂度**分**，不用于定级
WEIGHTS: Dict[str, float] = {
    "domains": 1.0,
    "capabilities": 1.5,
    "cross_domain_edges": 0.8,
    "written_state_fields": 0.6,
    "business_branches": 0.4,
    "external_entries": 1.0,
    "role_hits": 1.2,
}

#: 各校验收口的结构区间（来自 README4 §四）
LEVEL_RULES: List[Dict[str, object]] = [
    {"level": "L1", "label": "基础项目", "max_domains": 4, "desc": "1–5 个一级模块，一条主流程"},
    {"level": "L2", "label": "多模块项目", "max_domains": 9, "desc": "5–10 个一级模块，多个二级模块，存在跨模块调用"},
    {"level": "L3", "label": "复杂业务项目", "max_domains": 24, "desc": "10–25 个模块，多角色，多条流程，权限/审批/异常"},
    {"level": "L4", "label": "综合设计项目", "max_domains": None, "desc": "25 个以上模块，多外部系统，多角色协作"},
]

#: 升级/降级门限（可被教师覆盖）
GATES = {
    # 二级模块数 >= 这个值才算"存在多个二级模块"，L1 升 L2
    "l2_min_capabilities": 8,
    # L3 需要：角色种类 >= 2 或（有审批类能力 且 状态字段 >= 5）
    "l3_min_roles": 2,
    "l3_min_state_fields": 5,
    # L4 需要：角色种类 >= 3 且外部入口 >= 3；否则最多 L3
    "l4_min_roles": 3,
    "l4_min_entries": 3,
}

TRAINING_BY_LEVEL: Dict[str, List[str]] = {
    "L1": ["module_identify", "card_fill", "flow_order"],
    "L2": ["module_split", "card_fill", "flow_design"],
    "L3": ["multi_scenario", "state_machine", "boundary_refactor", "compare"],
    "L4": ["full_design", "multi_option", "reconstruct", "defense"],
}


@dataclass
class ComplexityResult:
    level: str = "L1"
    level_label: str = ""
    level_desc: str = ""
    level_basis: List[str] = field(default_factory=list)
    raw: float = 0.0
    breakdown: Dict[str, float] = field(default_factory=dict)
    weights: Dict[str, float] = field(default_factory=dict)
    thresholds: List[Dict[str, object]] = field(default_factory=list)
    gates: Dict[str, object] = field(default_factory=dict)
    formula: str = ""
    training_task_types: List[str] = field(default_factory=list)
    algorithm_version: str = ALGORITHM_VERSION
    caveat: str = ""

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "level_label": self.level_label,
            "level_desc": self.level_desc,
            "level_basis": self.level_basis,
            "raw": round(self.raw, 2),
            "breakdown": {k: round(v, 2) for k, v in self.breakdown.items()},
            "weights": self.weights,
            "thresholds": self.thresholds,
            "gates": self.gates,
            "formula": self.formula,
            "training_task_types": self.training_task_types,
            "algorithm_version": self.algorithm_version,
            "caveat": self.caveat,
        }


def _role_hits(units, capabilities: Sequence[Capability]) -> int:
    """角色/权限词命中数（标识符 + 类常量）。

    只统计**去重后的角色词种类**，不是出现次数 —— 否则一个项目里到处写
    ``user`` 就会把复杂度顶到 L4。
    """
    terms = {str(t).lower() for t in lexicon.role_terms()}
    if not terms:
        return 0
    found = set()
    for unit in units:
        haystack = [unit.symbol, unit.module]
        for method in unit.methods:
            haystack.append(method.symbol)
        for text in haystack:
            lowered = str(text).lower()
            for token in re.split(r"[^0-9a-z\u4e00-\u9fff]+", lowered):
                if token and token in terms:
                    found.add(token)
            for term in terms:
                if re.search(r"[\u4e00-\u9fff]", term) and term in str(text):
                    found.add(term)
    return len(found)


def _cross_domain_edges(domains: Sequence[Domain], capabilities: Sequence[Capability],
                        relations: Sequence) -> int:
    """跨域调用边数（功能点粒度上的跨域关系，去重）。"""
    cap_to_domain = {cap.capability_id: cap.parent_id for cap in capabilities}
    edges = set()
    for relation in relations:
        src_domain = cap_to_domain.get(relation.from_module)
        dst_domain = cap_to_domain.get(relation.to_module)
        if src_domain and dst_domain and src_domain != dst_domain:
            edges.add((src_domain, dst_domain))
    return len(edges)


def _external_entries(units) -> int:
    """外部入口数：没有任何调用者的公开函数（且它自己不写状态也算入口候选——这里只数公开且无调用者）。"""
    count = 0
    for unit in units:
        for method in unit.methods:
            if method.is_public and not method.calls_out:
                count += 1
    return count


def compute_complexity(
    domains: Sequence[Domain],
    capabilities: Sequence[Capability],
    facts: Sequence[Fact],
    units: Sequence,
    relations: Sequence,
) -> ComplexityResult:
    """计算复杂度级别与七维明细。"""
    written_state = set()
    for cap in capabilities:
        for member in cap.members:
            for attr in member.state_writes:
                written_state.add(attr)

    branches = sum(1 for f in facts if f.kind in (KIND_RULE, KIND_GUARD, KIND_RAISE))

    breakdown = {
        "domains": float(len(domains)),
        "capabilities": float(len(capabilities)),
        "cross_domain_edges": float(_cross_domain_edges(domains, capabilities, relations)),
        "written_state_fields": float(len(written_state)),
        "business_branches": float(branches),
        "external_entries": float(_external_entries(units)),
        "role_hits": float(_role_hits(units, capabilities)),
    }
    raw = sum(breakdown[key] * WEIGHTS[key] for key in WEIGHTS)

    # ---- 定级：按 README4 §四 的结构条件，而不是按 raw 切阈值 ----
    role_count = int(breakdown["role_hits"])
    state_fields = int(breakdown["written_state_fields"])
    entry_count = int(breakdown["external_entries"])
    domain_count = len(domains)
    capability_count = len(capabilities)

    # 审批/治理类能力（approve / reject / cancel / validate）—— L3 的"权限、审批"证据
    governance_verbs = {"approve", "reject", "cancel", "identity", "validate"}
    governance_caps = [c for c in capabilities if getattr(c, "verb_class", "") in governance_verbs]

    basis: List[str] = []

    # 一级：按一级模块数落区间
    level = "L4"
    level_label = "综合设计项目"
    level_desc = ""
    for item in LEVEL_RULES:
        max_domains = item["max_domains"]
        if max_domains is None or domain_count <= int(max_domains):
            level = str(item["level"])
            level_label = str(item["label"])
            level_desc = str(item["desc"])
            break
    basis.append(f"一级业务域 {domain_count} 个 → 落区间 {level}（{level_desc}）")

    # L1 → L2：存在多个二级模块
    if level == "L1" and capability_count >= GATES["l2_min_capabilities"]:
        level, level_label, level_desc = "L2", "多模块项目", str(LEVEL_RULES[1]["desc"])
        basis.append(
            f"二级功能点 {capability_count} 个 >= {GATES['l2_min_capabilities']}，"
            "视为「存在多个二级模块」→ 升为 L2"
        )

    # L3 门限：多角色 或（审批类能力 + 足够的状态字段）
    if level == "L3" or level == "L4":
        has_roles = role_count >= int(GATES["l3_min_roles"])
        has_governance = bool(governance_caps) and state_fields >= int(GATES["l3_min_state_fields"])
        if not (has_roles or has_governance):
            level, level_label, level_desc = "L2", "多模块项目", str(LEVEL_RULES[1]["desc"])
            basis.append(
                f"未达到 L3 门限（角色 {role_count} < {GATES['l3_min_roles']}，"
                f"且审批类能力 {len(governance_caps)} 个 / 状态字段 {state_fields} "
                f"< {GATES['l3_min_state_fields']}）→ 降为 L2"
            )
        else:
            basis.append(
                f"满足 L3 门限：角色 {role_count} 个，审批/校验类能力 {len(governance_caps)} 个，"
                f"状态字段 {state_fields} 个"
            )

    # L4 门限：多角色协作 + 多个外部入口
    if level == "L4":
        if role_count >= int(GATES["l4_min_roles"]) and entry_count >= int(GATES["l4_min_entries"]):
            basis.append(
                f"满足 L4 门限：角色 {role_count} >= {GATES['l4_min_roles']}，"
                f"外部入口 {entry_count} >= {GATES['l4_min_entries']}"
            )
        else:
            level, level_label, level_desc = "L3", "复杂业务项目", str(LEVEL_RULES[2]["desc"])
            basis.append(
                f"未达到 L4 门限（角色 {role_count} / 外部入口 {entry_count}）→ 降为 L3"
            )

    formula = (
        "level = 由 README4 §四 的结构条件判定（一级域数 / 二级功能点数 / 角色数 / "
        "审批类能力 / 流程数）；complexity_raw 仅作跨项目比较的辅助分："
        + " + ".join(f"{WEIGHTS[k]}×{k}" for k in WEIGHTS)
    )

    return ComplexityResult(
        level=level,
        level_label=level_label,
        level_desc=level_desc,
        level_basis=basis,
        raw=raw,
        breakdown=breakdown,
        weights=dict(WEIGHTS),
        thresholds=[dict(t) for t in LEVEL_RULES],
        gates=dict(GATES),
        formula=formula,
        training_task_types=list(TRAINING_BY_LEVEL.get(level, [])),
        caveat=(
            "级别按 README4 §四 的结构定义判定，依据写在 level_basis 里，教师可手动覆盖；"
            "门限数值未经多项目校准；domains/capabilities 为 inferred，其余维度为 verified。"
        ),
    )
