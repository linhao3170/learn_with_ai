"""
LearnWithAI FastAPI backend entry.

Minimum viable backend: wraps the existing analysis engine and exposes it
via HTTP APIs. Designed to stay lean — no auth, no database, no task queue.
All heavy lifting is done by the engine/ package imported from the parent project.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# ---- Make the engine package importable ----
# The engine lives one level above backend/, shared between the analysis
# pipeline and the API layer.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Support both ``uvicorn app.main:app`` from backend/ and importing the app
# from the repository root (the latter is useful for smoke tests and demos).
try:  # noqa: E402
    from app.services.analyzer import analyze_project
except ModuleNotFoundError:  # pragma: no cover - depends on launch directory
    from backend.app.services.analyzer import analyze_project

app = FastAPI(
    title="LearnWithAI API",
    description="Project-level business logic understanding training platform",
    version="0.1.0",
)

# CORS — the frontend dev server runs on a different port
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/projects/demo")
async def get_demo_project():
    """Return the pre-computed lab safety assistant analysis.

    Used by the frontend on first load. Returns the same data as the
    static demo JSON but through the API so the client can switch to
    live analysis without changing the data shape.
    """
    demo_path = PROJECT_ROOT / "frontend" / "public" / "demo" / "project_analysis.json"
    if not demo_path.exists():
        raise HTTPException(status_code=404, detail="Demo data not found")
    import json
    with open(demo_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/analyze")
async def analyze_uploaded_project(file: UploadFile = File(...)):
    """Analyze an uploaded Python project and return full training data.

    Accepts a single .py file or a .zip archive. Runs the full analysis
    pipeline (parsing → call graph → state tracking → flow extraction →
    training generation) and returns structured JSON.
    """
    import tempfile
    import zipfile
    import shutil
    import os

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    suffix = Path(file.filename).suffix.lower()
    tmp_dir = Path(tempfile.mkdtemp(prefix="lwai_"))

    try:
        contents = await file.read()

        if suffix == ".zip":
            # Extract zip
            zip_path = tmp_dir / "upload.zip"
            zip_path.write_bytes(contents)

            # Find the actual project root (skip nested single-folder wrappers)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(tmp_dir)

            # Heuristic: find the directory with .py files
            py_files = list(tmp_dir.rglob("*.py"))
            if not py_files:
                raise HTTPException(status_code=400, detail="No Python files found in archive")

            # Use the common root of all .py files
            project_dir = _find_project_root(py_files)

        elif suffix == ".py":
            # Single file — put it in a directory
            (tmp_dir / file.filename).write_bytes(contents)
            project_dir = tmp_dir
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type. Please upload a .py file or .zip archive.",
            )

        # Run analysis
        result = analyze_project(str(project_dir))
        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _find_project_root(py_files: list[Path]) -> Path:
    """Find the common parent directory of all Python files.

    If the common parent is a single-wrapper directory (contains only
    one subdirectory and no .py files), drill down one level.
    """
    if not py_files:
        raise ValueError("No Python files")

    # Find common path
    common = py_files[0].parent
    for f in py_files[1:]:
        f_parents = list(f.parents) + [f]
        while common not in f.parents and common != f:
            common = common.parent
            if common == common.parent:
                break

    # If common dir has no .py files and only one subdir, go deeper
    current = common
    while True:
        py_in_current = [p for p in current.iterdir() if p.suffix == ".py"]
        subdirs = [p for p in current.iterdir() if p.is_dir()]
        if not py_in_current and len(subdirs) == 1:
            current = subdirs[0]
        else:
            break

    return current


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
