"""业务逻辑分析平台（Sprint 6）—— 13 个路由，接口表见 ``docs/05`` §21.5。

一条流水线：投入项目 → 分析大小 → 按大小分流 → 产出业务板块
           → 点击板块看分析 → 沉浸式学习业务逻辑 → 证据与校验

纪律（与引擎侧一致）：

- 事实来自 AST，讲解由规则生成，**引擎不调 LLM**；
- 每条结论带 file + start_line + end_line + 摘录 + 哈希；
- 校验器（``POST .../verify``）重读磁盘源码 + 重解析 AST 复核；
- 未过校验、未经教师确认的内容，界面上一直带待确认标记。

它承载的路由：

- ``POST /api/logic-platform/analyze`` —— 投入 .py / .zip（**会转存源码**，与 ``/api/analyze`` 的关键区别）
- ``GET  /api/logic-platform/projects`` —— 可分析的演示项目列表
- ``GET  /api/logic-platform/narration-status`` —— 讲解层状态（默认关闭）
- ``GET  /api/logic-platform/{id}/analysis`` / ``/size`` / ``/sections`` / ``/sections/{section_id}``
- ``GET  /api/logic-platform/{id}/lessons`` / ``/lessons/{capability_id}``
- ``POST /api/logic-platform/{id}/lessons/{capability_id}/verify`` —— 重跑确定性校验
- ``POST /api/logic-platform/{id}/lessons/{capability_id}/narration`` —— 可选 LLM 润色（未配置 503）
- ``GET  /api/logic-platform/{id}/source`` —— 源码切片（证据跳转落点）
- ``POST /api/teacher/logic-platform/{id}/lessons/{capability_id}/review`` —— 教师确认 / 拒绝
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

from ._common import _find_project_root

try:  # noqa: E402 - 与 main.py 相同的双入口兼容
    from app.services import logic_platform_service
except ModuleNotFoundError:  # pragma: no cover - depends on launch directory
    from backend.app.services import logic_platform_service

router = APIRouter()


def _lp_error(error) -> None:
    """把服务层的 ``(状态码, 中文说明)`` 翻成 HTTPException。

    与 teaching_service 的六个路由同一写法：路由只做映射，不藏逻辑。
    """
    status, detail = error
    raise HTTPException(status_code=status, detail=detail)


@router.post("/api/logic-platform/analyze")
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


@router.get("/api/logic-platform/projects")
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


@router.get("/api/logic-platform/narration-status")
async def logic_platform_narration_status():
    """讲解层状态 —— 让界面能**如实**告诉评审"这个平台有没有用 AI"。"""
    return logic_platform_service.narration_status()


@router.get("/api/logic-platform/{analysis_id}/analysis")
async def logic_platform_analysis(analysis_id: str, force: bool = Query(False)):
    """大小分析 + 处理策略 + 业务板块看板。

    ``analysis_id`` 可以是演示项目 id（如 ``python_dotenv``），
    也可以是上传后得到的 ``lp_*``。
    """
    analysis, error = logic_platform_service.get_analysis(analysis_id, force=force)
    if error is not None:
        _lp_error(error)
    return analysis


@router.get("/api/logic-platform/{analysis_id}/size")
async def logic_platform_size(analysis_id: str):
    size, error = logic_platform_service.get_size(analysis_id)
    if error is not None:
        _lp_error(error)
    return size


@router.get("/api/logic-platform/{analysis_id}/sections")
async def logic_platform_sections(analysis_id: str):
    sections, error = logic_platform_service.get_sections(analysis_id)
    if error is not None:
        _lp_error(error)
    return sections


@router.get("/api/logic-platform/{analysis_id}/sections/{section_id}")
async def logic_platform_section(analysis_id: str, section_id: str):
    """单个业务板块的分析（板块卡片 + 它的能力点与成员函数行号）。"""
    section, error = logic_platform_service.get_section(analysis_id, section_id)
    if error is not None:
        _lp_error(error)
    return section


@router.get("/api/logic-platform/{analysis_id}/lessons")
async def logic_platform_lessons(analysis_id: str):
    """已生成过的课程索引（哪些能力点已经有讲稿）。"""
    index, error = logic_platform_service.get_lessons_index(analysis_id)
    if error is not None:
        _lp_error(error)
    return index


@router.get("/api/logic-platform/{analysis_id}/lessons/{capability_id}")
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


@router.post("/api/logic-platform/{analysis_id}/lessons/{capability_id}/verify")
async def logic_platform_verify(analysis_id: str, capability_id: str):
    """重跑确定性校验 → 返回"现在这一刻，讲稿的引用是否仍然成立"。"""
    report, error = logic_platform_service.verify_lesson(analysis_id, capability_id)
    if error is not None:
        _lp_error(error)
    return report


@router.post("/api/logic-platform/{analysis_id}/lessons/{capability_id}/narration")
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


@router.get("/api/logic-platform/{analysis_id}/source")
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


@router.post("/api/teacher/logic-platform/{analysis_id}/lessons/{capability_id}/review")
async def logic_platform_teacher_review(analysis_id: str, capability_id: str, payload: dict):
    """教师确认 / 拒绝一课（可细化到单条断言）。

    审核记录绑定当前 ``source_hash``：源码一变，旧审核自动 ``stale``，
    **系统不会沿用失效的审核结论**（README §6.1 的纪律）。
    """
    result, error = logic_platform_service.save_review(analysis_id, capability_id, payload)
    if error is not None:
        _lp_error(error)
    return result
