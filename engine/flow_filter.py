"""
流程过滤器（P0-06 / README5 §3.4）

问题
----
"初始化 / 造样例数据"这类流程会调用很多管理器，因此在按调用量排序时
常常排到第一位。``LabSafetyApp Initialization Flow`` 就曾经被当成
"最核心的业务流程"展示给学生，并被用来出"流程推演"题 —— 这是**教学性错误**：
它教的是"核心业务 = 造样例数据"。

现状
----
``engine/deep_analyzer/business_priority.py`` 里已经有一个 ``_operational_factor``
（``setup_markers`` + ``factor=0.2``），但它只在 BLPS 的**流程优先级分数**里生效；
``ProjectAnalyzer.core_flows``、``TrainingGenerator`` 第 3 关都没有用它，
所以三个地方对"哪条流程最重要"的判断互相矛盾。

本模块把这段规则抽成**唯一实现**，供三处共用：

- ``ProjectAnalyzer``：把生命周期流程排到列表末尾（保留，不删除）；
- ``TrainingGenerator``：优先选非生命周期流程出题；
- ``BusinessPriorityAnalyzer``：沿用它做降权系数。

纪律
----
本模块只做**排序与降权**，不删除任何流程，也不把流程判定成"业务/非业务"的
确定结论 —— ``is_lifecycle_flow`` 为真只意味着"它更像初始化/样例数据"，
置信度是 ``inferred``。

词汇来源
--------
默认词表内联在这里；README5 计划把它迁到 ``engine/lexicon/lifecycle.json``
（教师可编辑）。迁移时只需替换 :func:`_markers` 的实现，调用方不用改。
"""

from __future__ import annotations

from typing import Any, Iterable, List, Sequence

__all__ = [
    "LIFECYCLE_MARKERS",
    "LIFECYCLE_FACTOR",
    "is_lifecycle_flow",
    "lifecycle_score",
    "sort_flows_business_first",
    "pick_primary_flow",
]

#: 命中任一标记即认为是"生命周期 / 样例数据"流程（inferred）
LIFECYCLE_MARKERS = (
    "initialize",
    "initialise",
    "init",
    "bootstrap",
    "seed",
    "sample_data",
    "sampledata",
    "setup",
    "fixture",
    "populate",
    "demo_data",
)

#: 降权系数（README2 §19.2 的 q=0.2，保持口径不变）
LIFECYCLE_FACTOR = 0.2


def _markers() -> Sequence[str]:
    """返回生命周期标记词。将来从 ``engine/lexicon/lifecycle.json`` 读取。"""
    return LIFECYCLE_MARKERS


def _flow_texts(flow: Any) -> List[str]:
    """收集一条流程里所有可用于判定的文本（名称 / 入口 / 首步 / 步骤名）。

    传入的 ``flow`` 可能是 ``BusinessFlow``（deep_analyzer）或 ``CoreFlow``
    （project_analyzer）或一个 dict，三者字段名不同，这里统一兼容。
    """
    texts: List[str] = []

    def _collect(source, keys: Iterable[str]) -> None:
        for key in keys:
            value = source.get(key) if isinstance(source, dict) else getattr(source, key, None)
            if isinstance(value, str) and value:
                texts.append(value.lower())

    _collect(flow, ("name", "flow_name", "entry_node", "entry", "flow_id"))

    steps = flow.get("steps") if isinstance(flow, dict) else getattr(flow, "steps", None)
    if isinstance(steps, list) and steps:
        for step in steps[:3]:
            _collect(step, ("name", "method", "method_name", "node_id", "description"))
    return texts


def lifecycle_score(flow: Any) -> int:
    """返回命中的生命周期标记个数（0 表示不像生命周期流程）。"""
    texts = _flow_texts(flow)
    return sum(1 for marker in _markers() if any(marker in text for text in texts))


def is_lifecycle_flow(flow: Any) -> bool:
    """判断一条流程是否更像"初始化 / 样例数据"流程。

    Returns:
        ``True`` 表示命中生命周期标记。这是 ``inferred`` 级别的判断，
        **不能**当作"该流程不是业务"的确定结论。
    """
    return lifecycle_score(flow) > 0


def sort_flows_business_first(flows: Sequence[Any]) -> List[Any]:
    """按"业务优先、生命周期靠后"稳定排序。

    排序键为 ``(是否生命周期, 原始下标)``，因此：

    - 非生命周期流程保持原有相对顺序；
    - 生命周期流程被移到末尾，但**一条都不丢**；
    - 同一份输入永远得到同一份输出（可复现）。
    """
    indexed = list(enumerate(flows or []))
    indexed.sort(key=lambda pair: (1 if is_lifecycle_flow(pair[1]) else 0, pair[0]))
    return [flow for _, flow in indexed]


def pick_primary_flow(flows: Sequence[Any]) -> Any:
    """挑出"最适合作为教学主流程"的一条；没有则返回 ``None``。

    规则：第一条非生命周期流程；若全都是生命周期流程，则诚实退回第一条
    （不返回 None —— 因为"这个项目只有初始化流程"本身就是有效信息）。
    """
    if not flows:
        return None
    ordered = sort_flows_business_first(flows)
    return ordered[0]
