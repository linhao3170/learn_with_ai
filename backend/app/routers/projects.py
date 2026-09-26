"""项目 / 契约 / 业务图谱 / 源码切片（证据跳转）—— ``docs/04`` §11.1 前 8 行。

它承载的路由（路径与方法逐字沿用拆分前的 ``main.py``）：

- ``GET  /api/health`` —— 健康检查（返回 ``contract_version``）
- ``GET  /api/projects`` —— 项目列表（含是否有快照 / 答案表 / 源码）
- ``GET  /api/projects/demo`` —— 默认演示项目学生契约（兼容旧路径）
- ``GET  /api/projects/{project_id}/analysis`` —— 契约快照（``?mode=teacher`` 才补回答案）
- ``GET  /api/projects/{project_id}/business-graph`` —— 业务图谱（Sprint 1）
- ``GET  /api/projects/{project_id}/business-graph/cards/{module_id}`` —— 单张模块卡片
- ``GET  /api/projects/{project_id}/source`` —— 源码切片（P0-09，证据跳转落点）
- ``GET  /api/projects/{project_id}/source-by-location`` —— 用引擎的 ``location`` 串取源码

数据与判定全在 ``backend/app/services/project_store.py``；本文件只做「参数 → 服务 → 响应」的映射。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

try:  # noqa: E402 - 与 main.py 相同的双入口兼容（uvicorn 从 backend/ 起 / 从仓库根导入）
    from app.services import project_store
except ModuleNotFoundError:  # pragma: no cover - depends on launch directory
    from backend.app.services import project_store

router = APIRouter()


@router.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "0.5.0", "contract_version": "1.0"}


@router.get("/api/projects")
async def list_projects():
    """列出所有可用项目（演示快照 + 是否具备答案表/源码）。

    前端用它来渲染"项目切换"，并判断某项目能否在线判题。
    """
    return {"projects": project_store.list_projects()}


@router.get("/api/projects/demo")
async def get_demo_project():
    """返回默认演示项目的学生契约（向后兼容旧路径）。"""
    snapshot = project_store.load_snapshot(project_store.DEFAULT_PROJECT_ID)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Demo data not found")
    return snapshot


@router.get("/api/projects/{project_id}/analysis")
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


@router.get("/api/projects/{project_id}/business-graph")
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


@router.get("/api/projects/{project_id}/business-graph/cards/{module_id}")
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


@router.get("/api/projects/{project_id}/source")
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


@router.get("/api/projects/{project_id}/source-by-location")
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
