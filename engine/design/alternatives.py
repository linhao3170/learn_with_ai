"""可接受替代结构与禁止合并项（README §4 阶段四 / §9.1 ``alternatives.py``）。

README 阶段四的原话是：

    系统不能只判断「和标准答案是否完全一致」，因为业务设计存在多种合理方案。
    应采用「标准逻辑图 + 可接受替代结构」。

所以任务对象里有两个字段：

- ``acceptable_alternatives``：**允许**的多种结构（例如「审批可以独立成模块，也可以归入借用流程」）；
- ``forbidden_merges``：**明确不允许**的合并（例如「审批不能和申请合并，因为它们是两个角色的职责」）。

本模块只做这两件事的判定，输出信号（``ALT_ACCEPTED`` / ``ALT_FORBIDDEN_MERGE``），
不判「哪个方案更好」，也不给分。

诚实边界（必须写进报告）
========================
1. **自动生成的任务没有这两份清单**（它们只能来自教师种子 ``design_tasks.seed.json``，
   因为「哪些合并可接受」是业务判断，规则引擎不许自己编）。
   这时 ``available = False``，并写明「本轮不做结构偏好判定」——
   **不允许把「没有清单」当成「学生没有命中替代结构」**。
2. **判定只基于匹配结果**：学生的模块与必备能力的对应关系来自 ``matcher``；
   匹配不上的模块（``unrecognized``）不参与本模块判定（它们已经单独列出）。
3. 只认「必备能力 key」（``mh_*``），不认模块显示名 —— 名字是学生自己起的，
   拿名字判结构偏好等于用词表判分。
   （**判定**只认 key；但**输出给学生看的文案**必须是中文名，见 ``_display_names``。）
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

__all__ = [
    "ALGORITHM_VERSION",
    "evaluate_alternatives",
]

ALGORITHM_VERSION = "design-alternatives-1.0"


def _matched_module_ids(match: Dict[str, Any], key: str) -> List[str]:
    """某项必备能力被哪些学生模块承担（按匹配结果里的顺序，稳定）。"""
    for entry in match.get("matched") or []:
        if str(entry.get("key")) == str(key):
            return [str(item.get("module_id")) for item in entry.get("matched_modules") or []]
    return []


def _same_module(match: Dict[str, Any], left: str, right: str) -> bool:
    """两项必备能力是否被**同一个**模块承担。"""
    left_ids = set(_matched_module_ids(match, left))
    right_ids = set(_matched_module_ids(match, right))
    return bool(left_ids & right_ids)


def _different_modules(match: Dict[str, Any], left: str, right: str) -> bool:
    """两项必备能力是否被**不同**模块承担（两边都识别到才有意义）。"""
    left_ids = set(_matched_module_ids(match, left))
    right_ids = set(_matched_module_ids(match, right))
    if not left_ids or not right_ids:
        return False
    return not bool(left_ids & right_ids)


def _pairs(keys: Sequence[Any]) -> List[Tuple[str, str]]:
    """把 key 列表拆成不重复的两两组合（顺序稳定：``i < j``）。"""
    items = [str(key) for key in keys or []]
    return [(items[i], items[j]) for i in range(len(items)) for j in range(i + 1, len(items))]


def _display_names(task: Dict[str, Any], match: Dict[str, Any]) -> Dict[str, str]:
    """必备能力 key → 中文名（给 UI 与反馈文案用）。

    **为什么需要它**：``violations`` 里的 ``a`` / ``b`` 会被直接渲染给学生
    （``StageDesign.vue`` 的「禁止合并」列表与 ``ALT_FORBIDDEN_MERGE`` 模板），
    早先直接放的是种子里的内部 key（``mh_*``）——那属于 README §6.2 明令
    「学生界面绝不能出现」的内部实现标记。所以显示名统一在这里解析一次，
    原始 key 另存 ``a_key`` / ``b_key`` 供教师排查。

    名字来源按优先级：任务自己的 ``must_have``（最权威）→ ``match`` 里已经带上名字的项。
    """
    names: Dict[str, str] = {}
    for item in task.get("must_have") or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "")
        if key:
            names[key] = str(item.get("name_cn") or key)
    for bucket in ("matched", "missing"):
        for entry in match.get(bucket) or []:
            if not isinstance(entry, dict):
                continue
            key = str(entry.get("key") or "")
            if key and key not in names:
                names[key] = str(entry.get("name_cn") or key)
    return names


def evaluate_alternatives(
    task: Dict[str, Any],
    match: Dict[str, Any],
) -> Dict[str, Any]:
    """判定学生的结构选择是否落在教师给出的可接受区间内。

    :param task: 设计任务（``task_builder.build_design_task`` 的**完整版**，含两份清单）
    :param match: ``matcher.match_modules`` 的结果
    :returns: ``{"available", "reason_cn"|"", "accepted", "accepted_alternative", "violations"}``

    **没有清单时 ``available = False``**，且 ``accepted`` 为 ``None``（不是 ``False``）——
    「没判」与「没命中」必须严格区分。

    ``violations`` 的每一条形如
    ``{"a", "b", "a_key", "b_key", "reason_cn", "code"}``：
    ``a`` / ``b`` 是**中文显示名**（直接进学生界面），``a_key`` / ``b_key`` 才是种子里的 key。
    """
    alternatives = [item for item in (task.get("acceptable_alternatives") or []) if isinstance(item, dict)]
    forbidden = [item for item in (task.get("forbidden_merges") or []) if isinstance(item, dict)]

    violations: List[Dict[str, Any]] = []
    names = _display_names(task, match)
    for item in forbidden:
        left = str(item.get("a") or "")
        right = str(item.get("b") or "")
        if not left or not right:
            continue
        if _same_module(match, left, right):
            violations.append(
                {
                    # a / b 是给学生看的显示名；原始 key 留在 a_key / b_key（README §6.2）
                    "a": names.get(left, left),
                    "b": names.get(right, right),
                    "a_key": left,
                    "b_key": right,
                    "reason_cn": str(item.get("reason_cn") or ""),
                    "code": "ALT_FORBIDDEN_MERGE",
                }
            )

    if not alternatives and not forbidden:
        return {
            "algorithm_version": ALGORITHM_VERSION,
            "available": False,
            "reason_cn": (
                "本任务没有教师给定的可接受替代结构与禁止合并项"
                "（自动生成的任务只做必备能力覆盖，不判结构偏好），因此本轮不做结构偏好判定。"
            ),
            "accepted": None,
            "accepted_alternative": None,
            "accepted_alternative_ids": [],
            "violations": [],
        }

    accepted_ids: List[str] = []
    accepted_names: List[str] = []
    for item in alternatives:
        merge_keys = item.get("merge_keys") or []
        separate_keys = item.get("separate_keys") or []
        pairs = _pairs(merge_keys)
        separate_pairs = _pairs(separate_keys)
        if not pairs and not separate_pairs:
            # 两份清单都空 = 这条替代结构没法判定（不给它记「命中」，也不记「未命中」）
            continue
        hit = True
        for left, right in pairs:
            if not _same_module(match, left, right):
                hit = False
                break
        if hit:
            for left, right in separate_pairs:
                if not _different_modules(match, left, right):
                    hit = False
                    break
        if hit:
            accepted_ids.append(str(item.get("alternative_id") or item.get("name_cn") or ""))
            accepted_names.append(str(item.get("name_cn") or item.get("alternative_id") or ""))

    return {
        "algorithm_version": ALGORITHM_VERSION,
        "available": True,
        "reason_cn": "",
        "accepted": bool(accepted_ids),
        "accepted_alternative": accepted_names[0] if accepted_names else None,
        "accepted_alternative_ids": accepted_ids,
        "violations": violations,
    }
