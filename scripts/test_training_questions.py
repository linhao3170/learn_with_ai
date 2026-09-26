"""
第 2 / 3 / 4 关「一关多题」出题覆盖测试（README 优先级 4，含二轮扩展）

改造前是什么样
--------------
- 第 2 关只问**核心度最高的那一个**业务模块（`selected[0]` 那次修复之后依然如此），
  其余业务模块的职责学生一题都练不到；
- 第 3 关只问 `pick_primary_flow` 挑出的**那一条**流程；
- 第 4 关只问 `top_implementations[0]` **那一条**关键实现。

现在是什么样（优先级 4 一轮修第 2 关 / 二轮修第 3、4 关）
----------------------------------------------------------
三关都是「每个够格的对象各出一道」，凑不出就**不出这一题**，不编造：

- 第 2 关：够格 = ① 有非空业务语义文本；② 能从**其他业务模块**里凑出 3 个互不相同、
  且不等于正确答案的干扰项；
- 第 3 关：按 `flow_filter.sort_flows_business_first` 的**唯一排序口径**逐条流程出题；
  只有整个项目一条业务流都没有时才退回生命周期流程（拿初始化流程当核心业务教
  是教学性错误）。上限 `_MAX_LEVEL3_QUESTIONS`；
- 第 4 关：逐条关键实现出题，上限 `_MAX_LEVEL4_QUESTIONS`（比 2/3 关小）。

WO-03 一轮改了两处（都不放宽纪律，只把"没做的"变成"看得见的"）
--------------------------------------------------------------
① **第 2 关"为什么不出题"必须能查**：出题结果与原因由引擎的
   `TrainingGenerator.level2_report()` / `level2_summary()` 给出（原因码见引擎里的
   `LEVEL2_*` 常量）。`python_dotenv` 仍然**一道第 2 关题都不出** ——
   本测试不把它"修好"，而是断言它的退化是**有理由、有数字**的：
   全项目不同的非空业务语义文本只有 1 种，凑不出 3 个真实干扰项；
   另一条候选模块则根本没有业务语义文本。**不编造干扰项**。
② **第 4 关干扰项不再是写死的 4 句反模式**，而是由**目标方法自己的已核实事实**
   派生（`derive_deep_distractors()`）：每条干扰项都必须与目标方法的一项真实事实
   **相反**（校验 / 提前返回 / 异常 / 状态写入 / 循环 / 分支），因此对本方法
   **可证明是错的**。事实不足 3 项的实现**跳过不出题**（本测试断言这条门槛）。
   ⚠️ 干扰项**句式仍是固定文案**，所以 `source` 仍必须是 `template` ——
   本测试专门断言它**没有**被改成 `data_driven`（不许为了让文档好看而改标口径）。

测什么
------
1. **覆盖**：够格的对象各出一道，且各题问的是**不同**的对象（靠正确项文本两两不同断言）；
2. **不编造**：第 2 关每个选项都必须等于本项目某个模块的业务语义文本；
   第 3 关每个选项都必须由本项目的**真实流程步骤标签**拼成；
   第 4 关每个干扰项都必须能回指到目标方法的一项**真实存在**的事实字段；
3. **不用 CRUD 标签当职责**（P0-05）：`新增/创建操作` 这类内部信号不进选项与讲解；
4. **可作答**：4 个选项 / 文本互不相同 / 有且只有一个正确项；
   正确答案与答案表（`answer_key()`）**逐题按下标**一致（判题靠下标，错位就是判错分）；
5. **标题可区分**：前端把标题当关卡标签与雷达维度名，重名就分不清哪一关是哪一题；
6. **确定性**：同一份数据两次生成逐字节一致；
7. **上限与顺序**：三关各自的上限都生效；关卡顺序恒为 1 → 2… → 3… → 4…；
8. **只问业务模块**：编排 / 支撑模块永远不作为第 2 关主体（与第 1 关口径一致）；
9. **第 4 关的反套路断言**：干扰项逐题轮换（至少两种不同组合），
   且证据必须是项目内相对路径；
10. **退化必须可解释**：凑不出数据时**不出题**，且原因码 + 真实数字能被取到
    （合成用例里用两条对照把"没文本"与"文本不够"分开断言 ——
    如果引擎把两种原因混成一个，其中一条必 FAIL）。

用法
----
    python scripts/test_training_questions.py
    python scripts/test_training_questions.py --project sample_projects/lab_safety_assistant --verbose
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # pragma: no cover
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from engine.project_analyzer import ProjectAnalyzer  # noqa: E402
from engine.project_analyzer.module_analyzer import ModuleInfo  # noqa: E402
from engine.project_analyzer.training_generator import (  # noqa: E402
    _CRUD_LABELS,
    _DISTRACTOR_COUNT,
    _MAX_LEVEL2_QUESTIONS,
    _MAX_LEVEL3_QUESTIONS,
    _MAX_LEVEL4_QUESTIONS,
    LEVEL2_ASKED,
    LEVEL2_DISTRACTOR_POOL_TOO_SMALL,
    LEVEL2_NO_BUSINESS_TEXT,
    LEVEL2_OVER_LIMIT,
    TrainingGenerator,
    _business_modules,
    _business_text,
    _step_label,
    derive_deep_distractors,
)
from engine.flow_filter import is_lifecycle_flow, sort_flows_business_first  # noqa: E402

DEFAULT_PROJECTS = [
    "sample_projects/lab_safety_assistant",
    "validation/python_dotenv",
]


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


# ---------------------------------------------------------------------------
# 从**真实分析结果**重建 ModuleInfo（只用契约里已有的字段）
# ---------------------------------------------------------------------------

def modules_from_payload(payload: Dict[str, Any]) -> List[ModuleInfo]:
    """把 ``ProjectAnalysisResult.to_dict()`` 里的 modules 还原成 ModuleInfo。

    为什么要还原：判"够格"的口径（`_role_of` / `_business_text`）是引擎里**唯一**的实现，
    测试必须复用它，而不是在这里另写一份判断。
    """
    out: List[ModuleInfo] = []
    for mod in payload.get("modules", []) or []:
        out.append(
            ModuleInfo(
                module_id=str(mod.get("module_id") or ""),
                name=str(mod.get("name") or ""),
                module_type=str(mod.get("type") or ""),
                description=str(mod.get("description") or ""),
                key_responsibilities=list(mod.get("responsibilities") or []),
                core_score=float(mod.get("core_score") or 0.0),
                method_count=int(mod.get("method_count") or 0),
                class_count=int(mod.get("class_count") or 0),
            )
        )
    return out


def level2_questions(questions: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [q for q in questions if q.get("level") == 2]


def level_of(questions: Sequence[Dict[str, Any]], level: int) -> List[Dict[str, Any]]:
    return [q for q in questions if q.get("level") == level]


def _option_texts(question: Dict[str, Any]) -> List[str]:
    return [str(o.get("text") or "") for o in question.get("options", [])]


def _answer_texts(
    questions: Sequence[Dict[str, Any]], answer_key: Dict[str, Any], index: int
) -> List[str]:
    """按**整份题目列表里的下标**从答案表取出正确项文本（判题按下标，错位就是判错分）。"""
    question = questions[index]
    answers = {str(a) for a in ((answer_key.get(str(index)) or {}).get("answers")) or []}
    return [str(o.get("text") or "") for o in question.get("options", []) if str(o.get("id")) in answers]


def correct_texts(
    questions: Sequence[Dict[str, Any]], answer_key: Dict[str, Any]
) -> List[str]:
    """按答案表取出每道第 2 关题的**正确选项文本**。

    答案表用下标作键（``str(index)``），所以这里必须用题目在**整个列表**里的下标去查 ——
    这正是"下标错位就会判错分"的那条链路。
    """
    out: List[str] = []
    for index, question in enumerate(questions):
        if question.get("level") != 2:
            continue
        answers = ((answer_key.get(str(index)) or {}).get("answers")) or []
        options = {o.get("id"): str(o.get("text") or "") for o in question.get("options", [])}
        for option_id in answers:
            out.append(options.get(str(option_id), ""))
    return out


# ---------------------------------------------------------------------------
# 通用断言（真实项目与合成用例共用）
# ---------------------------------------------------------------------------

def assert_questions_wellformed(
    name: str,
    questions: Sequence[Dict[str, Any]],
    answer_key: Dict[str, Any],
    real_texts: set,
    checker: Checker,
) -> None:
    """第 2 关每道题的结构性断言。``real_texts`` = 本项目全部模块的业务语义文本集合。"""
    lv2 = level2_questions(questions)

    checker.check(
        f"{name} 第 2 关的答案表下标与题目一一对应",
        len(answer_key) == len(questions)
        and all(str(i) in answer_key for i in range(len(questions))),
        f"题目 {len(questions)} 道 / 答案表 {len(answer_key)} 条",
    )

    bad_shape: List[str] = []
    bad_answer: List[str] = []
    fabricated: List[str] = []
    crud_leak: List[str] = []
    for index, question in enumerate(questions):
        if question.get("level") != 2:
            continue
        options = question.get("options", [])
        texts = [str(o.get("text") or "") for o in options]
        answers = ((answer_key.get(str(index)) or {}).get("answers")) or []
        correct_option_texts = [
            str(o.get("text") or "") for o in options if str(o.get("id")) in {str(a) for a in answers}
        ]
        if (
            question.get("question_type") != "responsibility_match"
            or len(options) != 4
            or len(set(texts)) != 4
            or any(not t for t in texts)
        ):
            bad_shape.append(f"#{index}")
        if len(correct_option_texts) != 1 or len(answers) != 1:
            bad_answer.append(f"#{index} answers={answers}")
        for text in texts:
            if text not in real_texts:
                fabricated.append(f"#{index} {text[:24]!r}")
            if text in _CRUD_LABELS:
                crud_leak.append(f"#{index} {text}")
        explanation = str(question.get("explanation") or "")
        if any(label in explanation for label in _CRUD_LABELS):
            crud_leak.append(f"#{index} explanation")

    checker.check(
        f"{name} 每道第 2 关题都是 4 选 1、选项互不相同",
        not bad_shape,
        "、".join(bad_shape) if bad_shape else f"{len(lv2)} 道题全部合规",
    )
    checker.check(
        f"{name} 每道第 2 关题有且只有一个正确项，且与答案表一致",
        not bad_answer,
        "、".join(bad_answer) if bad_answer else f"{len(lv2)} 道题正确答案都能逐题对上",
    )
    checker.check(
        f"{name} 第 2 关的选项全部来自本项目真实模块（不编造干扰项）",
        not fabricated,
        "、".join(fabricated) if fabricated else f"{len(lv2) * 4} 个选项全部可回指到模块文本",
    )
    checker.check(
        f"{name} 第 2 关没有把 CRUD 分类标签当职责（P0-05）",
        not crud_leak,
        "、".join(crud_leak) if crud_leak else "选项与讲解里都没有出现",
    )


# ---------------------------------------------------------------------------
# 真实项目
# ---------------------------------------------------------------------------

def run_project(project: str, checker: Checker, verbose: bool) -> None:
    name = Path(project).name
    print(f"\n=== 校验对象：{project} ===")
    analyzer = ProjectAnalyzer()
    result = analyzer.analyze(project)
    payload = result.to_dict()
    questions = (payload.get("training") or {}).get("questions", []) or []
    answer_key = result.training_answer_key
    modules = modules_from_payload(payload)

    business = _business_modules(modules)
    texts = {m.module_id: _business_text(m) for m in business}
    non_empty = [mid for mid, text in texts.items() if text]
    distinct_texts = {texts[mid] for mid in non_empty}
    real_texts = set(texts.values())

    print(
        f"    模块 {len(modules)} 个 / 业务模块 {len(business)} 个 / "
        f"有业务语义文本的 {len(non_empty)} 个（去重 {len(distinct_texts)} 种）"
    )
    print(
        f"    题目 {len(questions)} 道（第 2 关 {len(level2_questions(questions))} 道）"
    )

    # ---- 0) 第 2 关"为什么不出题"：如实打印引擎记录的原因（WO-03 一轮）----
    generator = analyzer.training_generator
    report = generator.level2_report()
    print(f"    第 2 关出题结论：{generator.level2_summary()}")
    for item in report:
        print(
            f"      - {item['module_name']} [id={item['module_id']}]"
            f" asked={item['asked']} reason={item['reason']}"
            f" 干扰项 {item['distractors_found']}/{_DISTRACTOR_COUNT}"
            f"（全项目不同职责文本 {item['distinct_texts_in_project']} 种）"
        )

    lv2 = level2_questions(questions)

    # ---- 1) 覆盖：文本够多的项目里，每个有文本的业务模块都被问到 ----
    if len(distinct_texts) >= 4:
        expected = min(len(non_empty), _MAX_LEVEL2_QUESTIONS)
        checker.check(
            f"{name} 每个够格的业务模块各出一道第 2 关题",
            len(lv2) == expected,
            f"够格 {len(non_empty)} 个 → 出题 {len(lv2)} 道（上限 {_MAX_LEVEL2_QUESTIONS}）",
        )
        covered = correct_texts(questions, answer_key)
        checker.check(
            f"{name} 第 2 关问到的是**不同**的模块（不是同一个模块问四遍）",
            len(covered) == len(set(covered)) and len(covered) >= 2,
            f"正确文本 {len(covered)} 条 / 去重 {len(set(covered))} 条",
        )
    else:
        checker.check(
            f"{name} 业务语义文本不足 4 种时不出第 2 关题（诚实退化）",
            not lv2,
            f"去重 {len(distinct_texts)} 种 → 出题 {len(lv2)} 道",
        )

    # ---- 1b) WO-03 一轮：退化必须是**可解释的**，而且理由要与真实数据对得上 ----
    #  ① 每个业务模块都有一条结论，原因码必须来自引擎的枚举（不许是随手写的字符串）；
    #  ② 结论与"实际出题数"必须自洽（出的题 == 标记为 asked 的数量）；
    #  ③ 说"凑不出干扰项"的模块，必须真的凑不出：全项目不同的非空职责文本
    #     连"正确答案 1 条 + 干扰项 _DISTRACTOR_COUNT 条"都凑不满 ——
    #     这条把"我们没编造"变成了**可验证的数字关系**，而不是一句声明。
    valid_reasons = {
        LEVEL2_ASKED,
        LEVEL2_OVER_LIMIT,
        LEVEL2_NO_BUSINESS_TEXT,
        LEVEL2_DISTRACTOR_POOL_TOO_SMALL,
    }
    checker.check(
        f"{name} 第 2 关每个业务模块都有出题结论、原因码来自引擎枚举",
        bool(report)
        and all(str(item.get("reason") or "") in valid_reasons for item in report)
        and len(report) == len(business),
        f"结论 {len(report)} 条 / 业务模块 {len(business)} 个；"
        f"原因码 {sorted({str(i.get('reason')) for i in report})}",
    )
    checker.check(
        f"{name} 第 2 关的结论与实际出题数自洽（asked 几条就出几道）",
        sum(1 for item in report if item.get("asked")) == len(lv2),
        f"asked={sum(1 for item in report if item.get('asked'))} / 实际 {len(lv2)} 道",
    )
    too_small = [
        item for item in report if item.get("reason") == LEVEL2_DISTRACTOR_POOL_TOO_SMALL
    ]
    if too_small:
        checker.check(
            f"{name} 说「凑不出干扰项」的模块，数字上确实凑不出（不编造而不是漏做）",
            len(distinct_texts) < 1 + _DISTRACTOR_COUNT
            and all(
                int(item.get("distractors_found") or 0) < _DISTRACTOR_COUNT
                for item in too_small
            ),
            f"全项目不同职责文本 {len(distinct_texts)} 种 < 1 答案 + "
            f"{_DISTRACTOR_COUNT} 干扰项 = {1 + _DISTRACTOR_COUNT} 种 → "
            f"最多只能凑出 {len(distinct_texts) - 1} 个干扰项",
        )

    # ---- 2) 前端把标题当关卡名与雷达维度名，因此不许重名 ----
    titles = [str(q.get("title") or "") for q in questions]
    checker.check(
        f"{name} 题目标题互不重复（关卡标签 / 雷达维度名）",
        len(titles) == len(set(titles)),
        f"{len(titles)} 个标题 / 去重 {len(set(titles))} 个",
    )

    # ---- 3) 关卡顺序：第 2 关必须夹在第 1 关与第 3 关之间（判题靠下标）----
    levels = [int(q.get("level") or 0) for q in questions]
    checker.check(
        f"{name} 关卡顺序为 1 → 2… → 3 → 4（判题按下标，顺序不能乱）",
        levels == sorted(levels) and (not levels or levels[0] == 1),
        f"levels={levels}",
    )

    # ---- 4) 编排 / 支撑模块不作为第 2 关主体 ----
    business_texts = {texts[m.module_id] for m in business if texts.get(m.module_id)}
    covered = correct_texts(questions, answer_key)
    checker.check(
        f"{name} 第 2 关只问业务模块，不问编排 / 支撑模块",
        all(text in business_texts for text in covered),
        "、".join(text[:20] for text in covered if text not in business_texts) or "全部来自业务模块",
    )

    # ---- 5) 通用结构断言 ----
    assert_questions_wellformed(name, questions, answer_key, real_texts, checker)

    # ---- 6) 第 3 关：每条够格的业务流程各一道（优先级 4 二轮）----
    # 流程取自契约的 `core_flows`（**就是训练生成器实际拿到的那一份**，
    # 不是 deep_analysis.business_flows —— 那是另一个产物，别混）。
    assert_level3(name, questions, answer_key, payload.get("core_flows") or [], checker)

    # ---- 7) 第 4 关：每条够格的关键实现各一道 + 干扰项由真实事实派生（WO-03 一轮）----
    ki_bundle = (payload.get("deep_analysis") or {}).get("key_implementations") or {}
    # 契约里的字段名是 `method`（`KeyImplementation.to_dict()`），不是 `method_name`
    ki_payloads = [
        item for item in (ki_bundle.get("implementations") or []) if isinstance(item, dict)
    ]
    assert_level4(name, questions, answer_key, ki_payloads, checker)


# ---------------------------------------------------------------------------
# 第 3 关：流程推演（每条够格的流程一道）
# ---------------------------------------------------------------------------

def _flow_is_lifecycle(flow: Dict[str, Any]) -> bool:
    """复用引擎的**唯一判定**（``flow_filter.is_lifecycle_flow``），不在这里另写一份。"""
    return is_lifecycle_flow(_FlowLike(flow))


class _FlowLike:
    """把契约里的流程 dict 包成 ``flow_filter`` 能读的形状。

    ``flow_filter`` 只读 ``flow_id`` / ``name`` / ``description`` / ``steps[].method``
    这几个字段，这里原样透传，避免在测试里复制一套生命周期词表。
    """

    def __init__(self, payload: Dict[str, Any]) -> None:
        self.flow_id = str(payload.get("flow_id") or "")
        self.name = str(payload.get("name") or "")
        self.description = str(payload.get("description") or "")
        self.steps = list(payload.get("steps") or [])


def assert_level3(
    name: str,
    questions: Sequence[Dict[str, Any]],
    answer_key: Dict[str, Any],
    flows: Sequence[Dict[str, Any]],
    checker: Checker,
) -> None:
    """第 3 关的结构性断言。

    ``flows`` = 契约里的业务流程。**判定一律复用引擎自己的实现**
    （``sort_flows_business_first`` / ``is_lifecycle_flow`` / ``_step_label``），
    测试里不重写一份"什么算够格"。
    """
    lv3 = level_of(questions, 3)
    ordered = sort_flows_business_first([_FlowLike(f) for f in flows])
    business = [f for f in ordered if not is_lifecycle_flow(f)]

    # 够格 = 至少 2 步（1 步的流程构不成"顺序"或"下一步"两种题型里的任何一种）
    eligible = [f for f in (business or ordered) if len(getattr(f, "steps", []) or []) >= 2]
    upper = min(len(eligible), _MAX_LEVEL3_QUESTIONS)
    checker.check(
        f"{name} 第 3 关：够格的业务流程各出一道（上限内）",
        (upper == 0 and not lv3) or (1 <= len(lv3) <= upper),
        f"够格流程 {len(eligible)} 条（业务流 {len(business)} / 共 {len(ordered)}）→ "
        f"出题 {len(lv3)} 道（上限 {_MAX_LEVEL3_QUESTIONS}）",
    )

    # 生命周期流程绝不当核心业务流教：有业务流时，每道题问的都必须是业务流
    if business and lv3:
        asked = [str(q.get("title") or "").split("·")[-1] for q in lv3]
        business_names = {str(getattr(f, "name", "")) for f in business}
        checker.check(
            f"{name} 第 3 关：有业务流时绝不把生命周期流程当核心业务流问",
            all(name_ in business_names for name_ in asked),
            "、".join(a for a in asked if a not in business_names) or f"问到的都是业务流：{'、'.join(asked)}",
        )

    # 每道题：4 选 1 / 选项互不相同 / 正确项与答案表一致
    bad_shape: List[str] = []
    bad_answer: List[str] = []
    all_labels = {
        _step_label(step)
        for flow in ordered
        for step in (getattr(flow, "steps", []) or [])
        if _step_label(step)
    }
    fabricated: List[str] = []
    for question in lv3:
        index = questions.index(question)
        texts = _option_texts(question)
        if (
            question.get("question_type") not in ("flow_ordering", "flow_next_step")
            or len(texts) != 4
            or len(set(texts)) != 4
            or any(not t for t in texts)
        ):
            bad_shape.append(f"#{index}")
        correct = _answer_texts(questions, answer_key, index)
        if len(correct) != 1:
            bad_answer.append(f"#{index} correct={correct}")
        for text in texts:
            # 排序题的正确项是「步骤 → 步骤 → 步骤」，拆开每一段都必须是真实步骤标签；
            # next-step 题的选项本身就是单个步骤标签。两种都要能回指到真实数据。
            parts = [p.strip() for p in text.split("→")] if "→" in text else [text]
            if any(part and part not in all_labels for part in parts):
                fabricated.append(f"#{index} {text[:28]!r}")
    checker.check(
        f"{name} 第 3 关每题都是 4 选 1、选项互不相同",
        not bad_shape,
        "、".join(bad_shape) if bad_shape else f"{len(lv3)} 道题全部合规",
    )
    checker.check(
        f"{name} 第 3 关每道题有且只有一个正确项，且与答案表一致",
        not bad_answer,
        "、".join(bad_answer) if bad_answer else f"{len(lv3)} 道题正确答案都能逐题对上",
    )
    checker.check(
        f"{name} 第 3 关的选项全部由本项目真实流程步骤拼成（不编造）",
        not fabricated,
        "、".join(fabricated) if fabricated else f"{len(lv3) * 4} 个选项全部可回指到流程步骤",
    )


# ---------------------------------------------------------------------------
# 第 4 关：关键实现（每条够格实现一道 + 干扰项由真实事实派生）
# ---------------------------------------------------------------------------

#: 规则 → 它必须与之相反的那项**已核实事实**在契约里的字段名与判定。
#:
#: 为什么在这里另写一份字段名：这是**独立核对**用的 —— 引擎的 `derive_deep_distractors`
#: 说"这条干扰项与某事实相反"是它的声明，本表拿**原始契约字段**再验一遍
#: （不是为了替引擎判够格，够格口径仍然复用引擎的实现）。字段名对不上就会 FAIL。
_RULE_FACT_FIELDS: Dict[str, tuple] = {
    "skip_validation": ("validation_checks", lambda v: bool(v)),
    "no_early_return": ("guard_clauses", lambda v: bool(v)),
    "swallow_errors": ("error_handling", lambda v: bool(v)),
    "no_state_write": ("state_writes", lambda v: bool(v)),
    "handle_first_only": ("loop_count", lambda v: int(v or 0) > 0),
    "no_branch": ("branch_count", lambda v: int(v or 0) > 0),
}


class _KiLike:
    """把契约里的关键实现 dict 包成 `derive_deep_distractors` 能读的形状。

    与 `_FlowLike` 同一个套路：**只透传引擎真正读的那几个字段**，
    这样测试不需要复制一份"什么算够格"的判断，也不需要依赖契约里其余的键。
    """

    def __init__(self, payload: Dict[str, Any]) -> None:
        self.method_name = str(payload.get("method") or "")
        self.module_name = str(payload.get("module") or "")
        for field in (
            "validation_checks",
            "guard_clauses",
            "error_handling",
            "state_writes",
            "loop_count",
            "branch_count",
        ):
            setattr(self, field, payload.get(field))


def assert_level4(
    name: str,
    questions: Sequence[Dict[str, Any]],
    answer_key: Dict[str, Any],
    ki_payloads: Sequence[Dict[str, Any]],
    checker: Checker,
) -> None:
    """第 4 关的结构性断言。

    ``ki_payloads`` = 契约里 `deep_analysis.key_implementations.implementations`
    （**重要度降序**）。"哪条够格"复用引擎的 `derive_deep_distractors`：
    够格 = 它的已核实事实足以派生 ``_DISTRACTOR_COUNT`` 条**可证明为错**的干扰项。
    """
    kis = [_KiLike(item) for item in ki_payloads]
    ki_methods = [ki.method_name for ki in kis]
    pools = [derive_deep_distractors(ki) for ki in kis]
    eligible = [
        ki.method_name
        for ki, pool in zip(kis, pools)
        if len(pool) >= _DISTRACTOR_COUNT
    ]
    expected = eligible[: min(len(eligible), _MAX_LEVEL4_QUESTIONS)]

    lv4 = level_of(questions, 4)
    asked = [str(q.get("title") or "").split("·")[-1] for q in lv4]
    checker.check(
        f"{name} 第 4 关：够格（已核实事实 ≥{_DISTRACTOR_COUNT} 项）的实现各一道、按重要度取前 N 条",
        asked == expected,
        f"关键实现 {len(ki_methods)} 条 / 够格 {len(eligible)} 条 → 出题 {len(lv4)} 道"
        f"（上限 {_MAX_LEVEL4_QUESTIONS}）；预期 {'、'.join(expected) or '无'}，"
        f"实得 {'、'.join(asked) or '无'}",
    )

    pool_by_method = {ki.method_name: pool for ki, pool in zip(kis, pools)}
    payload_by_method = {ki.method_name: item for ki, item in zip(kis, ki_payloads)}

    bad_shape: List[str] = []
    bad_answer: List[str] = []
    fabricated: List[str] = []
    unproven: List[str] = []
    distractor_sets: List[frozenset] = []
    evidence_ok = True
    for question in lv4:
        index = questions.index(question)
        # 标题形如「第4关：关键实现·<方法名>」（多题时可能带 #2 后缀）
        asked_method = str(question.get("title") or "").split("·")[-1].split("#")[0]
        texts = _option_texts(question)
        if question.get("question_type") != "key_implementation" or len(texts) != 4 or len(set(texts)) != 4:
            bad_shape.append(f"#{index}")
        correct = _answer_texts(questions, answer_key, index)
        if len(correct) != 1:
            bad_answer.append(f"#{index} correct={correct}")

        # 干扰项必须取自引擎的**规则表**（不是编造的句子），而且每条都要能证明
        # "它相反的那项事实真的存在" —— 用原始契约字段独立验一遍。
        pool = pool_by_method.get(asked_method) or []
        rule_by_text = {item.text: item for item in pool}
        raw = payload_by_method.get(asked_method) or {}
        distractors = [t for t in texts if t not in set(correct)]
        distractor_sets.append(frozenset(distractors))
        for text in distractors:
            item = rule_by_text.get(text)
            if item is None:
                fabricated.append(f"#{index} {text[:24]!r}")
                continue
            field, predicate = _RULE_FACT_FIELDS.get(item.rule, ("", None))
            if predicate is None or not predicate(raw.get(field)):
                unproven.append(f"#{index} {item.rule}→{field}={raw.get(field)!r}")

        # 干扰项句式仍是固定文案 → source 必须还是 template（不许改标 data_driven）
        if question.get("source") != "template":
            unproven.append(f"#{index} source={question.get('source')!r}（应为 template）")

        for item in question.get("evidence") or []:
            path = str(item.get("file") or "")
            if path and (path.startswith("/") or ":" in path):
                evidence_ok = False

    checker.check(
        f"{name} 第 4 关每题都是 4 选 1、选项互不相同",
        not bad_shape,
        "、".join(bad_shape) if bad_shape else f"{len(lv4)} 道题全部合规",
    )
    checker.check(
        f"{name} 第 4 关每道题有且只有一个正确项，且与答案表一致",
        not bad_answer,
        "、".join(bad_answer) if bad_answer else f"{len(lv4)} 道题正确答案都能逐题对上",
    )
    checker.check(
        f"{name} 第 4 关每个干扰项都来自引擎的规则表（不是编造的句子）",
        not fabricated,
        "、".join(fabricated) if fabricated else f"{len(lv4) * _DISTRACTOR_COUNT} 个干扰项全部可回指到规则",
    )
    checker.check(
        f"{name} 第 4 关每条干扰项都与目标方法的一项**真实存在**的事实相反",
        not unproven,
        "、".join(unproven) if unproven else "逐条用契约原始字段验过：反着说的那项事实确实存在",
    )
    checker.check(
        f"{name} 第 4 关证据是项目内相对路径",
        evidence_ok,
        "" if evidence_ok else "发现绝对路径",
    )
    if len(lv4) >= 2:
        checker.check(
            f"{name} 第 4 关的干扰项**逐题轮换**（不共用同一组，避免排除法做出来）",
            len(set(distractor_sets)) >= 2,
            f"{len(lv4)} 道题 / {len(set(distractor_sets))} 种干扰项组合",
        )


# ---------------------------------------------------------------------------
# 合成用例（快、能构造真实项目里凑不出的边界）
# ---------------------------------------------------------------------------

def _module(mid: str, name: str, text: str, score: float = 0.5, mtype: str = "business",
            responsibilities: Sequence[str] = ()) -> ModuleInfo:
    return ModuleInfo(
        module_id=mid,
        name=name,
        module_type=mtype,
        description=text,
        key_responsibilities=list(responsibilities),
        core_score=score,
        method_count=6,
    )


def run_synthetic(checker: Checker, verbose: bool) -> None:
    print("\n=== 合成用例（边界：上限 / 空文本 / 干扰项不足 / 非业务模块）===")

    def generate(modules: List[ModuleInfo], seed: int = 42):
        gen = TrainingGenerator(seed=seed)
        training = gen.generate(modules, [], project_name="合成项目")
        return training

    # ---- A) 4 个业务模块，各有不同文本 → 4 道题 ----
    four = [
        _module("m1", "甲模块", "甲的职责：处理甲类对象"),
        _module("m2", "乙模块", "乙的职责：处理乙类对象"),
        _module("m3", "丙模块", "丙的职责：处理丙类对象"),
        _module("m4", "丁模块", "丁的职责：处理丁类对象"),
    ]
    training = generate(four)
    payload = training.to_dict()
    lv2 = level2_questions(payload["questions"])
    checker.check(
        "合成：4 个业务模块 → 4 道第 2 关题（改造前只有 1 道）",
        len(lv2) == 4,
        f"实得 {len(lv2)} 道",
    )
    assert_questions_wellformed(
        "合成(4 模块)",
        payload["questions"],
        training.answer_key(),
        {m.description for m in four},
        checker,
    )

    # ---- B) 8 个业务模块 → 不能无限出题 ----
    eight = [_module(f"m{i}", f"模块{i}", f"模块{i}的职责：处理第{i}类对象") for i in range(1, 9)]
    training8 = generate(eight)
    lv2_8 = level2_questions(training8.to_dict()["questions"])
    checker.check(
        f"合成：8 个业务模块 → 出题数被上限 {_MAX_LEVEL2_QUESTIONS} 截住（学生做得完）",
        len(lv2_8) == _MAX_LEVEL2_QUESTIONS,
        f"实得 {len(lv2_8)} 道",
    )

    # ---- C) 只有一个业务模块 → 凑不出 3 个干扰项 → 不出题 ----
    one = [_module("m1", "甲模块", "甲的职责：处理甲类对象")]
    checker.check(
        "合成：只有 1 个业务模块 → 不出第 2 关题（不编造干扰项）",
        not level2_questions(generate(one).to_dict()["questions"]),
        "0 道",
    )

    # ---- D) 文本是 CRUD 标签 / 空 → 不能当职责 ----
    crud_only = four + [
        _module("m5", "戊模块", "查询/获取操作"),
        _module("m6", "己模块", ""),
    ]
    training_crud = generate(crud_only)
    payload_crud = training_crud.to_dict()
    lv2_crud = level2_questions(payload_crud["questions"])
    option_texts = {str(o["text"]) for q in lv2_crud for o in q["options"]}
    checker.check(
        "合成：文本只有 CRUD 标签或为空的模块不出题（P0-05）",
        len(lv2_crud) == 4 and not (option_texts & set(_CRUD_LABELS)),
        f"出题 {len(lv2_crud)} 道；选项里的 CRUD 标签 {sorted(option_texts & set(_CRUD_LABELS))}",
    )
    checker.check(
        "合成：凑不出干扰项的模块被跳过，但其他模块照常出题",
        all("戊" not in str(q.get("title") or "") and "己" not in str(q.get("title") or "")
            for q in lv2_crud),
        "戊 / 己 都没有出现在题干里",
    )

    # ---- E) 编排 / 支撑模块不作为主体 ----
    mixed = [
        _module("m1", "甲模块", "甲的职责：处理甲类对象"),
        _module("m2", "乙模块", "乙的职责：处理乙类对象"),
        _module("m3", "丙模块", "丙的职责：处理丙类对象"),
        _module("m4", "丁模块", "丁的职责：处理丁类对象"),
        _module("app", "装配模块", "把各模块装配起来并编排调用", 0.9, "orchestrator"),
        _module("util", "工具模块", "提供通用工具能力", 0.8, "utils"),
    ]
    training_mixed = generate(mixed)
    titles = [str(q.get("title") or "") for q in level2_questions(training_mixed.to_dict()["questions"])]
    checker.check(
        "合成：编排 / 支撑模块即使核心度最高也不作为第 2 关主体",
        len(titles) == 4 and not any("装配模块" in t or "工具模块" in t for t in titles),
        f"{len(titles)} 道题：" + "、".join(t.split("·")[-1] for t in titles),
    )

    # ---- F) 确定性 ----
    first = generate(four).to_dict()
    second = generate(four).to_dict()
    checker.check(
        "合成：同一份模块数据两次生成逐字节一致（含选项顺序）",
        json.dumps(first, ensure_ascii=False, sort_keys=True)
        == json.dumps(second, ensure_ascii=False, sort_keys=True),
        "一致",
    )

    # ---- G) WO-03 一轮要求的负向对照：**够格但无文本** → 不出题 ----
    #      "够格"指它确实是业务模块（角色 / 方法数都够）；缺的是**业务语义文本**。
    #      造得像真的一样：4 个业务模块，描述与职责全是 CRUD 分类标签或空串。
    eligible_but_textless = [
        _module("n1", "甲模块", "新增/创建操作", responsibilities=["新增/创建操作"]),
        _module("n2", "乙模块", "", responsibilities=["查询/获取操作"]),
        _module("n3", "丙模块", "更新/修改操作", responsibilities=["删除/停用操作"]),
        _module("n4", "丁模块", "", responsibilities=[]),
    ]
    gen_textless = TrainingGenerator(seed=42)
    textless_payload = gen_textless.generate(
        eligible_but_textless, [], project_name="合成项目"
    ).to_dict()
    textless_report = gen_textless.level2_report()
    checker.check(
        "合成（负向对照）：够格但无业务语义文本 → 一道第 2 关题都不出",
        not level2_questions(textless_payload["questions"]),
        f"出题 {len(level2_questions(textless_payload['questions']))} 道",
    )
    checker.check(
        "合成（负向对照）：不出题的原因是 no_business_text，且**每个模块都有结论**",
        len(textless_report) == len(eligible_but_textless)
        and all(item["reason"] == LEVEL2_NO_BUSINESS_TEXT for item in textless_report)
        and all(item["has_business_text"] is False for item in textless_report),
        f"{len(textless_report)} 条结论，原因码 "
        f"{sorted({str(i['reason']) for i in textless_report})}",
    )
    checker.check(
        "合成（负向对照）：没出题时 summary 会把原因说出来（不是静默空列表）",
        "不出题" in gen_textless.level2_summary()
        and "业务语义文本" in gen_textless.level2_summary(),
        gen_textless.level2_summary(),
    )

    # ---- H) WO-03 一轮：有文本、但**数目不够** → 原因必须是另一条 ------------------
    #      这条与 G 是一对**区分性对照**：若引擎把"没文本"和"文本不够"混成一个原因，
    #      G 与 H 里必有一条 FAIL。
    two_texts = [
        _module("t1", "甲模块", "甲的职责：处理甲类对象"),
        _module("t2", "乙模块", "乙的职责：处理乙类对象"),
    ]
    gen_two = TrainingGenerator(seed=42)
    two_payload = gen_two.generate(two_texts, [], project_name="合成项目").to_dict()
    two_report = {item["module_id"]: item for item in gen_two.level2_report()}
    checker.check(
        "合成：只有 2 种职责文本 → 不出题，原因是 distractor_pool_too_small（与 G 区分开）",
        not level2_questions(two_payload["questions"])
        and two_report["t1"]["reason"] == LEVEL2_DISTRACTOR_POOL_TOO_SMALL
        and two_report["t1"]["distractors_found"] == 1
        and two_report["t1"]["distinct_texts_in_project"] == 2,
        f"出题 {len(level2_questions(two_payload['questions']))} 道；"
        f"t1: {two_report['t1']['reason']}（凑出 {two_report['t1']['distractors_found']} 个，"
        f"全项目 {two_report['t1']['distinct_texts_in_project']} 种文本）",
    )

    # ---- I) WO-03 一轮：第 4 关的够格门槛（合成关键实现，快且能造真实项目里没有的边界）----
    run_synthetic_level4(checker)


#: 第 4 关合成用例用的最小关键实现替身：只带引擎真正读的字段。
_STUB_KI_LIST_FIELDS = (
    "validation_checks",
    "guard_clauses",
    "error_handling",
    "state_writes",
)
_STUB_KI_INT_FIELDS = ("loop_count", "branch_count")


class _StubKi:
    """合成一条关键实现（**只带 `derive_deep_distractors` 真正读的字段**）。"""

    def __init__(self, method: str, **facts) -> None:
        self.method_name = method
        self.module_name = "m1"
        self.design_approach = str(facts.pop("design_approach", ""))
        self.categories = list(facts.pop("categories", []))
        self.importance_reasons = list(facts.pop("importance_reasons", []))
        self.filepath = str(facts.pop("filepath", "m1.py"))
        self.start_line = int(facts.pop("start_line", 1))
        self.end_line = int(facts.pop("end_line", 2))
        for field in _STUB_KI_LIST_FIELDS:
            value = facts.pop(field, None)
            setattr(self, field, None if value is None else list(value))
        for field in _STUB_KI_INT_FIELDS:
            setattr(self, field, int(facts.pop(field, 0) or 0))
        if facts:
            raise TypeError(f"未识别的字段：{sorted(facts)}")


class _StubKiBundle:
    def __init__(self, kis: List[_StubKi]) -> None:
        self.top_implementations = kis


def run_synthetic_level4(checker: Checker) -> None:
    """第 4 关干扰项派生规则的边界（够格 / 不够格 / 轮换）。"""
    print("\n=== 合成用例：第 4 关干扰项由已核实事实派生 ===")

    modules = [_module("m1", "甲模块", "甲的职责：处理甲类对象")]
    empty_flows: List = []

    # ---- I0) 六条规则各自只由**自己的那项事实**触发（规则 ↔ 事实字段一一对应）----
    #      为什么要有这条：真实项目不一定用到每一条规则（例如 `no_branch` 可能
    #      一次都没被选中），只靠真实项目就会漏掉"规则改名了 / 测试的字段表写错了"。
    #      每条只给一项事实，引擎就必须只回这一个规则 id。
    only_fact = {
        "skip_validation": {"validation_checks": ["a is None"]},
        "no_early_return": {"guard_clauses": ["a is None -> raise"]},
        "swallow_errors": {"error_handling": ["ValueError"]},
        "no_state_write": {"state_writes": ["items"]},
        "handle_first_only": {"loop_count": 1},
        "no_branch": {"branch_count": 2},
    }
    mismatched: List[str] = []
    for rule, facts in sorted(only_fact.items()):
        emitted = [
            item.rule
            for item in derive_deep_distractors(
                _KiLike({**facts, "method": f"only_{rule}", "module": "m1"})
            )
        ]
        field, predicate = _RULE_FACT_FIELDS.get(rule, ("", None))
        if emitted != [rule] or predicate is None or not predicate(facts.get(field)):
            mismatched.append(f"{rule}→{emitted or '无'}")
    checker.check(
        "合成：六条规则各自只由自己的那项事实触发（规则 ↔ 事实字段一一对应）",
        not mismatched,
        "、".join(mismatched) if mismatched else f"{len(only_fact)} 条规则逐条对上",
    )

    # ---- I1) 事实足够（校验 + 异常 + 循环 = 3 项）→ 出一道，干扰项只许来自这三条 ----
    rich = _StubKi(
        "rich_method",
        validation_checks=["x is None"],
        error_handling=["ValueError"],
        loop_count=1,
        guard_clauses=None,
        state_writes=None,
        branch_count=0,
    )
    gen_rich = TrainingGenerator(seed=42)
    rich_training = gen_rich.generate(
        modules, empty_flows, project_name="合成项目", key_implementations=_StubKiBundle([rich])
    )
    rich_questions = rich_training.to_dict()["questions"]
    key_rich = rich_training.answer_key()
    lv4_rich = level_of(rich_questions, 4)
    rich_pool = {item.text: item for item in derive_deep_distractors(rich)}
    rich_distractors = [
        text
        for question in lv4_rich
        for text in _option_texts(question)
        if text
        not in {
            str(o["text"])
            for o in question["options"]
            if str(o["id"]) in {str(a) for a in key_rich[str(rich_questions.index(question))]["answers"]}
        }
    ]
    checker.check(
        "合成：3 项已核实事实 → 出一道第 4 关题，且干扰项全部来自规则表",
        len(lv4_rich) == 1
        and len(rich_distractors) == _DISTRACTOR_COUNT
        and all(text in rich_pool for text in rich_distractors),
        f"出题 {len(lv4_rich)} 道 / 干扰项 {len(rich_distractors)} 个"
        f"（规则池 {len(rich_pool)} 条）",
    )
    checker.check(
        "合成：第 4 关每条干扰项都能说出它反的是哪一项事实（contradicts 非空）",
        all(rich_pool[text].contradicts.strip() for text in rich_distractors if text in rich_pool)
        and {item.rule for item in derive_deep_distractors(rich)}
        == {"skip_validation", "swallow_errors", "handle_first_only"},
        "规则：" + "、".join(sorted({item.rule for item in derive_deep_distractors(rich)})),
    )

    # ---- I2) 事实只有 2 项（循环 + 分支）→ **不够格**，一道都不出（不编造）----
    thin = _StubKi(
        "thin_method",
        validation_checks=None,
        error_handling=None,
        state_writes=None,
        guard_clauses=None,
        loop_count=1,
        branch_count=1,
    )
    gen_thin = TrainingGenerator(seed=42)
    thin_payload = gen_thin.generate(
        modules, empty_flows, project_name="合成项目", key_implementations=_StubKiBundle([thin])
    ).to_dict()
    checker.check(
        "合成（负向对照）：已核实事实只有 2 项 → 第 4 关不出题（凑不出 3 个可证明为错的干扰项）",
        not level_of(thin_payload["questions"], 4)
        and len(derive_deep_distractors(thin)) == 2,
        f"出题 {len(level_of(thin_payload['questions'], 4))} 道 / 规则池 {len(derive_deep_distractors(thin))} 条",
    )

    # ---- I3) 事实不足的实现被跳过时，由**后面够格的实现顶上** ----
    gen_mixed = TrainingGenerator(seed=42)
    mixed_payload = gen_mixed.generate(
        modules,
        empty_flows,
        project_name="合成项目",
        key_implementations=_StubKiBundle([thin, rich]),
    ).to_dict()
    asked = [str(q.get("title") or "").split("·")[-1] for q in level_of(mixed_payload["questions"], 4)]
    checker.check(
        "合成：不够格的实现被跳过，后面够格的顶上（不是整关不出）",
        asked == ["rich_method"],
        f"实得 {'、'.join(asked) or '无'}",
    )

    # ---- I4) 轮换：多条实现的干扰项三元组不共用同一组 ----
    many = [
        _StubKi(
            f"m{i}_method",
            validation_checks=["a is None"],
            guard_clauses=["a is None -> raise"],
            error_handling=["ValueError"],
            state_writes=["items"],
            loop_count=1,
            branch_count=2,
        )
        for i in range(3)
    ]
    gen_many = TrainingGenerator(seed=42)
    many_payload = gen_many.generate(
        modules, empty_flows, project_name="合成项目", key_implementations=_StubKiBundle(many)
    )
    many_questions = many_payload.to_dict()["questions"]
    key = many_payload.answer_key()
    combos = set()
    for index, question in enumerate(many_questions):
        if question.get("level") != 4:
            continue
        answers = set(key[str(index)]["answers"])
        correct = {str(o["text"]) for o in question["options"] if str(o["id"]) in answers}
        combos.add(frozenset(str(o["text"]) for o in question["options"] if str(o["text"]) not in correct))
    checker.check(
        "合成：第 4 关多题之间干扰项三元组**不共用同一组**（轮换生效）",
        len(combos) >= 2,
        f"{len([q for q in many_questions if q.get('level') == 4])} 道题 / {len(combos)} 种组合",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="第 2 / 3 / 4 关「一关多题」出题覆盖测试")
    parser.add_argument("--project", action="append", default=None,
                        help="只校验指定项目目录（可重复），默认为两个演示项目")
    parser.add_argument("--verbose", action="store_true", help="打印每一条断言")
    args = parser.parse_args()

    checker = Checker(verbose=args.verbose)
    print("=" * 74)
    print("第 2 / 3 / 4 关「一关多题」出题覆盖测试（README 优先级 4，含二轮扩展）")
    print("=" * 74)

    for project in (args.project or DEFAULT_PROJECTS):
        if not (REPO_ROOT / project).is_dir():
            print(f"\n[跳过] {project}: 目录不存在")
            continue
        run_project(project, checker, args.verbose)

    run_synthetic(checker, args.verbose)

    total = len(checker.rows)
    failed = checker.failed
    print("\n" + "=" * 74)
    if failed:
        print(f"结果：{total - failed}/{total} 项通过，{failed} 项失败")
        for name, ok, detail in checker.rows:
            if not ok:
                print(f"  [FAIL] {name}" + (f"  — {detail}" if detail else ""))
        print("=" * 74)
        return 1
    print(f"结果：{total}/{total} 项全部通过")
    print(
        "（出题上限：第 2 关 {0} / 第 3 关 {1} / 第 4 关 {2}）".format(
            _MAX_LEVEL2_QUESTIONS, _MAX_LEVEL3_QUESTIONS, _MAX_LEVEL4_QUESTIONS
        )
    )
    print("=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
