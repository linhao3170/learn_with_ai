"""
第 4 步：事实绑定（README5 §3.1 第 4 步）—— 全部 ``verified``

把功能点成员函数里的 **``if`` 条件 / ``raise`` / 状态写入**抽成结构化的"业务事实"：

```json
{"fact_id": "f_0007", "capability_id": "c_...", "kind": "business_rule",
 "code": "if start < res_end and end > res_start",
 "file": "sample_projects/.../reservation_manager.py", "start_line": 122, "confidence": "verified"}
```

**纪律**：``text`` 的中文描述如果不能从代码确定，就**只保留代码表达式**并标
``verified_code_only``，绝不编业务含义（README4 §9.2、README5 §3.1）。
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from ..parser.ast_cache import get_tree

#: 事实类型
KIND_RULE = "business_rule"
KIND_RAISE = "exception"
KIND_STATE = "state_change"
KIND_GUARD = "guard"

#: 单条事实的代码片段长度上限（避免题干里塞进一整个函数）
MAX_CODE_LEN = 160


@dataclass
class Fact:
    """一条可核验的业务事实（verified）。"""
    fact_id: str
    capability_id: str
    kind: str
    code: str
    file: str
    start_line: int
    end_line: int
    symbol: str = ""
    text: str = ""
    text_status: str = "verified_code_only"   # verified_code_only | from_docstring
    confidence: str = "verified"

    def to_dict(self) -> dict:
        return {
            "fact_id": self.fact_id,
            "capability_id": self.capability_id,
            "kind": self.kind,
            "code": self.code,
            "text": self.text,
            "text_status": self.text_status,
            "file": self.file,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "symbol": self.symbol,
            "confidence": self.confidence,
        }


def _clip(text: str) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= MAX_CODE_LEN else text[: MAX_CODE_LEN - 1] + "…"


def _find_function_node(tree: ast.AST, symbol: str, start_line: int) -> Optional[ast.AST]:
    """在 AST 里按符号名 + 起始行定位函数节点（同名重载时用行号消歧）。"""
    best: Optional[ast.AST] = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol:
            if getattr(node, "lineno", -1) == start_line:
                return node
            if best is None:
                best = node
    return best


def _condition_text(test: ast.AST) -> str:
    try:
        return ast.unparse(test)
    except Exception:  # pragma: no cover - 极老的 AST 才可能失败
        return ""


def bind_facts(capabilities, units, project_info) -> List[Fact]:
    """第 4 步：为每个功能点绑定规则/异常/状态事实。

    Args:
        capabilities: ``Capability[]``（来自 capabilities.py）
        units: ``Unit[]``（用来把 symbol + 行号对应回文件）
        project_info: ``ProjectInfo``（用来取 AST 树）

    Returns:
        ``Fact[]``，按 ``(capability_id, file, start_line, kind)`` 排序（可复现）。
    """
    # symbol+line -> 文件绝对路径（用于取 AST）
    abs_path_of_rel: Dict[str, str] = {}
    for file_info in getattr(project_info, "files", []) or []:
        abs_path_of_rel[file_info.rel_path] = file_info.filepath

    facts: List[Fact] = []
    counter = 0

    for cap in sorted(capabilities, key=lambda c: (c.parent_id, c.capability_id)):
        for member in sorted(cap.members, key=lambda m: (m.file, m.start_line, m.symbol)):
            abs_path = abs_path_of_rel.get(member.file)
            tree = get_tree(abs_path) if abs_path else None

            # --- 状态变化：直接用状态追踪结果（verified） ---
            for attr in sorted(set(member.state_writes)):
                counter += 1
                facts.append(Fact(
                    fact_id=f"f_{counter:04d}",
                    capability_id=cap.capability_id,
                    kind=KIND_STATE,
                    code=f"{member.symbol} 写入 {attr}",
                    text="",
                    file=member.file,
                    start_line=member.start_line,
                    end_line=member.end_line,
                    symbol=member.symbol,
                ))

            if tree is None:
                continue

            func_node = _find_function_node(tree, member.symbol, member.start_line)
            if func_node is None:
                continue

            # --- if 条件：业务规则候选（verified，只给代码，不编语义） ---
            for node in ast.walk(func_node):
                if not isinstance(node, ast.If):
                    continue
                condition = _condition_text(node.test)
                if not condition:
                    continue
                line = int(getattr(node, "lineno", member.start_line))
                # 守卫条件（在函数开头、直接 raise/return）单独归类，便于教学
                is_guard = any(isinstance(s, (ast.Raise, ast.Return)) for s in node.body)
                counter += 1
                facts.append(Fact(
                    fact_id=f"f_{counter:04d}",
                    capability_id=cap.capability_id,
                    kind=KIND_GUARD if is_guard else KIND_RULE,
                    code=_clip(condition),
                    text="",
                    file=member.file,
                    start_line=line,
                    end_line=line,
                    symbol=member.symbol,
                ))

            # --- raise：异常分支（verified，带异常类型） ---
            for node in ast.walk(func_node):
                if not isinstance(node, ast.Raise) or node.exc is None:
                    continue
                exc = node.exc
                if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name):
                    exc_name = exc.func.id
                    message = ""
                    if exc.args and isinstance(exc.args[0], ast.Constant):
                        message = str(exc.args[0].value)
                    code = f"raise {exc_name}({message})" if message else f"raise {exc_name}"
                elif isinstance(exc, ast.Name):
                    code = f"raise {exc.id}"
                else:
                    continue
                line = int(getattr(node, "lineno", member.start_line))
                counter += 1
                facts.append(Fact(
                    fact_id=f"f_{counter:04d}",
                    capability_id=cap.capability_id,
                    kind=KIND_RAISE,
                    code=_clip(code),
                    text="",
                    file=member.file,
                    start_line=line,
                    end_line=line,
                    symbol=member.symbol,
                ))

    facts.sort(key=lambda f: (f.capability_id, f.file, f.start_line, f.kind, f.fact_id))
    return facts


def group_facts_by_capability(facts: Sequence[Fact]) -> Dict[str, Dict[str, List[Fact]]]:
    """把事实按 ``capability_id → kind → Fact[]`` 分组，供卡片生成使用。"""
    grouped: Dict[str, Dict[str, List[Fact]]] = {}
    for fact in facts:
        grouped.setdefault(fact.capability_id, {}).setdefault(fact.kind, []).append(fact)
    return grouped
