"""
生成前端演示快照 + 后端答案表（P0-13）

为什么需要这个脚本
------------------
Sprint 0 之前，前端只有一个写死的演示项目和一份写死的业务内容，
"换一个项目页面也能跑"这条验收项根本没法验证。

本脚本把"分析 → 学生快照 → 后端答案表 → 证据源码副本"变成一条可重复执行的流水线：

1. **学生快照**（``frontend/public/demo/...``）：不含 ``correct_answers``、
   不含 ``explanation``（P0-11）；
2. **后端答案表**（``backend/data/answer_keys/<project_id>.json``）：
   只存在于后端，判题接口用它；
3. **证据源码副本**：把项目源码按**项目内相对路径**复制到快照目录下的
   ``source/``，这样证据跳转在离线环境下也成立（P0-09）。

默认生成两个项目：

- ``lab_safety_assistant``（自造教学样本，默认项目，快照落在 demo 根目录）
- ``python_dotenv``（**真实第三方项目**，快照落在 ``demo/projects/python_dotenv/``）

用法
----
    python scripts/build_demo_snapshots.py
    python scripts/build_demo_snapshots.py --project sample_projects/lab_safety_assistant
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # pragma: no cover
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from engine.project_analyzer import ProjectAnalyzer  # noqa: E402

DEMO_ROOT = REPO_ROOT / "frontend" / "public" / "demo"
PROJECTS_ROOT = DEMO_ROOT / "projects"
ANSWER_KEY_ROOT = REPO_ROOT / "backend" / "data" / "answer_keys"

DEFAULT_PROJECT_ID = "lab_safety_assistant"

#: 参与构建的项目：``(源目录, project_id, 是否默认项目)``
DEFAULT_TARGETS = [
    ("sample_projects/lab_safety_assistant", DEFAULT_PROJECT_ID, True),
    ("validation/python_dotenv", "python_dotenv", False),
]

#: 复制源码时跳过的目录
SKIP_DIRS = {
    "__pycache__", ".git", "venv", "env", ".venv", "node_modules",
    "dist", "build", "tests", "test", ".pytest_cache",
}


def _copy_sources(project_dir: Path, dest: Path) -> int:
    """按项目内相对路径复制 .py 源码，保留目录结构（P0-09）。"""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    count = 0
    for path in sorted(project_dir.rglob("*.py")):
        relative = path.relative_to(project_dir)
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        count += 1
    return count


def build_one(project_path: str, project_id: str, is_default: bool) -> dict:
    """分析一个项目并写出快照、答案表与源码副本。"""
    source_dir = (REPO_ROOT / project_path).resolve()
    if not source_dir.is_dir():
        return {"project_id": project_id, "status": "missing", "path": str(source_dir)}

    result = ProjectAnalyzer().analyze(str(source_dir))

    # 1) 学生快照（无答案、无讲解）
    student_payload = result.to_dict()
    student_payload["project_id"] = project_id
    if is_default:
        snapshot_path = DEMO_ROOT / "project_analysis.json"
        source_dest = DEMO_ROOT / "source"
    else:
        snapshot_path = PROJECTS_ROOT / project_id / "project_analysis.json"
        source_dest = PROJECTS_ROOT / project_id / "source"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(
        json.dumps(student_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 2) 后端答案表（含 correct_answers 与 explanation）
    answer_payload = {
        "contract_version": "1.0",
        "project_id": project_id,
        "source": project_path,
        "questions": result.training_answer_key,
    }
    ANSWER_KEY_ROOT.mkdir(parents=True, exist_ok=True)
    answer_key_path = ANSWER_KEY_ROOT / f"{project_id}.json"
    answer_key_path.write_text(
        json.dumps(answer_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 3) 证据源码副本
    copied = _copy_sources(source_dir, source_dest)

    return {
        "project_id": project_id,
        "status": "ok",
        "source_dir": project_path,
        "snapshot": str(snapshot_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "answer_key": str(answer_key_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "source_files_copied": copied,
        "modules": len(student_payload.get("modules", [])),
        "flows": len(student_payload.get("core_flows", [])),
        "questions": len(student_payload.get("training", {}).get("questions", [])),
        "total_lines": student_payload.get("overview", {}).get("total_lines", 0),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="生成演示快照、答案表与证据源码副本")
    parser.add_argument(
        "--project", action="append", default=None,
        help="只处理指定项目目录（可重复），默认为内置的两个项目",
    )
    args = parser.parse_args()

    targets = DEFAULT_TARGETS
    if args.project:
        targets = []
        for raw in args.project:
            path = Path(raw)
            project_id = path.name
            targets.append((str(path), project_id, project_id == DEFAULT_PROJECT_ID))

    print("=" * 72)
    print("构建演示快照 / 答案表 / 证据源码副本")
    print("=" * 72)

    reports = []
    for project_path, project_id, is_default in targets:
        report = build_one(project_path, project_id, is_default)
        reports.append(report)
        print()
        if report["status"] != "ok":
            print(f"[跳过] {project_id}: 目录不存在 {report.get('path')}")
            continue
        print(f"[完成] {project_id}")
        print(f"        源码目录    : {report['source_dir']}")
        print(f"        学生快照    : {report['snapshot']}")
        print(f"        后端答案表  : {report['answer_key']}")
        print(f"        源码副本    : {report['source_files_copied']} 个文件")
        print(f"        模块/流程/题: {report['modules']} / {report['flows']} / {report['questions']}")
        print(f"        代码行数    : {report['total_lines']}")

    print()
    ok = [r for r in reports if r["status"] == "ok"]
    print(f"共 {len(ok)}/{len(reports)} 个项目构建成功")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
