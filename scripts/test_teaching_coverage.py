"""
阶段一「项目认知」覆盖度比对器测试（培养方案第四章 阶段一）

测什么
------
1. **不打分**：报告里不存在 score / grade / correct / accuracy / percent 这类字段，
   也不存在任何比例数字 —— 阶段一只允许给""覆盖清单""；
2. **无证据不比对**：置信度 `unconfirmed` 的域与目标文本不参与比对，
   进 `not_comparable` 并把原因写清楚；它们不进分母；
3. **编排 / 支撑域不计入核心覆盖度**（与业务图谱引擎的既有口径一致）；
4. **命中判定**：中文按子串、英文按整词（`atom` 不许命中 `atomic`）；
5. **确定性**：同一份输入两次调用输出逐字节一致；
6. **纯规则**：模块不导入任何网络 / LLM / 随机库（源码级检查）。

用法
----
    python scripts/test_teaching_coverage.py
    python scripts/test_teaching_coverage.py --project validation/python_dotenv --verbose
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # pragma: no cover
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from engine.teaching import coverage as cov  # noqa: E402
from engine.project_analyzer import ProjectAnalyzer  # noqa: E402

DEFAULT_PROJECTS = [
    "sample_projects/lab_safety_assistant",
    "validation/python_dotenv",
]

#: 报告里绝对不允许出现的字段名（阶段一不打分）
FORBIDDEN_KEYS = (
    "score", "grade", "grading", "correct", "accuracy", "percent", "percentage",
    "ratio", "rate", "points", "mark",
)

#: 例外：`has_score` 是**反向标记**（值必须是 False，表示""本阶段没有分数""），
#: 它是这条纪律的显式声明，不是分数本身。
ALLOWED_KEYS = ("has_score",)

#: 引擎侧不允许导入的库（无网络、无 LLM、无随机）
FORBIDDEN_IMPORTS = (
    "requests", "httpx", "urllib", "http", "socket", "openai", "anthropic",
    "random", "time", "datetime",
)


class Checker:
    def __init__(self, verbose: bool = False) -> None:
        self.rows: List[tuple] = []
        self.verbose = verbose

    def check(self, name: str, passed: bool, detail: str = "") -> None:
        self.rows.append((name, bool(passed), detail))
        if self.verbose or not passed:
            mark = "PASS" if passed else "FAIL"
            print(f"    [{mark}] {name}" + (f"  — {detail}" if detail else ""))

    @property
    def failed(self) -> int:
        return sum(1 for _, ok, _ in self.rows if not ok)


def walk_keys(node: Any, out: List[str]) -> None:
    """递归收集 JSON 结构里所有键名（大小写不敏感地查违禁字段）。"""
    if isinstance(node, dict):
        for key, value in node.items():
            out.append(str(key))
            walk_keys(value, out)
    elif isinstance(node, list):
        for item in node:
            walk_keys(item, out)


def collect_keys(node: Any) -> List[str]:
    keys: List[str] = []
    walk_keys(node, keys)
    return keys


def all_comparable_text(report: Dict[str, Any]) -> str:
    """把每个域的比对键拼成一段""应当全命中""的文本。"""
    chunks: List[str] = []
    for group in ("covered", "missed"):
        for item in report.get(group, []):
            for key in item.get("keys_considered", []):
                chunks.append(key["key"])
    return " ".join(chunks)


def run_project(project: str, checker: Checker, verbose: bool) -> None:
    name = Path(project).name
    print(f"\n=== 校验对象：{project} ===")
    graph = ProjectAnalyzer().analyze(project).to_dict()["business_graph"]

    # ---- 1) 结构：能建出比对目标 ----
    targets = cov.build_domain_targets(graph)
    checker.check(
        f"{name} 能建出覆盖度比对目标",
        targets["stats"]["core_domains"] > 0,
        f"核心域 {targets['stats']['core_domains']} 个，"
        f"编排/支撑域 {targets['stats']['supporting_domains']} 个",
    )
    checker.check(
        f"{name} 编排/支撑域不进入核心覆盖度",
        all(item["role"] in ("orchestrator", "support") for item in targets["supporting"]),
        "、".join(f"{i['name_cn']}({i['role']})" for i in targets["supporting"]) or "本项目无编排/支撑域",
    )

    # ---- 2) 空输入：不命中任何域，但仍然是一份合法报告 ----
    empty = cov.evaluate_orientation(graph, "")
    checker.check(
        f"{name} 空输入时不命中任何域",
        empty["empty_input"] is True and empty["counts"]["covered"] == 0,
        f"covered={empty['counts']['covered']}，missed={empty['counts']['missed']}",
    )

    # ---- 3) 把全部比对键写进回答 → 应当全部命中 ----
    full_text = all_comparable_text(empty)
    full = cov.evaluate_orientation(graph, full_text)
    checker.check(
        f"{name} 回答里出现全部比对键时全部命中",
        full["counts"]["covered"] == full["counts"]["comparable_domains"]
        and full["counts"]["comparable_domains"] > 0,
        f"命中 {full['counts']['covered']}/{full['counts']['comparable_domains']}",
    )

    # ---- 4) 无关回答：0 命中，且不给""你答错了""的结论 ----
    unrelated = cov.evaluate_orientation(graph, "今天天气不错，我想去操场跑两圈。")
    checker.check(
        f"{name} 无关回答 0 命中",
        unrelated["counts"]["covered"] == 0,
        f"covered={unrelated['counts']['covered']}",
    )

    # ---- 5) 不打分：报告里没有任何分数字段 ----
    keys = {k.lower() for k in collect_keys(full)}
    hits = sorted(
        k for k in keys
        if any(token in k for token in FORBIDDEN_KEYS) and k not in ALLOWED_KEYS
    )
    checker.check(
        f"{name} 报告里没有分数字段",
        not hits and full["has_score"] is False and full["scoring"] == "coverage_only",
        f"命中违禁字段 {hits}" if hits else f"scoring={full['scoring']}, has_score={full['has_score']}",
    )

    # ---- 6) 确定性：两次调用逐字节一致 ----
    again = cov.evaluate_orientation(graph, full_text)
    checker.check(
        f"{name} 同一输入两次调用逐字节一致",
        json.dumps(full, ensure_ascii=False, sort_keys=True)
        == json.dumps(again, ensure_ascii=False, sort_keys=True),
        "一致",
    )

    # ---- 7) 未确认的内容不参与比对（人造用例，不动真实图谱） ----
    probe = json.loads(json.dumps(graph))
    probe_domain = (probe.get("domains") or [{}])[0]
    probe_id = str(probe_domain.get("domain_id") or "")
    probe_domain["confidence"] = "unconfirmed"
    probe["module_cards"][probe_id]["objective"] = "这条目标还没有教师确认"
    probe["module_cards"][probe_id]["objective_confidence"] = "unconfirmed"
    probe_report = cov.evaluate_orientation(probe, "这条目标还没有教师确认")
    not_comparable_ids = {item["domain_id"] for item in probe_report["not_comparable"]}
    checker.check(
        f"{name} unconfirmed 的域不参与比对（不进分母）",
        probe_id in not_comparable_ids
        and probe_id not in {i["domain_id"] for i in probe_report["covered"]}
        and probe_report["counts"]["comparable_domains"] < full["counts"]["comparable_domains"],
        f"{probe_id} → not_comparable，comparable {full['counts']['comparable_domains']} → "
        f"{probe_report['counts']['comparable_domains']}",
    )
    reasons = [item["reason"] for item in probe_report["not_comparable"] if item["domain_id"] == probe_id]
    checker.check(
        f"{name} not_comparable 必须写明原因",
        bool(reasons and reasons[0].strip()),
        reasons[0] if reasons else "原因为空",
    )

    # ---- 8) 英文按整词匹配：'atomic' 不许命中 'atom' ----
    ascii_domains = [
        item for item in targets["core"]
        if item["name_cn"] and re.fullmatch(r"[A-Za-z0-9 ._\-]+", item["name_cn"].strip())
    ]
    if ascii_domains:
        target = ascii_domains[0]
        word = cov.strip_structural_words(target["name_cn"]) or target["name_cn"]
        base = word.split(" ")[0].lower()
        tricked = cov.evaluate_orientation(graph, f"{base}ic {base}s {base}ing")
        checker.check(
            f"{name} 英文按整词匹配（{base}ic 不命中 {base}）",
            all(item["domain_id"] != target["domain_id"] for item in tricked["covered"]),
            f"域 {target['name_cn']} 未被 {base}ic/{base}s/{base}ing 命中",
        )
    else:
        checker.check(f"{name} （本项目无纯英文域名，跳过整词匹配用例）", True)


def check_purity(checker: Checker) -> None:
    """模块必须是纯规则：无网络、无 LLM、无随机、无时间依赖。"""
    source = (REPO_ROOT / "engine" / "teaching" / "coverage.py").read_text(encoding="utf-8")
    imported = set()
    for line in source.splitlines():
        match = re.match(r"\s*(?:from|import)\s+([A-Za-z_][\w.]*)", line)
        if match:
            imported.add(match.group(1).split(".")[0])
        match2 = re.match(r"\s*from\s+([A-Za-z_][\w.]*)\s+import\s+", line)
        if match2:
            imported.add(match2.group(1).split(".")[0])
    bad = sorted(imported & set(FORBIDDEN_IMPORTS))
    checker.check(
        "覆盖度比对器不导入网络/LLM/随机/时间库",
        not bad,
        f"违禁导入 {bad}" if bad else f"仅导入 {sorted(imported)}",
    )
    checker.check(
        "覆盖度比对器带 algorithm_version 与 caveats",
        cov.ALGORITHM_VERSION.startswith("orientation-coverage-") and bool(cov.SCORING),
        f"algorithm_version={cov.ALGORITHM_VERSION}",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="阶段一覆盖度比对器测试")
    parser.add_argument("--project", action="append", default=None,
                        help="参与检查的项目目录（可重复）")
    parser.add_argument("--verbose", action="store_true", help="打印每一项，而不只是失败项")
    args = parser.parse_args()

    projects = args.project or DEFAULT_PROJECTS
    checker = Checker(verbose=args.verbose)

    print("=" * 78)
    print("阶段一「项目认知」覆盖度比对器测试")
    print("=" * 78)

    for project in projects:
        if not (REPO_ROOT / project).is_dir():
            checker.check(f"{project} 存在", False, "目录不存在")
            continue
        run_project(project, checker, args.verbose)

    print("\n=== 纯规则检查 ===")
    check_purity(checker)

    print("\n" + "=" * 78)
    total = len(checker.rows)
    print(f"合计 {total - checker.failed}/{total} 项通过")
    print("=" * 78)
    return 1 if checker.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
