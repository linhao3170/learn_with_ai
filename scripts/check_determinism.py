"""
确定性双跑校验（Sprint 0 验收 / README5 §3.9）

README4 的核心卖点之一是"可复现"：同一份代码 + 同一算法版本 → 同一份输出。
在 Sprint 0 之前这条**并不成立**，原因有三个（README5 §1.2-⑨）：

1. ``QuizGenerator`` 默认不播种，用的还是全局 ``random``；
2. ``TrainingGenerator`` 用 ``random.seed()`` 改全局状态，同进程互相污染；
3. ``ProjectParser`` 的 ``os.walk`` 未排序，文件顺序依赖文件系统。

本脚本在**同一个进程内连续分析两次**（这是最严格的检查：全局随机状态、
缓存、模块级可变状态都会被暴露），逐字段比对两次输出。

⚠️ **同进程双跑查不出"set 迭代顺序"这一类问题**（README §19.2 ⑳ 的教训）：
Python 的字符串哈希**每个进程都不同**，但同一个进程里两次跑的哈希顺序是一样的，
所以"集合 → 列表 → 拼进文本"这种写法在同进程双跑下**永远一致**，
换一个进程就变了（实测：同一个 `build_demo_snapshots.py` 连续两次跑出的
学生快照 sha256 不同）。因此本脚本还有 `--cross-process` 模式：
用**不同的 PYTHONHASHSEED** 各起一个子进程，比对两次产出的**字节**。
（不指定种子、只跑两次子进程是不够的 —— 那两次有可能碰巧一致。）

用法
----
    python scripts/check_determinism.py
    python scripts/check_determinism.py --project validation/python_dotenv
    python scripts/check_determinism.py --project a --project b --verbose
    python scripts/check_determinism.py --cross-process        # 跨进程（不同 PYTHONHASHSEED）

退出码：0 = 完全一致；1 = 存在差异（并打印第一处差异路径）。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # pragma: no cover
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

DEFAULT_PROJECTS = [
    "sample_projects/lab_safety_assistant",
    "validation/python_dotenv",
]

#: `--cross-process` 用的子进程代码：分析一个项目并把结果写进指定文件。
#: **写文件而不是走管道**：受限沙箱下"通过管道捕获原生程序输出"会被拒
#: （README §19.5），写文件两种模式下都能跑。
_CHILD_CODE = (
    "import json, sys\n"
    "from pathlib import Path\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "from engine.project_analyzer import ProjectAnalyzer\n"
    "payload = ProjectAnalyzer().analyze(sys.argv[2]).to_dict()\n"
    "Path(sys.argv[3]).write_text(\n"
    "    json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str), encoding='utf-8')\n"
)

#: 用来制造"不同哈希顺序"的种子（0/1 已足够：字符串哈希顺序必然不同）
_HASH_SEEDS = ("0", "1")


def _first_difference(a, b, path: str = "$"):
    """返回 ``(差异路径, 左值, 右值)``；完全一致时返回 ``None``。"""
    if type(a) is not type(b):
        return path, f"<{type(a).__name__}>", f"<{type(b).__name__}>"

    if isinstance(a, dict):
        if set(a) != set(b):
            only_left = sorted(set(a) - set(b))
            only_right = sorted(set(b) - set(a))
            return path, f"多出 {only_left}", f"多出 {only_right}"
        for key in a:
            diff = _first_difference(a[key], b[key], f"{path}.{key}")
            if diff:
                return diff
        return None

    if isinstance(a, list):
        if len(a) != len(b):
            return path, f"长度 {len(a)}", f"长度 {len(b)}"
        for index, (left, right) in enumerate(zip(a, b)):
            diff = _first_difference(left, right, f"{path}[{index}]")
            if diff:
                return diff
        return None

    if a != b:
        return path, repr(a)[:120], repr(b)[:120]
    return None


def check_project(project_path: str, verbose: bool = False) -> dict:
    """对单个项目做"同进程双跑"确定性检查。"""
    from engine.project_analyzer import ProjectAnalyzer
    from engine.parser import clear_ast_cache

    # 第一次：清空缓存，模拟"全新进程"
    clear_ast_cache()
    first = ProjectAnalyzer().analyze(project_path).to_dict()

    # 第二次：不清缓存，模拟"同一进程里再跑一次"（更严格）
    second = ProjectAnalyzer().analyze(project_path).to_dict()

    left = json.dumps(first, ensure_ascii=False, sort_keys=True, default=str)
    right = json.dumps(second, ensure_ascii=False, sort_keys=True, default=str)

    diff = _first_difference(
        copy.deepcopy(json.loads(left)),
        copy.deepcopy(json.loads(right)),
    )

    result = {
        "project": project_path,
        "identical": left == right,
        "bytes": len(left.encode("utf-8")),
        "difference": diff,
    }

    if verbose and diff:
        print(f"    第一处差异: {diff[0]}")
        print(f"      第一次: {diff[1]}")
        print(f"      第二次: {diff[2]}")

    return result


def check_project_cross_process(project_path: str, verbose: bool = False) -> dict:
    """跨进程确定性检查：不同 ``PYTHONHASHSEED`` 各跑一个子进程，比对字节。

    为什么需要它：同进程双跑对"``set`` 迭代顺序"完全免疫（同一个进程里哈希顺序
    是稳定的），而 `design_approach` / 模式证据里那些 ``a, b, c`` 字符串列表
    恰恰是从 ``set`` 拼出来的。这条检查就是为此加的（README §19.2 ⑳）。
    """
    import os
    import subprocess
    import tempfile

    outputs = []
    with tempfile.TemporaryDirectory() as tmp:
        for seed in _HASH_SEEDS:
            out_path = Path(tmp) / f"out_{seed}.json"
            env = dict(os.environ, PYTHONHASHSEED=seed)
            proc = subprocess.run(
                [
                    sys.executable, "-c", _CHILD_CODE,
                    str(REPO_ROOT), project_path, str(out_path),
                ],
                cwd=str(REPO_ROOT),
                env=env,
                # 不用管道捕获子进程输出（受限沙箱下会被拒，README §19.5）
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if proc.returncode != 0 or not out_path.is_file():
                return {
                    "project": project_path,
                    "identical": False,
                    "bytes": 0,
                    "difference": (
                        "<子进程失败>",
                        f"exit={proc.returncode}",
                        f"PYTHONHASHSEED={seed}",
                    ),
                }
            outputs.append((seed, out_path.read_bytes()))

    baseline_seed, baseline = outputs[0]
    for seed, data in outputs[1:]:
        if data != baseline:
            diff = _first_difference(
                json.loads(baseline.decode("utf-8")),
                json.loads(data.decode("utf-8")),
            )
            return {
                "project": project_path,
                "identical": False,
                "bytes": len(baseline),
                "difference": diff or (
                    "<字节不同但字段一致>",
                    f"PYTHONHASHSEED={baseline_seed}",
                    f"PYTHONHASHSEED={seed}",
                ),
            }

    if verbose:
        print(f"    跨进程比对：{len(outputs)} 个进程字节一致（PYTHONHASHSEED={','.join(_HASH_SEEDS)}）")
    return {
        "project": project_path,
        "identical": True,
        "bytes": len(baseline),
        "difference": None,
        "sha256": hashlib.sha256(baseline).hexdigest()[:16],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="检查分析输出的确定性")
    parser.add_argument("--project", action="append", default=None,
                        help="项目目录（可重复）；默认为内置两个项目")
    parser.add_argument("--verbose", action="store_true", help="打印第一处差异详情")
    parser.add_argument(
        "--cross-process",
        action="store_true",
        help="跨进程模式：不同 PYTHONHASHSEED 各起一个子进程，比对字节（能查出 set 迭代顺序问题）",
    )
    args = parser.parse_args()

    projects = args.project or DEFAULT_PROJECTS

    print("=" * 72)
    if args.cross_process:
        print(f"确定性跨进程校验（PYTHONHASHSEED={','.join(_HASH_SEEDS)} 各起一个子进程，逐字节比对）")
    else:
        print("确定性双跑校验（同一进程内连续分析两次，逐字段比对）")
    print("=" * 72)

    failures = 0
    for project in projects:
        if not (REPO_ROOT / project).is_dir():
            print(f"\n[跳过] {project}: 目录不存在")
            continue
        print(f"\n[检查] {project}")
        if args.cross_process:
            result = check_project_cross_process(project, verbose=args.verbose)
        else:
            result = check_project(project, verbose=args.verbose)
        if result["identical"]:
            extra = f"，sha256={result['sha256']}" if result.get("sha256") else ""
            print(f"    一致 ✓  （序列化 {result['bytes']} 字节{extra}）")
        else:
            failures += 1
            print(f"    不一致 ✗  第一处差异: {result['difference'][0]}")
            if args.verbose:
                print(f"      第一次: {result['difference'][1]}")
                print(f"      第二次: {result['difference'][2]}")
            else:
                print("    （加 --verbose 看具体值）")

    print()
    if failures:
        print(f"结果：{failures} 个项目输出不一致 ✗")
        return 1
    print("结果：全部一致 ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
