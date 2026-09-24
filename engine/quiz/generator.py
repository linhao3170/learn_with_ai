"""
闯关题生成器

基于业务逻辑分析结果，用模板方式生成三道关卡：
- 关卡1：代码识别题（选择题，识别代码片段的功能）
- 关卡2：业务逻辑题（选择题，理解流程和边界条件）
- 关卡3：逻辑引导题（填空题，按步骤补全关键逻辑）

设计原则：
1. 所有题目的正确答案必须能从静态分析结果中推导出来
2. 干扰项要有迷惑性，但不能有歧义
3. 每道题都附带来源行号证据

P0-12：中文标签外置到 ``engine/lexicon/quiz_labels.json``；
P0-14：随机源改为独立的 ``random.Random`` 实例（默认播种 42），
       不再改写全局随机状态，默认输出可复现。
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from .. import lexicon


def _quiz_labels() -> Dict[str, Any]:
    """读取闯关题标签词典（缺失时回退到空 dict，由调用方给兜底值）。"""
    return lexicon.load_lexicon("quiz_labels")


@dataclass
class QuizOption:
    id: str  # A/B/C/D
    text: str
    is_correct: bool = False


@dataclass
class QuizQuestion:
    level: int  # 1/2/3
    question_type: str  # code_recognition / logic_understanding / guided_fill
    title: str
    description: str
    options: List[QuizOption] = field(default_factory=list)
    correct_answer: str = ""  # A/B/C/D...
    explanation: str = ""
    evidence_lines: List[int] = field(default_factory=list)
    knowledge_points: List[str] = field(default_factory=list)
    difficulty: int = 1  # 1-5

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "question_type": self.question_type,
            "title": self.title,
            "description": self.description,
            "options": [
                {"id": o.id, "text": o.text}
                for o in self.options
            ],
            "correct_answer": self.correct_answer,
            "explanation": self.explanation,
            "evidence_lines": self.evidence_lines,
            "knowledge_points": self.knowledge_points,
            "difficulty": self.difficulty,
        }


@dataclass
class QuizSet:
    questions: List[QuizQuestion] = field(default_factory=list)

    def to_dict(self) -> list:
        return [q.to_dict() for q in self.questions]


class QuizGenerator:
    """
    闯关题生成器
    基于分析结果生成 3 道递进式题目。
    当前使用模板 + 启发式规则，保证答案可验证。
    """

    def __init__(self, seed: Optional[int] = 42):
        """
        P0-14（README5 §1.2-⑨）
        ----------------------
        以前默认 ``seed=None``，即**不播种**，用的是**全局** ``random`` 模块 ——
        结果既不可复现，又会互相污染（同进程里另一个生成器调用 ``random.seed``
        会改变这里的输出）。

        现在：
        - 默认 ``seed=42``，保证同一份输入得到同一份题目；
        - 使用**独立的** ``random.Random`` 实例，不再碰全局随机状态；
        - 显式传 ``seed=None`` 可以要"每次都不同"，这时用一个独立实例，
          仍然不影响其他组件。
        """
        self._rng = random.Random(seed)

    def generate(self, analysis_result: Dict[str, Any], source_lines: List[str]) -> QuizSet:
        quiz = QuizSet()
        all_funcs = self._collect_functions(analysis_result)
        crud_funcs = self._get_crud_functions(analysis_result)
        validation_funcs = self._get_validation_functions(analysis_result)

        q1 = self._generate_level1(all_funcs, crud_funcs, source_lines)
        if q1:
            quiz.questions.append(q1)

        q2 = self._generate_level2(all_funcs, validation_funcs, source_lines)
        if q2:
            quiz.questions.append(q2)

        q3 = self._generate_level3(all_funcs, crud_funcs, source_lines)
        if q3:
            quiz.questions.append(q3)

        return quiz

    def _collect_functions(self, ar: Dict[str, Any]) -> List[Dict[str, Any]]:
        funcs = []
        for cls in ar.get("classes", []):
            for m in cls.get("methods", []):
                m["_in_class"] = cls["name"]
                m["_full_name"] = cls["name"] + "." + m["name"]
                funcs.append(m)
        for f in ar.get("functions", []):
            f["_in_class"] = None
            f["_full_name"] = f["name"]
            funcs.append(f)
        funcs = [f for f in funcs if not f["name"].startswith("__")]
        return funcs

    def _get_crud_functions(self, ar: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            p for p in ar.get("patterns", [])
            if p["pattern_id"] == "crud" and p["target_type"] == "function"
        ]

    def _get_validation_functions(self, ar: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            p for p in ar.get("patterns", [])
            if p["pattern_id"] == "data_validation"
        ]

    # ===== 关卡 1 =====
    def _generate_level1(self, all_funcs, crud_funcs, source_lines):
        if not crud_funcs and not all_funcs:
            return None

        target = None
        func_obj = None
        if crud_funcs:
            target = self._rng.choice(crud_funcs)
            target_name = target["target_name"]
            func_obj = next((f for f in all_funcs if f["name"] == target_name), None)

        if not func_obj and all_funcs:
            func_obj = self._rng.choice(all_funcs)
            target_name = func_obj["name"]

        if not func_obj:
            return None

        start = func_obj["start_line"]
        end = func_obj["end_line"]
        code_lines = source_lines[start - 1 : end]
        code_snippet = "\n".join(code_lines)

        sub_type = target.get("sub_type", "") if target else ""
        # P0-12：标签来自 engine/lexicon/quiz_labels.json，不再写死在代码里
        crud_map = _quiz_labels().get("crud_map", {})
        correct_label = crud_map.get(sub_type, _quiz_labels().get("fallback_label", "实现指定功能的函数"))

        all_labels = list(_quiz_labels().get("all_labels", [])) or [correct_label]
        distractors = [l for l in all_labels if l != correct_label]
        self._rng.shuffle(distractors)
        distractors = distractors[:3]

        options_text = [correct_label] + distractors
        self._rng.shuffle(options_text)

        options = []
        correct_id = ""
        for i, text in enumerate(options_text):
            opt_id = chr(ord("A") + i)
            is_correct = text == correct_label
            if is_correct:
                correct_id = opt_id
            options.append(QuizOption(id=opt_id, text=text, is_correct=is_correct))

        return QuizQuestion(
            level=1,
            question_type="code_recognition",
            title="代码功能识别",
            description="阅读下面的代码，判断它实现了什么功能：\n\n```python\n" + code_snippet + "\n```",
            options=options,
            correct_answer=correct_id,
            explanation="这段代码是 " + target_name + " 函数，可以从函数名、参数和操作模式推断其功能。",
            evidence_lines=list(range(start, end + 1)),
            knowledge_points=["basic.function", "basic.dict"],
            difficulty=1,
        )

    # ===== 关卡 2 =====
    def _generate_level2(self, all_funcs, validation_funcs, source_lines):
        valid_funcs = [f for f in all_funcs if f.get("raise_count", 0) > 0]
        if not valid_funcs:
            valid_funcs = [f for f in all_funcs if f.get("if_count", 0) > 1]
        if not valid_funcs:
            return None

        func = self._rng.choice(valid_funcs)
        func_name = func["_full_name"]
        start = func["start_line"]
        end = func["end_line"]

        raise_line = None
        for i in range(start - 1, min(end, len(source_lines))):
            if "raise " in source_lines[i]:
                raise_line = i + 1
                break

        if not raise_line:
            return None

        raise_code = source_lines[raise_line - 1].strip()
        err_match = re.search(r"raise\s+(\w+)", raise_code)
        error_type = err_match.group(1) if err_match else "异常"

        correct = "抛出 " + error_type + " 异常"
        distractors = [
            "返回 None",
            "返回 False",
            "自动修正为合法值",
            "跳过该操作继续执行",
            "打印错误信息后继续",
            "退出程序",
        ]
        self._rng.shuffle(distractors)
        distractors = distractors[:3]

        options_text = [correct] + distractors
        self._rng.shuffle(options_text)

        options = []
        correct_id = ""
        for i, text in enumerate(options_text):
            opt_id = chr(ord("A") + i)
            is_correct = text == correct
            if is_correct:
                correct_id = opt_id
            options.append(QuizOption(id=opt_id, text=text, is_correct=is_correct))

        return QuizQuestion(
            level=2,
            question_type="logic_understanding",
            title="边界条件理解",
            description=(
                "在 `" + func_name + "` 函数中，"
                + _quiz_labels().get(
                    "exception_stem_suffix",
                    "如果传入的参数不合法，系统会如何处理？",
                )
            ),
            options=options,
            correct_answer=correct_id,
            explanation=(
                "该函数使用防御式编程，在执行操作前先验证参数合法性。"
                "一旦发现不合法输入，立即通过 " + error_type + " 抛出异常，"
                "阻止后续逻辑执行。"
            ),
            evidence_lines=[raise_line],
            knowledge_points=["adv.exception", "validation.boundary", "validation.custom"],
            difficulty=2,
        )

    # ===== 关卡 3 =====
    def _generate_level3(self, all_funcs, crud_funcs, source_lines):
        candidates = [
            f for f in all_funcs
            if f.get("if_count", 0) >= 1 and f.get("call_count", 0) >= 1
        ]
        if not candidates:
            candidates = [f for f in all_funcs if f.get("if_count", 0) >= 1]
        if not candidates:
            candidates = all_funcs
        if not candidates:
            return None

        func = self._rng.choice(candidates)
        func_name = func["_full_name"]
        start = func["start_line"]
        end = func["end_line"]

        blank_line_idx = None
        blank_text = ""
        for i in range(start, min(end, len(source_lines))):
            line = source_lines[i].strip()
            if not line or line.startswith("#") or line.startswith('"""') or line.startswith("def "):
                continue
            if "[" in line and "] =" in line:
                blank_line_idx = i + 1
                blank_text = line
                break
            if "return " in line and ("self" in line or "True" in line or "False" in line):
                blank_line_idx = i + 1
                blank_text = line
                break
            if "raise " in line:
                blank_line_idx = i + 1
                blank_text = line
                break

        if not blank_line_idx:
            for i in range(start, min(end, len(source_lines))):
                if source_lines[i].strip() and not source_lines[i].strip().startswith("#"):
                    blank_line_idx = i + 1
                    blank_text = source_lines[i].strip()
                    break

        if not blank_line_idx or not blank_text:
            return None

        code_with_blank = []
        for i in range(start - 1, min(end, len(source_lines))):
            line_num = i + 1
            if line_num == blank_line_idx:
                indent = len(source_lines[i]) - len(source_lines[i].lstrip())
                code_with_blank.append(" " * indent + "? _______  # 请填写正确的代码")
            else:
                code_with_blank.append(source_lines[i])

        code_snippet = "\n".join(code_with_blank)
        correct = blank_text.strip()
        if len(correct) > 60:
            correct_display = correct[:57] + "..."
        else:
            correct_display = correct

        distractors = self._generate_code_distractors(blank_text)

        options_text = [correct_display] + distractors
        self._rng.shuffle(options_text)

        options = []
        correct_id = ""
        for i, text in enumerate(options_text):
            opt_id = chr(ord("A") + i)
            is_correct = text == correct_display
            if is_correct:
                correct_id = opt_id
            options.append(QuizOption(id=opt_id, text=text, is_correct=is_correct))

        return QuizQuestion(
            level=3,
            question_type="guided_fill",
            title="关键代码补全",
            description=(
                "下面是 `" + func_name + "` 函数的代码，其中有一行被遮挡了。"
                "请根据上下文逻辑，选择正确的语句填入空白处：\n\n"
                "```python\n" + code_snippet + "\n```"
            ),
            options=options,
            correct_answer=correct_id,
            explanation=(
                "正确答案是 `" + correct_display + "`。\n"
                "这行代码是该函数的核心操作，结合前面的验证逻辑和整体业务目的可以推断。"
            ),
            evidence_lines=[blank_line_idx],
            knowledge_points=["pattern.crud", "basic.dict", "validation.boundary"],
            difficulty=3,
        )

    def _generate_code_distractors(self, correct_line: str) -> List[str]:
        line = correct_line.strip()
        distractors = []

        # 字典赋值类干扰
        if "[" in line and "] =" in line:
            d1 = line.replace("] =", "] = None  # ")
            d1 = d1[:len(line)]
            if d1 != line and d1 not in distractors:
                distractors.append(d1[:60] + ("..." if len(d1) > 60 else ""))

        # 条件方向改变
        if "if " in line and ">" in line:
            d2 = line.replace(">", "<")
            if d2 != line and d2 not in distractors:
                distractors.append(d2[:60] + ("..." if len(d2) > 60 else ""))
        elif "if " in line and "<" in line:
            d2 = line.replace("<", ">")
            if d2 != line and d2 not in distractors:
                distractors.append(d2[:60] + ("..." if len(d2) > 60 else ""))

        # return 类干扰
        if line.startswith("return "):
            distractors.append("pass  # 不返回任何值")
            distractors.append("continue  # 继续下一轮")

        # 通用干扰项
        generic = [
            "pass  # 跳过该步骤",
            "break  # 跳出循环",
            "return None  # 返回空",
            "raise RuntimeError  # 抛出运行时错误",
        ]
        self._rng.shuffle(generic)
        for g in generic:
            if len(distractors) >= 3:
                break
            if g not in distractors and g != line:
                distractors.append(g)

        return distractors[:3]


def generate_quiz(analysis_result, source_code, seed=None):
    source_lines = source_code.splitlines()
    return QuizGenerator(seed=seed).generate(analysis_result, source_lines)
