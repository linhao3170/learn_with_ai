"""L4 · 教学服务层（``backend/app/services/teaching_service.py``）

职责边界（很重要）
==================
本层**只做编排，不做判定**：

- 判定逻辑在 ``engine/teaching/``（纯函数、确定性、无网络、无 LLM）；
- 本层负责：取快照 → 入口校验（空提交 / 超长 / 卡片不存在 / 未知问题标识）→ 调引擎
  → 把结果原样交给路由层。

为什么阶段一 / 阶段二的比对放在后端而不是前端
============================================
1. 与既有的边界一致："判定在后端、前端只拿结论"（架构文档第十一章 11.3）。
   离线模式下**数据层面就没有判定通道**，UI 只能如实说"离线演示模式：覆盖度报告不可用"，
   而不是自己在浏览器里算一份出来 —— 那样两边的口径迟早会不一致。
2. 判定口径（比对键来自哪些字段、哪些置信度不参与）必须**只有一份实现**，
   否则前端一份、后端一份，改一处漏一处。
3. 阶段二的**题目**也从后端下发（``build_module_card_task_for_project``）：
   题目文本与「问题 → 字段」映射在 ``engine/lexicon/stage_questions.json``，
   前端不认识任何一个业务字段 —— 换项目、换问法都不用改前端（README 第十八章验收项）。

本层不做什么
------------
- 不存学生答案（两个阶段都不判分，没有答案可存；学习会话仍是 P0 的 ``localStorage``）；
- 不调 LLM、不落盘、不加缓存（判定是纯函数，重算成本可忽略）。
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from engine.teaching.card_coverage import (
    MAX_ANSWER_CHARS,
    MAX_TOTAL_CHARS,
    build_module_card_task,
    evaluate_module_card_answers,
    question_specs,
)
from engine.teaching.coverage import MAX_INPUT_CHARS, evaluate_orientation

from engine.design import build_design_task, evaluate_design, list_design_tasks, resolve_task
from engine.design import submission as design_submission
from engine.design.task_builder import student_view

try:  # noqa: E402 - 支持 uvicorn app.main:app（backend/ 下启动）与仓库根导入两种方式
    from app.services import project_store
except ModuleNotFoundError:  # pragma: no cover
    from backend.app.services import project_store

__all__ = [
    "STAGE",
    "STAGE_MODULE_CARD",
    "STAGE_DESIGN",
    "build_module_card_task_for_project",
    "evaluate_module_card_for_project",
    "evaluate_orientation_for_project",
    "list_design_tasks_for_project",
    "build_design_task_for_project",
    "evaluate_design_for_project",
]

#: 阶段标识（与课堂流程的""阶段一""一一对应）
STAGE = "orientation"
#: 阶段二标识：模块卡片学习
STAGE_MODULE_CARD = "module_card"
#: 阶段四标识：设计画布（README §12.1 的 8 页信息架构里对应「模块设计」）
STAGE_DESIGN = "design_canvas"

#: 错误 = (HTTP 状态码, 给用户看的说明)
ErrorDetail = Tuple[int, str]


def evaluate_orientation_for_project(
    project_id: str,
    text: Any,
) -> Tuple[Optional[Dict[str, Any]], Optional[ErrorDetail]]:
    """阶段一覆盖度比对：``(report, None)`` 或 ``(None, (status, detail))``。

    校验口径（全部显式，不静默兜底）：

    - 项目快照不存在 → 404；
    - 快照里没有 ``business_graph`` → 404（旧快照，提示重跑产物脚本）；
    - 空提交（或只有空白）→ 400；
    - 超过 ``MAX_INPUT_CHARS`` → 400。
    """
    snapshot = project_store.load_snapshot(project_id, teacher_mode=False)
    if snapshot is None:
        return None, (404, f"项目快照不存在: {project_id}")

    graph = snapshot.get("business_graph")
    if not graph:
        return None, (
            404,
            "该项目快照里没有 business_graph（可能由业务图谱之前的版本生成，"
            f"请重跑 scripts/build_demo_snapshots.py）: {project_id}",
        )

    body = str(text if text is not None else "")
    if not body.strip():
        return None, (400, "请先写下你的回答：阶段一不接受空提交。")
    if len(body) > MAX_INPUT_CHARS:
        return None, (400, f"回答过长（{len(body)} 字，上限 {MAX_INPUT_CHARS} 字），请精炼后再提交。")

    return evaluate_orientation(graph, body), None


# ============================================================
# 阶段二「模块卡片学习」（题目 + 事实覆盖比对）
# ============================================================

def _load_graph(project_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[ErrorDetail]]:
    """取项目快照里的业务图谱（阶段一 / 阶段二共用同一套「取不到就说清楚」的口径）。"""
    snapshot = project_store.load_snapshot(project_id, teacher_mode=False)
    if snapshot is None:
        return None, (404, f"项目快照不存在: {project_id}")

    graph = snapshot.get("business_graph")
    if not graph:
        return None, (
            404,
            "该项目快照里没有 business_graph（可能由业务图谱之前的版本生成，"
            f"请重跑 scripts/build_demo_snapshots.py）: {project_id}",
        )
    return graph, None


def build_module_card_task_for_project(
    project_id: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[ErrorDetail]]:
    """阶段二的任务包：五个问题 + 本项目所有模块卡片（学生可见字段）。

    题目来自 ``engine/lexicon/stage_questions.json``，卡片内容来自该项目的 ``business_graph``：
    **前端不认识任何一个业务字段**，换项目不用改页面代码。
    """
    graph, error = _load_graph(project_id)
    if error is not None:
        return None, error
    return build_module_card_task(graph), None


def evaluate_module_card_for_project(
    project_id: str,
    module_id: Any,
    answers: Any,
) -> Tuple[Optional[Dict[str, Any]], Optional[ErrorDetail]]:
    """阶段二事实覆盖比对：``(report, None)`` 或 ``(None, (status, detail))``。

    校验口径（全部显式，不静默兜底）：

    - 项目快照 / 图谱缺失 → 404；
    - 没给 ``module_id`` → 400；卡片不在图谱里 → 404（**不静默降级成一张空卡片**）；
    - ``answers`` 不是对象 → 400；
    - 所有回答都是空白 → 400（本阶段不接受空提交）；
    - 单个回答超过 ``MAX_ANSWER_CHARS`` / 合计超过 ``MAX_TOTAL_CHARS`` → 400；
    - 出现本阶段不认识的问题标识 → 400。

    最后一条是刻意的：引擎会把未知标识列进报告，但**后端选择直接拒绝**——
    学生写下的内容绝不能因为前端发错 key 就被悄悄排除在比对之外。
    """
    graph, error = _load_graph(project_id)
    if error is not None:
        return None, error

    card_id = str(module_id or "").strip()
    if not card_id:
        return None, (400, "缺少 module_id：阶段二必须先选定一张模块卡片。")

    cards = graph.get("module_cards") or {}
    if card_id not in cards:
        return None, (404, f"模块卡片不存在: {card_id}（项目 {project_id}）")

    if not isinstance(answers, dict):
        return None, (400, "answers 必须是「问题标识 → 回答文本」的对象。")

    known_ids = {item["question_id"] for item in question_specs()}
    unknown_ids = sorted(str(key) for key in answers.keys() if str(key) not in known_ids)
    if unknown_ids:
        return None, (
            400,
            "提交里含有本阶段不认识的问题标识（" + "、".join(unknown_ids)
            + "）：不能把学生写下的内容静默丢掉，请刷新页面重新作答。",
        )

    cleaned: Dict[str, str] = {key: str(value if value is not None else "") for key, value in answers.items()}
    if not any(text.strip() for text in cleaned.values()):
        return None, (400, "请至少回答一个问题：阶段二不接受空提交。")

    for key, text in cleaned.items():
        if len(text) > MAX_ANSWER_CHARS:
            return None, (
                400,
                f"「{key}」的回答过长（{len(text)} 字，单题上限 {MAX_ANSWER_CHARS} 字），请精炼后再提交。",
            )
    total = sum(len(text) for text in cleaned.values())
    if total > MAX_TOTAL_CHARS:
        return None, (400, f"回答合计过长（{total} 字，上限 {MAX_TOTAL_CHARS} 字），请精炼后再提交。")

    report = evaluate_module_card_answers(graph, card_id, cleaned)
    if not report:
        # 图谱里刚查过卡片，理论上到不了这里；真到了就是引擎的返回契约坏了 —— 不许静默返回空报告
        return None, (404, f"模块卡片不存在: {card_id}（项目 {project_id}）")
    return report, None


# ============================================================
# 阶段四「设计画布」（README §18 优先级 3）
# ============================================================

def list_design_tasks_for_project(
    project_id: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[ErrorDetail]]:
    """设计任务清单（学生视图口径）：按项目复杂度级别给出任务类型。"""
    graph, error = _load_graph(project_id)
    if error is not None:
        return None, error
    return list_design_tasks(graph), None


def build_design_task_for_project(
    project_id: str,
    task_id: Any = None,
    teacher_mode: bool = False,
) -> Tuple[Optional[Dict[str, Any]], Optional[ErrorDetail]]:
    """取一个设计任务。

    - ``teacher_mode=False``（默认）：**学生视图** —— 不含必备能力全文、不含评分权重、
      不含必备依赖与禁止合并项（README §10.5 字段可见性矩阵）；
    - ``teacher_mode=True``（``?mode=teacher``）：完整版，供教师端审核使用。

    ``task_id`` 为空时取默认任务；给了但不认识 → 404（**不静默降级成默认任务**：
    学生答的那道题和系统评分的那道题必须是同一道）。
    """
    graph, error = _load_graph(project_id)
    if error is not None:
        return None, error

    key = str(task_id or "").strip()
    task = resolve_task(graph, key)
    if task is None:
        listing = list_design_tasks(graph)
        return None, (
            404,
            f"设计任务不存在: {key}（项目 {project_id} 的可用任务："
            + "、".join(str(item.get("task_id")) for item in listing.get("tasks") or [])
            + "）",
        )
    return (dict(task) if teacher_mode else student_view(task)), None


def evaluate_design_for_project(
    project_id: str,
    task_id: Any,
    submission: Any,
) -> Tuple[Optional[Dict[str, Any]], Optional[ErrorDetail]]:
    """设计层六维评审：``(report, None)`` 或 ``(None, (status, detail))``。

    校验口径（全部显式，不静默兜底）：

    - 项目快照 / 图谱缺失 → 404；
    - ``task_id`` 缺失或不存在 → 404（评分必须针对一道**存在的**题）；
    - ``submission`` 不是对象 → 400；
    - 一个模块都没有 → 400（**设计层不接受空提交**：空画布不是「0 分设计」）；
    - 模块数超上限、模块没有名字、设计理由超长 → 400。

    注意：**判定的口径全部在 ``engine/design/``**（纯函数、确定性、无 LLM），
    本层只做入口校验与编排 —— 与阶段一 / 二同一条分工。
    """
    graph, error = _load_graph(project_id)
    if error is not None:
        return None, error

    if not isinstance(submission, dict):
        return None, (400, "submission 必须是 design_submission 对象（见 README §10.4）。")

    key = str(task_id or submission.get("task_id") or "").strip()
    task = resolve_task(graph, key)
    if task is None:
        return None, (404, f"设计任务不存在: {key or '（未提供 task_id）'}（项目 {project_id}）")

    normalized = design_submission.normalize_submission(submission)
    modules = normalized.get("modules") or []
    if not modules:
        return None, (400, "请先在画布上添加至少一个模块：设计层不接受空提交。")
    if len(modules) > design_submission.MAX_MODULES:
        return None, (
            400,
            f"模块过多（{len(modules)} 个，上限 {design_submission.MAX_MODULES} 个），请先合并或删减。",
        )
    unnamed = [index + 1 for index, item in enumerate(modules) if not str(item.get("name") or "").strip()]
    if unnamed:
        return None, (
            400,
            "有模块还没有名字（第 " + "、".join(str(index) for index in unnamed)
            + " 个）：没有名字的模块无法参与匹配与评审，请先给每个模块起名。",
        )
    if len(normalized.get("design_rationale") or "") > design_submission.MAX_RATIONALE_CHARS:
        return None, (
            400,
            f"设计理由过长（上限 {design_submission.MAX_RATIONALE_CHARS} 字），请精炼后再提交。",
        )

    return evaluate_design(graph, task, normalized), None
