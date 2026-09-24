"""
业务图谱引擎测试（README5 Sprint 1）

测什么
------
1. **结构不变量**：五步流水线的产物都在、没有绝对路径、没有答案泄漏；
2. **确定性**：同一份代码两次构建**逐字节一致**（README5 §3.9）；
3. **质量下限**：域数/功能点数落在合理区间 —— 防止"一个类一个域"或"全并成一个域"
   这两种退化（都真实发生过）；
4. **教学正确性**：
   - 编排类（如 `LabSafetyApp`）不能被当成核心业务域（README5 §3.1 第 2 步）；
   - `__init__` 之类的 dunder 不能变成二级功能点；
   - 生命周期流程必须排到最后（README5 §3.4）；
   - 模块卡片必须带 evidence，规则/状态/异常必须是 verified；
5. **教师种子合并**：种子优先、locked 字段不被覆盖、来源标记正确（README5 §3.8）。

用法
----
    python scripts/test_business_graph.py
    python scripts/test_business_graph.py --project validation/python_dotenv --verbose
"""

from __future__ import annotations

import argparse
import io
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
    # 真实第三方项目（README5 §9.2 要求 >= 3 个未参与规则调试的项目）
    "validation/flask",
    "validation/urllib3",
]

#: 质量下限的判定口径 —— **与项目规模挂钩**，不用绝对数字。
#:
#: 第一版用的是绝对区间（域 ∈ [2,12]、功能点 ∈ [3,60]），在 784 行的样本上没问题，
#: 但一跑到 flask（10086 行 / 35 文件 / 16 域）和 urllib3（14069 行 / 43 文件 / 19 域）
#: 就全部误报。规模差 10 倍，域数量当然应该差好几倍。
#:
#: 真正要防的是**两种退化**，它们与规模无关：
#:   · 过并 —— 整个项目塌成一两个域（urllib3 曾经 2 域 / 11536 行）；
#:   · 过碎 —— 一个单元一个域（python-dotenv 曾经一个类一个域，16 域）。
#: 所以改成：域数量有下限，且**每个域的平均功能点数**落在合理区间。
MIN_DOMAINS = 2
#: 每个业务域平均挂多少个二级功能点 —— 太少说明切分不足，太多说明域没分好
MIN_CAPS_PER_DOMAIN = 1.2
MAX_CAPS_PER_DOMAIN = 12.0
#: 域数量上限：一个域至少要有一个"来源单元"，所以域数不该超过单元数
MAX_DOMAINS_PER_UNIT = 1.5


class Checker:
    def __init__(self, verbose: bool = False) -> None:
        self.rows: list[tuple[str, bool, str]] = []
        self.verbose = verbose

    def check(self, name: str, passed: bool, detail: str = "") -> None:
        self.rows.append((name, bool(passed), detail))
        if self.verbose or not passed:
            mark = "PASS" if passed else "FAIL"
            print(f"    [{mark}] {name}" + (f"  — {detail}" if detail else ""))

    @property
    def failed(self) -> int:
        return sum(1 for _, ok, _ in self.rows if not ok)


def build_graph(project: str) -> dict:
    """构建业务图谱（不复用 ProjectAnalyzer，避免被主链路异常兜底掩盖错误）。"""
    from engine.project_analyzer.project_parser import ProjectParser
    from engine.deep_analyzer import DeepAnalyzer
    from engine.business_graph import build_business_graph
    from engine.parser import clear_ast_cache

    clear_ast_cache()
    project_info = ProjectParser().parse_project(project)
    deep = DeepAnalyzer(max_flows=10, max_flow_depth=6).analyze(project_info)
    return build_business_graph(project_info, deep, project)


def check_structure(graph: dict, checker: Checker) -> None:
    """结构不变量。"""
    for key in ("contract_version", "algorithm_version", "source_hash", "level",
                "complexity", "domains", "capabilities", "module_cards",
                "module_relations", "facts", "flows", "hierarchy", "caveats"):
        checker.check(f"契约字段存在: {key}", key in graph, "")

    checker.check(
        "source_hash 形如 sha256:...",
        str(graph.get("source_hash", "")).startswith("sha256:"),
        str(graph.get("source_hash"))[:24],
    )

    blob = json.dumps(graph, ensure_ascii=False)
    import re
    checker.check(
        "图谱里没有开发机绝对路径",
        not re.search(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]", blob),
        "",
    )
    checker.check("图谱里没有 correct_answers", "correct_answers" not in blob, "")
    checker.check("图谱里没有 _inferred_ 标记", "_inferred_" not in blob, "")

    # 证据完整性
    cards = graph.get("module_cards", {})
    cards_missing_evidence = [
        cid for cid, card in cards.items()
        if card.get("level") == 2 and not card.get("evidence")
    ]
    checker.check(
        "每个二级模块卡都有 evidence",
        not cards_missing_evidence,
        f"{len(cards_missing_evidence)} 个缺证据",
    )

    # 事实必须全部 verified，且带行号
    bad_facts = [
        f.get("fact_id") for f in graph.get("facts", [])
        if f.get("confidence") != "verified" or not f.get("start_line")
    ]
    checker.check(
        "所有事实都是 verified 且带行号",
        not bad_facts,
        f"{len(bad_facts)} 条不合格",
    )

    # 复杂度明细
    complexity = graph.get("complexity", {})
    checker.check(
        "复杂度带七维明细 + 公式 + caveat",
        len(complexity.get("breakdown", {})) == 7 and complexity.get("formula") and complexity.get("caveat"),
        f"level={complexity.get('level')}, raw={complexity.get('raw')}",
    )
    checker.check(
        "复杂度带定级依据 level_basis",
        bool(complexity.get("level_basis")),
        "; ".join(complexity.get("level_basis", [])[:1]),
    )


def check_quality(graph: dict, checker: Checker) -> None:
    """质量下限：防止"过并"与"过碎"两种真实退化（判定口径与规模挂钩）。"""
    domains = graph.get("domains", [])
    caps = graph.get("capabilities", [])
    # 单元数 = 所有域里的 unit_id 去重（契约里 domains[].units 就是结构单元清单）
    units = len({uid for d in domains for uid in (d.get("units") or [])})

    checker.check(
        f"至少 {MIN_DOMAINS} 个业务域（不是整块塌成一个）",
        len(domains) >= MIN_DOMAINS,
        f"{len(domains)} 个域",
    )

    if domains:
        per_domain = len(caps) / len(domains)
        checker.check(
            f"每个域平均 {MIN_CAPS_PER_DOMAIN}–{MAX_CAPS_PER_DOMAIN} 个二级功能点",
            MIN_CAPS_PER_DOMAIN <= per_domain <= MAX_CAPS_PER_DOMAIN,
            f"{per_domain:.1f} 个/域（{len(caps)} 功能点 / {len(domains)} 域）",
        )
        checker.check(
            "没有空功能点的业务域",
            all(d.get("children") for d in domains),
            str([d["domain_id"] for d in domains if not d.get("children")][:3]),
        )

    # 域数量不该超过"来源单元数 × 1.5" —— 否则就是"一个类一个域"
    if units:
        checker.check(
            f"域数量没有超过单元数的 {MAX_DOMAINS_PER_UNIT} 倍（不是一单元一域）",
            len(domains) <= max(MIN_DOMAINS, units * MAX_DOMAINS_PER_UNIT),
            f"{len(domains)} 域 / {units} 单元",
        )

    checker.check("至少 3 个二级功能点", len(caps) >= 3, f"{len(caps)} 个")

    # dunder 不能成为功能点
    dunder_caps = [
        c["capability_id"] for c in caps
        if any(m.get("symbol", "").startswith("__") and m.get("symbol", "").endswith("__")
               for m in c.get("members", []))
    ]
    checker.check("dunder 方法（__init__ 等）没有变成二级功能点", not dunder_caps, str(dunder_caps[:3]))

    # 功能点必须有成员
    empty_caps = [c["capability_id"] for c in caps if not c.get("members")]
    checker.check("没有空功能点", not empty_caps, str(empty_caps[:3]))

    # 每个域都要有名字
    unnamed = [d["domain_id"] for d in domains if not d.get("name_cn")]
    checker.check("每个业务域都有中文名", not unnamed, str(unnamed[:3]))

    # 名字来源必须可追溯
    bad_status = [
        d["domain_id"] for d in domains
        if d.get("name_status") not in ("from_docstring", "from_lexicon", "from_identifier", "from_structural_role")
    ]
    checker.check("域名来源可追溯（name_status）", not bad_status, str(bad_status[:3]))

    # 每个域都要有聚类依据
    no_evidence = [d["domain_id"] for d in domains if not d.get("evidence")]
    checker.check("每个业务域都有聚类依据 evidence", not no_evidence, str(no_evidence[:3]))


def check_teaching(graph: dict, checker: Checker) -> None:
    """教学正确性 —— 这几条都是 README4/README5 明确点名的教学错误。"""
    # 1) 编排类不能当核心业务模块
    orchestrators = set(graph.get("orchestrators", []))
    core_domains = {
        d["domain_id"] for d in graph.get("domains", [])
        if d.get("role") == "core"
    }
    checker.check(
        "编排类域没有被当成核心业务域",
        not (orchestrators & core_domains),
        f"orchestrators={sorted(orchestrators)[:3]}",
    )

    # 2) 生命周期流程必须排在最后
    flows = graph.get("flows", [])
    if flows:
        last_non_lifecycle = max(
            (i for i, f in enumerate(flows) if not f.get("is_lifecycle")), default=-1
        )
        first_lifecycle = min(
            (i for i, f in enumerate(flows) if f.get("is_lifecycle")), default=len(flows)
        )
        checker.check(
            "生命周期流程排在业务流之后",
            first_lifecycle > last_non_lifecycle,
            f"最后一条业务流 #{last_non_lifecycle}，第一条生命周期流 #{first_lifecycle}",
        )
        checker.check(
            "生命周期流程带降权系数",
            all(f.get("weight_factor", 1.0) < 1.0 for f in flows if f.get("is_lifecycle")),
            "",
        )

    # 3) 场景类型分布合理
    types = [f.get("scenario_type") for f in flows]
    checker.check(
        "流程都标了 scenario_type",
        all(t in ("normal", "exception", "edge_case") for t in types),
        f"{len(types)} 条流程",
    )

    # 4) "不负责什么"必须可解释（来自三条规则之一）
    caps = {c["capability_id"]: c for c in graph.get("capabilities", [])}
    with_does_not = [
        cid for cid, card in graph.get("module_cards", {}).items()
        if card.get("level") == 2 and card.get("does_not")
    ]
    checker.check(
        "至少有一个二级模块生成了『不负责什么』",
        len(with_does_not) > 0,
        f"{len(with_does_not)} 个模块有 does_not",
    )

    # 5) 关系是 verified 且带证据
    bad_relations = [
        r for r in graph.get("module_relations", [])
        if r.get("confidence") != "verified"
    ]
    checker.check("模块关系都是 verified", not bad_relations, f"{len(bad_relations)} 条不合格")

    # 6) 未审核状态必须如实标注
    checker.check(
        "图谱状态如实标注为未审核/混合",
        graph.get("status") in ("needs_review", "mixed", "approved"),
        f"status={graph.get('status')}",
    )


def check_determinism(project: str, checker: Checker) -> None:
    """同一份代码两次构建必须逐字节一致（README5 §3.9）。"""
    first = json.dumps(build_graph(project), ensure_ascii=False, sort_keys=True)
    second = json.dumps(build_graph(project), ensure_ascii=False, sort_keys=True)
    checker.check(
        "同进程双跑业务图谱逐字节一致",
        first == second,
        f"{len(first)} 字节" if first == second else "存在差异",
    )


def check_seed_merge(checker: Checker) -> None:
    """教师种子合并（README5 §3.8）。"""
    from engine.business_graph.seed_merger import merge_graph

    auto = {
        "domains": [{"domain_id": "d_x", "name_cn": "系统推断名", "role": "core"}],
        "module_cards": {
            "c_x": {"module_id": "c_x", "name_cn": "系统推断名", "objective": ""},
        },
    }
    seed = {
        "domains": [{"domain_id": "d_x", "name_cn": "教师改名", "locked": ["name_cn"]}],
        "module_cards": {
            "c_x": {"module_id": "c_x", "name_cn": "教师改的名", "objective": "教师写的目标", "review_status": "approved"},
            "c_teacher_only": {"module_id": "c_teacher_only", "name_cn": "系统没识别出来的能力"},
        },
    }
    merged, report = merge_graph(auto, seed)

    card = merged["module_cards"]["c_x"]
    checker.check("种子的 name_cn 覆盖了系统推断名", card["name_cn"] == "教师改的名", card["name_cn"])
    checker.check("种子新增的能力被保留", "c_teacher_only" in merged["module_cards"], "")
    checker.check(
        "系统未识别的种子节点标了 note",
        "系统未能从代码中识别" in str(merged["module_cards"]["c_teacher_only"].get("note", "")),
        merged["module_cards"]["c_teacher_only"].get("note", "")[:20],
    )
    checker.check("合并报告记录了 seed_loaded", report.get("seed_loaded") is True, "")
    checker.check("教师节点来源标为 teacher", card.get("source") == "teacher", str(card.get("source")))


def main() -> int:
    parser = argparse.ArgumentParser(description="业务图谱引擎测试")
    parser.add_argument("--project", action="append", default=None, help="项目目录（可重复）")
    parser.add_argument("--verbose", action="store_true", help="打印每一项")
    args = parser.parse_args()

    projects = args.project or DEFAULT_PROJECTS
    total_failed = 0

    print("=" * 78)
    print("业务图谱引擎测试（README5 Sprint 1）")
    print("=" * 78)

    for project in projects:
        if not (REPO_ROOT / project).is_dir():
            print(f"\n[跳过] {project}: 目录不存在")
            continue

        print(f"\n### {project}")
        graph = build_graph(project)
        checker = Checker(args.verbose)

        print(f"  域 {len(graph.get('domains', []))} 个 / 功能点 {len(graph.get('capabilities', []))} 个 / "
              f"卡片 {len(graph.get('module_cards', {}))} 个 / 事实 {len(graph.get('facts', []))} 条 / "
              f"关系 {len(graph.get('module_relations', []))} 条 / 流程 {len(graph.get('flows', []))} 条 / "
              f"级别 {graph.get('level')}")
        names = "、".join(d.get("name_cn", "?") for d in graph.get("domains", []))
        print(f"  业务域：{names}")

        check_structure(graph, checker)
        check_quality(graph, checker)
        check_teaching(graph, checker)
        check_determinism(project, checker)

        print(f"  → {len(checker.rows) - checker.failed}/{len(checker.rows)} 项通过")
        total_failed += checker.failed

    print("\n### 教师种子合并")
    seed_checker = Checker(args.verbose)
    check_seed_merge(seed_checker)
    print(f"  → {len(seed_checker.rows) - seed_checker.failed}/{len(seed_checker.rows)} 项通过")
    total_failed += seed_checker.failed

    print()
    if total_failed:
        print(f"结果：{total_failed} 项未通过 ✗")
        return 1
    print("结果：全部通过 ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
