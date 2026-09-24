"""
LearnWithAI FastAPI backend entry.

Minimum viable backend: wraps the analysis engine and exposes it via HTTP APIs.
Designed to stay lean — no auth, no database, no task queue.

Sprint 0 变化（README5 第七章）
-------------------------------
P0-09  新增 ``GET /api/projects/{project_id}/source`` —— 证据跳转不再靠 basename
       拼接，而是按**项目内相对路径**取源码切片（带行号与上下文）。
P0-11  新增 ``POST /api/projects/{project_id}/checkpoints/{index}/answer`` ——
       判题在后端完成；答案表只存在于 ``backend/data/answer_keys/``，
       学生契约里既没有 ``correct_answers`` 也没有 ``explanation``。
P0-13  新增 ``GET /api/projects`` 与 ``GET /api/projects/{project_id}/analysis``，
       前端可以"在线 API 优先、离线快照回落"两种模式跑通同一套页面。

Sprint 3 变化（培训功能 · 阶段一「项目认知」）
---------------------------------------------
新增 ``POST /api/projects/{project_id}/teaching/orientation/coverage`` ——
学生写一段自由文本，后端做**纯规则**覆盖度比对，**只回覆盖清单、不打分**
（培养方案第四章 阶段一；架构文档第十一章 11.2 里一直写着、但此前没有实现的""覆盖度题""分支）。
判定实现只有一份：``engine/teaching/coverage.py``。

Sprint 4 变化（培训功能 · 阶段二「模块卡片学习」）
--------------------------------------------------
新增两个接口（培养方案第四章 阶段二：逐张卡片 + 五个问题，系统只做**事实覆盖比对**）：

- ``GET  /api/projects/{project_id}/teaching/module-card/task`` ——
  五个问题（来自 ``engine/lexicon/stage_questions.json``）+ 本项目全部卡片（来自 ``business_graph``）；
- ``POST /api/projects/{project_id}/teaching/module-card/coverage`` ——
  学生的五个回答 → 事实覆盖报告（**不打分**，``unconfirmed`` 的字段不参与比对）。

判定实现只有一份：``engine/teaching/card_coverage.py``，命中判定复用阶段一的
``engine/teaching/coverage.py``。应用版本随之升到 ``0.3.0``（Sprint 3 只加路由未升版本号，
这次升是因为新增了**两个**接口与一个新阶段）。

Sprint 5 变化（培训功能 · 阶段四「设计画布」，README §18 优先级 3）
------------------------------------------------------------------
新增三个接口（培养方案第四章 阶段四「学生自己设计模块」+ 阶段五「六维评审」）：

- ``GET  /api/projects/{project_id}/teaching/design/tasks`` ——
  按项目复杂度级别（L1–L4）给出可用设计任务（学生视图口径）；
- ``GET  /api/projects/{project_id}/teaching/design/task`` —— 取一道题的题干与需求简报；
  ``?mode=teacher`` 给完整版（含必备能力清单）；学生视图**不下发**必备能力与权重；
- ``POST /api/projects/{project_id}/teaching/design/evaluate`` ——
  学生画布提交 → 六维评审报告（**算不出来的维度返回 ``not_evaluated``，不填 0**）。

判定实现只有一份：``engine/design/``（``rubric.py`` 是六维，``matcher.py`` 复用阶段一的
命中判定）。应用版本升到 ``0.4.0``（新增三个阶段接口 + 设计层引擎）。
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
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
    from app.services import project_store, teaching_service, logic_platform_service
except ModuleNotFoundError:  # pragma: no cover - depends on launch directory
    from backend.app.services.analyzer import analyze_project
    from backend.app.services import project_store, teaching_service, logic_platform_service

app = FastAPI(
    title="LearnWithAI API",
    description="Project-level business logic understanding training platform",
    version="0.5.0",
)

# CORS — the frontend dev server runs on a different port
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 健康检查与项目列表
# ============================================================

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "0.5.0", "contract_version": "1.0"}


@app.get("/api/projects")
async def list_projects():
    """列出所有可用项目（演示快照 + 是否具备答案表/源码）。

    前端用它来渲染"项目切换"，并判断某项目能否在线判题。
    """
    return {"projects": project_store.list_projects()}


@app.get("/api/projects/demo")
async def get_demo_project():
    """返回默认演示项目的学生契约（向后兼容旧路径）。"""
    snapshot = project_store.load_snapshot(project_store.DEFAULT_PROJECT_ID)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Demo data not found")
    return snapshot


@app.get("/api/projects/{project_id}/analysis")
async def get_project_analysis(
    project_id: str,
    mode: str = Query("student", description="student | teacher"),
):
    """返回项目契约快照。

    ``mode=teacher`` 会把 ``correct_answers`` 与 ``explanation`` 补回去，
    只应给教师预览使用（README3 §6.5）。
    """
    teacher_mode = mode == "teacher"
    snapshot = project_store.load_snapshot(project_id, teacher_mode=teacher_mode)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"项目快照不存在: {project_id}")
    return snapshot


# ============================================================
# 业务图谱（Sprint 1 / README5 §4.2）
# ============================================================

@app.get("/api/projects/{project_id}/business-graph")
async def get_business_graph(project_id: str):
    """返回项目的**业务图谱**。

    这是"业务逻辑分析"的正式产物：一级业务域 → 二级功能点 → 动作/规则/状态，
    每个节点都带置信度与代码证据。

    与 ``/analysis`` 分开，是为了让前端能只取业务图谱（比整份契约小很多），
    也方便 Sprint 2 的 `BusinessGraphView` 单独演进。
    """
    snapshot = project_store.load_snapshot(project_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"项目快照不存在: {project_id}")

    graph = snapshot.get("business_graph")
    if not graph:
        raise HTTPException(
            status_code=404,
            detail=(
                "该项目快照里没有 business_graph"
                f"（可能由 Sprint 1 之前的版本生成，请重跑 scripts/build_demo_snapshots.py）: {project_id}"
            ),
        )
    return graph


@app.get("/api/projects/{project_id}/business-graph/cards/{module_id}")
async def get_module_card(project_id: str, module_id: str):
    """返回单张业务模块卡片（一级业务域或二级功能点）。"""
    snapshot = project_store.load_snapshot(project_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"项目快照不存在: {project_id}")

    cards = ((snapshot.get("business_graph") or {}).get("module_cards")) or {}
    card = cards.get(module_id)
    if card is None:
        raise HTTPException(status_code=404, detail=f"模块卡片不存在: {module_id}")
    return card


# ============================================================
# 证据跳转：源码切片（P0-09）
# ============================================================

@app.get("/api/projects/{project_id}/source")
async def get_source_slice(
    project_id: str,
    path: str = Query(..., description="项目内相对路径，例如 user_manager.py"),
    start: int | None = Query(None, description="起始行（1-based，含）"),
    end: int | None = Query(None, description="结束行（1-based，含）"),
):
    """按项目内相对路径返回源码切片与上下文。

    这是"点一下跳到第 88 行"的服务端落点。路径越界或文件不存在时返回 404，
    **不静默失败**（P0-09 要求）。
    """
    result = project_store.read_source(project_id, path, start, end)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"源码不存在或不可读: {path}（项目 {project_id}）",
        )
    return result


@app.get("/api/projects/{project_id}/source-by-location")
async def get_source_by_location(
    project_id: str,
    location: str = Query(..., description="形如 path/to/file.py:88 或 file.py:88-120"),
):
    """按引擎输出的 ``location`` 字符串取源码（内部会拆出路径与行号）。"""
    path, start, end = project_store.parse_location(location)
    if not path:
        raise HTTPException(status_code=400, detail=f"无法解析 location: {location}")
    result = project_store.read_source(project_id, path, start, end)
    if result is None:
        raise HTTPException(status_code=404, detail=f"源码不存在或不可读: {path}")
    return result


# ============================================================
# 判题（P0-11）
# ============================================================

@app.post("/api/projects/{project_id}/checkpoints/{question_index}/answer")
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


# ============================================================
# 培训功能 · 阶段一「项目认知」（Sprint 3）
# ============================================================

@app.post("/api/projects/{project_id}/teaching/orientation/coverage")
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


# ============================================================
# 培训功能 · 阶段二「模块卡片学习」（Sprint 4）
# ============================================================

@app.get("/api/projects/{project_id}/teaching/module-card/task")
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


@app.post("/api/projects/{project_id}/teaching/module-card/coverage")
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


# ============================================================
# 培训功能 · 阶段四「设计画布」（README §18 优先级 3）
# ============================================================

@app.get("/api/projects/{project_id}/teaching/design/tasks")
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


@app.get("/api/projects/{project_id}/teaching/design/task")
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


@app.post("/api/projects/{project_id}/teaching/design/evaluate")
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


# ============================================================
# 实时分析
# ============================================================

@app.post("/api/analyze")
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


@app.post("/api/analyses/{analysis_id}/checkpoints/{question_index}/answer")
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


# ============================================================
# 业务逻辑分析平台（Sprint 6）
#
# 一条流水线：投入项目 → 分析大小 → 按大小分流 → 产出业务板块
#            → 点击板块看分析 → 沉浸式学习业务逻辑 → 证据与校验
#
# 纪律（与引擎侧一致）：
# - 事实来自 AST，讲解由规则生成，**引擎不调 LLM**；
# - 每条结论带 file + start_line + end_line + 摘录 + 哈希；
# - 校验器（POST .../verify）重读磁盘源码 + 重解析 AST 复核；
# - 未过校验、未经教师确认的内容，界面上一直带待确认标记。
# ============================================================


def _lp_error(error) -> None:
    """把服务层的 ``(状态码, 中文说明)`` 翻成 HTTPException。

    与 teaching_service 的六个路由同一写法：路由只做映射，不藏逻辑。
    """
    status, detail = error
    raise HTTPException(status_code=status, detail=detail)


@app.post("/api/logic-platform/analyze")
async def logic_platform_analyze(file: UploadFile = File(...)):
    """投入一个项目（.py / .zip），返回大小分级 + 处理策略 + 业务板块。

    ⚠️ 与 ``/api/analyze`` 的关键区别：**这个接口会把源码转存下来**。
    ``/api/analyze`` 在 ``finally`` 里删掉上传目录，它不负责证据回看；
    本平台承诺"每条结论都能点开源码的那几行"，所以源码必须留存。
    """
    import tempfile
    import zipfile
    import shutil

    if not file.filename:
        raise HTTPException(status_code=400, detail="没有收到文件")

    suffix = Path(file.filename).suffix.lower()
    tmp_dir = Path(tempfile.mkdtemp(prefix="lwai_lp_"))

    try:
        contents = await file.read()

        if suffix == ".zip":
            zip_path = tmp_dir / "upload.zip"
            zip_path.write_bytes(contents)
            with zipfile.ZipFile(zip_path, "r") as zf:
                # 防 zip-slip：成员解析后必须仍落在 tmp_dir 内
                for member in zf.namelist():
                    target = (tmp_dir / member).resolve()
                    if not str(target).startswith(str(tmp_dir.resolve())):
                        raise HTTPException(status_code=400, detail=f"压缩包内含非法路径：{member}")
                zf.extractall(tmp_dir)
            py_files = list(tmp_dir.rglob("*.py"))
            if not py_files:
                raise HTTPException(status_code=400, detail="压缩包里没有 Python 文件")
            project_dir = _find_project_root(py_files)
        elif suffix == ".py":
            (tmp_dir / file.filename).write_bytes(contents)
            project_dir = tmp_dir
        else:
            raise HTTPException(
                status_code=400,
                detail="只支持 .py 单文件或 .zip 压缩包。",
            )

        analysis, error = logic_platform_service.analyze_uploaded_project(
            tmp_dir, project_dir, display_name=Path(file.filename).stem
        )
        if error is not None:
            _lp_error(error)
        return JSONResponse(content=analysis)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"业务逻辑分析失败：{str(e)}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.get("/api/logic-platform/projects")
async def logic_platform_projects():
    """可做平台分析的演示项目列表（来自已有快照）。"""
    import json as _json

    demo_root = logic_platform_service.DEMO_ROOT
    projects: list[dict] = []
    default_snapshot = demo_root / "project_analysis.json"
    if default_snapshot.exists():
        try:
            payload = _json.loads(default_snapshot.read_text(encoding="utf-8"))
            projects.append(
                {
                    "project_id": logic_platform_service.DEFAULT_PROJECT_ID,
                    "project_name": payload.get("project_name") or logic_platform_service.DEFAULT_PROJECT_ID,
                }
            )
        except (OSError, ValueError):
            pass
    projects_root = demo_root / "projects"
    if projects_root.exists():
        for child in sorted(projects_root.iterdir(), key=lambda p: p.name):
            if not child.is_dir() or not (child / "project_analysis.json").exists():
                continue
            try:
                payload = _json.loads((child / "project_analysis.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            projects.append(
                {"project_id": child.name, "project_name": payload.get("project_name") or child.name}
            )
    return {"projects": projects}


@app.get("/api/logic-platform/narration-status")
async def logic_platform_narration_status():
    """讲解层状态 —— 让界面能**如实**告诉评审"这个平台有没有用 AI"。"""
    return logic_platform_service.narration_status()


@app.get("/api/logic-platform/{analysis_id}/analysis")
async def logic_platform_analysis(analysis_id: str, force: bool = Query(False)):
    """大小分析 + 处理策略 + 业务板块看板。

    ``analysis_id`` 可以是演示项目 id（如 ``python_dotenv``），
    也可以是上传后得到的 ``lp_*``。
    """
    analysis, error = logic_platform_service.get_analysis(analysis_id, force=force)
    if error is not None:
        _lp_error(error)
    return analysis


@app.get("/api/logic-platform/{analysis_id}/size")
async def logic_platform_size(analysis_id: str):
    size, error = logic_platform_service.get_size(analysis_id)
    if error is not None:
        _lp_error(error)
    return size


@app.get("/api/logic-platform/{analysis_id}/sections")
async def logic_platform_sections(analysis_id: str):
    sections, error = logic_platform_service.get_sections(analysis_id)
    if error is not None:
        _lp_error(error)
    return sections


@app.get("/api/logic-platform/{analysis_id}/sections/{section_id}")
async def logic_platform_section(analysis_id: str, section_id: str):
    """单个业务板块的分析（板块卡片 + 它的能力点与成员函数行号）。"""
    section, error = logic_platform_service.get_section(analysis_id, section_id)
    if error is not None:
        _lp_error(error)
    return section


@app.get("/api/logic-platform/{analysis_id}/lessons")
async def logic_platform_lessons(analysis_id: str):
    """已生成过的课程索引（哪些能力点已经有讲稿）。"""
    index, error = logic_platform_service.get_lessons_index(analysis_id)
    if error is not None:
        _lp_error(error)
    return index


@app.get("/api/logic-platform/{analysis_id}/lessons/{capability_id}")
async def logic_platform_lesson(
    analysis_id: str,
    capability_id: str,
    regenerate: bool = Query(False),
):
    """沉浸式学习业务逻辑：某个能力点的逐段讲稿（含证据与校验结果）。

    ``regenerate=true`` 会重算（同一份源码结果逐字节一致，一般不需要）。
    """
    lesson, error = logic_platform_service.build_lesson(
        analysis_id, capability_id, regenerate=regenerate
    )
    if error is not None:
        _lp_error(error)
    return lesson


@app.post("/api/logic-platform/{analysis_id}/lessons/{capability_id}/verify")
async def logic_platform_verify(analysis_id: str, capability_id: str):
    """重跑确定性校验 → 返回"现在这一刻，讲稿的引用是否仍然成立"。"""
    report, error = logic_platform_service.verify_lesson(analysis_id, capability_id)
    if error is not None:
        _lp_error(error)
    return report


@app.post("/api/logic-platform/{analysis_id}/lessons/{capability_id}/narration")
async def logic_platform_narration(
    analysis_id: str,
    capability_id: str,
    payload: dict | None = None,
):
    """可选：用 LLM 润色讲解（默认关闭）。

    未配置讲解服务时返回 **503** 并说明原因 —— 不静默降级、不假装生成过。
    启用后产物仍强制 ``needs_review``，且每一条讲解都要落在它所属段的行范围内。
    """
    body = payload or {}
    result, error = logic_platform_service.apply_narration(
        analysis_id, capability_id, narration=body.get("narration"), provider=body.get("provider")
    )
    if error is not None:
        _lp_error(error)
    return result


@app.get("/api/logic-platform/{analysis_id}/source")
async def logic_platform_source(
    analysis_id: str,
    path: str = Query(..., description="项目内相对路径（POSIX）"),
    start: int | None = Query(None),
    end: int | None = Query(None),
):
    """源码切片 —— 证据跳转的落点。

    返回结构与 ``/api/projects/{id}/source`` 一致，前端可复用同一个查看器。
    """
    payload, error = logic_platform_service.read_source(analysis_id, path, start, end)
    if error is not None:
        _lp_error(error)
    return payload


@app.post("/api/teacher/logic-platform/{analysis_id}/lessons/{capability_id}/review")
async def logic_platform_teacher_review(analysis_id: str, capability_id: str, payload: dict):
    """教师确认 / 拒绝一课（可细化到单条断言）。

    审核记录绑定当前 ``source_hash``：源码一变，旧审核自动 ``stale``，
    **系统不会沿用失效的审核结论**（README §6.1 的纪律）。
    """
    result, error = logic_platform_service.save_review(analysis_id, capability_id, payload)
    if error is not None:
        _lp_error(error)
    return result


def _find_project_root(py_files: list[Path]) -> Path:
    """Find the common parent directory of all Python files.

    If the common parent is a single-wrapper directory (contains only
    one subdirectory and no .py files), drill down one level.
    """
    if not py_files:
        raise ValueError("No Python files")

    common = py_files[0].parent
    for f in py_files[1:]:
        while common not in f.parents and common != f:
            common = common.parent
            if common == common.parent:
                break

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
