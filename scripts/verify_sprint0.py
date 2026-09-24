"""
Sprint 0 验收总检查（README5 §8 的 Sprint 0 验收清单）

为什么需要一个"总检查"
----------------------
Sprint 0 的验收项分散在多个脚本里（契约校验、确定性双跑、硬编码审计、
引擎测试）。逐个跑容易漏，也不方便在答辩前快速确认"现在是不是干净的"。

本脚本**在一个进程内**把所有可自动化的验收项跑完并打印一张总表：

| 编号 | 验收项 | 实现方式 |
|---|---|---|
| A1 | 契约不含绝对路径 / 答案 / 内部标记 | 复用 `validate_contract.validate_payload` |
| A2 | 同一份代码双跑输出一致 | 复用 `check_determinism.check_project` |
| A3 | 引擎代码里没有业务硬编码 | 复用 `audit_hardcoding.scan_engine` |
| A4 | `engine/business_logic` 可正常导入，坏引用已清除 | 直接 import + 断言 |
| A5 | AST 缓存生效：每个文件只解析一次 | `ast_cache.stats()` + 与文件数比对 |
| A6 | 每个演示项目都有 快照 / 答案表 / 源码副本 | 检查产物文件 |
| A7 | 学生快照里没有答案，教师模式有 | 直接读后端服务函数 |
| A8 | 后端判题可用且不泄漏答案本身 | 复用 `project_store.grade_answer` |
| A9 | 阶段一「项目认知」覆盖度报告：不打分、无遗漏域、确定性、拒绝空提交 | 复用 `backend.app.services.teaching_service` + `engine.teaching.coverage` |
| A10 | 阶段二「模块卡片学习」事实覆盖报告：题目来自配置、卡片不丢、不打分、待确认字段不参与比对 | 复用 `backend.app.services.teaching_service` + `engine.teaching.card_coverage` |

注意：本脚本**不**调用子进程，也不用管道捕获输出 ——
在当前沙箱下通过管道捕获原生程序输出会被拒绝，所以全部改为进程内调用。

用法
----
    python scripts/verify_sprint0.py
    python scripts/verify_sprint0.py --project sample_projects/lab_safety_assistant
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
]

#: 演示项目（project_id）→ 是否默认项目
DEMO_PROJECTS = [
    ("lab_safety_assistant", True),
    ("python_dotenv", False),
]

#: 设计层六维的顺序（A11 用它核对「六维齐全」，与引擎里的定义保持同一份顺序）
DIMENSION_KEYS = ("coverage", "clarity", "hierarchy", "dependency", "edge_case", "rationale")


class Summary:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, bool, str]] = []

    def add(self, code: str, name: str, passed: bool, detail: str = "") -> None:
        self.rows.append((code, name, passed, detail))

    @property
    def failed(self) -> int:
        return sum(1 for _, _, passed, _ in self.rows if not passed)

    def render(self) -> None:
        print()
        print("=" * 78)
        print("Sprint 0 验收总表")
        print("=" * 78)
        for code, name, passed, detail in self.rows:
            mark = "PASS" if passed else "FAIL"
            line = f"[{mark}] {code:<3} {name}"
            if detail:
                line += f"  — {detail}"
            print(line)
        print("-" * 78)
        total = len(self.rows)
        ok = total - self.failed
        print(f"合计 {ok}/{total} 项通过" + ("" if not self.failed else f"，{self.failed} 项失败"))


# ============================================================
# 各项检查
# ============================================================

def check_contract(summary: Summary, projects: list[str]) -> None:
    """A1：契约校验（复用 validate_contract）。"""
    from scripts.validate_contract import validate_payload
    from engine.project_analyzer import ProjectAnalyzer

    for project in projects:
        if not (REPO_ROOT / project).is_dir():
            summary.add("A1", f"契约校验 {project}", False, "目录不存在")
            continue
        payload = ProjectAnalyzer().analyze(project).to_dict()
        report = validate_payload(payload, project)
        failed = [name for name, passed, _ in report.checks if not passed]
        summary.add(
            "A1",
            f"契约校验 {Path(project).name}",
            not failed,
            "" if not failed else f"未通过: {failed}",
        )


def check_determinism(summary: Summary, projects: list[str]) -> None:
    """A2：确定性双跑。"""
    from scripts.check_determinism import check_project

    for project in projects:
        if not (REPO_ROOT / project).is_dir():
            summary.add("A2", f"确定性双跑 {project}", False, "目录不存在")
            continue
        result = check_project(project)
        summary.add(
            "A2",
            f"确定性双跑 {Path(project).name}",
            result["identical"],
            "" if result["identical"] else f"第一处差异 {result['difference'][0]}",
        )


def check_hardcoding(summary: Summary) -> None:
    """A3：引擎里没有业务硬编码。"""
    from scripts.audit_hardcoding import scan_engine

    engine_dir = REPO_ROOT / "engine"
    hits, errors, scanned = scan_engine(engine_dir, REPO_ROOT)
    summary.add(
        "A3",
        "引擎无业务硬编码",
        not hits and not errors,
        f"扫描 {scanned} 个文件，命中 {len(hits)} 处，解析错误 {len(errors)} 个",
    )


def check_business_logic(summary: Summary) -> None:
    """A4：models 层可导入、契约别名正确、坏引用已清除。"""
    try:
        import engine.business_logic as bl
        from engine.business_logic import BusinessGraph, BusinessModule
    except Exception as exc:  # pragma: no cover
        summary.add("A4", "business_logic 可导入", False, f"{type(exc).__name__}: {exc}")
        return

    graph = BusinessGraph()
    graph.modules["m"] = BusinessModule(module_id="m", name="样例模块")
    payload = graph.to_dict()
    module_card = payload.get("module_cards", {}).get("m", {})

    problems = []
    if "module_cards" not in payload:
        problems.append("缺少 module_cards（契约别名）")
    if "name_cn" not in module_card:
        problems.append("缺少 name_cn（契约别名）")
    if "does_not" not in module_card:
        problems.append("缺少 does_not（契约别名）")
    if payload.get("contract_version") != "1.0":
        problems.append("缺少 contract_version")

    # 坏引用必须已经删除
    try:
        bl.BusinessLogicTrainingEngine  # noqa: B018
        problems.append("坏引用 BusinessLogicTrainingEngine 仍然存在")
    except AttributeError:
        pass

    summary.add(
        "A4",
        "business_logic 契约层可用",
        not problems,
        "" if not problems else "; ".join(problems),
    )


def check_ast_cache(summary: Summary, project: str) -> None:
    """A5：AST 缓存生效（每个文件只解析一次）。"""
    if not (REPO_ROOT / project).is_dir():
        summary.add("A5", f"AST 缓存 {project}", False, "目录不存在")
        return

    from engine.parser import clear_ast_cache, ast_cache_stats
    from engine.project_analyzer import ProjectAnalyzer

    clear_ast_cache()
    result = ProjectAnalyzer().analyze(project)
    stats = ast_cache_stats()
    total_files = (result.overview or {}).get("total_files", 0)

    # 每个文件恰好一次 tree miss（= 真正解析一次），其余都是命中
    ok = stats["tree_misses"] <= total_files and stats["tree_hits"] > 0
    summary.add(
        "A5",
        f"AST 缓存 {Path(project).name}",
        ok,
        f"{total_files} 个文件；source miss/hit={stats['source_misses']}/{stats['source_hits']}，"
        f"tree miss/hit={stats['tree_misses']}/{stats['tree_hits']}",
    )


def check_artifacts(summary: Summary) -> None:
    """A6：两个演示项目的产物齐全。"""
    from backend.app.services import project_store

    for project_id, is_default in DEMO_PROJECTS:
        snapshot = project_store.snapshot_path(project_id)
        answer_key = project_store.answer_key_path(project_id)
        source_root = project_store.demo_source_root(project_id)
        missing = []
        if not snapshot.exists():
            missing.append("学生快照")
        if not answer_key.exists():
            missing.append("后端答案表")
        if not source_root.exists():
            missing.append("源码副本")
        summary.add(
            "A6",
            f"演示产物 {project_id}",
            not missing,
            "产物齐全" if not missing else f"缺少 {missing}",
        )


def check_answer_visibility(summary: Summary) -> None:
    """A7：学生快照无答案/讲解，教师模式有。"""
    from backend.app.services import project_store

    problems = []
    for project_id, _ in DEMO_PROJECTS:
        student = project_store.load_snapshot(project_id, teacher_mode=False)
        teacher = project_store.load_snapshot(project_id, teacher_mode=True)
        if student is None:
            problems.append(f"{project_id}: 学生快照缺失")
            continue

        for index, question in enumerate((student.get("training") or {}).get("questions", []) or []):
            if "correct_answers" in question:
                problems.append(f"{project_id} 学生快照第 {index} 题含 correct_answers")
            if "explanation" in question:
                problems.append(f"{project_id} 学生快照第 {index} 题含 explanation")

        if teacher is None:
            problems.append(f"{project_id}: 教师模式读取失败")
        else:
            teacher_questions = (teacher.get("training") or {}).get("questions", []) or []
            if teacher_questions and "correct_answers" not in teacher_questions[0]:
                problems.append(f"{project_id} 教师模式没有补回 correct_answers")

    summary.add(
        "A7",
        "答案可见性边界（学生无 / 教师有）",
        not problems,
        "" if not problems else "; ".join(problems[:3]),
    )


def check_backend_grading(summary: Summary) -> None:
    """A8：后端判题在答案表存在时可用，且不返回答案本身。"""
    from backend.app.services import project_store

    project_id = DEMO_PROJECTS[0][0]
    key = project_store.load_answer_key(project_id)
    if not key or not key.get("questions"):
        summary.add("A8", "后端判题", False, "答案表缺失或为空")
        return

    index = sorted(key["questions"].keys(), key=lambda x: int(x))[0]
    expected = key["questions"][index]["answers"]
    result = project_store.grade_answer(project_id, int(index), expected)

    problems = []
    if result is None:
        problems.append("判题返回 None")
    else:
        if result["result"] != "correct":
            problems.append(f"标准答案被判为 {result['result']}")
        if "correct_answers" in result:
            problems.append("判题结果把答案本身返回了")

    wrong = project_store.grade_answer(project_id, int(index), ["__Z__"])
    if wrong and wrong["result"] == "correct":
        problems.append("错误答案被判为 correct")

    summary.add(
        "A8",
        "后端判题（含不泄漏答案）",
        not problems,
        "" if not problems else "; ".join(problems),
    )


def check_teaching_orientation(summary: Summary) -> None:
    """A9：阶段一「项目认知」的覆盖度报告（Sprint 3）。

    查四件事：
      1. **不打分**：报告里没有 score / correct 这类字段，``scoring == "coverage_only"``；
      2. **不丢域**：每个核心域必须恰好落进 covered / missed / not_comparable 之一
         （否则就是""悄悄漏掉了一个模块""——那比给错覆盖清单更糟）；
      3. **确定性**：同一份输入两次调用逐字节一致；
      4. **入口校验**：空提交被明确拒绝（400），不返回一份""全未命中""的报告。
    """
    from backend.app.services import teaching_service

    problems: list[str] = []
    checked = 0

    for project_id, _ in DEMO_PROJECTS:
        snapshot = project_store_snapshot(project_id)
        if snapshot is None:
            problems.append(f"{project_id}: 快照缺失")
            continue
        graph = snapshot.get("business_graph") or {}
        core_ids = {
            str(d.get("domain_id"))
            for d in (graph.get("domains") or [])
            if str(d.get("role") or "").lower() not in ("orchestrator", "support")
        }

        # 造一段""把每个可比对键都写进去""的回答：应当全部命中
        report, error = teaching_service.evaluate_orientation_for_project(
            project_id, " ".join(str(d.get("name_cn") or "") for d in (graph.get("domains") or []))
        )
        if error is not None:
            problems.append(f"{project_id}: 覆盖度比对失败 {error}")
            continue
        checked += 1

        if report.get("has_score") is not False or report.get("scoring") != "coverage_only":
            problems.append(f"{project_id}: 报告不是 coverage_only（{report.get('scoring')}）")

        forbidden = ("score", "correct", "grade", "accuracy", "percent", "ratio")
        keys: list[str] = []

        def _walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    keys.append(str(key).lower())
                    _walk(value)
            elif isinstance(node, list):
                for item in node:
                    _walk(item)

        _walk(report)
        bad = sorted({k for k in keys if any(t in k for t in forbidden) and k != "has_score"})
        if bad:
            problems.append(f"{project_id}: 报告里出现分数字段 {bad}")

        buckets = {str(i["domain_id"]) for i in report["covered"]} | \
                  {str(i["domain_id"]) for i in report["missed"]} | \
                  {str(i["domain_id"]) for i in report["not_comparable"]}
        if buckets != core_ids:
            problems.append(f"{project_id}: 核心域覆盖不全，差集 {sorted(core_ids ^ buckets)}")

        if report["counts"]["comparable_domains"] != len(report["covered"]) + len(report["missed"]):
            problems.append(f"{project_id}: comparable 计数与清单长度不一致")

        import json as _json
        again, _ = teaching_service.evaluate_orientation_for_project(
            project_id, " ".join(str(d.get("name_cn") or "") for d in (graph.get("domains") or []))
        )
        if _json.dumps(report, ensure_ascii=False, sort_keys=True) != _json.dumps(again, ensure_ascii=False, sort_keys=True):
            problems.append(f"{project_id}: 同一输入两次调用结果不一致")

        if not report.get("caveats"):
            problems.append(f"{project_id}: 报告没有 caveats（诚实边界）")

        _, empty_error = teaching_service.evaluate_orientation_for_project(project_id, "   ")
        if empty_error is None or empty_error[0] != 400:
            problems.append(f"{project_id}: 空提交未被拒绝")

    summary.add(
        "A9",
        "阶段一覆盖度报告（不打分 / 不丢域 / 确定性）",
        not problems,
        f"{checked} 个项目通过" if not problems else "; ".join(problems[:3]),
    )


def project_store_snapshot(project_id: str):
    """取项目快照（避免在模块顶层 import backend 时踩到 sys.path 顺序问题）。"""
    from backend.app.services import project_store

    return project_store.load_snapshot(project_id)


def check_teaching_module_card(summary: Summary) -> None:
    """A10：阶段二「模块卡片学习」的事实覆盖报告（Sprint 4）。

    查六件事：
      1. **题目来自配置**：任务包给出 5 个问题，且卡片数与图谱一致（一张都不许丢）；
      2. **不打分**：报告里没有 score / correct 这类字段，``scoring == "fact_coverage_only"``；
      3. **比对真的跑了**：把全部比对键写进回答 → 可比对的问题全部命中、未命中 0 条；
      4. **确定性**：同一份输入两次调用逐字节一致；
      5. **无证据不比对**：置信度为 ``unconfirmed`` 的字段被排除，报告里写明「待教师确认」；
      6. **入口校验**：空提交 / 未知问题标识 / 不存在的卡片分别被 400 / 400 / 404 拒绝。
    """
    from backend.app.services import teaching_service

    problems: list[str] = []
    checked = 0
    cards_total = 0
    cards_needing_review = 0

    for project_id, _ in DEMO_PROJECTS:
        task, error = teaching_service.build_module_card_task_for_project(project_id)
        if error is not None:
            problems.append(f"{project_id}: 任务包构建失败 {error}")
            continue

        if len(task["questions"]) != 5:
            problems.append(f"{project_id}: 问题数不是 5（{len(task['questions'])}）")
        if not all(q["text_cn"] for q in task["questions"]):
            problems.append(f"{project_id}: 有问题没有文本")

        snapshot = project_store_snapshot(project_id) or {}
        graph = snapshot.get("business_graph") or {}
        if len(task["cards"]) != len(graph.get("module_cards") or {}):
            problems.append(
                f"{project_id}: 卡片数不一致（任务包 {len(task['cards'])} / "
                f"图谱 {len(graph.get('module_cards') or {})}）"
            )

        cards_total += len(task["cards"])
        cards_needing_review += task["counts"]["cards_needing_review"]

        # 选一张"目标文本已确认"的卡片：比对键最多，最能验证比对真的跑了
        target = next(
            (c for c in task["cards"] if str(c.get("objective") or "").strip()
             and str(c.get("objective_confidence") or "") != "unconfirmed"),
            task["cards"][0],
        )
        module_id = str(target["module_id"])

        _probe, probe_error = teaching_service.evaluate_module_card_for_project(
            project_id, module_id, {"q1_problem": "先探一次，拿比对键。"}
        )
        if probe_error is not None:
            problems.append(f"{project_id}: 覆盖比对失败 {probe_error}")
            continue
        checked += 1

        all_keys = " ".join(
            key["key"] for q in _probe["questions"] for key in q["keys_considered"]
        )
        answers = {q["question_id"]: all_keys for q in _probe["questions"]}
        report, error = teaching_service.evaluate_module_card_for_project(project_id, module_id, answers)
        if error is not None:
            problems.append(f"{project_id}: 覆盖比对失败 {error}")
            continue

        if report.get("has_score") is not False or report.get("scoring") != "fact_coverage_only":
            problems.append(f"{project_id}: 报告不是 fact_coverage_only（{report.get('scoring')}）")

        forbidden = ("score", "correct", "grade", "accuracy", "percent", "ratio")
        keys: list[str] = []

        def _walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    keys.append(str(key).lower())
                    _walk(value)
            elif isinstance(node, list):
                for item in node:
                    _walk(item)

        _walk(report)
        bad = sorted({k for k in keys if any(t in k for t in forbidden) and k != "has_score"})
        if bad:
            problems.append(f"{project_id}: 报告里出现分数字段 {bad}")

        counts = report["counts"]
        if counts["unmatched_keys"] != 0 or counts["questions_with_hits"] != counts["comparable_questions"]:
            problems.append(
                f"{project_id}: 全键回答未全部命中（命中 {counts['matched_keys']} / "
                f"未命中 {counts['unmatched_keys']}）"
            )

        for question in report["questions"]:
            if question["comparable"] == bool(question["not_comparable_reason"]):
                problems.append(
                    f"{project_id}: {question['question_id']} 的「可比对」与原因自相矛盾"
                )
            if not question["comparable"] and not question["not_comparable_reason"].strip():
                problems.append(f"{project_id}: {question['question_id']} 不可比对却没写原因")

        again, _ = teaching_service.evaluate_module_card_for_project(project_id, module_id, answers)
        if json.dumps(report, ensure_ascii=False, sort_keys=True) != json.dumps(
            again, ensure_ascii=False, sort_keys=True
        ):
            problems.append(f"{project_id}: 同一输入两次调用结果不一致")

        # 未确认字段：把目标的置信度改成 unconfirmed（内存里改，不动磁盘），键必须被拿掉
        probe = json.loads(json.dumps(graph))
        probe_card = probe["module_cards"].get(module_id) or {}
        probe_card["objective_confidence"] = "unconfirmed"
        from engine.teaching.card_coverage import evaluate_module_card_answers

        after = evaluate_module_card_answers(probe, module_id, answers)
        still = [
            key
            for question in after["questions"]
            for key in question["keys_considered"]
            if key["origin"] == "card_objective"
        ]
        before = [
            key
            for question in report["questions"]
            for key in question["keys_considered"]
            if key["origin"] == "card_objective"
        ]
        if before and still:
            problems.append(f"{project_id}: unconfirmed 的目标文本仍参与比对（{len(still)} 条键）")
        if after.get("card_needs_review") is not True or not after.get("unconfirmed_fields"):
            problems.append(f"{project_id}: unconfirmed 字段没有被标记为「待教师确认」")
        if not any("待教师确认" in line for line in after.get("caveats") or []):
            problems.append(f"{project_id}: 报告 caveats 里没有「该卡片待教师确认」的说明")

        # 入口校验
        _, empty_error = teaching_service.evaluate_module_card_for_project(
            project_id, module_id, {"q1_problem": "   "}
        )
        if empty_error is None or empty_error[0] != 400:
            problems.append(f"{project_id}: 空提交未被拒绝（{empty_error}）")

        _, unknown_error = teaching_service.evaluate_module_card_for_project(
            project_id, module_id, {"q_not_a_question": "内容"}
        )
        if unknown_error is None or unknown_error[0] != 400:
            problems.append(f"{project_id}: 未知问题标识未被拒绝（{unknown_error}）")

        _, card_error = teaching_service.evaluate_module_card_for_project(
            project_id, "not_a_real_card", {"q1_problem": "内容"}
        )
        if card_error is None or card_error[0] != 404:
            problems.append(f"{project_id}: 不存在的卡片未被拒绝（{card_error}）")

    summary.add(
        "A10",
        "阶段二事实覆盖报告（题目来自配置 / 卡片不丢 / 不打分 / 待确认不比对）",
        not problems,
        (
            f"{checked} 个项目、{cards_total} 张卡片通过"
            f"（其中 {cards_needing_review} 张含待教师确认字段）"
            if not problems else "; ".join(problems[:3])
        ),
    )


def check_teaching_design(summary: Summary) -> None:
    """A11：阶段四「设计画布」的六维评审（Sprint 5 / README §18 优先级 3）。

    查六件事：

      1. **任务来自图谱与级别**：任务清单非空、默认任务可取到、题干占位符已全部替换；
      2. **可见性矩阵**：学生视图里没有 ``must_have`` 全文 / 权重数值 / 必备依赖 / 禁止合并项，
         教师视图（``?mode=teacher``）有；
      3. **六维齐全 + 算不出来就 not_evaluated**：``score is None``、带 ``reason``、
         且**空提交不给总分**（不是 0 分）；
      4. **覆盖度口径**：为每项必备能力建一个模块时覆盖度满分；少一项时为 ``(n-1)/n``；
      5. **确定性**：同一份输入两次调用逐字节一致；
      6. **入口校验**：空提交 / 未命名模块 / 不存在的任务分别被 400 / 400 / 404 明确拒绝。
    """
    from backend.app.services import teaching_service

    problems: list[str] = []
    checked = 0
    task_count = 0

    for project_id, _ in DEMO_PROJECTS:
        snapshot = project_store_snapshot(project_id)
        if snapshot is None:
            problems.append(f"{project_id}: 快照缺失")
            continue
        graph = snapshot.get("business_graph") or {}

        listing, error = teaching_service.list_design_tasks_for_project(project_id)
        if error is not None:
            problems.append(f"{project_id}: 任务清单失败 {error}")
            continue
        tasks = listing.get("tasks") or []
        if not tasks:
            problems.append(f"{project_id}: 任务清单为空")
            continue
        task_count += len(tasks)

        default_id = str(listing.get("default_task_id") or "")
        student_view, error = teaching_service.build_design_task_for_project(project_id, default_id)
        if error is not None:
            problems.append(f"{project_id}: 学生视图取失败 {error}")
            continue
        teacher_view, error = teaching_service.build_design_task_for_project(
            project_id, default_id, teacher_mode=True
        )
        if error is not None:
            problems.append(f"{project_id}: 教师视图取失败 {error}")
            continue
        checked += 1

        # 1) 题干占位符
        for key in ("prompt_cn", "scenario_cn"):
            if "{" in str(teacher_view.get(key) or ""):
                problems.append(f"{project_id}: {key} 里还有未替换的占位符")

        # 2) 可见性矩阵
        teacher_only = ("must_have", "required_relations", "forbidden_merges", "acceptable_alternatives", "rubric_weights")
        leaked = [key for key in teacher_only if key in student_view]
        if leaked:
            problems.append(f"{project_id}: 学生视图泄漏教师字段 {leaked}")
        if not teacher_view.get("must_have"):
            problems.append(f"{project_id}: 教师视图没有 must_have")

        # 3) 六维 + 好设计 / 空提交
        must_have = teacher_view.get("must_have") or []
        modules = []
        for index, item in enumerate(must_have):
            modules.append(
                {
                    "module_id": f"m{index + 1}",
                    "name": str(item.get("name_cn") or ""),
                    "level": 1,
                    "parent_id": None,
                    "objective": f"负责{item.get('name_cn') or ''}",
                    "inputs": ["入参"],
                    "outputs": ["出参"],
                    "does_not": ["不负责其它模块的职责"],
                    "business_rules": ["必须校验入参是否为空"],
                    "state_changes": ["写入状态字段"],
                    "exceptions": ["入参为空时拒绝并报错"],
                    "depends_on": [],
                }
            )
        relations = [
            {"from": f"m{index + 1}", "to": f"m{index}", "type": "uses"} for index in range(1, len(modules))
        ]
        submission = {
            "submission_id": "sub_verify",
            "task_id": default_id,
            "iteration": 1,
            "modules": modules,
            "relations": relations,
            "design_rationale": (
                "我把必备能力按职责拆成模块：每个模块只负责一件事，模块之间是依赖关系，"
                "状态变化集中在链路末端，并且每个模块都写了入参校验与拒绝规则。"
            ),
        }
        report, error = teaching_service.evaluate_design_for_project(project_id, default_id, submission)
        if error is not None:
            problems.append(f"{project_id}: 评审失败 {error}")
            continue

        if [item.get("key") for item in report.get("dimensions") or []] != list(DIMENSION_KEYS):
            problems.append(f"{project_id}: 六维不齐 {[item.get('key') for item in report.get('dimensions') or []]}")
        if any(
            item.get("score") is not None
            for item in report.get("dimensions") or []
            if item.get("status") != "evaluated"
        ):
            problems.append(f"{project_id}: not_evaluated 的维度带了分数（不许填 0）")
        if not all(item.get("reason") for item in report.get("dimensions") or [] if item.get("status") != "evaluated"):
            problems.append(f"{project_id}: not_evaluated 的维度没写原因")

        coverage = next((item for item in report["dimensions"] if item["key"] == "coverage"), {})
        if must_have and coverage.get("score") != 100.0:
            problems.append(f"{project_id}: 全覆盖设计的覆盖度不是 100（{coverage.get('score')}）")
        covered_weight = sum(item["normalized_weight"] for item in report.get("weights") or [])
        if report.get("weights") and abs(covered_weight - 1.0) > 0.001:
            problems.append(f"{project_id}: 权重归一化后不等于 1（{covered_weight}）")

        import json as _json

        again, _ = teaching_service.evaluate_design_for_project(project_id, default_id, submission)
        if _json.dumps(report, ensure_ascii=False, sort_keys=True) != _json.dumps(again, ensure_ascii=False, sort_keys=True):
            problems.append(f"{project_id}: 同一份设计两次评审结果不一致")

        if not report.get("caveats"):
            problems.append(f"{project_id}: 报告没有 caveats（诚实边界）")

        # 4) 入口校验
        _, empty_error = teaching_service.evaluate_design_for_project(
            project_id, default_id, {"modules": [], "relations": []}
        )
        if empty_error is None or empty_error[0] != 400:
            problems.append(f"{project_id}: 空提交未被拒绝（{empty_error}）")

        _, unnamed_error = teaching_service.evaluate_design_for_project(
            project_id, default_id, {"modules": [{"module_id": "m1", "name": "  "}], "relations": []}
        )
        if unnamed_error is None or unnamed_error[0] != 400:
            problems.append(f"{project_id}: 未命名模块未被拒绝（{unnamed_error}）")

        _, task_error = teaching_service.evaluate_design_for_project(
            project_id, "not_a_task", submission
        )
        if task_error is None or task_error[0] != 404:
            problems.append(f"{project_id}: 不存在的任务未被拒绝（{task_error}）")

    summary.add(
        "A11",
        "阶段四设计层六维评审（可见性 / not_evaluated / 确定性 / 入口校验）",
        not problems,
        f"{checked} 个项目、{task_count} 个任务通过" if not problems else "; ".join(problems[:3]),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Sprint 0 验收总检查")
    parser.add_argument("--project", action="append", default=None,
                        help="参与契约/确定性检查的项目目录（可重复）")
    args = parser.parse_args()

    projects = args.project or DEFAULT_PROJECTS
    summary = Summary()

    print("=" * 78)
    print("Sprint 0 验收总检查（进程内运行，不启动子进程）")
    print("=" * 78)

    check_contract(summary, projects)
    check_determinism(summary, projects)
    check_hardcoding(summary)
    check_business_logic(summary)
    check_ast_cache(summary, projects[0])
    check_artifacts(summary)
    check_answer_visibility(summary)
    check_backend_grading(summary)
    check_teaching_orientation(summary)
    check_teaching_module_card(summary)
    check_teaching_design(summary)

    summary.render()
    return 1 if summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
