"""阶段二「模块卡片学习」的事实覆盖比对器（培养方案第四章 阶段二）。

学生在阶段二逐张打开模块卡片，用**自己的话**回答五个问题
（解决什么问题 / 接收什么输入 / 输出什么结果 / 改变了什么状态 / 为什么不应该和其他模块合并）。
系统**不打分**，只做一件事：

    把学生写的话，与这张卡片上**已经有人确认过**的字段做事实覆盖比对——
    你提到了卡片上哪些事实、哪些还没提到。

四条纪律（与阶段一完全同源，全部可被脚本检查）
==============================================
1. **不打分**：返回值里没有 ``score`` / ``grade`` / ``correct`` 这类字段，
   只有每个问题的 matched / missed 清单（``scoring = "fact_coverage_only"``）。
2. **无证据不比对**：置信度为 ``unconfirmed``（待教师确认）的字段**不参与比对**，
   该问题进 ``not_comparable`` 并写明原因，且报告里显式给出「该卡片待教师确认」；
   这些字段既不进分子也不进分母。
3. **只有一份命中判定**：归一化、比对键去重、中英文命中规则全部复用
   ``engine/teaching/coverage.py``（``prepare_text`` / ``add_comparison_key`` / ``key_hit``），
   本模块只加一层「问题 → 参与比对的卡片字段」映射。
4. **确定性**：无随机、无网络、无 LLM、无时间依赖；同一份输入两次调用输出逐字节相同。

题目从哪来
==========
五个问题的**文本**和「问题 → 字段」映射都在 ``engine/lexicon/stage_questions.json`` 里
（教学配置，不是业务词）。教师改问法 / 换比对字段不需要改引擎代码，也不需要改前端组件：
前端从 ``build_module_card_task`` 拿题目，自己不认识任何一个问题。

与阶段一不一致的地方（必须写明，不许含糊）
==========================================
- 培养方案第四章阶段二的原话是「学生提到的关键事实是否出现在卡片的 ``verified`` 字段里」。
  本实现的口径是**只有 ``unconfirmed`` 被挡在门外**，``inferred`` / ``from_docstring``
  这类字段**参与**比对，但每个比对键都带 ``origin_confidence``，UI 必须把徽章显示出来。
  理由：阶段一已经是这条口径（``coverage.py`` 的 ``_UNCONFIRMED_TOKENS``），
  **同一个仓库里不允许存在两套「什么算没确认」的判定**。教师想更严，只需把那些字段的
  置信度改成 ``unconfirmed``（或改这份词典的字段映射），不需要改代码。

做不到的事（写出来，不让 UI 假装做到了）
==========================================
- **「提到」不等于「理解」**：命中只说明学生写到了那个词；抄卡片也能命中，
  规则引擎分不出「理解了」和「照着抄」——这一条写进 ``caveats``。
- **不做中文分词**：无法给出「你额外提到的、卡片上没有的东西」。
- **规则条件类比对键是代码表达式**（引擎只给代码、不编语义），中文表述的答案通常命中不了，
  因此这类键未命中**不构成答错的证据**——这一条也写进 ``caveats``。
- **本引擎里「输入 / 输出 / 状态变化」同源**（都来自状态读写追踪），
  三个问题的比对键可能重叠；``build_module_card_task`` 的输出与报告的 ``caveats``
  都会如实说明，**不为了凑出差异而编造第二份数据**。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from engine.lexicon import lexicon_source, load_lexicon
from engine.teaching import coverage as cov

__all__ = [
    "ALGORITHM_VERSION",
    "REPORT_VERSION",
    "TASK_VERSION",
    "CONTRACT_VERSION",
    "SCORING",
    "STAGE",
    "MAX_ANSWER_CHARS",
    "MAX_TOTAL_CHARS",
    "STATE_WRITE_MARKER",
    "stage_name_cn",
    "answer_prompt",
    "question_spec_source",
    "question_specs",
    "extract_state_path",
    "build_question_targets",
    "build_module_card_task",
    "evaluate_module_card_answers",
]

#: 产物版本（纪律：每个产物带 algorithm_version）
ALGORITHM_VERSION = "card-coverage-1.0"
REPORT_VERSION = "1.0"
TASK_VERSION = "1.0"
CONTRACT_VERSION = "1.0"

#: 阶段标识（与课堂流程的「阶段二」一一对应）
STAGE = "module_card"

#: 本阶段唯一的判定口径：只给事实覆盖清单，不给分数
SCORING = "fact_coverage_only"

#: 词典缺失时的兜底阶段名（正常情况下来自 ``lexicon/stage_questions.json``）
STAGE_NAME_CN_FALLBACK = "模块卡片学习"
ANSWER_PROMPT_FALLBACK = (
    "请用自己的话回答下面五个问题。系统不打分，只做「事实覆盖比对」："
    "看你的回答里提到了这张卡片上哪些已核实的事实，以及哪些没有提到。"
)

#: 每个问题的作答上限与总上限（后端在入口处拦截，这里是第二道闸）
MAX_ANSWER_CHARS = 1000
MAX_TOTAL_CHARS = 4000

#: 状态变化事实的文本里「写入」这一步的标记。
#: 来源：``engine/business_graph/facts.py`` 用 ``f"{symbol} 写入 {attr}"`` 生成状态变化事实；
#: 这里只做**取最后一个标记之后那一段**的解析，解析不出来就退回整条文本当键（见 ``extract_state_path``）。
STATE_WRITE_MARKER = " 写入 "

#: 状态路径长这样：``check_items`` / ``_next_item_id`` / ``data["k"]``
_STATE_PATH_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+|\[[^\]]+\])*$")

#: 卡片字段 → 中文名（用于「为什么没参与比对」的说明；这些是引擎概念，不是业务词）
_FIELD_LABELS: Dict[str, str] = {
    "name": "模块名",
    "objective": "模块目标",
    "business_rules": "业务规则",
    "preconditions": "前置判断",
    "exceptions": "异常分支",
    "inputs": "输入清单",
    "outputs": "输出清单",
    "state_changes": "状态变化",
    "does_not": "「不负责什么」",
    "upstream_modules": "上游模块",
    "downstream_modules": "下游模块",
}

#: 事实型字段 → (比对键来源标识, 中文名)
_FACT_FIELDS: Dict[str, Tuple[str, str]] = {
    "business_rules": ("card_business_rule", "业务规则"),
    "preconditions": ("card_guard", "前置判断"),
    "exceptions": ("card_exception", "异常分支"),
    "state_changes": ("card_state_change", "状态变化"),
}

#: 卡片里引用其它模块的字段
_MODULE_REF_FIELDS: Dict[str, str] = {
    "upstream_modules": "上游模块",
    "downstream_modules": "下游模块",
}


# ============================================================
# 题目配置（来自词典，不在代码里写死）
# ============================================================

def _spec() -> Dict[str, Any]:
    return load_lexicon("stage_questions")


def question_spec_source() -> str:
    """题目词典的来源路径（排查「到底用的是哪份题目配置」用）。"""
    return lexicon_source("stage_questions")


def stage_name_cn() -> str:
    return str(_spec().get("stage_name_cn") or STAGE_NAME_CN_FALLBACK)


def answer_prompt() -> str:
    return str(_spec().get("answer_prompt_cn") or ANSWER_PROMPT_FALLBACK)


def question_specs() -> List[Dict[str, Any]]:
    """五个问题（按配置顺序，保持插入顺序 —— 顺序稳定才有确定性输出）。

    词典缺失 / 损坏时返回空列表：调用方（任务接口）会给出空题目并在 ``caveats`` 里
    如实说明，**不静默编一套题目出来**。
    """
    items = _spec().get("questions") or []
    out: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        question_id = str(item.get("question_id") or "").strip()
        if not question_id:
            continue
        fields = [str(f).strip() for f in (item.get("fields") or []) if str(f or "").strip()]
        out.append(
            {
                "question_id": question_id,
                "text_cn": str(item.get("text_cn") or ""),
                "placeholder_cn": str(item.get("placeholder_cn") or ""),
                "fields": fields,
            }
        )
    return out


# ============================================================
# 卡片读取的小工具
# ============================================================

def _cards_of(graph: Dict[str, Any]) -> Dict[str, Any]:
    cards = (graph or {}).get("module_cards") or {}
    return cards if isinstance(cards, dict) else {}


def _card_of(graph: Dict[str, Any], module_id: str) -> Optional[Dict[str, Any]]:
    card = _cards_of(graph).get(str(module_id))
    return card if isinstance(card, dict) else None


def _domains_of(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [d for d in ((graph or {}).get("domains") or []) if isinstance(d, dict)]


def _domain_of(graph: Dict[str, Any], domain_id: Any) -> Dict[str, Any]:
    for domain in _domains_of(graph):
        if str(domain.get("domain_id")) == str(domain_id):
            return domain
    return {}


def _facts_of(card: Dict[str, Any], field: str) -> List[Dict[str, Any]]:
    value = card.get(field)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]


def _fact_text(fact: Dict[str, Any]) -> str:
    """事实的可比对文本：优先 ``text``（教师/引擎写过的语义），否则退回 ``code``。"""
    text = str(fact.get("text") or "").strip()
    if text:
        return text
    return str(fact.get("code") or "").strip()


def _fact_detail(fact: Dict[str, Any]) -> str:
    """事实出处（项目内相对路径 + 行号区间），UI 要能拿它跳源码。"""
    path = str(fact.get("file") or "")
    start = fact.get("start_line")
    end = fact.get("end_line")
    if not path:
        return ""
    if start is None:
        return path
    if end is None or end == start:
        return f"{path}:{start}"
    return f"{path}:{start}-{end}"


def extract_state_path(code: Any) -> str:
    """从状态变化事实的文本里取出**状态路径**（状态字段名）。

    ``"add_item 写入 items"`` → ``"items"``；取不出来时返回空串（调用方退回整条文本）。
    这是对 ``engine/business_graph/facts.py`` 那句模板的最小解析，
    只认最后一个标记之后的那一段；解析结果还要过 ``_STATE_PATH_RE`` 才算数。
    """
    text = str(code or "")
    if STATE_WRITE_MARKER not in text:
        return ""
    candidate = text.rsplit(STATE_WRITE_MARKER, 1)[-1].strip()
    if _STATE_PATH_RE.match(candidate):
        return candidate
    return ""


def _member_field_confidence(card: Dict[str, Any]) -> Any:
    """成员级字段（输入 / 输出清单）的置信度。

    这些清单来自状态读写追踪（``member_confidence = verified``）。
    取不到就退回卡片自身的置信度；两者都取不到 = 没人确认过 = ``unconfirmed``。
    """
    for key in ("member_confidence", "confidence"):
        value = card.get(key)
        if value is not None and str(value).strip():
            return value
    return "unconfirmed"


# ============================================================
# 问题 → 字段 → 比对键
# ============================================================

def _field_keys(graph: Dict[str, Any], card: Dict[str, Any], field: str) -> Dict[str, Any]:
    """为一个卡片字段建比对键。

    返回 ``{"keys": [...], "status": "...", "reason": "...", "blocked": [...], "items": n}``，
    ``status`` ∈ ``compared`` / ``unconfirmed`` / ``empty`` / ``unresolved``。

    **所有比对键都必须带 origin_confidence**：UI 要能回答「系统是拿什么比出来的」，
    以及「这条键本身有没有人确认过」。
    """
    keys: List[Dict[str, Any]] = []
    blocked: List[Dict[str, Any]] = []
    label = _FIELD_LABELS.get(field, field)

    def _blocked(confidence: Any, reason: str) -> None:
        blocked.append({"field": field, "confidence": str(confidence or ""), "reason": reason})

    # --- 模块名 ---
    if field == "name":
        confidence = card.get("confidence")
        name_cn = str(card.get("name_cn") or "").strip()
        if cov.is_unconfirmed(confidence):
            _blocked(confidence, f"{label}的置信度是「待教师确认」，未经确认的名称不参与比对")
            return {"keys": [], "status": "unconfirmed", "reason": "", "blocked": blocked, "items": 1}
        cov.add_comparison_key(keys, name_cn, "card_name_raw", confidence, "卡片名称原文")
        stripped = cov.strip_structural_words(name_cn)
        if stripped and stripped != cov.normalize_text(name_cn):
            cov.add_comparison_key(keys, stripped, "card_name", confidence, "卡片名称去掉结构性词")
        if not keys:
            return {"keys": [], "status": "empty", "reason": "", "blocked": blocked, "items": 1}
        return {"keys": keys, "status": "compared", "reason": "", "blocked": blocked, "items": 1}

    # --- 模块目标（语义文本；引擎给不出就空着） ---
    if field == "objective":
        text = str(card.get("objective") or "").strip()
        confidence = card.get("objective_confidence")
        if cov.is_unconfirmed(confidence):
            # 引擎给不出业务含义时会把 objective 留空、并把置信度标成 unconfirmed：
            # 这时**两件事都要说**——「还没有人确认」与「文本是空的」，不许只说一半。
            _blocked(
                confidence,
                f"{label}还是「待教师确认」"
                + ("（图谱里这段文本是空的，引擎推不出业务含义就不编）" if not text else ""),
            )
            return {"keys": [], "status": "unconfirmed", "reason": "", "blocked": blocked, "items": 1}
        if not text:
            return {"keys": [], "status": "empty", "reason": "", "blocked": blocked, "items": 0}
        cov.add_comparison_key(keys, text, "card_objective", confidence, "卡片目标文本")
        return {"keys": keys, "status": "compared", "reason": "", "blocked": blocked, "items": 1}

    # --- 事实型字段（规则 / 前置判断 / 异常 / 状态变化） ---
    if field in _FACT_FIELDS:
        origin, _cn = _FACT_FIELDS[field]
        facts = _facts_of(card, field)
        if not facts:
            return {"keys": [], "status": "empty", "reason": "", "blocked": blocked, "items": 0}
        for fact in facts:
            confidence = fact.get("confidence")
            detail = _fact_detail(fact)
            if cov.is_unconfirmed(confidence):
                _blocked(confidence, f"这条{label}还没被确认（{detail or '无出处'}），不参与比对")
                continue
            if field == "state_changes":
                path = extract_state_path(fact.get("code"))
                if path:
                    cov.add_comparison_key(keys, path, "card_state_path", confidence, detail)
                else:
                    # 解析不出状态路径：整条文本当键（宁可弱，也不假装解析成功）
                    cov.add_comparison_key(
                        keys, _fact_text(fact), f"{origin}_code", confidence, detail
                    )
            else:
                cov.add_comparison_key(keys, _fact_text(fact), origin, confidence, detail)
        if keys:
            return {"keys": keys, "status": "compared", "reason": "", "blocked": blocked, "items": len(facts)}
        if blocked:
            return {"keys": [], "status": "unconfirmed", "reason": "", "blocked": blocked, "items": len(facts)}
        return {"keys": [], "status": "empty", "reason": "", "blocked": blocked, "items": len(facts)}

    # --- 状态字段清单（输入 / 输出） ---
    if field in ("inputs", "outputs"):
        items = _string_list(card.get(field))
        if not items:
            return {"keys": [], "status": "empty", "reason": "", "blocked": blocked, "items": 0}
        confidence = _member_field_confidence(card)
        if cov.is_unconfirmed(confidence):
            _blocked(confidence, f"{label}的置信度是「待教师确认」，不参与比对")
            return {"keys": [], "status": "unconfirmed", "reason": "", "blocked": blocked, "items": len(items)}
        origin = "card_input" if field == "inputs" else "card_output"
        for item in items:
            cov.add_comparison_key(keys, item, origin, confidence, "状态读写追踪给出的字段名")
        return {"keys": keys, "status": "compared", "reason": "", "blocked": blocked, "items": len(items)}

    # --- 「不负责什么」 ---
    if field == "does_not":
        items = _string_list(card.get("does_not"))
        confidence = card.get("does_not_confidence")
        if not items:
            return {"keys": [], "status": "empty", "reason": "", "blocked": blocked, "items": 0}
        if cov.is_unconfirmed(confidence):
            _blocked(confidence, f"{label}的置信度是「待教师确认」，不参与比对")
            return {"keys": [], "status": "unconfirmed", "reason": "", "blocked": blocked, "items": len(items)}
        for item in items:
            cov.add_comparison_key(keys, item, "card_does_not", confidence, "「不负责什么」条目")
        return {"keys": keys, "status": "compared", "reason": "", "blocked": blocked, "items": len(items)}

    # --- 上下游模块（比的是**被引用模块的名字**，不是内部 id） ---
    if field in _MODULE_REF_FIELDS:
        ids = _string_list(card.get(field))
        if not ids:
            return {"keys": [], "status": "empty", "reason": "", "blocked": blocked, "items": 0}
        unresolved = 0
        for module_id in ids:
            other = _card_of(graph, module_id)
            if other is None:
                unresolved += 1
                continue
            confidence = other.get("confidence")
            name_cn = str(other.get("name_cn") or "").strip()
            if not name_cn:
                unresolved += 1
                continue
            if cov.is_unconfirmed(confidence):
                _blocked(confidence, f"{label}「{module_id}」的名称待教师确认，不参与比对")
                continue
            cov.add_comparison_key(
                keys, name_cn, "card_upstream_name" if field == "upstream_modules" else "card_downstream_name",
                confidence, f"被引用模块 {module_id} 的名称",
            )
        if keys:
            return {"keys": keys, "status": "compared", "reason": "", "blocked": blocked, "items": len(ids)}
        if blocked:
            return {"keys": [], "status": "unconfirmed", "reason": "", "blocked": blocked, "items": len(ids)}
        if unresolved:
            return {"keys": [], "status": "unresolved", "reason": "", "blocked": blocked, "items": len(ids)}
        return {"keys": [], "status": "empty", "reason": "", "blocked": blocked, "items": len(ids)}

    # 未知字段选择器：**不静默忽略** —— 记成 unresolved，报告里写明
    return {
        "keys": [],
        "status": "unresolved",
        "reason": f"题目配置里的字段选择器 `{field}` 引擎不认识",
        "blocked": blocked,
        "items": 0,
    }


def _question_not_comparable_reason(field_results: Sequence[Dict[str, Any]]) -> str:
    """一个问题没有任何可比对键时，必须说清是**哪一步**把它挡住的。"""
    labels: List[str] = []
    unconfirmed_labels: List[str] = []
    unresolved_labels: List[str] = []
    empty_labels: List[str] = []
    for result in field_results:
        label = str(result.get("label") or "")
        status = str(result.get("status") or "")
        if status == "unconfirmed":
            unconfirmed_labels.append(label)
        elif status == "unresolved":
            unresolved_labels.append(label)
        elif status == "empty":
            empty_labels.append(label)
        labels.append(label)

    if unconfirmed_labels:
        return (
            "该卡片待教师确认：" + "、".join(unconfirmed_labels)
            + " 的置信度是「待教师确认」，本问题暂不参与比对"
        )
    if unresolved_labels:
        return "本问题引用的内容（" + "、".join(unresolved_labels) + "）在图谱里没有可用的名字，暂不参与比对"
    if empty_labels:
        return (
            "图谱里这张卡片没有" + "、".join(empty_labels)
            + "（引擎给不出就不编），本问题暂不参与比对"
        )
    return "本问题没有可参与比对的字段"


def build_question_targets(graph: Dict[str, Any], module_id: str) -> Optional[Dict[str, Any]]:
    """把一张卡片拆成「每个问题 → 比对键」。

    返回 ``None`` 表示这张卡片不在图谱里（调用方要显式报 404，不许静默降级）。

    返回结构::

        {"module": {...}, "questions": [...], "card_needs_review": bool,
         "field_status": [...], "unconfirmed_fields": [...]}
    """
    card = _card_of(graph, module_id)
    if card is None:
        return None

    module = {
        "module_id": str(card.get("module_id") or module_id),
        "name_cn": str(card.get("name_cn") or ""),
        "level": card.get("level"),
        "parent_id": card.get("parent_id"),
        "confidence": str(card.get("confidence") or ""),
        "name_status": str(card.get("name_status") or ""),
        "review_status": str(card.get("review_status") or ""),
        "source": str(card.get("source") or ""),
        "objective": str(card.get("objective") or ""),
        "objective_confidence": str(card.get("objective_confidence") or ""),
    }
    domain = _domain_of(graph, card.get("parent_id"))
    module["domain_id"] = str(domain.get("domain_id") or "")
    module["domain_name_cn"] = str(domain.get("name_cn") or "")
    module["domain_role"] = str(domain.get("role") or "")

    questions: List[Dict[str, Any]] = []
    field_status: List[Dict[str, Any]] = []
    unconfirmed_fields: List[Dict[str, Any]] = []

    for spec in question_specs():
        keys: List[Dict[str, Any]] = []
        results: List[Dict[str, Any]] = []
        for field in spec["fields"]:
            result = _field_keys(graph, card, field)
            result["field"] = field
            result["label"] = _FIELD_LABELS.get(field, field)
            results.append(result)
            # 键按「字段顺序 + 字段内插入顺序」拼接 —— 顺序稳定才有确定性输出
            for key in result["keys"]:
                if not any(
                    item["key"] == key["key"] and item["origin"] == key["origin"] for item in keys
                ):
                    keys.append(key)
            status = dict(result)
            status.pop("keys", None)
            status["question_id"] = spec["question_id"]
            field_status.append(status)
            for blocked in result["blocked"]:
                unconfirmed_fields.append(
                    {
                        "field": blocked["field"],
                        "label": _FIELD_LABELS.get(blocked["field"], blocked["field"]),
                        "confidence": blocked["confidence"],
                        "question_id": spec["question_id"],
                        "reason": blocked["reason"],
                    }
                )

        questions.append(
            {
                "question_id": spec["question_id"],
                "text_cn": spec["text_cn"],
                "placeholder_cn": spec["placeholder_cn"],
                "fields": list(spec["fields"]),
                "keys": keys,
                "comparable": bool(keys),
                "not_comparable_reason": "" if keys else _question_not_comparable_reason(results),
                "field_results": [
                    {
                        "field": r["field"],
                        "label": r["label"],
                        "status": r["status"],
                        "items": r["items"],
                    }
                    for r in results
                ],
            }
        )

    return {
        "module": module,
        "questions": questions,
        "card_needs_review": bool(unconfirmed_fields),
        "field_status": field_status,
        "unconfirmed_fields": unconfirmed_fields,
    }


# ============================================================
# 卡片顺序（任务接口用；与图谱里的域顺序一致，且不丢卡片）
# ============================================================

def _cards_in_order(graph: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """按「域顺序 → 域卡片 → 该域二级卡片」给出卡片，并返回域清单。

    图谱里存在但上面没覆盖到的卡片（例如 ``parent_id`` 不在 ``domains`` 里）
    **追加在最后**：宁可多给一张，也不许悄悄少给一张。
    """
    cards = _cards_of(graph)
    domains = _domains_of(graph)
    capabilities = [c for c in ((graph or {}).get("capabilities") or []) if isinstance(c, dict)]

    by_parent: Dict[str, List[Dict[str, Any]]] = {}
    for cap in capabilities:
        by_parent.setdefault(str(cap.get("parent_id") or ""), []).append(cap)
    for key in by_parent:
        by_parent[key].sort(key=lambda c: str(c.get("capability_id") or ""))

    ordered: List[Dict[str, Any]] = []
    seen: set = set()

    def _take(module_id: Any) -> None:
        key = str(module_id or "")
        card = cards.get(key)
        if isinstance(card, dict) and key not in seen:
            ordered.append(card)
            seen.add(key)

    for domain in domains:
        domain_id = str(domain.get("domain_id") or "")
        _take(domain_id)
        for cap in by_parent.get(domain_id, []):
            _take(cap.get("capability_id"))

    for module_id in sorted(cards):
        _take(module_id)

    return ordered, domains


def _task_card(graph: Dict[str, Any], card: Dict[str, Any]) -> Dict[str, Any]:
    """任务接口里的一张卡片（学生可见字段 + 「哪些字段待教师确认」）。"""
    module_id = str(card.get("module_id") or "")
    targets = build_question_targets(graph, module_id) or {"unconfirmed_fields": [], "card_needs_review": False}
    domain = _domain_of(graph, card.get("parent_id"))

    def _names(ids: Any) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for ref in _string_list(ids):
            other = _card_of(graph, ref) or {}
            out.append(
                {
                    "module_id": ref,
                    "name_cn": str(other.get("name_cn") or ""),
                    "confidence": str(other.get("confidence") or ""),
                    "resolved": bool(other),
                }
            )
        return out

    return {
        "module_id": module_id,
        "name_cn": str(card.get("name_cn") or ""),
        "level": card.get("level"),
        "parent_id": card.get("parent_id"),
        "domain_id": str(domain.get("domain_id") or ""),
        "domain_name_cn": str(domain.get("name_cn") or ""),
        "domain_role": str(domain.get("role") or ""),
        "role": str(card.get("role") or ""),
        "confidence": str(card.get("confidence") or ""),
        "member_confidence": str(card.get("member_confidence") or ""),
        "name_status": str(card.get("name_status") or ""),
        "review_status": str(card.get("review_status") or ""),
        "source": str(card.get("source") or ""),
        "objective": str(card.get("objective") or ""),
        "objective_confidence": str(card.get("objective_confidence") or ""),
        "does_not": _string_list(card.get("does_not")),
        "does_not_confidence": str(card.get("does_not_confidence") or ""),
        "inputs": _string_list(card.get("inputs")),
        "outputs": _string_list(card.get("outputs")),
        "business_rules": _facts_of(card, "business_rules"),
        "state_changes": _facts_of(card, "state_changes"),
        "preconditions": _facts_of(card, "preconditions"),
        "exceptions": _facts_of(card, "exceptions"),
        "upstream_modules": _string_list(card.get("upstream_modules")),
        "downstream_modules": _string_list(card.get("downstream_modules")),
        "upstream_names": _names(card.get("upstream_modules")),
        "downstream_names": _names(card.get("downstream_modules")),
        "members": card.get("members") or [],
        "evidence": card.get("evidence") or [],
        "card_needs_review": bool(targets.get("card_needs_review")),
        "pending_confirmation_fields": [
            item["label"] for item in targets.get("unconfirmed_fields") or []
        ],
    }


# ============================================================
# 任务（题目 + 卡片，全部由 business_graph 派生）
# ============================================================

def _task_caveats(graph: Dict[str, Any], counts: Dict[str, int]) -> List[str]:
    return [
        "题目与卡片内容**全部由业务图谱派生**（题目文本来自 engine/lexicon/stage_questions.json，"
        "卡片内容来自该项目的 business_graph），前端不认识任何一个业务字段。",
        f"本阶段**不打分**：只做事实覆盖比对——你写的内容里提到了这张卡片哪些已核实的事实、"
        f"哪些还没提到（scoring = {SCORING}）。",
        f"本项目图谱里有 {counts['cards']} 张卡片，其中 {counts['cards_needing_review']} 张卡片上"
        "至少有一个字段的置信度是「待教师确认」；那些字段**不参与比对**。",
        "「输入 / 输出 / 状态变化」三个问题在本引擎里同源（都来自状态读写追踪），"
        "它们的比对键可能重叠——引擎不会为了凑出差异而编造第二份数据。",
        f"题库来源：{question_spec_source() or '未记录'}。",
    ]


def build_module_card_task(graph: Dict[str, Any]) -> Dict[str, Any]:
    """阶段二的任务包：五个问题 + 本项目所有卡片（学生可见字段）。

    前端只依赖这一份产物：**换一个项目，题目与卡片内容跟着换，页面代码不改**
    （README 第十八章 优先级 1 的验收标准）。
    """
    graph = graph or {}
    specs = question_specs()
    cards, domains = _cards_in_order(graph)
    task_cards = [_task_card(graph, card) for card in cards]

    core_domains = [d for d in domains if cov.normalize_text(d.get("role")) not in ("orchestrator", "support")]
    counts = {
        "questions": len(specs),
        "cards": len(task_cards),
        "domains": len(domains),
        "core_domains": len(core_domains),
        "supporting_domains": len(domains) - len(core_domains),
        "cards_needing_review": sum(1 for c in task_cards if c["card_needs_review"]),
    }

    caveats = _task_caveats(graph, counts)
    if not specs:
        caveats.insert(
            0,
            "**题目配置没有加载出来**（engine/lexicon/stage_questions.json 缺失或损坏）："
            "本阶段暂时给不出问题，也不做任何比对。",
        )

    return {
        "task_version": TASK_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "contract_version": CONTRACT_VERSION,
        "project_id": str(graph.get("project_id") or ""),
        "project_name": str(graph.get("project_name") or ""),
        "source_hash": str(graph.get("source_hash") or ""),
        "level": str(graph.get("level") or ""),
        "stage": STAGE,
        "stage_name_cn": stage_name_cn(),
        "scoring": SCORING,
        "has_score": False,
        "answer_prompt_cn": answer_prompt(),
        "answer_max_chars": MAX_ANSWER_CHARS,
        "answer_total_max_chars": MAX_TOTAL_CHARS,
        "question_spec_source": question_spec_source(),
        "questions": [
            {
                "question_id": item["question_id"],
                "text_cn": item["text_cn"],
                "placeholder_cn": item["placeholder_cn"],
            }
            for item in specs
        ],
        "cards": task_cards,
        "counts": counts,
        "caveats": caveats,
    }


# ============================================================
# 覆盖比对（学生先输出 → 系统后反馈）
# ============================================================

def _report_caveats(
    targets: Dict[str, Any],
    counts: Dict[str, int],
    unknown_question_ids: Sequence[str],
) -> List[str]:
    lines = [
        "本阶段**不打分、不给标准答案**：报告只说明你的回答里提到了这张卡片上的哪些事实、"
        "以及哪些还没有被提到。",
        "比对键只来自图谱里已有的文本（卡片名 / 目标 / 状态字段名 / 规则条件 / 上下游模块名），"
        "**系统不做中文分词**，因此列不出「你额外提到的、卡片上没有的东西」。",
        "命中判定是「比对键出现在你的回答里」（中文按子串、英文按整词）。"
        "**「提到」不等于「理解」**：照着卡片抄也能命中，引擎分不出理解与抄写——"
        "你的理解是否到位，由教师看你的原话判断。",
        "规则条件类的比对键是**代码表达式**（引擎只给代码、不编语义），用中文表述的答案通常不会命中，"
        "因此这类键没命中**不构成答错的证据**。",
        "本引擎里「输入 / 输出 / 状态变化」三个问题同源（都来自状态读写追踪），"
        "比对键可能重叠——引擎不会为了凑出差异而编造第二份数据。",
    ]
    if counts["unconfirmed_fields"]:
        names = "、".join(sorted({item["label"] for item in targets["unconfirmed_fields"]}))
        lines.append(
            f"**该卡片待教师确认**：{names} 等 {counts['unconfirmed_fields']} 处内容的置信度是"
            "「待教师确认」，它们不参与比对，也不计入上面的清单。"
        )
    if counts["not_comparable_questions"]:
        lines.append(
            f"有 {counts['not_comparable_questions']} 个问题这次没有参与比对"
            "（每个问题后面写明了原因），所以「没命中」在这几个问题上不代表你答错了。"
        )
    if unknown_question_ids:
        lines.append(
            "提交里含有本阶段不认识的问题标识（" + "、".join(unknown_question_ids)
            + "），它们被原样列出、未参与比对。"
        )
    return lines


def evaluate_module_card_answers(
    graph: Dict[str, Any],
    module_id: str,
    answers: Dict[str, Any],
) -> Dict[str, Any]:
    """阶段二的事实覆盖比对。

    :param graph: 业务图谱（``business_graph`` 本体）
    :param module_id: 卡片 id（二级功能点或一级域）
    :param answers: ``{question_id: 学生回答原文}``
    :returns: 覆盖报告（JSON 可序列化、确定性、**无分数字段**）

    与阶段一一样，**空输入也返回报告**（``empty_input: True``）：本函数是纯函数、不做入口校验；
    「不许空提交」由后端与前端各自把关。``module_id`` 不在图谱里时返回 ``{}``，
    由调用方显式报 404 —— 不许静默降级成「一张空卡片」。
    """
    targets = build_question_targets(graph, str(module_id))
    if targets is None:
        return {}

    answers = answers if isinstance(answers, dict) else {}
    known_ids = [q["question_id"] for q in targets["questions"]]
    unknown_ids = [
        str(key) for key in answers.keys() if str(key) not in known_ids
    ]
    unknown_ids.sort()

    question_reports: List[Dict[str, Any]] = []
    matched_total = 0
    missed_total = 0
    comparable = 0
    with_hits = 0
    not_comparable = 0
    empty_answers = 0

    for question in targets["questions"]:
        raw = answers.get(question["question_id"])
        text = str(raw if raw is not None else "")
        _normalized, compact, tokens = cov.prepare_text(text)
        empty_answer = not compact
        if empty_answer:
            empty_answers += 1

        matched: List[Dict[str, Any]] = []
        missed: List[Dict[str, Any]] = []
        for key in question["keys"]:
            (matched if cov.key_hit(key["key"], compact, tokens) else missed).append(key)

        if question["comparable"]:
            comparable += 1
            if matched:
                with_hits += 1
        else:
            not_comparable += 1
        matched_total += len(matched)
        missed_total += len(missed)

        question_reports.append(
            {
                "question_id": question["question_id"],
                "text_cn": question["text_cn"],
                "answer_chars": len(text),
                "empty_answer": empty_answer,
                "comparable": question["comparable"],
                "not_comparable_reason": question["not_comparable_reason"],
                "matched_keys": matched,
                "missed_keys": missed,
                # 未命中的键也要带上：UI 要能回答「系统是拿什么比出来的」
                "keys_considered": question["keys"],
                "field_results": question["field_results"],
            }
        )

    counts = {
        "questions": len(question_reports),
        "comparable_questions": comparable,
        "questions_with_hits": with_hits,
        "not_comparable_questions": not_comparable,
        "matched_keys": matched_total,
        "unmatched_keys": missed_total,
        "unconfirmed_fields": len(targets["unconfirmed_fields"]),
        "empty_answers": empty_answers,
    }

    return {
        "report_version": REPORT_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "contract_version": CONTRACT_VERSION,
        "project_id": str(graph.get("project_id") or ""),
        "source_hash": str(graph.get("source_hash") or ""),
        "stage": STAGE,
        "stage_name_cn": stage_name_cn(),
        "scoring": SCORING,
        "has_score": False,
        "module": targets["module"],
        "card_needs_review": targets["card_needs_review"],
        "unconfirmed_fields": targets["unconfirmed_fields"],
        "empty_input": empty_answers == len(question_reports),
        "unknown_question_ids": unknown_ids,
        "counts": counts,
        "questions": question_reports,
        "caveats": _report_caveats(targets, counts, unknown_ids),
    }
