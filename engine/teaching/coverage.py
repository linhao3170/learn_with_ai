"""阶段一「项目认知」的覆盖度比对器（培养方案第四章 阶段一 / 架构文档第十一章 11.2 的覆盖度分支）。

学生在阶段一写的是一段自由文本：""用自己的话说说这个项目为什么需要这些模块""。
系统**不打分、不给标准答案**，只回一份覆盖度报告：命中了哪些一级业务域、漏了哪些。

四条纪律（全部可被脚本检查）
============================
1. **不打分**：返回值里没有 ``score`` / ``grade`` / ``correct`` 这类字段，只有 covered / missed 清单
   （培养方案第四章 阶段一：""系统只输出覆盖度报告，不打分、不给标准答案""）。
2. **无证据不比对**：比对键**只**来自图谱里已经存在的文本（域名、域目标）；
   置信度为 ``unconfirmed``（待教师确认）或缺失的字段**不参与比对**，
   该域进入 ``not_comparable`` 并写明原因——不拿一条没人确认过的话去判学生漏了什么。
3. **不编业务含义**：本模块不含任何业务词，词典在 ``engine/lexicon/structural_names.json``；
   每个比对键的来源（``origin``）与原始置信度逐条记录，UI 必须显示""系统是拿什么比出来的""。
4. **确定性**：无随机、无网络、无 LLM、无 ``set`` 遍历顺序依赖；同一份输入两次调用输出逐字节相同
   （设计原则第七条）。

做不到的事（写出来，不让 UI 假装做到了）
========================================
- **不做中文分词**：没有分词器就无法可靠地抽取""学生提到的、不属于任何域的名词""，
  所以报告里**没有**""你额外提到了哪些模块""这一类结论。命中判定是
  ""比对键出现在学生文本里""——中文按子串、英文按整词。
- **命中 ≠ 答对**：命中只说明学生提到了这个域的名字；他是否理解这个域为什么存在、
  边界在哪，规则引擎判不了（纪律：规则引擎判事实，教师判语义，LLM 只做映射与润色）。
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Sequence, Tuple

from engine.lexicon import load_lexicon

__all__ = [
    "ALGORITHM_VERSION",
    "REPORT_VERSION",
    "SCORING",
    # --- 阶段二复用的公开入口（不要把命中判定复制第二份）---
    "add_comparison_key",
    "is_unconfirmed",
    "key_hit",
    "prepare_text",
    "build_domain_targets",
    "evaluate_orientation",
    "normalize_text",
    "strip_structural_words",
]

#: 产物版本（纪律：每个产物带 algorithm_version）
ALGORITHM_VERSION = "orientation-coverage-1.0"
REPORT_VERSION = "1.0"
CONTRACT_VERSION = "1.0"
#: 本阶段唯一的判定口径：只给覆盖清单，不给分数
SCORING = "coverage_only"

#: 判定为""还没有人能确认""的置信度档位 —— 这些字段不参与比对。
#: 原始值先做小写 / 去空格归一，再和这张表比对。
_UNCONFIRMED_TOKENS = frozenset({"", "unconfirmed", "unknown", "none", "null", "未标注", "待确认"})

#: 编排 / 支撑域：按培养方案，它们不进""核心业务模块""列表，因此不参与核心覆盖度。
_NON_CORE_ROLES = frozenset({"orchestrator", "support"})

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_ASCII_TOKEN_RE = re.compile(r"[a-z0-9]+")
_PAREN_RE = re.compile(r"[（(][^）)]*[）)]")
_WS_RE = re.compile(r"\s+")

#: 比对键最短长度：一个字/一个字母的键噪声太大（""的""、""i""），不作为命中依据。
MIN_KEY_LEN = 2

#: 学生输入的长度上限（后端在入口处拦截，这里是第二道闸）
MAX_INPUT_CHARS = 4000


# ============================================================
# 归一化
# ============================================================

def normalize_text(value: Any) -> str:
    """全角 → 半角、大小写归一、压缩空白。中文不受影响（NFKC 不改变汉字）。"""
    text = unicodedata.normalize("NFKC", str(value if value is not None else ""))
    return _WS_RE.sub(" ", text).strip().lower()


def _stopwords() -> Tuple[str, ...]:
    """结构性词表（来自词典，不在代码里硬编码）。"""
    data = load_lexicon("structural_names")
    words = data.get("coverage_stopwords") or []
    out = [normalize_text(w) for w in words if str(w or "").strip()]
    # 长词优先，避免""管理模块""这种连写被半个词切掉后残留
    return tuple(sorted(set(out), key=lambda w: (-len(w), w)))


def strip_structural_words(name: Any) -> str:
    """从模块名里剥掉结构性词与括号限定语，得到可比对的核心词。

    例：``安全检查模块`` → ``安全检查``；``系统装配（cli）`` → ``装配``。
    """
    text = _PAREN_RE.sub(" ", normalize_text(name))
    for word in _stopwords():
        text = text.replace(word, " ")
    return _WS_RE.sub(" ", text).strip()


def _is_unconfirmed(confidence: Any) -> bool:
    """置信度是否表示""还没人确认过""（这些字段不参与比对）。"""
    return normalize_text(confidence) in _UNCONFIRMED_TOKENS


def _key_len_ok(key: str) -> bool:
    if len(key) < MIN_KEY_LEN:
        return False
    # 纯 ASCII 键里必须有一个长度 ≥ 3 的词，否则""i""""ab""这种键会把任何英文输入都判成命中
    if _CJK_RE.search(key):
        return True
    return any(len(part) >= 3 for part in _ASCII_TOKEN_RE.findall(key))


def _add_key(keys: List[Dict[str, Any]], key: str, origin: str, confidence: Any, detail: str = "") -> None:
    """加入一个比对键（去重，保持插入顺序 —— 顺序稳定才有确定性输出）。"""
    normalized = _WS_RE.sub(" ", normalize_text(key))
    if not _key_len_ok(normalized):
        return
    if any(item["key"] == normalized and item["origin"] == origin for item in keys):
        return
    keys.append(
        {
            "key": normalized,
            "origin": origin,
            "origin_confidence": str(confidence if confidence is not None else ""),
            "detail": detail,
        }
    )


# ============================================================
# 比对目标（一级业务域 → 比对键）
# ============================================================

def build_domain_targets(graph: Dict[str, Any]) -> Dict[str, Any]:
    """把业务图谱拆成""参与覆盖度的核心域""与""不参与的核心外域""两组。

    返回 ``{"core": [...], "supporting": [...], "stats": {...}}``，
    每个 core 项带 ``keys``（比对键 + 来源）、``not_comparable_reason``（为空表示可参与比对）。
    """
    graph = graph or {}
    domains = [d for d in (graph.get("domains") or []) if isinstance(d, dict)]
    cards = graph.get("module_cards") or {}
    if not isinstance(cards, dict):
        cards = {}

    core: List[Dict[str, Any]] = []
    supporting: List[Dict[str, Any]] = []
    objective_missing = 0

    for domain in sorted(domains, key=lambda d: str(d.get("domain_id") or "")):
        domain_id = str(domain.get("domain_id") or "")
        name_cn = str(domain.get("name_cn") or "")
        role = normalize_text(domain.get("role"))
        card = cards.get(domain_id) if isinstance(cards.get(domain_id), dict) else {}

        entry: Dict[str, Any] = {
            "domain_id": domain_id,
            "name_cn": name_cn,
            "role": role or "core",
            "confidence": str(domain.get("confidence") or ""),
            "name_status": str(domain.get("name_status") or ""),
            "capability_ids": list(domain.get("children") or []),
            "keys": [],
            "not_comparable_reason": "",
        }

        if role in _NON_CORE_ROLES:
            supporting.append(entry)
            continue

        # --- 比对键 1：域名（剥离结构性词前后的两种写法都算）---
        if _is_unconfirmed(entry["confidence"]):
            entry["not_comparable_reason"] = "该域名的置信度是「待教师确认」，未经确认的名称不参与比对"
        else:
            stripped = strip_structural_words(name_cn)
            _add_key(entry["keys"], stripped, "domain_name", entry["confidence"], "域名去掉结构性词")
            if stripped:
                _add_key(entry["keys"], name_cn, "domain_name_raw", entry["confidence"], "域名原文")

        # --- 比对键 2：域目标（objective）---
        objective = str(card.get("objective") or "")
        objective_confidence = card.get("objective_confidence")
        if not objective.strip():
            objective_missing += 1
        elif _is_unconfirmed(objective_confidence):
            # 目标文本存在但没人确认过 —— 不参与比对，且要说清楚是哪一步被挡住的
            if not entry["not_comparable_reason"]:
                entry["not_comparable_reason"] = (
                    "该域的目标（objective）还是「待教师确认」，未经确认的目标文本不参与比对"
                )
        else:
            _add_key(entry["keys"], objective, "domain_objective", objective_confidence, "域目标文本")

        if not entry["keys"] and not entry["not_comparable_reason"]:
            entry["not_comparable_reason"] = "该域没有可用于比对的名称或目标（只剩结构性词）"

        core.append(entry)

    return {
        "core": core,
        "supporting": supporting,
        "stats": {
            "core_domains": len(core),
            "supporting_domains": len(supporting),
            "objective_missing": objective_missing,
        },
    }


# ============================================================
# 命中判定
# ============================================================

def _ascii_tokens(normalized_text: str) -> frozenset:
    return frozenset(_ASCII_TOKEN_RE.findall(normalized_text))


def _hit(key: str, compact_text: str, tokens: frozenset) -> bool:
    """比对键是否出现在学生文本里。

    - 含中文的键：在""去掉空格后的归一文本""里做子串匹配（中文没有词边界）；
    - 纯 ASCII 键：按整词匹配（避免 ``atom`` 命中 ``atomic``），且要求至少一个词长 ≥ 3。
    """
    if _CJK_RE.search(key):
        return key.replace(" ", "") in compact_text
    parts = _ASCII_TOKEN_RE.findall(key)
    if not parts or not any(len(p) >= 3 for p in parts):
        return False
    return all(p in tokens for p in parts)


# ============================================================
# 复用入口（阶段二「模块卡片学习」用这一组，不要另写一份）
# ============================================================

def prepare_text(text: Any) -> Tuple[str, str, frozenset]:
    """归一化一次，返回 ``(normalized, compact, ascii_tokens)``。

    阶段一 / 阶段二共用同一份预处理：**同一段学生文本，两个阶段算出来的
    "能不能命中" 必须一致**，否则同一句话在两张页面上给出不同结论。
    """
    normalized = normalize_text(text)
    return normalized, normalized.replace(" ", ""), _ascii_tokens(normalized)


def add_comparison_key(
    keys: List[Dict[str, Any]],
    key: Any,
    origin: str,
    confidence: Any,
    detail: str = "",
) -> None:
    """把一个比对键加进 ``keys``（公开入口，行为与阶段一完全一致）。"""
    _add_key(keys, key, origin, confidence, detail)


def is_unconfirmed(confidence: Any) -> bool:
    """该置信度是否表示""还没有人能确认"" —— 这些字段**不参与比对**。"""
    return _is_unconfirmed(confidence)


def key_hit(key: str, compact_text: str, tokens: frozenset) -> bool:
    """比对键是否出现在学生文本里（中文按子串、英文按整词）。"""
    return _hit(key, compact_text, tokens)


def _caveats(stats: Dict[str, int]) -> List[str]:
    """报告的诚实边界（固定 + 随数据变化）。"""
    lines = [
        "本阶段**不判对错、不打分**：报告只说明你的回答提到了哪些一级业务域，"
        "以及哪些域还没有被提到。",
        "命中判定是「比对键出现在你的回答里」（中文按子串、英文按整词），"
        "**系统不做中文分词**，因此无法列出「你额外提到的、不属于任何域的名词」。",
        f"比对键只来自图谱里已有的文本；本项目 {stats['objective_missing']} 个核心域"
        "还没有教师确认的目标文本，这些域只用域名比对。",
        f"另有 {stats['supporting_domains']} 个域是编排 / 支撑域，按「编排类不进入核心业务模块」"
        "的口径不计入核心覆盖度。",
        "命中只代表你提到了这个域，不代表你已经说清它为什么存在——"
        "这部分由教师判断，规则引擎不做结论。",
    ]
    return lines


# ============================================================
# 对外入口
# ============================================================

def evaluate_orientation(graph: Dict[str, Any], text: str) -> Dict[str, Any]:
    """阶段一覆盖度比对：给学生一段自由文本，返回覆盖清单。

    :param graph: 业务图谱（``business_graph`` 本体，含 ``domains`` / ``module_cards``）
    :param text: 学生的回答原文
    :returns: 覆盖度报告（JSON 可序列化、确定性、无分数字段）

    注意：**空输入也返回报告**（``empty_input: True``，全部记为未命中），
    因为本函数是纯函数、不做入口校验；""不许空提交""由后端与前端各自把关。
    """
    targets = build_domain_targets(graph)
    normalized = normalize_text(text)
    compact = normalized.replace(" ", "")
    tokens = _ascii_tokens(normalized)
    empty_input = not compact

    covered: List[Dict[str, Any]] = []
    missed: List[Dict[str, Any]] = []
    not_comparable: List[Dict[str, Any]] = []

    for entry in targets["core"]:
        if entry["not_comparable_reason"] or not entry["keys"]:
            not_comparable.append(
                {
                    "domain_id": entry["domain_id"],
                    "name_cn": entry["name_cn"],
                    "role": entry["role"],
                    "reason": entry["not_comparable_reason"] or "该域没有可用于比对的名称或目标",
                }
            )
            continue

        matched = [k for k in entry["keys"] if _hit(k["key"], compact, tokens)]
        record = {
            "domain_id": entry["domain_id"],
            "name_cn": entry["name_cn"],
            "role": entry["role"],
            "confidence": entry["confidence"],
            "name_status": entry["name_status"],
            "matched_keys": matched,
            # 未命中的域也把比对键带上：UI 要能回答""系统是拿什么比出来的""
            "keys_considered": entry["keys"],
            "capability_ids": entry["capability_ids"],
        }
        if matched:
            covered.append(record)
        else:
            missed.append(record)

    stats = {
        "core_domains": targets["stats"]["core_domains"],
        "comparable_domains": len(covered) + len(missed),
        "covered": len(covered),
        "missed": len(missed),
        "not_comparable": len(not_comparable),
        "supporting_domains": targets["stats"]["supporting_domains"],
        "objective_missing": targets["stats"]["objective_missing"],
    }

    return {
        "report_version": REPORT_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "contract_version": CONTRACT_VERSION,
        "project_id": str(graph.get("project_id") or ""),
        "source_hash": str(graph.get("source_hash") or ""),
        "stage": "orientation",
        "stage_name_cn": "项目认知",
        "scoring": SCORING,
        "has_score": False,
        "empty_input": empty_input,
        "input": {"chars": len(str(text or "")), "normalized_chars": len(normalized)},
        "counts": stats,
        "covered": covered,
        "missed": missed,
        "not_comparable": not_comparable,
        "supporting_domains": [
            {
                "domain_id": item["domain_id"],
                "name_cn": item["name_cn"],
                "role": item["role"],
                "capability_ids": item["capability_ids"],
            }
            for item in targets["supporting"]
        ],
        "caveats": _caveats({**targets["stats"], "supporting_domains": targets["stats"]["supporting_domains"]}),
    }
