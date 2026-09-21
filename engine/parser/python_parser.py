"""
Python 代码解析器

基于 Python 标准库 ast + astroid，提取代码的结构化信息：
- 模块、类、函数/方法
- 文档字符串
- 行号证据
- 导入信息
- 控制流节点计数
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class FunctionInfo:
    """函数/方法信息"""
    name: str
    start_line: int
    end_line: int
    docstring: Optional[str] = None
    parameters: List[str] = field(default_factory=list)
    return_annotation: Optional[str] = None
    is_method: bool = False
    is_async: bool = False
    decorators: List[str] = field(default_factory=list)
    # 控制流统计（用于难度评估和模式识别）
    if_count: int = 0
    loop_count: int = 0
    try_count: int = 0
    raise_count: int = 0
    call_count: int = 0
    # 调用的函数名（候选）
    called_functions: List[str] = field(default_factory=list)


@dataclass
class ClassInfo:
    """类信息"""
    name: str
    start_line: int
    end_line: int
    docstring: Optional[str] = None
    bases: List[str] = field(default_factory=list)
    methods: List[FunctionInfo] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)


@dataclass
class ImportInfo:
    """导入信息"""
    module: str
    names: List[str] = field(default_factory=list)
    line: int = 0
    is_from: bool = False


@dataclass
class ParsedResult:
    """解析结果"""
    source_code: str
    source_lines: List[str]
    module_docstring: Optional[str] = None
    functions: List[FunctionInfo] = field(default_factory=list)  # 顶层函数
    classes: List[ClassInfo] = field(default_factory=list)
    imports: List[ImportInfo] = field(default_factory=list)
    ast_tree: Optional[ast.AST] = None  # 原始 AST（需要时可用）

    def get_all_functions(self) -> List[FunctionInfo]:
        """获取所有函数（包括类方法）"""
        all_funcs = list(self.functions)
        for cls in self.classes:
            all_funcs.extend(cls.methods)
        return all_funcs

    def get_code_snippet(self, start_line: int, end_line: int) -> str:
        """获取指定行号范围的代码片段（行号从1开始）"""
        if start_line < 1:
            start_line = 1
        if end_line > len(self.source_lines):
            end_line = len(self.source_lines)
        return "\n".join(self.source_lines[start_line - 1 : end_line])


class _ASTVisitor(ast.NodeVisitor):
    """AST 访问者，收集结构化信息"""

    def __init__(self, source_lines: List[str]):
        self.source_lines = source_lines
        self.functions: List[FunctionInfo] = []
        self.classes: List[ClassInfo] = []
        self.imports: List[ImportInfo] = []
        self._current_class: Optional[ClassInfo] = None

    # ---- 导入 ----
    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append(
                ImportInfo(
                    module=alias.name,
                    names=[alias.asname] if alias.asname else [alias.name.split(".")[0]],
                    line=node.lineno,
                    is_from=False,
                )
            )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            self.imports.append(
                ImportInfo(
                    module=node.module,
                    names=[a.name for a in node.names],
                    line=node.lineno,
                    is_from=True,
                )
            )
        self.generic_visit(node)

    # ---- 类 ----
    def visit_ClassDef(self, node: ast.ClassDef):
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(ast.unparse(base))

        decorators = []
        for dec in node.decorator_list:
            decorators.append(ast.unparse(dec))

        cls_info = ClassInfo(
            name=node.name,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            docstring=ast.get_docstring(node),
            bases=bases,
            decorators=decorators,
        )

        old_class = self._current_class
        self._current_class = cls_info

        # 只访问 body 里的方法
        for child in node.body:
            self.visit(child)

        self._current_class = old_class
        self.classes.append(cls_info)

    # ---- 函数 ----
    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._collect_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._collect_function(node, is_async=True)

    def _collect_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool):
        # 参数列表（去掉 self）
        params = []
        for arg in node.args.args:
            params.append(arg.arg)

        decorators = [ast.unparse(d) for d in node.decorator_list]

        # 控制流统计
        if_count = sum(1 for _ in _iter_nodes(node, ast.If))
        loop_count = sum(1 for _ in _iter_nodes(node, ast.For)) + sum(
            1 for _ in _iter_nodes(node, ast.While)
        )
        try_count = sum(1 for _ in _iter_nodes(node, ast.Try))
        raise_count = sum(1 for _ in _iter_nodes(node, ast.Raise))
        call_count = sum(1 for _ in _iter_nodes(node, ast.Call))

        # 被调函数名
        called = []
        for call_node in _iter_nodes(node, ast.Call):
            func = call_node.func
            if isinstance(func, ast.Name):
                called.append(func.id)
            elif isinstance(func, ast.Attribute):
                called.append(func.attr)
        # 去重但保持顺序
        seen = set()
        called_unique = []
        for c in called:
            if c not in seen:
                seen.add(c)
                called_unique.append(c)

        func_info = FunctionInfo(
            name=node.name,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            docstring=ast.get_docstring(node),
            parameters=params,
            return_annotation=ast.unparse(node.returns) if node.returns else None,
            is_method=self._current_class is not None,
            is_async=is_async,
            decorators=decorators,
            if_count=if_count,
            loop_count=loop_count,
            try_count=try_count,
            raise_count=raise_count,
            call_count=call_count,
            called_functions=called_unique,
        )

        if self._current_class is not None:
            self._current_class.methods.append(func_info)
        else:
            self.functions.append(func_info)


def _iter_nodes(node: ast.AST, node_type: type) -> list:
    """迭代指定类型的所有后代节点"""
    results = []
    for child in ast.walk(node):
        if isinstance(child, node_type):
            results.append(child)
    return results


class PythonParser:
    """Python 代码解析器"""

    def parse(self, source_code: str) -> ParsedResult:
        """
        解析 Python 源码，返回结构化结果。

        Args:
            source_code: Python 源码字符串

        Returns:
            ParsedResult 结构化解析结果

        Raises:
            SyntaxError: 源码语法错误
        """
        tree = ast.parse(source_code)
        lines = source_code.splitlines()

        visitor = _ASTVisitor(lines)
        visitor.visit(tree)

        module_doc = ast.get_docstring(tree)

        return ParsedResult(
            source_code=source_code,
            source_lines=lines,
            module_docstring=module_doc,
            functions=visitor.functions,
            classes=visitor.classes,
            imports=visitor.imports,
            ast_tree=tree,
        )


def parse_python(source_code: str) -> ParsedResult:
    """便捷函数：解析 Python 代码"""
    return PythonParser().parse(source_code)
