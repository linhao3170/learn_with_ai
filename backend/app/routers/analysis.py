"""上传即分析 + 实时分析结果的判题 —— ``docs/04`` §11.1。

它承载的路由：

- ``POST /api/analyze`` —— 上传 ``.py`` / ``.zip``，跑完整分析并返回训练数据
  （P0-11：答案表写入 ``backend/data/answer_keys/<analysis_id>.json``，响应里只给 ``analysis_id``）；
- ``POST /api/analyses/{analysis_id}/checkpoints/{question_index}/answer`` ——
  实时分析结果的判题（``analysis_id`` 必须带 ``live_`` 前缀）。

⚠️ 与业务逻辑分析平台的 ``POST /api/logic-platform/analyze`` 的关键区别：
**这个接口在 ``finally`` 里删掉上传目录**，不负责源码回看（见 ``routers/logic_platform.py``）。

``_find_project_root`` 是它与平台上传接口共用的工具，拆到 ``routers/_common.py``（原样搬移）。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from ._common import _find_project_root

try:  # noqa: E402 - 与 main.py 相同的双入口兼容
    from app.services import project_store
except ModuleNotFoundError:  # pragma: no cover - depends on launch directory
    from backend.app.services import project_store

router = APIRouter()


@router.post("/api/analyze")
async def analyze_uploaded_project(file: UploadFile = File(...)):
    """Analyze an uploaded Python project and return full training data.

    Accepts a single .py file or a .zip archive. Runs the full analysis
    pipeline (parsing → call graph → state tracking → flow extraction →
    training generation) and returns structured JSON.

    P0-11：答案表写入 ``backend/data/answer_keys/<analysis_id>.json``，
    响应里只给 ``analysis_id``，不给答案。
    """
    import tempfile
    import zipfile
    import shutil

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    suffix = Path(file.filename).suffix.lower()
    tmp_dir = Path(tempfile.mkdtemp(prefix="lwai_"))

    try:
        contents = await file.read()

        if suffix == ".zip":
            zip_path = tmp_dir / "upload.zip"
            zip_path.write_bytes(contents)

            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(tmp_dir)

            py_files = list(tmp_dir.rglob("*.py"))
            if not py_files:
                raise HTTPException(status_code=400, detail="No Python files found in archive")

            project_dir = _find_project_root(py_files)

        elif suffix == ".py":
            (tmp_dir / file.filename).write_bytes(contents)
            project_dir = tmp_dir
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type. Please upload a .py file or .zip archive.",
            )

        # Run analysis and grade-answer capture in one pass
        from engine.project_analyzer import ProjectAnalyzer

        analysis_id = project_store.new_analysis_id()
        result_obj = ProjectAnalyzer().analyze(str(project_dir))

        project_store.save_live_answer_key(
            analysis_id,
            project_store.build_answer_key_payload(
                project_dir.name, getattr(result_obj, "training_answer_key", {}) or {}
            ),
        )

        payload = result_obj.to_dict()
        payload["analysis_id"] = analysis_id
        payload["project_id"] = analysis_id
        return JSONResponse(content=payload)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.post("/api/analyses/{analysis_id}/checkpoints/{question_index}/answer")
async def submit_live_answer(analysis_id: str, question_index: int, payload: dict):
    """实时分析结果的判题入口（答案表按 ``analysis_id`` 存放）。"""
    if not analysis_id.startswith("live_"):
        raise HTTPException(status_code=400, detail="非法的 analysis_id")
    selected = payload.get("selected") or []
    if isinstance(selected, str):
        selected = [selected]

    key = project_store.load_answer_key(analysis_id)
    if not key:
        raise HTTPException(status_code=404, detail="答案表不存在或已过期")

    # 复用同一套判题逻辑
    expected_entry = (key.get("questions") or {}).get(str(question_index))
    if not expected_entry:
        raise HTTPException(status_code=404, detail="题目下标越界")

    expected = set(expected_entry.get("answers", []) or [])
    given = {str(item).strip().upper() for item in selected if str(item).strip()}
    matched = sorted(expected & given)
    missing = sorted(expected - given)
    extra = sorted(given - expected)
    if not given:
        outcome = "wrong"
    elif not extra and not missing:
        outcome = "correct"
    elif matched:
        outcome = "partial"
    else:
        outcome = "wrong"

    return {
        "question_index": question_index,
        "result": outcome,
        "matched": matched,
        "missing": missing,
        "extra": extra,
        "explanation": expected_entry.get("explanation", ""),
        "knowledge_points": expected_entry.get("knowledge_points", []),
    }
