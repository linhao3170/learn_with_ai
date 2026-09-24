"""
业务图谱第三方项目验证（README5 §9.2 / README4 §9.2 的证据纪律）

为什么必须跑这个
----------------
README4 §9.2 的第一条铁律是"**不许在自造样本上报告准确率**"，第二条是
"数字必须能回指"。业务图谱引擎目前只在 1 个自造样本 + 1 个真实项目上跑过，
按 README5 §9.2 的要求（≥3 个未参与规则调试的第三方项目）**还不够**。

本脚本做的事
------------
1. 在多个项目上跑业务图谱引擎，收集**可机器判定**的指标：
   - 规模（文件/行数/域/功能点/事实/关系/流程）；
   - 覆盖率：有多少功能点带中文 docstring 命名、多少带词典命名、多少只能退回标识符；
   - 退化率：`inferred-low` 占比、`flat` 层级占比、`unclassified`（待归类）功能点占比；
   - 证据完整度：带行号的成员比例、带 evidence 的卡片比例；
   - 确定性：同一项目双跑是否逐字节一致。
2. 产出**人工核对模板**（`--emit-review`）：把每个域、每个功能点及其依据列成 Markdown 表，
   留出"人工判定"列。**脚本绝不自己填这一列** —— 准确率必须由人填。

诚实边界
--------
这些指标里**没有"准确率"**。准确率必须人工比对后才有，脚本只负责把材料准备好、
把"可机器判定的部分"算清楚。README4 §9.2：不美化、不编造、数字可回指。

用法
----
    python scripts/validate_business_graph.py
    python scripts/validate_business_graph.py --project validation/flask --emit-review
    python scripts/validate_business_graph.py --output validation/business_graph_validation.md
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # pragma: no cover
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

DEFAULT_PROJECTS = [
    "sample_projects/lab_safety_assistant",   # 自造样本（**不用于报告准确率**，只作对照）
    "validation/python_dotenv",               # 真实第三方（小）
    "validation/flask",                       # 真实第三方（中）
    "validation/urllib3",                     # 真实第三方（大）
]

#: 自造样本：在报告里必须显著标注，禁止用来宣传准确率
SELF_MADE = {"sample_projects/lab_safety_assistant"}


def analyze(project: str) -> dict:
    """跑一次完整分析，返回契约 dict 与耗时。"""
    from engine.project_analyzer import ProjectAnalyzer
    from engine.parser import clear_ast_cache

    clear_ast_cache()
    started = time.time()
    result = ProjectAnalyzer().analyze(str(REPO_ROOT / project))
    elapsed = time.time() - started
    return result.to_dict(), elapsed


def measure(project: str) -> dict:
    """收集一个项目的可机器判定指标。"""
    contract, elapsed = analyze(project)
    graph = contract.get("business_graph") or {}

    domains = graph.get("domains", []) or []
    caps = graph.get("capabilities", []) or []
    cards = graph.get("module_cards", {}) or {}
    facts = graph.get("facts", []) or []
    flows = graph.get("flows", []) or []
    relations = graph.get("module_relations", []) or []
    hierarchy = graph.get("hierarchy", {}) or {}

    # ---- 命名质量：域名与功能点名分别有多少来自 docstring / 词典 / 只能退回标识符 ----
    def name_stats(items, key="name_status"):
        total = len(items)
        buckets: dict[str, int] = {}
        for item in items:
            buckets[item.get(key, "unknown")] = buckets.get(item.get(key, "unknown"), 0) + 1
        return total, buckets

    domain_total, domain_names = name_stats(domains)
    cap_total, cap_names = name_stats(caps)

    # ---- 置信度分布 ----
    def confidence_stats(items):
        buckets: dict[str, int] = {}
        for item in items:
            buckets[item.get("confidence", "unknown")] = buckets.get(item.get("confidence", "unknown"), 0) + 1
        return buckets

    # ---- 证据完整度 ----
    cap_members = [m for c in caps for m in c.get("members", [])]
    members_with_lines = [m for m in cap_members if m.get("start_line")]
    cap_cards = [c for c in cards.values() if c.get("level") == 2]
    cards_with_evidence = [c for c in cap_cards if c.get("evidence")]
    facts_with_lines = [f for f in facts if f.get("start_line")]

    # ---- 退化指标 ----
    flat_domains = [d for d in hierarchy.values() if d == "flat"]
    unclassified_caps = [c for c in caps if "unclassified" in str(c.get("entity", ""))]
    unconfirmed_objectives = [
        c for c in cap_cards
        if c.get("objective_confidence") == "unconfirmed" or not c.get("objective")
    ]

    # ---- 确定性（同进程双跑）----
    second, _ = analyze(project)
    deterministic = (
        json.dumps(contract, ensure_ascii=False, sort_keys=True)
        == json.dumps(second, ensure_ascii=False, sort_keys=True)
    )

    def pct(part: int, whole: int) -> str:
        return f"{(100.0 * part / whole):.1f}%" if whole else "—"

    return {
        "project": project,
        "self_made": project in SELF_MADE,
        "status": graph.get("status"),
        "level": graph.get("level"),
        "complexity_raw": (graph.get("complexity") or {}).get("raw"),
        "elapsed_sec": round(elapsed, 2),
        "files": contract.get("overview", {}).get("total_files"),
        "lines": contract.get("overview", {}).get("total_lines"),
        "domains": len(domains),
        "capabilities": len(caps),
        "cards": len(cards),
        "facts": len(facts),
        "relations": len(relations),
        "flows": len(flows),
        "flow_types": _count_by(flows, "scenario_type"),
        "domain_name_status": domain_names,
        "capability_name_status": cap_names,
        "domain_confidence": confidence_stats(domains),
        "capability_confidence": confidence_stats(caps),
        "members_with_lines": f"{len(members_with_lines)}/{len(cap_members)} ({pct(len(members_with_lines), len(cap_members))})",
        "cap_cards_with_evidence": f"{len(cards_with_evidence)}/{len(cap_cards)} ({pct(len(cards_with_evidence), len(cap_cards))})",
        "facts_with_lines": f"{len(facts_with_lines)}/{len(facts)} ({pct(len(facts_with_lines), len(facts))})",
        "flat_domains": f"{len(flat_domains)}/{len(hierarchy)}",
        "unclassified_caps": f"{len(unclassified_caps)}/{len(caps)} ({pct(len(unclassified_caps), len(caps))})",
        "unconfirmed_objectives": f"{len(unconfirmed_objectives)}/{len(cap_cards)} ({pct(len(unconfirmed_objectives), len(cap_cards))})",
        "deterministic": deterministic,
        "domains_detail": [
            {"domain_id": d["domain_id"], "name_cn": d["name_cn"], "role": d["role"],
             "confidence": d["confidence"], "children": len(d.get("children", [])),
             "name_status": d.get("name_status"),
             "evidence": [f'{e.get("signal")}={e.get("value")}' for e in d.get("evidence", [])[:4]]}
            for d in domains
        ],
        "capabilities_detail": [
            {"capability_id": c["capability_id"], "name_cn": c["name_cn"],
             "parent_id": c["parent_id"], "verb_class": c["verb_class"],
             "entity": c["entity"], "confidence": c["confidence"],
             "members": [m["symbol"] for m in c.get("members", [])]}
            for c in caps
        ],
    }


def _count_by(items, key: str) -> dict:
    buckets: dict[str, int] = {}
    for item in items:
        value = item.get(key, "unknown")
        buckets[value] = buckets.get(value, 0) + 1
    return buckets


def render_report(rows: list[dict], emit_review: bool) -> str:
    lines: list[str] = []
    lines.append("# 业务图谱 · 多项目验证报告\n")
    lines.append("> 由 `python scripts/validate_business_graph.py` 生成。**可重复执行**。\n")
    lines.append("> ")
    lines.append("> **这份报告里没有「准确率」** —— 准确率必须人工核对后才有。")
    lines.append("> 脚本只负责把**可机器判定**的指标算出来，并把人工核对所需的材料列全。")
    lines.append("> README4 §9.2：不美化数据；自造样本不得用来报告准确率。\n")

    lines.append("\n## 1. 规模与产出\n")
    lines.append("| 项目 | 类型 | 文件 | 行数 | 域 | 功能点 | 卡片 | 事实 | 关系 | 流程 | 级别 | 耗时 |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|")
    for row in rows:
        kind = "**自造样本**" if row["self_made"] else "真实第三方"
        lines.append(
            f"| `{row['project']}` | {kind} | {row['files']} | {row['lines']} | {row['domains']} | "
            f"{row['capabilities']} | {row['cards']} | {row['facts']} | {row['relations']} | "
            f"{row['flows']} | {row['level']} | {row['elapsed_sec']}s |"
        )

    lines.append("\n> ⚠️ **`sample_projects/lab_safety_assistant` 是自造样本，其上的任何指标都不具备说服力**")
    lines.append("> （启发式规则就是照着它调的，等于在训练集上报告成绩）。")
    lines.append("> 它留在这里只作为**对照基线**：如果真实第三方项目的指标比它差很多，说明规则过拟合了。\n")

    lines.append("\n## 2. 命名来源分布（可机器判定）\n")
    lines.append("`from_docstring` = 作者自己写的中文 docstring（最可靠）；")
    lines.append("`from_lexicon` = 词典翻译；`from_identifier` = 只能退回标识符词根（**质量最差**）；")
    lines.append('`from_structural_role` = 结构性角色名（如「系统装配」）。\n')
    lines.append("| 项目 | 域：docstring / lexicon / identifier / structural | 功能点：docstring / lexicon / identifier |")
    lines.append("|---|---|---|")
    for row in rows:
        d = row["domain_name_status"]
        c = row["capability_name_status"]
        lines.append(
            f"| `{row['project']}` | {d.get('from_docstring', 0)} / {d.get('from_lexicon', 0)} / "
            f"{d.get('from_identifier', 0)} / {d.get('from_structural_role', 0)} | "
            f"{c.get('from_docstring', 0)} / {c.get('from_lexicon', 0)} / {c.get('from_identifier', 0)} |"
        )

    lines.append("\n## 3. 置信度与退化指标（可机器判定）\n")
    lines.append("| 项目 | 域置信度 | 功能点置信度 | 成员带行号 | 二级卡片带证据 | 事实带行号 | flat 层级域 | 待归类功能点 | 目标待教师填 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for row in rows:
        lines.append(
            f"| `{row['project']}` | {row['domain_confidence']} | {row['capability_confidence']} | "
            f"{row['members_with_lines']} | {row['cap_cards_with_evidence']} | {row['facts_with_lines']} | "
            f"{row['flat_domains']} | {row['unclassified_caps']} | {row['unconfirmed_objectives']} |"
        )

    lines.append("\n**怎么读这张表**：")
    lines.append("- `成员带行号` / `二级卡片带证据` / `事实带行号` 越接近 100% 越好 —— 它们决定「结论能不能回指代码」；")
    lines.append("- `待归类功能点` 比例高，说明词典覆盖不住这个项目的命名风格（**这是引擎的真实短板，要如实写进材料**）；")
    lines.append("- `目标待教师填` 是**设计上就应该高**的：README4 §2.1 要求业务含义必须由教师确认，规则引擎给不出就不编。\n")

    lines.append("\n## 4. 确定性\n")
    lines.append("| 项目 | 同进程双跑逐字节一致 |")
    lines.append("|---|---|")
    for row in rows:
        lines.append(f"| `{row['project']}` | {'✅ 是' if row['deterministic'] else '❌ 否（必须修）'} |")

    lines.append("\n## 5. 场景类型分布\n")
    lines.append("| 项目 | normal | exception | edge_case |")
    lines.append("|---|---:|---:|---:|")
    for row in rows:
        t = row["flow_types"]
        lines.append(f"| `{row['project']}` | {t.get('normal', 0)} | {t.get('exception', 0)} | {t.get('edge_case', 0)} |")

    lines.append("\n## 6. 人工核对模板\n")
    lines.append("**下面每一行的「人工判定」列都必须由人填写**，脚本不填。")
    lines.append("建议的判定口径（三分类，不要用「对/错」二分）：\n")
    lines.append("| 判定 | 含义 |")
    lines.append("|---|---|")
    lines.append("| `正确` | 划分与命名都符合业务实际 |")
    lines.append("| `命名不当` | 划分对了，但中文名不准（可由教师改名修掉） |")
    lines.append("| `划分错误` | 该合没合 / 该拆没拆 / 根本不该存在 |")
    lines.append("| `无法判定` | 需要业务知识，标成待教师确认 |")
    lines.append("")
    lines.append("> 统计口径：`划分错误 / 总域数` 才是「业务图谱划分错误率」，")
    lines.append("> 它和 README2 §19 的「事实错误率」**不是一回事，不能混着报**。\n")

    if emit_review:
        for row in rows:
            if row["self_made"]:
                continue   # 自造样本不做人工核对模板（没有意义）
            lines.append(f"\n### 6.x `{row['project']}`（{row['lines']} 行）\n")
            lines.append("#### 一级业务域\n")
            lines.append("| domain_id | 系统命名 | 角色 | 置信度 | 子节点 | 聚类依据 | 人工判定 | 备注 |")
            lines.append("|---|---|---|---|---:|---|---|---|")
            for d in row["domains_detail"]:
                lines.append(
                    f"| `{d['domain_id']}` | {d['name_cn']} | {d['role']} | {d['confidence']} | "
                    f"{d['children']} | {'; '.join(d['evidence'])} |  |  |"
                )
            lines.append("\n#### 二级功能点\n")
            lines.append("| capability_id | 系统命名 | 所属域 | 动词/对象 | 置信度 | 成员函数 | 人工判定 | 备注 |")
            lines.append("|---|---|---|---|---|---|---|---|")
            for c in row["capabilities_detail"]:
                lines.append(
                    f"| `{c['capability_id']}` | {c['name_cn']} | `{c['parent_id']}` | "
                    f"{c['verb_class']}/{c['entity']} | {c['confidence']} | "
                    f"{', '.join(c['members'])} |  |  |"
                )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="业务图谱多项目验证")
    parser.add_argument("--project", action="append", default=None, help="项目目录（可重复）")
    parser.add_argument("--output", help="把 Markdown 报告写到该路径")
    parser.add_argument("--emit-review", action="store_true", help="同时输出人工核对模板")
    parser.add_argument("--json-output", help="把原始指标写成 JSON")
    args = parser.parse_args()

    projects = args.project or DEFAULT_PROJECTS

    print("=" * 78)
    print("业务图谱 · 多项目验证")
    print("=" * 78)

    rows = []
    for project in projects:
        if not (REPO_ROOT / project).is_dir():
            print(f"\n[跳过] {project}: 目录不存在")
            continue
        print(f"\n[分析] {project} ...", end="", flush=True)
        row = measure(project)
        rows.append(row)
        kind = "自造样本" if row["self_made"] else "真实第三方"
        print(
            f" 完成（{row['elapsed_sec']}s；{kind}；{row['domains']} 域 / "
            f"{row['capabilities']} 功能点 / {row['facts']} 事实 / 级别 {row['level']}）"
        )
        if not row["deterministic"]:
            print("   ⚠️ 双跑结果不一致 —— 必须修！")

    if not rows:
        print("\n没有可用项目。")
        return 1

    report = render_report(rows, args.emit_review)
    if args.output:
        out_path = REPO_ROOT / args.output
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(f"\n报告已写入: {args.output}")
    if args.json_output:
        json_path = REPO_ROOT / args.json_output
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"原始指标已写入: {args.json_output}")

    print()
    real = [r for r in rows if not r["self_made"]]
    print(f"项目数：{len(rows)}（其中真实第三方 {len(real)} 个）")
    if len(real) < 3:
        print(f"⚠️ README5 §9.2 要求 >= 3 个未参与规则调试的第三方项目，当前只有 {len(real)} 个。")
    else:
        print("✅ 已满足 README5 §9.2 的第三方项目数量要求。")
    print("提醒：本报告没有「准确率」；准确率需要按第 6 节模板人工核对后才有。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
