"""培训功能：阶段一 / 二 / 四·五 的六个接口 —— ``docs/04`` §11.1，教学口径见 ``docs/01`` §4。

它承载的路由（**都不打分**，只有阶段四 / 五有分数）：

- ``POST /api/projects/{project_id}/teaching/orientation/coverage`` —— 阶段一覆盖度比对（Sprint 3）
- ``GET  /api/projects/{project_id}/teaching/module-card/task`` —— 阶段二任务包（Sprint 4）
- ``POST /api/projects/{project_id}/teaching/module-card/coverage`` —— 阶段二事实覆盖比对（Sprint 4）
- ``GET  /api/projects/{project_id}/teaching/design/tasks`` —— 阶段四设计任务清单（Sprint 5）
- ``GET  /api/projects/{project_id}/teaching/design/task`` —— 取一道设计任务（``?mode=teacher``）
- ``POST /api/projects/{project_id}/teaching/design/evaluate`` —— 阶段四 / 五 六维评审（Sprint 5）

判定实现只有一份，全在 ``engine/`` 里（``teaching/coverage.py`` / ``teaching/card_coverage.py`` /
``design/rubric.py``），本文件只把 ``(状态码, 中文说明)`` 翻成 ``HTTPException``。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

try:  # noqa: E402 - 与 main.py 相同的双入口兼容
    from app.services import teaching_service
except ModuleNotFoundError:  # pragma: no cover - depends on launch directory
    from backend.app.services import teaching_service

router = APIRouter()


@router.post("/api/projects/{project_id}/teaching/orientation/coverage")
async def orientation_coverage(project_id: str, payload: dict):
    """阶段一「项目认知」的覆盖度比对。

    请求体：``{"text": "学生用自己的话写的一段回答"}``

    响应：覆盖度报告（``engine/teaching/coverage.py`` 的产物）——
    ``covered`` / ``missed`` / ``not_comparable`` 三份清单 + ``counts`` + ``caveats``。
    **没有分数、没有标准答案**：阶段一明确"系统只输出覆盖度报告，不打分"。

    离线模式下前端不会走到这里（判定通道只在后端）；这里不做离线兜底，也不返回任何答案字段。
    """
    text = payload.get("text")
    if text is None:
        text = payload.get("answer")
    report, error = teaching_service.evaluate_orientation_for_project(project_id, text)
    if error is not None:
        status, detail = error
        raise HTTPException(status_code=status, detail=detail)
    return report


@router.get("/api/projects/{project_id}/teaching/module-card/task")
async def module_card_task(project_id: str):
    """阶段二的任务包：五个问题 + 本项目全部模块卡片。

    题目文本与「问题 → 参与比对的字段」映射在 ``engine/lexicon/stage_questions.json``，
    卡片内容来自该项目的 ``business_graph``。**前端不认识任何一个业务字段**：
    换一个项目、换一种问法，页面代码都不用改（README 第十八章验收项）。

    这里只下发"学什么"，**不下发任何比对键**——学生提交之前，页面上不该出现比对的答案。
    """
    task, error = teaching_service.build_module_card_task_for_project(project_id)
    if error is not None:
        status, detail = error
        raise HTTPException(status_code=status, detail=detail)
    return task


@router.post("/api/projects/{project_id}/teaching/module-card/coverage")
async def module_card_coverage(project_id: str, payload: dict):
    """阶段二的事实覆盖比对。

    请求体：``{"module_id": "c_xxx", "answers": {"q1_problem": "...", ...}}``

    响应：``engine/teaching/card_coverage.py`` 的产物 —— 每个问题的
    ``matched_keys`` / ``missed_keys`` / ``not_comparable_reason`` + ``counts`` + ``caveats``。
    **没有分数、没有标准答案**；置信度为 ``unconfirmed`` 的字段不参与比对，
    报告会显式提示「该卡片待教师确认」。

    离线模式下前端不会走到这里（判定通道只在后端）；这里不做离线兜底。
    """
    answers = payload.get("answers")
    if answers is None:
        answers = payload.get("responses")
    report, error = teaching_service.evaluate_module_card_for_project(
        project_id, payload.get("module_id"), answers
    )
    if error is not None:
        status, detail = error
        raise HTTPException(status_code=status, detail=detail)
    return report


@router.get("/api/projects/{project_id}/teaching/design/tasks")
async def design_task_list(project_id: str):
    """设计任务清单：按项目复杂度级别（L1–L4）给出可用任务。

    清单里**不含**必备能力全文与评分权重（README §10.5 的字段可见性矩阵）：
    学生视图只给题干、场景、需求简报与「本次有几项必备能力」。
    """
    listing, error = teaching_service.list_design_tasks_for_project(project_id)
    if error is not None:
        status, detail = error
        raise HTTPException(status_code=status, detail=detail)
    return listing


@router.get("/api/projects/{project_id}/teaching/design/task")
async def design_task(
    project_id: str,
    task_id: str | None = None,
    mode: str | None = None,
):
    """取一个设计任务（学生视图；``?mode=teacher`` 给完整版）。

    - 学生视图：`must_have` 全文 / `rubric_weights` / `required_relations` / `forbidden_merges`
      **一律不下发**；
    - 教师视图（`?mode=teacher`）：完整任务，供教师审核必备能力清单用
      （与判题接口的 ``?mode=teacher`` 是同一条边界纪律）。
    """
    task, error = teaching_service.build_design_task_for_project(
        project_id, task_id, teacher_mode=(str(mode or "").lower() == "teacher")
    )
    if error is not None:
        status, detail = error
        raise HTTPException(status_code=status, detail=detail)
    return task


@router.post("/api/projects/{project_id}/teaching/design/evaluate")
async def design_evaluate(project_id: str, payload: dict):
    """设计层六维评审。

    请求体：``{"task_id": "dt_...", "submission": {"modules": [...], "relations": [...],
    "design_rationale": "..."}}``（契约见 README §10.4）

    响应：``engine/design/rubric.py`` 的产物 —— 六维结果（``status`` / ``score`` /
    ``findings`` / ``issues`` / ``signals``）+ ``overall_score`` + ``caveats``。

    **算不出来的维度返回 ``not_evaluated`` 且 ``score`` 为 ``null``，不填 0**；
    反馈是「信号码 → 中文模板」的纯函数映射，每条都能追溯到触发它的结构信号。
    **判定只在后端**：离线演示模式不给这一通道（前端会明确显示不可用）。
    """
    submission = payload.get("submission")
    if submission is None:
        submission = payload.get("design")
    report, error = teaching_service.evaluate_design_for_project(
        project_id, payload.get("task_id"), submission
    )
    if error is not None:
        status, detail = error
        raise HTTPException(status_code=status, detail=detail)
    return report
