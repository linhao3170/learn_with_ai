"""
业务逻辑模块的数据契约层（data-model / schema layer ONLY）
============================================================

**这个包只定义数据结构，不含任何算法或引擎实现。**

历史背景（README5 §1.2-⑥）：这里曾试图懒加载 `BusinessLogicTrainingEngine`
（来自不存在的 `.engine` 模块）和 `ModuleCard`（`models.py` 里也没有），
两者都是坏引用，任何一次属性访问都会抛 AttributeError。现已删除。

真正的实现在别处，规划位置：
  - 业务图谱构建流水线（`BusinessGraphBuilder`，五步）：`engine/business_graph/`
    （见 README5 §2.4 目录结构 / §3.1 流水线设计）；
  - 设计任务生成、六维评分等：`engine/design/`。

所以：**不要指望 `from engine.business_logic import <某个引擎>` 能拿到可运行对象。**
这里只提供 `to_dict()` 序列化契约（README3 §6.1 / README5 §4.1、§4.2），
每个 `to_dict()` 都带 `contract_version`，字段名统一为
`name_cn` / `does_not` / `module_cards`。

用法：
    from engine.business_logic import BusinessGraph, BusinessModule
    from engine.business_logic.models import CONTRACT_VERSION
"""

from .models import (
    CONTRACT_VERSION,
    BusinessModule,
    BusinessGraph,
    BusinessFlowStep,
    BusinessFlow,
    GoldGraph,
    StudentModule,
    DesignSubmission,
    DimensionScore,
    EvaluationResult,
    TrainingStage,
    TrainingPlan,
    FlowScenario,
)

__version__ = "0.1.0"

__all__ = [
    "CONTRACT_VERSION",
    "BusinessModule",
    "BusinessGraph",
    "BusinessFlowStep",
    "BusinessFlow",
    "GoldGraph",
    "StudentModule",
    "DesignSubmission",
    "DimensionScore",
    "EvaluationResult",
    "TrainingStage",
    "TrainingPlan",
    "FlowScenario",
]


def __getattr__(name):
    """给不存在的名字一个明确的 AttributeError（而不是静默的坏懒加载）。

    这里只覆盖"属性不存在"的情况，不会代替上面的真实导出。
    """
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}. "
        "engine.business_logic 只是数据模型/契约层，没有引擎实现；"
        "引擎计划放在 engine/business_graph/。可用名字见 "
        f"engine.business_logic.__all__ = {__all__!r}"
    )
