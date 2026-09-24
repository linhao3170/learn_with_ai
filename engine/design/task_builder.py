"""分级设计任务生成器（README §9.1 ``task_builder.py``）。

给学生一个**新需求**，而不是直接给出原项目结构；任务按项目复杂度分级（L1–L4）。

``must_have``（必备能力清单）从哪来 —— 这是本模块最要紧的纪律
==========================================================
README §9.1 原文：

    ① 教师种子（``design_tasks.seed.json``，**首选**）；
    ② 从同类现有项目的域 / 能力清单**提炼 + 人工确认**；
    ③ **绝不**让 LLM 直接生成 ``must_have`` 并当成评分基准。

本模块只实现 ① 与 ②，且 ② **必须如实标注**：

- 命中教师种子 → ``must_have_source = "teacher_seed"``、``needs_review = False``；
- 没命中种子 → ``must_have_source = "auto_from_project"``、``needs_review = True``，
  并在 caveats 里写明「清单由本项目图谱自动提炼、尚未经教师确认，存在照着本项目结构抄的捷径」。
  **不允许把自动提炼的清单当成教师审核过的评分基准**（README §18：「自动生成图谱但未标注
  『待审核』」是不许上台的半成品）。

学生视图 / 教师视图必须是两份（README §10.5 字段可见性矩阵）
==========================================================
- ``must_have`` / ``required_relations`` / ``forbidden_merges`` / ``rubric_weights``
  的**完整内容只给教师**；
- 学生视图只给：题干、场景、需求简报（按任务类型决定给「功能清单 / 流程线索 / 只有规模」）、
  以及「本任务有几项必备能力」这个范围提示（§12.6 的第 1 层提示：指向范围）。
- 两份视图由**同一个函数**产出（``build_design_task(..., teacher_mode=...)``），
  不给前端两份可能漂移的代码路径。

做不到的事
==========
- **不编业务含义**：模块名、目标、边界全部来自图谱里已有的文本（域名 / 能力名 / 流程名）；
  引擎推不出来的（``objective`` 为空）就空着，不编；
- **不编需求文档**：自动生成的简报只有「已有能力名 / 流程名 / 规模数字」三种口径，
  没有教师写的需求描述（那需要教师种子）；
- **不做 LLM 调用**：题干模板来自 ``engine/lexicon/design_tasks.json``。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from engine.lexicon import lexicon_source, load_lexicon

__all__ = [
    "ALGORITHM_VERSION",
    "TASK_VERSION",
    "CONTRACT_VERSION",
    "LEVEL_ORDER",
    "task_spec_source",
    "types_config",
    "level_types",
    "teacher_seed_tasks",
    "teacher_seed_source",
    "must_have_from_graph",
    "list_design_tasks",
    "build_design_task",
    "resolve_task",
    "student_view",
]

#: 产物版本（纪律：每个产物带 algorithm_version）
ALGORITHM_VERSION = "design-task-1.0"
TASK_VERSION = "1.0"
CONTRACT_VERSION = "1.0"

#: 级别顺序（用于「上一级的 max_domains + 1 = 本级的 min」这类推导）
LEVEL_ORDER = ("L1", "L2", "L3", "L4")

#: ``brief_includes`` 的三种口径
BRIEF_CAPABILITIES = "capabilities"
BRIEF_FLOWS = "flows"
BRIEF_COUNTS = "counts"

_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


# ============================================================
# 词典
# ============================================================

def task_spec_source() -> str:
    """任务模板词典的来源路径（排查「用的哪份题干」用）。"""
    return lexicon_source("design_tasks")


def types_config() -> Dict[str, Dict[str, Any]]:
    """任务类型 → 配置（题干模板、简报口径、must_have 来源）。"""
    data = load_lexicon("design_tasks").get("types") or {}
    if not isinstance(data, dict):
        return {}
    return {str(key): dict(value) for key, value in data.items() if isinstance(value, dict)}


def level_types(level: str) -> List[str]:
    """该级别允许的任务类型（顺序即默认顺序：第一个是默认任务）。"""
    data = load_lexicon("design_tasks").get("level_types") or {}
    items = data.get(str(level)) or []
    return [str(item) for item in items if str(item or "").strip()]


def _brief_config() -> Dict[str, Any]:
    data = load_lexicon("design_tasks").get("brief") or {}
    return dict(data) if isinstance(data, dict) else {}


def _must_have_config() -> Dict[str, Any]:
    data = load_lexicon("design_tasks").get("must_have") or {}
    return dict(data) if isinstance(data, dict) else {}


def _fill(template: str, values: Dict[str, Any]) -> str:
    """替换题干模板里的占位符（缺值一律换成空串，**不留 ``{xxx}``**）。"""
    def _replace(match: "re.Match[str]") -> str:
        key = match.group(1)
        value = values.get(key, "")
        if isinstance(value, (list, tuple)):
            return "、".join(str(item) for item in value)
        return str(value)

    return _PLACEHOLDER_RE.sub(_replace, str(template or ""))


# ============================================================
# 教师种子
# ============================================================

def teacher_seed_source() -> str:
    """教师种子的来源路径（排查「任务到底是不是教师给的」用）。"""
    return lexicon_source("design_tasks.seed")


def teacher_seed_tasks(project_id: str) -> List[Dict[str, Any]]:
    """该项目下教师审核过的任务（没有就返回空列表 —— 不编一份出来）。"""
    data = load_lexicon("design_tasks.seed")
    tasks = data.get("tasks") or {}
    if not isinstance(tasks, dict):
        return []
    items = tasks.get(str(project_id)) or []
    return [dict(item) for item in items if isinstance(item, dict)]


# ============================================================
# must_have：从图谱提炼（② 号的「提炼」部分；人工确认由教师种子完成）
# ============================================================

def _core_domain_ids(graph: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for domain in graph.get("domains") or []:
        if not isinstance(domain, dict):
            continue
        role = str(domain.get("role") or "").strip().lower()
        if role in ("orchestrator", "support"):
            continue
        out.append(str(domain.get("domain_id") or ""))
    return out


def _flow_names_by_capability(graph: Dict[str, Any]) -> Dict[str, str]:
    """能力 id → 它所在流程的名字（取第一条命中的流程；找不到就空着）。"""
    mapping: Dict[str, str] = {}
    for flow in graph.get("flows") or []:
        if not isinstance(flow, dict):
            continue
        name = str(flow.get("name_cn") or flow.get("flow_id") or "")
        for capability_id in flow.get("involved_capabilities") or []:
            key = str(capability_id)
            if key and key not in mapping and name:
                mapping[key] = name
    return mapping


def _capability_facts(graph: Dict[str, Any]) -> Dict[str, Dict[str, int]]:
    """能力 id → 事实计数（规则 / 前置判断 / 异常 / 状态变化）。"""
    stats: Dict[str, Dict[str, int]] = {}
    for fact in graph.get("facts") or []:
        if not isinstance(fact, dict):
            continue
        capability_id = str(fact.get("capability_id") or "")
        kind = str(fact.get("kind") or "")
        if not capability_id or not kind:
            continue
        bucket = stats.setdefault(capability_id, {})
        bucket[kind] = bucket.get(kind, 0) + 1
    return stats


def _flow_participation(graph: Dict[str, Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for flow in graph.get("flows") or []:
        if not isinstance(flow, dict):
            continue
        for capability_id in flow.get("involved_capabilities") or []:
            key = str(capability_id)
            counts[key] = counts.get(key, 0) + 1
    return counts


def _flow_names(graph: Dict[str, Any], limit: int = 5) -> List[str]:
    """图谱里的流程名（去重、保持图谱顺序、截断到 limit）。

    去重是必要的：同一个流程名会带不同后缀的变体（例如「… Flow」与「… Flow（边界）」），
    简报里出现两次同名流程会让学生以为那是两条不同的流程。
    """
    out: List[str] = []
    for flow in graph.get("flows") or []:
        if not isinstance(flow, dict):
            continue
        name = str(flow.get("name_cn") or flow.get("flow_id") or "").strip()
        if name and name not in out:
            out.append(name)
        if len(out) >= limit:
            break
    return out


def _capability_entries(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    cards = graph.get("module_cards") or {}
    cards = cards if isinstance(cards, dict) else {}
    flows = _flow_names_by_capability(graph)
    fact_stats = _capability_facts(graph)
    flow_counts = _flow_participation(graph)

    core_domains = set(_core_domain_ids(graph))
    entries: List[Dict[str, Any]] = []
    for capability in graph.get("capabilities") or []:
        if not isinstance(capability, dict):
            continue
        capability_id = str(capability.get("capability_id") or "")
        if not capability_id:
            continue
        parent = str(capability.get("parent_id") or "")
        if core_domains and parent not in core_domains:
            continue
        card = cards.get(capability_id) if isinstance(cards.get(capability_id), dict) else {}
        stats = fact_stats.get(capability_id, {})
        members = capability.get("members") or []
        entries.append(
            {
                "key": capability_id,
                "name_cn": str(capability.get("name_cn") or ""),
                "cluster": str(capability.get("cluster") or ""),
                "verb_class": str(capability.get("verb_class") or ""),
                "verb_cn": str(capability.get("verb_cn") or ""),
                "entity": str(capability.get("entity") or ""),
                "entity_cn": str(capability.get("entity_cn") or ""),
                "domain_id": parent,
                "related_flow": flows.get(capability_id, ""),
                "members": len(members),
                "state_writes": len(set(card.get("outputs") or [])),
                "guards": int(stats.get("guard", 0)),
                "exceptions": int(stats.get("exception", 0)),
                "rules": int(stats.get("rule", 0)),
                "flow_count": int(flow_counts.get(capability_id, 0)),
                "source": "auto_from_project",
            }
        )
    return entries


def _importance(entry: Dict[str, Any]) -> Tuple[int, int, int, int]:
    """重要度（用于挑必备能力）：先看流程参与，再看异常 / 规则，再看状态写入与成员数。"""
    return (
        int(entry.get("flow_count") or 0),
        int(entry.get("exceptions") or 0) + int(entry.get("guards") or 0) + int(entry.get("rules") or 0),
        int(entry.get("state_writes") or 0),
        int(entry.get("members") or 0),
    )


def must_have_from_graph(graph: Dict[str, Any], source_kind: str = "core_capabilities") -> List[Dict[str, Any]]:
    """从图谱提炼必备能力清单（``source_kind`` 三种口径）。

    - ``core_capabilities``：核心域里最重要的若干能力（默认）；
    - ``flow_capabilities``：至少参与一条流程的能力；
    - ``boundary_capabilities``：带异常 / 前置判断 / 规则的能力。

    **同一 ``(动词类别, 业务对象)`` 只保留最重要的一条**：否则清单会变成
    「查询 / 查询 / 查询」的重复项，覆盖度也就失去意义。
    输出顺序稳定（重要度降序 + key 升序），保证同一份图谱两次调用结果一致。
    """
    entries = _capability_entries(graph)
    if source_kind == "flow_capabilities":
        entries = [item for item in entries if int(item.get("flow_count") or 0) > 0]
    elif source_kind == "boundary_capabilities":
        entries = [
            item
            for item in entries
            if int(item.get("exceptions") or 0) + int(item.get("guards") or 0) + int(item.get("rules") or 0) > 0
        ]

    entries.sort(key=lambda item: (tuple(-v for v in _importance(item)), str(item.get("key"))))

    limit = int(_must_have_config().get("limit") or 10)
    picked: List[Dict[str, Any]] = []
    seen_pairs: List[Tuple[str, str]] = []
    for entry in entries:
        pair = (str(entry.get("verb_class") or ""), str(entry.get("entity") or ""))
        if pair in seen_pairs:
            continue
        seen_pairs.append(pair)
        picked.append(entry)
        if len(picked) >= limit:
            break
    return picked


# ============================================================
# 简报（学生看得见的「需求侧」信息）
# ============================================================

def _brief(
    graph: Dict[str, Any],
    spec: Dict[str, Any],
    must_have: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """按任务类型的 ``brief_includes`` 生成简报。

    - ``capabilities``：把功能需求清单给学生（考「归类」）；
    - ``flows``：给流程线索（考「流程与模块的对应」）；
    - ``counts``：只给规模数字（考「自己拆模块」）。
    """
    config = _brief_config()
    flow_limit = int(config.get("flow_limit") or 5)
    capability_limit = int(config.get("capability_limit") or 12)
    mode = str(spec.get("brief_includes") or BRIEF_COUNTS)

    flows: List[str] = _flow_names(graph, flow_limit)
    capability_names = [str(item.get("name_cn") or item.get("key")) for item in must_have]
    domain_count = len({str(item.get("domain_id") or "") for item in must_have if item.get("domain_id")})

    items: List[str] = []
    if mode == BRIEF_CAPABILITIES:
        items = capability_names[:capability_limit]
    elif mode == BRIEF_FLOWS:
        items = flows

    text = ""
    if mode == BRIEF_CAPABILITIES:
        text = "本项目的功能需求清单：" + "、".join(items) if items else "本项目没有可用于简报的功能需求清单。"
    elif mode == BRIEF_FLOWS:
        text = "本项目的流程线索：" + "、".join(items) if items else "本项目没有可用于简报的流程记录。"
    else:
        text = (
            f"本项目规模：{len(must_have)} 项核心功能需求、{domain_count} 个业务域、"
            f"{len(graph.get('flows') or [])} 条流程（具体模块由你自己拆）。"
        )

    return {
        "mode": mode,
        "items": items,
        "text_cn": text,
        "flow_names": flows,
        "capability_names": capability_names,
        "counts": {
            "must_have": len(must_have),
            "domains": domain_count,
            "flows": len(graph.get("flows") or []),
        },
    }


# ============================================================
# 任务组装
# ============================================================

def _level_from_graph(graph: Dict[str, Any]) -> str:
    level = str(graph.get("level") or "").strip()
    if level in LEVEL_ORDER:
        return level
    complexity_level = str((graph.get("complexity") or {}).get("level") or "").strip()
    return complexity_level if complexity_level in LEVEL_ORDER else "L1"


def _level_label(graph: Dict[str, Any], level: str) -> Dict[str, str]:
    """级别标签与说明（来自图谱自己的复杂度阈值表，同一份定义只存在一处）。"""
    for item in ((graph.get("complexity") or {}).get("thresholds") or []):
        if isinstance(item, dict) and str(item.get("level")) == level:
            return {"label": str(item.get("label") or ""), "desc": str(item.get("desc") or "")}
    return {"label": "", "desc": ""}


def _level_module_range(graph: Dict[str, Any], level: str) -> Tuple[Optional[int], Optional[int]]:
    thresholds = [item for item in ((graph.get("complexity") or {}).get("thresholds") or []) if isinstance(item, dict)]
    for index, item in enumerate(thresholds):
        if str(item.get("level")) != level:
            continue
        previous = thresholds[index - 1].get("max_domains") if index > 0 else None
        minimum = 1 if previous is None else int(previous) + 1
        maximum = item.get("max_domains")
        return minimum, (None if maximum is None else int(maximum))
    return None, None


def _auto_task(graph: Dict[str, Any], level: str, type_key: str, index: int) -> Dict[str, Any]:
    spec = types_config().get(type_key)
    if not spec:
        return {}
    must_have = must_have_from_graph(graph, str(spec.get("must_have_source") or "core_capabilities"))
    core_must_have = must_have_from_graph(graph, "core_capabilities")
    minimum, maximum = _level_module_range(graph, level)
    meta = _level_label(graph, level)
    project_name = str(graph.get("project_name") or graph.get("project_id") or "本项目")
    values = {
        "project_name": project_name,
        "level": level,
        "level_label": meta.get("label") or "",
        "level_desc": meta.get("desc") or "",
        "capability_count": len(core_must_have),
        "domain_count": len({str(item.get("domain_id") or "") for item in core_must_have}),
        "flow_count": len(graph.get("flows") or []),
        "flow_names": _flow_names(graph, 5),
        "module_count_min": minimum if minimum is not None else 1,
        "module_count_max": maximum if maximum is not None else "不限",
    }
    task_id = f"dt_{graph.get('project_id') or 'project'}_{level}_{type_key}"
    return {
        "task_version": TASK_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "contract_version": CONTRACT_VERSION,
        "task_id": task_id,
        "project_id": str(graph.get("project_id") or ""),
        "project_name": project_name,
        "source_hash": str(graph.get("source_hash") or ""),
        "level": level,
        "level_label": meta.get("label") or "",
        "level_desc": meta.get("desc") or "",
        "type": type_key,
        "type_name_cn": str(spec.get("name_cn") or type_key),
        "goal_cn": str(spec.get("goal_cn") or ""),
        "prompt_cn": _fill(str(spec.get("prompt_cn") or ""), values),
        "scenario_cn": _fill(str(spec.get("scenario_cn") or ""), values),
        "prompt_source": task_spec_source(),
        "brief_includes": str(spec.get("brief_includes") or BRIEF_COUNTS),
        "brief": _brief(graph, spec, must_have),
        "must_have": must_have,
        "must_have_source": "auto_from_project",
        "must_have_confirmed": False,
        "needs_review": True,
        "required_relations": [],
        "required_edge_cases": [],
        "forbidden_merges": [],
        "acceptable_alternatives": [],
        # 权重数值只在教师视图出现（§10.5）；留空表示「用词典里的默认权重」
        "rubric_weights": {},
        "order": index,
    }


def _seed_task(graph: Dict[str, Any], seed: Dict[str, Any], index: int) -> Dict[str, Any]:
    level = str(seed.get("level") or _level_from_graph(graph))
    type_key = str(seed.get("type") or (level_types(level) or ["module_split"])[0])
    spec = types_config().get(type_key) or {}
    minimum, maximum = _level_module_range(graph, level)
    meta = _level_label(graph, level)
    project_name = str(graph.get("project_name") or graph.get("project_id") or "本项目")

    must_have: List[Dict[str, Any]] = []
    for item in seed.get("must_have") or []:
        if not isinstance(item, dict):
            continue
        must_have.append(
            {
                "key": str(item.get("key") or item.get("name_cn") or ""),
                "name_cn": str(item.get("name_cn") or ""),
                "aliases": [str(alias) for alias in (item.get("aliases") or [])],
                "cluster": str(item.get("cluster") or ""),
                "verb_class": str(item.get("verb_class") or ""),
                "verb_cn": str(item.get("verb_cn") or ""),
                "entity": str(item.get("entity") or ""),
                "entity_cn": str(item.get("entity_cn") or ""),
                "related_flow": str(item.get("related_flow") or ""),
                "source": "teacher_seed",
            }
        )

    values = {
        "project_name": project_name,
        "level": level,
        "level_label": meta.get("label") or "",
        "level_desc": meta.get("desc") or "",
        "capability_count": len(must_have),
        "domain_count": len({str(item.get("entity") or "") for item in must_have}),
        "flow_count": len(graph.get("flows") or []),
        "flow_names": _flow_names(graph, 5),
        "module_count_min": minimum if minimum is not None else 1,
        "module_count_max": maximum if maximum is not None else "不限",
    }

    task_id = str(seed.get("task_id") or f"dt_{graph.get('project_id') or 'project'}_{level}_{type_key}")
    weights = seed.get("rubric_weights") if isinstance(seed.get("rubric_weights"), dict) else {}
    return {
        "task_version": TASK_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "contract_version": CONTRACT_VERSION,
        "task_id": task_id,
        "project_id": str(graph.get("project_id") or ""),
        "project_name": project_name,
        "source_hash": str(graph.get("source_hash") or ""),
        "level": level,
        "level_label": meta.get("label") or "",
        "level_desc": meta.get("desc") or "",
        "type": type_key,
        "type_name_cn": str(spec.get("name_cn") or type_key),
        "goal_cn": str(spec.get("goal_cn") or ""),
        "prompt_cn": _fill(str(seed.get("prompt_cn") or spec.get("prompt_cn") or ""), values),
        "scenario_cn": _fill(str(seed.get("scenario_cn") or spec.get("scenario_cn") or ""), values),
        "prompt_source": teacher_seed_source(),
        "brief_includes": str(spec.get("brief_includes") or BRIEF_COUNTS),
        "brief": _brief(graph, spec, must_have),
        "must_have": must_have,
        "must_have_source": "teacher_seed",
        "must_have_confirmed": str(seed.get("review_status") or "") == "confirmed",
        "needs_review": str(seed.get("review_status") or "") != "confirmed",
        "required_relations": [dict(item) for item in (seed.get("required_relations") or []) if isinstance(item, dict)],
        "required_edge_cases": [str(item) for item in (seed.get("required_edge_cases") or []) if str(item or "").strip()],
        "forbidden_merges": [dict(item) for item in (seed.get("forbidden_merges") or []) if isinstance(item, dict)],
        "acceptable_alternatives": [
            dict(item) for item in (seed.get("acceptable_alternatives") or []) if isinstance(item, dict)
        ],
        "rubric_weights": {str(key): float(value) for key, value in weights.items()} if weights else {},
        "order": index,
    }


def full_tasks(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    """该项目的**完整版**任务清单（含 must_have 与权重，只给服务端与教师视图）。"""
    graph = graph if isinstance(graph, dict) else {}
    project_id = str(graph.get("project_id") or "")
    seeds = teacher_seed_tasks(project_id)
    tasks: List[Dict[str, Any]] = []
    if seeds:
        for index, seed in enumerate(seeds):
            task = _seed_task(graph, seed, index)
            if task:
                tasks.append(task)
        if tasks:
            return tasks

    level = _level_from_graph(graph)
    for index, type_key in enumerate(level_types(level)):
        task = _auto_task(graph, level, type_key, index)
        if task:
            tasks.append(task)
    return tasks


def resolve_task(graph: Dict[str, Any], task_id: Any) -> Optional[Dict[str, Any]]:
    """按 ``task_id`` 取完整版任务；取不到返回 ``None``（调用方显式报 404，不许静默降级）。"""
    key = str(task_id or "").strip()
    tasks = full_tasks(graph)
    if not key:
        return tasks[0] if tasks else None
    for task in tasks:
        if str(task.get("task_id")) == key:
            return task
    return None


# ============================================================
# 学生视图 / 教师视图
# ============================================================

def student_view(task: Dict[str, Any]) -> Dict[str, Any]:
    """学生视图：**不含** must_have 全文、不含权重数值、不含必备依赖与禁止合并项。"""
    brief = task.get("brief") or {}
    counts = brief.get("counts") or {}
    view: Dict[str, Any] = {
        "task_version": task.get("task_version"),
        "algorithm_version": task.get("algorithm_version"),
        "contract_version": task.get("contract_version"),
        "task_id": task.get("task_id"),
        "project_id": task.get("project_id"),
        "project_name": task.get("project_name"),
        "source_hash": task.get("source_hash"),
        "level": task.get("level"),
        "level_label": task.get("level_label"),
        "level_desc": task.get("level_desc"),
        "type": task.get("type"),
        "type_name_cn": task.get("type_name_cn"),
        "goal_cn": task.get("goal_cn"),
        "prompt_cn": task.get("prompt_cn"),
        "scenario_cn": task.get("scenario_cn"),
        "brief": {
            "mode": brief.get("mode"),
            "text_cn": brief.get("text_cn"),
            "items": list(brief.get("items") or []),
            "counts": {
                "must_have": int(counts.get("must_have") or 0),
                "domains": int(counts.get("domains") or 0),
                "flows": int(counts.get("flows") or 0),
            },
        },
        "must_have_count": len(task.get("must_have") or []),
        "needs_review": bool(task.get("needs_review")),
        "must_have_source": str(task.get("must_have_source") or ""),
        "dimension_names": [str(item.get("name_cn") or item.get("key")) for item in load_lexicon("design_dimensions").get("dimensions") or []],
        "caveats": [
            "本任务是**设计任务**：没有唯一标准答案，系统按六维结构信号评审，"
            "不判断你的设计「对不对」（README §4 阶段四 / 阶段五）。",
            "必备能力清单**不下发**给你；系统只会告诉你「本次有几项必备能力」，"
            "以及按任务类型给出的需求简报。",
        ],
    }
    if task.get("needs_review"):
        view["caveats"].append(
            "本任务的必备能力清单由本项目图谱自动提炼（auto_from_project），"
            "**尚未经教师确认**：清单本身可能不准，教师审核后会更新。"
        )
    else:
        view["caveats"].append("本任务的必备能力清单来自教师审核过的任务种子（teacher_seed）。")
    return view


def build_design_task(
    graph: Dict[str, Any],
    task_id: Any = None,
    teacher_mode: bool = False,
) -> Optional[Dict[str, Any]]:
    """取一个设计任务：``teacher_mode=True`` 给完整版（含 must_have / 权重），否则给学生视图。

    :returns: 任务对象；``task_id`` 不存在时返回 ``None``（调用方显式 404）
    """
    task = resolve_task(graph, task_id)
    if task is None:
        return None
    return dict(task) if teacher_mode else student_view(task)


def list_design_tasks(graph: Dict[str, Any]) -> Dict[str, Any]:
    """任务清单（学生视图口径）：UI 的任务下拉框用这一份。"""
    graph = graph if isinstance(graph, dict) else {}
    views = [student_view(task) for task in full_tasks(graph)]
    return {
        "algorithm_version": ALGORITHM_VERSION,
        "task_version": TASK_VERSION,
        "contract_version": CONTRACT_VERSION,
        "project_id": str(graph.get("project_id") or ""),
        "source_hash": str(graph.get("source_hash") or ""),
        "level": _level_from_graph(graph),
        "default_task_id": str(views[0]["task_id"]) if views else "",
        "tasks": [
            {
                "task_id": item["task_id"],
                "type": item["type"],
                "type_name_cn": item["type_name_cn"],
                "level": item["level"],
                "goal_cn": item["goal_cn"],
                "must_have_count": item["must_have_count"],
                "needs_review": item["needs_review"],
                "must_have_source": item["must_have_source"],
            }
            for item in views
        ],
        "counts": {"tasks": len(views)},
        "caveats": [
            "任务类型按项目复杂度级别给出（README §9.1 的分级表），题干预设在 "
            "engine/lexicon/design_tasks.json（教师可改，不用改代码）。",
            "任务清单里**不含**必备能力全文与评分权重（README §10.5 的字段可见性矩阵）。",
        ],
    }
