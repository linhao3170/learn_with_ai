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

它是学生快照的唯一写出方（WO-04 一轮）
--------------------------------------
``frontend/public/demo/`` 下的学生快照**只有本脚本能写**（唯一写出函数
``write_student_snapshot``）。旧管线冒烟（``test_project_analyzer.py`` /
``test_deep_analyzer.py`` / ``test_full_engine.py``）曾经写回同一个路径，于是
"跑冒烟"与"跑产物脚本"的先后顺序会改变学生在页面上看到的内容 ——
这就是 ``docs/07`` §17.2 记的**顺序陷阱**（``docs/08`` §19.1 第 22 条）。

现在那三个冒烟脚本只写 ``validation/results/`` 下的调试产物，并且各自在
**同一次运行内**跑前跑后取一次学生快照的内容 sha256（`student_snapshot_state()`
另带 mtime），断言逐个相同（``assert_student_snapshots_unchanged``）。守卫
**只比"前后是否相同"**，不写死任何哈希值 —— 题目一变产物就变，写死的哈希合并后必然失效。

用法
----
    python scripts/build_demo_snapshots.py
    python scripts/build_demo_snapshots.py --project sample_projects/lab_safety_assistant

守卫（给冒烟脚本用的共用 API）
------------------------------
    from scripts.build_demo_snapshots import (
        student_snapshot_state, assert_student_snapshots_unchanged,
    )
"""

from __future__ import annotations

import argparse
import hashlib
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

#: 守卫的覆盖范围：`frontend/public/demo/` 下的**全部**文件（递归）。
#:
#: 刻意**不排除** `analysis_output.json` —— 它由 `scripts/generate_web_data.py` 生成、
#: 被 App 的旧分析页真的在读，所以它同样是"学生看得见的内容"，
#: 而 `test_full_engine.py` 从 `frontend/public` 这个 cwd 跑时覆盖的正是它（顺序陷阱的实测落点）。
#: `student_manager.py` 是那个脚本的**输入**（`docs/90-archive.md` 附录 C 有记录），但它在同一个
#: 目录、也不是任何脚本的产物，所以一并纳入：冒烟脚本没有任何理由写这个目录里的东西。
DEMO_GUARD_EXCLUDE: tuple[str, ...] = ()

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


def student_snapshot_files() -> list[Path]:
    """列出 `frontend/public/demo/` 下**全部**学生可见文件（递归，按路径排序）。

    覆盖：默认项目的 `project_analysis.json` 与 `source/`（证据源码副本）、
    其它项目的 `projects/<id>/`（快照 + 源码副本）、旧分析页读的 `analysis_output.json`
    与它的输入 `student_manager.py`。见 `DEMO_GUARD_EXCLUDE` 的说明。
    """
    if not DEMO_ROOT.is_dir():
        return []
    excluded = {(REPO_ROOT / rel).resolve() for rel in DEMO_GUARD_EXCLUDE}
    return [
        path
        for path in sorted(DEMO_ROOT.rglob("*"), key=lambda p: p.as_posix())
        if path.is_file() and path.resolve() not in excluded
    ]


def student_snapshot_digests() -> dict[str, str]:
    """学生快照 → 内容 sha256（**只比"前后是否相同"，绝不写死具体值**）。

    题目一变产物就变（`WO-03` 一轮已经改过题目），写死的哈希在合并之后必然失效。
    """
    return {
        path.relative_to(REPO_ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in student_snapshot_files()
    }


def student_snapshot_state() -> dict[str, tuple[str, int]]:
    """学生快照 → ``(sha256, mtime_ns)``。

    为什么要连 `mtime_ns` 一起记（实测理由，`WO-04` 一轮）
    ----------------------------------------------------
    在这份仓库**当前的状态**下，`test_project_analyzer.py` 的旧写法
    （覆盖写 `frontend/public/demo/project_analysis.json`）产出的字节与
    `build_demo_snapshots.py` 的产出**完全相同** —— 因为 `ProjectAnalyzer.to_dict()`
    本来就带 `project_id`（`engine/project_analyzer/main.py:72`），
    而产物脚本那句 `student_payload["project_id"] = project_id` 对默认项目是个**空操作**。
    于是**只看 sha256 抓不到"被写了一遍"**：文件被 `"w"` 模式截断重写、内容却一字不差。

    "冒烟脚本有没有写学生快照"这个问题的正确判据是"**它写了没有**"，
    所以内容哈希之外再记一个 mtime：**sha256 不同 = 内容变了；sha256 相同但 mtime 变了 =
    被覆盖写过一遍**。两种都算踩了顺序陷阱，都要报出来。
    """
    state: dict[str, tuple[str, int]] = {}
    for path in student_snapshot_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        state[rel] = (
            hashlib.sha256(path.read_bytes()).hexdigest(),
            path.stat().st_mtime_ns,
        )
    return state


def assert_student_snapshots_unchanged(
    before: dict[str, tuple[str, int]] | dict[str, str], *, context: str
) -> None:
    """断言学生快照在 `before` 之后**一个都没被写过** —— 旧管线冒烟的顺序陷阱守卫。

    为什么需要它（`docs/08` §19.1 第 22 条 / `docs/07` §17.2 的顺序陷阱）
    ------------------------------------------------------------------
    旧管线冒烟脚本曾经把分析结果写回 `frontend/public/demo/` 下的学生快照，
    于是"跑完冒烟"与"跑完产物脚本"的**顺序**会改变学生在页面上看到的内容，
    而这个陷阱只能靠人记得"跑完冒烟要重跑 `build_demo_snapshots.py`"。
    现在冒烟只写 `validation/results/` 下的调试产物，并由本函数把这条事实钉住：
    **同一次运行内跑冒烟前后，学生快照的内容 sha256（以及 mtime）必须逐个相同。**

    ⚠️ 只比"前后是否相同"，**不写死任何哈希数值** —— 题目一变产物就变。

    `before` 接受两种形状，**两种都要正确比对**（这是踩过的坑）：
    - ``student_snapshot_state()`` → ``{路径: (sha256, mtime_ns)}`` —— 推荐，能抓到
      "字节相同但被覆盖写过"；
    - ``student_snapshot_digests()`` → ``{路径: sha256}`` —— 只比内容，不比 mtime。
      **不能**把它的值与"状态的二元组"直接比：那会把每一个文件都判成变过
      （`WO-04` 一轮的负向对照抓到过这个假阳），所以这里先把两边归一成同一形状。

    诚实边界：`frontend/public/demo/` 不存在时（例如刚克隆、快照还没生成）
    守卫是空转的 —— 它证明不了"将来也不会写"，只能证明"这一次没写"。
    所以它会把比对到的文件数打出来，0 个时明说自己是空转的。
    """
    after = student_snapshot_state()

    def _normalize(value: object) -> tuple[str, int | None]:
        """统一成 ``(sha256, mtime_ns | None)``；``None`` = 这次比对不看 mtime。"""
        if isinstance(value, tuple):
            return (str(value[0]), int(value[1]))
        return (str(value), None)

    before_state = {rel: _normalize(value) for rel, value in before.items()}
    after_state = {rel: _normalize(value) for rel, value in after.items()}

    def _changed(rel: str) -> bool:
        if rel not in before_state or rel not in after_state:
            return True
        old_hash, old_mtime = before_state[rel]
        new_hash, new_mtime = after_state[rel]
        if old_hash != new_hash:
            return True
        # 老调用方只给了内容哈希 → 这一次不比 mtime（不假装知道）
        return old_mtime is not None and old_mtime != new_mtime

    changed = sorted(rel for rel in set(before_state) | set(after_state) if _changed(rel))

    def _what(rel: str) -> str:
        if rel not in before_state:
            return "被新建"
        if rel not in after_state:
            return "被删掉"
        old_hash, old_mtime = before_state[rel]
        new_hash, new_mtime = after_state[rel]
        if old_hash != new_hash:
            return "内容变了（sha256 不同）"
        if old_mtime is not None and old_mtime != new_mtime:
            return "被覆盖写过（字节相同，但 mtime 变了）"
        return "变了（比对形状不一致？）"

    if not changed:
        print(f"[守卫] 学生快照未被写过：{len(after_state)} 个文件（{context}）")
        if not after_state:
            print("[守卫] ⚠️ 没有可比对的快照文件（frontend/public/demo/ 下没有产物）—— 本次守卫是空转的")
        return

    detail = "\n".join(f"  - {rel}：{_what(rel)}" for rel in changed)
    raise AssertionError(
        f"{context} 改动了学生快照（`frontend/public/demo/` 下由 build_demo_snapshots.py 独占的产物）：\n"
        f"{detail}\n"
        "学生快照的唯一写出方是 `python scripts/build_demo_snapshots.py`；"
        "旧管线冒烟只允许写 `validation/results/` 下的调试产物。"
        "（顺序陷阱，见 docs/07 §17.2 与 docs/08 §19.1 第 22 条）"
    )


def write_student_snapshot(payload: dict, snapshot_path: Path) -> Path:
    """学生快照的**唯一写出函数**。

    `frontend/public/demo/` 下的产物只许从这里出（"一份实现"）：这样
    "谁在写学生快照"这个问题全仓只有一个答案，守卫函数也才有唯一的作用对象。
    """
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return snapshot_path


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
    write_student_snapshot(student_payload, snapshot_path)

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
