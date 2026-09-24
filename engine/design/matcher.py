"""学生模块 ↔ 必备能力的匹配器（README §9.2 前置：``matcher.py``）。

学生在设计画布上画出来的模块，要能和任务给出的「必备能力清单」（``must_have``）对上，
六维里的第一维（核心需求覆盖度）与第二维（职责清晰度）都建立在这份匹配结果之上。

三条纪律（全部可被脚本检查）
============================
1. **只有一份归一化与命中判定**：剥结构性词、全角转半角、大小写归一全部复用
   ``engine/teaching/coverage.py``（``normalize_text`` / ``strip_structural_words`` /
   ``prepare_text`` / ``key_hit``）。同一份仓库里不允许存在两套「两个名字算不算同一个」的判定 ——
   否则阶段二说「提到了」、设计层说「没提到」，同一句话在两张页面上结论不同。
2. **匹配结果必须三分类，绝不能二分类**（README §9.2）：

   - ``matched``：必备能力已经在设计里被识别到 → 计入覆盖度；
   - ``missing``：明确没有被覆盖的必备能力；
   - ``unrecognized``：学生画的、但没对上任何必备能力的模块 → **不计入覆盖度**，
     单独列出「系统未能识别，可能是命名不同，请教师 / 学生确认」。

3. **措辞不能定罪**：词汇匹配必然有假阴性。所以本模块只输出结构化结论
   （``matched`` / ``missing`` / ``unrecognized`` + 命中方式 ``method`` + 参与比对的键），
   一句定罪式文案都不写 —— 文案在 ``engine/lexicon/design_feedback.json``，
   且模板里写的是「未在设计中识别到」（而不是「你漏了」）。

匹配优先级（README §9.2 原文）
=============================
    ① 精确等于 name_cn 或任一 alias            → exact
    ② 一方包含另一方（长度 ≥ 2）                → contains
    ③ 中文 bigram + 英文 token 的交集/并集 ≥ 0.5 → token
    ④ 未命中                                    → unrecognized

一个模块只按它**最强的那一种**命中方式计入（跑起来才发现的问题）
============================================================
严格按「逐对独立判定」实现时会出现这样的事：必备能力叫「普通能力一 / 普通能力二 / 普通能力三」，
学生画了一个叫「普通能力一」的模块 —— 它与第一项是 ``exact``，但与第二、三项的 bigram 交并比
是 3/5 = 0.6，于是**一个模块同时成了三项必备能力的承担者**，覆盖度被凭空抬高。

所以本模块的规则是：**先算出一个模块对全部必备能力的最佳命中方式，再只用该方式的那些配对**。
- 命中方式相同时**保留多条**（一个模块同时承担多项能力是真实存在的，
  「职责过载」正是靠这一点才能被检出）；
- 命中方式更弱的不再叠加（避免「名字像」被算成「覆盖了」）。
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from engine.teaching import coverage as cov
__all__ = [
    "ALGORITHM_VERSION",
    "METHOD_EXACT",
    "METHOD_CONTAINS",
    "METHOD_TOKEN",
    "CONTAINMENT_MIN_LEN",
    "TOKEN_OVERLAP_THRESHOLD",
    "normalize_name",
    "name_tokens",
    "match_one",
    "match_modules",
    "find_names_in_text",
]

#: 产物版本（纪律：每个产物带 algorithm_version）
ALGORITHM_VERSION = "design-matcher-1.0"

METHOD_EXACT = "exact"
METHOD_CONTAINS = "contains"
METHOD_TOKEN = "token"

#: 包含关系的下限长度：一个字的包含（「的」在「目的」里）没有判别力
CONTAINMENT_MIN_LEN = 2

#: bigram / token 的交集并集比阈值（README §9.2 的 0.5，写在这里而不是散在代码里）
TOKEN_OVERLAP_THRESHOLD = 0.5

#: 中文 bigram 的字符区间（与 coverage.py 的 CJK 判定同源）
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_ASCII_TOKEN_RE = re.compile(r"[a-z0-9]+")


def normalize_name(name: Any) -> str:
    """模块名的归一化形式：剥结构性词 + 去括号限定语 + 全角转半角 + 小写。

    直接复用阶段一的 ``strip_structural_words``（同一份实现，第二份不存在）。
    """
    return cov.strip_structural_words(name)


def _cjk_bigrams(text: str) -> List[str]:
    """中文部分按**字符** bigram 切（不做分词：仓库里没有分词器，也不假装有）。"""
    chars = [ch for ch in text if _CJK_RE.match(ch)]
    if len(chars) < 2:
        return chars
    return [chars[i] + chars[i + 1] for i in range(len(chars) - 1)]


def name_tokens(name: Any) -> frozenset:
    """名字的比对 token 集：中文 bigram + 英文词（长度 ≥ 2）。

    英文 token 保留 1 个字符的（如 ``a``）没有判别力，直接丢掉；
    但整个名字都是短 token 时保留原样，避免把名字清空成空集。
    """
    normalized = normalize_name(name)
    tokens: List[str] = list(_cjk_bigrams(normalized))
    ascii_tokens = [t for t in _ASCII_TOKEN_RE.findall(normalized) if len(t) >= 2]
    tokens.extend(ascii_tokens)
    return frozenset(tokens)


def _jaccard(left: frozenset, right: frozenset) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _match_pair(student_name: Any, target_name: Any) -> Optional[str]:
    """一个学生模块名 vs 一个比对键（必备能力名 / 别名）的命中方式。"""
    student = normalize_name(student_name)
    target = normalize_name(target_name)
    if not student or not target:
        return None
    if student == target:
        return METHOD_EXACT
    # 包含关系：只有两个归一化名字都足够长时才允许（避免「的」这种噪音）
    if len(student) >= CONTAINMENT_MIN_LEN and len(target) >= CONTAINMENT_MIN_LEN:
        if student in target or target in student:
            return METHOD_CONTAINS
    if _jaccard(name_tokens(student), name_tokens(target)) >= TOKEN_OVERLAP_THRESHOLD:
        return METHOD_TOKEN
    return None


#: 命中方式的可信度排序（同一对名字可能同时满足多种：取最强的那一种）
_METHOD_RANK = {METHOD_EXACT: 3, METHOD_CONTAINS: 2, METHOD_TOKEN: 1}


def _better(left: Optional[str], right: Optional[str]) -> Optional[str]:
    if left is None:
        return right
    if right is None:
        return left
    return left if _METHOD_RANK[left] >= _METHOD_RANK[right] else right


def match_one(student_name: Any, target: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """一个学生模块 vs 一项必备能力：返回 ``{"method", "key", "key_kind"}`` 或 ``None``。

    ``key_kind`` ∈ ``name`` / ``alias``：UI 要能回答「系统是拿哪个键比出来的」。
    """
    best: Optional[Dict[str, Any]] = None
    candidates: List[Tuple[str, str]] = [(str(target.get("name_cn") or ""), "name")]
    for alias in target.get("aliases") or []:
        candidates.append((str(alias or ""), "alias"))
    for candidate, kind in candidates:
        method = _match_pair(student_name, candidate)
        if method is None:
            continue
        record = {"method": method, "key": cov.normalize_text(candidate), "key_kind": kind}
        if best is None or _METHOD_RANK[method] > _METHOD_RANK[best["method"]]:
            best = record
    return best


def _module_name(module: Dict[str, Any]) -> str:
    """学生模块的显示名（``name`` 是 §10.4 的契约字段，``name_cn`` 是兼容写法）。"""
    return str(module.get("name") or module.get("name_cn") or "")


def _module_id(module: Dict[str, Any], index: int) -> str:
    module_id = str(module.get("module_id") or "").strip()
    return module_id or f"m{index + 1}"


def match_modules(
    modules: Sequence[Dict[str, Any]],
    must_have: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """把学生画的模块与必备能力清单对上（三分类）。

    :param modules: 归一化后的学生模块（``submission.normalize_submission`` 的产物）
    :param must_have: 必备能力清单，每项至少带 ``key`` 与 ``name_cn``
    :returns: 匹配结果（含 matched / missing / unrecognized 三类与逐项命中方式）

    **方向**：以 must_have 为主表（覆盖度是「必备能力有没有承担者」），
    学生多画出来的模块进 ``unrecognized_modules``，不计入覆盖度。
    """
    modules = [m for m in (modules or []) if isinstance(m, dict)]
    must_have = [m for m in (must_have or []) if isinstance(m, dict)]

    # 学生模块先编号：顺序 = 提交顺序（稳定），不排序不随机
    student: List[Dict[str, Any]] = []
    for index, module in enumerate(modules):
        student.append(
            {
                "module_id": _module_id(module, index),
                "name": _module_name(module),
                "normalized": normalize_name(_module_name(module)),
                "index": index,
            }
        )

    per_module_hits: Dict[str, List[Dict[str, Any]]] = {m["module_id"]: [] for m in student}
    matched: List[Dict[str, Any]] = []
    missing: List[Dict[str, Any]] = []

    # 第一遍：每个模块对所有必备能力各算出「最佳命中方式」
    pair_methods: Dict[Tuple[str, str], Dict[str, Any]] = {}
    best_for_module: Dict[str, Optional[str]] = {m["module_id"]: None for m in student}
    for target in must_have:
        key = str(target.get("key") or target.get("name_cn") or "")
        for module in student:
            record = match_one(module["name"], target)
            if record is None:
                continue
            pair_methods[(module["module_id"], key)] = record
            best_for_module[module["module_id"]] = _better(
                best_for_module[module["module_id"]], record["method"]
            )

    # 第二遍：只保留「这个模块最强的那种方式」的配对
    for target in must_have:
        key = str(target.get("key") or target.get("name_cn") or "")
        hits: List[Dict[str, Any]] = []
        for module in student:
            record = pair_methods.get((module["module_id"], key))
            if record is None:
                continue
            if _METHOD_RANK.get(record["method"], 0) < _METHOD_RANK.get(best_for_module[module["module_id"]] or "", 0):
                continue
            detail = {
                "module_id": module["module_id"],
                "module_name": module["name"],
                "method": record["method"],
                "matched_key": record["key"],
                "matched_key_kind": record["key_kind"],
            }
            hits.append(detail)
            per_module_hits[module["module_id"]].append(
                {
                    "must_have_key": key,
                    "must_have_name_cn": str(target.get("name_cn") or ""),
                    "method": record["method"],
                    # 第 2 维（职责清晰度）要用：能力簇 / 动词类别 / 业务对象
                    "cluster": str(target.get("cluster") or ""),
                    "verb_class": str(target.get("verb_class") or ""),
                    "verb_cn": str(target.get("verb_cn") or ""),
                    "entity": str(target.get("entity") or ""),
                }
            )

        entry = {
            "key": key,
            "name_cn": str(target.get("name_cn") or ""),
            "cluster": str(target.get("cluster") or ""),
            "verb_class": str(target.get("verb_class") or ""),
            "entity": str(target.get("entity") or ""),
            "entity_cn": str(target.get("entity_cn") or ""),
            "related_flow": str(target.get("related_flow") or ""),
            "aliases": [str(a) for a in (target.get("aliases") or [])],
            "matched_modules": hits,
        }
        (matched if hits else missing).append(entry)

    unrecognized: List[Dict[str, Any]] = []
    for module in student:
        if not per_module_hits[module["module_id"]]:
            unrecognized.append(
                {
                    "module_id": module["module_id"],
                    "name": module["name"],
                    "normalized": module["normalized"],
                }
            )

    total = len(matched) + len(missing)
    return {
        "algorithm_version": ALGORITHM_VERSION,
        "matched": matched,
        "missing": missing,
        "unrecognized_modules": unrecognized,
        "module_hits": [
            {
                "module_id": module["module_id"],
                "name": module["name"],
                "matched_must_have": per_module_hits[module["module_id"]],
            }
            for module in student
        ],
        "counts": {
            "modules": len(student),
            "must_have": total,
            "matched": len(matched),
            "missing": len(missing),
            "unrecognized_modules": len(unrecognized),
        },
    }


def find_names_in_text(names: Iterable[Any], text: Any) -> List[str]:
    """一段自由文本里出现了哪些（已知词表里的）名字。

    用途：第 6 维「设计理由里提到的模块名是否真的在图上」。
    **只查已知词表，不做中文分词** —— 系统列不出「你提到的、词表里没有的名字」，
    这一条限制必须写进报告的 ``caveats``，不许假装做得到。

    命中判定同样复用阶段一的 ``coverage.key_hit``（中文按子串、英文按整词）。
    """
    _normalized, compact, tokens = cov.prepare_text(text)
    if not compact:
        return []
    found: List[str] = []
    for name in names:
        raw = str(name or "")
        key = cov.normalize_text(raw)
        if not key:
            continue
        if cov.key_hit(key, compact, tokens) and raw not in found:
            found.append(raw)
    return found
