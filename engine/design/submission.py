"""``design_submission.json`` 的归一化与入口校验（README §10.4 的契约落点）。

为什么单独一个模块（README 的 §16.3 文件清单里没有它）
====================================================
契约归一化不属于「任务生成 / 匹配 / 结构检查 / 评分 / 反馈」中的任何一项，
但它必须**只有一份实现**：画布提交的 JSON、离线演示的 JSON、测试里的合成 JSON
都要经过同一个入口，否则「前端多传一个字段」和「引擎少读一个字段」这类问题
永远只能靠肉眼发现。所以它是 ``engine/design/`` 的第 8 个文件，
并在 README 第十六章里登记（新增文件必须登记，不许只在代码里存在）。

契约（§10.4）
=============
::

    {"contract_version": "1.0", "submission_id": "sub_001", "task_id": "dt_...",
     "iteration": 2,
     "modules": [{"module_id": "m1", "name": "用户权限", "level": 1, "parent_id": null,
                  "objective": "...", "inputs": [...], "outputs": [...], "does_not": "...",
                  "business_rules": [...], "state_changes": [...], "exceptions": [...],
                  "depends_on": []}],
     "relations": [{"from": "m3", "to": "m1", "type": "uses"}],
     "flow_designs": [], "design_rationale": "..."}

兼容写法（引擎据实归一，不猜语义）
==================================
- ``does_not`` / ``depends_on`` / ``inputs`` / ``outputs`` / ``business_rules`` /
  ``state_changes`` / ``exceptions``：契约里是字符串的字段也接受数组（阶段二的卡片就是数组）；
- ``name`` 与 ``name_cn`` 互为别名（README §10.1 那个「三套并存」的教训：契约字段统一到
  ``name_cn`` 之后，学生设计这一层用的是 ``name``，两个都认，但**归一化后只留一个**）；
- ``module_id`` 缺失时按提交顺序补 ``m1..mN``（画布一定会给，补号是为了让手写 JSON 也能跑）。

做不到的事
==========
- **不猜意图**：不认识的字段不报错也不使用（``unknown_fields`` 里如实列出键名），
  不做「智能补全」——补出来的结构会让学生以为是自己画的；
- **不做中文分词**：``does_not`` 这类自由文本只做长度与空值判定。
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

__all__ = [
    "CONTRACT_VERSION",
    "SUBMISSION_VERSION",
    "MAX_MODULES",
    "MAX_RELATIONS",
    "MAX_NAME_CHARS",
    "MAX_TEXT_CHARS",
    "MAX_RATIONALE_CHARS",
    "KNOWN_MODULE_FIELDS",
    "normalize_submission",
    "empty_submission",
    "structural_issues",
]

CONTRACT_VERSION = "1.0"
SUBMISSION_VERSION = "1.0"

#: 入口上限（后端在入口处拦截，这里是第二道闸；画布是给人用的，不是给机器刷的）
MAX_MODULES = 60
MAX_RELATIONS = 200
MAX_NAME_CHARS = 60
MAX_TEXT_CHARS = 400
MAX_RATIONALE_CHARS = 4000

#: 引擎认识的模块字段（其余字段进 ``unknown_fields``，如实列出但不使用）
KNOWN_MODULE_FIELDS = (
    "module_id", "name", "name_cn", "level", "parent_id", "objective",
    "inputs", "outputs", "does_not", "business_rules", "state_changes",
    "exceptions", "depends_on",
)

#: 列表型字段
_LIST_FIELDS = (
    "inputs", "outputs", "does_not", "business_rules", "state_changes", "exceptions", "depends_on",
)


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _clip(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[:limit]


def _string_list(value: Any, limit: int = MAX_TEXT_CHARS) -> List[str]:
    """把 str / list 统一成去空、去重（保持顺序）的字符串列表。"""
    if value is None:
        return []
    raw: Sequence[Any]
    if isinstance(value, (list, tuple)):
        raw = value
    else:
        raw = [value]
    out: List[str] = []
    for item in raw:
        text = _clip(_text(item), limit)
        if text and text not in out:
            out.append(text)
    return out


def _level(value: Any) -> int:
    """层级：契约里是整数；解析不出来时**默认 1**（不猜 2、不按模块数推断）。"""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 1
    return parsed if parsed > 0 else 1


def normalize_submission(raw: Any) -> Dict[str, Any]:
    """把提交的 JSON 归一化成引擎内部结构（幂等：对归一化结果再跑一次结果不变）。

    :param raw: 画布 / 测试提交的原始对象
    :returns: ``{"contract_version", "submission_id", "task_id", "iteration",
              "modules", "relations", "flow_designs", "design_rationale",
              "unknown_fields", "truncated"}``

    **空输入也返回结构**（``modules == []``）：本函数不做「不许空提交」的判定 ——
    那是后端入口的职责（``teaching_service``），本层只保证结构可被后续模块消费。
    """
    raw = raw if isinstance(raw, dict) else {}
    truncated = False

    modules_raw = raw.get("modules")
    modules_raw = modules_raw if isinstance(modules_raw, list) else []
    if len(modules_raw) > MAX_MODULES:
        modules_raw = modules_raw[:MAX_MODULES]
        truncated = True

    modules: List[Dict[str, Any]] = []
    # 归一化产物里已经记过的未知字段要**带下去**：否则对产物再跑一次，
    # 「哪些字段引擎没认」这条记录会消失，归一化就不是幂等的
    unknown_fields: List[str] = []
    if isinstance(raw.get("unknown_fields"), list):
        for item in raw["unknown_fields"]:
            text = _text(item)
            if text and text not in unknown_fields:
                unknown_fields.append(text)
    for index, item in enumerate(modules_raw):
        if not isinstance(item, dict):
            continue
        for key in item.keys():
            key_text = str(key)
            if key_text not in KNOWN_MODULE_FIELDS and key_text not in unknown_fields:
                unknown_fields.append(key_text)

        module_id = _text(item.get("module_id")) or f"m{index + 1}"
        name = _clip(_text(item.get("name") or item.get("name_cn")), MAX_NAME_CHARS)
        parent_id = _text(item.get("parent_id")) or None
        module: Dict[str, Any] = {
            "module_id": module_id,
            "name": name,
            "level": _level(item.get("level")),
            "parent_id": parent_id,
            "objective": _clip(_text(item.get("objective")), MAX_TEXT_CHARS * 3),
        }
        for field in _LIST_FIELDS:
            module[field] = _string_list(item.get(field))
        modules.append(module)

    relations_raw = raw.get("relations")
    relations_raw = relations_raw if isinstance(relations_raw, list) else []
    if len(relations_raw) > MAX_RELATIONS:
        relations_raw = relations_raw[:MAX_RELATIONS]
        truncated = True

    relations: List[Dict[str, Any]] = []
    for item in relations_raw:
        if not isinstance(item, dict):
            continue
        source = _text(item.get("from"))
        target = _text(item.get("to"))
        if not source or not target:
            continue
        relations.append({"from": source, "to": target, "type": _text(item.get("type")) or "uses"})

    flow_designs_raw = raw.get("flow_designs")
    flow_designs: List[Dict[str, Any]] = []
    if isinstance(flow_designs_raw, list):
        for item in flow_designs_raw:
            if not isinstance(item, dict):
                continue
            steps: List[Dict[str, Any]] = []
            for order, step in enumerate(item.get("steps") or [], start=1):
                if not isinstance(step, dict):
                    continue
                steps.append(
                    {
                        "order": order,
                        "module_id": _text(step.get("module_id")),
                        "text": _clip(_text(step.get("text") or step.get("name_cn")), MAX_TEXT_CHARS),
                        "is_state_change": bool(step.get("is_state_change")),
                    }
                )
            flow_designs.append(
                {
                    "flow_id": _text(item.get("flow_id")) or f"flow_{len(flow_designs) + 1}",
                    "name_cn": _clip(_text(item.get("name_cn") or item.get("name")), MAX_NAME_CHARS),
                    "steps": steps,
                }
            )

    try:
        iteration = int(raw.get("iteration") or 1)
    except (TypeError, ValueError):
        iteration = 1
    if iteration < 1:
        iteration = 1

    for key in raw.keys():
        key_text = str(key)
        if key_text in ("modules", "relations", "flow_designs") or key_text in unknown_fields:
            continue
        if key_text not in (
            "contract_version", "submission_id", "task_id", "iteration", "design_rationale",
            # 归一化产物自身的字段：认它们，归一化才是幂等的（对产物再跑一次结果不变）
            "submission_version", "unknown_fields", "truncated",
        ):
            unknown_fields.append(key_text)

    return {
        "contract_version": CONTRACT_VERSION,
        "submission_version": SUBMISSION_VERSION,
        "submission_id": _text(raw.get("submission_id")),
        "task_id": _text(raw.get("task_id")),
        "iteration": iteration,
        "modules": modules,
        "relations": relations,
        "flow_designs": flow_designs,
        "design_rationale": _clip(_text(raw.get("design_rationale")), MAX_RATIONALE_CHARS),
        "unknown_fields": unknown_fields,
        "truncated": truncated,
    }


def empty_submission(**overrides: Any) -> Dict[str, Any]:
    """一份空提交（测试与「画布还没画」的场景用；结构与本模块的返回完全一致）。"""
    payload: Dict[str, Any] = {
        "submission_id": "sub_empty",
        "task_id": "",
        "iteration": 1,
        "modules": [],
        "relations": [],
        "flow_designs": [],
        "design_rationale": "",
    }
    payload.update(overrides)
    return normalize_submission(payload)


def structural_issues(submission: Dict[str, Any]) -> List[Dict[str, Any]]:
    """提交本身的结构性问题（不是设计质量问题）。

    目前查三件事，全部是「数据完整性」级别，不涉及语义判断：

    1. 一个模块都没有 → ``SUBMISSION_EMPTY_MODULES``；
    2. 重名模块 → ``SUBMISSION_DUPLICATE_NAME``（重名让职责边界无法核查）；
    3. ``parent_id`` 指向不存在的模块 → ``SUBMISSION_UNKNOWN_PARENT``。

    返回 ``[{"code", "params"}]``，由 ``rubric`` 交给 ``feedback`` 渲染成中文。
    """
    issues: List[Dict[str, Any]] = []
    modules = [m for m in (submission.get("modules") or []) if isinstance(m, dict)]
    if not modules:
        issues.append({"code": "SUBMISSION_EMPTY_MODULES", "params": {}})
        return issues

    known: List[str] = [str(m.get("module_id") or "") for m in modules]
    by_name: Dict[str, List[str]] = {}
    for module in modules:
        name = _text(module.get("name"))
        if not name:
            continue
        by_name.setdefault(name, []).append(str(module.get("module_id") or ""))
    for name, ids in by_name.items():
        if len(ids) > 1:
            issues.append(
                {"code": "SUBMISSION_DUPLICATE_NAME", "params": {"name": name, "n": len(ids), "module_ids": "、".join(ids)}}
            )

    for module in modules:
        parent = _text(module.get("parent_id"))
        if parent and parent not in known:
            issues.append(
                {
                    "code": "SUBMISSION_UNKNOWN_PARENT",
                    "params": {"module": _text(module.get("name")) or str(module.get("module_id")), "parent": parent},
                }
            )
    return issues
