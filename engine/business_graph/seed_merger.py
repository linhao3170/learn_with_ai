"""
教师种子图谱与合并机制（README5 §3.8）

为什么必须有这一层
------------------
自动生成业务图谱是研究性工作，短期内不可能在所有项目上达到"可直接教学"的准确度。
但演示不能翻车，叙事也不能说谎。所以：

- **种子图谱**（``sample_projects/<project>/business_graph.seed.json``）由教师/人工维护；
- 自动结果是"初始推断版"；
- 两者按 id 对齐后合并，**种子优先**，每个节点带 ``source`` 徽章 ——
  UI 上明确区分"教师审核版"与"系统推断版"。

合并规则（README5 §3.8）
------------------------
1. 按 ``capability_id`` / ``domain_id`` 对齐；
2. seed 中 ``locked: true`` 的字段不可被 auto 覆盖；
3. auto 新发现、seed 没有的能力 → 追加，标 ``source: auto``、``confidence: inferred``；
4. seed 有、auto 未发现的能力 → 保留，标 ``source: teacher``，
   并在审核界面提示"系统未能从代码中识别"；
5. 输出里每个节点都带 ``source``，让 UI 能如实展示。
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

#: 允许被种子上锁的字段（README5 §3.8 规则 2）
LOCKABLE_FIELDS = (
    "name_cn", "objective", "does_not", "parent_id", "role", "entity_cn",
    "inputs", "outputs", "business_rules_text",
)


def seed_path_for(project_path: str) -> Optional[str]:
    """给定项目目录，返回种子图谱路径（不存在则 ``None``）。"""
    candidate = os.path.join(project_path, "business_graph.seed.json")
    return candidate if os.path.isfile(candidate) else None


def load_seed(project_path: str) -> Optional[dict]:
    """读取教师种子图谱；缺失或损坏时返回 ``None``（**不阻断**自动生成）。"""
    path = seed_path_for(project_path)
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def merge_graph(auto: dict, seed: Optional[dict]) -> Tuple[dict, dict]:
    """把种子图谱合并进自动结果。

    Args:
        auto: 自动生成的图谱 dict（必须含 ``domains`` / ``module_cards``）
        seed: 教师种子 dict 或 ``None``

    Returns:
        ``(merged, report)``。``report`` 说明合并动作，便于审核界面展示。
    """
    report: Dict[str, Any] = {
        "seed_loaded": seed is not None,
        "locked_fields": 0,
        "teacher_kept": [],
        "auto_kept": [],
        "unmatched_auto": [],
    }
    if not seed:
        return auto, report

    merged = json.loads(json.dumps(auto))  # 深拷贝，避免污染调用方
    domains = merged.setdefault("domains", [])
    cards = merged.setdefault("module_cards", {})

    domain_by_id = {d.get("domain_id"): d for d in domains}

    # ---- 一级域：先按 id，再按 name_cn ----
    for seed_domain in seed.get("domains", []) or []:
        target = domain_by_id.get(seed_domain.get("domain_id"))
        if target is None:
            for candidate in domains:
                if candidate.get("name_cn") == seed_domain.get("name_cn"):
                    target = candidate
                    break
        if target is None:
            # 规则 4：种子有、auto 没有 → 保留并标注
            new_domain = dict(seed_domain)
            new_domain["source"] = "teacher"
            new_domain["confidence"] = "confirmed"
            new_domain["note"] = "系统未能从代码中识别该业务域"
            domains.append(new_domain)
            domain_by_id[new_domain.get("domain_id")] = new_domain
            report["teacher_kept"].append(new_domain.get("domain_id"))
            continue
        _apply_seed_fields(target, seed_domain, report)
        target["source"] = "teacher"

    # ---- 二级功能点 / 模块卡片 ----
    for cap_id, seed_card in (seed.get("module_cards") or {}).items():
        target = cards.get(cap_id)
        if target is None:
            new_card = dict(seed_card)
            new_card["module_id"] = cap_id
            new_card["source"] = "teacher"
            new_card["confidence"] = "confirmed"
            new_card["review_status"] = "approved"
            new_card["note"] = "系统未能从代码中识别该功能点"
            cards[cap_id] = new_card
            report["teacher_kept"].append(cap_id)
            continue
        _apply_seed_fields(target, seed_card, report)
        target["source"] = "teacher"
        if seed_card.get("review_status"):
            target["review_status"] = seed_card["review_status"]

    # ---- 规则 3：auto 新发现、seed 未覆盖的节点标注清楚 ----
    for card_id, card in sorted(cards.items()):
        if card.get("source") not in ("teacher",):
            card["source"] = "auto"
            card.setdefault("review_status", "needs_review")
            report["unmatched_auto"].append(card_id)

    merged["seed_report"] = report
    return merged, report


def _apply_seed_fields(target: dict, source: dict, report: dict) -> None:
    """把种子字段写进目标；带锁的字段只由种子说了算。"""
    locked = set(source.get("locked") or [])
    for field in LOCKABLE_FIELDS:
        if field not in source:
            continue
        if field in locked or field in target:
            target[field] = source[field]
            if field in locked:
                report["locked_fields"] += 1
    # 种子显式提供的其它字段也照抄（但不动结构与证据）
    for field, value in source.items():
        if field in ("locked", "evidence", "members", "business_rules", "state_changes"):
            continue
        target[field] = value
