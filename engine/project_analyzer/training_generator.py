"""
项目级训练题生成器

生成四关引导式训练：
第1关：功能拆分 — 选出系统应该有哪些核心模块
第2关：模块职责 — 匹配模块和它的职责
第3关：流程推演 — 排序核心业务流程的步骤
第4关：关键实现 — 选择核心功能的实现思路
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from .module_analyzer import ModuleInfo, CoreFlow


@dataclass
class TrainingOption:
    """选项"""
    id: str
    text: str
    is_correct: bool = False
    hint: str = ""


@dataclass
class TrainingQuestion:
    """一道训练题"""
    level: int  # 1/2/3/4
    question_type: str  # module_selection / responsibility_match / flow_ordering / key_implementation
    title: str
    description: str
    options: List[TrainingOption] = field(default_factory=list)
    correct_answers: List[str] = field(default_factory=list)  # 正确答案（多选可能多个）
    explanation: str = ""
    knowledge_points: List[str] = field(default_factory=list)
    difficulty: int = 1

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "question_type": self.question_type,
            "title": self.title,
            "description": self.description,
            "options": [{"id": o.id, "text": o.text, "hint": o.hint} for o in self.options],
            "correct_answers": self.correct_answers,
            "explanation": self.explanation,
            "knowledge_points": self.knowledge_points,
            "difficulty": self.difficulty,
        }


@dataclass
class TrainingSet:
    """一套完整的项目级训练"""
    project_name: str = ""
    project_description: str = ""
    questions: List[TrainingQuestion] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "project_description": self.project_description,
            "questions": [q.to_dict() for q in self.questions],
        }


class TrainingGenerator:
    """项目级训练题生成器"""

    def __init__(self, seed: Optional[int] = 42):
        if seed is not None:
            random.seed(seed)

    def generate(
        self,
        modules: List[ModuleInfo],
        core_flows: List[CoreFlow],
        project_name: str,
        project_description: str = "",
        key_implementations: Optional[object] = None,
    ) -> TrainingSet:
        """生成四关训练题

        Args:
            modules: 模块列表
            core_flows: 核心业务流程
            project_name: 项目名称
            project_description: 项目描述
            key_implementations: 关键实现分析结果（可选，来自 deep_analyzer）
        """
        training = TrainingSet(
            project_name=project_name,
            project_description=project_description,
        )

        # 第 1 关：功能拆分
        q1 = self._generate_level1(modules)
        if q1:
            training.questions.append(q1)

        # 第 2 关：模块职责匹配
        q2 = self._generate_level2(modules)
        if q2:
            training.questions.append(q2)

        # 第 3 关：流程推演
        q3 = self._generate_level3(core_flows, modules)
        if q3:
            training.questions.append(q3)

        # 第 4 关：关键实现
        q4 = self._generate_level4(modules, core_flows, key_implementations)
        if q4:
            training.questions.append(q4)

        return training

    # ===== 第 1 关：功能拆分 =====

    def _generate_level1(self, modules: List[ModuleInfo]) -> Optional[TrainingQuestion]:
        """
        第 1 关：功能拆分
        从候选模块中选出这个系统应该有的核心模块
        """
        if len(modules) < 2:
            return None

        correct_modules = [(m.module_id, m.name) for m in modules]

        # 生成干扰项模块
        distractor_modules = [
            ("payment_module", "支付管理模块"),
            ("chat_module", "即时通讯模块"),
            ("report_module", "报表统计模块"),
            ("logistics_module", "物流配送模块"),
            ("game_module", "游戏娱乐模块"),
            ("video_module", "视频点播模块"),
            ("weather_module", "天气预报模块"),
            ("music_module", "音乐播放模块"),
        ]
        random.shuffle(distractor_modules)

        # 干扰项数量 = 正确答案数量（让题目有区分度）
        num_distractors = min(len(distractor_modules), max(2, len(correct_modules)))
        selected_distractors = distractor_modules[:num_distractors]

        # 混合所有选项
        all_options = correct_modules + selected_distractors
        random.shuffle(all_options)

        options = []
        correct_ids = []
        for i, (mid, mname) in enumerate(all_options):
            opt_id = chr(ord("A") + i)
            is_correct = mid in [m[0] for m in correct_modules]
            if is_correct:
                correct_ids.append(opt_id)
            options.append(TrainingOption(
                id=opt_id,
                text=mname,
                is_correct=is_correct,
            ))

        return TrainingQuestion(
            level=1,
            question_type="module_selection",
            title="第1关：功能拆分",
            description=(
                f"这是一个「{correct_modules[0][1].replace('模块', '')}」相关的系统。\n"
                f"请从以下选项中选出这个系统**应该包含**的核心功能模块（多选）。\n\n"
                f"提示：思考一下这个系统的核心业务是什么，支撑这个业务需要哪些功能模块？"
            ),
            options=options,
            correct_answers=correct_ids,
            explanation=(
                f"这个系统包含 {len(correct_modules)} 个核心模块："
                f"{'、'.join(m[1] for m in correct_modules)}。\n\n"
                f"正确的拆分思路是：先确定系统的核心业务，然后围绕核心业务识别支撑它的各个功能模块。"
                f"每个模块应该有清晰的职责边界，模块之间通过接口协作。"
            ),
            knowledge_points=["系统设计", "模块划分", "职责边界"],
            difficulty=2,
        )

    # ===== 第 2 关：模块职责匹配 =====

    def _generate_level2(self, modules: List[ModuleInfo]) -> Optional[TrainingQuestion]:
        """
        第 2 关：模块职责匹配
        给出模块列表和职责描述，匹配对应关系
        """
        if len(modules) < 2:
            return None

        # 取前 4 个主要模块来出题
        selected = modules[:min(4, len(modules))]

        # 生成选项：每个模块的职责描述
        options = []
        correct_pairs = {}  # 模块 -> 选项 ID

        # 生成模块描述列表（打乱顺序）
        descriptions = []
        for mod in selected:
            desc = mod.key_responsibilities[:3] if mod.key_responsibilities else [mod.description]
            desc_text = "、".join(desc[:2])
            descriptions.append((mod.module_id, mod.name, desc_text))

        shuffled_desc = descriptions.copy()
        random.shuffle(shuffled_desc)

        # 构建题目：左边是模块，右边是描述，让用户选择正确的匹配
        # 简化版：给出一个模块，问它的主要职责是什么
        target_module = selected[0]
        correct_desc = target_module.key_responsibilities[:2] if target_module.key_responsibilities else [target_module.description]
        correct_text = "、".join(correct_desc)

        # 生成干扰描述（其他模块的职责）
        distractors = []
        for mod in selected[1:]:
            d = mod.key_responsibilities[:2] if mod.key_responsibilities else [mod.description]
            distractors.append("、".join(d))

        # 补够 3 个干扰项
        generic_distractors = [
            "负责系统的日志记录和监控告警",
            "负责数据的备份和恢复",
            "负责用户界面的渲染和交互",
            "负责网络请求的发送和接收",
        ]
        random.shuffle(generic_distractors)
        for gd in generic_distractors:
            if len(distractors) >= 3:
                break
            distractors.append(gd)

        distractors = distractors[:3]

        all_options = [correct_text] + distractors
        random.shuffle(all_options)

        options = []
        correct_id = ""
        for i, text in enumerate(all_options):
            opt_id = chr(ord("A") + i)
            is_correct = text == correct_text
            if is_correct:
                correct_id = opt_id
            options.append(TrainingOption(id=opt_id, text=text, is_correct=is_correct))

        return TrainingQuestion(
            level=2,
            question_type="responsibility_match",
            title="第2关：模块职责",
            description=(
                f"**「{target_module.name}」** 的主要职责是什么？\n\n"
                f"请从下面选项中选出最准确的描述。"
            ),
            options=options,
            correct_answers=[correct_id],
            explanation=(
                f"「{target_module.name}」的核心职责是：{correct_text}。\n\n"
                f"理解模块职责的关键是看它对外提供什么能力、管理什么数据。"
                f"一个好的模块应该职责单一，只负责一类相关的功能。"
            ),
            knowledge_points=["模块职责", "单一职责", "接口设计"],
            difficulty=2,
        )

    # ===== 第 3 关：流程推演 =====

    def _generate_level3(self, core_flows: List[CoreFlow], modules: List[ModuleInfo]) -> Optional[TrainingQuestion]:
        """
        第 3 关：流程推演
        给出核心业务流程的步骤，让用户排序
        """
        if not core_flows:
            return None

        flow = core_flows[0]  # 取最核心的流程
        steps = flow.steps

        if len(steps) < 3:
            return None

        # 打乱步骤顺序作为题目
        shuffled_steps = steps.copy()
        random.shuffle(shuffled_steps)

        # 构建选项（排序题简化为选择题：哪个是正确的顺序？）
        correct_order = " → ".join(s["name"].split("：")[0] for s in steps)

        # 生成干扰顺序
        def make_wrong_order(steps, swap_count=1):
            wrong = steps.copy()
            for _ in range(swap_count):
                i, j = random.sample(range(len(wrong)), 2)
                wrong[i], wrong[j] = wrong[j], wrong[i]
            return " → ".join(s["name"].split("：")[0] for s in wrong)

        wrong_orders = [
            make_wrong_order(steps, 2),
            make_wrong_order(steps, 1),
            make_wrong_order(steps, 3),
        ]

        all_options = [correct_order] + wrong_orders
        random.shuffle(all_options)

        options = []
        correct_id = ""
        for i, text in enumerate(all_options):
            opt_id = chr(ord("A") + i)
            is_correct = text == correct_order
            if is_correct:
                correct_id = opt_id
            options.append(TrainingOption(id=opt_id, text=text, is_correct=is_correct))

        return TrainingQuestion(
            level=3,
            question_type="flow_ordering",
            title="第3关：流程推演",
            description=(
                f"**「{flow.name}」** 的正确执行顺序是什么？\n\n"
                f"请思考一个完整的业务流程应该先做什么、后做什么，"
                f"选出步骤顺序正确的选项。\n\n"
                f"涉及模块：{', '.join(flow.involved_modules)}"
            ),
            options=options,
            correct_answers=[correct_id],
            explanation=(
                f"正确顺序是：{correct_order}\n\n"
                f"理解业务流程的关键是思考「数据和状态是怎么变化的」："
                f"什么操作会触发状态改变？改变之前需要什么前提？"
                f"校验通常在操作之前，审批通常在创建之后。"
            ),
            knowledge_points=["业务流程", "状态流转", "数据流"],
            difficulty=3,
        )


    def _generate_level4_deep(self, key_implementations, modules: List[ModuleInfo]) -> Optional[TrainingQuestion]:
        """
        第 4 关：关键实现（深度分析版）
        基于真实代码分析的关键实现题，使用 key_implementation 分析结果。
        """
        top_kis = key_implementations.top_implementations
        if not top_kis:
            return None

        # Pick the most important method
        ki = top_kis[0]

        # Find the module display name
        module_name = ki.module_name
        module_display = module_name
        for m in modules:
            if m.module_id == module_name:
                module_display = m.name
                break

        method_name = ki.method_name

        # Build question stem from real analysis data
        question_parts = []
        question_parts.append(
            f"在「{module_display}」中，`{method_name}` 是一个关键方法。\n"
        )
        if ki.design_approach:
            question_parts.append(f"它的主要特点是：{ki.design_approach}。\n")
        question_parts.append("请选择这个功能**最合理**的实现思路：")
        question_text = "\n".join(question_parts)

        # Build correct answer from real code analysis
        correct_parts = []
        if ki.validation_checks:
            checks = "、".join(ki.validation_checks[:3])
            correct_parts.append(f"先进行边界条件校验（{checks}）")
        if "algorithmic" in ki.categories and ki.loop_count > 0:
            correct_parts.append("通过遍历/循环实现核心算法逻辑")
        if ki.state_writes:
            writes = "、".join(ki.state_writes[:3])
            correct_parts.append(f"修改状态字段（{writes}）")
        if ki.error_handling:
            errors = "、".join([e.split(":")[0] for e in ki.error_handling[:3]])
            correct_parts.append(f"非法情况抛出异常（{errors}）")

        if not correct_parts:
            correct_parts.append("参数校验 -> 核心逻辑 -> 状态更新 -> 返回结果")

        correct = "；".join(correct_parts)

        # Build distractors
        distractors = self._generate_distractors_deep(ki, correct_parts)

        all_options = [correct] + distractors
        random.shuffle(all_options)

        options = []
        correct_id = ""
        for i, text in enumerate(all_options):
            opt_id = chr(ord("A") + i)
            is_correct = text == correct
            if is_correct:
                correct_id = opt_id
            options.append(TrainingOption(id=opt_id, text=text, is_correct=is_correct))

        # Build explanation with real code evidence
        explanation_parts = [f"正确思路：{correct}\n"]
        explanation_parts.append("\n代码证据：")
        if ki.importance_reasons:
            for reason in ki.importance_reasons[:3]:
                explanation_parts.append(f"  - {reason}")
        if ki.error_handling:
            explanation_parts.append(f"  - 抛出 {len(ki.error_handling)} 种异常处理非法输入")
        if ki.state_writes:
            explanation_parts.append(f"  - 修改 {len(ki.state_writes)} 个状态字段")
        short_file = ki.filepath.replace("\\", "/").split("/")[-1]
        explanation_parts.append(
            f"  - 代码位于 {short_file} 第 {ki.start_line}-{ki.end_line} 行"
        )

        explanation_parts.append("\n设计关键实现时需要考虑：")
        explanation_parts.append("1. 前置条件是什么（状态、权限、参数）")
        explanation_parts.append("2. 核心逻辑是什么（算法、操作）")
        explanation_parts.append("3. 异常情况怎么处理（边界、回滚）")
        explanation_parts.append("4. 结果怎么返回（成功/失败的标识）")

        # Knowledge points based on actual categories
        knowledge_points = []
        if "algorithmic" in ki.categories:
            knowledge_points.append("算法设计")
        if "validation" in ki.categories:
            knowledge_points.append("边界条件")
        if "state_mutation" in ki.categories or "state_transition" in ki.categories:
            knowledge_points.append("状态管理")
        if "error_handling" in ki.categories:
            knowledge_points.append("异常处理")
        if not knowledge_points:
            knowledge_points = ["设计思路", "代码实现"]

        return TrainingQuestion(
            level=4,
            question_type="key_implementation",
            title="第4关：关键实现",
            description=question_text,
            options=options,
            correct_answers=[correct_id],
            explanation="\n".join(explanation_parts),
            knowledge_points=knowledge_points,
            difficulty=4,
        )

    def _generate_distractors_deep(self, ki, correct_parts):
        """Generate distractors for the deep-analysis level 4 question."""
        method_name = ki.method_name.lower()

        # Generic distractors
        distractors = [
            "直接操作数据即可，不需要校验参数和状态，让调用方自己保证合法",
            "把所有逻辑都写在一个大函数里，不用拆分成小方法，一次性完成所有操作",
            "先返回结果，后台异步执行实际操作，这样性能更好",
            "用 try-except 捕获所有异常，有异常就返回 None，不区分错误类型",
        ]

        # Targeted distractors based on method characteristics
        if "algorithmic" in ki.categories and ki.loop_count > 0:
            distractors.insert(
                0,
                "只需要检查第一个和最后一个元素是否冲突，不需要遍历全部数据"
            )

        if "validation" in ki.categories:
            distractors.insert(
                1,
                "只校验参数类型是否正确，业务规则交给数据库约束处理"
            )

        if "state_transition" in ki.categories or "approve" in method_name or "reject" in method_name:
            distractors.insert(
                0,
                "直接修改状态即可，不需要检查当前状态是什么，反正最后都会变"
            )

        if "conflict_detection" in ki.categories:
            distractors.insert(
                0,
                "只需要比较开始时间是否相同，开始时间不同就不会有冲突"
            )

        return distractors[:3]

    # ===== 第 4 关：关键实现 =====

    def _generate_level4(self, modules: List[ModuleInfo], core_flows: List[CoreFlow],
                         key_implementations: Optional[object] = None) -> Optional[TrainingQuestion]:
        """
        第 4 关：关键实现思路
        问某个核心功能的实现思路应该是什么
        """
        # If we have deep analysis data, use the enhanced version
        if key_implementations and hasattr(key_implementations, 'top_implementations'):
            return self._generate_level4_deep(key_implementations, modules)

        # 找一个有核心度的模块
        core_module = next((m for m in modules if m.core_score >= 0.3), modules[0] if modules else None)
        if not core_module:
            return None

        # 找到一个关键方法（比如校验/检测类的）
        key_method = None
        for cls in core_module.classes:
            for m in cls.get("methods", []):
                if re.search(r"(check|verify|validate|detect|conflict)", m.name.lower()):
                    key_method = m
                    break
            if key_method:
                break

        if not key_method:
            # 没有校验类方法，就取方法最多的类的第一个方法
            for cls in core_module.classes:
                methods = [m for m in cls.get("methods", []) if not m.name.startswith("_")]
                if methods:
                    key_method = methods[0]
                    break

        if not key_method:
            return None

        method_name = key_method.name

        # 生成题目：这个方法的核心实现思路应该是什么
        question_text = (
            f"在「{core_module.name}」中，`{method_name}` 是一个关键功能。\n"
            f"请选择这个功能**最合理**的实现思路："
        )

        # 正确答案（根据方法名推断）
        if re.search(r"conflict", method_name.lower()):
            correct = (
                "遍历所有已有预约，逐一对比时间段，"
                "判断新预约与已有预约的时间是否重叠（开始时间 < 对方结束 且 结束时间 > 对方开始）"
            )
            distractors = [
                "只需要比较开始时间是否相同，开始时间不同就不会冲突",
                "用哈希表存储每个时间段，有冲突直接查表",
                "把时间转换成分钟数，然后用位运算判断重叠",
            ]
        elif re.search(r"(check|verify|validate)", method_name.lower()):
            correct = (
                "先校验参数合法性（非空、格式、范围等），"
                "再校验业务规则（状态、权限、约束等），全部通过才执行操作"
            )
            distractors = [
                "先执行操作，如果出错了再回滚",
                "只需要校验参数类型是否正确，业务逻辑交给数据库约束",
                "用 try-except 捕获所有异常，有异常就算不合法",
            ]
        elif re.search(r"(approve|reject)", method_name.lower()):
            correct = (
                "先检查当前状态是否为「待审批」，"
                "然后修改状态为「已批准/已拒绝」，记录审批人和时间"
            )
            distractors = [
                "直接修改状态即可，不需要检查当前状态",
                "只需要更新状态，审批人信息不重要",
                "审批和创建是同一个接口，传个参数区分就行",
            ]
        else:
            correct = (
                "先进行参数校验，然后执行核心操作，"
                "最后更新状态并返回结果"
            )
            distractors = [
                "直接操作数据就行，不需要校验",
                "把所有逻辑都写在一个函数里，不用拆分",
                "先返回结果，后台异步执行实际操作",
            ]

        all_options = [correct] + distractors
        random.shuffle(all_options)

        options = []
        correct_id = ""
        for i, text in enumerate(all_options):
            opt_id = chr(ord("A") + i)
            is_correct = text == correct
            if is_correct:
                correct_id = opt_id
            options.append(TrainingOption(id=opt_id, text=text, is_correct=is_correct))

        return TrainingQuestion(
            level=4,
            question_type="key_implementation",
            title="第4关：关键实现",
            description=question_text,
            options=options,
            correct_answers=[correct_id],
            explanation=(
                f"正确思路：{correct}\n\n"
                f"设计核心功能的实现时，需要考虑：\n"
                f"1. 前置条件是什么（状态、权限、参数）\n"
                f"2. 核心逻辑是什么（算法、操作）\n"
                f"3. 异常情况怎么处理（边界、回滚）\n"
                f"4. 结果怎么返回（成功/失败的标识）"
            ),
            knowledge_points=["算法设计", "边界条件", "状态管理"],
            difficulty=4,
        )
