"""
流程与场景（README5 §3.4）

把"函数级流程"提升到"功能点级流程"，并生成三型场景：

| 类型 | 生成方式 | 置信度 |
|---|---|---|
| ``normal`` | 主路径（无 raise 触发） | verified |
| ``exception`` | 取某个 raise 作为失败点，路径到该点终止 | verified |
| ``edge_case`` | 取边界条件（``>=`` / ``<=`` / 空集合 / 上限） | verified |

**两个必须遵守的点**
1. 生命周期流程（初始化 / 造样例数据）用 ``engine/flow_filter.py`` 统一降权并排到末尾 ——
   它**保留但不再置顶**（README5 §3.4 修的是"把初始化流程当核心业务教"这个教学错误）。
2. **不自动编自然语言场景描述**。场景描述 = 模板 + 代码事实；教师可改写。
   不调 LLM 生成"业务故事"（README5 §3.4）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from ..flow_filter import is_lifecycle_flow, sort_flows_business_first, LIFECYCLE_FACTOR
from .capabilities import Capability
from .domains import Domain
from .facts import Fact, KIND_GUARD, KIND_RAISE, KIND_RULE

#: 边界条件的特征（用于 edge_case 场景）
_BOUNDARY_PATTERNS = (
    r">=", r"<=", r">\s*0", r"<\s*0", r"==\s*0", r"!=\s*0",
    r"len\(", r"\bis None\b", r"\bnot\b",
)


@dataclass
class FlowStep:
    """功能点级流程步骤（verified）。"""
    order: int
    capability_id: str
    name_cn: str
    module: str = ""
    file: str = ""
    line: int = 0
    symbol: str = ""
    is_state_change: bool = False
    is_validation: bool = False
    is_module_boundary: bool = False

    def to_dict(self) -> dict:
        return {
            "order": self.order,
            "capability_id": self.capability_id,
            "name_cn": self.name_cn,
            "symbol": self.symbol,
            "module": self.module,
            "file": self.file,
            "line": self.line,
            "is_state_change": self.is_state_change,
            "is_validation": self.is_validation,
            "is_module_boundary": self.is_module_boundary,
            "evidence": ([{"file": self.file, "start_line": self.line, "end_line": self.line}]
                         if self.file and self.line else []),
        }


@dataclass
class BusinessFlow:
    """功能点级业务流程（verified 结构 + inferred 命名）。"""
    flow_id: str
    name_cn: str
    scenario_type: str            # normal | exception | edge_case
    description: str = ""
    steps: List[FlowStep] = field(default_factory=list)
    involved_domains: List[str] = field(default_factory=list)
    involved_capabilities: List[str] = field(default_factory=list)
    is_lifecycle: bool = False
    weight_factor: float = 1.0
    entry_capability: str = ""
    failure_point: str = ""
    confidence: str = "verified"
    name_status: str = "from_source"

    def to_dict(self) -> dict:
        return {
            "flow_id": self.flow_id,
            "name_cn": self.name_cn,
            "scenario_type": self.scenario_type,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "involved_domains": self.involved_domains,
            "involved_capabilities": self.involved_capabilities,
            "is_lifecycle": self.is_lifecycle,
            "weight_factor": self.weight_factor,
            "entry_capability": self.entry_capability,
            "failure_point": self.failure_point,
            "confidence": self.confidence,
            "name_status": self.name_status,
        }


def _symbol_to_capability(capabilities: Sequence[Capability]) -> Dict[str, Capability]:
    index: Dict[str, Capability] = {}
    for cap in sorted(capabilities, key=lambda c: c.capability_id):
        for member in cap.members:
            index.setdefault(member.symbol, cap)
    return index


def _facts_of(capability_id: str, facts: Sequence[Fact]) -> List[Fact]:
    return [f for f in facts if f.capability_id == capability_id]


def _is_boundary_condition(code: str) -> bool:
    return any(re.search(pattern, code) for pattern in _BOUNDARY_PATTERNS)


# ------------------------------------------------------------
# 流程步骤兼容层
# ------------------------------------------------------------
# 流程步骤有两种形态：
#   - `deep_analyzer/flow_extractor.py` 的 `FlowStep` dataclass：
#       step_order / method_name / module_name / line_number / is_state_change ...
#   - `ProjectAnalyzer._convert_deep_flows()` 产出的 dict：
#       order / method / module / line / file / is_state_change ...
# 两个都要吃，所以统一用下面这组读取函数。

def _step_value(step, *names, default=None):
    for name in names:
        if isinstance(step, dict):
            if name in step and step[name] is not None:
                return step[name]
        else:
            value = getattr(step, name, None)
            if value is not None:
                return value
    return default


def _step_order(step) -> int:
    return int(_step_value(step, "order", "step_order", default=0) or 0)


def _step_symbol(step) -> str:
    return str(_step_value(step, "method", "method_name", "name", default="") or "")


def _flow_name(flow) -> str:
    if isinstance(flow, dict):
        return str(flow.get("name") or flow.get("flow_id") or "flow")
    return str(getattr(flow, "name", "") or getattr(flow, "flow_id", "flow"))


def _flow_id(flow):
    if isinstance(flow, dict):
        return flow.get("flow_id", "")
    return getattr(flow, "flow_id", "")


def _project_steps(
    raw_steps: Sequence,
    symbol_to_cap: Dict[str, Capability],
    cap_to_domain: Dict[str, str],
    node_files: Optional[Dict[str, str]] = None,
) -> List[FlowStep]:
    """把函数级流程步骤投影到功能点级，并合并同一功能点的连续步骤。

    ``node_files`` 是 ``node_id -> 项目内相对路径`` 的映射：deep 分析器的
    ``FlowStep`` dataclass **不带文件字段**，只有 ``node_id``。
    不传这张表的话，流程步骤的 ``file`` 全是空串，前端就无法从流程跳源码
    （这是前端走查报回来的真实缺口）。
    """
    steps: List[FlowStep] = []
    last_cap = None
    for raw in sorted(raw_steps, key=_step_order):
        symbol = _step_symbol(raw)
        cap = symbol_to_cap.get(symbol)
        if cap is None:
            continue
        if cap.capability_id == last_cap:
            continue
        last_cap = cap.capability_id

        file_rel = str(_step_value(raw, "file", default="") or "")
        if not file_rel and node_files:
            node_id = str(_step_value(raw, "node_id", default="") or "")
            file_rel = node_files.get(node_id, "")
        # 兜底：用功能点成员里同名函数的文件
        if not file_rel:
            for member in cap.members:
                if member.symbol == symbol:
                    file_rel = member.file
                    break

        steps.append(FlowStep(
            order=len(steps) + 1,
            capability_id=cap.capability_id,
            name_cn=cap.name_cn,
            symbol=symbol,
            module=str(_step_value(raw, "module", "module_name", default="") or ""),
            file=file_rel,
            line=int(_step_value(raw, "line", "line_number", default=0) or 0),
            is_state_change=bool(_step_value(raw, "is_state_change", default=False)),
            is_validation=bool(_step_value(raw, "is_validation", default=False)),
            is_module_boundary=bool(_step_value(raw, "is_module_boundary", default=False)),
        ))
    return steps


def build_flows(
    core_flows: Sequence,
    capabilities: Sequence[Capability],
    facts: Sequence[Fact],
    domains: Sequence[Domain],
    max_flows: int = 6,
    node_files: Optional[Dict[str, str]] = None,
) -> List[BusinessFlow]:
    """把代码级流程提升为功能点级业务流，并派生异常/边界场景。

    Args:
        node_files: ``call_graph node_id -> 项目内相对路径``；用于补齐流程步骤的文件证据。

    Returns:
        ``BusinessFlow[]``：业务流在前、生命周期流程在后（稳定排序）。
    """
    symbol_to_cap = _symbol_to_capability(capabilities)
    cap_to_domain = {cap.capability_id: cap.parent_id for cap in capabilities}

    flows: List[BusinessFlow] = []

    for flow in sort_flows_business_first(core_flows):
        raw_steps = list(getattr(flow, "steps", []) or [])
        steps = _project_steps(raw_steps, symbol_to_cap, cap_to_domain, node_files)
        if len(steps) < 2:
            continue

        lifecycle = is_lifecycle_flow(flow)
        name = _flow_name(flow)
        # 去重保序：deep 流程里同一功能点可能被多次引用
        involved_caps: List[str] = []
        for step in steps:
            if step.capability_id not in involved_caps:
                involved_caps.append(step.capability_id)
        involved_domains = sorted({cap_to_domain.get(c, "") for c in involved_caps} - {""})

        flows.append(BusinessFlow(
            flow_id=f"bg_{_flow_id(flow) or len(flows) + 1}",
            name_cn=name,
            scenario_type="normal",
            description=(
                f"{len(steps)} 个功能点跨 {len(involved_domains)} 个业务域协作完成；"
                "名称与步骤均来自真实调用链。"
            ),
            steps=steps,
            involved_domains=involved_domains,
            involved_capabilities=involved_caps,
            is_lifecycle=lifecycle,
            weight_factor=LIFECYCLE_FACTOR if lifecycle else 1.0,
            entry_capability=steps[0].capability_id,
            confidence="verified",
            name_status="from_source",
        ))

    # ---- 派生异常场景：以某个 raise 为失败点 ----
    exception_flows: List[BusinessFlow] = []
    for flow in list(flows):
        if flow.is_lifecycle:
            continue
        for index, step in enumerate(flow.steps):
            raises = [f for f in _facts_of(step.capability_id, facts) if f.kind == KIND_RAISE]
            if not raises:
                continue
            failure = sorted(raises, key=lambda f: (f.file, f.start_line))[0]
            truncated = flow.steps[: index + 1]
            if len(truncated) < 2:
                # 派生出来的场景至少要 2 步，否则它不是一个"流程"，只是一条报错 —— 不出题
                continue
            exception_flows.append(BusinessFlow(
                flow_id=f"{flow.flow_id}_exception_{index + 1}",
                name_cn=f"{flow.name_cn}（异常）",
                scenario_type="exception",
                description=(
                    f"当 `{failure.code}` 触发时，流程在「{step.name_cn}」终止，"
                    "后续步骤不再执行。"
                ),
                steps=[
                    FlowStep(**{**s.__dict__, "order": n + 1})
                    for n, s in enumerate(truncated)
                ],
                involved_domains=flow.involved_domains,
                involved_capabilities=[s.capability_id for s in truncated],
                entry_capability=flow.entry_capability,
                failure_point=f"{failure.file}:{failure.start_line}",
                confidence="verified",
            ))
            break   # 每条正常流程先只派生一个异常场景，避免题目爆炸

    # ---- 派生边界场景：以边界条件（>= / <= / len() / not ...）为线索 ----
    edge_flows: List[BusinessFlow] = []
    for flow in list(flows):
        if flow.is_lifecycle:
            continue
        for index, step in enumerate(flow.steps):
            bounds = [
                f for f in _facts_of(step.capability_id, facts)
                if f.kind in (KIND_RULE, KIND_GUARD) and _is_boundary_condition(f.code)
            ]
            if not bounds:
                continue
            boundary = sorted(bounds, key=lambda f: (f.file, f.start_line))[0]
            truncated = flow.steps[: index + 1]
            if len(truncated) < 2:
                continue
            edge_flows.append(BusinessFlow(
                flow_id=f"{flow.flow_id}_edge_{index + 1}",
                name_cn=f"{flow.name_cn}（边界）",
                scenario_type="edge_case",
                description=(
                    f"当满足边界条件 `{boundary.code}` 时，"
                    f"「{step.name_cn}」的判断结果会改变流程走向。"
                ),
                steps=[
                    FlowStep(**{**s.__dict__, "order": n + 1})
                    for n, s in enumerate(truncated)
                ],
                involved_domains=flow.involved_domains,
                involved_capabilities=[s.capability_id for s in truncated],
                entry_capability=flow.entry_capability,
                failure_point=f"{boundary.file}:{boundary.start_line}",
                confidence="verified",
            ))
            break

    # 组装：正常流程 → 异常 → 边界；生命周期流程仍然在最后
    normal = [f for f in flows if not f.is_lifecycle]
    lifecycle = [f for f in flows if f.is_lifecycle]
    ordered = normal + exception_flows + edge_flows + lifecycle
    return ordered[: max(max_flows, len(normal))]
