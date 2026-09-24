"""项目大小分析（业务逻辑分析平台的第 1 步）

这一层只做一件事：**把"这个项目有多大"变成一组可回指的、确定性的数字，
并据此选出处理策略。**

三条纪律
--------
1. **不新造定级算法。** 级别来自 ``business_graph.complexity``
   （``complexity-1.1``，按 README §5 的结构定义判定）。本模块只读，
   并把它连同 ``level_basis`` 原样透传 —— 教师要看的就是"为什么是 L2"。
2. **每个数字都要标来源。** ``structure_rows`` 的每一项都带 ``source``：
   ``ast`` 表示来自解析器（可复现、可核对），``business_graph`` 表示来自图谱推断层
   （其中 domains / capabilities 本身是 ``inferred``）。界面必须显示这一列，
   否则"1112 行"和"6 个业务域"看起来一样可靠，而它们的可靠度完全不同。
3. **失败要如实说。** 图谱构建失败时（``build_business_graph`` 用裸
   ``except Exception`` 兜底成 ``status: failed``），级别是算不出来的。
   此时 ``level_known=False``、``level=""``、``caveats`` 里写清楚，
   **不许**回落到某个默认级别还假装正常。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import tiering

ALGORITHM_VERSION = "size-1.0"

#: ``structure_rows`` 里每一行的来源标记。
#: ``ast``              —— 解析器直出，可复现（verified）
#: ``business_graph``   —— 图谱推断层，其中域/能力点是 inferred
SOURCE_AST = "ast"
SOURCE_GRAPH = "business_graph"

#: 界面列标签（中文在这里定义，前端不硬编码业务词 —— README §10.3 的做法）
_LABELS: Dict[str, str] = {
    "total_files": "Python 文件数",
    "total_lines": "代码行数",
    "total_classes": "类数量",
    "total_functions": "函数数量",
    "domains": "一级业务域",
    "capabilities": "二级功能点",
    "facts": "已绑定事实",
    "flows": "业务流程",
    "module_cards": "模块卡片",
    "nested_domains": "有多级结构的域",
    "flat_domains": "诚实降级为单级的域",
    "capabilities_per_domain_max": "单域功能点上限",
}

_UNITS: Dict[str, str] = {
    "total_files": "个",
    "total_lines": "行",
    "total_classes": "个",
    "total_functions": "个",
    "domains": "个",
    "capabilities": "个",
    "facts": "条",
    "flows": "条",
    "module_cards": "张",
    "nested_domains": "个",
    "flat_domains": "个",
    "capabilities_per_domain_max": "个",
}

#: 每行的口径说明 —— 学生/教师问"这个数字怎么算的"时要能立刻回答。
_NOTES: Dict[str, str] = {
    "total_lines": "空行与注释计入，与项目实际规模一致（validation/README.md 的统计口径）",
    "facts": "一条事实 = 一个可回指到 file+行号 的业务规则 / 异常 / 状态写入 / 前置判断",
    "nested_domains": "域内可识别能力数 >= 3 才算有多级结构；不足则诚实降级，不硬拆（README §3.1）",
    "flat_domains": "域内可识别能力数 < 3，只做一级展示并标 hierarchy: flat",
    "capabilities_per_domain_max": "引擎的聚类上限 MAX_CAPABILITIES_PER_DOMAIN=8",
}


@dataclass
class ProjectSize:
    """项目大小分析结果。"""

    project_id: str = ""
    project_name: str = ""
    level: str = ""
    level_known: bool = False
    level_label: str = ""
    level_desc: str = ""
    level_basis: List[str] = field(default_factory=list)
    structure: Dict[str, int] = field(default_factory=dict)
    structure_rows: List[Dict[str, Any]] = field(default_factory=list)
    complexity: Dict[str, Any] = field(default_factory=dict)
    tier: Dict[str, Any] = field(default_factory=dict)
    size_basis: List[str] = field(default_factory=list)
    source_hash: str = ""
    graph_status: str = ""
    graph_error: str = ""
    caveats: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "size_version": ALGORITHM_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "project_id": self.project_id,
            "project_name": self.project_name,
            "level": self.level,
            "level_known": self.level_known,
            "level_label": self.level_label,
            "level_desc": self.level_desc,
            "level_basis": list(self.level_basis),
            "structure": dict(self.structure),
            "structure_rows": [dict(row) for row in self.structure_rows],
            "complexity": dict(self.complexity),
            "tier": dict(self.tier),
            "size_basis": list(self.size_basis),
            "source_hash": self.source_hash,
            "graph_status": self.graph_status,
            "graph_error": self.graph_error,
            "caveats": list(self.caveats),
        }


def _row(key: str, value: int, source: str) -> Dict[str, Any]:
    note = _NOTES.get(key, "")
    return {
        "key": key,
        "label": _LABELS.get(key, key),
        "value": int(value),
        "unit": _UNITS.get(key, ""),
        "source": source,
        "note": note,
    }


def _count_hierarchy(graph: Dict[str, Any]) -> Dict[str, int]:
    """统计有多少域是多级、多少域诚实降级为单级。

    ``hierarchy`` 是 ``{domain_id: "nested"|"flat"}``，由 ``capabilities.py`` 的
    Rule E 按「域内能力数 >= 3」判定。这里只做计数与排序（排序是为了确定性）。
    """
    hierarchy = graph.get("hierarchy") or {}
    nested = 0
    flat = 0
    for domain_id in sorted(hierarchy.keys()):
        if str(hierarchy[domain_id]) == "nested":
            nested += 1
        else:
            flat += 1
    return {"nested_domains": nested, "flat_domains": flat}


def _capabilities_per_domain_max(graph: Dict[str, Any]) -> int:
    counts: Dict[str, int] = {}
    for cap in graph.get("capabilities") or []:
        if not isinstance(cap, dict):
            continue
        parent = str(cap.get("parent_id") or "")
        counts[parent] = counts.get(parent, 0) + 1
    return max(counts.values()) if counts else 0


def analyze_size(
    project_id: str,
    project_name: str,
    overview: Optional[Dict[str, Any]],
    graph: Optional[Dict[str, Any]],
) -> ProjectSize:
    """从既有产物算出项目大小与处理策略。

    参数
    ----
    overview: ``ProjectAnalysisResult.overview``
    graph:    ``business_graph`` 字典（可能缺失，或 ``status == "failed"``）
    """
    overview = dict(overview or {})
    graph = dict(graph or {})
    graph_status = str(graph.get("status") or "")
    graph_error = str(graph.get("error") or "")
    graph_ok = bool(graph) and graph_status != "failed"

    result = ProjectSize(
        project_id=str(project_id or ""),
        project_name=str(project_name or ""),
        source_hash=str(graph.get("source_hash") or ""),
        graph_status=graph_status,
        graph_error=graph_error,
    )

    # ---- 1. 结构规模：AST 侧的数字（verified，来源标记 ast） ----
    structure: Dict[str, int] = {
        "total_files": int(overview.get("total_files") or 0),
        "total_lines": int(overview.get("total_lines") or 0),
        "total_classes": int(overview.get("total_classes") or 0),
        "total_functions": int(overview.get("total_functions") or 0),
    }

    # ---- 2. 结构规模：图谱侧的数字（域/能力点为 inferred） ----
    if graph_ok:
        structure.update(
            {
                "domains": len(graph.get("domains") or []),
                "capabilities": len(graph.get("capabilities") or []),
                "facts": len(graph.get("facts") or []),
                "flows": len(graph.get("flows") or []),
                "module_cards": len(graph.get("module_cards") or {}),
                "capabilities_per_domain_max": _capabilities_per_domain_max(graph),
            }
        )
        structure.update(_count_hierarchy(graph))

    result.structure = structure

    # rows 固定顺序输出（确定性），且只输出真实存在的键
    order = [
        "total_files", "total_lines", "total_classes", "total_functions",
        "domains", "capabilities", "facts", "flows", "module_cards",
        "nested_domains", "flat_domains", "capabilities_per_domain_max",
    ]
    ast_keys = {"total_files", "total_lines", "total_classes", "total_functions"}
    rows: List[Dict[str, Any]] = []
    for key in order:
        if key not in structure:
            continue
        rows.append(_row(key, structure[key], SOURCE_AST if key in ast_keys else SOURCE_GRAPH))
    result.structure_rows = rows

    # ---- 3. 级别与七维明细：直接沿用 complexity 的结论 ----
    complexity = graph.get("complexity") if isinstance(graph.get("complexity"), dict) else {}
    if complexity:
        result.complexity = dict(complexity)
        result.level = str(complexity.get("level") or graph.get("level") or "")
        result.level_label = str(complexity.get("level_label") or "")
        result.level_desc = str(complexity.get("level_desc") or "")
        result.level_basis = [str(item) for item in (complexity.get("level_basis") or [])]
        result.level_known = bool(result.level)
    elif graph_ok and graph.get("level"):
        # 老契约没有 complexity 字段，只有 level —— 如实透传，并说明依据缺失
        result.level = str(graph.get("level"))
        result.level_known = True

    # ---- 4. 处理策略 ----
    result.tier = tiering.plan_for_level(result.level if result.level_known else None)

    # ---- 5. 中文依据：把"这个大小是怎么来的"讲清楚 ----
    basis: List[str] = []
    if structure.get("total_lines"):
        basis.append(
            f"代码规模：{structure.get('total_files', 0)} 个 Python 文件、"
            f"{structure['total_lines']} 行（口径见 structure_rows 的 note）"
        )
    if graph_ok:
        basis.append(
            f"结构规模：{structure.get('domains', 0)} 个一级业务域、"
            f"{structure.get('capabilities', 0)} 个二级功能点、"
            f"{structure.get('facts', 0)} 条已绑定事实"
        )
        if structure.get("flat_domains"):
            basis.append(
                f"其中 {structure['flat_domains']} 个域的能力点不足 3 个，"
                "按 README §3.1 诚实降级为单级展示（不硬拆出假的多级结构）"
            )
    if result.level_known:
        basis.append(
            f"复杂度级别：{result.level}（{result.level_label}）——"
            "由结构定义判定，判定过程见 level_basis"
        )
    else:
        basis.append("复杂度级别：算不出来（图谱缺失或构建失败），按最保守策略处理")
    basis.extend(f"定级过程：{item}" for item in result.level_basis)
    result.size_basis = basis

    # ---- 6. caveats ----
    caveats: List[str] = [tiering.TIER_CAVEAT]
    if not graph_ok:
        detail = graph_error or ("business_graph 缺失" if not graph else "business_graph.status 异常")
        caveats.append(
            f"业务图谱不可用（{detail}）：本次只给出 AST 侧的规模数字，"
            "不产出业务板块，也不猜级别。请先重建图谱（scripts/build_demo_snapshots.py）。"
        )
    if result.level_known and not result.complexity:
        caveats.append("该契约只有 level 没有 complexity 明细，七维分项与门限不可得。")
    caveats.append(
        "「代码行数」不含 __pycache__/.git/tests（与 validation 统计口径一致）；"
        "域与功能点为引擎推断（inferred），行数/文件数/类数/函数数为 AST 直出（verified）。"
    )
    result.caveats = caveats
    return result
