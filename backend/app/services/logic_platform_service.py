"""业务逻辑分析平台 · 后端服务层

职责
----
把引擎（``engine/logic_platform``）的产物接进 API，并且**自己负责持久化** ——
因为 ``POST /api/analyze`` 会在 ``finally`` 里把上传的源码删掉（``main.py:461``），
而本平台的核心承诺是"每一条结论都能回指到源码的某一文件某几行"。
源码没了，证据链就断了。所以这一层必须自己把源码转存。

持久化布局
----------
::

    backend/data/logic_platform/<analysis_id>/
      meta.json         分析元数据（来源、源码根、source_hash、版本）
      graph.json        业务图谱（讲稿生成需要它的能力点/成员索引）
      analysis.json     大小 + 处理策略 + 业务板块看板
      lessons/<cap_id>.json   已生成的讲稿（含校验结果与审核状态）
      reviews.json      教师审核记录（绑定 source_hash）
      source/**.py      上传项目的源码副本（演示项目不复制，直接读原目录）

约定（与 backend/app 其余部分一致）
-----------------------------------
- 服务层**不抛异常**，一律返回 ``(result, error)``，``error`` 是 ``(状态码, 中文说明)`` 或 ``None``；
  由路由层负责 ``raise HTTPException``；
- 显式校验、**不做静默兜底**（README 的房规）：找不到就是 404，级别算不出来就说算不出来；
- 契约里不出现开发机绝对路径：``meta.json`` 里存的是**相对仓库根**的路径。
"""

from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]

#: 平台数据的落盘根目录（backend/data/logic_platform）。
#: 注意：``backend/data/`` 不对外提供静态服务，源码副本只给本模块读。
DATA_ROOT = REPO_ROOT / "backend" / "data" / "logic_platform"

#: 演示项目源码/快照所在（与 project_store 的口径一致，但本模块不 import 它，
#: 避免两个模块对"项目在哪"各有一套说法 —— 这里只读快照，源码根由本模块算）。
DEMO_ROOT = REPO_ROOT / "frontend" / "public" / "demo"
DEFAULT_PROJECT_ID = "lab_safety_assistant"

ErrorDetail = Tuple[int, str]

#: 允许生成讲稿的最大能力点数 —— 防止有人用一个大项目把接口当批量生成器用。
MAX_LESSON_BUILD = 1

_PLATFORM_VERSION = "lp-1.0"


# ============================================================
# 路径与元数据
# ============================================================


def _analysis_dir(analysis_id: str) -> Path:
    return DATA_ROOT / str(analysis_id)


def _rel_to_repo(path: Path) -> str:
    """把绝对路径转成相对仓库根的 POSIX 路径（**绝不把绝对路径写进盘上元数据**）。"""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except (ValueError, OSError):
        return ""


def _read_json(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def new_analysis_id() -> str:
    """``lp_<12 hex>`` —— 与 ``live_`` / ``project_id`` 都不冲突，来源一眼可辨。"""
    return f"lp_{uuid.uuid4().hex[:12]}"


def _demo_source_root(project_id: str) -> Path:
    if project_id == DEFAULT_PROJECT_ID:
        return DEMO_ROOT / "source"
    return DEMO_ROOT / "projects" / project_id / "source"


def _demo_snapshot_path(project_id: str) -> Path:
    if project_id == DEFAULT_PROJECT_ID:
        return DEMO_ROOT / "project_analysis.json"
    return DEMO_ROOT / "projects" / project_id / "project_analysis.json"


def resolve_source_root(analysis_id: str) -> Tuple[Optional[Path], Optional[ErrorDetail]]:
    """找出这个分析的源码根目录（校验器要直接读它）。"""
    meta = _read_json(_analysis_dir(analysis_id) / "meta.json")
    if not meta:
        return None, (404, f"分析不存在：{analysis_id}（请先调用 /api/logic-platform/analyze）")
    rel = str(meta.get("source_root_rel") or "")
    if not rel:
        return None, (500, "该分析的元数据里没有源码根路径，无法回看证据")
    root = REPO_ROOT / rel
    if not root.exists():
        return None, (
            410,
            f"源码已不可用（{rel}）—— 证据无法回看。"
            "上传项目的源码副本可能被清理了，请重新分析。",
        )
    return root, None


# ============================================================
# 阶段 1–3：分析（大小 → 策略 → 板块）
# ============================================================


def _load_demo_inputs(project_id: str) -> Tuple[Optional[dict], Optional[dict], Optional[ErrorDetail]]:
    snapshot = _demo_snapshot_path(project_id)
    payload = _read_json(snapshot)
    if not payload:
        return None, None, (
            404,
            f"找不到项目快照：{project_id}。"
            "请先运行 scripts/build_demo_snapshots.py 生成演示快照。",
        )
    source_root = _demo_source_root(project_id)
    if not source_root.exists():
        return None, None, (
            404,
            f"找不到源码目录：{_rel_to_repo(source_root)}（证据无法回看，拒绝在缺源码时产出讲稿）",
        )
    return payload.get("overview") or {}, payload.get("business_graph") or {}, None


def analyze_existing_project(project_id: str, force: bool = False) -> Tuple[Optional[dict], Optional[ErrorDetail]]:
    """为一个**已建快照的演示项目**做平台分析（第一次会落盘缓存）。"""
    from engine.logic_platform import analyze_project as engine_analyze

    project_id = str(project_id or "").strip()
    if not project_id:
        return None, (400, "缺少 project_id")

    cache_dir = _analysis_dir(project_id)
    if not force:
        cached = _read_json(cache_dir / "analysis.json")
        if cached:
            return cached, None

    overview, graph, error = _load_demo_inputs(project_id)
    if error is not None:
        return None, error

    project_name = str((_read_json(_demo_snapshot_path(project_id)) or {}).get("project_name") or project_id)
    analysis = engine_analyze(project_id, project_name, overview, graph)

    _write_json(cache_dir / "meta.json", {
        "analysis_id": project_id,
        "project_id": project_id,
        "project_name": project_name,
        "source_kind": "demo",
        "source_root_rel": _rel_to_repo(_demo_source_root(project_id)),
        "source_hash": str(graph.get("source_hash") or ""),
        "platform_version": _PLATFORM_VERSION,
    })
    _write_json(cache_dir / "graph.json", graph)
    _write_json(cache_dir / "analysis.json", analysis)
    return analysis, None


def analyze_uploaded_project(
    tmp_dir: Path,
    project_dir: Path,
    display_name: str = "",
) -> Tuple[Optional[dict], Optional[ErrorDetail]]:
    """为一个**上传的项目**做平台分析，并**把源码转存下来**。

    ``tmp_dir`` 会在调用方（路由）的 ``finally`` 里被删除，
    所以这里必须先把源码拷进 ``backend/data/logic_platform/<id>/source/``，
    否则学生点"看证据"时源码已经不存在了。

    ``display_name`` 是**用户上传时的文件名派生出来的项目名**。
    为什么需要它：``ProjectAnalyzer`` 从目录名取 ``project_name``，
    而上传项目的目录是 ``tempfile.mkdtemp(prefix="lwai_lp_")`` 造的，
    于是界面上会显示成 ``lwai_lp_ysdaufc2`` —— 一个对用户毫无意义的临时目录名。
    所以有 ``display_name`` 时优先用它（zip 用压缩包名、py 用文件名）。
    """
    from engine.logic_platform import analyze_project as engine_analyze
    from engine.project_analyzer import ProjectAnalyzer

    analysis_id = new_analysis_id()
    target = _analysis_dir(analysis_id)
    source_target = target / "source"
    source_target.mkdir(parents=True, exist_ok=True)

    # ---- 转存源码（保持相对目录结构；跳过噪音目录）----
    copied = 0
    for path in sorted(project_dir.rglob("*.py")):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        try:
            rel = path.relative_to(project_dir)
        except ValueError:
            continue
        dest = source_target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(path, dest)
            copied += 1
        except OSError:
            continue
    if copied == 0:
        return None, (400, "上传的项目里没有可用的 .py 文件，无法分析")

    result = ProjectAnalyzer().analyze(str(project_dir))
    payload = result.to_dict()
    overview = payload.get("overview") or {}
    graph = payload.get("business_graph") or {}
    project_name = str(display_name or "").strip() or str(
        payload.get("project_name") or project_dir.name or analysis_id
    )

    analysis = engine_analyze(analysis_id, project_name, overview, graph)

    _write_json(target / "meta.json", {
        "analysis_id": analysis_id,
        "project_id": analysis_id,
        "project_name": project_name,
        # 分析器自己算出来的名字（临时目录名）也留档，便于排障时对得上
        "analyzer_project_name": str(payload.get("project_name") or ""),
        "source_kind": "upload",
        "source_root_rel": _rel_to_repo(source_target),
        "source_hash": str(graph.get("source_hash") or ""),
        "files_copied": copied,
        "platform_version": _PLATFORM_VERSION,
    })
    _write_json(target / "graph.json", graph)
    _write_json(target / "analysis.json", analysis)
    return analysis, None


#: 转存源码时跳过的目录（与 scripts/build_demo_snapshots.py 的 SKIP_DIRS 同口径）
_SKIP_DIRS = frozenset({
    "__pycache__", ".git", ".hg", ".svn", "venv", ".venv", "env", "node_modules",
    "dist", "build", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox",
})


def get_analysis(analysis_id: str, force: bool = False) -> Tuple[Optional[dict], Optional[ErrorDetail]]:
    """取分析结果。``analysis_id`` 既可以是演示项目 id，也可以是 ``lp_*``。"""
    analysis_id = str(analysis_id or "").strip()
    if not analysis_id:
        return None, (400, "缺少 analysis_id")

    meta = _read_json(_analysis_dir(analysis_id) / "meta.json")
    if meta and not force:
        cached = _read_json(_analysis_dir(analysis_id) / "analysis.json")
        if cached:
            return cached, None

    if analysis_id.startswith("lp_"):
        return None, (
            404,
            f"找不到上传分析：{analysis_id}（上传分析不落快照，分析结果存在 "
            "backend/data/logic_platform/ 下；若已被清理请重新上传）",
        )
    # 没缓存过 → 当作演示项目现算
    return analyze_existing_project(analysis_id, force=force)


def get_size(analysis_id: str) -> Tuple[Optional[dict], Optional[ErrorDetail]]:
    analysis, error = get_analysis(analysis_id)
    if error is not None:
        return None, error
    return (analysis or {}).get("size") or {}, None


def get_sections(analysis_id: str) -> Tuple[Optional[dict], Optional[ErrorDetail]]:
    analysis, error = get_analysis(analysis_id)
    if error is not None:
        return None, error
    return (analysis or {}).get("sections") or {}, None


def get_section(analysis_id: str, section_id: str) -> Tuple[Optional[dict], Optional[ErrorDetail]]:
    sections, error = get_sections(analysis_id)
    if error is not None:
        return None, error
    for section in (sections or {}).get("sections") or []:
        if str(section.get("section_id")) == str(section_id):
            return section, None
    return None, (404, f"板块不存在：{section_id}")


# ============================================================
# 阶段 4–5：讲稿 + 校验
# ============================================================


def _lesson_path(analysis_id: str, capability_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in str(capability_id))
    return _analysis_dir(analysis_id) / "lessons" / f"{safe}.json"


def _lessons_index_path(analysis_id: str) -> Path:
    return _analysis_dir(analysis_id) / "lessons" / "_index.json"


def _update_lessons_index(analysis_id: str, capability_id: str, section_id: str, summary: dict) -> None:
    index = _read_json(_lessons_index_path(analysis_id)) or {"lessons": {}}
    lessons = index.setdefault("lessons", {})
    lessons[str(capability_id)] = {
        "capability_id": str(capability_id),
        "section_id": str(section_id),
        "generated": True,
        "can_publish": bool(summary.get("can_publish")),
        "review_status": str(summary.get("review_status") or ""),
        "segments": int(summary.get("segments") or 0),
    }
    _write_json(_lessons_index_path(analysis_id), index)


def get_lessons_index(analysis_id: str) -> Tuple[Optional[dict], Optional[ErrorDetail]]:
    _, error = get_analysis(analysis_id)
    if error is not None:
        return None, error
    index = _read_json(_lessons_index_path(analysis_id)) or {"lessons": {}}
    return index, None


def _load_reviews(analysis_id: str) -> dict:
    return _read_json(_analysis_dir(analysis_id) / "reviews.json") or {
        "reviews_version": "1.0",
        "source_hash": "",
        "lessons": {},
    }


def _current_source_hash(analysis_id: str) -> str:
    meta = _read_json(_analysis_dir(analysis_id) / "meta.json") or {}
    return str(meta.get("source_hash") or "")


def _apply_reviews(lesson: dict, analysis_id: str, capability_id: str) -> dict:
    """把教师审核记录合并进讲稿，并做 **stale 判定**。

    README §6.1 的纪律：源码哈希一变，旧审核**不能静默覆盖**新结果，
    必须返回 ``stale``。这里如实实现：哈希不一致时把审核结果标成
    ``stale=true`` 并**不采纳**，同时把原因写进 ``blocking_issues``，
    让界面上看得见"这份审核已经失效，请重新确认"。
    """
    reviews = _load_reviews(analysis_id)
    stored_hash = str(reviews.get("source_hash") or "")
    current_hash = _current_source_hash(analysis_id)
    entry = (reviews.get("lessons") or {}).get(str(capability_id)) or {}
    review = lesson.get("review") if isinstance(lesson.get("review"), dict) else {}

    if not entry:
        # ⚠️ 没有审核记录时**必须重算** can_publish，不能沿用读进来的旧值。
        #
        # 真实踩到的 bug：教师「确认」后讲稿被写盘（can_publish=True），
        # 随后调「重置审核」→ 这里只把 human_review 置成 none，
        # 却把磁盘上那份 can_publish=True 原样留下并写回 ——
        # 于是"已重置"的课仍然是可发布状态。发布权归教师，
        # 没有教师确认就不许是 True，这是硬语义。
        review["human_review"] = {"status": "none", "stale": False, "claims": {}}
        review["can_publish"] = False
        review["status"] = (
            "rejected" if not review.get("verification_passed") else "needs_review"
        )
        lesson["review"] = review
        return lesson

    stale = bool(stored_hash and current_hash and stored_hash != current_hash)
    review["human_review"] = {
        "status": "stale" if stale else str(entry.get("status") or "none"),
        "stale": stale,
        "reviewer": str(entry.get("reviewer") or ""),
        "updated_at": str(entry.get("updated_at") or ""),
        "claims": dict(entry.get("claims") or {}),
        "note": str(entry.get("note") or ""),
        "stored_source_hash": stored_hash,
        "current_source_hash": current_hash,
    }
    if stale:
        blocking = list(review.get("blocking_issues") or [])
        blocking.append(
            "源码在上次审核之后发生了变化（source_hash 不一致）—— "
            "此前的审核结论已失效（stale），必须重新确认，系统不会沿用它。"
        )
        review["blocking_issues"] = blocking
        review["can_publish"] = False
        review["status"] = "needs_review"
    elif review["human_review"]["status"] == "confirmed":
        # 教师确认过、且源码没变 → 这是唯一能把状态推到 approved 的路径。
        # 仍然要求**机械复核通过**：教师确认不能覆盖"引用对不上源码"这种硬错误。
        verification_passed = bool(review.get("verification_passed"))
        review["can_publish"] = bool(verification_passed)
        review["status"] = "approved" if verification_passed else "needs_review"
        if not verification_passed:
            blocking = list(review.get("blocking_issues") or [])
            blocking.append(
                "教师已确认，但机械复核未通过（引用与磁盘源码不符）——"
                "发布仍被拦住：教师确认不能覆盖「引用不成立」这类硬错误。"
            )
            review["blocking_issues"] = blocking
    elif review["human_review"]["status"] == "rejected":
        review["status"] = "rejected"
        review["can_publish"] = False
    lesson["review"] = review
    return lesson


def build_lesson(
    analysis_id: str,
    capability_id: str,
    regenerate: bool = False,
) -> Tuple[Optional[dict], Optional[ErrorDetail]]:
    """生成（或读缓存）一课讲稿，并跑确定性校验。

    缓存策略：**已生成过就直接读盘**，不重复生成 ——
    讲稿是确定性的（同源码同结果），重复生成只是浪费；
    要重算请显式传 ``regenerate=True``。
    """
    from engine.logic_platform import build_lesson_for

    analysis, error = get_analysis(analysis_id)
    if error is not None:
        return None, error
    source_root, error = resolve_source_root(analysis_id)
    if error is not None:
        return None, error
    graph = _read_json(_analysis_dir(analysis_id) / "graph.json") or {}

    if not regenerate:
        cached = _read_json(_lesson_path(analysis_id, capability_id))
        if cached:
            return _apply_reviews(cached, analysis_id, capability_id), None

    capability_id = str(capability_id or "").strip()
    if not capability_id:
        return None, (400, "缺少 capability_id")

    # 只有"进入课程预算"的能力点才能生成 —— 超出预算的要如实拒绝，并给出建议
    target: Optional[dict] = None
    parent_section: Optional[dict] = None
    for section in ((analysis or {}).get("sections") or {}).get("sections") or []:
        for capability in section.get("capabilities") or []:
            if str(capability.get("capability_id")) == capability_id:
                target, parent_section = capability, section
                break
        if target is not None:
            break

    if target is None or parent_section is None:
        return None, (404, f"能力点不存在：{capability_id}（它可能超出本级板块/能力点预算，未在本次展示）")

    walkthrough_info = target.get("walkthrough") or {}
    if not walkthrough_info.get("available"):
        return None, (
            409,
            f"该能力点本级不生成课程：{walkthrough_info.get('reason') or '超出本级预算'}。"
            "板块分析与证据仍然完整可看。",
        )

    built = build_lesson_for(
        analysis=analysis,
        capability_id=capability_id,
        source_root=str(source_root),
        graph=graph,
        lesson_number=1,
        run_verification=True,
    )
    if not built.get("ok"):
        return None, (500, str(built.get("error") or "讲稿生成失败"))

    lesson = built["lesson"]
    _write_json(_lesson_path(analysis_id, capability_id), lesson)
    _update_lessons_index(
        analysis_id, capability_id, str(parent_section.get("section_id") or ""),
        {
            "can_publish": (lesson.get("review") or {}).get("can_publish"),
            "review_status": (lesson.get("review") or {}).get("status"),
            "segments": len(lesson.get("segments") or []),
        },
    )
    return _apply_reviews(lesson, analysis_id, capability_id), None


def verify_lesson(analysis_id: str, capability_id: str) -> Tuple[Optional[dict], Optional[ErrorDetail]]:
    """单独重跑校验器（评审时用：证明"现在这一刻"引用仍然成立）。"""
    from engine.logic_platform import verify as engine_verify

    lesson, error = build_lesson(analysis_id, capability_id)
    if error is not None:
        return None, error
    source_root, error = resolve_source_root(analysis_id)
    if error is not None:
        return None, error
    report = engine_verify.verify_lesson(lesson, str(source_root))
    return {
        "lesson_id": lesson.get("lesson_id"),
        "capability_id": capability_id,
        "report": report.to_dict(),
        "summary": engine_verify.summarize_for_students(report),
    }, None


# ============================================================
# 源码切片（证据跳转的落点）
# ============================================================


def read_source(
    analysis_id: str,
    relative_path: str,
    start: Optional[int] = None,
    end: Optional[int] = None,
    context: int = 5,
) -> Tuple[Optional[dict], Optional[ErrorDetail]]:
    """读项目内**相对路径**的源码切片，带上下文行。

    与 ``project_store.read_source`` 的返回结构保持一致
    （``{file, total_lines, start, end, window_start, window_end, lines[{number,text}]}``），
    这样前端可以复用同一个 ``SourceViewerModal``。

    **不做 basename 兜底**：``project_store`` 有一个"找不到就按文件名找"的兼容分支，
    那是历史包袱（演示源码目录是扁平的）。本平台一律要求完整相对路径 ——
    同名文件兜底会跳到错误的文件，而"跳错证据"比"跳不过去"严重得多。
    """
    if not relative_path:
        return None, (400, "缺少 path")
    normalized = str(relative_path).replace("\\", "/").lstrip("/")
    if ".." in normalized.split("/"):
        return None, (400, "路径不允许包含 ..")

    source_root, error = resolve_source_root(analysis_id)
    if error is not None:
        return None, error

    target = (source_root / normalized).resolve()
    try:
        target.relative_to(source_root.resolve())
    except ValueError:
        return None, (400, "路径越界：只能读项目内的文件")

    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None, (404, f"源码不存在或不可读：{normalized}（项目 {analysis_id}）")

    lines = text.splitlines()
    total = len(lines)
    first = max(1, int(start or 1))
    last = min(total, int(end or total))
    if last < first:
        last = first
    window_start = max(1, first - context)
    window_end = min(total, last + context)
    return {
        "file": normalized,
        "resolved_file": normalized,
        "total_lines": total,
        "start": first,
        "end": last,
        "window_start": window_start,
        "window_end": window_end,
        "lines": [
            {"number": number, "text": lines[number - 1]}
            for number in range(window_start, window_end + 1)
        ],
    }, None


# ============================================================
# 阶段 6：教师审核
# ============================================================


def save_review(
    analysis_id: str,
    capability_id: str,
    payload: dict,
) -> Tuple[Optional[dict], Optional[ErrorDetail]]:
    """确认 / 拒绝一课（可细化到单条断言）。

    写入时会绑定**当前** ``source_hash``；源码一变，这份审核自动变
    ``stale``（见 :func:`_apply_reviews`）。
    """
    lesson, error = build_lesson(analysis_id, capability_id)
    if error is not None:
        return None, error

    status = str((payload or {}).get("status") or "").strip().lower()
    if status not in ("confirmed", "rejected", "reset"):
        return None, (400, "status 必须是 confirmed / rejected / reset 之一")

    claims_in = (payload or {}).get("claims") or {}
    if not isinstance(claims_in, dict):
        return None, (400, "claims 必须是 {claim_id: {decision, note}} 形式")

    valid_claim_ids = set()
    for segment in lesson.get("segments") or []:
        for key in ("must_remember", "know_enough"):
            for claim in segment.get(key) or []:
                valid_claim_ids.add(str(claim.get("claim_id") or ""))
        summary = segment.get("one_sentence_summary")
        if isinstance(summary, dict):
            valid_claim_ids.add(str(summary.get("claim_id") or ""))

    claims: Dict[str, Any] = {}
    unknown: List[str] = []
    for claim_id, decision in claims_in.items():
        if str(claim_id) not in valid_claim_ids:
            unknown.append(str(claim_id))
            continue
        if not isinstance(decision, dict):
            continue
        verdict = str(decision.get("decision") or "").strip().lower()
        if verdict not in ("confirm", "reject"):
            return None, (400, f"断言 {claim_id} 的 decision 必须是 confirm / reject")
        claims[str(claim_id)] = {
            "decision": verdict,
            "note": str(decision.get("note") or "")[:400],
            "at": _now_iso(),
        }
    if unknown:
        # 「学生文本不被静默丢弃」的同一条纪律：未知 id 一律拒绝，不猜
        return None, (400, f"未知的 claim_id：{'、'.join(sorted(unknown)[:5])}")

    reviews = _load_reviews(analysis_id)
    if status == "reset":
        (reviews.get("lessons") or {}).pop(str(capability_id), None)
    else:
        reviews["lessons"] = reviews.get("lessons") or {}
        reviews["lessons"][str(capability_id)] = {
            "status": status,
            "reviewer": str((payload or {}).get("reviewer") or "")[:80],
            "note": str((payload or {}).get("note") or "")[:1000],
            "claims": claims,
            "updated_at": _now_iso(),
        }
    # 每次审核都绑定当前的源码哈希
    reviews["source_hash"] = _current_source_hash(analysis_id)
    reviews["reviews_version"] = "1.0"
    _write_json(_analysis_dir(analysis_id) / "reviews.json", reviews)

    updated = _apply_reviews(lesson, analysis_id, capability_id)
    # 审核后状态可能变化，同步索引与讲稿缓存
    _write_json(_lesson_path(analysis_id, capability_id), updated)
    _update_lessons_index(
        analysis_id, capability_id, "", {
            "can_publish": (updated.get("review") or {}).get("can_publish"),
            "review_status": (updated.get("review") or {}).get("status"),
            "segments": len(updated.get("segments") or []),
        },
    )
    return {
        "analysis_id": analysis_id,
        "capability_id": capability_id,
        "review": updated.get("review") or {},
        "can_publish": (updated.get("review") or {}).get("can_publish"),
        "status": (updated.get("review") or {}).get("status"),
    }, None


def _now_iso() -> str:
    """审核记录的时间戳。

    **只在审核存储里出现**，不进讲稿契约 —— 讲稿必须是对源码的纯函数，
    带时间戳会让"同一份源码两次生成逐字节一致"这条断言失效。
    """
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ============================================================
# 可选：LLM 讲解层（默认关闭）
# ============================================================


def apply_narration(
    analysis_id: str,
    capability_id: str,
    narration: Optional[dict] = None,
    provider: Optional[str] = None,
) -> Tuple[Optional[dict], Optional[ErrorDetail]]:
    """把 LLM 讲解合进讲稿（逐条把关 + 重跑校验）。

    ``narration`` 为空时，尝试用 ``narration_service.request_narration`` 去取；
    讲解服务未配置（默认）时返回 **503**，并明确说明"平台默认关闭 LLM 讲解层"——
    **不静默降级、不假装生成过**。
    """
    from engine.logic_platform import narration as engine_narration

    lesson, error = build_lesson(analysis_id, capability_id)
    if error is not None:
        return None, error
    source_root, error = resolve_source_root(analysis_id)
    if error is not None:
        return None, error

    if narration is None:
        try:
            from . import narration_service
        except Exception as exc:  # pragma: no cover - 只在缺模块时触发
            return None, (500, f"讲解服务不可用：{exc}")
        narration, error = narration_service.request_narration(lesson, provider=provider)
        if error is not None:
            return None, error
        if narration is None:
            return None, (
                503,
                "LLM 讲解层未启用。平台默认关闭它：确定性事实层与证据校验不依赖任何模型。"
                "如需启用，请配置 LWAI_NARRATION_PROVIDER / LWAI_NARRATION_BASE_URL / "
                "LWAI_NARRATION_API_KEY 后重启后端，并在请求里显式指定 provider。",
            )

    updated, outcome = engine_narration.apply_narration(lesson, narration, str(source_root))
    _write_json(_lesson_path(analysis_id, capability_id), updated)
    return {
        "analysis_id": analysis_id,
        "capability_id": capability_id,
        "outcome": outcome.to_dict(),
        "review": updated.get("review") or {},
        "lesson": updated,
    }, None


def narration_status() -> dict:
    """讲解层当前状态（给界面显示"这个平台有没有用 AI"用）。"""
    try:
        from . import narration_service

        return narration_service.status()
    except Exception as exc:  # pragma: no cover
        return {
            "enabled": False,
            "reason": f"讲解服务模块不可用：{exc}",
            "detached_from_engine": True,
        }
