"""RubricEngine：六维评审（README §9.2 的可计算定义）。

这是整个培训功能里**最容易做假的部分**，所以它的每一条结论都必须能追溯到一个结构信号：

    学生的设计（design_submission）
      │
      ├─ matcher.match_modules           → 必备能力 ↔ 模块 的三分类匹配
      ├─ graph_checks.analyze_graph      → 环 / 孤岛 / 悬空边 / 层级 / 声明与画线是否自洽
      ├─ alternatives.evaluate_alternatives → 可接受替代结构 / 禁止合并项
      ▼
    rubric（本模块）：六维 → 每一维 = 若干信号 + 分数
      ▼
    feedback.render                     → 信号码 → 中文模板（唯一文案来源）

五条硬规则（README §18 优先级 3 与§9.2 原文，全部可被脚本检查）
==============================================================
1. **算不出来的维度返回 ``not_evaluated``，不许填 0**：``score`` 为 ``null``，
   附 ``reason``，且**不参与权重归一化**（不是按 0 分算进总分）。
   唯一的例外是第 5 维：README §9.2 明确写「未填 → 按 0 计但标注 ``not_filled``」——
   那是「学生还没填」，不是「引擎算不出来」，两者必须严格区分，
   所以第 5 维返回 ``status: evaluated`` + ``score: 0.0`` + ``not_filled: true``。
2. **「未识别」与「未覆盖」严格区分**：``unrecognized``（学生画了、但没对上必备能力）
   与 ``missing``（必备能力没有承担者）是两张清单，措辞都不许定罪（见 ``matcher``）。
3. **第 6 维只衡量「理由可核查性」，不衡量「正确性」**：只查「引用的名字在不在图上」
   「有没有引用规则或状态」「声明与画线是否自洽」「字数是否在合理区间」，
   绝不判断「理由说得对不对」。
4. **反馈必须是「信号码 → 中文模板」的纯函数映射**：报告里的 ``issues`` 恒等于
   ``feedback.render_issues(signals)`` 的输出（测试逐条断言这条恒等式）。
5. **确定性**：无随机、无网络、无 LLM、无时间依赖；同一份输入两次调用逐字节一致；
   输出带 ``algorithm_version`` + ``source_hash``。

做不到的事（写出来，不让 UI 假装做到了）
======================================
- **不做语义理解**：模块名与必备能力靠词表匹配（exact / contains / bigram+token），
  必然有假阴性 —— 所以缺项文案写的是「未在设计中识别到」，而不是「你漏了」；
- **不判「哪个设计更好」**：六维之外的偏好（优雅、可扩展的直觉）不进入分数；
- **不判「学生是不是理解了业务」**：那是教师与答辩环节的事（纪律：规则引擎判事实，
  教师判语义，LLM 只做映射与润色）；
- **不做中文分词**：列不出「你提到的、词表里没有的名字」。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence, Tuple

from engine.lexicon import lexicon_source, load_lexicon
from engine.teaching import coverage as cov

from . import alternatives as alt_mod
from . import feedback as fb
from . import graph_checks as gc
from . import matcher as matcher_mod
from . import submission as sub_mod

__all__ = [
    "ALGORITHM_VERSION",
    "REPORT_VERSION",
    "CONTRACT_VERSION",
    "SCORING",
    "DIMENSION_KEYS",
    "evaluate_design",
    "report_signature",
]

#: 产物版本（纪律：每个产物带 algorithm_version；README §9.2 的输出契约写的是 rubric-1.0）
ALGORITHM_VERSION = "rubric-1.0"
REPORT_VERSION = "1.0"
CONTRACT_VERSION = "1.0"

#: 本阶段有分数（六维加权），这与阶段一 / 二的 ``coverage_only`` 是**两回事**：
#: 阶段一 / 二不打分，设计层是六维评审。报告里如实写明，避免把两者混为一谈。
SCORING = "rubric_six_dimensions"

DIMENSION_KEYS = ("coverage", "clarity", "hierarchy", "dependency", "edge_case", "rationale")

#: 第 5 维「未填」时的分数（README §9.2：按 0 计但标注 not_filled）
NOT_FILLED_SCORE = 0.0

#: 必备能力的 related_flow 查不到时的降级短语（不留空括号）
RELATED_FLOW_FALLBACK = "这条能力所在的业务流程"


# ============================================================
# 词典配置
# ============================================================

def _dimension_specs() -> List[Dict[str, Any]]:
    data = load_lexicon("design_dimensions")
    specs = [item for item in (data.get("dimensions") or []) if isinstance(item, dict)]
    return specs


def _scoring_config() -> Dict[str, Any]:
    return load_lexicon("design_dimensions").get("scoring") or {}


def _penalty_table(dimension_key: str) -> Dict[str, Dict[str, Any]]:
    table = _scoring_config().get("penalties") or {}
    entries = table.get(dimension_key) or {}
    return {str(key): dict(value) for key, value in entries.items() if isinstance(value, dict)}


def _ratio_weights() -> Dict[str, Dict[str, Any]]:
    table = (_scoring_config().get("penalties") or {}).get("_ratio_signals") or {}
    return {str(key): dict(value) for key, value in table.items() if isinstance(value, dict)}


def _round(value: float) -> float:
    digits = int(_scoring_config().get("round_digits") or 1)
    return round(float(value), digits)


def dimension_spec_source() -> str:
    """六维配置的来源路径（排查「权重到底用的哪份」用）。"""
    return lexicon_source("design_dimensions")


def _dimension_meta(key: str) -> Dict[str, Any]:
    for spec in _dimension_specs():
        if str(spec.get("key")) == key:
            return spec
    return {"key": key, "name_cn": key, "weight": 0.0, "not_evaluated_reason_cn": ""}


# ============================================================
# 信号与扣分
# ============================================================

def _signal(code: str, dimension: str, params: Optional[Dict[str, Any]] = None, penalty: float = 0.0) -> Dict[str, Any]:
    """构造一个信号（含它自己扣了多少分 —— 「这一分是怎么来的」必须能一眼看穿）。"""
    return {
        "code": str(code),
        "dimension": str(dimension),
        "params": dict(params or {}),
        "penalty": _round(penalty),
    }


def _clamp_score(value: float) -> float:
    return _round(max(0.0, min(100.0, float(value))))


def _apply_penalties(
    signals: List[Dict[str, Any]],
    dimension_key: str,
    base: Optional[float] = None,
) -> Tuple[float, float]:
    """给每个信号写上它自己的扣分，返回 ``(这一维的分数, 总扣分)``。

    两种信号：

    - **按次扣分**（词典里给了 ``per`` / ``cap``）：每次触发扣 ``per``，同码累计不超过 ``cap``；
    - **绝对扣分**（信号自带 ``penalty`` 且标了内部标记 ``_absolute``）：用于比例类与
      「超出多少个就扣多少」的信号，扣分由 rubric 算好（例如 ``扣分 = 权重 × 未命中比例``）。
      内部标记在输出前会被剥掉（内部实现标记不许进学生视图）。
    """
    if base is None:
        base = float(_scoring_config().get("base") or 100.0)
    table = _penalty_table(dimension_key)
    used: Dict[str, float] = {}
    total = 0.0
    for item in signals:
        code = str(item.get("code"))
        if item.get("_absolute"):
            value = float(item.get("penalty") or 0.0)
            item["penalty"] = _round(value)
            total += value
            continue
        config = table.get(code)
        if not config:
            item["penalty"] = 0.0
            continue
        per = float(config.get("per") or 0.0)
        cap = float(config.get("cap") or 0.0)
        already = used.get(code, 0.0)
        allowed = max(0.0, cap - already) if cap else per
        take = min(per, allowed)
        used[code] = already + take
        item["penalty"] = _round(take)
        total += take
    return _clamp_score(base - total), _round(total)


def _ratio_penalty(code: str, miss_ratio: float) -> float:
    """命中率类信号：扣分 = 权重 × 未命中比例。"""
    config = _ratio_weights().get(code) or {}
    weight = float(config.get("weight") or 0.0)
    ratio = max(0.0, min(1.0, float(miss_ratio)))
    return _round(weight * ratio)


def _active_signals(signals: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """清洗信号：去掉内部标记（``_`` 前缀）与空码，供渲染与输出。

    纪律：内部实现标记**不许进学生视图**（README §6.2 / §10.5），
    所以 ``_absolute`` 这类只在计算过程中存在的键必须在这里剥掉。
    """
    out: List[Dict[str, Any]] = []
    for item in signals:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "")
        if not code:
            continue
        clean = {key: value for key, value in item.items() if not str(key).startswith("_")}
        out.append(clean)
    return out


def _dimension(
    key: str,
    status: str,
    score: Optional[float],
    findings: List[str],
    signals: List[Dict[str, Any]],
    reason: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """组装一维的结果（``issues`` 由信号渲染而来 —— 两者不是两份数据）。"""
    meta = _dimension_meta(key)
    active = _active_signals(signals)
    payload: Dict[str, Any] = {
        "key": key,
        "name": str(meta.get("name_cn") or key),
        "weight": float(meta.get("weight") or 0.0),
        "status": status,
        "score": None if score is None else _round(score),
        "definition_cn": str(meta.get("definition_cn") or ""),
        "findings": list(findings),
        "issues": fb.render_issues(active),
        "signals": active,
    }
    if status != "evaluated":
        payload["reason"] = reason or str(meta.get("not_evaluated_reason_cn") or "")
    if extra:
        payload.update(extra)
    return payload


# ============================================================
# 任务侧的小工具
# ============================================================

def _task_must_have(task: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [item for item in (task.get("must_have") or []) if isinstance(item, dict)]


def _modules_are_blank(modules: Sequence[Dict[str, Any]]) -> bool:
    """学生是否**一张卡片都没填**（只画了框）。"""
    for module in modules:
        if str(module.get("objective") or "").strip():
            return False
        for field in ("inputs", "outputs", "does_not", "business_rules", "state_changes", "exceptions"):
            if module.get(field):
                return False
    return True


def _combined_text(modules: Sequence[Dict[str, Any]], rationale: str) -> str:
    """把学生写下的所有自由文本拼成一段（用于词族 / 边界的词表匹配）。"""
    chunks: List[str] = [str(rationale or "")]
    for module in modules:
        chunks.append(str(module.get("name") or ""))
        chunks.append(str(module.get("objective") or ""))
        for field in ("does_not", "business_rules", "state_changes", "exceptions", "inputs", "outputs"):
            value = module.get(field)
            if isinstance(value, list):
                chunks.extend(str(item) for item in value)
            elif value:
                chunks.append(str(value))
    return " ".join(chunk for chunk in chunks if chunk)


def _word_families() -> Dict[str, Any]:
    return load_lexicon("design_words")


# ============================================================
# 第 1 维 · 核心需求覆盖度
# ============================================================

def _dim_coverage(task: Dict[str, Any], match: Dict[str, Any]) -> Dict[str, Any]:
    counts = match["counts"]
    total = int(counts["must_have"])
    matched = int(counts["matched"])
    signals: List[Dict[str, Any]] = []

    if total == 0:
        return _dimension(
            "coverage",
            "not_evaluated",
            None,
            ["本任务没有必备能力清单，覆盖度无法计算。"],
            [],
            extra={"counts": counts},
        )

    score = _round(100.0 * matched / total)
    matched_names = [str(item.get("name_cn") or item.get("key")) for item in match["matched"]]
    findings = [
        f"已覆盖 {matched}/{total} 项必备能力"
        + ("：" + "、".join(matched_names) if matched_names else "（一项都没有识别到）"),
    ]
    for entry in match["missing"]:
        related_flow = str(entry.get("related_flow") or "") or RELATED_FLOW_FALLBACK
        signals.append(
            _signal(
                "COVERAGE_MISSING",
                "coverage",
                {"name": str(entry.get("name_cn") or entry.get("key")), "related_flow": related_flow},
            )
        )
    for module in match["unrecognized_modules"]:
        signals.append(
            _signal("COVERAGE_UNRECOGNIZED", "coverage", {"module": str(module.get("name") or module.get("module_id"))})
        )

    if match["unrecognized_modules"]:
        findings.append(
            f"另有 {len(match['unrecognized_modules'])} 个模块没有对应到任何必备能力，"
            "它们**不计入覆盖度**，需人工确认是命名不同还是承担了清单之外的需求。"
        )
    return _dimension("coverage", "evaluated", score, findings, signals, extra={"counts": counts})


# ============================================================
# 第 2 维 · 模块职责清晰度
# ============================================================

def _matched_clusters(match: Dict[str, Any], module_id: str) -> List[str]:
    clusters: List[str] = []
    for entry in match.get("module_hits") or []:
        if str(entry.get("module_id")) != str(module_id):
            continue
        for hit in entry.get("matched_must_have") or []:
            cluster = str(hit.get("cluster") or "")
            if cluster and cluster not in clusters:
                clusters.append(cluster)
    return clusters


def _matched_pairs(match: Dict[str, Any], module_id: str) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    for entry in match.get("module_hits") or []:
        if str(entry.get("module_id")) != str(module_id):
            continue
        for hit in entry.get("matched_must_have") or []:
            verb = str(hit.get("verb_cn") or hit.get("verb_class") or "")
            entity = str(hit.get("entity") or "")
            if verb or entity:
                pairs.append((verb, entity))
    return pairs


def _cluster_cn(cluster_key: str) -> str:
    clusters = load_lexicon("clusters").get("clusters") or {}
    entry = clusters.get(cluster_key) if isinstance(clusters, dict) else None
    if isinstance(entry, dict) and entry.get("cn"):
        return str(entry["cn"])
    return cluster_key


def _dim_clarity(task: Dict[str, Any], match: Dict[str, Any], modules: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    if not modules or _modules_are_blank(modules):
        return _dimension(
            "clarity",
            "not_evaluated",
            None,
            ["学生没有填写任何卡片内容（目标、边界、输入输出全为空），职责清晰度无法计算。"],
            [],
        )

    scoring = _scoring_config()
    threshold = 0
    try:
        threshold = int(load_lexicon("clusters").get("overload_threshold") or 3)
    except (TypeError, ValueError):
        threshold = 3
    if threshold <= 0:
        threshold = 3
    coarse_ratio = float(scoring.get("coarse_ratio") or 4.0)

    signals: List[Dict[str, Any]] = []
    findings: List[str] = []

    # ① 「不负责什么」空值率
    no_boundary = [m for m in modules if not m.get("does_not")]
    if no_boundary:
        signals.append(
            _signal("CLARITY_NO_BOUNDARY", "clarity", {"n": len(no_boundary)})
        )

    # ② 职责过载：一个模块覆盖 ≥ threshold 个能力簇
    overloaded: List[Tuple[str, List[str]]] = []
    for module in modules:
        clusters = _matched_clusters(match, str(module.get("module_id")))
        if len(clusters) >= threshold:
            overloaded.append((str(module.get("name") or module.get("module_id")), clusters))
    for name, clusters in overloaded:
        signal = _signal(
            "CLARITY_OVERLOADED",
            "clarity",
            {
                "module": name,
                "clusters": "、".join(_cluster_cn(cluster) for cluster in clusters),
                "suggest": "、".join(f"{_cluster_cn(cluster)}类模块" for cluster in clusters),
            },
        )
        signals.append(signal)

    # ③ 职责重叠：两个模块覆盖同一 (动词, 对象)
    overlaps: List[Tuple[str, str, str, str]] = []
    module_list = list(modules)
    for i in range(len(module_list)):
        for j in range(i + 1, len(module_list)):
            left = module_list[i]
            right = module_list[j]
            left_pairs = set(_matched_pairs(match, str(left.get("module_id"))))
            right_pairs = set(_matched_pairs(match, str(right.get("module_id"))))
            shared = [pair for pair in left_pairs if pair in right_pairs]
            for verb, entity in sorted(shared):
                overlaps.append(
                    (
                        str(left.get("name") or left.get("module_id")),
                        str(right.get("name") or right.get("module_id")),
                        verb,
                        entity,
                    )
                )
    for a, b, verb, entity in overlaps:
        signals.append(_signal("CLARITY_OVERLAP", "clarity", {"a": a, "b": b, "verb": verb, "entity": entity}))

    # ④ 粒度过粗：模块数 : 覆盖能力数 ≥ 1:coarse_ratio
    covered = int(match["counts"]["matched"])
    module_count = len(modules)
    if module_count and covered and covered / module_count >= coarse_ratio:
        signals.append(
            _signal(
                "CLARITY_TOO_COARSE",
                "clarity",
                {"modules": module_count, "covered": covered, "ratio": _round(covered / module_count)},
            )
        )

    score, penalty = _apply_penalties(signals, "clarity")
    findings.append(
        f"本维度从 {int(float(scoring.get('base') or 100.0))} 分起算，"
        f"按下列信号逐项扣分，共扣 {_round(penalty)} 分。"
    )
    findings.append(
        f"判定口径：一个模块覆盖 ≥ {threshold} 个能力簇即为「职责过载」；"
        f"模块数与已覆盖能力数之比 ≥ 1:{coarse_ratio:g} 即为「粒度过粗」。"
    )
    if not no_boundary:
        findings.append("所有模块都填写了「不负责什么」——这一项没有扣分。")

    return _dimension(
        "clarity",
        "evaluated",
        score,
        findings,
        signals,
        extra={
            "counts": {"no_boundary": len(no_boundary), "overloaded": len(overloaded), "overlaps": len(overlaps)},
            "deduction": penalty,
        },
    )


# ============================================================
# 第 3 维 · 层级结构合理性
# ============================================================

def _level_range(graph: Dict[str, Any], level: str) -> Dict[str, Any]:
    """从图谱自己的 ``complexity.thresholds`` 推出该级别的一级模块推荐区间。

    同一份定义只允许存在一处：推荐区间**不在这里写死**，全部来自复杂度分级引擎。
    """
    thresholds = ((graph.get("complexity") or {}).get("thresholds")) or []
    thresholds = [item for item in thresholds if isinstance(item, dict)]
    level = str(level or "")
    for index, item in enumerate(thresholds):
        if str(item.get("level")) != level:
            continue
        maximum = item.get("max_domains")
        previous = None
        if index > 0:
            previous = thresholds[index - 1].get("max_domains")
        minimum = 1 if previous is None else int(previous) + 1
        return {
            "level": level,
            "min": minimum,
            "max": None if maximum is None else int(maximum),
            "label": str(item.get("label") or ""),
        }
    return {"level": level, "min": None, "max": None, "label": ""}


def _dim_hierarchy(graph: Dict[str, Any], task: Dict[str, Any], modules: Sequence[Dict[str, Any]], checks: Dict[str, Any]) -> Dict[str, Any]:
    scoring = _scoring_config()
    max_depth_allowed = int(scoring.get("max_depth") or 3)
    hint_modules = int(scoring.get("flat_group_hint_modules") or 8)

    has_parent = any(m.get("parent_id") for m in modules)
    if len(modules) <= 1 or not has_parent:
        signal_list = [
            _signal("HIERARCHY_FLAT", "hierarchy", {"modules": len(modules), "hint_modules": hint_modules})
        ]
        return _dimension(
            "hierarchy",
            "not_evaluated",
            None,
            [
                "所有模块都在同一层级（没有父子关系），按 README §9.2 的口径："
                "**降为「结构简化」提示，不给负分**，本维度不参与权重归一化。"
            ],
            signal_list,
        )

    signals: List[Dict[str, Any]] = []
    findings: List[str] = []
    level = str(task.get("level") or graph.get("level") or "")
    span = _level_range(graph, level)
    primary = sum(1 for m in modules if not m.get("parent_id"))

    if span.get("min") is not None:
        over = 0
        if span.get("max") is not None and primary > int(span["max"]):
            over = primary - int(span["max"])
        elif primary < int(span["min"]):
            over = int(span["min"]) - primary
        if over:
            table = _penalty_table("hierarchy").get("HIERARCHY_COUNT_OUT_OF_RANGE") or {}
            per = float(table.get("per") or 5.0)
            cap = float(table.get("cap") or 20.0)
            signal = _signal(
                "HIERARCHY_COUNT_OUT_OF_RANGE",
                "hierarchy",
                {
                    "primary": primary,
                    "min": span["min"],
                    "max": span["max"] if span.get("max") is not None else "不限",
                    "level": level,
                    "level_label": span.get("label") or "",
                    "excess": over,
                },
            )
            signal["penalty"] = _round(min(cap, per * over))
            signal["_absolute"] = True
            signals.append(signal)
        findings.append(
            f"一级模块 {primary} 个；本项目级别 {level} 的常见区间来自该项目的复杂度分级"
            f"（{span.get('min')}–{span.get('max') if span.get('max') is not None else '不限'}）。"
        )
    else:
        findings.append(
            f"图谱里没有 {level} 的复杂度阈值记录，一级模块数量这一项**本轮未评估**"
            "（不编一个区间出来）。"
        )

    if int(checks.get("max_depth") or 0) > max_depth_allowed:
        signals.append(
            _signal(
                "HIERARCHY_TOO_DEEP",
                "hierarchy",
                {"depth": int(checks["max_depth"]), "max_depth": max_depth_allowed},
            )
        )

    children = checks.get("children") or []
    if children:
        detail = "、".join(f"{item['module_id']} 挂 {item['children']} 个" for item in children[:6])
        findings.append(f"子节点分布：{detail}" + ("（只列前 6 个）" if len(children) > 6 else ""))

    score, penalty = _apply_penalties(signals, "hierarchy")
    return _dimension(
        "hierarchy",
        "evaluated",
        score,
        findings,
        signals,
        extra={
            "counts": {"primary_modules": primary, "max_depth": int(checks.get("max_depth") or 0)},
            "deduction": penalty,
        },
    )


# ============================================================
# 第 4 维 · 依赖与流程完整性
# ============================================================

def _required_relation_hits(task: Dict[str, Any], match: Dict[str, Any], checks: Dict[str, Any]) -> Dict[str, Any]:
    """必备依赖关系命中率（只有教师种子给出 ``required_relations`` 时才算）。"""
    required = [item for item in (task.get("required_relations") or []) if isinstance(item, dict)]
    if not required:
        return {"available": False, "total": 0, "matched": 0, "missing": []}

    adjacency = checks["graph"]["adjacency"]
    names = {str(item.get("key")): str(item.get("name_cn") or item.get("key")) for item in _task_must_have(task)}
    matched: List[Dict[str, Any]] = []
    missing: List[Dict[str, Any]] = []
    for item in required:
        left = str(item.get("from_key") or "")
        right = str(item.get("to_key") or "")
        left_modules = {
            str(hit.get("module_id"))
            for entry in match.get("matched") or []
            if str(entry.get("key")) == left
            for hit in entry.get("matched_modules") or []
        }
        right_modules = {
            str(hit.get("module_id"))
            for entry in match.get("matched") or []
            if str(entry.get("key")) == right
            for hit in entry.get("matched_modules") or []
        }
        hit = any(target in (adjacency.get(source) or []) for source in left_modules for target in right_modules)
        record = {
            "from_key": left,
            "to_key": right,
            "from_name_cn": names.get(left, left),
            "to_name_cn": names.get(right, right),
            "reason_cn": str(item.get("reason_cn") or ""),
        }
        (matched if hit else missing).append(record)
    return {"available": True, "total": len(required), "matched": len(matched), "missing": missing}


def _dim_dependency(task: Dict[str, Any], match: Dict[str, Any], checks: Dict[str, Any], modules: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    if not checks.get("edge_count"):
        return _dimension(
            "dependency",
            "not_evaluated",
            None,
            ["学生没有建立任何依赖关系（既没有画线，也没有声明 depends_on），仅报告「未建立依赖关系」。"],
            [_signal("DEP_NOT_FILLED", "dependency", {"modules": len(modules)})],
        )

    signals: List[Dict[str, Any]] = []
    findings: List[str] = []

    for cycle in checks.get("cycles") or []:
        signals.append(_signal("DEP_CYCLE", "dependency", {"path": str(cycle.get("path") or "")}))
    for edge in checks.get("dangling_edges") or []:
        signals.append(
            _signal("DEP_DANGLING_EDGE", "dependency", {"from": str(edge.get("from")), "to": str(edge.get("to"))})
        )
    for node in checks.get("orphans") or []:
        signals.append(
            _signal("DEP_ORPHAN", "dependency", {"module": str(node.get("name") or node.get("module_id"))})
        )

    relations = _required_relation_hits(task, match, checks)
    if relations["available"] and relations["missing"]:
        names = "、".join(f"{item['from_name_cn']} → {item['to_name_cn']}" for item in relations["missing"])
        miss_ratio = 1.0 - (relations["matched"] / relations["total"] if relations["total"] else 0.0)
        signal = _signal(
            "DEP_REQUIRED_MISSING",
            "dependency",
            {"matched": relations["matched"], "total": relations["total"], "names": names},
        )
        signal["penalty"] = _ratio_penalty("DEP_REQUIRED_MISSING", miss_ratio)
        signal["_absolute"] = True
        signals.append(signal)
    if not relations["available"]:
        findings.append(
            "本任务没有教师给出的必备依赖关系清单，因此「必备依赖命中率」这一项**本轮未评估**"
            "（不编一份依赖清单出来）。"
        )
    else:
        findings.append(f"必备依赖关系命中 {relations['matched']}/{relations['total']} 条。")

    flow_designs = [flow for flow in (checks.get("flow_designs") or []) if isinstance(flow, dict)]
    for flow in flow_designs:
        steps = [step for step in (flow.get("steps") or []) if isinstance(step, dict)]
        if steps and not any(step.get("is_state_change") for step in steps):
            signals.append(
                _signal("DEP_FLOW_NOT_REACHING_STATE", "dependency", {"flow": str(flow.get("name_cn") or flow.get("flow_id"))})
            )
    if not flow_designs:
        findings.append(
            "学生没有提交流程设计（flow_designs 为空），因此「主流程是否可达状态更新节点」这一项"
            "**本轮未评估**。"
        )

    score, penalty = _apply_penalties(signals, "dependency")

    findings.append(
        f"结构检查：{checks['counts']['nodes']} 个模块、{checks['counts']['edges']} 条边、"
        f"{checks['counts']['cycles']} 个环、{checks['counts']['orphans']} 个孤岛、"
        f"{checks['counts']['dangling_edges']} 条悬空边；共扣 {penalty} 分。"
    )
    return _dimension(
        "dependency",
        "evaluated",
        score,
        findings,
        signals,
        extra={
            "counts": dict(checks.get("counts") or {}),
            "required_relations": relations,
            "flow_designs_evaluated": len(flow_designs),
            "deduction": penalty,
        },
    )


# ============================================================
# 第 5 维 · 异常与边界情况
# ============================================================

def _dim_edge_case(task: Dict[str, Any], modules: Sequence[Dict[str, Any]], rationale: str) -> Dict[str, Any]:
    scoring = _scoring_config()
    base = float(scoring.get("base") or 100.0)

    declared = [m for m in modules if m.get("exceptions") or m.get("business_rules") or m.get("state_changes")]
    if not declared:
        return _dimension(
            "edge_case",
            "evaluated",
            NOT_FILLED_SCORE,
            [
                "学生没有填写任何异常分支、业务规则或状态变化。"
                "按 README §9.2 的口径：**这一维「未填」按 0 计并标注 not_filled**"
                "（这不是「算不出来」，而是「还没有填」）。"
            ],
            [_signal("EDGE_NOT_FILLED", "edge_case", {})],
            extra={"not_filled": True},
        )

    signals: List[Dict[str, Any]] = []
    findings: List[str] = []

    text = _combined_text(modules, rationale)
    _normalized, compact, tokens = cov.prepare_text(text)

    # ③ 是否出现「失败 / 拒绝 / 回滚 / 异常」词族
    families = _word_families().get("families") or {}
    family_words: List[str] = []
    for key in sorted(families.keys()):
        entry = families[key]
        if isinstance(entry, dict):
            family_words.extend(str(word) for word in (entry.get("words") or []))
    hit_words = [word for word in family_words if cov.key_hit(cov.normalize_text(word), compact, tokens)]
    if not hit_words and family_words:
        signals.append(
            _signal(
                "EDGE_FAMILY_MISSING",
                "edge_case",
                {"words": "、".join(family_words[:6]) + " 等"},
            )
        )
    else:
        findings.append(f"出现了 {len(hit_words)} 个异常 / 边界相关词（例如：{'、'.join(hit_words[:5])}）。")

    # ② 学生卡片 exceptions 非空率
    missing_exceptions = [m for m in modules if not m.get("exceptions")]
    ratio = (len(missing_exceptions) / len(modules)) if modules else 0.0
    if missing_exceptions:
        table = _penalty_table("edge_case").get("EDGE_DECLARED_EMPTY") or {}
        per = float(table.get("per") or 20.0)
        cap = float(table.get("cap") or 20.0)
        signal = _signal(
            "EDGE_DECLARED_EMPTY",
            "edge_case",
            {"missing": len(missing_exceptions), "ratio_percent": _round(ratio * 100)},
        )
        signal["penalty"] = _round(min(cap, per * ratio))
        signal["_absolute"] = True
        signals.append(signal)

    # ① 必备边界命中率（只有教师种子给出 required_edge_cases 时才算）
    required_cases = [str(item) for item in (task.get("required_edge_cases") or []) if str(item or "").strip()]
    if required_cases:
        found = matcher_mod.find_names_in_text(required_cases, text)
        miss_ratio = 1.0 - (len(found) / len(required_cases))
        if len(found) < len(required_cases):
            missing_cases = [case for case in required_cases if case not in found]
            signal = _signal(
                "EDGE_REQUIRED_MISSING",
                "edge_case",
                {"matched": len(found), "total": len(required_cases), "cases": "、".join(missing_cases)},
            )
            signal["penalty"] = _ratio_penalty("EDGE_REQUIRED_MISSING", miss_ratio)
            signal["_absolute"] = True
            signals.append(signal)
        findings.append(f"必备边界情况命中 {len(found)}/{len(required_cases)} 个。")
    else:
        findings.append(
            "本任务没有教师给出的必备边界清单，因此「必备边界命中率」这一项**本轮未评估**；"
            "本维度只按「你自己有没有给出异常与边界」计算。"
        )

    score, penalty = _apply_penalties(signals, "edge_case", base=base)

    findings.append(f"有 {len(declared)}/{len(modules)} 个模块写了异常分支 / 业务规则 / 状态变化；共扣 {penalty} 分。")
    return _dimension(
        "edge_case",
        "evaluated",
        score,
        findings,
        signals,
        extra={
            "not_filled": False,
            "counts": {"modules": len(modules), "declared": len(declared)},
            "deduction": penalty,
        },
    )


# ============================================================
# 第 6 维 · 设计理由与证据（只衡量可核查性）
# ============================================================

def _dim_rationale(task: Dict[str, Any], match: Dict[str, Any], checks: Dict[str, Any], modules: Sequence[Dict[str, Any]], rationale: str) -> Dict[str, Any]:
    if not str(rationale or "").strip():
        return _dimension(
            "rationale",
            "not_evaluated",
            None,
            ["学生没有填写设计理由，无法核查理由与设计是否一致。"],
            [_signal("RATIONALE_NOT_FILLED", "rationale", {})],
        )

    scoring = _scoring_config()
    min_chars = int(scoring.get("rationale_min_chars") or 40)
    signals: List[Dict[str, Any]] = []
    findings: List[str] = [
        "本维度**只衡量「理由可核查性」，不衡量「理由是否正确」**（README §9.2 第 6 维）。"
    ]

    if len(rationale) < min_chars:
        signals.append(_signal("RATIONALE_TOO_SHORT", "rationale", {"chars": len(rationale), "min_chars": min_chars}))

    # ① 引用的名字是否真的在图上：只查「必备能力清单里的名字」（已知词表，不做分词）
    must_have_names = [str(item.get("name_cn") or "") for item in _task_must_have(task) if str(item.get("name_cn") or "")]
    checked_names = must_have_names + [
        str(item.get("name") or "") for item in modules if str(item.get("name") or "")
    ]
    mentioned = matcher_mod.find_names_in_text(checked_names, rationale)
    created = {str(m.get("name") or "") for m in modules}
    unmatched_mentions = [name for name in mentioned if name not in created]
    for name in unmatched_mentions[:6]:
        signals.append(_signal("RATIONALE_UNCHECKABLE", "rationale", {"name": name}))
    if unmatched_mentions:
        findings.append(
            f"理由里提到了 {len(unmatched_mentions)} 个「不在你画的模块里」的名字："
            + "、".join(unmatched_mentions[:5])
        )
    else:
        findings.append("理由里提到的名字都能在图上找到（或没有提到清单里的名字）。")

    # ② 是否引用了 ≥ 1 条规则或状态
    markers = (_word_families().get("rule_markers") or {}).get("words") or []
    _normalized, compact, tokens = cov.prepare_text(_combined_text(modules, rationale))
    hit_markers = [str(word) for word in markers if cov.key_hit(cov.normalize_text(word), compact, tokens)]
    if not hit_markers:
        signals.append(_signal("RATIONALE_NO_RULE_OR_STATE", "rationale", {}))

    # ③ 声明的 depends_on 与画的边是否自洽
    for item in checks.get("declared_vs_drawn") or []:
        signals.append(
            _signal(
                "RATIONALE_DEPENDS_ON_INCONSISTENT",
                "rationale",
                {
                    "module": str(item.get("name") or item.get("module_id")),
                    "declared": "、".join(item.get("declared") or []) or "（无）",
                    "drawn": "、".join(item.get("drawn") or []) or "（无）",
                },
            )
        )
    if checks.get("declared_vs_drawn"):
        findings.append(
            f"有 {len(checks['declared_vs_drawn'])} 个模块的 depends_on 声明与画布上的连线不一致。"
        )

    score, penalty = _apply_penalties(signals, "rationale")
    findings.append(f"设计理由 {len(rationale)} 字（建议不少于 {min_chars} 字）；共扣 {penalty} 分。")
    return _dimension("rationale", "evaluated", score, findings, signals, extra={"deduction": penalty})


# ============================================================
# 汇总
# ============================================================

def _overall(dimensions: Sequence[Dict[str, Any]], task: Dict[str, Any]) -> Dict[str, Any]:
    """权重归一化 + 总分（``not_evaluated`` 的维度**不参与**归一化，也不按 0 算）。"""
    weights_override = task.get("rubric_weights") if isinstance(task.get("rubric_weights"), dict) else {}
    entries: List[Dict[str, Any]] = []
    for dimension in dimensions:
        key = str(dimension.get("key"))
        weight = float(weights_override.get(key, dimension.get("weight") or 0.0))
        entries.append({"key": key, "name": dimension.get("name"), "weight": weight, "dimension": dimension})

    evaluated = [item for item in entries if item["dimension"].get("status") == "evaluated"]
    total_weight = sum(item["weight"] for item in evaluated)
    evaluated_count = len(evaluated)
    total_count = len(entries)

    if not evaluated or total_weight <= 0:
        reasons = [
            str(item["dimension"].get("reason") or "")
            for item in entries
            if str(item["dimension"].get("reason") or "").strip()
        ]
        detail = reasons[0] if reasons else ""
        return {
            "evaluated_dimensions": evaluated_count,
            "total_dimensions": total_count,
            "weights_renormalized": False,
            "overall_score": None,
            "overall_note": (
                "本轮没有任何一维可以计算，因此**不给总分**（不填 0：填 0 会被读成「设计得零分」）。"
                + (f"原因：{detail}" if detail else "")
            ),
            "weights": [],
        }

    weights: List[Dict[str, Any]] = []
    score = 0.0
    for item in evaluated:
        normalized = item["weight"] / total_weight
        weights.append(
            {
                "key": item["key"],
                "name": item["name"],
                "weight": _round(item["weight"]),
                "normalized_weight": round(normalized, 4),
                "score": item["dimension"].get("score"),
            }
        )
        score += float(item["dimension"].get("score") or 0.0) * normalized

    skipped = [
        f"『{item['name']}』（{item['dimension'].get('reason') or '未评估'}）"
        for item in entries
        if item["dimension"].get("status") != "evaluated"
    ]
    note = f"本轮评估覆盖 {evaluated_count}/{total_count} 维。"
    if skipped:
        note += "权重已按比例归一化；" + "、".join(skipped) + " 未参与评分。"
    if weights_override:
        note += "本次使用任务自带的 rubric_weights（教师种子）。"

    return {
        "evaluated_dimensions": evaluated_count,
        "total_dimensions": total_count,
        "weights_renormalized": evaluated_count < total_count,
        "overall_score": _round(score),
        "overall_note": note,
        "weights": weights,
    }


def _task_caveats(task: Dict[str, Any], match: Dict[str, Any]) -> List[str]:
    source = str(task.get("must_have_source") or "")
    lines = [
        "**「未识别」不等于「未覆盖」**：`unrecognized` 是「你画了、但系统没能把它和必备能力对上」"
        "（可能是命名不同），它**不计入覆盖度**，也不当作你漏了；`missing` 才是必备能力没有承担者。",
        "模块名与必备能力靠词表匹配（exact / contains / bigram+token），**词汇匹配必然有假阴性**，"
        "所以文案写的是「未在设计中识别到」，而不是「你漏了」。",
        "**规则引擎判事实，教师判语义**：本报告只说明结构信号，不判断你的设计「对不对」「好不好」；"
        "分数不是对业务能力的结论。",
        "第 6 维只衡量「理由可核查性」，**不衡量理由的正确性**。",
        "**系统不做中文分词**：列不出「你提到的、词表里没有的名字」。",
        "算不出来的维度返回 `not_evaluated` 并附原因，**不填 0**；唯一的例外是「异常与边界」维"
        "（未填按 0 计并标注 `not_filled`，因为那是「还没有填」而不是「算不出来」）。",
    ]
    if source == "auto_from_project":
        lines.append(
            "**本任务的必备能力清单由本项目图谱自动提炼（`source = auto_from_project`），"
            "尚未经教师确认**：清单本身可能不准，且存在「照着本项目现有结构抄」的捷径 ——"
            "教师提供 `engine/lexicon/design_tasks.seed.json` 后，任务来源会变成 `teacher_seed`。"
        )
    if match["counts"]["unrecognized_modules"]:
        lines.append(
            f"有 {match['counts']['unrecognized_modules']} 个模块没有对应到任何必备能力，"
            "请教师 / 学生确认是命名不同还是承担了清单之外的需求。"
        )
    return lines


def _no_submission_dimensions() -> List[Dict[str, Any]]:
    """**画布上一个模块都没有**时的六维结果：全部 ``not_evaluated``，一个分都不给。

    这一条是刻意的（跑起来才发现的问题）：如果照常计算，覆盖度会得 0 分、
    「异常与边界」会因为「未填」得 0 分，于是总分变成 0 —— 而「没交设计」被读成
    「设计得零分」是完全不同的两件事。README §5 的纪律是「算不出来不许填 0」，
    「还没交」同样不是 0 分。所以这里六维全 ``not_evaluated``、
    ``overall_score = null``，并写明「请先在画布上添加模块」。
    """
    reason = "提交里没有任何模块（画布是空的），本轮不对任何一维评分。"
    return [
        _dimension(key, "not_evaluated", None, [reason], [], reason=reason)
        for key in DIMENSION_KEYS
    ]


def evaluate_design(
    graph: Dict[str, Any],
    task: Dict[str, Any],
    submission: Any,
) -> Dict[str, Any]:
    """六维评审：``(业务图谱, 设计任务, 学生的 design_submission)`` → 评审报告。

    :param graph: 业务图谱（用于取复杂度阈值；也是 ``source_hash`` 的来源）
    :param task: **完整版**设计任务（含 ``must_have`` / ``required_relations`` 等，
                 由 ``task_builder.build_design_task(..., teacher_mode=True)`` 或
                 ``task_builder.resolve_task`` 给出）
    :param submission: 学生提交（原始 JSON 即可，内部会归一化）
    :returns: 评审报告（JSON 可序列化、确定性、带 ``algorithm_version``）

    ``submission`` 为空（``{"modules": []}``）时**也返回报告**：本函数是纯函数、不做入口校验，
    「不许空提交」由后端与前端各自把关（与阶段一 / 二的同一条分工）。
    """
    graph = graph if isinstance(graph, dict) else {}
    task = task if isinstance(task, dict) else {}
    normalized = submission if (isinstance(submission, dict) and "modules" in submission and isinstance(submission.get("modules"), list) and "unknown_fields" in submission) else sub_mod.normalize_submission(submission)

    modules = normalized.get("modules") or []
    relations = normalized.get("relations") or []

    structural = sub_mod.structural_issues(normalized)
    match = matcher_mod.match_modules(modules, _task_must_have(task))
    checks = gc.analyze_graph(modules, relations)
    checks["flow_designs"] = normalized.get("flow_designs") or []
    alt_result = alt_mod.evaluate_alternatives(task, match)

    dimensions = _no_submission_dimensions() if not modules else [
        _dim_coverage(task, match),
        _dim_clarity(task, match, modules),
        _dim_hierarchy(graph, task, modules, checks),
        _dim_dependency(task, match, checks, modules),
        _dim_edge_case(task, modules, str(normalized.get("design_rationale") or "")),
        _dim_rationale(task, match, checks, modules, str(normalized.get("design_rationale") or "")),
    ]

    # 结构性问题（重名 / 悬空父模块 / 空提交）先渲染成 issues，
    # 并作为**顶层**清单给出：它们是数据完整性问题，不属于任何一维的质量判断
    structural_signals = [_signal(item["code"], "submission", item.get("params") or {}) for item in structural]
    structural_issues = fb.render_issues(structural_signals)

    overall = _overall(dimensions, task)
    signals: List[Dict[str, Any]] = []
    for dimension in dimensions:
        for item in dimension.get("signals") or []:
            signals.append({"dimension": dimension["key"], **item})
    for item in alt_result.get("violations") or []:
        signals.append(
            _signal("ALT_FORBIDDEN_MERGE", "alternatives", {"a": item["a"], "b": item["b"], "reason": item.get("reason_cn") or "教师给定的禁止合并项"})
        )
    if alt_result.get("accepted"):
        signals.append(
            _signal("ALT_ACCEPTED", "alternatives", {"alternative": alt_result.get("accepted_alternative") or ""})
        )

    alternatives_issues = fb.render_issues(
        [item for item in signals if str(item.get("dimension")) == "alternatives"]
    )

    report: Dict[str, Any] = {
        "report_version": REPORT_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "contract_version": CONTRACT_VERSION,
        "project_id": str(graph.get("project_id") or task.get("project_id") or ""),
        "source_hash": str(graph.get("source_hash") or ""),
        "task_id": str(task.get("task_id") or normalized.get("task_id") or ""),
        "task_type": str(task.get("type") or ""),
        "task_type_name_cn": str(task.get("type_name_cn") or ""),
        "level": str(task.get("level") or graph.get("level") or ""),
        "submission_id": str(normalized.get("submission_id") or ""),
        "iteration": int(normalized.get("iteration") or 1),
        "scoring": SCORING,
        "has_score": True,
        # 权重与扣分表的来源（排查「这份报告到底用的哪份配置」用；与阶段二的
        # question_spec_source 是同一条可追溯性纪律）
        "rubric_spec_source": dimension_spec_source(),
        "evaluated_dimensions": overall["evaluated_dimensions"],
        "total_dimensions": overall["total_dimensions"],
        "weights_renormalized": overall["weights_renormalized"],
        "overall_score": overall["overall_score"],
        "overall_note": overall["overall_note"],
        "weights": overall["weights"],
        "dimensions": dimensions,
        "signals": signals,
        "matching": {
            "algorithm_version": match["algorithm_version"],
            "counts": match["counts"],
            "matched": [
                {"key": item["key"], "name_cn": item["name_cn"], "module_ids": [h["module_id"] for h in item["matched_modules"]]}
                for item in match["matched"]
            ],
            "missing": [{"key": item["key"], "name_cn": item["name_cn"]} for item in match["missing"]],
            "unrecognized_modules": match["unrecognized_modules"],
        },
        "graph_checks": {
            "algorithm_version": checks["algorithm_version"],
            "counts": checks["counts"],
            "cycles": checks["cycles"],
            "orphans": [{"module_id": item["module_id"], "name": item["name"]} for item in checks["orphans"]],
            "dangling_edges": checks["dangling_edges"],
            "declared_vs_drawn": checks["declared_vs_drawn"],
            "max_depth": checks["max_depth"],
            "children": checks["children"],
        },
        "alternatives": alt_result,
        "submission_issues": structural_issues,
        "alternatives_issues": alternatives_issues,
        "submission_warnings": {
            "unknown_fields": list(normalized.get("unknown_fields") or []),
            "truncated": bool(normalized.get("truncated")),
        },
        "caveats": _task_caveats(task, match)
        + ([alt_result["reason_cn"]] if not alt_result.get("available") and alt_result.get("reason_cn") else []),
    }
    return report


def report_signature(report: Dict[str, Any]) -> str:
    """报告的稳定签名（测试用：同一输入两次调用必须一致）。"""
    return json.dumps(report, ensure_ascii=False, sort_keys=True)
