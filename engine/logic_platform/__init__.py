"""业务逻辑分析平台引擎（``engine/logic_platform``）

一条流水线，六个阶段
--------------------
::

    投入项目
      │
      ├─ 1. sizing     analyze_size(...)        分析项目大小 → L1–L4 + 结构规模（带来源）
      │
      ├─ 2. tiering    plan_for_level(...)      按大小选处理策略（展开多少 / 讲多少）
      │
      ├─ 3. sections   build_sections(...)      产出业务板块（**无论大小都产出**）
      │
      ├─ 4. lesson     build_lesson(...)        单个能力点的沉浸式讲解（逐段 + 证据）
      │
      ├─ 5. verify     verify_and_apply(...)    确定性校验：重读源码 + 重解析 AST
      │
      └─ 6. narration  apply_narration(...)     可选的 LLM 讲解层（默认关闭，逐条把关）

本包的三条纪律
--------------
1. **无 LLM、无网络、无随机、无时间依赖。** 全部走 stdlib ``ast``。
   这不是风格偏好 —— ``scripts/test_teaching_coverage.py`` 等三个测试里
   写死了 ``FORBIDDEN_IMPORTS``，本包一旦联网，那三个测试立刻红。
   LLM 讲解层的**调用**在 ``backend/app/services/narration_service.py``，
   本包只定义契约与把关逻辑（``narration.py``）。
2. **确定性逐字节可复现。** 所有遍历都排序；输出里不含 ``set`` 遍历顺序；
   同一份源码两次调用结果一致。
3. **无证据不入学生视图。** 每一条结论都带
   ``file`` + ``start_line`` + ``end_line`` + 真实摘录 + ``excerpt_hash``；
   校验器拦下的条目保留原文并标红，**不静默删除**。

与既有引擎的关系（复用，不重造）
--------------------------------
- 定级、域、能力点、事实、流程、模块卡片 → 全部来自 ``engine.business_graph``；
- 核心度排序 → 复用 ``engine.design.task_builder`` 的 ``_capability_entries`` /
  ``_importance``（同一份实现，两个用途）；
- 逐语句遍历思路 → 与 ``engine.visualizer.flowchart`` 同源，但这里做分段而非画图；
- 源码读取 → 生成用 ``engine.parser.ast_cache``，**校验时刻意绕开它**
  （校验器必须读磁盘上的真文件，不能读自己的记忆）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import hashing, modules, narration, sizing, tiering, verify, walkthrough

#: 本包对外契约版本（前端启动时校验；与 engine 的 contract_version 独立）
PLATFORM_VERSION = "lp-1.0"

__all__ = [
    "PLATFORM_VERSION",
    "hashing",
    "sizing",
    "tiering",
    "modules",
    "walkthrough",
    "verify",
    "narration",
    "analyze_project",
    "build_lesson_for",
]


def analyze_project(
    project_id: str,
    project_name: str,
    overview: Optional[Dict[str, Any]],
    graph: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """阶段 1–3：大小 → 策略 → 业务板块。

    不读源码、不生成讲稿，因此很快，适合"投入项目后立刻返回"的第一步。
    讲稿（阶段 4–6）按需对单个能力点生成 —— 一个大项目不该在点击前
    就把几十课的讲稿全算出来。
    """
    size = sizing.analyze_size(project_id, project_name, overview, graph)
    size_dict = size.to_dict()
    board = modules.build_sections(project_id, project_name, graph, size.tier)
    board_dict = board.to_dict()

    return {
        "platform_version": PLATFORM_VERSION,
        "project_id": str(project_id or ""),
        "project_name": str(project_name or ""),
        "size": size_dict,
        "sections": board_dict,
        "caveats": list(dict.fromkeys(size_dict.get("caveats", []) + board_dict.get("caveats", []))),
    }


def build_lesson_for(
    analysis: Dict[str, Any],
    capability_id: str,
    source_root: str,
    graph: Optional[Dict[str, Any]] = None,
    lesson_number: int = 1,
    run_verification: bool = True,
) -> Dict[str, Any]:
    """阶段 4–5：为某个能力点生成一课并校验。

    返回的 lesson 里 ``review.can_publish`` 只有在**零失败**时才为 True，
    且那也仍不是"可以发布给学生"的意思 —— 还差教师确认（阶段 6）。

    ``graph`` 用于把「调用了哪个函数」翻译成「哪个能力点」，
    以及取 ``level`` / ``source_hash``。它不参与任何事实判定。
    """
    analysis = analysis if isinstance(analysis, dict) else {}
    board = analysis.get("sections") if isinstance(analysis.get("sections"), dict) else {}
    size = analysis.get("size") if isinstance(analysis.get("size"), dict) else {}
    graph = graph if isinstance(graph, dict) else {}

    capability: Optional[Dict[str, Any]] = None
    section: Optional[Dict[str, Any]] = None
    for candidate_section in board.get("sections") or []:
        if not isinstance(candidate_section, dict):
            continue
        for candidate in candidate_section.get("capabilities") or []:
            if isinstance(candidate, dict) and str(candidate.get("capability_id")) == str(capability_id):
                capability = candidate
                section = candidate_section
                break
        if capability is not None:
            break

    if capability is None or section is None:
        return {
            "ok": False,
            "error": f"板块看板里没有这个能力点：{capability_id}",
            "error_kind": "capability_not_found",
        }

    lesson = walkthrough.build_lesson(
        project_id=str(analysis.get("project_id") or ""),
        capability=capability,
        section=section,
        graph=graph,
        source_root=source_root,
        tier=(size.get("tier") if isinstance(size.get("tier"), dict) else {}),
        lesson_number=lesson_number,
    )
    lesson_dict = lesson.to_dict()
    if run_verification:
        verify.verify_and_apply(lesson_dict, source_root)
    return {"ok": True, "lesson": lesson_dict}
