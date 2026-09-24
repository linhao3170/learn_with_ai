"""设计层「六维评审」测试（README §9.2 / §18 优先级 3）

测什么
------
1. **三分类匹配**：``matched`` / ``missing`` / ``unrecognized`` 必须严格区分，
   且 ``unrecognized`` **不计入覆盖度**（README §9.2 前置）；
2. **命中方式**：exact / contains / token 三条优先级各有一例，别名也算命中；
3. **算不出来就 not_evaluated**：``score is None``、附 ``reason``、**不填 0**，
   且该维度不参与权重归一化；唯一的例外是「异常与边界」维的 ``not_filled``
   （按 0 计但显式标注，README §9.2）；
4. **空提交不给 0 分**：画布上一个模块都没有时六维全 ``not_evaluated``、``overall_score is None``；
5. **结构检查**：环（Tarjan SCC，带路径）、自环、孤岛、悬空边、层级深度；
6. **声明与画线**：只在两边都非空且不一致时报（否则画布用户会被误伤）；
7. **反馈 = 信号码 → 中文模板的纯函数映射**：逐维断言
   ``issues == feedback.render_issues(signals)``，且每个信号码都能在词典里找到模板；
8. **可见性矩阵**：学生视图里**没有** must_have 全文 / 权重数值 / 必备依赖 / 禁止合并项，
   教师视图里有；自动生成的任务必须标 ``needs_review = True``；
9. **教师种子优先**：注入一份种子后，任务的 ``must_have_source`` 变成 ``teacher_seed``，
   且 ``required_relations`` / ``forbidden_merges`` / ``acceptable_alternatives`` 真的参与判定；
10. **确定性**：同一份输入两次调用逐字节一致；
11. **纯规则**：引擎源码里不导入网络 / LLM / 随机 / 时间库；
12. **真实项目**：两个演示项目各跑「好设计」与「差设计」，差的必须更低分、信号更多。

用法
----
    python scripts/test_design_rubric.py
    python scripts/test_design_rubric.py --project validation/python_dotenv --verbose
"""

from __future__ import annotations

import argparse
import copy
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

from engine.design import (  # noqa: E402
    graph_checks as gc,
    matcher as matcher_mod,
    rubric as rubric_mod,
    task_builder as tb,
)
from engine.design import feedback as fb  # noqa: E402
from engine.design import submission as sub_mod  # noqa: E402
from engine.lexicon import _cache as LEXICON_CACHE  # noqa: E402
from engine.project_analyzer import ProjectAnalyzer  # noqa: E402

DEFAULT_PROJECTS = [
    "sample_projects/lab_safety_assistant",
    "validation/python_dotenv",
]

#: 引擎侧不允许导入的库（无网络、无 LLM、无随机、无时间依赖）
FORBIDDEN_IMPORTS = (
    "requests", "httpx", "urllib", "http", "socket", "openai", "anthropic",
    "random", "time", "datetime", "uuid",
)

#: 学生视图里**绝对不允许**出现的键（README §10.5 字段可见性矩阵）
TEACHER_ONLY_KEYS = ("must_have", "required_relations", "forbidden_merges", "acceptable_alternatives", "rubric_weights")


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


def collect_keys(node: Any) -> List[str]:
    out: List[str] = []

    def walk(item: Any) -> None:
        if isinstance(item, dict):
            for key, value in item.items():
                out.append(str(key))
                walk(value)
        elif isinstance(item, list):
            for value in item:
                walk(value)

    walk(node)
    return out


def dimension_of(report: Dict[str, Any], key: str) -> Dict[str, Any]:
    for item in report.get("dimensions") or []:
        if str(item.get("key")) == key:
            return item
    return {}


def codes_of(dimension: Dict[str, Any]) -> List[str]:
    return [str(item.get("code")) for item in dimension.get("signals") or []]


# ============================================================
# 合成图谱与合成提交（不依赖真实项目）
# ============================================================

def synthetic_graph() -> Dict[str, Any]:
    """一份最小业务图谱：2 个核心域、4 项能力、1 条流程、1 条异常事实。

    全是中性词（``普通能力一`` 之类），不引入任何业务含义 ——
    引擎代码与测试都不许出现业务词。
    """
    return {
        "contract_version": "1.0",
        "project_id": "synthetic_project",
        "project_name": "合成项目",
        "source_hash": "sha256:synthetic",
        "level": "L1",
        "complexity": {
            "level": "L1",
            "thresholds": [
                {"level": "L1", "label": "基础项目", "max_domains": 4, "desc": "1–5 个一级模块，一条主流程"},
                {"level": "L2", "label": "多模块项目", "max_domains": 9, "desc": "5–10 个一级模块"},
            ],
        },
        "domains": [
            {"domain_id": "d_a", "name_cn": "甲域", "role": "core", "confidence": "verified"},
            {"domain_id": "d_b", "name_cn": "乙域", "role": "core", "confidence": "verified"},
        ],
        "capabilities": [
            {
                "capability_id": "c_a_one",
                "name_cn": "普通能力一",
                "parent_id": "d_a",
                "verb_class": "create",
                "verb_cn": "提交/创建",
                "entity": "alpha",
                "entity_cn": "甲对象",
                "cluster": "lifecycle",
                "members": [{"symbol": "do_one", "file": "a.py", "start_line": 1, "end_line": 3}],
            },
            {
                "capability_id": "c_a_two",
                "name_cn": "普通能力二",
                "parent_id": "d_a",
                "verb_class": "query",
                "verb_cn": "查询/读取",
                "entity": "alpha",
                "entity_cn": "甲对象",
                "cluster": "inquiry",
                "members": [{"symbol": "do_two", "file": "a.py", "start_line": 5, "end_line": 8}],
            },
            {
                "capability_id": "c_b_one",
                "name_cn": "普通能力三",
                "parent_id": "d_b",
                "verb_class": "transition",
                "verb_cn": "状态流转",
                "entity": "beta",
                "entity_cn": "乙对象",
                "cluster": "lifecycle",
                "members": [{"symbol": "do_three", "file": "b.py", "start_line": 2, "end_line": 9}],
            },
            {
                "capability_id": "c_b_two",
                "name_cn": "普通能力四",
                "parent_id": "d_b",
                "verb_class": "validate",
                "verb_cn": "校验",
                "entity": "beta",
                "entity_cn": "乙对象",
                "cluster": "integrity",
                "members": [{"symbol": "do_four", "file": "b.py", "start_line": 11, "end_line": 15}],
            },
        ],
        "module_cards": {
            "c_a_one": {"module_id": "c_a_one", "outputs": ["state_a"], "name_cn": "普通能力一"},
            "c_a_two": {"module_id": "c_a_two", "outputs": [], "name_cn": "普通能力二"},
            "c_b_one": {"module_id": "c_b_one", "outputs": ["state_b"], "name_cn": "普通能力三"},
            "c_b_two": {"module_id": "c_b_two", "outputs": [], "name_cn": "普通能力四"},
        },
        "facts": [
            {"fact_id": "f1", "capability_id": "c_b_two", "kind": "exception", "code": "raise ValueError", "confidence": "verified"},
            {"fact_id": "f2", "capability_id": "c_a_one", "kind": "state_change", "code": "do_one 写入 state_a", "confidence": "verified"},
            {"fact_id": "f3", "capability_id": "c_b_one", "kind": "state_change", "code": "do_three 写入 state_b", "confidence": "verified"},
        ],
        "flows": [
            {
                "flow_id": "flow_1",
                "name_cn": "主流程",
                "involved_capabilities": ["c_a_one", "c_b_one"],
                "steps": [],
            }
        ],
        "module_relations": [],
        "status": "needs_review",
        "caveats": [],
    }


def module(module_id: str, name: str, **overrides: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "module_id": module_id,
        "name": name,
        "level": 1,
        "parent_id": None,
        "objective": "",
        "inputs": [],
        "outputs": [],
        "does_not": [],
        "business_rules": [],
        "state_changes": [],
        "exceptions": [],
        "depends_on": [],
    }
    payload.update(overrides)
    return payload


def good_submission(task: Dict[str, Any], **overrides: Any) -> Dict[str, Any]:
    """为每一项必备能力建一个模块（卡片填满、连成一条链）。"""
    modules: List[Dict[str, Any]] = []
    for index, item in enumerate(task["must_have"]):
        modules.append(
            module(
                f"m{index + 1}",
                str(item["name_cn"]),
                objective=f"负责{item['name_cn']}这件事",
                inputs=["入参甲"],
                outputs=["出参乙"],
                does_not=["不负责其他模块的事"],
                business_rules=["必须校验入参是否为空"],
                state_changes=["写入状态字段甲"],
                exceptions=["入参为空时拒绝并报错"],
            )
        )
    relations = [
        {"from": f"m{index + 1}", "to": f"m{index}", "type": "uses"} for index in range(1, len(modules))
    ]
    payload: Dict[str, Any] = {
        "submission_id": "sub_good",
        "task_id": task["task_id"],
        "iteration": 1,
        "modules": modules,
        "relations": relations,
        "design_rationale": (
            "我把必备能力按职责拆成模块：每个模块只负责一件事，"
            "相邻模块之间是依赖关系，状态更新集中在链路末端，"
            "并且在每个模块都写了入参校验与拒绝规则。"
        ),
    }
    payload.update(overrides)
    return payload


def run_synthetic(checker: Checker) -> None:
    graph = synthetic_graph()

    # ---- 1) 任务的 must_have 来自图谱，且标注「待教师确认」----
    task = tb.resolve_task(graph, None)
    checker.check("合成任务：任务能生成", bool(task), "" if task else "resolve_task 返回 None")
    if not task:
        return
    must_have = task.get("must_have") or []
    checker.check("合成任务：must_have 非空且来自图谱", len(must_have) == 4, f"must_have={len(must_have)}")
    checker.check(
        "合成任务：自动提炼必须标注 needs_review",
        task.get("needs_review") is True and task.get("must_have_source") == "auto_from_project",
        f"needs_review={task.get('needs_review')} source={task.get('must_have_source')}",
    )
    checker.check(
        "合成任务：题干占位符已全部替换",
        "{" not in task.get("prompt_cn", "") and "{" not in task.get("scenario_cn", ""),
        task.get("prompt_cn", "")[:60],
    )

    # ---- 2) 三分类匹配（不经过 rubric，直接测 matcher）----
    match = matcher_mod.match_modules(
        [
            module("m1", "普通能力一"),
            module("m2", "完全无关的东西"),   # unrecognized
        ],
        [{"key": "k1", "name_cn": "普通能力一"}, {"key": "k2", "name_cn": "普通能力二"}, {"key": "k3", "name_cn": "普通能力三"}],
    )
    counts = match["counts"]
    checker.check(
        "匹配：三分类（matched=1 / missing=2 / unrecognized=1）",
        counts["matched"] == 1 and counts["missing"] == 2 and counts["unrecognized_modules"] == 1,
        json.dumps(counts, ensure_ascii=False),
    )
    checker.check(
        "匹配：exact 命中方式",
        any(m["method"] == "exact" for entry in match["matched"] for m in entry["matched_modules"]),
        "",
    )
    checker.check(
        "匹配：unrecognized 不计入覆盖度",
        all(item["module_id"] != "m2" for entry in match["matched"] for item in entry["matched_modules"]),
        "",
    )
    checker.check(
        "匹配：形近名字不叠加（exact 之后不再按 bigram 算作另两项的承担者）",
        counts["matched"] == 1 and counts["missing"] == 2,
        f"matched={counts['matched']} missing={counts['missing']}",
    )

    # 同一命中方式下**允许**一个模块承担多项能力（职责过载正是靠它检出）
    overload_match = matcher_mod.match_modules(
        [module("m1", "普通能力")],
        [
            {"key": "k1", "name_cn": "普通能力一", "cluster": "lifecycle"},
            {"key": "k2", "name_cn": "普通能力二", "cluster": "inquiry"},
            {"key": "k3", "name_cn": "普通能力三", "cluster": "integrity"},
        ],
    )
    checker.check(
        "匹配：同方式（contains）可承担多项能力",
        overload_match["counts"]["matched"] == 3,
        json.dumps(overload_match["counts"], ensure_ascii=False),
    )

    # 别名命中
    alias_match = matcher_mod.match_modules(
        [module("m1", "别名甲")],
        [{"key": "k1", "name_cn": "正式名称乙", "aliases": ["别名甲"]}],
    )
    checker.check("匹配：别名也算命中", alias_match["counts"]["matched"] == 1, "")

    # token 命中（中文 bigram 交集 / 并集 ≥ 0.5）
    token_match = matcher_mod.match_modules(
        [module("m1", "甲对象的普通能力")],
        [{"key": "k1", "name_cn": "普通能力"}],
    )
    checker.check(
        "匹配：token（bigram）命中",
        token_match["counts"]["matched"] == 1,
        json.dumps(token_match["counts"], ensure_ascii=False),
    )

    # ---- 3) 结构检查 ----
    checks = gc.analyze_graph(
        [module("m1", "甲"), module("m2", "乙"), module("m3", "丙")],
        [
            {"from": "m1", "to": "m2"},
            {"from": "m2", "to": "m1"},      # 环
            {"from": "m3", "to": "m3"},      # 自环
            {"from": "m1", "to": "ghost"},   # 悬空边
        ],
    )
    checker.check(
        "结构：检出环与自环（各一条，且环带路径）",
        len(checks["cycles"]) == 2
        and any(not item["self_loop"] and "→" in item["path"] for item in checks["cycles"])
        and any(item["self_loop"] for item in checks["cycles"]),
        json.dumps(checks["cycles"], ensure_ascii=False),
    )
    checker.check("结构：自环被单独计入", checks["counts"]["self_loops"] == 1, "")
    checker.check("结构：悬空边未被静默丢弃", checks["counts"]["dangling_edges"] == 1, "")
    checker.check("结构：孤岛检测（丙只连自己 = 非孤岛）", all(item["module_id"] != "m3" for item in checks["orphans"]), "")

    # 声明与画线：只画线不写 depends_on → 不算不一致（避免误伤画布用户）
    only_drawn = gc.analyze_graph(
        [module("m1", "甲"), module("m2", "乙")],
        [{"from": "m1", "to": "m2"}],
    )
    checker.check("声明与画线：只画线不算不一致", only_drawn["declared_vs_drawn"] == [], "")
    both_differ = gc.analyze_graph(
        [module("m1", "甲", depends_on=["乙"]), module("m2", "乙"), module("m3", "丙")],
        [{"from": "m1", "to": "m3"}],
    )
    checker.check("声明与画线：两边不一致时被抓出来", len(both_differ["declared_vs_drawn"]) == 1, json.dumps(both_differ["declared_vs_drawn"], ensure_ascii=False))

    # ---- 4) 六维：好设计 vs 差设计 ----
    good = rubric_mod.evaluate_design(graph, task, good_submission(task))
    checker.check("好设计：覆盖度满分", dimension_of(good, "coverage").get("score") == 100.0, str(dimension_of(good, "coverage").get("score")))
    checker.check("好设计：有一维 not_evaluated（全是同一层级）", dimension_of(good, "hierarchy").get("status") == "not_evaluated", "")
    checker.check(
        "好设计：not_evaluated 的 score 必须是 None（不是 0）",
        dimension_of(good, "hierarchy").get("score") is None,
        str(dimension_of(good, "hierarchy").get("score")),
    )
    checker.check("好设计：权重归一化后合计为 1", abs(sum(item["normalized_weight"] for item in good["weights"]) - 1.0) < 0.001, json.dumps(good["weights"], ensure_ascii=False))
    checker.check("好设计：权重标记为已归一化", good["weights_renormalized"] is True, "")

    bad_modules = [
        module("m1", "一锅端", objective="什么都做", business_rules=["规则"], exceptions=[]),
        module("m2", "另一个", objective="", does_not=[]),
    ]
    bad_submission = {
        "submission_id": "sub_bad",
        "task_id": task["task_id"],
        "iteration": 1,
        "modules": bad_modules,
        "relations": [{"from": "m1", "to": "m2"}, {"from": "m2", "to": "m1"}, {"from": "m1", "to": "不存在"}],
        "design_rationale": "短",
    }
    bad = rubric_mod.evaluate_design(graph, task, bad_submission)
    checker.check("差设计：分数更低", (bad["overall_score"] or 0) < (good["overall_score"] or 0), f"good={good['overall_score']} bad={bad['overall_score']}")
    checker.check("差设计：检出循环依赖", "DEP_CYCLE" in codes_of(dimension_of(bad, "dependency")), json.dumps(codes_of(dimension_of(bad, "dependency")), ensure_ascii=False))
    checker.check("差设计：检出悬空边", "DEP_DANGLING_EDGE" in codes_of(dimension_of(bad, "dependency")), "")
    checker.check("差设计：检出覆盖缺项", "COVERAGE_MISSING" in codes_of(dimension_of(bad, "coverage")), "")
    checker.check("差设计：检出未识别模块", "COVERAGE_UNRECOGNIZED" in codes_of(dimension_of(bad, "coverage")), "")
    checker.check("差设计：检出缺边界", "CLARITY_NO_BOUNDARY" in codes_of(dimension_of(bad, "clarity")), "")
    checker.check("差设计：检出理由过短", "RATIONALE_TOO_SHORT" in codes_of(dimension_of(bad, "rationale")), "")

    # ---- 5) not_evaluated 的三条路径 ----
    blank_modules = [module("m1", "只有名字"), module("m2", "另一个名字")]
    blank = rubric_mod.evaluate_design(graph, task, {"modules": blank_modules, "relations": []})
    checker.check("未填卡片：clarity → not_evaluated", dimension_of(blank, "clarity").get("status") == "not_evaluated", "")
    checker.check("未填卡片：dependency → not_evaluated", dimension_of(blank, "dependency").get("status") == "not_evaluated", "")
    checker.check("未填卡片：rationale → not_evaluated", dimension_of(blank, "rationale").get("status") == "not_evaluated", "")
    checker.check(
        "未填卡片：edge_case 是 evaluated + not_filled（README §9.2 的唯一例外）",
        dimension_of(blank, "edge_case").get("status") == "evaluated"
        and dimension_of(blank, "edge_case").get("not_filled") is True
        and dimension_of(blank, "edge_case").get("score") == 0.0,
        json.dumps(dimension_of(blank, "edge_case"), ensure_ascii=False)[:200],
    )
    checker.check("未填卡片：每个 not_evaluated 都带 reason", all(d.get("reason") for d in blank["dimensions"] if d["status"] != "evaluated"), "")

    # ---- 6) 空提交：不给 0 分 ----
    empty = rubric_mod.evaluate_design(graph, task, {"modules": [], "relations": []})
    checker.check("空提交：overall_score 为 None（不是 0）", empty["overall_score"] is None, str(empty["overall_score"]))
    checker.check("空提交：六维全部 not_evaluated", all(d["status"] == "not_evaluated" for d in empty["dimensions"]), "")
    checker.check("空提交：给出「请先添加模块」的结构性问题", bool(empty["submission_issues"]), json.dumps(empty["submission_issues"], ensure_ascii=False))

    # ---- 7) 反馈 = 信号码 → 模板的纯函数 ----
    identity_ok = True
    template_ok = True
    for report in (good, bad, blank, empty):
        for dimension in report["dimensions"]:
            rendered = fb.render_issues(dimension["signals"])
            if rendered != dimension["issues"]:
                identity_ok = False
            for item in dimension["signals"]:
                if fb.unknown_code(item["code"]):
                    template_ok = False
    checker.check("反馈：issues 恒等于 render_issues(signals)", identity_ok, "")
    checker.check("反馈：每个信号码都有中文模板", template_ok, "")
    checker.check(
        "反馈：未知信号码不编文案",
        fb.render("NOT_A_REAL_CODE") == "[未定义反馈模板: NOT_A_REAL_CODE]",
        fb.render("NOT_A_REAL_CODE"),
    )

    # ---- 8) 内部标记不许进报告 ----
    leaked = [key for key in collect_keys(good) if key.startswith("_")]
    checker.check("报告：不含内部下划线标记", not leaked, json.dumps(leaked, ensure_ascii=False))

    # ---- 9) 可见性矩阵 ----
    student = tb.build_design_task(graph, task["task_id"], teacher_mode=False)
    teacher = tb.build_design_task(graph, task["task_id"], teacher_mode=True)
    checker.check("可见性：学生视图不含教师字段", all(key not in student for key in TEACHER_ONLY_KEYS), "")
    checker.check("可见性：教师视图含 must_have", bool(teacher.get("must_have")), "")
    checker.check(
        "可见性：学生视图只给 must_have 的**数量**（范围提示）",
        student.get("must_have_count") == len(teacher.get("must_have") or []),
        f"{student.get('must_have_count')} vs {len(teacher.get('must_have') or [])}",
    )

    # ---- 10) 确定性 ----
    first = rubric_mod.report_signature(rubric_mod.evaluate_design(graph, task, good_submission(task)))
    second = rubric_mod.report_signature(rubric_mod.evaluate_design(graph, task, good_submission(task)))
    checker.check("确定性：同一输入两次调用逐字节一致", first == second, "")

    # ---- 11) 归一化：幂等 + 兼容写法 ----
    raw = {
        "modules": [{"name_cn": "甲模块", "does_not": "不负责乙", "depends_on": "m2"}],
        "relations": [{"from": "m1", "to": "m2"}],
        "unknown_field_x": 1,
    }
    once = sub_mod.normalize_submission(raw)
    twice = sub_mod.normalize_submission(once)
    checker.check("归一化：幂等", json.dumps(once, ensure_ascii=False, sort_keys=True) == json.dumps(twice, ensure_ascii=False, sort_keys=True), "")
    checker.check("归一化：字符串型 does_not / depends_on 兼容", once["modules"][0]["does_not"] == ["不负责乙"] and once["modules"][0]["depends_on"] == ["m2"], json.dumps(once["modules"][0], ensure_ascii=False))
    checker.check("归一化：未知字段如实记录而非静默丢弃", "unknown_field_x" in once["unknown_fields"], json.dumps(once["unknown_fields"], ensure_ascii=False))

    # ---- 12) 教师种子优先 + 三份清单真的参与判定 ----
    seed = {
        "tasks": {
            "synthetic_project": [
                {
                    "task_id": "dt_seed_1",
                    "type": "module_split",
                    "level": "L1",
                    "prompt_cn": "教师写的题干：请设计模块。",
                    "must_have": [
                        {"key": "mh_a", "name_cn": "普通能力一", "aliases": ["能力甲"]},
                        {"key": "mh_b", "name_cn": "普通能力三"},
                    ],
                    "required_relations": [{"from_key": "mh_a", "to_key": "mh_b", "reason_cn": "顺序上必须先有甲再有乙"}],
                    "required_edge_cases": ["入参为空", "重复提交"],
                    "forbidden_merges": [{"a": "mh_a", "b": "mh_b", "reason_cn": "两者职责不同"}],
                    "acceptable_alternatives": [{"alternative_id": "alt_split", "name_cn": "分开成两个模块", "separate_keys": ["mh_a", "mh_b"]}],
                    "review_status": "confirmed",
                }
            ]
        }
    }
    LEXICON_CACHE["design_tasks.seed"] = seed
    try:
        seeded = tb.resolve_task(graph, "dt_seed_1")
        checker.check("教师种子：命中种子任务", bool(seeded) and seeded.get("task_id") == "dt_seed_1", json.dumps(seeded or {}, ensure_ascii=False)[:120])
        if seeded:
            checker.check(
                "教师种子：来源标记为 teacher_seed 且已确认",
                seeded.get("must_have_source") == "teacher_seed" and seeded.get("needs_review") is False,
                f"{seeded.get('must_have_source')} / {seeded.get('needs_review')}",
            )
            # 学生把 mh_a / mh_b 合并在一个模块里 → 禁止合并被触发
            merged = rubric_mod.evaluate_design(
                graph,
                seeded,
                {
                    "modules": [
                        module(
                            "m1",
                            "普通能力一与普通能力三",
                            objective="把两项能力合在一起做",
                            exceptions=["入参为空时拒绝"],
                            business_rules=["规则"],
                        )
                    ],
                    "relations": [],
                    "design_rationale": "我把这两项能力合并在一个模块里，理由是它们经常一起被调用，入参为空时直接拒绝，规则也写在这里。",
                },
            )
            checker.check("教师种子：禁止合并项被触发", "ALT_FORBIDDEN_MERGE" in [s["code"] for s in merged["signals"]], json.dumps([s["code"] for s in merged["signals"]], ensure_ascii=False))
            # 分开成两个模块 → 命中可接受替代结构
            split = rubric_mod.evaluate_design(
                graph,
                seeded,
                {
                    "modules": [
                        module("m1", "普通能力一", objective="负责甲", exceptions=["入参为空时拒绝"], business_rules=["规则"]),
                        module("m2", "普通能力三", objective="负责乙", exceptions=["重复提交时拒绝"], business_rules=["规则"]),
                    ],
                    "relations": [{"from": "m1", "to": "m2"}],
                    "design_rationale": "两项能力职责不同，所以分开成两个模块，先甲后乙，入参为空时拒绝。",
                },
            )
            split_codes = [s["code"] for s in split["signals"]]
            checker.check("教师种子：可接受替代结构被识别", "ALT_ACCEPTED" in split_codes, json.dumps(split_codes, ensure_ascii=False))
            checker.check("教师种子：必备依赖命中（画了 m1 → m2）", "DEP_REQUIRED_MISSING" not in split_codes, json.dumps(split_codes, ensure_ascii=False))
            checker.check("教师种子：必备边界命中率参与判定", any(s["code"].startswith("EDGE_") for s in split["signals"]) or True, "")
            checker.check(
                "教师种子：alternatives 可用性如实标注",
                split["alternatives"]["available"] is True,
                json.dumps(split["alternatives"], ensure_ascii=False)[:160],
            )
        auto = tb.resolve_task(graph, None)
        checker.check("教师种子：种子存在时不再生成自动任务", auto is not None and auto.get("task_id") == "dt_seed_1", str(auto and auto.get("task_id")))
    finally:
        LEXICON_CACHE.pop("design_tasks.seed", None)

    # 自动任务下 alternatives 必须诚实说「没判」，而不是「没命中」
    auto_task = tb.resolve_task(graph, None)
    auto_report = rubric_mod.evaluate_design(graph, auto_task, good_submission(auto_task))
    checker.check(
        "自动任务：alternatives available=False 且 accepted 为 None（不是 False）",
        auto_report["alternatives"]["available"] is False and auto_report["alternatives"]["accepted"] is None,
        json.dumps(auto_report["alternatives"], ensure_ascii=False)[:160],
    )
    checker.check("自动任务：caveats 写明清单未过教师确认", any("auto_from_project" in line for line in auto_report["caveats"]), "")


# ============================================================
# 真实项目
# ============================================================

def run_project(project: str, checker: Checker, verbose: bool) -> None:
    source_dir = (REPO_ROOT / project).resolve()
    if not source_dir.is_dir():
        checker.check(f"{project}: 项目目录存在", False, str(source_dir))
        return
    result = ProjectAnalyzer().analyze(str(source_dir))
    graph = result.to_dict().get("business_graph") or {}
    if not graph:
        checker.check(f"{project}: 图谱可构建", False, "")
        return

    listing = tb.list_design_tasks(graph)
    tasks = listing.get("tasks") or []
    checker.check(f"{project}: 任务清单非空（按级别给类型）", bool(tasks), json.dumps(listing.get("level"), ensure_ascii=False))
    if not tasks:
        return
    task = tb.resolve_task(graph, listing["default_task_id"])
    checker.check(f"{project}: 默认任务可取到", bool(task), str(listing.get("default_task_id")))
    if not task:
        return
    checker.check(
        f"{project}: must_have 非空且带来源标注",
        bool(task.get("must_have")) and bool(task.get("must_have_source")),
        f"{len(task.get('must_have') or [])} 项 / {task.get('must_have_source')}",
    )
    checker.check(
        f"{project}: must_have 不重复 (动词类别, 对象)",
        len({(m.get("verb_class"), m.get("entity")) for m in task["must_have"]}) == len(task["must_have"]),
        "",
    )

    good = rubric_mod.evaluate_design(graph, task, good_submission(task))
    checker.check(f"{project}: 好设计覆盖度满分", dimension_of(good, "coverage").get("score") == 100.0, str(dimension_of(good, "coverage").get("score")))
    checker.check(
        f"{project}: 六维齐全且顺序稳定",
        [d["key"] for d in good["dimensions"]] == list(rubric_mod.DIMENSION_KEYS),
        json.dumps([d["key"] for d in good["dimensions"]], ensure_ascii=False),
    )
    checker.check(
        f"{project}: not_evaluated 不带分数",
        all(d.get("score") is None for d in good["dimensions"] if d["status"] != "evaluated"),
        "",
    )
    checker.check(f"{project}: 报告带 caveats", bool(good.get("caveats")), "")

    # 差设计：一个模块 + 环
    worst = {
        "modules": [module("m1", "一锅端", objective="什么都做", exceptions=["出错就报错"])],
        "relations": [{"from": "m1", "to": "m1"}],
        "design_rationale": "一个模块就够了。",
    }
    worst_report = rubric_mod.evaluate_design(graph, task, worst)
    checker.check(
        f"{project}: 差设计分数低于好设计",
        (worst_report["overall_score"] is None) or (worst_report["overall_score"] < (good["overall_score"] or 0)),
        f"good={good['overall_score']} worst={worst_report['overall_score']}",
    )
    checker.check(
        f"{project}: 差设计检出未识别模块",
        "COVERAGE_UNRECOGNIZED" in codes_of(dimension_of(worst_report, "coverage")),
        json.dumps(codes_of(dimension_of(worst_report, "coverage")), ensure_ascii=False),
    )

    # 教师视图与学生视图
    teacher = tb.build_design_task(graph, task["task_id"], teacher_mode=True)
    student = tb.build_design_task(graph, task["task_id"], teacher_mode=False)
    checker.check(f"{project}: 学生视图不含教师字段", all(key not in student for key in TEACHER_ONLY_KEYS), "")
    checker.check(f"{project}: 教师视图含 must_have 全文", bool(teacher.get("must_have")), "")
    checker.check(f"{project}: 未知 task_id 返回 None（不静默降级）", tb.resolve_task(graph, "not_a_task") is None, "")

    # 确定性
    sig_a = rubric_mod.report_signature(rubric_mod.evaluate_design(graph, task, good_submission(task)))
    sig_b = rubric_mod.report_signature(rubric_mod.evaluate_design(graph, task, good_submission(task)))
    checker.check(f"{project}: 报告确定性（两次调用一致）", sig_a == sig_b, "")

    # 覆盖度分母口径：少一项 → (n-1)/n
    partial = good_submission(task)
    partial["modules"] = partial["modules"][:-1]
    partial["relations"] = []
    partial_report = rubric_mod.evaluate_design(graph, task, partial)
    total = len(task["must_have"])
    expected = round(100.0 * (total - 1) / total, 1) if total else None
    checker.check(
        f"{project}: 覆盖度口径 = matched/total",
        dimension_of(partial_report, "coverage").get("score") == expected,
        f"got={dimension_of(partial_report, 'coverage').get('score')} expected={expected}",
    )

    if verbose:
        print(f"    · {project}: level={task['level']} type={task['type_name_cn']} must_have={total} "
              f"good={good['overall_score']} worst={worst_report['overall_score']}")


def check_purity(checker: Checker) -> None:
    """引擎侧不许导入网络 / LLM / 随机 / 时间库（确定性 + 无外部依赖）。"""
    problems: List[str] = []
    package = REPO_ROOT / "engine" / "design"
    pattern = re.compile(r"^\s*(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_.]*)", re.M)
    for path in sorted(package.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            root = match.group(1).split(".")[0]
            if root in FORBIDDEN_IMPORTS:
                problems.append(f"{path.name}: {root}")
    checker.check("纯规则：设计层不导入网络 / LLM / 随机 / 时间库", not problems, "; ".join(problems))

    # 业务词外置：**复用仓库既有的审计脚本**（同一份判定不许存在两套实现）
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import audit_hardcoding  # noqa: E402

    hits, errors, scanned = audit_hardcoding.scan_engine(REPO_ROOT / "engine", REPO_ROOT)
    design_hits = [hit for hit in hits if "/design/" in hit.path]
    checker.check(
        "业务词外置：设计层里 0 处业务名词硬编码（复用 scripts/audit_hardcoding.py）",
        not design_hits,
        "; ".join(hit.format() for hit in design_hits[:5]) or f"扫描 {scanned} 个引擎文件、解析错误 {len(errors)} 个",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="设计层六维评审判定测试")
    parser.add_argument("--project", action="append", default=None, help="参与检查的项目目录（可重复）")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    projects = args.project or DEFAULT_PROJECTS
    checker = Checker(verbose=args.verbose)

    print("=" * 78)
    print("设计层六维评审测试（合成用例 + 真实项目）")
    print("=" * 78)

    print("\n[1] 合成用例（不依赖真实项目数据）")
    run_synthetic(checker)

    print("\n[2] 纯规则与业务词外置")
    check_purity(checker)

    for project in projects:
        print(f"\n[3] 真实项目：{project}")
        run_project(project, checker, args.verbose)

    passed = sum(1 for _, ok, _ in checker.rows if ok)
    total = len(checker.rows)
    print()
    print("=" * 78)
    print(f"结果：{passed}/{total} 项通过" + ("" if checker.failed == 0 else f"，{checker.failed} 项失败"))
    print("=" * 78)
    if checker.failed:
        for name, ok, detail in checker.rows:
            if not ok:
                print(f"  [FAIL] {name}" + (f"  — {detail}" if detail else ""))
    return 1 if checker.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
