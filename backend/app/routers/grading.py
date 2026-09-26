"""后端判题 —— ``docs/04`` §11.1 + §11.2（判题的实现要点）。

它承载的路由：

- ``POST /api/projects/{project_id}/checkpoints/{question_index}/answer`` ——
  学生提交答案 → 后端判题 → 返回结果与讲解。

**边界纪律（P0-11，不许在这一层改动）**：正确答案本身不下发；讲解只在作答之后返回；
答案表只存在于 ``backend/data/answer_keys/``。判题实现只有一份，在
``backend/app/services/project_store.py`` 的 ``grade_answer``。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

try:  # noqa: E402 - 与 main.py 相同的双入口兼容
    from app.services import project_store
except ModuleNotFoundError:  # pragma: no cover - depends on launch directory
    from backend.app.services import project_store

router = APIRouter()


@router.post("/api/projects/{project_id}/checkpoints/{question_index}/answer")
async def submit_answer(project_id: str, question_index: int, payload: dict):
    """学生提交答案 → 后端判题 → 返回结果与讲解。

    请求体：``{"selected": ["A", "C"]}``
    响应：``{"result": "correct|partial|wrong", "matched": [], "missing": [],
    "extra": [], "explanation": "...", "knowledge_points": []}``

    **正确答案本身不下发**；讲解只在作答之后才返回。
    """
    selected = payload.get("selected") or payload.get("answer") or []
    if isinstance(selected, str):
        selected = [selected]
    if not isinstance(selected, list):
        raise HTTPException(status_code=400, detail="selected 必须是选项 ID 数组")

    result = project_store.grade_answer(project_id, question_index, selected)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"该项目没有可用的答案表或题目下标越界: {project_id} #{question_index}",
        )
    return result
