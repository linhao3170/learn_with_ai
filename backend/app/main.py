"""
LearnWithAI FastAPI backend entry.

Minimum viable backend: wraps the analysis engine and exposes it via HTTP APIs.
Designed to stay lean — no auth, no database, no task queue.

WO-02（W1，``docs/10-work-orders.md`` §23.2）—— **本文件不再定义任何路由**
--------------------------------------------------------------------------
在此之前这里是**全应用唯一的路由文件**：30 个路由全挤在 ``main.py`` 里，于是每一条
要加接口的工单都得改同一个文件（§22.5 的热文件 H1，并行开发最硬的瓶颈）。
现在路由**按域拆到** ``app/routers/`` 下的 5 个模块，本文件只保留：

1. ``sys.path`` 准备（让 ``engine`` 可导入）；
2. ``FastAPI(...)`` 创建（``version=`` **必须留在这里** —— 文档门禁 ``verify_docs.py`` 的 D3 读它）；
3. CORS；
4. ``include_router`` —— **注册顺序 = 拆分前路由在本文件里出现的顺序**，保证匹配行为不变；
5. ``__main__`` 里的 uvicorn 启动。

**这次拆分只搬移、不改行为**：路径 / 方法 / 请求体 / 响应字段 / 状态码 / 错误文案逐字未变
（证据：拆分前后 ``app.openapi()`` 逐字节相同，见该轮交付说明）。各 router 承载哪些路由、
对应哪一章文档，写在每个 router 文件头部与 ``app/routers/__init__.py`` 的清单里。

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
（WO-02 起，这个路由住在 ``app/routers/teaching.py``。）

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

Sprint 6 变化（业务逻辑分析平台）
---------------------------------
新增 13 个 ``/api/logic-platform/*`` 路由（``docs/05`` §21.5），应用版本升到 ``0.5.0``。
WO-02 起它们住在 ``app/routers/logic_platform.py``。
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ---- Make the engine package importable ----
# The engine lives one level above backend/, shared between the analysis
# pipeline and the API layer.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Support both ``uvicorn app.main:app`` from backend/ and importing the app
# from the repository root (the latter is useful for smoke tests and demos).
# ``analyze_project`` 在 WO-02 拆分前就只被 import、没有被本文件引用；
# 为不改变本模块的导入面而**原样保留**（拆分只搬路由，不顺手删东西）。
try:  # noqa: E402
    from app.services.analyzer import analyze_project  # noqa: F401
    from app.routers import analysis as analysis_router
    from app.routers import grading as grading_router
    from app.routers import logic_platform as logic_platform_router
    from app.routers import projects as projects_router
    from app.routers import teaching as teaching_router
except ModuleNotFoundError:  # pragma: no cover - depends on launch directory
    from backend.app.services.analyzer import analyze_project  # noqa: F401
    from backend.app.routers import analysis as analysis_router
    from backend.app.routers import grading as grading_router
    from backend.app.routers import logic_platform as logic_platform_router
    from backend.app.routers import projects as projects_router
    from backend.app.routers import teaching as teaching_router

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
# 路由装配（WO-02：按域分文件，本文件不再定义任何路由）
#
# 注册顺序刻意等于拆分前它们在 main.py 里出现的顺序：
#   /api/health … /api/projects/{id}/source-by-location    → projects.py
#   /api/projects/{id}/checkpoints/{i}/answer              → grading.py
#   /api/projects/{id}/teaching/**（六个）                  → teaching.py
#   /api/analyze、/api/analyses/**                         → analysis.py
#   /api/logic-platform/**、/api/teacher/logic-platform/**  → logic_platform.py
# 这样"谁先命中"与拆分前完全一致。
# ============================================================

app.include_router(projects_router.router)
app.include_router(grading_router.router)
app.include_router(teaching_router.router)
app.include_router(analysis_router.router)
app.include_router(logic_platform_router.router)


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
