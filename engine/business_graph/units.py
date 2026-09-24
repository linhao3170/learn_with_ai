"""
第 1 步：结构单元采集（README5 §3.1）

单元（Unit）= 一个类，或一组顶层函数。
这一层**全部是 verified**：类名、方法名、行号、状态读写、调用关系都来自 AST 与调用图。

关键设计：**只做事实采集，不做任何业务判断**。
"这个类是干什么的" 是后面几步的事；这里只回答"代码里有什么"。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set

from ..deep_analyzer.state_tracker import split_inferred_markers


@dataclass
class UnitMethod:
    """单元里的一个方法/函数（verified）。"""
    symbol: str
    file: str                  # 项目内相对路径
    start_line: int
    end_line: int
    is_public: bool = True
    docstring: str = ""
    #: 该方法写入的状态路径（来自状态追踪，已过滤内部推断标记）
    state_writes: List[str] = field(default_factory=list)
    state_reads: List[str] = field(default_factory=list)
    #: 该方法调用的其它符号名（用于二级功能点的聚簇）
    calls_out: List[str] = field(default_factory=list)
    #: 由本方法写入的状态路径被推断出来的部分（P0-07 的分层保留）
    state_writes_inferred: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "file": self.file,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "is_public": self.is_public,
            "docstring": self.docstring,
            "state_writes": self.state_writes,
            "state_reads": self.state_reads,
            "calls_out": self.calls_out,
            "state_writes_inferred": self.state_writes_inferred,
        }


@dataclass
class Unit:
    """一个结构单元（verified）。"""
    unit_id: str
    kind: str                  # "class" | "functions"
    symbol: str                # 类名；顶层函数组用文件名
    module: str                # 所属代码模块（= 项目内相对路径点分名）
    file: str                  # 项目内相对路径（POSIX）
    start_line: int
    end_line: int
    docstring: str = ""            # 类/文件 docstring（原始语言）
    file_docstring: str = ""       # 文件级 docstring（中文项目里常写"XX管理模块"）
    methods: List[UnitMethod] = field(default_factory=list)
    state_writes: List[str] = field(default_factory=list)
    state_reads: List[str] = field(default_factory=list)
    called_by: List[str] = field(default_factory=list)
    #: 来自调用图的角色线索（orchestrator / core / ...），可能为空
    role_hint: str = ""

    @property
    def public_methods(self) -> List[UnitMethod]:
        return [m for m in self.methods if m.is_public]

    def to_dict(self) -> dict:
        return {
            "unit_id": self.unit_id,
            "kind": self.kind,
            "symbol": self.symbol,
            "module": self.module,
            "file": self.file,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "docstring": self.docstring,
            "file_docstring": self.file_docstring,
            "methods": [m.to_dict() for m in self.methods],
            "state_writes": self.state_writes,
            "state_reads": self.state_reads,
            "called_by": self.called_by,
            "role_hint": self.role_hint,
            "confidence": "verified",
        }


def _split_docstring_first_line(docstring: Optional[str]) -> str:
    """取 docstring 第一行非空文本。"""
    if not docstring:
        return ""
    for line in str(docstring).splitlines():
        line = line.strip()
        if line:
            return line
    return ""


# ------------------------------------------------------------
# 调用图边兼容层
# ------------------------------------------------------------
# `project_call_graph.CallEdge` 是 dataclass（from_node/to_node/line_number/call_type），
# 而 `to_dict()` 后又是 dict（from/to/line/type）。两个分析器在不同阶段会分别拿到
# 两种形态，所以这里统一成一组读取函数，别在业务代码里到处 isinstance 判断。

def edge_target(edge) -> str:
    """出边的目标 node_id（同时兼容 CallEdge 与 dict）。"""
    if isinstance(edge, dict):
        return str(edge.get("to") or edge.get("to_node") or "")
    return str(getattr(edge, "to_node", "") or "")


def edge_source(edge) -> str:
    """入边的来源 node_id。"""
    if isinstance(edge, dict):
        return str(edge.get("from") or edge.get("from_node") or "")
    return str(getattr(edge, "from_node", "") or "")


def edge_line(edge) -> int:
    """调用发生的行号。"""
    if isinstance(edge, dict):
        return int(edge.get("line") or edge.get("line_number") or 0)
    return int(getattr(edge, "line_number", 0) or 0)


def edge_type(edge) -> str:
    """调用类型。"""
    if isinstance(edge, dict):
        return str(edge.get("type") or edge.get("call_type") or "direct")
    return str(getattr(edge, "call_type", "direct") or "direct")


def _state_index(state_analysis) -> Dict[str, Dict[str, Any]]:
    """把 StateAnalysis 整理成 ``{"module:Class": {...}}`` 便于按类查。"""
    index: Dict[str, Dict[str, Any]] = {}
    if state_analysis is None:
        return index
    classes = getattr(state_analysis, "classes", None)
    if isinstance(classes, dict):
        for key, cs in classes.items():
            index[key] = {
                "class": getattr(cs, "class_name", ""),
                "module": getattr(cs, "module_name", ""),
                "method_writes": getattr(cs, "method_writes", {}) or {},
                "method_reads": getattr(cs, "method_reads", {}) or {},
                "method_dict_writes": getattr(cs, "method_dict_writes", {}) or {},
            }
    return index


def _rel_of(project_info, filepath: str) -> str:
    """把绝对路径转成项目内相对路径（POSIX）。"""
    if not filepath:
        return ""
    normalizer = getattr(project_info, "rel_path_of", None)
    if callable(normalizer):
        return normalizer(filepath)
    return str(filepath).replace("\\", "/")


def collect_units(project_info, call_graph=None, state_analysis=None) -> List[Unit]:
    """第 1 步：采集结构单元（verified）。

    Args:
        project_info: ``ProjectInfo``（来自 ProjectParser）
        call_graph: ``ProjectCallGraph``（可选，用于 called_by 与 role 线索）
        state_analysis: ``StateAnalysis``（可选，用于每个方法的状态读写）

    Returns:
        ``Unit`` 列表，按 ``unit_id`` 排序（保证可复现）。
    """
    state_index = _state_index(state_analysis)

    # 调用图：node_id -> 被谁调用；以及模块角色线索
    called_by_index: Dict[str, List[str]] = {}
    role_by_module: Dict[str, str] = {}
    node_file_index: Dict[str, str] = {}
    if call_graph is not None:
        for node_id, node in (getattr(call_graph, "nodes", {}) or {}).items():
            node_file_index[node_id] = getattr(node, "filepath", "") or ""
            callers = [edge_source(c) for c in (getattr(node, "called_by", []) or [])]
            called_by_index[node_id] = sorted(c for c in callers if c)

    units: List[Unit] = []

    for file_info in sorted(project_info.files, key=lambda f: f.rel_path):
        parsed = file_info.parsed
        rel = file_info.rel_path
        module = file_info.module_name
        # 注意：PythonParser 把文件级 docstring 放在 `module_docstring`（不是 `docstring`）。
        # 第一版读错了字段，导致所有中文模块名（"预约管理模块"）都拿不到，
        # 域名退化成英文词根 —— 这是个很容易再犯的坑，所以在两处都做了兜底。
        file_doc = _split_docstring_first_line(
            getattr(parsed, "module_docstring", None) or getattr(parsed, "docstring", None)
        )

        # 文件级状态（顶层函数用）
        file_writes: Set[str] = set()
        file_reads: Set[str] = set()

        # ---- 类单元 ----
        for cls in sorted(parsed.classes, key=lambda c: (c.start_line, c.name)):
            unit_id = f"u_{module.replace('.', '_')}_{cls.name}"
            class_key = f"{module}:{cls.name}"
            state = state_index.get(class_key, {})
            method_writes = state.get("method_writes", {}) or {}
            method_reads = state.get("method_reads", {}) or {}
            method_dict_writes = state.get("method_dict_writes", {}) or {}
            dict_writes_inferred = state.get("method_dict_writes_inferred", {}) or {}

            methods: List[UnitMethod] = []
            for method in sorted(cls.methods, key=lambda m: (m.start_line, m.name)):
                node_id = f"{module}:{cls.name}.{method.name}"
                writes = sorted(set(method_writes.get(method.name, []) or []))
                reads = sorted(set(method_reads.get(method.name, []) or []))
                # 注意：这里读的是 ClassState **dataclass**，它的 method_dict_writes
                # 仍带 `x._inferred_` 哨兵（只有 to_dict() 会拆开）。所以必须在这里
                # 也拆一次，否则内部标记会顺着 能力→卡片→事实 一路泄漏到学生界面。
                dict_writes, inferred = split_inferred_markers(
                    method_dict_writes.get(method.name, []) or []
                )
                if dict_writes:
                    writes = sorted(set(writes) | set(dict_writes))
                methods.append(UnitMethod(
                    symbol=method.name,
                    file=rel,
                    start_line=method.start_line,
                    end_line=method.end_line,
                    is_public=not method.name.startswith("_"),
                    docstring=_split_docstring_first_line(getattr(method, "docstring", "")),
                    state_writes=writes,
                    state_reads=reads,
                    calls_out=sorted(set(getattr(method, "called_functions", None) or [])),
                    state_writes_inferred=inferred,
                ))

            cls_writes = sorted({w for m in methods for w in m.state_writes})
            cls_reads = sorted({r for m in methods for r in m.state_reads})
            called_by = called_by_index.get(f"{module}:{cls.name}", [])

            units.append(Unit(
                unit_id=unit_id,
                kind="class",
                symbol=cls.name,
                module=module,
                file=rel,
                start_line=cls.start_line,
                end_line=cls.end_line,
                docstring=_split_docstring_first_line(getattr(cls, "docstring", "")),
                file_docstring=file_doc,
                methods=methods,
                state_writes=cls_writes,
                state_reads=cls_reads,
                called_by=called_by,
            ))

        # ---- 顶层函数单元（按文件聚合，避免碎成一堆单函数单元）----
        top_functions = list(getattr(parsed, "functions", []) or [])
        if top_functions:
            unit_id = f"u_{module.replace('.', '_')}_functions"
            methods = []
            for func in sorted(top_functions, key=lambda f: (f.start_line, f.name)):
                writes = sorted(set(
                    (state_index.get(f"{module}:{func.name}", {}) or {}).get("method_writes", {}).get(func.name, []) or []
                ))
                reads = sorted(set(
                    (state_index.get(f"{module}:{func.name}", {}) or {}).get("method_reads", {}).get(func.name, []) or []
                ))
                file_writes.update(writes)
                file_reads.update(reads)
                methods.append(UnitMethod(
                    symbol=func.name,
                    file=rel,
                    start_line=func.start_line,
                    end_line=func.end_line,
                    is_public=not func.name.startswith("_"),
                    docstring=_split_docstring_first_line(getattr(func, "docstring", "")),
                    state_writes=writes,
                    state_reads=reads,
                    calls_out=sorted(set(getattr(func, "called_functions", None) or [])),
                ))

            units.append(Unit(
                unit_id=unit_id,
                kind="functions",
                symbol=file_info.filename.rsplit(".", 1)[0],
                module=module,
                file=rel,
                start_line=min(m.start_line for m in methods),
                end_line=max(m.end_line for m in methods),
                docstring="",
                file_docstring=file_doc,
                methods=methods,
                state_writes=sorted(file_writes),
                state_reads=sorted(file_reads),
            ))

    # 稳定排序：unit_id 字典序
    units.sort(key=lambda u: u.unit_id)
    return units


def unit_out_degree(unit: Unit) -> int:
    """单元"向外调用"的规模（用于编排类判定）。"""
    return sum(len(m.calls_out) for m in unit.methods)
