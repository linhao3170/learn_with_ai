"""
Mermaid 流程图生成器

借鉴 pyflowchart 的核心思路（AST -> 控制流图），
但输出格式改为 Mermaid，并且增加：
- 节点与源码行号的双向映射
- 业务语义标注
- 模块级/函数级两种粒度

输出的 Mermaid 语法可以直接交给 mermaid.js 渲染成交互式 SVG。
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple


@dataclass
class FlowNode:
    """流程图节点"""
    node_id: str
    label: str
    node_type: str  # start / end / operation / condition / io / subroutine
    line_start: int = 0
    line_end: int = 0
    code_snippet: str = ""
    annotations: List[str] = field(default_factory=list)  # 业务标注


@dataclass
class FlowEdge:
    """流程图边"""
    from_id: str
    to_id: str
    label: str = ""


@dataclass
class FlowchartData:
    """流程图数据（结构化，前端可用）"""
    nodes: List[FlowNode] = field(default_factory=list)
    edges: List[FlowEdge] = field(default_factory=list)
    title: str = ""
    mermaid_syntax: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "nodes": [
                {
                    "id": n.node_id,
                    "label": n.label,
                    "type": n.node_type,
                    "line_start": n.line_start,
                    "line_end": n.line_end,
                    "code_snippet": n.code_snippet,
                    "annotations": n.annotations,
                }
                for n in self.nodes
            ],
            "edges": [
                {"from": e.from_id, "to": e.to_id, "label": e.label}
                for e in self.edges
            ],
            "mermaid_syntax": self.mermaid_syntax,
        }


class FlowchartGenerator:
    """
    Mermaid 流程图生成器

    支持两种粒度：
    1. 函数级流程图：展示函数内部的控制流（if/else/for/while/try）
    2. 模块级流程图：展示函数间调用关系和主业务流程
    """

    def __init__(self):
        self._node_counter = 0

    def _next_id(self, prefix: str = "n") -> str:
        self._node_counter += 1
        return f"{prefix}{self._node_counter}"

    # ===== 函数级流程图 =====

    def generate_function_flowchart(
        self,
        source_code: str,
        function_name: str,
    ) -> FlowchartData:
        """
        生成指定函数的内部控制流图

        Args:
            source_code: 完整源码
            function_name: 函数名

        Returns:
            FlowchartData 流程图数据
        """
        tree = ast.parse(source_code)
        lines = source_code.splitlines()

        # 找到目标函数
        func_node = self._find_function(tree, function_name)
        if not func_node:
            return FlowchartData(title=f"{function_name} (未找到)")

        self._node_counter = 0
        nodes: List[FlowNode] = []
        edges: List[FlowEdge] = []

        # 开始节点
        start_id = self._next_id()
        nodes.append(
            FlowNode(
                node_id=start_id,
                label=f"开始\n{function_name}",
                node_type="start",
                line_start=func_node.lineno,
                line_end=func_node.lineno,
            )
        )

        # 分析函数体
        last_ids = [start_id]
        last_ids = self._process_body(
            func_node.body, lines, nodes, edges, last_ids
        )

        # 结束节点
        end_id = self._next_id()
        nodes.append(
            FlowNode(
                node_id=end_id,
                label="结束",
                node_type="end",
                line_start=func_node.end_lineno or func_node.lineno,
                line_end=func_node.end_lineno or func_node.lineno,
            )
        )
        for lid in last_ids:
            edges.append(FlowEdge(from_id=lid, to_id=end_id))

        # 生成 Mermaid 语法
        mermaid = self._to_mermaid(nodes, edges, title=function_name)

        return FlowchartData(
            nodes=nodes,
            edges=edges,
            title=function_name,
            mermaid_syntax=mermaid,
        )

    def _find_function(self, tree: ast.AST, name: str) -> Optional[ast.FunctionDef]:
        """在 AST 中查找指定函数（支持类方法）"""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == name:
                    return node
        return None

    def _process_body(
        self,
        body: List[ast.stmt],
        lines: List[str],
        nodes: List[FlowNode],
        edges: List[FlowEdge],
        prev_ids: List[str],
    ) -> List[str]:
        """
        处理一组语句块，返回最后的节点 ID 列表
        prev_ids: 上一步的节点 ID 列表（可能有多个分支）
        """
        current_ids = prev_ids

        for stmt in body:
            current_ids = self._process_stmt(stmt, lines, nodes, edges, current_ids)

        return current_ids

    def _process_stmt(
        self,
        stmt: ast.stmt,
        lines: List[str],
        nodes: List[FlowNode],
        edges: List[FlowEdge],
        prev_ids: List[str],
    ) -> List[str]:
        """处理单条语句，返回出口节点 ID 列表"""

        # if / elif / else
        if isinstance(stmt, ast.If):
            return self._process_if(stmt, lines, nodes, edges, prev_ids)

        # for 循环
        if isinstance(stmt, ast.For):
            return self._process_for(stmt, lines, nodes, edges, prev_ids)

        # while 循环
        if isinstance(stmt, ast.While):
            return self._process_while(stmt, lines, nodes, edges, prev_ids)

        # try/except
        if isinstance(stmt, (ast.Try,)):
            return self._process_try(stmt, lines, nodes, edges, prev_ids)

        # raise
        if isinstance(stmt, ast.Raise):
            node_id = self._next_id()
            label = "抛出异常"
            snippet = self._get_snippet(lines, stmt.lineno, stmt.end_lineno or stmt.lineno)
            nodes.append(
                FlowNode(
                    node_id=node_id,
                    label=label,
                    node_type="operation",
                    line_start=stmt.lineno,
                    line_end=stmt.end_lineno or stmt.lineno,
                    code_snippet=snippet,
                    annotations=["异常处理"],
                )
            )
            for pid in prev_ids:
                edges.append(FlowEdge(from_id=pid, to_id=node_id))
            return [node_id]

        # return
        if isinstance(stmt, ast.Return):
            node_id = self._next_id()
            snippet = self._get_snippet(lines, stmt.lineno, stmt.end_lineno or stmt.lineno)
            nodes.append(
                FlowNode(
                    node_id=node_id,
                    label="返回结果",
                    node_type="end",
                    line_start=stmt.lineno,
                    line_end=stmt.end_lineno or stmt.lineno,
                    code_snippet=snippet,
                )
            )
            for pid in prev_ids:
                edges.append(FlowEdge(from_id=pid, to_id=node_id))
            return [node_id]

        # 普通语句（赋值、函数调用等）合并成操作节点
        node_id = self._next_id()
        snippet = self._get_snippet(lines, stmt.lineno, stmt.end_lineno or stmt.lineno)
        # 简化：取第一行作为标签
        label = snippet.strip().split("\n")[0][:30]
        if len(snippet.strip().split("\n")) > 1:
            label += "..."

        nodes.append(
            FlowNode(
                node_id=node_id,
                label=label,
                node_type="operation",
                line_start=stmt.lineno,
                line_end=stmt.end_lineno or stmt.lineno,
                code_snippet=snippet,
            )
        )
        for pid in prev_ids:
            edges.append(FlowEdge(from_id=pid, to_id=node_id))
        return [node_id]

    def _process_if(
        self,
        stmt: ast.If,
        lines: List[str],
        nodes: List[FlowNode],
        edges: List[FlowEdge],
        prev_ids: List[str],
    ) -> List[str]:
        """处理 if 语句"""
        # 条件节点
        cond_id = self._next_id()
        cond_snippet = self._get_snippet(lines, stmt.lineno, stmt.lineno)
        # 提取条件文本
        cond_text = cond_snippet.strip()
        if cond_text.startswith("if ") and cond_text.endswith(":"):
            cond_text = cond_text[3:-1].strip()

        nodes.append(
            FlowNode(
                node_id=cond_id,
                label=cond_text[:40],
                node_type="condition",
                line_start=stmt.lineno,
                line_end=stmt.lineno,
                code_snippet=cond_snippet.strip(),
                annotations=["条件判断"],
            )
        )
        for pid in prev_ids:
            edges.append(FlowEdge(from_id=pid, to_id=cond_id))

        # 真分支
        true_ids = self._process_body(stmt.body, lines, nodes, edges, [cond_id])
        for e in edges:
            if e.from_id == cond_id and e.to_id == (stmt.body[0].lineno if hasattr(stmt.body[0], 'lineno') else None):
                pass  # 已经有边了

        # 找从 cond_id 出发到 body 第一个节点的边，加标签
        first_body_node = self._find_first_node_of_body(nodes, stmt.body)
        for e in edges:
            if e.from_id == cond_id and e.to_id == first_body_node:
                e.label = "是"
                break
        else:
            # 手动加
            if true_ids:
                for e in edges:
                    if e.from_id == cond_id:
                        e.label = "是"
                        break

        # 假分支 (elif/else)
        false_ids: List[str] = []
        if stmt.orelse:
            # 检查 orelse 里是不是 elif
            if len(stmt.orelse) == 1 and isinstance(stmt.orelse[0], ast.If):
                # elif: 递归处理
                false_ids = self._process_body(stmt.orelse, lines, nodes, edges, [cond_id])
            else:
                # else 分支
                false_ids = self._process_body(stmt.orelse, lines, nodes, edges, [cond_id])

            # 给从 cond_id 到 else 第一个节点的边加"否"标签
            first_else_node = self._find_first_node_of_body(nodes, stmt.orelse)
            for e in edges:
                if e.from_id == cond_id and e.to_id == first_else_node:
                    e.label = "否"
                    break

        # 合并出口
        all_exits = true_ids + false_ids
        return all_exits if all_exits else [cond_id]

    def _find_first_node_of_body(self, nodes: List[FlowNode], body: List[ast.stmt]) -> Optional[str]:
        """找到 body 中第一条语句对应的节点 ID"""
        if not body:
            return None
        first_line = body[0].lineno
        for n in nodes:
            if n.line_start == first_line and n.node_type != "condition":
                return n.node_id
        return None

    def _process_for(
        self,
        stmt: ast.For,
        lines: List[str],
        nodes: List[FlowNode],
        edges: List[FlowEdge],
        prev_ids: List[str],
    ) -> List[str]:
        """处理 for 循环"""
        # 循环条件节点
        loop_id = self._next_id()
        snippet = self._get_snippet(lines, stmt.lineno, stmt.lineno)
        label = snippet.strip()
        if label.startswith("for ") and label.endswith(":"):
            label = label[4:-1].strip()

        nodes.append(
            FlowNode(
                node_id=loop_id,
                label=f"循环: {label[:30]}",
                node_type="condition",
                line_start=stmt.lineno,
                line_end=stmt.lineno,
                code_snippet=snippet.strip(),
                annotations=["循环结构"],
            )
        )
        for pid in prev_ids:
            edges.append(FlowEdge(from_id=pid, to_id=loop_id))

        # 循环体
        body_ids = self._process_body(stmt.body, lines, nodes, edges, [loop_id])
        # 循环体回到循环条件
        for bid in body_ids:
            edges.append(FlowEdge(from_id=bid, to_id=loop_id, label="继续"))

        return [loop_id]

    def _process_while(
        self,
        stmt: ast.While,
        lines: List[str],
        nodes: List[FlowNode],
        edges: List[FlowEdge],
        prev_ids: List[str],
    ) -> List[str]:
        """处理 while 循环"""
        loop_id = self._next_id()
        snippet = self._get_snippet(lines, stmt.lineno, stmt.lineno)
        label = snippet.strip()
        if label.startswith("while ") and label.endswith(":"):
            label = label[6:-1].strip()

        nodes.append(
            FlowNode(
                node_id=loop_id,
                label=f"当 {label[:30]}",
                node_type="condition",
                line_start=stmt.lineno,
                line_end=stmt.lineno,
                code_snippet=snippet.strip(),
                annotations=["循环结构"],
            )
        )
        for pid in prev_ids:
            edges.append(FlowEdge(from_id=pid, to_id=loop_id))

        body_ids = self._process_body(stmt.body, lines, nodes, edges, [loop_id])
        for bid in body_ids:
            edges.append(FlowEdge(from_id=bid, to_id=loop_id))

        return [loop_id]

    def _process_try(
        self,
        stmt: ast.Try,
        lines: List[str],
        nodes: List[FlowNode],
        edges: List[FlowEdge],
        prev_ids: List[str],
    ) -> List[str]:
        """处理 try/except"""
        try_id = self._next_id()
        nodes.append(
            FlowNode(
                node_id=try_id,
                label="尝试执行",
                node_type="operation",
                line_start=stmt.lineno,
                line_end=stmt.lineno,
                code_snippet="try:",
                annotations=["异常处理"],
            )
        )
        for pid in prev_ids:
            edges.append(FlowEdge(from_id=pid, to_id=try_id))

        # try 体
        body_ids = self._process_body(stmt.body, lines, nodes, edges, [try_id])

        # except 块
        except_ids: List[str] = []
        for handler in stmt.handlers:
            exc_id = self._next_id()
            exc_name = handler.type.id if isinstance(handler.type, ast.Name) else "Exception"
            nodes.append(
                FlowNode(
                    node_id=exc_id,
                    label=f"捕获异常\n{exc_name}",
                    node_type="condition",
                    line_start=handler.lineno,
                    line_end=handler.lineno,
                    annotations=["异常处理"],
                )
            )
            edges.append(FlowEdge(from_id=try_id, to_id=exc_id))
            handler_ids = self._process_body(
                handler.body, lines, nodes, edges, [exc_id]
            )
            except_ids.extend(handler_ids)

        return body_ids + except_ids

    def _get_snippet(self, lines: List[str], start: int, end: int) -> str:
        if start < 1:
            start = 1
        if end > len(lines):
            end = len(lines)
        return "\n".join(lines[start - 1 : end])

    # ===== 模块级流程图 =====

    def generate_module_flowchart(
        self,
        analysis_result: dict,
    ) -> FlowchartData:
        """
        从分析结果生成模块级业务流程图

        使用分析结果中的 main_flow 和 call_graph 生成高层流程图。
        """
        self._node_counter = 0
        nodes: List[FlowNode] = []
        edges: List[FlowEdge] = []

        main_flow = analysis_result.get("main_flow", [])
        if not main_flow:
            return FlowchartData(title="主流程")

        # 开始
        start_id = self._next_id()
        nodes.append(FlowNode(node_id=start_id, label="开始", node_type="start"))

        prev_id = start_id
        for step in main_flow:
            node_id = self._next_id()
            desc = step.get("description", "")
            # 简化标签
            label = desc.replace("实现 ", "").replace("操作：", ":\n")
            if len(label) > 30:
                label = label[:27] + "..."

            annotations = []
            patterns = analysis_result.get("patterns", [])
            func_name = step.get("related_function", "")
            for p in patterns:
                if p.get("target_name") == func_name:
                    annotations.append(p.get("pattern_name", ""))

            nodes.append(
                FlowNode(
                    node_id=node_id,
                    label=label,
                    node_type="operation",
                    line_start=step.get("line_start", 0),
                    line_end=step.get("line_end", 0),
                    annotations=list(set(a for a in annotations if a)),
                )
            )
            edges.append(FlowEdge(from_id=prev_id, to_id=node_id))
            prev_id = node_id

        # 结束
        end_id = self._next_id()
        nodes.append(FlowNode(node_id=end_id, label="结束", node_type="end"))
        edges.append(FlowEdge(from_id=prev_id, to_id=end_id))

        mermaid = self._to_mermaid(nodes, edges, title="主业务流程")

        return FlowchartData(
            nodes=nodes,
            edges=edges,
            title="主业务流程",
            mermaid_syntax=mermaid,
        )

    # ===== Mermaid 输出 =====

    def _to_mermaid(
        self,
        nodes: List[FlowNode],
        edges: List[FlowEdge],
        title: str = "",
    ) -> str:
        """将节点和边转换为 Mermaid flowchart 语法"""
        lines = ["flowchart TD"]

        # 节点形状映射
        shape_map = {
            "start": ("([", "])"),      # 体育场形（开始/结束）
            "end": ("([", "])"),
            "operation": ("[", "]"),    # 矩形（操作）
            "condition": ("{", "}"),    # 菱形（判断）
            "io": ("[/", "/]"),         # 平行四边形（IO）
            "subroutine": ("[[", "]]"), # 双矩形（子程序）
        }

        def _escape(text: str) -> str:
            # Mermaid 中文本需要用引号避免特殊字符问题
            return text.replace('"', "'").replace("\n", "<br/>")

        for node in nodes:
            left, right = shape_map.get(node.node_type, ("[", "]"))
            label = _escape(node.label)
            lines.append(f"    {node.node_id}{left}\"{label}\"{right}")

        for edge in edges:
            if edge.label:
                label = _escape(edge.label)
                lines.append(f"    {edge.from_id} -->|{label}| {edge.to_id}")
            else:
                lines.append(f"    {edge.from_id} --> {edge.to_id}")

        return "\n".join(lines)


def generate_mermaid_flowchart(source_code: str, function_name: str) -> FlowchartData:
    """便捷函数：生成函数的 Mermaid 流程图"""
    return FlowchartGenerator().generate_function_flowchart(source_code, function_name)
