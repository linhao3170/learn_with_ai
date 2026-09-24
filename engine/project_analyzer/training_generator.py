"""
项目级训练题生成器

生成引导式训练题（第 1~4 关）：
  第 1 关：功能拆分   —— 从项目自己的模块里选出**真正承担业务职责**的核心模块
  第 2 关：模块职责   —— 匹配模块和它的业务职责
                        （**每个够格的业务模块各一道**，见 ``_generate_level2``；
                         因此一次训练的题目数**不是固定的 4 道**）
  第 3 关：流程推演   —— 排序**真实业务**流程的步骤（排除初始化/样例数据流程）
  第 4 关：关键实现   —— 选择核心功能的实现思路（必须基于真实代码证据）

Sprint 0 改造说明（README5 第七章）
-----------------------------------
P0-04  删除了写死的域外干扰项（支付/即时通讯/报表/物流/游戏/视频/天气/音乐）
       和写死的域内答案（"遍历所有已有预约…时间重叠"）。
       **干扰项现在全部来自本项目自身的数据**（编排类 / 支撑类模块），
       不再凭空捏造业务模块。

P0-05  第 2 关不再拿 CRUD 分类标签（"新增/创建操作"）当"模块职责"，
       改为使用类 docstring 等**业务语义文本**。

P0-06  第 3 关用 ``engine/flow_filter.py`` 挑主流程，不再直接取 ``core_flows[0]``
       （那曾经是 ``LabSafetyApp Initialization Flow``）。

P0-08  第 1 关的"正确模块"不再等于"全部模块"；编排类（orchestrator）与
       支撑类模块变成干扰项 —— 这正是 README4 想训练的判断力。

P0-11  ``to_dict()`` 默认**不输出** ``correct_answers``；答案只在后端判题
       和教师预览模式里出现。

P0-14  随机源改为独立的 ``random.Random(seed)`` 实例，不再污染全局随机状态。

诚实边界
--------
- 第 4 关的干扰项是**通用反模式**（固定文案），不是从代码推导出来的；
  这一点必须如实说明。README5 Sprint 1 计划把它换成"从其他模块的真实实现
  中派生干扰项"。
- 任何一关如果**凑不出足够的数据**，就返回 ``None``（少一题），
  **绝不编造**。
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from .module_analyzer import ModuleInfo, CoreFlow
from ..flow_filter import pick_primary_flow, is_lifecycle_flow, sort_flows_business_first


# ============================================================
# 角色归类（P0-08）
# ============================================================

#: deep_analyzer 的角色取值（会覆盖 module_type）
_BUSINESS_ROLES = frozenset({"core", "business", "intermediate"})
#: 只有"装配/编排"和"边缘工具"这两类才**确定**不是业务模块。
#: ``intermediate`` 只是中心度居中，不代表它不承载业务 —— 把它算作业务模块
#: 更保守，避免把真实业务模块藏起来（例如 python-dotenv 的 variables/parser）。
_NON_BUSINESS_ROLES = frozenset({
    "orchestrator", "peripheral", "support",
    "utils", "infrastructure", "data_persistence", "api",
})

#: module_analyzer 关键词类型 → 角色归类
_KEYWORD_TYPE_ROLE = {
    "utils": "support",
    "data_persistence": "support",
    "api": "support",
}

#: ``_categorize_methods`` 产出的 CRUD 分类标签 —— 它们是**内部信号**，
#: 不是"业务职责"（P0-05）。展示职责时必须过滤掉。
_CRUD_LABELS = frozenset({
    "新增/创建操作", "删除/停用操作", "更新/修改操作", "查询/获取操作",
})

#: 每道职责题的干扰项数量（与第 1 关的"多选"不同，第 2 关是四选一）。
_DISTRACTOR_COUNT = 3

#: 第 2 关最多出几道题（README 优先级 4：以前"一道题只问一个模块"）。
#:
#: 为什么要有上限：一关一题，业务模块多的大项目（flask 12 域、urllib3 19 域）
#: 如果每个模块都出一题，学生会做到第 20 关还没有反馈 ——
#: 教学产品里"做不完"等于"没有反馈"。所以按核心度取前 N 个模块，取满即止。
#:
#: 为什么是 4：加上第 1/3/4 关，一次训练最多 7 关，一节课内做得完；
#: 而两个演示项目里业务模块最多的那个（lab_safety_assistant）恰好是 4 个 ——
#: **上限不会在演示项目上截断任何模块**，属于留有余量的设置。
#: 这是**教学编排参数**，不是业务词，因此留在引擎里（业务词才必须进 lexicon）。
_MAX_LEVEL2_QUESTIONS = 4

#: 第 3 关：**每条够格的业务流程各一道**（优先级 4 二轮）。上限同为 4。
#: 为什么：改造前只问"主流程"一条，`lab_safety_assistant` 有 6 条流程却只练到 1 条。
#: ⚠️ 只在**没有任何业务流**时才退回生命周期流程（与 ``pick_primary_flow`` 同一条口径）——
#: 教学生"核心业务 = 造样例数据"是教学性错误（README §19.1 #6）。
_MAX_LEVEL3_QUESTIONS = 4

#: 第 4 关：**每条够格的关键实现各一道**（优先级 4 二轮）。上限比第 2/3 关小。
#: 为什么更小：这一关的干扰项目前是**固定模板**（``source: template``，
#: 见 ``_generate_distractors_deep`` 的 TODO），题出得越多，"认出那几句反模式"
#: 的套路收益越大。所以只取最靠前的 3 条关键实现，并逐题轮换干扰项三元组。
_MAX_LEVEL4_QUESTIONS = 3


def _unique_question_title(base: str, used: Dict[str, int]) -> str:
    """给多题题型生成互不相同的标题（同名时追加 ``#2`` ``#3``）。

    为什么必须有：前端把 ``title`` 当作**关卡标签与雷达维度名**
    （``TrainingView.vue`` 会剥掉「第N关：」前缀），重名就分不清哪一题是哪一题 ——
    这正是 README §19.2 ⑰ 里"数据层没错、渲染层分不清"的那类问题。
    """
    used[base] = used.get(base, 0) + 1
    return base if used[base] == 1 else f"{base}#{used[base]}"


def _role_of(module: ModuleInfo) -> str:
    """把一个模块归成 ``business`` / ``orchestrator`` / ``support`` 之一。"""
    raw = (getattr(module, "module_type", "") or "").lower()
    if raw in _BUSINESS_ROLES:
        return "business"
    if raw in _NON_BUSINESS_ROLES:
        return "orchestrator" if raw == "orchestrator" else "support"
    if raw in _KEYWORD_TYPE_ROLE:
        return _KEYWORD_TYPE_ROLE[raw]
    # 未知类型：只要它有业务内容就当业务模块（宁可当选，也不把业务模块藏起来）
    return "business" if (module.method_count or 0) >= 4 else "support"


def _business_modules(modules: List[ModuleInfo]) -> List[ModuleInfo]:
    return [m for m in modules if _role_of(m) == "business"]


def _non_business_modules(modules: List[ModuleInfo]) -> List[ModuleInfo]:
    return [m for m in modules if _role_of(m) != "business"]


def _role_reason(module: ModuleInfo) -> str:
    """给一个非业务模块生成可解释的"为什么它不是核心业务模块"。"""
    role = _role_of(module)
    if role == "orchestrator":
        return "它不持有自己的业务状态，主要是把各个模块装配起来并编排调用"
    return "它提供的是通用/支撑能力，不承载具体的业务对象与状态"


def _business_text(module: ModuleInfo) -> str:
    """取模块的**业务语义**描述（P0-05：过滤掉 CRUD 分类标签）。"""
    parts: List[str] = []
    description = (getattr(module, "description", "") or "").strip()
    if description and description not in _CRUD_LABELS:
        parts.append(description)
    for item in getattr(module, "key_responsibilities", []) or []:
        text = (item or "").strip()
        if not text or text in _CRUD_LABELS:
            continue
        if text not in parts:
            parts.append(text)
    return "、".join(parts[:2])


def _step_label(step: dict) -> str:
    """取流程步骤的可读标签。

    以前依赖 ``s["name"].split("：")[0]``（全角冒号），步骤名格式一变题干就断。
    现在优先用 ``method`` 字段（纯标识符，永远存在），再退回 ``name``。
    """
    label = step.get("method") or step.get("name") or step.get("description") or "?"
    label = str(label)
    # 若 name 里带了「中文：英文」这种前缀，取后半段标识符
    if "：" in label:
        label = label.split("：")[-1]
    return label.strip() or "?"


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
    correct_answers: List[str] = field(default_factory=list)  # 仅后端判题/教师预览使用
    explanation: str = ""
    knowledge_points: List[str] = field(default_factory=list)
    difficulty: int = 1
    #: ``data_driven`` = 题干与选项都来自项目数据；``template`` = 含固定文案
    source: str = "data_driven"
    #: 代码证据（file:line），供"可定位"使用
    evidence: List[dict] = field(default_factory=list)

    def to_dict(self, include_answers: bool = False) -> dict:
        """序列化。

        P0-11：默认**不输出** ``correct_answers`` —— 答案不下发到浏览器。
        只有教师预览模式才用 ``include_answers=True``。
        """
        data = {
            "level": self.level,
            "question_type": self.question_type,
            "title": self.title,
            "description": self.description,
            "options": [{"id": o.id, "text": o.text, "hint": o.hint} for o in self.options],
            "explanation": self.explanation,
            "knowledge_points": self.knowledge_points,
            "difficulty": self.difficulty,
            "source": self.source,
            "evidence": self.evidence,
        }
        if include_answers:
            data["correct_answers"] = self.correct_answers
        return data


@dataclass
class TrainingSet:
    """一套完整的项目级训练"""
    project_name: str = ""
    project_description: str = ""
    questions: List[TrainingQuestion] = field(default_factory=list)

    def to_dict(self, include_answers: bool = False) -> dict:
        return {
            "project_name": self.project_name,
            "project_description": self.project_description,
            "questions": [q.to_dict(include_answers=include_answers) for q in self.questions],
        }

    def answer_key(self) -> dict:
        """判题答案表 —— **只允许在后端使用**。

        结构 ``{question_index: {"level": int, "answers": [...], "explanation": str}}``，
        键用下标而不是题目 ID，因为当前契约里题目没有稳定 ID
        （README5 Sprint 1 会补 ``checkpoint_id``）。
        """
        return {
            str(index): {
                "level": q.level,
                "question_type": q.question_type,
                "answers": list(q.correct_answers),
                "explanation": q.explanation,
                "knowledge_points": q.knowledge_points,
            }
            for index, q in enumerate(self.questions)
        }


def _unique_module_names(modules: List[ModuleInfo]) -> Dict[str, str]:
    """给每个模块一个**在本次训练里唯一**的显示名。

    为什么需要：lexicon 的中文名表是从同一个域（实验室安全）总结出来的，
    对别的项目会退化 —— 例如 python-dotenv 的 ``variables`` 与 ``parser``
    都落进 ``management`` 类型，于是都叫"管理模块"。那样出的题会出现
    "承担业务职责的模块有 2 个：管理模块、管理模块"，学生根本没法作答。

    处理方式（诚实且最小）：重名时把模块 id 附在后面，例如
    ``管理模块（variables）``。**不猜**更好的中文名 ——
    真正的按目录/docstring 命名是 Sprint 1 业务图谱引擎的职责。
    """
    counts: Dict[str, int] = {}
    for module in modules:
        counts[module.name] = counts.get(module.name, 0) + 1

    resolved: Dict[str, str] = {}
    for module in modules:
        display = module.name
        if counts.get(display, 0) > 1:
            tail = module.module_id.split(".")[-1]
            if tail and tail != display:
                display = f"{display}（{tail}）"
        resolved[module.module_id] = display
    return resolved


class TrainingGenerator:
    """项目级训练题生成器"""

    def __init__(self, seed: Optional[int] = 42):
        """P0-14：使用独立的 ``random.Random`` 实例，不再改全局随机状态。"""
        self._rng = random.Random(seed)
        #: P0-10：把绝对路径改写成项目内相对路径。由 ProjectAnalyzer 注入；
        #: 单独使用本生成器时退化为"只取文件名"。
        self._rel_path = lambda p: (str(p).replace("\\", "/").split("/")[-1] if p else "")
        #: 本次生成使用的唯一模块显示名（由 :func:`_unique_module_names` 填入）
        self._display_names: Dict[str, str] = {}

    def set_path_formatter(self, formatter) -> None:
        """注入路径格式化函数（P0-10）。"""
        if callable(formatter):
            self._rel_path = formatter

    def _name_of(self, module: ModuleInfo) -> str:
        """取模块在**本次训练里**的显示名（重名时带限定后缀）。"""
        return self._display_names.get(module.module_id, module.name)

    def generate(
        self,
        modules: List[ModuleInfo],
        core_flows: List[CoreFlow],
        project_name: str,
        project_description: str = "",
        key_implementations: Optional[object] = None,
    ) -> TrainingSet:
        """生成引导式训练题

        Args:
            modules: 模块列表（``module_type`` 已被 deep 分析的 role 覆盖）
            core_flows: 业务流程（已由 ProjectAnalyzer 按"业务优先"排序）
            project_name: 项目名称
            project_description: 项目描述
            key_implementations: 关键实现分析结果（可选，来自 deep_analyzer）
        """
        training = TrainingSet(
            project_name=project_name,
            project_description=project_description,
        )

        # 先算好唯一的模块显示名，避免"两个模块都叫管理模块"这种无法作答的题目
        self._display_names = _unique_module_names(modules)

        questions: List[TrainingQuestion] = []

        level1 = self._generate_level1(modules)
        if level1:
            questions.append(level1)

        # 第 2/3/4 关都可能出**多道**题（每个业务模块 / 每条流程 / 每条关键实现各一道），
        # 所以是 extend 不是 append。题目靠**下标**判题（``answer_key()`` 用 str(index)），
        # 因此顺序必须固定：第 1 关 → 第 2 关（可能多题）→ 第 3 关 → 第 4 关。
        questions.extend(self._generate_level2(modules))
        questions.extend(self._generate_level3(core_flows, modules))
        questions.extend(self._generate_level4(modules, core_flows, key_implementations))

        training.questions = questions
        return training

    # ===== 第 1 关：功能拆分 =====

    def _generate_level1(self, modules: List[ModuleInfo]) -> Optional[TrainingQuestion]:
        """第 1 关：从项目自身的模块里选出真正的核心业务模块。

        正确项 = 业务模块；干扰项 = 本项目自己的编排类 / 支撑类模块。
        **不使用任何域外捏造的模块。**
        """
        business = _business_modules(modules)
        non_business = _non_business_modules(modules)

        # 数据不足以构成一道有区分度的题 —— 诚实放弃，不编造（P0-04）。
        # 注意：非业务模块可能只有 1 个（例如"整个项目只有一个 app 装配模块"），
        # 这时题目依然成立（4 个正确 + 1 个错误），所以门槛是 1 而不是 2。
        if len(business) < 2 or len(non_business) < 1:
            return None

        distractor_count = min(len(non_business), max(2, len(business)))
        selected_distractors = non_business[:distractor_count]

        entries = [(m, True) for m in business] + [(m, False) for m in selected_distractors]
        self._rng.shuffle(entries)

        options: List[TrainingOption] = []
        correct_ids: List[str] = []
        for index, (module, is_correct) in enumerate(entries):
            option_id = chr(ord("A") + index)
            if is_correct:
                correct_ids.append(option_id)
            options.append(TrainingOption(id=option_id, text=self._name_of(module), is_correct=is_correct))

        wrong_lines = [
            f"  - 「{self._name_of(m)}」不算核心业务模块：{_role_reason(m)}"
            for m, _ in entries if not _
        ]
        explanation = (
            f"这个项目里承担具体业务职责的模块有 {len(business)} 个："
            f"{'、'.join(self._name_of(m) for m in business)}。\n\n"
            "以下几个模块同样存在于代码中，但它们不是**业务模块**：\n"
            + "\n".join(wrong_lines)
            + "\n\n区分「业务模块」和「支撑/装配模块」是业务逻辑训练的第一步："
              "业务模块管理具体的业务对象和状态，支撑模块只提供通用能力，"
              "装配模块只负责把大家连起来。"
        )

        return TrainingQuestion(
            level=1,
            question_type="module_selection",
            title="第1关：功能拆分",
            description=(
                f"这是一个包含 {len(modules)} 个代码模块的项目。\n"
                "请从以下选项中选出**真正承担业务职责的核心业务模块**（多选）。\n\n"
                "提示：不是所有代码模块都是业务模块 —— "
                "有些只负责装配和编排，有些只提供通用支撑能力，它们都不该算作核心业务模块。"
            ),
            options=options,
            correct_answers=correct_ids,
            explanation=explanation,
            knowledge_points=["业务模块识别", "模块类型区分", "职责边界"],
            difficulty=2,
            source="data_driven",
        )

    # ===== 第 2 关：模块职责匹配 =====

    def _generate_level2(self, modules: List[ModuleInfo]) -> List[TrainingQuestion]:
        """第 2 关：模块职责匹配（业务语义描述，不用 CRUD 分类）。

        返回**一列表**而不是一道题：每个够格的业务模块各出一题
        （README 优先级 4：以前只问核心度最高的那一个模块，
        其余模块的职责学生一个都没练到）。

        出题门槛（**凑不出就不出这一题，绝不编造**）：

        - 目标模块必须有非空的业务语义文本（``_business_text``）；
        - 必须能从**其他业务模块**里凑出 ``_DISTRACTOR_COUNT`` 个互不相同、
          且不等于正确答案的干扰项。

        干扰项只取**业务模块**的文本，与改造前的口径一致：
        这样"四选一"练的仍然是"业务模块之间职责怎么区分"，
        不会混进支撑/装配模块的描述。

        上限见 ``_MAX_LEVEL2_QUESTIONS``；排序是"核心度降序 + module_id 升序"，
        与改造前的选主体规则一致，因此**确定性不变**（同分不再靠运气，靠 id）。
        """
        business = _business_modules(modules)
        if not business:
            return []

        ranked = sorted(business, key=lambda m: (-float(m.core_score or 0.0), m.module_id))
        texts = {m.module_id: _business_text(m) for m in ranked}

        questions: List[TrainingQuestion] = []
        for target in ranked[:_MAX_LEVEL2_QUESTIONS]:
            correct_text = texts.get(target.module_id, "")
            if not correct_text:
                # 没有业务语义文本就没有正确答案可言（P0-05：不许退回 CRUD 标签）
                continue

            distractors: List[str] = []
            for other in ranked:
                if other.module_id == target.module_id:
                    continue
                text = texts.get(other.module_id, "")
                if text and text != correct_text and text not in distractors:
                    distractors.append(text)
                if len(distractors) >= _DISTRACTOR_COUNT:
                    break

            # 凑不出 3 个来自真实模块的干扰项就放弃这一题（不再用编造的通用描述填充）
            if len(distractors) < _DISTRACTOR_COUNT:
                continue

            question = self._build_level2_question(target, correct_text, distractors)
            questions.append(question)

        return questions

    def _build_level2_question(
        self, target: ModuleInfo, correct_text: str, distractors: List[str]
    ) -> TrainingQuestion:
        """把"目标模块 + 正确答案 + 三个真实干扰项"装成一道四选一。"""
        all_options = [correct_text] + distractors
        self._rng.shuffle(all_options)

        options: List[TrainingOption] = []
        correct_id = ""
        for index, text in enumerate(all_options):
            option_id = chr(ord("A") + index)
            is_correct = text == correct_text
            if is_correct:
                correct_id = option_id
            options.append(TrainingOption(id=option_id, text=text, is_correct=is_correct))

        target_name = self._name_of(target)
        return TrainingQuestion(
            level=2,
            question_type="responsibility_match",
            title=f"第2关：模块职责·{target_name}",
            description=(
                f"**「{target_name}」** 的主要职责是什么？\n\n"
                "请从下面选项中选出最准确的描述。"
            ),
            options=options,
            correct_answers=[correct_id],
            explanation=(
                f"「{target_name}」的职责是：{correct_text}。\n\n"
                "理解模块职责的关键是看它对外提供什么能力、管理什么数据。"
                "一个好的模块应该职责单一，只负责一类相关的功能。"
            ),
            knowledge_points=["模块职责", "单一职责", "接口设计"],
            difficulty=2,
            source="data_driven",
        )

    # ===== 第 3 关：流程推演 =====

    def _generate_level3(
        self, core_flows: List[CoreFlow], modules: List[ModuleInfo]
    ) -> List[TrainingQuestion]:
        """第 3 关：真实业务流程推演（**每条够格的流程各一道**）。

        P0-06：用 ``flow_filter`` 挑主流程，避免把"初始化/造样例数据"当成核心业务教。

        两种题型（都**完全由数据驱动**）：

        - 流程 ≥ 3 步  → 全流程排序题；
        - 流程 = 2 步  → "下一步会调用什么"题，干扰项取自本项目**其他流程**的真实步骤。

        为什么需要第二种：本项目里真正有 3 步以上的流程往往只有初始化流程；
        真实业务流（``提交预约 → 冲突检测``）常常只有 2 步。
        以前的做法是"退回初始化流程"（教学性错误），
        现在改为换一种合法的题型，**既不编造，也不拿初始化流程顶替**。

        优先级 4 二轮（本函数）把"只出主流程一道题"改成**每条流程各一道**：
        改造前 `lab_safety_assistant` 有 6 条流程却只练到 1 条，其余 5 条的顺序
        学生一题都做不到。现在按 ``flow_filter.sort_flows_business_first`` 的
        **唯一排序口径**逐条出题（第一条与旧行为完全一致），上限见
        ``_MAX_LEVEL3_QUESTIONS``；**凑不出 3 个真实干扰项/选项的流程直接跳过，
        不编造**（与第 2 关同一条纪律）。
        """
        if not core_flows:
            return []

        ordered_flows = sort_flows_business_first(core_flows)
        # 业务流优先；**只有一条业务流都没有**时才退回生命周期流程
        # （"这个项目只有初始化流程"本身是有效信息，但绝不能拿它当核心业务流教）。
        business_flows = [flow for flow in ordered_flows if not is_lifecycle_flow(flow)]
        candidates = business_flows or ordered_flows

        questions: List[TrainingQuestion] = []
        used_titles: Dict[str, int] = {}

        for flow in candidates:
            if len(questions) >= _MAX_LEVEL3_QUESTIONS:
                break

            steps = list(getattr(flow, "steps", []) or [])
            ordered = sorted(steps, key=lambda s: s.get("order", 0))

            question: Optional[TrainingQuestion] = None
            if len(ordered) >= 3:
                question = self._flow_ordering_question(flow, ordered)
            elif len(ordered) == 2:
                question = self._flow_next_step_question(flow, ordered, core_flows)
            if question is None:
                continue

            # 标题必须能区分是哪一条流程：前端把它当关卡标签与雷达维度名，
            # 多道题同名就分不清（README §19.2 ⑰ 就是这么被抓出来的）。
            question.title = _unique_question_title(
                f"第3关：流程推演·{getattr(flow, 'name', '') or '未命名流程'}", used_titles
            )
            questions.append(question)

        return questions

    def _flow_ordering_question(
        self, flow, ordered: List[dict]
    ) -> Optional[TrainingQuestion]:
        """全流程排序题（步骤 ≥ 3）。"""
        labels = self._unique_step_labels(ordered)
        if labels is None:
            return None

        correct_order = " → ".join(labels)

        def make_wrong_order(swap_count: int) -> str:
            wrong = labels.copy()
            for _ in range(swap_count):
                i, j = self._rng.sample(range(len(wrong)), 2)
                wrong[i], wrong[j] = wrong[j], wrong[i]
            return " → ".join(wrong)

        wrong_orders: List[str] = []
        for swap_count in (2, 1, 3):
            candidate = make_wrong_order(swap_count)
            if candidate != correct_order and candidate not in wrong_orders:
                wrong_orders.append(candidate)
        if len(wrong_orders) < 3:
            return None

        all_options = [correct_order] + wrong_orders[:3]
        self._rng.shuffle(all_options)

        options: List[TrainingOption] = []
        correct_id = ""
        for index, text in enumerate(all_options):
            option_id = chr(ord("A") + index)
            is_correct = text == correct_order
            if is_correct:
                correct_id = option_id
            options.append(TrainingOption(id=option_id, text=text, is_correct=is_correct))

        return TrainingQuestion(
            level=3,
            question_type="flow_ordering",
            title="第3关：流程推演",
            description=(
                f"**「{flow.name}」** 的正确执行顺序是什么？\n\n"
                "请思考一个完整的业务流程应该先做什么、后做什么，"
                "选出步骤顺序正确的选项。\n\n"
                f"涉及模块：{', '.join(getattr(flow, 'involved_modules', []) or [])}"
            ),
            options=options,
            correct_answers=[correct_id],
            explanation=(
                f"正确顺序是：{correct_order}\n\n"
                "理解业务流程的关键是思考「数据和状态是怎么变化的」："
                "什么操作会触发状态改变？改变之前需要什么前提？"
                "校验通常在操作之前，审批通常在创建之后。"
                + self._lifecycle_note(flow)
            ),
            knowledge_points=["业务流程", "状态流转", "数据流"],
            difficulty=3,
            source="data_driven",
            evidence=self._flow_evidence(ordered),
        )

    def _flow_next_step_question(
        self, flow, ordered: List[dict], all_flows: List[CoreFlow]
    ) -> Optional[TrainingQuestion]:
        """"下一步会调用什么"题（步骤 = 2）。

        干扰项 = 本项目**其他流程**里真实出现过的步骤标签（data_driven）。
        """
        first, second = ordered[0], ordered[1]
        first_label = _step_label(first)
        correct_label = _step_label(second)
        if not first_label or not correct_label or first_label == correct_label:
            return None

        pool: List[str] = []
        for other in all_flows:
            for step in (getattr(other, "steps", []) or []):
                label = _step_label(step)
                if label and label not in (correct_label, first_label) and label not in pool:
                    pool.append(label)
        if len(pool) < 3:
            return None

        distractors = pool[:3]
        all_options = [correct_label] + distractors
        self._rng.shuffle(all_options)

        options: List[TrainingOption] = []
        correct_id = ""
        for index, text in enumerate(all_options):
            option_id = chr(ord("A") + index)
            is_correct = text == correct_label
            if is_correct:
                correct_id = option_id
            options.append(TrainingOption(id=option_id, text=text, is_correct=is_correct))

        origin = {
            _step_label(step): step.get("module", "")
            for other in all_flows
            for step in (getattr(other, "steps", []) or [])
        }

        return TrainingQuestion(
            level=3,
            question_type="flow_next_step",
            title="第3关：流程推演",
            description=(
                f"在流程 **「{flow.name}」** 中，`{first_label}` 执行之后，"
                "接下来会调用哪一个方法？\n\n"
                "请从下面选项中选出**本项目真实存在的下一步**。\n\n"
                f"涉及模块：{', '.join(getattr(flow, 'involved_modules', []) or [])}"
            ),
            options=options,
            correct_answers=[correct_id],
            explanation=(
                f"正确顺序是：{first_label} → {correct_label}\n\n"
                f"`{correct_label}` 位于模块「{origin.get(correct_label, '?')}」。\n\n"
                "理解业务流程的关键是思考「数据和状态是怎么变化的」："
                "什么操作会触发状态改变？改变之前需要什么前提？"
                + self._lifecycle_note(flow)
            ),
            knowledge_points=["业务流程", "调用顺序", "模块协作"],
            difficulty=2,
            source="data_driven",
            evidence=self._flow_evidence(ordered),
        )

    @staticmethod
    def _flow_evidence(ordered: List[dict]) -> List[dict]:
        """流程步骤的代码证据（file 由上层统一改写成相对路径）。"""
        return [
            {
                "step": _step_label(step),
                "module": step.get("module", ""),
                "file": step.get("file", ""),
                "line": step.get("line", 0),
            }
            for step in ordered
            if step.get("line")
        ]

    @staticmethod
    def _lifecycle_note(flow) -> str:
        """当主流程仍是生命周期流程时，必须在题干里说明（诚实边界）。"""
        if not is_lifecycle_flow(flow):
            return ""
        return (
            "\n\n⚠️ 注意：这是本项目**唯一**可用于推演的流程，"
            "而它的名称特征像是初始化/样例数据流程。"
            "请把它当作「数据准备过程」而不是「用户业务过程」来理解。"
        )


    # ===== 第 4 关：关键实现 =====

    def _generate_level4(
        self,
        modules: List[ModuleInfo],
        core_flows: List[CoreFlow],
        key_implementations: Optional[object] = None,
    ) -> List[TrainingQuestion]:
        """第 4 关：关键实现思路（**每条够格的关键实现各一道**）。

        只有拿到 **deep_analyzer 的真实证据** 才出题。
        以前在缺少证据时会退回一套写死的模板答案
        （如"遍历所有已有预约…判断时间是否重叠"），
        对非预约类项目就是**错误答案**，因此已删除该分支（P0-04）。

        优先级 4 二轮（本函数）把"只问最重要那一条实现"改成**逐条出题**：
        改造前 `lab_safety_assistant` 有 10 条关键实现却只练到 1 条。
        上限见 ``_MAX_LEVEL4_QUESTIONS``，**凑不出 3 个干扰项的实现直接跳过**。
        """
        if key_implementations is not None and hasattr(key_implementations, "top_implementations"):
            return self._generate_level4_deep(key_implementations, modules)
        return []

    def _generate_level4_deep(
        self, key_implementations, modules: List[ModuleInfo]
    ) -> List[TrainingQuestion]:
        """基于真实代码分析的关键实现题（逐条）。"""
        top_kis = key_implementations.top_implementations
        if not top_kis:
            return []

        questions: List[TrainingQuestion] = []
        used_titles: Dict[str, int] = {}
        for index, ki in enumerate(top_kis):
            if len(questions) >= _MAX_LEVEL4_QUESTIONS:
                break
            question = self._level4_question_for(ki, modules, index)
            if question is None:
                continue
            # 标题带上方法名：多道题必须能区分（前端当关卡标签与雷达维度名）
            question.title = _unique_question_title(
                f"第4关：关键实现·{ki.method_name}", used_titles
            )
            questions.append(question)
        return questions

    def _level4_question_for(
        self, ki, modules: List[ModuleInfo], index: int
    ) -> Optional[TrainingQuestion]:
        """为**单条**关键实现构造一道题（``index`` 用于轮换干扰项三元组）。"""
        module_display = ki.module_name
        for module in modules:
            if module.module_id == ki.module_name:
                module_display = module.name
                break

        method_name = ki.method_name

        question_parts = [f"在「{module_display}」中，`{method_name}` 是一个关键方法。\n"]
        if ki.design_approach:
            question_parts.append(f"它的主要特点是：{ki.design_approach}。\n")
        question_parts.append("请选择这个功能**最合理**的实现思路：")

        correct_parts: List[str] = []
        if ki.validation_checks:
            checks = "、".join(ki.validation_checks[:3])
            correct_parts.append(f"先进行边界条件校验（{checks}）")
        if "algorithmic" in ki.categories and ki.loop_count > 0:
            correct_parts.append("通过遍历/循环实现核心算法逻辑")
        if ki.state_writes:
            writes = "、".join(self._public_state_names(ki.state_writes[:3]))
            if writes:
                correct_parts.append(f"修改状态字段（{writes}）")
        if ki.error_handling:
            errors = "、".join([e.split(":")[0] for e in ki.error_handling[:3]])
            correct_parts.append(f"非法情况抛出异常（{errors}）")

        if not correct_parts:
            return None

        correct = "；".join(correct_parts)
        distractors = self._generate_distractors_deep(ki)
        if len(distractors) < 3:
            return None

        # ⚠️ 干扰项是**通用反模式**（固定文案，``source: "template"``，见
        # ``_generate_distractors_deep`` 的 TODO）。多道题共用同一组干扰项时，
        # 学生只要认出"那三句反模式"就能用排除法选出正确项 —— 所以这里按题号
        # **轮换三元组**（4 条里取 3 条，共 4 种组合），让每道题的选项集合不同。
        # 这**降低**了而不是消除了可被套路的风险：只要干扰项还是模板，
        # 就不能把它宣传成"从代码里推导出来的干扰项"。
        start = index % len(distractors)
        rotated = [distractors[(start + offset) % len(distractors)] for offset in range(3)]

        all_options = [correct] + rotated
        self._rng.shuffle(all_options)

        options: List[TrainingOption] = []
        correct_id = ""
        for index, text in enumerate(all_options):
            option_id = chr(ord("A") + index)
            is_correct = text == correct
            if is_correct:
                correct_id = option_id
            options.append(TrainingOption(id=option_id, text=text, is_correct=is_correct))

        explanation_parts = [f"正确思路：{correct}\n", "\n代码证据："]
        for reason in (ki.importance_reasons or [])[:3]:
            explanation_parts.append(f"  - {reason}")
        if ki.error_handling:
            explanation_parts.append(f"  - 抛出 {len(ki.error_handling)} 种异常处理非法输入")
        if ki.state_writes:
            explanation_parts.append(f"  - 修改 {len(ki.state_writes)} 个状态字段")
        explanation_parts.append(
            f"  - 代码位于 {self._rel_path(ki.filepath)} 第 {ki.start_line}-{ki.end_line} 行"
        )
        explanation_parts.append(
            "\n⚠️ 本关的三个干扰项是**通用反模式**（固定文案），"
            "不是从代码里推导出来的；正确项才是由真实代码证据生成的。"
            "（多道题之间会轮换这三条，避免用排除法认出固定的一组）"
        )

        knowledge_points: List[str] = []
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
            description="\n".join(question_parts),
            options=options,
            correct_answers=[correct_id],
            explanation="\n".join(explanation_parts),
            knowledge_points=knowledge_points,
            difficulty=4,
            # 干扰项是固定文案，因此诚实标为 template
            source="template",
            evidence=[{
                "file": ki.filepath,
                "start_line": ki.start_line,
                "end_line": ki.end_line,
                "symbol": ki.method_name,
            }],
        )

    @staticmethod
    def _unique_step_labels(steps: List[dict]) -> Optional[List[str]]:
        """生成互不相同的步骤标签，让排序题可判定。

        分级策略（越往后信息越多，但一定保证唯一）：

        1. 只用 ``method`` 名；
        2. 有重名 → 用 ``module.method``；
        3. 仍有重名 → 追加 ``#序号``。

        返回 ``None`` 表示连序号都没法区分（理论上不会发生）。
        """
        base = [_step_label(step) for step in steps]
        if len(set(base)) == len(base):
            return base

        with_module = [
            f"{step.get('module', '?')}.{_step_label(step)}" for step in steps
        ]
        if len(set(with_module)) == len(with_module):
            return with_module

        seen: Dict[str, int] = {}
        final: List[str] = []
        for label in with_module:
            seen[label] = seen.get(label, 0) + 1
            final.append(f"{label}#{seen[label]}")
        if len(set(final)) != len(final):
            return None
        return final

    @staticmethod
    def _public_state_names(names: List[str]) -> List[str]:
        """过滤掉状态追踪的内部标记（P0-07）。

        ``state_tracker`` 用 ``f"{attr}._inferred_"`` 记录"字典的某个 key 被写过"
        这种推断，属于**内部实现细节**，绝不允许出现在学生看到的题干里。
        """
        cleaned = []
        for name in names:
            text = str(name)
            if text.endswith("._inferred_") or text == "_inferred_":
                continue
            text = text.replace("._inferred_", "")
            if text and text not in cleaned:
                cleaned.append(text)
        return cleaned

    def _generate_distractors_deep(self, ki) -> List[str]:
        """第 4 关的干扰项：**通用反模式**。

        TODO(Sprint 1)：改为从"其他模块的真实实现"派生干扰项，
        让它也变成 data_driven。当前明确标记为固定文案。
        """
        return [
            "直接操作数据即可，不需要校验参数和状态，让调用方自己保证合法",
            "把所有逻辑都写在一个大函数里，不用拆分成小方法，一次性完成所有操作",
            "先返回结果，后台异步执行实际操作，这样性能更好",
            "用 try-except 捕获所有异常，有异常就返回 None，不区分错误类型",
        ]
