"""
阶段二「模块卡片学习」事实覆盖比对器测试（培养方案第四章 阶段二）

测什么
------
1. **不打分**：报告里不存在 score / grade / correct / accuracy / percent 这类字段，
   且 ``scoring == "fact_coverage_only"``、``has_score is False``；
2. **题目来自配置，不来自代码**：五个问题从 ``engine/lexicon/stage_questions.json`` 读出，
   每个问题的字段选择器引擎都认识（出现未知选择器必须被报出来，不许静默忽略）；
3. **卡片不丢**：任务包里的卡片数 == 图谱 ``module_cards`` 的张数（一张都不能少）；
4. **无证据不比对**：``unconfirmed`` 的字段不参与比对 → 该问题进 ``not_comparable``，
   原因里必须出现「待教师确认」；这些字段不进清单也不进分母；
5. **命中判定与阶段一同一份**：全部比对键写进回答 → 全部命中；
   无关回答 → 0 命中；且每个比对键都能被 ``coverage.key_hit`` 复现同样的结论；
6. **确定性**：同一份输入两次调用输出逐字节一致；
7. **纯规则**：模块不导入任何网络 / LLM / 随机 / 时间库（源码级检查）；
8. **合成用例**（不依赖真实项目数据）：状态字段名、上下游模块名被写进回答时必须命中。

用法
----
    python scripts/test_teaching_card_coverage.py
    python scripts/test_teaching_card_coverage.py --project validation/python_dotenv --verbose
"""

from __future__ import annotations

import argparse
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

from engine.project_analyzer import ProjectAnalyzer  # noqa: E402
from engine.teaching import card_coverage as cc  # noqa: E402
from engine.teaching import coverage as cov  # noqa: E402

DEFAULT_PROJECTS = [
    "sample_projects/lab_safety_assistant",
    "validation/python_dotenv",
]

#: 报告里绝对不允许出现的字段名（阶段二不打分）
FORBIDDEN_KEYS = (
    "score", "grade", "grading", "correct", "accuracy", "percent", "percentage",
    "ratio", "rate", "points", "mark",
)

#: 例外：`has_score` 是**反向标记**（值必须是 False，表示「本阶段没有分数」）
ALLOWED_KEYS = ("has_score",)

#: 引擎侧不允许导入的库（无网络、无 LLM、无随机、无时间依赖）
FORBIDDEN_IMPORTS = (
    "requests", "httpx", "urllib", "http", "socket", "openai", "anthropic",
    "random", "time", "datetime",
)

#: 引擎认识的字段选择器（题目配置里出现别的就必须被报出来）
KNOWN_FIELDS = {
    "name", "objective", "business_rules", "preconditions", "exceptions",
    "inputs", "outputs", "state_changes", "does_not",
    "upstream_modules", "downstream_modules",
}


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
    """递归收集 JSON 结构里所有键名（大小写不敏感地查违禁字段）。"""
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


def all_keys_text(report: Dict[str, Any]) -> str:
    """把报告里每个问题的比对键拼成一段「应当全命中」的文本。"""
    chunks: List[str] = []
    for question in report.get("questions", []):
        for key in question.get("keys_considered", []):
            chunks.append(key["key"])
    return " ".join(chunks)


# ============================================================
# 合成用例（不依赖真实项目：卡片是手写的，字段名是中性词）
# ============================================================

def synthetic_graph() -> Dict[str, Any]:
    """一张最小卡片：状态字段名 + 上下游模块名 + 一个待确认的目标。"""
    return {
        "contract_version": "1.0",
        "algorithm_version": "bg-test",
        "project_id": "synthetic_unit_test",
        "source_hash": "sha256:synthetic",
        "domains": [
            {"domain_id": "d_a", "name_cn": "记录处理模块", "role": "core", "confidence": "inferred",
             "children": ["c_a_create"]},
        ],
        "capabilities": [
            {"capability_id": "c_a_create", "name_cn": "创建记录", "parent_id": "d_a", "level": 2},
            {"capability_id": "c_a_approve", "name_cn": "审批记录", "parent_id": "d_a", "level": 2},
            {"capability_id": "c_a_report", "name_cn": "汇总报表", "parent_id": "d_a", "level": 2},
        ],
        "module_cards": {
            "d_a": {
                "module_id": "d_a", "name_cn": "记录处理模块", "level": 1, "parent_id": None,
                "objective": "", "objective_confidence": "unconfirmed",
                "inputs": ["items"], "outputs": ["items"], "member_confidence": "verified",
                "business_rules": [], "state_changes": [], "preconditions": [], "exceptions": [],
                "does_not": ["不负责审批结果"], "does_not_confidence": "inferred",
                "upstream_modules": [], "downstream_modules": ["c_a_approve"],
                "members": [], "evidence": [],
                "confidence": "inferred", "review_status": "needs_review", "source": "auto",
            },
            "c_a_create": {
                "module_id": "c_a_create", "name_cn": "创建记录", "level": 2, "parent_id": "d_a",
                "objective": "把一条新记录写进系统", "objective_confidence": "from_docstring",
                "inputs": ["items"], "outputs": ["items", "counter"],
                "member_confidence": "verified",
                "business_rules": [
                    {"fact_id": "f_1", "kind": "business_rule", "code": "not content",
                     "text": "", "file": "a.py", "start_line": 10, "end_line": 10,
                     "confidence": "verified"},
                ],
                "state_changes": [
                    {"fact_id": "f_2", "kind": "state_change", "code": "create_record 写入 items",
                     "text": "", "file": "a.py", "start_line": 8, "end_line": 12,
                     "confidence": "verified"},
                ],
                "preconditions": [
                    {"fact_id": "f_3", "kind": "guard", "code": "not content", "text": "",
                     "file": "a.py", "start_line": 9, "end_line": 9, "confidence": "verified"},
                ],
                "exceptions": [],
                "does_not": ["不负责审批结果"], "does_not_confidence": "inferred",
                "upstream_modules": [], "downstream_modules": ["c_a_report"],
                "members": [{"symbol": "create_record", "role": "entry", "file": "a.py",
                             "start_line": 8, "end_line": 12}],
                "evidence": [{"file": "a.py", "start_line": 8, "end_line": 12}],
                "confidence": "inferred", "review_status": "needs_review", "source": "auto",
            },
            "c_a_report": {
                "module_id": "c_a_report", "name_cn": "汇总报表", "level": 2, "parent_id": "d_a",
                "objective": "", "objective_confidence": "unconfirmed",
                "inputs": [], "outputs": [], "business_rules": [], "state_changes": [],
                "preconditions": [], "exceptions": [],
                "does_not": [], "does_not_confidence": "unconfirmed",
                "upstream_modules": [], "downstream_modules": [],
                "members": [], "evidence": [],
                "confidence": "inferred", "review_status": "needs_review", "source": "auto",
            },
            "c_a_approve": {
                "module_id": "c_a_approve", "name_cn": "审批记录", "level": 2, "parent_id": "d_a",
                "objective": "", "objective_confidence": "unconfirmed",
                "inputs": [], "outputs": [], "business_rules": [], "state_changes": [],
                "preconditions": [], "exceptions": [],
                "does_not": [], "does_not_confidence": "unconfirmed",
                "upstream_modules": ["c_a_create"], "downstream_modules": [],
                "members": [], "evidence": [],
                "confidence": "unconfirmed", "review_status": "needs_review", "source": "auto",
            },
        },
        "module_relations": [],
    }


def run_synthetic(checker: Checker) -> None:
    """合成用例：命中判定必须真的按字段比对，而不是「有字就算命中」。"""
    print("\n=== 合成用例（手写卡片，不依赖真实项目数据）===")
    graph = synthetic_graph()
    task = cc.build_module_card_task(graph)

    checker.check(
        "合成用例：任务包给出 5 个问题",
        len(task["questions"]) == 5,
        f"{len(task['questions'])} 个问题",
    )
    checker.check(
        "合成用例：卡片一张都不少（4 张：1 个域卡片 + 3 个二级卡片）",
        len(task["cards"]) == 4,
        "、".join(c["module_id"] for c in task["cards"]),
    )

    # 状态字段名写进回答 → 第 4 问必须命中
    report = cc.evaluate_module_card_answers(
        graph,
        "c_a_create",
        {"q4_state": "它写入了 items 这个状态字段。", "q5_not_merge": "汇总报表是另一个模块的事。"},
    )
    by_id = {q["question_id"]: q for q in report["questions"]}
    checker.check(
        "合成用例：回答里写状态字段名 → 「改变了什么状态」命中",
        any(k["key"] == "items" for k in by_id["q4_state"]["matched_keys"]),
        f"命中 {[k['key'] for k in by_id['q4_state']['matched_keys']]}",
    )
    checker.check(
        "合成用例：回答里写下游模块名 → 「为什么不该合并」命中",
        any("汇总报表" in k["key"] for k in by_id["q5_not_merge"]["matched_keys"]),
        f"命中 {[k['key'] for k in by_id['q5_not_merge']['matched_keys']]}",
    )

    # 无关回答 → 0 命中
    unrelated = cc.evaluate_module_card_answers(
        graph, "c_a_create", {q: "今天天气不错，我去操场跑两圈。" for q in
                              ("q1_problem", "q2_inputs", "q3_outputs", "q4_state", "q5_not_merge")}
    )
    checker.check(
        "合成用例：无关回答 0 命中",
        unrelated["counts"]["matched_keys"] == 0,
        f"命中 {unrelated['counts']['matched_keys']} 条",
    )

    # 未确认字段：卡片 c_a_approve 的 objective / 名称 / does_not 全是 unconfirmed
    approve = cc.evaluate_module_card_answers(
        graph, "c_a_approve", {"q1_problem": "它要审批记录。"}
    )
    q1 = {q["question_id"]: q for q in approve["questions"]}["q1_problem"]
    checker.check(
        "合成用例：卡片置信度不足的字段不参与比对，并提示「待教师确认」",
        q1["comparable"] is False and "待教师确认" in q1["not_comparable_reason"],
        q1["not_comparable_reason"],
    )
    checker.check(
        "合成用例：该卡片被标记为 card_needs_review",
        approve["card_needs_review"] is True and bool(approve["unconfirmed_fields"]),
        f"{len(approve['unconfirmed_fields'])} 处待确认",
    )
    checker.check(
        "合成用例：不存在的卡片返回空结果（由后端转成 404，不许静默降级）",
        cc.evaluate_module_card_answers(graph, "not_a_card", {}) == {},
        "返回 {}",
    )
    checker.check(
        "合成用例：不认识的问题标识被原样列出，不静默丢弃",
        cc.evaluate_module_card_answers(graph, "c_a_create", {"q9_unknown": "x"})[
            "unknown_question_ids"
        ] == ["q9_unknown"],
        "unknown_question_ids=['q9_unknown']",
    )


# ============================================================
# 真实项目检查
# ============================================================

def run_project(project: str, checker: Checker, verbose: bool) -> None:
    name = Path(project).name
    print(f"\n=== 校验对象：{project} ===")
    graph = ProjectAnalyzer().analyze(project).to_dict()["business_graph"]
    cards = graph.get("module_cards") or {}

    # ---- 1) 任务包：题目来自词典、卡片不丢 ----
    task = cc.build_module_card_task(graph)
    question_ids = [q["question_id"] for q in task["questions"]]
    checker.check(
        f"{name} 任务包给出 5 个问题（来自题目配置，不写死在前端）",
        len(question_ids) == 5 and all(q["text_cn"] for q in task["questions"]),
        "、".join(q["text_cn"] for q in task["questions"]),
    )
    checker.check(
        f"{name} 卡片一张都不少",
        len(task["cards"]) == len(cards),
        f"任务包 {len(task['cards'])} 张 / 图谱 {len(cards)} 张",
    )

    unknown_selectors: List[str] = []
    empty_fields: List[str] = []
    for item in cc.question_specs():
        if not item["fields"]:
            empty_fields.append(item["question_id"])
        for field in item["fields"]:
            if field not in KNOWN_FIELDS:
                unknown_selectors.append(f"{item['question_id']}:{field}")
    checker.check(
        f"{name} 题目配置里的字段选择器引擎都认识",
        not unknown_selectors and not empty_fields,
        f"未知 {unknown_selectors}；空字段 {empty_fields}" if (unknown_selectors or empty_fields)
        else f"{len(cc.question_specs())} 个问题全部有映射",
    )

    # ---- 2) 全键回答 → 全部命中；无关回答 → 0 命中；空输入 → 合法报告 ----
    first = task["cards"][0]
    empty_report = cc.evaluate_module_card_answers(graph, first["module_id"], {})
    full_answers = {q["question_id"]: all_keys_text(empty_report) for q in empty_report["questions"]}
    full_report = cc.evaluate_module_card_answers(graph, first["module_id"], full_answers)
    checker.check(
        f"{name} 空输入不命中任何键，但仍然是一份合法报告",
        empty_report["empty_input"] is True and empty_report["counts"]["matched_keys"] == 0
        and bool(empty_report["caveats"]),
        f"comparable_questions={empty_report['counts']['comparable_questions']}",
    )
    checker.check(
        f"{name} 把全部比对键写进回答 → 可比对的问题全部命中",
        full_report["counts"]["matched_keys"] > 0
        and full_report["counts"]["questions_with_hits"] == full_report["counts"]["comparable_questions"],
        f"命中 {full_report['counts']['matched_keys']} 条键 / "
        f"可比对问题 {full_report['counts']['comparable_questions']} 个",
    )
    unrelated = cc.evaluate_module_card_answers(
        graph, first["module_id"],
        {q["question_id"]: "今天天气不错，我想去操场跑两圈。" for q in empty_report["questions"]},
    )
    checker.check(
        f"{name} 无关回答 0 命中",
        unrelated["counts"]["matched_keys"] == 0,
        f"命中 {unrelated['counts']['matched_keys']} 条",
    )

    # ---- 3) 命中判定与阶段一同源（行为级交叉验证）----
    sample_answer = all_keys_text(empty_report)
    _norm, compact, tokens = cov.prepare_text(sample_answer)
    reproduced = all(
        cov.key_hit(key["key"], compact, tokens)
        for question in empty_report["questions"]
        for key in question["keys_considered"]
    )
    checker.check(
        f"{name} 阶段二的命中结论能被阶段一的 key_hit 逐条复现（只有一份判定）",
        reproduced and full_report["counts"]["unmatched_keys"] == 0,
        f"阶段二未命中 {full_report['counts']['unmatched_keys']} 条",
    )

    # ---- 4) 不打分 ----
    keys = {k.lower() for k in collect_keys(full_report)}
    hits = sorted(
        k for k in keys
        if any(token in k for token in FORBIDDEN_KEYS) and k not in ALLOWED_KEYS
    )
    checker.check(
        f"{name} 报告里没有分数字段",
        not hits and full_report["has_score"] is False
        and full_report["scoring"] == "fact_coverage_only",
        f"命中违禁字段 {hits}" if hits
        else f"scoring={full_report['scoring']}, has_score={full_report['has_score']}",
    )

    # ---- 5) 确定性 ----
    again = cc.evaluate_module_card_answers(graph, first["module_id"], full_answers)
    checker.check(
        f"{name} 同一输入两次调用逐字节一致",
        json.dumps(full_report, ensure_ascii=False, sort_keys=True)
        == json.dumps(again, ensure_ascii=False, sort_keys=True),
        "一致",
    )

    # ---- 6) 每个问题的比对键都带来源与原始置信度 ----
    missing_origin = [
        f"{q['question_id']}:{k['key']}"
        for q in full_report["questions"]
        for k in q["keys_considered"]
        if not k.get("origin") or "origin_confidence" not in k
    ]
    checker.check(
        f"{name} 每条比对键都带 origin 与原始置信度（UI 要能说清「拿什么比的」）",
        not missing_origin,
        f"缺来源 {missing_origin[:3]}" if missing_origin else "全部带来源",
    )

    # ---- 7) 未确认字段：人造用例，不许改真实图谱 ----
    probe_source = next(
        (
            c for c in task["cards"]
            if str(c.get("objective") or "").strip()
            and not cov.is_unconfirmed(c.get("objective_confidence"))
        ),
        None,
    )
    if probe_source is None:
        checker.check(
            f"{name} unconfirmed 的目标文本不参与比对（键真的被拿掉）",
            not any(
                k["origin"] == "card_objective"
                for q in full_report["questions"]
                for k in q["keys_considered"]
            ),
            "本项目没有任何「已确认的目标文本」，改用「待确认的目标文本一条键都没进」来断言",
        )
        after = full_report
    else:
        probe_id = str(probe_source["module_id"])
        probe_answer = str(probe_source["objective"])
        probe_answers = {q["question_id"]: probe_answer for q in empty_report["questions"]}
        before = cc.evaluate_module_card_answers(graph, probe_id, probe_answers)
        probe = json.loads(json.dumps(graph))
        probe["module_cards"][probe_id]["objective_confidence"] = "unconfirmed"
        after = cc.evaluate_module_card_answers(probe, probe_id, probe_answers)

        q1_before = {q["question_id"]: q for q in before["questions"]}["q1_problem"]
        q1_after = {q["question_id"]: q for q in after["questions"]}["q1_problem"]
        had = [k for k in q1_before["keys_considered"] if k["origin"] == "card_objective"]
        still = [k for k in q1_after["keys_considered"] if k["origin"] == "card_objective"]
        checker.check(
            f"{name} unconfirmed 的目标文本不参与比对（键真的被拿掉）",
            bool(had)
            and any(k["key"] == cov.normalize_text(probe_answer) for k in q1_before["matched_keys"])
            and not still
            and len(q1_after["keys_considered"]) < len(q1_before["keys_considered"]),
            f"{probe_id} q1 键数 {len(q1_before['keys_considered'])} → "
            f"{len(q1_after['keys_considered'])}（原本命中 "
            f"{sum(1 for k in q1_before['matched_keys'] if k['origin'] == 'card_objective')} 条）",
        )
    checker.check(
        f"{name} unconfirmed 字段在报告里被列为「待教师确认」",
        after["card_needs_review"] is True
        and any(
            "待教师确认" in item["reason"] or "待教师确认" in item["label"]
            for item in after["unconfirmed_fields"]
        ),
        f"{len(after['unconfirmed_fields'])} 处待确认",
    )
    checker.check(
        f"{name} unconfirmed 的问题写明原因（不许当成「没提到」）",
        all(
            (q["comparable"] and not q["not_comparable_reason"])
            or (not q["comparable"] and q["not_comparable_reason"].strip())
            for q in after["questions"]
        ),
        "每个不可比对的问题都有原因",
    )

    # ---- 8) 状态路径解析：报告可解析率（据实打印，不作门槛）----
    parsed = unparsed = 0
    for card in task["cards"]:
        for fact in card.get("state_changes") or []:
            if cc.extract_state_path(fact.get("code")):
                parsed += 1
            else:
                unparsed += 1
    checker.check(
        f"{name} 状态变化事实的状态路径可解析（解析不出会退回整条文本，不假装解析成功）",
        parsed + unparsed == 0 or parsed > 0,
        f"可解析 {parsed} 条 / 退回整条文本 {unparsed} 条",
    )


def check_purity(checker: Checker) -> None:
    """模块必须是纯规则：无网络、无 LLM、无随机、无时间依赖；且复用阶段一的判定。"""
    source = (REPO_ROOT / "engine" / "teaching" / "card_coverage.py").read_text(encoding="utf-8")
    imported = set()
    for line in source.splitlines():
        match = re.match(r"\s*(?:from|import)\s+([A-Za-z_][\w.]*)", line)
        if match:
            imported.add(match.group(1).split(".")[0])
    bad = sorted(imported & set(FORBIDDEN_IMPORTS))
    checker.check(
        "阶段二比对器不导入网络/LLM/随机/时间库",
        not bad,
        f"违禁导入 {bad}" if bad else f"仅导入 {sorted(imported)}",
    )
    checker.check(
        "阶段二比对器带 algorithm_version 与 scoring",
        cc.ALGORITHM_VERSION.startswith("card-coverage-") and cc.SCORING == "fact_coverage_only",
        f"algorithm_version={cc.ALGORITHM_VERSION}, scoring={cc.SCORING}",
    )
    checker.check(
        "阶段二复用阶段一的命中判定（同一模块对象，不是复制一份）",
        cc.cov is cov,
        "engine.teaching.card_coverage.cov is engine.teaching.coverage",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="阶段二「模块卡片学习」事实覆盖比对器测试")
    parser.add_argument("--project", action="append", default=None,
                        help="参与检查的项目目录（可重复）")
    parser.add_argument("--verbose", action="store_true", help="打印每一项，而不只是失败项")
    args = parser.parse_args()

    projects = args.project or DEFAULT_PROJECTS
    checker = Checker(verbose=args.verbose)

    print("=" * 78)
    print("阶段二「模块卡片学习」事实覆盖比对器测试")
    print("=" * 78)

    run_synthetic(checker)

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
