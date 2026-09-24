"""
教师种子（优先级 3.5）验收测试 —— README §18 优先级 3.5

为什么需要这个脚本
------------------
`scripts/test_design_rubric.py` 里确实有教师种子的断言，但它用的是**注进
`LEXICON_CACHE` 的合成种子**（合成工程 `synthetic_project`）。那批断言能证明
「引擎支持种子」，**不能证明仓库里这份 `design_tasks.seed.json` 真的可用**：

    优先级 3.5 的验收原文是「`ALT_ACCEPTED` / `DEP_REQUIRED_MISSING` /
    `EDGE_REQUIRED_MISSING` 这三个信号**能被真实触发**（不是只能靠测试注入
    种子来触发）」。

所以本脚本**不注入任何东西**，直接读仓库里的种子文件，在真实项目
`sample_projects/lab_safety_assistant` 上跑两份真实提交：

- 合规设计（每项能力一个模块 + 连成链 + 写上两个必备边界）→ 必备依赖与
  必备边界**都不该扣分**；
- 违规设计（把该分开的能力合并、且不写那两个边界）→ 三条信号全部触发。

测什么
------
1. **种子确实被读到**：`must_have_source = teacher_seed`、`needs_review = false`、
   `must_have_confirmed = true`（页面上不再出现「待教师确认」徽章）；
2. **清单可评分的硬约束**：`(verb_class, entity)` 两两不重复
   （`test_design_rubric.py` 也断言这条，这里在真实种子上再断言一次）；
3. **三份清单齐全**：必备依赖 2 条、必备边界 2 个、可接受替代结构 2 条、
   禁止合并 1 条（README §18 优先级 3.5 明写的交付物）；
4. **学生视图不泄漏**：不含 must_have / 依赖 / 禁止合并 / 替代结构 / 权重；
5. **合规设计不被误判**：`ALT_ACCEPTED` 出现，两条 `*_REQUIRED_MISSING` 不出现；
6. **违规设计能被抓住**：`DEP_REQUIRED_MISSING` / `EDGE_REQUIRED_MISSING` /
   `ALT_FORBIDDEN_MERGE` 全部出现（这就是 3.5 的验收口径）；
7. **只影响有种子那个项目**：`python_dotenv` 仍然走自动提炼
   （`auto_from_project` + `needs_review = true`）；
8. **种子存在时不再生成自动任务**：`lab_safety_assistant` 的任务数由 3 变 1
   —— 这是 `task_builder.py:533-539` 的设计，不是 bug，但必须有断言钉住；
9. **确定性**：同一份提交两次评审逐字节一致。

用法
----
    python scripts/test_design_seed.py
    python scripts/test_design_seed.py --verbose
"""

from __future__ import annotations

import argparse
import json
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

from engine.design import rubric as rubric_mod  # noqa: E402
from engine.design import task_builder as tb  # noqa: E402
from engine.project_analyzer import ProjectAnalyzer  # noqa: E402

#: 有教师种子的项目 / 只走自动提炼的项目
SEEDED_PROJECT = "sample_projects/lab_safety_assistant"
AUTO_PROJECT = "validation/python_dotenv"

SEEDED_PROJECT_ID = "lab_safety_assistant"
SEEDED_TASK_ID = "dt_lab_safety_assistant_L2_module_split"

#: 学生视图里**绝对不允许**出现的键（README §10.5 字段可见性矩阵）
TEACHER_ONLY_KEYS = (
    "must_have",
    "required_relations",
    "forbidden_merges",
    "acceptable_alternatives",
    "rubric_weights",
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

    @property
    def total(self) -> int:
        return len(self.rows)


def module(module_id: str, name: str, **overrides: Any) -> Dict[str, Any]:
    """一个学生模块（字段与 ``design_submission.json`` 契约一致）。"""
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


def codes_of(report: Dict[str, Any]) -> List[str]:
    """报告里出现过的全部信号码（顶层 ``signals``）。"""
    return [str(item.get("code")) for item in report.get("signals") or []]


def graph_of(project: str) -> Dict[str, Any]:
    source_dir = (REPO_ROOT / project).resolve()
    result = ProjectAnalyzer().analyze(str(source_dir))
    return result.to_dict().get("business_graph") or {}


# ---------------------------------------------------------------------------
# 两份真实提交
# ---------------------------------------------------------------------------

def conforming_submission(task: Dict[str, Any]) -> Dict[str, Any]:
    """合规设计：每项必备能力一个模块，连成链，并写上两个必备边界。

    链的方向是 ``m(i+1) → m(i)``，与 must_have 的**推荐顺序**一致 ——
    所以种子里的两条必备依赖（提交预约 → 冲突检测、借还 → 状态更新）
    都能被这种规范设计满足。边界措辞按种子里的 ``required_edge_cases`` 原样写出。
    """
    must_have = task.get("must_have") or []
    modules: List[Dict[str, Any]] = []
    for index, item in enumerate(must_have):
        name = str(item.get("name_cn") or "")
        exceptions = ["入参为空时拒绝并报错"]
        business_rules = ["必须校验入参是否为空"]
        if str(item.get("key")) == "mh_check_conflict":
            # 必备边界之一：时间冲突
            exceptions.append("同一实验室同一时段重复预约属于时间冲突，直接拒绝提交")
        if str(item.get("key")) == "mh_transition_equipment":
            # 必备边界之二：重复借用
            business_rules.append("设备不在可用状态时不得再次借出，避免重复借用")
        modules.append(
            module(
                f"m{index + 1}",
                name,
                objective=f"负责{name}这件事",
                inputs=["入参甲"],
                outputs=["出参乙"],
                does_not=["不负责其他模块的职责"],
                business_rules=business_rules,
                state_changes=["写入状态字段甲"],
                exceptions=exceptions,
            )
        )
    relations = [
        {"from": f"m{index + 1}", "to": f"m{index}", "type": "uses"} for index in range(1, len(modules))
    ]
    return {
        "submission_id": "sub_seed_ok",
        "task_id": task.get("task_id") or "",
        "iteration": 1,
        "modules": modules,
        "relations": relations,
        "design_rationale": (
            "我把必备能力按职责拆成模块：每项能力只由一个模块承担，相邻模块之间是依赖关系，"
            "冲突检测在提交之前被调用，设备状态回写发生在借还之后，"
            "每个模块都写了入参校验与拒绝规则。"
        ),
    }


def violating_submission(task: Dict[str, Any]) -> Dict[str, Any]:
    """违规设计：把该分开的能力合并，且完全不写那两个必备边界。

    - 「预约审批」与「用户身份与权限校验」合并 → 触发 ``ALT_FORBIDDEN_MERGE``；
    - 「提交预约申请」与「预约冲突检测」合并 → 必备依赖无从成立
      （同一模块之间没有边）→ 触发 ``DEP_REQUIRED_MISSING``；
    - 「设备借出与归还」与「设备状态更新」合并 → 第二条必备依赖同样不成立；
    - 全文不出现「时间冲突」「重复借用」→ 触发 ``EDGE_REQUIRED_MISSING``。

    模块名是**故意的**：它必须能让两项能力都匹配到同一个模块（靠 ``aliases``
    的子串命中），否则禁止合并项根本无从判定 —— 这条细节在
    ``alternatives.py`` 里写明了（只认匹配结果，不认模块显示名）。
    """
    modules = [
        module(
            "m1",
            "预约审批与权限校验",
            objective="既做审批，也顺手做权限校验",
            business_rules=["必须校验入参是否为空"],
            exceptions=["入参为空时拒绝并报错"],
        ),
        module(
            "m2",
            "提交预约申请与预约冲突检测",
            objective="提交和冲突检测放在一起做",
            business_rules=["必须校验入参是否为空"],
            exceptions=["入参为空时拒绝并报错"],
        ),
        module(
            "m3",
            "设备借出与归还与设备状态更新",
            objective="借还的时候顺便把状态改掉",
            business_rules=["必须校验入参是否为空"],
            exceptions=["入参为空时拒绝并报错"],
        ),
        module("m4", "取消预约", objective="负责取消预约", exceptions=["入参为空时拒绝"]),
        module("m5", "设备入库", objective="负责设备入库", exceptions=["入参为空时拒绝"]),
        module("m6", "安全检查执行", objective="负责执行安全检查", exceptions=["入参为空时拒绝"]),
        module("m7", "隐患整改与关闭", objective="负责隐患整改与关闭", exceptions=["入参为空时拒绝"]),
    ]
    return {
        "submission_id": "sub_seed_bad",
        "task_id": task.get("task_id") or "",
        "iteration": 1,
        "modules": modules,
        "relations": [
            {"from": "m2", "to": "m1", "type": "uses"},
            {"from": "m3", "to": "m2", "type": "uses"},
        ],
        "design_rationale": (
            "我把关系近的能力都合并在一起，模块数量少一些更好维护；"
            "每个模块都写了入参校验，入参为空就直接拒绝。"
        ),
    }


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def run(checker: Checker, verbose: bool) -> None:
    print("· 教师种子（优先级 3.5）")

    graph = graph_of(SEEDED_PROJECT)
    checker.check("图谱可构建", bool(graph), str(graph.get("project_id") or ""))

    # ---- 1) 种子被读到 ----
    listing = tb.list_design_tasks(graph)
    tasks = listing.get("tasks") or []
    task = tb.resolve_task(graph, listing.get("default_task_id"))
    checker.check("默认任务取到的是种子任务", bool(task) and task.get("task_id") == SEEDED_TASK_ID,
                  str(task and task.get("task_id")))
    if not task:
        return

    checker.check(
        "种子生效：来源 = teacher_seed",
        task.get("must_have_source") == "teacher_seed",
        str(task.get("must_have_source")),
    )
    checker.check(
        "种子生效：needs_review = false（页面上不再出现待教师确认徽章）",
        task.get("needs_review") is False and task.get("must_have_confirmed") is True,
        f"needs_review={task.get('needs_review')} confirmed={task.get('must_have_confirmed')}",
    )
    checker.check(
        "种子存在时不再生成自动任务（任务数由 3 变 1）",
        len(tasks) == 1,
        f"{len(tasks)} 个任务：{[t.get('task_id') for t in tasks]}",
    )

    # ---- 2) 清单的硬约束 ----
    must_have = task.get("must_have") or []
    pairs = [(str(item.get("verb_class")), str(item.get("entity"))) for item in must_have]
    checker.check("must_have 非空", bool(must_have), f"{len(must_have)} 项")
    checker.check("must_have 的 (verb_class, entity) 两两不重复", len(set(pairs)) == len(pairs),
                  json.dumps(sorted(set(p for p in pairs if pairs.count(p) > 1)), ensure_ascii=False))
    checker.check(
        "每项必备能力都有中文名与簇（否则反馈与职责判定会退化）",
        all(item.get("name_cn") and item.get("cluster") for item in must_have),
        "",
    )

    # ---- 3) 三份清单齐全（优先级 3.5 的交付物）----
    relations = task.get("required_relations") or []
    edge_cases = task.get("required_edge_cases") or []
    alternatives = task.get("acceptable_alternatives") or []
    forbidden = task.get("forbidden_merges") or []
    checker.check("必备依赖 2 条", len(relations) == 2, str(len(relations)))
    checker.check("必备边界 2 个", len(edge_cases) == 2, json.dumps(edge_cases, ensure_ascii=False))
    checker.check("可接受替代结构 2 条", len(alternatives) == 2, str(len(alternatives)))
    checker.check("禁止合并项 1 条", len(forbidden) == 1, str(len(forbidden)))

    keys = {str(item.get("key")) for item in must_have}
    referenced = set()
    for item in relations:
        referenced.add(str(item.get("from_key")))
        referenced.add(str(item.get("to_key")))
    for item in forbidden:
        referenced.add(str(item.get("a")))
        referenced.add(str(item.get("b")))
    for item in alternatives:
        referenced.update(str(key) for key in (item.get("merge_keys") or []))
        referenced.update(str(key) for key in (item.get("separate_keys") or []))
    checker.check(
        "三份清单引用的 key 全部存在于 must_have（没有指向不存在能力的悬空 key）",
        referenced <= keys,
        json.dumps(sorted(referenced - keys), ensure_ascii=False),
    )
    checker.check(
        "必备依赖引用的两项能力没有被同时列入「可接受合并」"
        "（否则必备依赖与替代结构会互相打架）",
        all(
            {str(item.get("from_key")), str(item.get("to_key"))}
            != {str(alt.get("merge_keys") or [None, None])[0], str(alt.get("merge_keys") or [None, None])[-1]}
            for item in relations
            for alt in alternatives
            if len(alt.get("merge_keys") or []) == 2
        ),
        "",
    )

    # ---- 4) 学生视图不泄漏 ----
    student = tb.build_design_task(graph, task["task_id"], teacher_mode=False)
    leaked = [key for key in TEACHER_ONLY_KEYS if key in student]
    checker.check("学生视图不含教师字段", not leaked, str(leaked))
    brief_text = json.dumps(student.get("brief") or {}, ensure_ascii=False)
    leaked_names = [str(item.get("name_cn")) for item in must_have if str(item.get("name_cn")) in brief_text]
    checker.check(
        "简报里没有列出必备能力清单（brief_includes = counts）",
        not leaked_names,
        json.dumps(leaked_names, ensure_ascii=False),
    )

    # ---- 5) 合规设计不被误判 ----
    good = rubric_mod.evaluate_design(graph, task, conforming_submission(task))
    good_codes = codes_of(good)
    checker.check("合规设计：命中可接受替代结构（ALT_ACCEPTED）", "ALT_ACCEPTED" in good_codes,
                  json.dumps([c for c in good_codes if c.startswith("ALT_")], ensure_ascii=False))
    checker.check("合规设计：必备依赖全部命中（无 DEP_REQUIRED_MISSING）",
                  "DEP_REQUIRED_MISSING" not in good_codes, json.dumps(good_codes, ensure_ascii=False))
    checker.check("合规设计：必备边界全部命中（无 EDGE_REQUIRED_MISSING）",
                  "EDGE_REQUIRED_MISSING" not in good_codes, json.dumps(good_codes, ensure_ascii=False))
    checker.check("合规设计：覆盖度满分（每项能力都有承担者）",
                  next((d.get("score") for d in good["dimensions"] if d["key"] == "coverage"), None) == 100.0,
                  str(next((d.get("score") for d in good["dimensions"] if d["key"] == "coverage"), None)))
    dep_dim = next((d for d in good["dimensions"] if d["key"] == "dependency"), {})
    checker.check("合规设计：依赖维度是「已评估」而不是未评估",
                  dep_dim.get("status") == "evaluated", str(dep_dim.get("status")))

    # ---- 6) 违规设计能被抓住（优先级 3.5 的验收口径）----
    bad = rubric_mod.evaluate_design(graph, task, violating_submission(task))
    bad_codes = codes_of(bad)
    checker.check("违规设计：必备依赖未命中被抓住（DEP_REQUIRED_MISSING）",
                  "DEP_REQUIRED_MISSING" in bad_codes, json.dumps(bad_codes, ensure_ascii=False))
    checker.check("违规设计：必备边界未命中被抓住（EDGE_REQUIRED_MISSING）",
                  "EDGE_REQUIRED_MISSING" in bad_codes, json.dumps(bad_codes, ensure_ascii=False))
    checker.check("违规设计：禁止合并被抓住（ALT_FORBIDDEN_MERGE）",
                  "ALT_FORBIDDEN_MERGE" in bad_codes, json.dumps(bad_codes, ensure_ascii=False))
    checker.check("违规设计：替代结构判定可用（available = true，不是「没判」）",
                  (bad.get("alternatives") or {}).get("available") is True,
                  json.dumps((bad.get("alternatives") or {}).get("available"), ensure_ascii=False))

    # 反馈文案必须能渲染出来（信号码 → 中文模板的纯函数）。
    # 注意报告的形状：`issues` 是**逐维**的，顶层只有 `submission_issues` /
    # `alternatives_issues`（rubric.py:1087-1111），不存在一个顶层 `issues`。
    dim_issues = {
        str(item.get("key")): [str(line) for line in (item.get("issues") or [])]
        for item in bad.get("dimensions") or []
    }
    checker.check(
        "违规设计的必备依赖扣分渲染成了中文 issues",
        any("必备依赖" in line for line in dim_issues.get("dependency") or []),
        json.dumps(dim_issues.get("dependency") or [], ensure_ascii=False)[:200],
    )
    checker.check(
        "违规设计的必备边界扣分渲染成了中文 issues",
        any("必备边界" in line for line in dim_issues.get("edge_case") or []),
        json.dumps(dim_issues.get("edge_case") or [], ensure_ascii=False)[:200],
    )
    checker.check(
        "违规设计的禁止合并渲染成了中文 issues",
        bool(bad.get("alternatives_issues")),
        json.dumps((bad.get("alternatives_issues") or [])[:1], ensure_ascii=False)[:200],
    )
    rendered_lines = [line for lines in dim_issues.values() for line in lines]
    rendered_lines += [str(line) for line in (bad.get("alternatives_issues") or [])]
    checker.check(
        "反馈文案里没有残留未替换的模板占位符 {xxx}",
        not [line for line in rendered_lines if "{" in line or "}" in line],
        json.dumps([line for line in rendered_lines if "{" in line or "}" in line][:1], ensure_ascii=False)[:200],
    )
    # 本轮修掉的一个真问题：禁止合并的文案早先把种子里的内部 key（mh_*）直接印给学生
    # （StageDesign.vue 的「禁止合并」列表也用的是同一个字段）——README §6.2 明令不许。
    checker.check(
        "学生可见文案里不出现种子内部 key（mh_*）",
        not [line for line in rendered_lines if "mh_" in line],
        json.dumps([line for line in rendered_lines if "mh_" in line][:1], ensure_ascii=False)[:200],
    )
    violations = (bad.get("alternatives") or {}).get("violations") or []
    checker.check(
        "禁止合并的 violations 同时给出中文显示名与原始 key（显示与排查都要）",
        bool(violations)
        and all(item.get("a") and item.get("b") and item.get("a_key") and item.get("b_key") for item in violations)
        and all("mh_" not in str(item.get("a")) for item in violations),
        json.dumps(violations[:1], ensure_ascii=False)[:200],
    )

    # ---- 7) 种子只影响有种子那个项目 ----
    auto_graph = graph_of(AUTO_PROJECT)
    auto_task = tb.resolve_task(auto_graph, None)
    checker.check(
        f"{AUTO_PROJECT}：仍然走自动提炼（auto_from_project + needs_review）",
        bool(auto_task)
        and auto_task.get("must_have_source") == "auto_from_project"
        and auto_task.get("needs_review") is True,
        f"{auto_task and auto_task.get('must_have_source')} / {auto_task and auto_task.get('needs_review')}",
    )

    # ---- 8) 确定性 ----
    sig_a = rubric_mod.report_signature(rubric_mod.evaluate_design(graph, task, conforming_submission(task)))
    sig_b = rubric_mod.report_signature(rubric_mod.evaluate_design(graph, task, conforming_submission(task)))
    checker.check("确定性：同一份提交两次评审一致", sig_a == sig_b, "")

    if verbose:
        print(f"    · 种子任务 {task['task_id']}：{len(must_have)} 项必备能力 / "
              f"{len(relations)} 条依赖 / {len(edge_cases)} 个边界 / {len(alternatives)} 条替代结构")
        print(f"    · 合规设计总分 {good.get('overall_score')}；违规设计总分 {bad.get('overall_score')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="教师种子（优先级 3.5）验收测试")
    parser.add_argument("--verbose", action="store_true", help="逐项打印结果")
    args = parser.parse_args()

    checker = Checker(verbose=args.verbose)
    run(checker, args.verbose)

    print(f"\n教师种子验收：{checker.total - checker.failed}/{checker.total} 项通过")
    if checker.failed:
        print("失败项：")
        for name, ok, detail in checker.rows:
            if not ok:
                print(f"  - {name}" + (f"  — {detail}" if detail else ""))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
