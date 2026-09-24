"""
项目仓库（P0-09 / P0-13）

职责
----
1. 把"前端快照 + 后端答案表 + 演示源码"看成同一个项目的三份产物，统一按
   ``project_id`` 定位；
2. 对外只暴露**项目内相对路径**的源码读取（P0-09：证据跳转不能再用 basename，
   也不能读项目目录以外的任何文件）；
3. 为判题提供**只存在于后端**的答案表（P0-11）。

目录约定
--------
```text
frontend/public/demo/                       # 默认项目（lab_safety_assistant）
├── project_analysis.json                   # 学生契约（无答案、无讲解）
├── source/                                 # 证据跳转用的源码副本
└── projects/<project_id>/                  # 其他演示项目
    ├── project_analysis.json
    └── source/...

backend/data/answer_keys/<project_id>.json  # 只存在于后端
```

设计取舍
--------
演示项目是**快照**，不是实时分析。这样做的原因见 README2 §五：
现场不跑实时分析，避免卡住整场。实时分析走 ``POST /api/analyze``，
它会把答案表存到 ``backend/data/answer_keys/<analysis_id>.json``，
所以两种模式共用同一套判题接口。
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Dict, List, Optional

#: 仓库根目录（backend/app/services/project_store.py → parents[3]）
REPO_ROOT = Path(__file__).resolve().parents[3]

#: 前端演示快照根目录
DEMO_ROOT = REPO_ROOT / "frontend" / "public" / "demo"

#: 其他演示项目所在目录
PROJECTS_ROOT = DEMO_ROOT / "projects"

#: 后端私有数据目录（答案表）
DATA_ROOT = REPO_ROOT / "backend" / "data"

#: 默认演示项目
DEFAULT_PROJECT_ID = "lab_safety_assistant"

_LOCATION_RE = re.compile(r"^(?P<path>.+?):(?P<start>\d+)(?:-(?P<end>\d+))?$")


# ============================================================
# 项目定位
# ============================================================

def demo_source_root(project_id: str) -> Path:
    """返回演示项目的源码根目录。"""
    if project_id == DEFAULT_PROJECT_ID:
        return DEMO_ROOT / "source"
    return PROJECTS_ROOT / project_id / "source"


def snapshot_path(project_id: str) -> Path:
    """返回项目的学生契约快照路径。"""
    if project_id == DEFAULT_PROJECT_ID:
        return DEMO_ROOT / "project_analysis.json"
    return PROJECTS_ROOT / project_id / "project_analysis.json"


def answer_key_path(project_id: str) -> Path:
    """返回项目的答案表路径（只存在于后端）。"""
    return DATA_ROOT / "answer_keys" / f"{project_id}.json"


def _read_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def list_projects() -> List[dict]:
    """列出所有可用项目（默认项目 + ``projects/`` 下的所有子目录）。"""
    projects: List[dict] = []

    def _describe(project_id: str, path: Path) -> dict:
        snapshot = _read_json(path)
        overview = (snapshot or {}).get("overview", {})
        return {
            "project_id": project_id,
            "project_name": (snapshot or {}).get("project_name", project_id),
            "contract_version": (snapshot or {}).get("contract_version"),
            "has_snapshot": snapshot is not None,
            "has_answer_key": answer_key_path(project_id).exists(),
            "has_source": demo_source_root(project_id).exists(),
            "total_lines": overview.get("total_lines", 0),
            "module_count": overview.get("module_count", 0),
        }

    default_path = snapshot_path(DEFAULT_PROJECT_ID)
    if default_path.exists():
        projects.append(_describe(DEFAULT_PROJECT_ID, default_path))

    if PROJECTS_ROOT.exists():
        for child in sorted(PROJECTS_ROOT.iterdir()):
            if not child.is_dir():
                continue
            path = child / "project_analysis.json"
            if path.exists():
                projects.append(_describe(child.name, path))

    return projects


def load_snapshot(project_id: str, teacher_mode: bool = False) -> Optional[dict]:
    """读取项目契约快照。

    Args:
        teacher_mode: 为 ``True`` 时返回带答案与讲解的版本。
            当前实现里学生快照本身就已经不含答案，因此教师模式会尝试
            用后端答案表把 ``correct_answers`` / ``explanation`` 补回去，
            供教师预览使用（README3 §6.5）。
    """
    snapshot = _read_json(snapshot_path(project_id))
    if snapshot is None:
        return None
    if not teacher_mode:
        return snapshot

    key = load_answer_key(project_id)
    if not key:
        return snapshot

    questions = list((snapshot.get("training") or {}).get("questions", []) or [])
    enriched = []
    for index, question in enumerate(questions):
        entry = (key.get("questions") or {}).get(str(index), {})
        enriched.append({
            **question,
            "correct_answers": entry.get("answers", []),
            "explanation": entry.get("explanation", ""),
        })
    return {
        **snapshot,
        "training": {**(snapshot.get("training") or {}), "questions": enriched},
        "teacher_mode": True,
    }


def load_answer_key(project_id: str) -> Optional[dict]:
    """读取后端答案表。"""
    return _read_json(answer_key_path(project_id))


def save_answer_key(project_id: str, answer_key: dict) -> Path:
    """保存答案表（只写后端目录，绝不进入前端快照）。"""
    path = answer_key_path(project_id)
    _write_json(path, answer_key)
    return path


# ============================================================
# 源码切片（P0-09）
# ============================================================

def _safe_join(root: Path, relative: str) -> Optional[Path]:
    """把项目内相对路径安全地拼到 root 下；越界返回 ``None``。"""
    if not relative:
        return None
    cleaned = relative.replace("\\", "/").lstrip("/")
    if ".." in cleaned.split("/"):
        return None
    candidate = (root / cleaned).resolve()
    try:
        root_resolved = root.resolve()
        candidate.relative_to(root_resolved)
    except (ValueError, OSError):
        return None
    return candidate


def read_source(
    project_id: str,
    relative_path: str,
    start: Optional[int] = None,
    end: Optional[int] = None,
) -> Optional[dict]:
    """读取项目内某个文件的源码切片。

    Returns:
        ``{"file", "total_lines", "start", "end", "code", "lines": [...]}``；
        文件不存在或路径越界时返回 ``None``。

        文件路径可以是项目内任意相对路径（含子目录），
        所以不同目录下的同名文件不会跳错 —— 这正是 P0-09 要修的问题。
    """
    root = demo_source_root(project_id)
    target = _safe_join(root, relative_path)
    if target is None or not target.is_file():
        # 兼容：演示源码目录是扁平的，允许退化为按文件名查找
        fallback = _safe_join(root, Path(relative_path).name)
        if fallback is None or not fallback.is_file():
            return None
        target = fallback

    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    all_lines = text.splitlines()
    total = len(all_lines)

    first = max(1, int(start)) if start else 1
    last = min(total, int(end)) if end else total
    if last < first:
        last = first

    # 带上前后文，便于"证据弹窗"展示上下文
    context = 5
    window_start = max(1, first - context)
    window_end = min(total, last + context)

    return {
        "file": relative_path.replace("\\", "/"),
        "resolved_file": str(target.relative_to(root.resolve()).as_posix())
        if target.is_relative_to(root.resolve()) else Path(relative_path).name,
        "total_lines": total,
        "start": first,
        "end": last,
        "window_start": window_start,
        "window_end": window_end,
        "lines": [
            {"number": number, "text": all_lines[number - 1]}
            for number in range(window_start, window_end + 1)
        ],
    }


def parse_location(location: str) -> tuple[Optional[str], Optional[int], Optional[int]]:
    """把 ``path/to/file.py:88`` 或 ``path/to/file.py:88-120`` 拆成三段。"""
    if not location:
        return None, None, None
    match = _LOCATION_RE.match(location.strip())
    if not match:
        return location.strip() or None, None, None
    start = int(match.group("start"))
    end = int(match.group("end")) if match.group("end") else start
    return match.group("path"), start, end


# ============================================================
# 判题（P0-11）
# ============================================================

def grade_answer(project_id: str, question_index: int, selected: List[str]) -> Optional[dict]:
    """后端判题。

    返回：
        ``{"result": "correct|partial|wrong|not_available", "matched": [...],
        "missing": [...], "extra": [...], "explanation": str,
        "knowledge_points": [...]}``

    **正确答案本身不会返回给学生** —— 学生只得到"对/部分对/不对"和讲解。
    讲解里可能包含正确答案（教学需要），但它只在**已经作答之后**才下发。
    """
    key = load_answer_key(project_id)
    if not key:
        return None

    entry = (key.get("questions") or {}).get(str(question_index))
    if not entry:
        return None

    expected = set(entry.get("answers", []) or [])
    given = {str(item).strip().upper() for item in (selected or []) if str(item).strip()}

    matched = sorted(expected & given)
    missing = sorted(expected - given)
    extra = sorted(given - expected)

    if not given:
        result = "wrong"
    elif not extra and not missing:
        result = "correct"
    elif matched:
        result = "partial"
    else:
        result = "wrong"

    return {
        "question_index": question_index,
        "result": result,
        "matched": matched,
        "missing": missing,
        "extra": extra,
        "explanation": entry.get("explanation", ""),
        "knowledge_points": entry.get("knowledge_points", []),
        "question_type": entry.get("question_type", ""),
    }


def grade_flow_order(project_id: str, question_index: int, order: List[str]) -> Optional[dict]:
    """流程排序题的判题（当前与选择题共用同一答案表）。

    单独留一个入口是为了 Sprint 1 引入 ``checkpoint_id`` 后做真正的序列判定。
    """
    return grade_answer(project_id, question_index, order)


# ============================================================
# 实时分析产物的答案表
# ============================================================

def new_analysis_id() -> str:
    return f"live_{uuid.uuid4().hex[:12]}"


def save_live_answer_key(analysis_id: str, answer_key: dict) -> Path:
    """保存实时分析的答案表。"""
    path = DATA_ROOT / "answer_keys" / f"{analysis_id}.json"
    _write_json(path, answer_key)
    return path


def build_answer_key_payload(source_name: str, answer_key: dict) -> dict:
    """把引擎输出的答案表包装成后端存储格式。"""
    return {
        "contract_version": "1.0",
        "project_id": source_name,
        "questions": answer_key,
    }
