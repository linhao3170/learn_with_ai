"""
State change tracker.

Analyzes which attributes each method reads/writes, distinguishing
queries from mutations and tracing how state flows through the system.
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple

from ..parser.ast_cache import get_tree


#: 内部推断标记（P0-07）
#:
#: ``_analyze_method_body`` 用 ``f"{attr}._inferred_"`` 表示"这个字典写入是
#: 别名启发式**推断**出来的，不是 AST 直接看到的"。它曾经是一个哨兵值，
#: 混在正常的状态路径里，结果泄漏到了学生看到的题干
#: （``modifies 3 state attribute(s): users, _next_id, users._inferred_``）。
#:
#: 现在统一用下面两个函数把"真实写入"和"推断写入"分开，
#: 推断信息单独用 ``method_dict_writes_inferred`` 承载，
#: 既不再泄漏内部标记，也**没有丢失** inferred / verified 的分层。
INTERNAL_INFERRED_SUFFIX = "._inferred_"


def is_internal_marker(name: str) -> bool:
    """判断一个状态路径是否是内部推断标记。"""
    return str(name).endswith(INTERNAL_INFERRED_SUFFIX) or str(name) == "_inferred_"


def strip_internal_markers(names) -> List[str]:
    """剔除内部推断标记，返回干净的状态路径列表（保序去重）。"""
    cleaned: List[str] = []
    for name in names or []:
        text = str(name)
        if is_internal_marker(text):
            continue
        if text not in cleaned:
            cleaned.append(text)
    return cleaned


def split_inferred_markers(names) -> Tuple[List[str], List[str]]:
    """把 ``names`` 拆成 ``(真实路径, 被推断的路径)`` 两部分。"""
    real: List[str] = []
    inferred: List[str] = []
    for name in names or []:
        text = str(name)
        if is_internal_marker(text):
            base = text[: -len(INTERNAL_INFERRED_SUFFIX)] if text.endswith(INTERNAL_INFERRED_SUFFIX) else text
            if base and base not in inferred:
                inferred.append(base)
            continue
        if text not in real:
            real.append(text)
    return real, inferred


@dataclass
class ClassState:
    """State inventory for a single class."""
    class_name: str
    module_name: str
    filepath: str
    state_attributes: List[str] = field(default_factory=list)
    dict_like_attrs: List[str] = field(default_factory=list)
    class_constants: List[str] = field(default_factory=list)
    method_writes: Dict[str, List[str]] = field(default_factory=dict)
    method_reads: Dict[str, List[str]] = field(default_factory=dict)
    method_dict_writes: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class StateAnalysis:
    """Project-level state analysis result."""
    classes: Dict[str, ClassState] = field(default_factory=dict)

    def get_class_state(self, module_name: str, class_name: str) -> Optional[ClassState]:
        return self.classes.get(f"{module_name}:{class_name}")

    def is_state_writer(self, module_name: str, class_name: str, method_name: str) -> bool:
        cs = self.get_class_state(module_name, class_name)
        if not cs:
            return False
        writes = cs.method_writes.get(method_name, [])
        dict_writes = cs.method_dict_writes.get(method_name, [])
        return len(writes) > 0 or len(dict_writes) > 0

    def to_dict(self) -> dict:
        """序列化（P0-07：内部推断标记不下发）。

        - ``method_dict_writes`` 只输出**真实**的字典写入路径；
        - 被推断出来的写入单独放在 ``method_dict_writes_inferred``，
          并标 ``inferred`` 语义，学生界面可以据此区分"看到的"和"推出来的"。
        """
        result = {}
        for key, cs in self.classes.items():
            clean_writes: Dict[str, List[str]] = {}
            inferred_writes: Dict[str, List[str]] = {}
            for method, paths in (cs.method_dict_writes or {}).items():
                real, inferred = split_inferred_markers(paths)
                if real:
                    clean_writes[method] = real
                if inferred:
                    inferred_writes[method] = inferred

            result[key] = {
                "class": cs.class_name,
                "module": cs.module_name,
                "filepath": cs.filepath,
                "state_attributes": cs.state_attributes,
                "dict_like_attrs": cs.dict_like_attrs,
                "class_constants": cs.class_constants,
                "method_writes": cs.method_writes,
                "method_reads": cs.method_reads,
                "method_dict_writes": clean_writes,
                "method_dict_writes_inferred": inferred_writes,
            }
        return result



class StateTracker:
    """Track state mutations and reads across a project."""

    def __init__(self):
        self.result = StateAnalysis()

    def analyze_project(self, project_info) -> StateAnalysis:
        """Analyze all classes in a project."""
        for file_info in project_info.files:
            mod = file_info.module_name
            filepath = file_info.filepath

            # P0-14：走共享 AST 缓存，避免同一文件被反复 ast.parse
            tree = get_tree(filepath)
            if tree is None:
                continue

            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.ClassDef):
                    cs = self._analyze_class(node, mod, filepath)
                    self.result.classes[f"{mod}:{cs.class_name}"] = cs

        return self.result

    def _analyze_class(self, class_node: ast.ClassDef, module_name: str, filepath: str) -> ClassState:
        cs = ClassState(
            class_name=class_node.name,
            module_name=module_name,
            filepath=filepath,
        )

        # Class-level constants (UPPER_CASE)
        for stmt in class_node.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        cs.class_constants.append(target.id)

        # __init__ for state attributes
        init_method = None
        for item in class_node.body:
            if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                init_method = item
                break

        if init_method:
            attrs, dict_attrs = self._extract_init_attributes(init_method)
            cs.state_attributes = attrs
            cs.dict_like_attrs = dict_attrs

        # Analyze each method
        for item in class_node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_name = item.name
                writes, reads, dict_writes = self._analyze_method_body(
                    item, cs.state_attributes, cs.dict_like_attrs
                )
                cs.method_writes[method_name] = sorted(writes)
                cs.method_reads[method_name] = sorted(reads)
                cs.method_dict_writes[method_name] = sorted(dict_writes)

        return cs

    def _extract_init_attributes(self, init_node: ast.FunctionDef) -> Tuple[List[str], List[str]]:
        """Extract all self.xxx attributes initialized in __init__."""
        attrs: Set[str] = set()
        dict_attrs: Set[str] = set()

        for stmt in init_node.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if (isinstance(target, ast.Attribute) and
                        isinstance(target.value, ast.Name) and
                        target.value.id == "self"):
                        attrs.add(target.attr)
                        if isinstance(stmt.value, (ast.Dict, ast.List, ast.Set)):
                            dict_attrs.add(target.attr)

            if isinstance(stmt, ast.AugAssign):
                if (isinstance(stmt.target, ast.Attribute) and
                    isinstance(stmt.target.value, ast.Name) and
                    stmt.target.value.id == "self"):
                    attrs.add(stmt.target.attr)

        return sorted(attrs), sorted(dict_attrs)

    def _analyze_method_body(self, func_node, known_attrs, dict_like_attrs):
        """
        Analyze a method body for state reads and writes.
        Returns (writes, reads, dict_writes).
        """
        writes: Set[str] = set()
        reads: Set[str] = set()
        dict_writes: Set[str] = set()

        known_set = set(known_attrs)
        dict_set = set(dict_like_attrs)

        for node in ast.walk(func_node):
            # Direct assignment: self.attr = ...
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    self_chain = self._extract_self_chain(target)
                    if self_chain:
                        attr_name = self_chain[0]
                        writes.add(attr_name)
                        if len(self_chain) > 1:
                            path = ".".join(attr_name for attr_name in self_chain if attr_name != "[]")
                            dict_writes.add(path)

            # Augmented assignment: self.x += 1
            if isinstance(node, ast.AugAssign):
                self_chain = self._extract_self_chain(node.target)
                if self_chain:
                    writes.add(self_chain[0])
                    reads.add(self_chain[0])

            # Mutating method calls on self.attr
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Attribute):
                    outer = func.value
                    if (isinstance(outer.value, ast.Name) and
                        outer.value.id == "self"):
                        attr_name = outer.attr
                        method_name = func.attr
                        mutating = {
                            "append", "extend", "insert", "remove", "pop",
                            "clear", "sort", "reverse",
                            "update", "setdefault", "add", "discard",
                        }
                        if method_name in mutating:
                            writes.add(attr_name)
                        reads.add(attr_name)

            # Reads: any self.attr access
            if isinstance(node, ast.Attribute):
                if (isinstance(node.value, ast.Name) and
                    node.value.id == "self"):
                    attr_name = node.attr
                    if not attr_name.startswith("__"):
                        reads.add(attr_name)

        # Filter to known state attributes
        real_writes = writes & known_set
        real_reads = reads & known_set
        real_dict_writes = dict_writes

        # ---- Alias-based heuristic detection ----
        # If a method reads dict-like attrs and has a mutation-style name,
        # it likely mutates state through local variable aliases.
        mutation_verbs = {
            "update", "set", "change", "modify", "approve", "reject",
            "cancel", "close", "complete", "assign", "deactivate",
            "borrow", "return", "add", "create", "register", "perform",
            "submit", "process", "fix", "mark", "clear", "reset",
            "delete", "remove",
        }
        method_name = func_node.name.lower()
        reads_dict = bool(real_reads & dict_set)

        if reads_dict and any(verb in method_name for verb in mutation_verbs):
            # Infer writes to the dict attrs it reads
            for attr in (real_reads & dict_set):
                real_writes.add(attr)
                real_dict_writes.add(f"{attr}._inferred_")

        return real_writes, real_reads, real_dict_writes

    def _extract_self_chain(self, node: ast.AST) -> Optional[List[str]]:
        """
        Extract the attribute/subscript chain from a self.x expression.
        Returns list of names, or None if not a self.x expression.
        """
        parts = []
        current = node

        while True:
            if isinstance(current, ast.Attribute):
                parts.insert(0, current.attr)
                current = current.value
            elif isinstance(current, ast.Subscript):
                if isinstance(current.slice, ast.Constant) and isinstance(current.slice.value, str):
                    parts.insert(0, current.slice.value)
                else:
                    parts.insert(0, "[]")
                current = current.value
            elif isinstance(current, ast.Name) and current.id == "self":
                return parts
            else:
                return None

        return None
