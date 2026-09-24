"""
业务逻辑培养引擎 - 核心数据模型（数据契约层，不是引擎实现）

定义业务图谱、模块卡片、训练计划、设计提交、评价结果等数据结构。
所有模型都支持 to_dict() 序列化，方便前后端传输。

契约版本（README5 §4.1）：
  本文件是业务的**规范性契约**来源。`to_dict()` 输出 README3 §6.1 的规范字段名
  （`name_cn` / `does_not` / `module_cards`），Python 属性名保持不变
  （`name` / `not_responsible` / `modules`），映射只在 `to_dict()` 里做一次。
  每个 `to_dict()` 都带 `contract_version`，前端启动时校验，不匹配就拒绝渲染。

注意：本文件只有数据模型，没有算法。业务图谱构建实现计划放在
`engine/business_graph/`（见 README5 §2.4 / §3.1）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple


# 数据契约版本（README5 §4.1：前端启动时校验，不匹配拒绝渲染）
CONTRACT_VERSION = "1.0"


# ============================================================
# 业务逻辑图谱 - 多级模块树
# ============================================================

@dataclass
class BusinessModule:
    """
    业务模块节点（支持多级嵌套）

    对应 README4 中的"业务逻辑图谱"节点，是学生学习的核心对象。
    每个模块对应一张模块卡片，模块之间通过父子关系形成层级树。
    """
    module_id: str                          # 唯一标识
    name: str                               # 中文名称
    level: int = 1                          # 层级深度（1=一级模块，2=二级...）
    parent_id: Optional[str] = None         # 父模块ID
    children: List[str] = field(default_factory=list)  # 子模块ID列表
    module_type: str = "business"           # 模块类型: core / support / optional / infrastructure
    tags: List[str] = field(default_factory=list)      # 标签（如"核心模块"、"支撑模块"）

    # 模块卡片内容
    objective: str = ""                     # 模块目标（一句话描述）
    inputs: List[str] = field(default_factory=list)    # 输入
    outputs: List[str] = field(default_factory=list)   # 输出
    business_rules: List[str] = field(default_factory=list)  # 业务规则
    upstream_modules: List[str] = field(default_factory=list)  # 上游模块
    downstream_modules: List[str] = field(default_factory=list)  # 下游模块
    state_changes: List[str] = field(default_factory=list)     # 状态变化
    not_responsible: List[str] = field(default_factory=list)   # 不负责什么（边界训练）
    exceptions: List[str] = field(default_factory=list)        # 异常情况

    # 代码证据（双图对齐）
    code_evidence: Dict = field(default_factory=dict)  # 关联的代码实现证据
    confidence: str = "inferred"           # 已确认 / 系统推断 / 待教师审核

    def to_dict(self) -> dict:
        return {
            "contract_version": CONTRACT_VERSION,
            "module_id": self.module_id,
            # 契约别名（README3 §6.1 兼容）：属性名仍是 name，对外输出 name_cn
            "name_cn": self.name,
            "level": self.level,
            "parent_id": self.parent_id,
            "children": self.children,
            "module_type": self.module_type,
            "tags": self.tags,
            "objective": self.objective,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "business_rules": self.business_rules,
            "upstream_modules": self.upstream_modules,
            "downstream_modules": self.downstream_modules,
            "state_changes": self.state_changes,
            # 契约别名（README3 §6.1 兼容）：属性名仍是 not_responsible，对外输出 does_not
            "does_not": self.not_responsible,
            "exceptions": self.exceptions,
            "code_evidence": self.code_evidence,
            "confidence": self.confidence,
        }


@dataclass
class BusinessGraph:
    """
    业务逻辑图谱

    一张完整的项目业务模块树，包含所有层级的模块和它们之间的关系。
    这是学生学习的"第一张图"，代码实现图谱是"第二张图"。
    """
    project_name: str = ""
    project_description: str = ""
    modules: Dict[str, BusinessModule] = field(default_factory=dict)
    root_modules: List[str] = field(default_factory=list)  # 一级模块ID列表
    max_depth: int = 1
    total_module_count: int = 0
    complexity_score: float = 0.0

    def get_module(self, module_id: str) -> Optional[BusinessModule]:
        return self.modules.get(module_id)

    def get_children(self, module_id: str) -> List[BusinessModule]:
        """获取某个模块的直接子模块"""
        m = self.modules.get(module_id)
        if not m:
            return []
        return [self.modules[cid] for cid in m.children if cid in self.modules]

    def get_root_modules(self) -> List[BusinessModule]:
        """获取所有一级模块"""
        return [self.modules[rid] for rid in self.root_modules if rid in self.modules]

    def get_all_descendants(self, module_id: str) -> List[BusinessModule]:
        """获取某个模块的所有后代模块（递归）"""
        result = []
        for child in self.get_children(module_id):
            result.append(child)
            result.extend(self.get_all_descendants(child.module_id))
        return result

    def get_core_modules(self) -> List[BusinessModule]:
        """获取所有核心业务模块"""
        return [m for m in self.modules.values() if m.module_type == "core"]

    def to_dict(self) -> dict:
        return {
            "contract_version": CONTRACT_VERSION,
            "project_name": self.project_name,
            "project_description": self.project_description,
            # 契约别名（README3 §6.1 兼容）：属性名仍是 modules，对外输出 module_cards
            "module_cards": {mid: m.to_dict() for mid, m in self.modules.items()},
            "root_modules": self.root_modules,
            "max_depth": self.max_depth,
            "total_module_count": self.total_module_count,
            "complexity_score": round(self.complexity_score, 2),
        }


# ============================================================
# 业务流程
# ============================================================

@dataclass
class BusinessFlowStep:
    """业务流程中的一个步骤"""
    step_id: str
    module_id: str                          # 对应业务模块
    module_name: str                        # 模块名称（冗余存储，方便展示）
    action: str                             # 动作描述
    order: int                              # 顺序
    is_branch: bool = False                 # 是否是分支点
    branch_condition: str = ""              # 分支条件
    is_state_change: bool = False           # 是否触发状态变化
    data_passed: List[str] = field(default_factory=list)  # 传递的数据

    def to_dict(self) -> dict:
        return {
            "contract_version": CONTRACT_VERSION,
            "step_id": self.step_id,
            "module_id": self.module_id,
            "module_name": self.module_name,
            "action": self.action,
            "order": self.order,
            "is_branch": self.is_branch,
            "branch_condition": self.branch_condition,
            "is_state_change": self.is_state_change,
            "data_passed": self.data_passed,
        }


@dataclass
class BusinessFlow:
    """
    一条完整的业务流程

    描述一个具体场景下，多个业务模块如何协作完成一个业务目标。
    用于第三阶段"业务流程推演"训练。
    """
    flow_id: str
    name: str                               # 流程名称
    description: str                        # 流程描述（场景）
    steps: List[BusinessFlowStep] = field(default_factory=list)
    involved_modules: List[str] = field(default_factory=list)
    flow_type: str = "normal"               # normal / exception / edge_case
    difficulty: int = 1                     # 难度等级

    def to_dict(self) -> dict:
        return {
            "contract_version": CONTRACT_VERSION,
            "flow_id": self.flow_id,
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "involved_modules": self.involved_modules,
            "flow_type": self.flow_type,
            "difficulty": self.difficulty,
        }


# ============================================================
# 教师标准逻辑图
# ============================================================

@dataclass
class GoldGraph:
    """
    教师标准逻辑图

    不是"唯一正确答案"，而是评价学生设计的参照系：
    - 必须存在的模块
    - 可以替代的结构
    - 禁止合并的节点
    - 必须存在的依赖关系

    这是 README4 的核心创新之一：允许多种合理设计，
    而不是用固定答案限制学生思维。
    """
    graph_id: str = ""
    project_name: str = ""

    # 必须存在的核心业务能力（按业务语义匹配，不按名称匹配）
    required_capabilities: List[str] = field(default_factory=list)

    # 可选模块（存在加分，不存在不扣分）
    optional_modules: List[str] = field(default_factory=list)

    # 可接受的替代结构（"审批可以独立成模块，也可以归入借用流程"这种）
    acceptable_alternatives: List[Dict] = field(default_factory=list)

    # 禁止合并的节点对（两个模块职责差异大，不能合并）
    forbidden_merges: List[Tuple[str, str]] = field(default_factory=list)

    # 必须存在的依赖/协作关系
    required_relations: List[Dict] = field(default_factory=list)

    # 必须处理的异常/边界场景
    required_edge_cases: List[str] = field(default_factory=list)

    # 参考的标准模块结构（用于评分参照）
    reference_modules: Dict[str, Dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "contract_version": CONTRACT_VERSION,
            "graph_id": self.graph_id,
            "project_name": self.project_name,
            "required_capabilities": self.required_capabilities,
            "optional_modules": self.optional_modules,
            "acceptable_alternatives": self.acceptable_alternatives,
            "forbidden_merges": [list(pair) for pair in self.forbidden_merges],
            "required_relations": self.required_relations,
            "required_edge_cases": self.required_edge_cases,
            "reference_modules": self.reference_modules,
        }


# ============================================================
# 学生设计提交
# ============================================================

@dataclass
class StudentModule:
    """学生设计的一个模块"""
    module_id: str
    name: str
    objective: str = ""
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    business_rules: List[str] = field(default_factory=list)
    state_changes: List[str] = field(default_factory=list)
    design_reason: str = ""                 # 设计理由

    def to_dict(self) -> dict:
        return {
            "contract_version": CONTRACT_VERSION,
            "module_id": self.module_id,
            # 契约别名（README3 §6.1 兼容）：属性名仍是 name，对外输出 name_cn
            "name_cn": self.name,
            "objective": self.objective,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "parent_id": self.parent_id,
            "children": self.children,
            "depends_on": self.depends_on,
            "business_rules": self.business_rules,
            "state_changes": self.state_changes,
            "design_reason": self.design_reason,
        }


@dataclass
class DesignSubmission:
    """
    学生模块设计提交

    学生在第四阶段"自己设计模块"时提交的完整设计方案。
    系统会基于 GoldGraph 对这个提交进行六维评价。
    """
    submission_id: str = ""
    student_id: str = ""
    project_name: str = ""
    design_prompt: str = ""                  # 设计题目/需求描述
    modules: Dict[str, StudentModule] = field(default_factory=dict)
    root_modules: List[str] = field(default_factory=list)
    relations: List[Dict] = field(default_factory=list)  # 模块间关系
    flow_designs: List[Dict] = field(default_factory=list)  # 学生设计的业务流程
    design_rationale: str = ""               # 整体设计思路说明

    def get_module(self, module_id: str) -> Optional[StudentModule]:
        return self.modules.get(module_id)

    def get_all_modules(self) -> List[StudentModule]:
        return list(self.modules.values())

    def to_dict(self) -> dict:
        return {
            "contract_version": CONTRACT_VERSION,
            "submission_id": self.submission_id,
            "student_id": self.student_id,
            "project_name": self.project_name,
            "design_prompt": self.design_prompt,
            "modules": {mid: m.to_dict() for mid, m in self.modules.items()},
            "root_modules": self.root_modules,
            "relations": self.relations,
            "flow_designs": self.flow_designs,
            "design_rationale": self.design_rationale,
        }


# ============================================================
# 评价结果 - 六维评价
# ============================================================

@dataclass
class DimensionScore:
    """单个评价维度的得分和反馈"""
    dimension: str                           # 维度名称
    weight: float                            # 权重
    score: float                             # 得分 0-100
    max_score: float = 100.0
    findings: List[str] = field(default_factory=list)  # 具体发现（优点）
    issues: List[str] = field(default_factory=list)    # 问题/改进建议
    evidence: List[str] = field(default_factory=list)  # 评价依据

    def to_dict(self) -> dict:
        return {
            "contract_version": CONTRACT_VERSION,
            "dimension": self.dimension,
            "weight": self.weight,
            "score": round(self.score, 1),
            "max_score": self.max_score,
            "findings": self.findings,
            "issues": self.issues,
            "evidence": self.evidence,
        }


@dataclass
class EvaluationResult:
    """
    设计方案评价结果

    对应 README4 第五阶段的六维评价：
    1. 核心需求覆盖度 (25%)
    2. 模块职责清晰度 (20%)
    3. 层级结构合理性 (15%)
    4. 模块依赖和流程完整性 (20%)
    5. 异常和边界情况 (10%)
    6. 设计理由与证据 (10%)
    """
    submission_id: str = ""
    overall_score: float = 0.0
    overall_feedback: str = ""
    dimensions: List[DimensionScore] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)      # 设计亮点
    improvements: List[str] = field(default_factory=list)   # 主要改进点
    grade: str = ""                           # 等级：优秀 / 良好 / 合格 / 需改进

    def get_dimension(self, name: str) -> Optional[DimensionScore]:
        for d in self.dimensions:
            if d.dimension == name:
                return d
        return None

    def to_dict(self) -> dict:
        return {
            "contract_version": CONTRACT_VERSION,
            "submission_id": self.submission_id,
            "overall_score": round(self.overall_score, 1),
            "overall_feedback": self.overall_feedback,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "strengths": self.strengths,
            "improvements": self.improvements,
            "grade": self.grade,
        }


# ============================================================
# 训练计划
# ============================================================

@dataclass
class TrainingStage:
    """一个训练阶段"""
    stage_id: str
    stage_name: str                          # 阶段名称
    stage_number: int                        # 第几阶段
    description: str                         # 阶段目标说明
    tasks: List[Dict] = field(default_factory=list)     # 具体任务
    estimated_minutes: int = 20              # 预计用时（分钟）
    is_required: bool = True                 # 是否必学

    def to_dict(self) -> dict:
        return {
            "contract_version": CONTRACT_VERSION,
            "stage_id": self.stage_id,
            "stage_name": self.stage_name,
            "stage_number": self.stage_number,
            "description": self.description,
            "tasks": self.tasks,
            "estimated_minutes": self.estimated_minutes,
            "is_required": self.is_required,
        }


@dataclass
class TrainingPlan:
    """
    完整的业务逻辑训练计划

    对应 README4 的五阶段学习流程：
    1. 项目认知
    2. 模块递进学习
    3. 业务流程推演
    4. 学生自主设计模块
    5. 系统评审与重构挑战
    """
    plan_id: str = ""
    project_name: str = ""
    complexity_level: int = 1                # 项目复杂度等级 1-4
    complexity_description: str = ""         # 复杂度描述
    stages: List[TrainingStage] = field(default_factory=list)
    total_estimated_minutes: int = 0
    core_modules_count: int = 0
    total_modules_count: int = 0

    def get_stage(self, stage_number: int) -> Optional[TrainingStage]:
        for s in self.stages:
            if s.stage_number == stage_number:
                return s
        return None

    def to_dict(self) -> dict:
        return {
            "contract_version": CONTRACT_VERSION,
            "plan_id": self.plan_id,
            "project_name": self.project_name,
            "complexity_level": self.complexity_level,
            "complexity_description": self.complexity_description,
            "stages": [s.to_dict() for s in self.stages],
            "total_estimated_minutes": self.total_estimated_minutes,
            "core_modules_count": self.core_modules_count,
            "total_modules_count": self.total_modules_count,
        }


# ============================================================
# 流程推演场景
# ============================================================

@dataclass
class FlowScenario:
    """流程推演场景"""
    scenario_id: str
    title: str
    description: str                         # 场景描述
    given_modules: List[str] = field(default_factory=list)  # 给出的模块（可选择）
    correct_sequence: List[str] = field(default_factory=list)  # 正确的模块顺序
    distractors: List[str] = field(default_factory=list)   # 干扰项模块
    hints: List[str] = field(default_factory=list)         # 提示
    difficulty: int = 1

    def to_dict(self) -> dict:
        return {
            "contract_version": CONTRACT_VERSION,
            "scenario_id": self.scenario_id,
            "title": self.title,
            "description": self.description,
            "given_modules": self.given_modules,
            "correct_sequence": self.correct_sequence,
            "distractors": self.distractors,
            "hints": self.hints,
            "difficulty": self.difficulty,
        }
