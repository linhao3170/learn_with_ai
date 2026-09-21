"""
调用图构建

基于静态分析构建函数间的调用关系图。
借鉴 pyan 的核心思路，但做了简化，输出 JSON 友好的结构。
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional

from ..parser.python_parser import ParsedResult, FunctionInfo, ClassInfo


@dataclass
class CallGraphNode:
    """调用图节点（函数/方法）"""
    id: str  # 唯一标识，如 "ClassName.method_name" 或 "function_name"
    name: str
    kind: str  # "function" / "method"
    class_name: Optional[str] = None
    start_line: int = 0
    end_line: int = 0
    calls: List[str] = field(default_factory=list)  # 调用的节点 id 列表
    called_by: List[str] = field(default_factory=list)  # 被哪些节点调用


@dataclass
class CallGraph:
    """调用图"""
    nodes: Dict[str, CallGraphNode] = field(default_factory=dict)
    entry_points: List[str] = field(default_factory=list)  # 入口函数（不被其他函数调用的）
    leaves: List[str] = field(default_factory=list)  # 叶子函数（不调用其他内部函数的）

    def get_node(self, node_id: str) -> Optional[CallGraphNode]:
        return self.nodes.get(node_id)

    def to_dict(self) -> dict:
        return {
            "nodes": {
                nid: {
                    "name": node.name,
                    "kind": node.kind,
                    "class_name": node.class_name,
                    "start_line": node.start_line,
                    "end_line": node.end_line,
                    "calls": node.calls,
                    "called_by": node.called_by,
                }
                for nid, node in self.nodes.items()
            },
            "entry_points": self.entry_points,
            "leaves": self.leaves,
        }


def build_call_graph(parsed: ParsedResult) -> CallGraph:
    """
    从解析结果构建调用图

    策略：
    1. 先收集所有内部定义的函数/方法作为节点
    2. 扫描每个函数体中的函数调用，匹配到已知节点
    3. 同时考虑 self.method() 形式的方法调用
    """
    graph = CallGraph()

    # 收集所有函数名
    func_names: Set[str] = set()
    method_names: Dict[str, Set[str]] = {}  # class_name -> set of method names

    # 顶层函数
    for func in parsed.functions:
        node_id = func.name
        func_names.add(func.name)
        graph.nodes[node_id] = CallGraphNode(
            id=node_id,
            name=func.name,
            kind="function",
            start_line=func.start_line,
            end_line=func.end_line,
        )

    # 类方法
    for cls in parsed.classes:
        method_names[cls.name] = set()
        for method in cls.methods:
            method_names[cls.name].add(method.name)
            node_id = f"{cls.name}.{method.name}"
            graph.nodes[node_id] = CallGraphNode(
                id=node_id,
                name=method.name,
                kind="method",
                class_name=cls.name,
                start_line=method.start_line,
                end_line=method.end_line,
            )

    # 分析调用关系
    def _resolve_calls(func: FunctionInfo, class_name: Optional[str] = None) -> List[str]:
        """解析一个函数中调用的内部节点"""
        resolved = []
        for called in func.called_functions:
            # 直接匹配顶层函数
            if called in func_names:
                resolved.append(called)
            # self 方法调用：如果在类中，且被调函数是同类的方法
            # 注意：called_functions 存的是 Attribute.attr，所以 self.xxx 的 xxx 会出现在这里
            elif class_name and called in method_names.get(class_name, set()):
                resolved.append(f"{class_name}.{called}")
        return list(set(resolved))  # 去重

    # 顶层函数的调用
    for func in parsed.functions:
        node_id = func.name
        calls = _resolve_calls(func)
        graph.nodes[node_id].calls = calls

    # 类方法的调用
    for cls in parsed.classes:
        for method in cls.methods:
            node_id = f"{cls.name}.{method.name}"
            calls = _resolve_calls(method, class_name=cls.name)
            graph.nodes[node_id].calls = calls

    # 反向构建 called_by
    for node_id, node in graph.nodes.items():
        for called_id in node.calls:
            if called_id in graph.nodes:
                graph.nodes[called_id].called_by.append(node_id)

    # 计算入口和叶子
    for node_id, node in graph.nodes.items():
        if not node.called_by:
            graph.entry_points.append(node_id)
        if not node.calls:
            graph.leaves.append(node_id)

    return graph
