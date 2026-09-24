"""项目大小 → 处理策略（业务逻辑分析平台的「分流层」）

这份文件回答一个问题：**同一个分析平台，面对 200 行的脚本和 20000 行的库，
凭什么给出不同的处理？**

设计立场（先写清楚，免得被当成"AI 智能判断规模"）
--------------------------------------------------
1. **大小来自现有引擎，不新造一套。** 级别取 ``business_graph.complexity`` 的
   ``level``（L1–L4），定级依据由 ``complexity.py`` 写在 ``level_basis`` 里，
   本模块**只读不改**，也不做第二次定级 —— 「同一个不变量只允许有一个实现」
   （README §2.2 铁律 4，来自 1054 处路径失真的真实事故）。
2. **分流的是"讲多少"，不是"判什么"。** 级别只影响**预算**：展开几个板块、
   给几个能力点生成沉浸式课程、每课最多几段、每段最多几行。
   它**不参与**任何事实判定 —— 事实永远来自 AST，与项目大小无关。
3. **预算数字是工程常数，标注为待实测校准。** 它们不是从数据里学出来的，
   是拍出来的。所以对外表述必须带 ``caveat``，不许包装成"智能评估"。

为什么必须分流（而不是一律全量展开）
------------------------------------
- 对小项目全量展开是对的：L1 只有 1–5 个域，看完不吃力，藏起来反而有害。
- 对大项目全量展开是**错的**：urllib3 有 19 个域，全量生成沉浸式课程意味着
  学生拿到一份读不完的材料 —— README §5 的原话是
  「**小项目不能生成过重的训练，复杂项目也不能只给四道题**」，
  流分的意义是让材料量与项目规模匹配。
- 所以 L3/L4 采用**核心优先 + 显式截断**：只对核心排序前 N 个能力点生成课程，
  其余板块照常展示分析（证据齐全），但课程入口标注「未展开（超出本级预算）」。
  **截断必须可见**，不能悄悄少给 —— 这是"不美化数据"纪律的直接推论。
"""

from __future__ import annotations

from typing import Dict, List, Optional

ALGORITHM_VERSION = "tiering-1.0"

#: 预算表。键是 ``complexity.level`` 的取值，缺项按 L1 处理（保守：少展开总比爆掉好）。
#:
#: 每个字段的含义
#: --------------
#: ``tier_label``                处理策略的中文名（给学生看的一句话概括）
#: ``section_budget``            一级板块最多展示几个（None = 不限）
#: ``capability_budget``         全部板块加起来最多展示几个能力点（None = 不限）
#: ``walkthrough_capability_budget``   最多给几个能力点生成沉浸式课程（None = 不限）
#: ``walkthrough_selection``     选哪些能力点：``all`` / ``core_ranked``
#: ``segments_per_lesson_cap``   单课最多几段（对应参考文档「第 N 段」，9 段是母本上限）
#: ``statements_per_segment_cap`` 单段最多几行源码（母本第 6 段 279-345 是 67 行上限，
#:                                但那一段内部又按「情况A/B/C」二次分块；这里取 40 行）
#: ``analysis_depth``            板块分析的展开程度：``full`` / ``prioritized`` / ``sampled``
#: ``rationale``                 为什么这个级别这么处理（中文，直接给学生/教师看）
#: ``student_note``              学生在这个级别应该期待什么
TIER_PLANS: Dict[str, Dict[str, object]] = {
    "L1": {
        "tier_label": "全量展开",
        "section_budget": None,
        "capability_budget": None,
        "walkthrough_capability_budget": None,
        "walkthrough_selection": "all",
        "segments_per_lesson_cap": 24,
        "statements_per_segment_cap": 40,
        "analysis_depth": "full",
        "rationale": (
            "L1 项目只有 1–5 个一级模块、结构简单，全量展开不会造成阅读负担。"
            "把内容藏起来反而有害：学生会误以为系统没分析出来。"
        ),
        "student_note": "规模小，所有板块与所有能力点都会展开，可以逐块看完。",
    },
    "L2": {
        "tier_label": "全量板块 + 全量课程",
        "section_budget": None,
        "capability_budget": None,
        "walkthrough_capability_budget": 12,
        "walkthrough_selection": "all",
        "segments_per_lesson_cap": 20,
        "statements_per_segment_cap": 40,
        "analysis_depth": "full",
        "rationale": (
            "L2 是「多模块项目」：板块数量还看得完，但能力点开始变多。"
            "板块分析全量给（证据不藏），课程按能力点数量设 12 个的上限，避免课程列表本身变成压力。"
        ),
        "student_note": "板块全部展开；沉浸式课程优先给核心能力点，超出上限的会显式标注未展开。",
    },
    "L3": {
        "tier_label": "核心优先",
        "section_budget": None,
        "capability_budget": 40,
        "walkthrough_capability_budget": 10,
        "walkthrough_selection": "core_ranked",
        "segments_per_lesson_cap": 16,
        "statements_per_segment_cap": 32,
        "analysis_depth": "prioritized",
        "rationale": (
            "L3 是「复杂业务项目」：10–25 个模块、多角色、多条流程。"
            "全量生成课程会产出读不完的材料，所以按核心度排序取前 10 个能力点做课程；"
            "其余板块仍然展示完整分析（含证据），只是课程入口标注「超出本级预算，未展开」。"
        ),
        "student_note": "板块全部可看；沉浸式课程只覆盖核心能力点，未覆盖的会明确标注，不会假装讲过了。",
    },
    "L4": {
        "tier_label": "核心优先 + 抽样",
        "section_budget": 24,
        "capability_budget": 48,
        "walkthrough_capability_budget": 8,
        "walkthrough_selection": "core_ranked",
        "segments_per_lesson_cap": 14,
        "statements_per_segment_cap": 28,
        "analysis_depth": "sampled",
        "rationale": (
            "L4 是「综合设计项目」：25 个以上模块、多外部系统。此时「全部讲完」不是目标也不现实；"
            "平台改为先给核心板块地图，再对核心度最高的 8 个能力点做精读课程，"
            "用于建立「这类项目该怎么读」的方法，而不是覆盖全部代码。"
        ),
        "student_note": "这是大型项目：平台给你核心地图 + 少量精读样本，用来学方法，不承诺覆盖全部业务。",
    },
}

#: 兜底计划（级别缺失或未知时使用）—— 取最保守的一档，且**必须**在 caveat 里说明。
FALLBACK_LEVEL = "L1"

#: 预算表的口径声明。会原样带进每个响应，前端必须显示。
TIER_CAVEAT = (
    "分级预算（展开数量 / 课程数量 / 段行上限）是工程常数，用于让材料量与项目规模匹配，"
    "不是从实测数据学出来的，标注为待实测校准；级别本身来自 business_graph.complexity "
    "（结构定义判定），本模块只读不改，不参与任何事实判定。"
)


def plan_for_level(level: Optional[str]) -> Dict[str, object]:
    """取某个级别的处理计划（返回副本，调用方改不动全局表）。

    未知/缺失级别一律回落到 :data:`FALLBACK_LEVEL`，并在返回值里把
    ``level_known`` 置 False —— 让前端能如实显示「级别未知，按最保守策略处理」，
    而不是假装算出了一个级别。
    """
    key = str(level or "").strip().upper()
    known = key in TIER_PLANS
    plan = dict(TIER_PLANS[key if known else FALLBACK_LEVEL])
    plan["level"] = key if known else ""
    plan["level_known"] = known
    plan["fallback_level"] = None if known else FALLBACK_LEVEL
    plan["algorithm_version"] = ALGORITHM_VERSION
    plan["caveat"] = TIER_CAVEAT
    return plan


def level_order() -> List[str]:
    """级别由低到高（固定顺序，供前端排序与测试断言用）。"""
    return ["L1", "L2", "L3", "L4"]


def effective_budget(plan: Dict[str, object], key: str, total: int) -> Dict[str, object]:
    """把一个预算字段算成 ``{"budget", "total", "shown", "truncated"}``。

    **截断必须可见**：调用方拿到 ``truncated=True`` 时，界面必须显示
    「共 N 项，本级策略展示前 M 项」。这是"不美化数据"纪律的落地方式 ——
    宁可让学生看到"没讲完"，也不能让他以为"就这么多"。
    """
    budget = plan.get(key)
    if budget is None:
        shown = total
    else:
        shown = min(int(budget), total)
    return {
        "budget": budget,
        "total": int(total),
        "shown": int(shown),
        "truncated": bool(budget is not None and total > int(budget)),
    }
