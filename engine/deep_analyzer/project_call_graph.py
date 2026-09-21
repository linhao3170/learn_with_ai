"""
Project-level call graph builder.

Resolves cross-file, cross-module method calls by building a global
symbol table from all parsed files, then tracing import relationships
and attribute chains (self.manager.method() -> actual target).

Key capabilities:
- Build a unified symbol table across all project files
- Resolve `from module import Class` to actual class definitions
- Resolve `self.attr.method()` calls when `self.attr` is initialized in __init__
- Track call direction and call count for dependency strength
"""

from __future__ import annotations

import os
import ast
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple


@dataclass
class CallNode:
    """A callable node in the project call graph (function or method)."""
    node_id: str  # e.g. "module_name:ClassName.method_name" or "module_name:function_name"
    name: str
    kind: str  # "function" | "method"
    module_name: str
    filepath: str
    class_name: Optional[str] = None
    start_line: int = 0
    end_line: int = 0
    docstring: Optional[str] = None
    # Outgoing calls
    calls: List[CallEdge] = field(default_factory=list)
    # Incoming calls
    called_by: List[CallEdge] = field(default_factory=list)
    # Whether this is likely an entry point (public, not called internally)
    is_entry_point: bool = False
    # Tags: "validation", "state_change", "query", "creation", etc.
    tags: List[str] = field(default_factory=list)


@dataclass
class CallEdge:
    """An edge in the call graph."""
    from_node: str  # source node_id
    to_node: str    # target node_id
    call_count: int = 1  # how many times the call appears in source
    call_type: str = "direct"  # "direct" | "self_method" | "composite_attr" | "imported"
    line_number: int = 0


@dataclass
class ProjectCallGraph:
    """Complete project-level call graph."""
    nodes: Dict[str, CallNode] = field(default_factory=dict)
    edges: List[CallEdge] = field(default_factory=list)
    # module_name -> list of node_ids in that module
    module_nodes: Dict[str, List[str]] = field(default_factory=dict)
    # class_full_name (module:Class) -> node_ids of its methods
    class_methods: Dict[str, List[str]] = field(default_factory=dict)
    # entry point node_ids
    entry_points: List[str] = field(default_factory=list)
    # leaf node_ids (don't call any internal nodes)
    leaves: List[str] = field(default_factory=list)

    def get_node(self, node_id: str) -> Optional[CallNode]:
        return self.nodes.get(node_id)

    def to_dict(self) -> dict:
        """Serialize to dict for JSON output."""
        return {
            "nodes": {
                nid: {
                    "name": n.name,
                    "kind": n.kind,
                    "module": n.module_name,
                    "class": n.class_name,
                    "filepath": n.filepath,
                    "start_line": n.start_line,
                    "end_line": n.end_line,
                    "docstring": n.docstring,
                    "calls": [
                        {"to": e.to_node, "count": e.call_count, "type": e.call_type, "line": e.line_number}
                        for e in n.calls
                    ],
                    "called_by": [
                        {"from": e.from_node, "count": e.call_count, "type": e.call_type}
                        for e in n.called_by
                    ],
                    "is_entry_point": n.is_entry_point,
                    "tags": n.tags,
                }
                for nid, n in self.nodes.items()
            },
            "entry_points": self.entry_points,
            "leaves": self.leaves,
            "modules": self.module_nodes,
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
        }


def _make_node_id(module_name: str, class_name: Optional[str], func_name: str) -> str:
    """Generate a unique node ID."""
    if class_name:
        return f"{module_name}:{class_name}.{func_name}"
    return f"{module_name}:{func_name}"


def build_project_call_graph(project_info) -> ProjectCallGraph:
    """
    Build a project-level call graph from a ProjectInfo object.

    Args:
        project_info: ProjectInfo from project_parser

    Returns:
        ProjectCallGraph with cross-file / cross-module resolution
    """
    graph = ProjectCallGraph()

    # ---- Phase 1: Collect all symbols ----
    # module_name -> {class_name: class_info_dict}
    module_classes: Dict[str, Dict[str, dict]] = {}
    # module_name -> {func_name: func_info_dict}
    module_functions: Dict[str, Dict[str, dict]] = {}
    # module_name -> list of import info
    module_imports: Dict[str, List[dict]] = {}

    for file_info in project_info.files:
        mod = file_info.module_name
        parsed = file_info.parsed

        module_classes[mod] = {}
        module_functions[mod] = {}
        module_imports[mod] = []

        # Collect classes
        for cls in parsed.classes:
            module_classes[mod][cls.name] = {
                "class_obj": cls,
                "filepath": file_info.filepath,
            }

        # Collect top-level functions
        for func in parsed.functions:
            module_functions[mod][func.name] = {
                "func_obj": func,
                "filepath": file_info.filepath,
            }

        # Collect imports
        for imp in parsed.imports:
            module_imports[mod].append({
                "module": imp.module,
                "names": imp.names,
                "is_from": imp.is_from,
                "line": imp.line,
            })

    # ---- Phase 2: Create all graph nodes ----
    for file_info in project_info.files:
        mod = file_info.module_name
        parsed = file_info.parsed
        filepath = file_info.filepath

        graph.module_nodes[mod] = []

        # Top-level functions
        for func in parsed.functions:
            nid = _make_node_id(mod, None, func.name)
            node = CallNode(
                node_id=nid,
                name=func.name,
                kind="function",
                module_name=mod,
                filepath=filepath,
                start_line=func.start_line,
                end_line=func.end_line,
                docstring=func.docstring,
            )
            graph.nodes[nid] = node
            graph.module_nodes[mod].append(nid)

        # Class methods
        for cls in parsed.classes:
            class_key = f"{mod}:{cls.name}"
            graph.class_methods[class_key] = []

            for method in cls.methods:
                nid = _make_node_id(mod, cls.name, method.name)
                node = CallNode(
                    node_id=nid,
                    name=method.name,
                    kind="method",
                    module_name=mod,
                    filepath=filepath,
                    class_name=cls.name,
                    start_line=method.start_line,
                    end_line=method.end_line,
                    docstring=method.docstring,
                )
                graph.nodes[nid] = node
                graph.module_nodes[mod].append(nid)
                graph.class_methods[class_key].append(nid)

    # ---- Phase 3: Build import resolution map ----
    # For each module, what names does it import from where?
    # imported_name -> (source_module, source_class_or_func, is_class)
    import_resolution: Dict[str, Dict[str, Tuple[str, str, bool]]] = {}

    for mod, imports in module_imports.items():
        import_resolution[mod] = {}
        for imp in imports:
            src_mod = imp["module"]
            # Only resolve if source module is in our project
            if src_mod not in module_classes and src_mod not in module_functions:
                continue

            if imp["is_from"]:
                for name in imp["names"]:
                    # Check if it's a class
                    if name in module_classes.get(src_mod, {}):
                        import_resolution[mod][name] = (src_mod, name, True)
                    # Or a function
                    elif name in module_functions.get(src_mod, {}):
                        import_resolution[mod][name] = (src_mod, name, False)
            else:
                # `import module` - the module name itself is available
                import_resolution[mod][src_mod.split(".")[-1]] = (src_mod, "", None)

    # ---- Phase 4: Analyze self.attr assignments in __init__ ----
    # For composite calls like self.reservation_manager.create_reservation()
    # we need to know what class self.reservation_manager is.
    # Format: class_key (module:Class) -> {attr_name: target_class_key}
    composite_attr_map: Dict[str, Dict[str, str]] = {}

    for mod, classes in module_classes.items():
        for cls_name, cls_info in classes.items():
            class_key = f"{mod}:{cls_name}"
            cls_obj = cls_info["class_obj"]

            # Find __init__ method
            init_method = None
            for m in cls_obj.methods:
                if m.name == "__init__":
                    init_method = m
                    break

            if not init_method:
                continue

            # Parse __init__ source to find self.attr = ClassName() assignments
            filepath = cls_info["filepath"]
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    source = f.read()
                tree = ast.parse(source)
            except (SyntaxError, UnicodeDecodeError):
                continue

            # Walk the AST and find __init__
            class FoundInit(Exception):
                pass

            init_node = None
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == cls_name:
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                            init_node = item
                            break
                    break

            if not init_node:
                continue

            attr_map = {}
            for stmt in ast.walk(init_node):
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        # self.attr = ...
                        if (isinstance(target, ast.Attribute) and
                            isinstance(target.value, ast.Name) and
                            target.value.id == "self"):
                            attr_name = target.attr
                            # Check if value is a Call to a ClassName()
                            if isinstance(stmt.value, ast.Call):
                                class_ref = _resolve_call_target(stmt.value.func, mod, import_resolution.get(mod, {}))
                                if class_ref:
                                    attr_map[attr_name] = class_ref

            composite_attr_map[class_key] = attr_map

    # ---- Phase 5: Resolve calls for each node ----
    for file_info in project_info.files:
        mod = file_info.module_name
        parsed = file_info.parsed
        filepath = file_info.filepath

        # Re-parse source for detailed call analysis
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            continue

        # For each function/method, find all calls and resolve them
        for cls in parsed.classes:
            class_key = f"{mod}:{cls.name}"
            for method in cls.methods:
                nid = _make_node_id(mod, cls.name, method.name)
                _resolve_method_calls(
                    tree=tree,
                    method_name=method.name,
                    class_name=cls.name,
                    module_name=mod,
                    node_id=nid,
                    graph=graph,
                    import_res=import_resolution.get(mod, {}),
                    module_classes=module_classes,
                    module_functions=module_functions,
                    composite_attrs=composite_attr_map.get(class_key, {}),
                    current_class_key=class_key,
                )

        for func in parsed.functions:
            nid = _make_node_id(mod, None, func.name)
            _resolve_function_calls(
                tree=tree,
                func_name=func.name,
                module_name=mod,
                node_id=nid,
                graph=graph,
                import_res=import_resolution.get(mod, {}),
                module_classes=module_classes,
                module_functions=module_functions,
            )

    # ---- Phase 6: Compute entry points and leaves ----
    for nid, node in graph.nodes.items():
        if not node.calls:
            graph.leaves.append(nid)

    # Entry points: public methods with no incoming calls AND meaningful outgoing calls,
    # or public methods that are top-level orchestration points
    for nid, node in graph.nodes.items():
        if node.name.startswith("_"):
            continue
        if node.name in ("__init__", "__str__", "__repr__"):
            continue
        # Must not be called by anyone (truly an entry point)
        if node.called_by:
            continue
        # Must have some substance: either has outgoing calls, or is a state mutation with doc
        has_substance = len(node.calls) >= 1 or (node.docstring and len(node.docstring) > 20)
        if not has_substance:
            continue
        # Skip simple getters and list-only query methods with no internal logic
        name_lower = node.name.lower()
        is_simple_getter = (
            (name_lower.startswith("get_") or name_lower.startswith("list_"))
            and len(node.calls) == 0
        )
        if is_simple_getter:
            continue
        node.is_entry_point = True
        graph.entry_points.append(nid)

    # ---- Phase 7: Tag nodes with semantic categories ----
    _tag_nodes(graph)

    return graph


def _resolve_call_target(func_node: ast.expr, module_name: str,
                         import_res: Dict[str, Tuple[str, str, bool]]) -> Optional[str]:
    """
    Resolve a function/method call expression to a class key if possible.
    Returns class_key like "module:ClassName" or None.
    """
    # Simple name: ClassName()
    if isinstance(func_node, ast.Name):
        name = func_node.id
        if name in import_res:
            src_mod, src_name, is_class = import_res[name]
            if is_class:
                return f"{src_mod}:{src_name}"
        return None

    # Attribute: module.Class() or obj.method()
    if isinstance(func_node, ast.Attribute):
        # module.ClassName()
        if isinstance(func_node.value, ast.Name):
            base = func_node.value.id
            attr = func_node.attr
            # Check if base is an imported module
            if base in import_res:
                src_mod, _, _ = import_res[base]
                # attr could be a class name in that module
                # We'll check later
                return None  # Can't fully resolve without module_classes
        return None

    return None


def _find_function_ast(tree: ast.AST, func_name: str, class_name: Optional[str] = None) -> Optional[ast.AST]:
    """Find the AST node for a specific function/method."""
    if class_name:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == func_name:
                        return item
                return None
        return None
    else:
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
                return node
        return None


def _collect_calls(func_ast: ast.AST) -> List[Tuple[ast.Call, int]]:
    """Collect all Call nodes inside a function with their line numbers."""
    calls = []
    for node in ast.walk(func_ast):
        if isinstance(node, ast.Call):
            calls.append((node, node.lineno))
    return calls


def _resolve_method_calls(tree, method_name, class_name, module_name, node_id,
                          graph, import_res, module_classes, module_functions,
                          composite_attrs, current_class_key):
    """Resolve all calls within a method and add edges to the graph."""
    func_ast = _find_function_ast(tree, method_name, class_name)
    if not func_ast:
        return

    calls = _collect_calls(func_ast)
    # Deduplicate by target
    target_counts: Dict[Tuple[str, str, int], int] = {}  # (to_node, call_type, line) -> count

    for call_node, line_no in calls:
        target = _resolve_single_call(
            call_node.func,
            module_name=module_name,
            class_name=class_name,
            import_res=import_res,
            module_classes=module_classes,
            module_functions=module_functions,
            composite_attrs=composite_attrs,
            current_class_key=current_class_key,
        )
        if target:
            key = (target[0], target[1], line_no)
            target_counts[key] = target_counts.get(key, 0) + 1

    source_node = graph.nodes.get(node_id)
    if not source_node:
        return

    for (to_id, call_type, line), count in target_counts.items():
        if to_id not in graph.nodes:
            continue
        edge = CallEdge(
            from_node=node_id,
            to_node=to_id,
            call_count=count,
            call_type=call_type,
            line_number=line,
        )
        source_node.calls.append(edge)
        graph.nodes[to_id].called_by.append(edge)
        graph.edges.append(edge)


def _resolve_function_calls(tree, func_name, module_name, node_id,
                            graph, import_res, module_classes, module_functions):
    """Resolve all calls within a top-level function."""
    func_ast = _find_function_ast(tree, func_name, None)
    if not func_ast:
        return

    calls = _collect_calls(func_ast)
    target_counts: Dict[Tuple[str, str, int], int] = {}

    for call_node, line_no in calls:
        target = _resolve_single_call(
            call_node.func,
            module_name=module_name,
            class_name=None,
            import_res=import_res,
            module_classes=module_classes,
            module_functions=module_functions,
            composite_attrs={},
            current_class_key=None,
        )
        if target:
            key = (target[0], target[1], line_no)
            target_counts[key] = target_counts.get(key, 0) + 1

    source_node = graph.nodes.get(node_id)
    if not source_node:
        return

    for (to_id, call_type, line), count in target_counts.items():
        if to_id not in graph.nodes:
            continue
        edge = CallEdge(
            from_node=node_id,
            to_node=to_id,
            call_count=count,
            call_type=call_type,
            line_number=line,
        )
        source_node.calls.append(edge)
        graph.nodes[to_id].called_by.append(edge)
        graph.edges.append(edge)


def _resolve_single_call(func_expr, module_name, class_name, import_res,
                         module_classes, module_functions, composite_attrs,
                         current_class_key) -> Optional[Tuple[str, str]]:
    """
    Resolve a single call expression to a target node_id.
    Returns (target_node_id, call_type) or None.

    Handles these patterns:
    1. func_name()                    -> local / imported function
    2. self.method()                  -> same-class method
    3. self.attr.method()             -> composite: attr is a known class instance
    4. ClassName()                    -> constructor (skip, not a business call)
    5. module.func()                  -> imported module function
    6. obj.method()                   -> unknown object, skip
    """
    # Case 1: simple name call
    if isinstance(func_expr, ast.Name):
        name = func_expr.id
        # Check if it's a local function in same module
        if name in module_functions.get(module_name, {}):
            return (f"{module_name}:{name}", "direct")
        # Check if it's an imported function
        if name in import_res:
            src_mod, src_name, is_class = import_res[name]
            if not is_class:
                return (f"{src_mod}:{src_name}", "imported")
        return None

    # Case 2-6: attribute call (something.method())
    if isinstance(func_expr, ast.Attribute):
        method_name = func_expr.attr
        base = func_expr.value

        # Case 2: self.method()
        if isinstance(base, ast.Name) and base.id == "self" and class_name:
            target_id = f"{module_name}:{class_name}.{method_name}"
            return (target_id, "self_method")

        # Case 3: self.attr.method()  (composite attribute chain)
        if (isinstance(base, ast.Attribute) and
            isinstance(base.value, ast.Name) and
            base.value.id == "self" and
            composite_attrs):
            attr_name = base.attr
            if attr_name in composite_attrs:
                target_class_key = composite_attrs[attr_name]
                # target_class_key is like "module:ClassName"
                target_mod, target_cls = target_class_key.split(":", 1)
                target_id = f"{target_mod}:{target_cls}.{method_name}"
                return (target_id, "composite_attr")

        # Case 5: Module.func() where Module is imported
        if isinstance(base, ast.Name):
            base_name = base.id
            if base_name in import_res:
                src_mod, _, _ = import_res[base_name]
                # Check if method_name is a function in src_mod
                if method_name in module_functions.get(src_mod, {}):
                    return (f"{src_mod}:{method_name}", "imported")
                # Check if it's a class's static/class method (hard to know, skip for now)

        # Case 6: other object.method() - can't resolve statically
        return None

    return None


def _tag_nodes(graph: ProjectCallGraph):
    """Tag nodes based on naming patterns and structural properties."""
    creation_keywords = {"create", "add", "new", "register", "insert", "initialize", "init"}
    query_keywords = {"get", "list", "find", "query", "search", "fetch", "show", "check", "has", "verify", "validate"}
    update_keywords = {"update", "modify", "set", "change", "edit", "assign", "approve", "reject", "close", "cancel", "complete", "borrow", "return", "deactivate"}
    delete_keywords = {"delete", "remove", "destroy", "drop"}
    validation_keywords = {"validate", "check", "verify", "ensure", "conflict", "permission"}
    state_keywords = {"status", "state", "approve", "reject", "cancel", "close", "complete", "open", "fix"}

    for nid, node in graph.nodes.items():
        name = node.name.lower()
        tags = set()

        if any(kw in name for kw in creation_keywords):
            tags.add("creation")
        if any(kw in name for kw in query_keywords):
            tags.add("query")
        if any(kw in name for kw in update_keywords):
            tags.add("update")
        if any(kw in name for kw in delete_keywords):
            tags.add("deletion")
        if any(kw in name for kw in validation_keywords):
            tags.add("validation")
        if any(kw in name for kw in state_keywords):
            tags.add("state_change")

        # Private methods are helper/util
        if node.name.startswith("_"):
            tags.add("helper")

        # Has internal calls -> orchestrator
        if len(node.calls) >= 3:
            tags.add("orchestrator")

        node.tags = sorted(tags)
