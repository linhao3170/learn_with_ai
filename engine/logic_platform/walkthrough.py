"""沉浸式学习业务逻辑 —— 逐段讲解生成器

把参考文档（``shuliyewu.txt``）的讲课形态做成**确定性、可复核**的产物。

它复刻的形态（逐字）
--------------------
::

    第 1 段：准备工作（175-188 行）
    <真实源码摘录，关键行带教学注释>
    重点记什么：
    - retrieve_citations() 是核心函数——把用户的问题去知识库（本地的）里搜
    - decision 是个很重要的变量——它记录"这个问题最终走了哪条路"
    一句话概括： 用户问了个问题，系统把问题接过来、找到会话、准备好秒表。

三个必须钉死的字面量（前端不得改写，见 ``render`` 块）：
- 段头：``第 {order} 段：{title}（{start}-{end} 行）``（全角冒号、全角括号、半角连字符）
- 要点标题：``重点记什么：``
- 一句话标题：``一句话概括： ``（**冒号后有一个半角空格**，母本 9 处全带）

设计立场：**引擎不写"漂亮话"，只写"有据可查的话"**
-----------------------------------------------------
本模块**不做任何 LLM 调用、不联网**（``engine/`` 的纪律，见
``engine/teaching/__init__.py``；三个测试脚本的 ``FORBIDDEN_IMPORTS`` 会强制这一点）。

生成方式：**先取事实，再套句式**。
1. 逐语句遍历 AST（与 ``engine/visualizer/flowchart.py`` 的
   ``_process_body`` / ``_process_stmt`` 同一思路，但这里不画流程图，
   而是把语句**按职责聚成段**）；
2. 每一段的"重点记什么"由**确定的信号**产生：调用了哪个已知能力点、
   写了哪个状态、哪一行 `return`、后面哪些行因此不执行、变量在后面哪一行被读；
3. 每一条要点、每一句总结都必带 ``evidence``（``file`` + ``start_line`` +
   ``end_line`` + 真实摘录 + ``excerpt_hash``）；
4. 讲不了的不讲 —— 宁可少一条要点，也不编一条业务含义（README §2.2：
   **无证据不入学生视图**）。

与母本的一处**刻意不同**（要如实说，不能装作一样）
--------------------------------------------------
母本在带读具体场景时会写「所以这个 if 的条件是 True，进入花括号！」。
本引擎**没有场景**（没有输入样本），静态分析只能知道"这里有个分支"，
**无法知道**它这次是真是假。所以 ``branch_detail.evaluates_to`` 一律是
``depends_on_scenario``，并由讲解句说明"真假取决于输入"。
这是本引擎比母本**更保守**的地方：母本那几句是举例，我们不许举例当结论。
"""

from __future__ import annotations

import ast
import copy
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..parser import ast_cache
from .hashing import sha256_text as _sha256, short_digest as _short_digest

ALGORITHM_VERSION = "walkthrough-1.0"

#: 生成主体。LLM 讲解层的产物会被标成 ``llm_draft``（见 ``narration.py``）。
GENERATED_BY_RULES = "ast_rule_engine"

#: 段头 / 要点 / 一句话的**字面模板**。前端必须照此渲染，不得改写
#: （``一句话概括：`` 的尾随空格是母本原样，故意保留）。
RENDER_TEMPLATES = {
    "header_format": "第 {order} 段：{title}（{start}-{end} 行）",
    "header_format_alt": "第 {start}-{end} 行：{title}",
    "bullets_heading": "重点记什么：",
    "summary_heading": "一句话概括： ",
    "know_enough_heading": "知道就行：",
    "lesson_recap_heading": "你现在需要记住的 {n} 个核心要点：",
    "lesson_open": (
        "好，代码拿到了，咱们一段一段啃。你不用记住每一行，我会告诉你"
        "哪些是核心概念一定要记住，哪些只是「知道有这么回事」就行。"
    ),
    "lesson_frame_prefix": "一句话先定调：",
    "lesson_close": "消化一下，有哪段没看懂的随时问我。",
}

#: 要点分类学（对应参考文档里「重点记什么」的 8 类 + 本引擎补的 2 类）
CATEGORY_SYMBOL_MEANING = "symbol_meaning"
CATEGORY_DATA_STRUCTURE = "data_structure"
CATEGORY_CONTROL_FLOW = "control_flow"
CATEGORY_RETURN_EARLY_EXIT = "return_early_exit"
CATEGORY_VARIABLE_USAGE = "variable_usage"
CATEGORY_DESIGN_INTENT = "design_intent"
CATEGORY_BOUNDARY_ENUM = "boundary_enum"
CATEGORY_DEFENSIVE_DESIGN = "defensive_design"
CATEGORY_WRAP_UP_DUTY = "wrap_up_duty"
CATEGORY_PARAMETER_VALUE = "parameter_value"

#: 段的种类（驱动前端图标与讲解口径）
KIND_PREPARE = "prepare"
KIND_CALL = "call"
KIND_BRANCH = "branch"
KIND_STATE_CHANGE = "state_change"
#: ``try/except`` —— 异常被**接住**（容错/降级）
KIND_EXCEPTION = "exception"
#: ``raise`` —— 异常被**抛出**（业务路径主动中断）
#:
#: 必须与 :data:`KIND_EXCEPTION` 分开：第一版把两者混成一个 ``exception``，
#: 结果生成器对 ``raise Error("read: End of string")`` 写出了
#: 「异常被接住而不是往上抛」—— 把**抛出**说成了**捕获**，
#: 是一句彻头彻尾的事实错误。校验器抓不到这类错（它只校验引用是否为真），
#: 只能靠生成阶段就把两种情况分开。
KIND_RAISE = "raise"
KIND_LOOP = "loop"
KIND_RETURN = "return"
KIND_CONFIG_DATA = "config_data"
KIND_WRAP_UP = "wrap_up"

#: Python 内置函数名 —— 调用它们不构成"业务能力"，不该出现在「知道就行」里。
#:
#: 这是一份**语言层事实**，不是业务词表，所以硬编码在这里不违反
#: 「业务词表必须外置到 engine/lexicon/」的纪律。
_PYTHON_BUILTINS = frozenset(
    """
    abs all any ascii bin bool breakpoint bytearray bytes callable chr classmethod
    compile complex delattr dict dir divmod enumerate eval exec filter float format
    frozenset getattr globals hasattr hash help hex id input int isinstance
    issubclass iter len list locals map max memoryview min next object oct open ord
    pow print property range repr reversed round set setattr slice sorted staticmethod
    str sum super tuple type vars zip __import__
    """.split()
    # 内置异常类：``raise ValueError(...)`` 里的 ``ValueError()`` 也是一次"调用"，
    # 但它是语言自带的异常类型，不是项目能力。第一版没排除它们，于是讲稿里
    # 出现了「`ValueError()` 不在本能力点的成员里 —— 你不用进它的内部」这种废话。
    + """
    ArithmeticError AssertionError AttributeError BaseException BlockingIOError
    BrokenPipeError BufferError BytesWarning ChildProcessError ConnectionAbortedError
    ConnectionError ConnectionRefusedError ConnectionResetError DeprecationWarning
    EOFError EncodingWarning EnvironmentError Exception FileExistsError
    FileNotFoundError FloatingPointError FutureWarning GeneratorExit IOError
    ImportError ImportWarning IndentationError IndexError InterruptedError
    IsADirectoryError KeyError KeyboardInterrupt LookupError MemoryError
    ModuleNotFoundError NameError NotADirectoryError NotImplementedError
    OSError OverflowError PendingDeprecationWarning PermissionError ProcessLookupError
    RecursionError ReferenceError ResourceWarning RuntimeError RuntimeWarning
    StopAsyncIteration StopIteration SyntaxError SyntaxWarning SystemError
    SystemExit TabError TimeoutError TypeError UnboundLocalError UnicodeDecodeError
    UnicodeEncodeError UnicodeError UnicodeTranslateError UnicodeWarning
    UserWarning ValueError Warning ZeroDivisionError
    """.split()
)

#: 段标题里**不许**出现的名称特征。
#:
#: 「其他能力（待归类：advance、has_next、peek）」是引擎的**诚实降级产物**
#: （``capabilities.py`` 的 Rule C），它作为能力名展示是对的，
#: 但拿它当**教学段标题**就荒谬了 —— 标题要说"这一段在做什么"，
#: 而不是"这些函数还没归类"。所以这些名字一律退回结构推导标题。
_TITLE_REJECT_TOKENS = ("待归类", "其他能力", "unclassified")

#: 段标题的来源标记 —— 前端必须显示，不许把推断的标题当成代码事实。
TITLE_FROM_CAPABILITY = "from_capability_name"
TITLE_FROM_DOCSTRING = "from_docstring"
TITLE_FROM_STRUCTURE = "from_structure"

#: 摘录里给关键行加的教学注释（role 决定前端样式）
ROLE_EXPLAIN = "explain"
ROLE_RETURN_MARKER = "return_marker"
ROLE_KEY_CALL = "key_call"
ROLE_STATE_CHANGE = "state_change"
ROLE_WARN = "warn"

#: 单个摘录里最多标注几行（避免整段全是注释，母本只在关键行标注）
MAX_ANNOTATIONS_PER_SEGMENT = 6
#: 要点条数上下限（母本每段 3–5 条；少于 1 条则该段不产要点标题）
MIN_BULLETS = 1
MAX_BULLETS = 5


# ============================================================
# 证据与断言（防幻觉的数据结构）
# ============================================================


@dataclass
class EvidenceRef:
    """一条可回指的证据。``file`` 必须是项目内相对路径（POSIX）。

    四个身份字段的分工（目标要求 ``fact_id + file + start_line + end_line + excerpt_hash``）
    -------------------------------------------------------------------------------------
    - ``evidence_id``：**本证据自己的稳定 id**，由 ``file:start-end`` 派生，确定性可复现。
      有了它，教师审核意见才能挂到"某一条证据"上（按数组下标挂会在插删后错位）。
    - ``fact_id``：**图谱事实表的 id**（``business_graph.facts[].fact_id``）。
      证据的行范围落在某条已绑定事实内时填上，**匹配不到就是空串** ——
      不为了"看起来完整"而编一个 id（图谱里确实有大量行不属于任何 fact）。
    - ``excerpt`` / ``excerpt_hash``：摘录与哈希，**校验器拿去和磁盘源码逐字符比对**。
    """

    file: str = ""
    start_line: int = 0
    end_line: int = 0
    symbol: str = ""
    excerpt: str = ""
    excerpt_hash: str = ""
    confidence: str = "verified"
    reason: str = ""
    fact_id: str = ""
    evidence_id: str = ""

    def to_dict(self) -> dict:
        return {
            "evidence_id": self.evidence_id,
            "fact_id": self.fact_id,
            "file": self.file,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "symbol": self.symbol,
            "excerpt": self.excerpt,
            "excerpt_hash": self.excerpt_hash,
            "confidence": self.confidence,
            "reason": self.reason,
        }


@dataclass
class Claim:
    """一句断言。**每句话都必须有一条以上证据**，否则不进学生视图。"""

    claim_id: str = ""
    claim_text: str = ""
    category: str = ""
    evidence: List[EvidenceRef] = field(default_factory=list)
    confidence: str = "verified"
    verified: bool = True
    reject_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "claim_text": self.claim_text,
            "category": self.category,
            "evidence": [e.to_dict() for e in self.evidence],
            "confidence": self.confidence,
            "verified": self.verified,
            "reject_reason": self.reject_reason,
        }


@dataclass
class LineAnnotation:
    """摘录里某一行的教学注释。``is_original_comment=True`` 表示这是源码自带注释。"""

    line: int = 0
    text: str = ""
    role: str = ROLE_EXPLAIN
    is_original_comment: bool = False

    def to_dict(self) -> dict:
        return {
            "line": self.line,
            "text": self.text,
            "role": self.role,
            "is_original_comment": self.is_original_comment,
        }


@dataclass
class BranchDetail:
    """分支段的结构化事实 —— 「看到 return 就表示这条分支结束了」的依据。"""

    condition_code: str = ""
    condition_line: int = 0
    #: 恒为 ``depends_on_scenario``：静态分析不知道输入，不许假装知道真假。
    evaluates_to: str = "depends_on_scenario"
    taken_path: str = ""
    skipped_start_line: int = 0
    skipped_end_line: int = 0
    is_return: bool = False
    return_at_line: int = 0
    return_expr: str = ""
    return_ordinal_in_function: int = 0
    raises: bool = False
    is_terminal: bool = False

    def to_dict(self) -> dict:
        skipped = None
        if self.skipped_start_line and self.skipped_end_line:
            skipped = {"start_line": self.skipped_start_line, "end_line": self.skipped_end_line}
        return {
            "condition_code": self.condition_code,
            "condition_line": self.condition_line,
            "evaluates_to": self.evaluates_to,
            "taken_path": self.taken_path,
            "skipped_line_range": skipped,
            "is_return": self.is_return,
            "return_at_line": self.return_at_line,
            "return_expr": self.return_expr,
            "return_ordinal_in_function": self.return_ordinal_in_function,
            "raises": self.raises,
            "is_terminal": self.is_terminal,
        }


@dataclass
class Segment:
    """一段。字段与参考文档的槽位一一对应。"""

    segment_id: str = ""
    order: int = 0
    title: str = ""
    title_status: str = TITLE_FROM_STRUCTURE
    header_text: str = ""
    segment_kind: str = KIND_PREPARE

    file: str = ""
    start_line: int = 0
    end_line: int = 0
    symbol: str = ""
    symbol_kind: str = "function"
    #: 本段所属的**函数**及其真实行范围 —— 参考文档总是先交代"只读 chat() 函数"，
    #: 没有这三个字段，学生看到段 1（84-87）接段 2（93）会以为中间丢了代码。
    member_symbol: str = ""
    member_start_line: int = 0
    member_end_line: int = 0

    code_excerpt: str = ""
    code_excerpt_hash: str = ""
    line_annotations: List[LineAnnotation] = field(default_factory=list)

    lead_in: str = ""
    emphasis_line: str = ""
    branch_detail: Optional[BranchDetail] = None

    must_remember: List[Claim] = field(default_factory=list)
    know_enough: List[Claim] = field(default_factory=list)
    one_sentence_summary: Optional[Claim] = None

    def to_dict(self) -> dict:
        return {
            "segment_id": self.segment_id,
            "order": self.order,
            "title": self.title,
            "title_status": self.title_status,
            "header_text": self.header_text,
            "segment_kind": self.segment_kind,
            "source": {
                "file": self.file,
                "display_path": self.file,
                "start_line": self.start_line,
                "end_line": self.end_line,
                "symbol": self.symbol,
                "symbol_kind": self.symbol_kind,
                "extra_ranges": [],
                "member_symbol": self.member_symbol,
                "member_start_line": self.member_start_line,
                "member_end_line": self.member_end_line,
            },
            "code_excerpt": self.code_excerpt,
            "code_excerpt_hash": self.code_excerpt_hash,
            "line_annotations": [a.to_dict() for a in self.line_annotations],
            "lead_in": self.lead_in,
            "emphasis_line": self.emphasis_line,
            "branch_detail": self.branch_detail.to_dict() if self.branch_detail else None,
            "must_remember": [c.to_dict() for c in self.must_remember],
            "know_enough": [c.to_dict() for c in self.know_enough],
            "one_sentence_summary": (
                self.one_sentence_summary.to_dict() if self.one_sentence_summary else None
            ),
        }


@dataclass
class Lesson:
    """一课（对应参考文档的一次 AI 回复）。"""

    lesson_id: str = ""
    lesson_number: int = 0
    title: str = ""
    capability_id: str = ""
    capability_name: str = ""
    section_id: str = ""
    section_name: str = ""
    level: str = ""

    intro: str = ""
    one_line_frame: str = ""
    segments: List[Segment] = field(default_factory=list)
    summary_diagram: str = ""
    lesson_recap: List[str] = field(default_factory=list)
    consolidate: str = ""
    next_action: str = "continue_reading"

    members_covered: List[Dict[str, Any]] = field(default_factory=list)
    members_total: int = 0
    truncated: bool = False
    truncation_reason: str = ""
    source_hash: str = ""
    review: Dict[str, Any] = field(default_factory=dict)
    caveats: List[str] = field(default_factory=list)
    render: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "lesson_version": ALGORITHM_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "lesson_id": self.lesson_id,
            "lesson_number": self.lesson_number,
            "title": self.title,
            "capability_id": self.capability_id,
            "capability_name": self.capability_name,
            "section_id": self.section_id,
            "section_name": self.section_name,
            "level": self.level,
            "intro": self.intro,
            "one_line_frame": self.one_line_frame,
            "segments": [s.to_dict() for s in self.segments],
            "summary_diagram": self.summary_diagram,
            "lesson_recap": list(self.lesson_recap),
            "consolidate": self.consolidate,
            "next_action": self.next_action,
            "members_covered": [dict(m) for m in self.members_covered],
            "members_total": self.members_total,
            "truncated": self.truncated,
            "truncation_reason": self.truncation_reason,
            "source_hash": self.source_hash,
            "review": dict(self.review),
            "caveats": list(self.caveats),
            "render": dict(self.render),
        }


# ============================================================
# 小工具
# ============================================================


def _span(stmt: ast.stmt) -> Tuple[int, int]:
    start = int(getattr(stmt, "lineno", 0) or 0)
    end = int(getattr(stmt, "end_lineno", 0) or start)
    return start, end


def _clip(text: str, limit: int = 48) -> str:
    """把代码压成一句可读的摘要（只用于讲解文字，**绝不用来替换摘录**）。"""
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "…"


def _safe_unparse(node: Optional[ast.AST]) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:  # pragma: no cover - 极老的语法节点
        return ""


def _call_name(call: ast.Call) -> str:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _walk_calls(nodes: Sequence[ast.AST]) -> List[ast.Call]:
    """按行号稳定排序地收集调用（确定性：不许依赖 ast.walk 的隐式顺序）。"""
    found: List[ast.Call] = []
    for node in nodes:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                found.append(sub)
    found.sort(key=lambda c: (int(getattr(c, "lineno", 0) or 0), _call_name(c)))
    return found


def _is_docstring_stmt(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(getattr(stmt, "value", None), ast.Constant)
        and isinstance(getattr(stmt.value, "value", None), str)
    )


def _has_return(stmts: Sequence[ast.stmt]) -> Optional[ast.Return]:
    for stmt in stmts:
        if isinstance(stmt, ast.Return):
            return stmt
    return None


def _has_raise(stmts: Sequence[ast.stmt]) -> Optional[ast.Raise]:
    for stmt in stmts:
        if isinstance(stmt, ast.Raise):
            return stmt
        if isinstance(stmt, (ast.If, ast.For, ast.While, ast.Try, ast.With)):
            for sub in ast.walk(stmt):
                if isinstance(sub, ast.Raise):
                    return sub
    return None


def _assign_targets(node: ast.AST) -> List[ast.AST]:
    """取赋值语句的目标节点。

    ``ast.Assign`` 用 ``targets``（列表，支持 ``a = b = 1``），
    ``ast.AugAssign`` / ``ast.AnnAssign`` 用 ``target``（单个）。
    两者混用是真实踩到的坑（AttributeError: 'Assign' object has no attribute 'target'）。
    """
    if isinstance(node, ast.Assign):
        return list(node.targets)
    target = getattr(node, "target", None)
    return [target] if isinstance(target, ast.AST) else []


def _assignment_nodes(nodes: Sequence[ast.AST]) -> List[ast.AST]:
    found: List[ast.AST] = []
    for node in nodes:
        for sub in ast.walk(node):
            if isinstance(sub, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                found.append(sub)
    return found


def _state_write_targets(stmts: Sequence[ast.stmt]) -> List[str]:
    """找出这一段写入的**状态**（``self.x = ...`` / ``obj.attr = ...`` / ``d[k] = ...``）。

    **刻意排除 ``ast.Name`` 目标**：``result = self.string[...]`` 里的 ``result``
    是一个**局部变量绑定**，不是业务状态。第一版把它算成状态写入，
    于是讲稿对着局部变量写出了「这一段会写入状态 `result`」—— 一句假话。
    局部变量由 :func:`_local_bindings` 单独处理，措辞也不同。
    """
    targets: List[str] = []
    for node in _assignment_nodes(stmts):
        for value in _assign_targets(node):
            name = ""
            if isinstance(value, ast.Attribute):
                name = value.attr
            elif isinstance(value, ast.Subscript):
                name = _safe_unparse(value)
            if name and name not in targets:
                targets.append(name)
    targets.sort()
    return targets


def _local_bindings(stmts: Sequence[ast.stmt]) -> List[str]:
    """这一段绑定的**局部变量名**（与状态写入区分开）。"""
    names: List[str] = []
    for node in _assignment_nodes(stmts):
        for target in _assign_targets(node):
            if isinstance(target, ast.Name) and target.id not in names:
                names.append(target.id)
    names.sort()
    return names


def _assigned_names(stmts: Sequence[ast.stmt]) -> List[str]:
    names: List[str] = []
    for node in _assignment_nodes(stmts):
        for target in _assign_targets(node):
            for sub in ast.walk(target):
                if isinstance(sub, ast.Name) and sub.id not in names:
                    names.append(sub.id)
    names.sort()
    return names


def _numeric_comparisons(stmts: Sequence[ast.stmt]) -> List[Tuple[int, str]]:
    """找出带数字字面量的比较（用于 ``parameter_value`` 要点：阈值也是事实）。"""
    out: List[Tuple[int, str]] = []
    for stmt in stmts:
        for node in ast.walk(stmt):
            if not isinstance(node, ast.Compare):
                continue
            for comp in [node.left] + list(node.comparators):
                if isinstance(comp, ast.Constant) and isinstance(comp.value, (int, float)):
                    code = _clip(_safe_unparse(node), 64)
                    line = int(getattr(node, "lineno", 0) or 0)
                    out.append((line, code))
                    break
    out.sort()
    return out


# ============================================================
# 分段的语句遍历
# ============================================================


def _is_control_flow(stmt: ast.stmt) -> bool:
    return isinstance(
        stmt, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith)
    )


def _own_body(func: ast.AST) -> List[ast.stmt]:
    """取函数体，并**穿过最外层的 try**。

    真实项目里函数体常被一个 ``try:`` 整个包住。若把它当成一段，
    整课就只剩一段，分段教学完全失效。所以最外层是单个 ``Try`` 时，
    用它的 ``body`` 继续分段；``Try`` 本身的信息由 ``lead_in`` 交代。
    """
    body: List[ast.stmt] = list(getattr(func, "body", []) or [])
    while body and _is_docstring_stmt(body[0]):
        body = body[1:]
    if len(body) == 1 and isinstance(body[0], ast.Try) and len(body[0].body) > 1:
        return list(body[0].body)
    return body


def _group_statements(body: Sequence[ast.stmt]) -> List[List[ast.stmt]]:
    """按职责把语句聚成组（每个组 = 未来的一个段）。

    规则（与母本的分段判据对齐）：
    1. 连续的"简单语句"（赋值 / 调用 / with）聚成一组；
    2. 每个控制流语句（``if`` / ``for`` / ``while`` / ``try``）**自成一组**
       —— 母本「第 4 段：强制规则直接返回（208-232 行）」就是一个 if 块；
    3. 独立的 ``return`` / ``raise`` 自成一组 —— 母本把每处提前返回单独成段。
    """
    groups: List[List[ast.stmt]] = []
    pending: List[ast.stmt] = []
    for stmt in body:
        if _is_control_flow(stmt) or isinstance(stmt, (ast.Return, ast.Raise)):
            if pending:
                groups.append(pending)
                pending = []
            groups.append([stmt])
        else:
            pending.append(stmt)
    if pending:
        groups.append(pending)
    return groups


def _merge_groups(
    groups: List[List[ast.stmt]], max_lines: int
) -> List[List[ast.stmt]]:
    """把相邻的**都是简单语句**的组并起来，直到接近行数上限。

    这一步是母本「第 1 段：准备工作（175-188 行）」能覆盖 14 行的原因：
    连续几个赋值/取数被当成同一件事讲。控制流组不参与合并
    （合并会让「这一段有个分支」这件事变得说不清）。
    """
    merged: List[List[ast.stmt]] = []
    for group in groups:
        mergeable = bool(merged) and not _is_control_flow(merged[-1][0]) and not _is_control_flow(group[0])
        if mergeable:
            prev_span = _span(merged[-1][0]), _span(merged[-1][-1])
            cur_span = _span(group[0]), _span(group[-1])
            candidate_lines = cur_span[1][1] - prev_span[0][0] + 1
            if candidate_lines <= max_lines:
                merged[-1] = merged[-1] + group
                continue
        merged.append(list(group))
    return merged


def _split_oversized(
    groups: List[List[ast.stmt]], max_lines: int, depth: int = 0
) -> List[List[ast.stmt]]:
    """把过大的组切开，保证每段都能读完。

    两种情况
    --------
    1. **多语句组**：按语句边界切（原有的做法）。
    2. **单个复合语句**（``try`` / ``if`` / ``for`` / ``while`` 包住一大坨）：
       按语句边界切是切不动的（它就一条语句），整段会变成几十行、
       内部的分支完全讲不到。做法是**下沉进它的 body**，
       再把头部语句接到第一小段上 —— 这样 ``group[0]`` 仍然是那个
       ``try``/``if``，段头标题与 ``branch_detail`` 都还在，
       而内容被切成了能读的小段。
       （真实踩到的例子：``python_dotenv`` 的一个 ``try`` 跨 146-178 共 33 行，
       里面还嵌着两个 ``if``，整段成段等于什么都没讲。）
    """
    out: List[List[ast.stmt]] = []
    for group in groups:
        if len(group) == 1:
            stmt = group[0]
            inner = _inner_body(stmt)
            span_start = _span(stmt)[0]
            span_end = _span(stmt)[1]
            if inner and len(inner) > 1 and (span_end - span_start + 1) > max_lines and depth < 3:
                sub = _merge_groups(_group_statements(inner), max_lines)
                sub = _split_oversized(sub, max_lines, depth + 1)
                if sub:
                    # 头部接到第一小段：保住 try/if 的语义与行号起点。
                    #
                    # ⚠️ 必须是**截断副本**，不能直接 `[stmt] + sub[0]`：
                    # `ast.walk(stmt)` 会走遍整个 try 子树（含所有 body 与 handlers），
                    # 于是第一小段的要点会引用到段外的行 —— 讲稿说的行号
                    # 与它展示的摘录对不上，正是本平台要消灭的那类错误。
                    # 截断副本的 body 只留本段语句，walk 自然收在段内。
                    sub[0] = [_truncate_compound(stmt, sub[0])]
                out.extend(sub)
                continue
            out.append(group)
            continue

        start = _span(group[0])[0]
        chunk: List[ast.stmt] = []
        for stmt in group:
            if chunk and _span(stmt)[1] - start + 1 > max_lines:
                out.append(chunk)
                chunk = []
                start = _span(stmt)[0]
            chunk.append(stmt)
        if chunk:
            out.append(chunk)
    return out


def _truncate_compound(stmt: ast.stmt, keep_body: Sequence[ast.stmt]) -> ast.stmt:
    """复合语句的**截断副本**：``body`` 只留 ``keep_body``，分支体一律清空。

    为什么必须是副本而不是原节点
    ----------------------------
    ``ast.walk`` 会走遍传入节点的**整棵子树**。若把原始 ``try`` 节点塞进一个小段，
    ``_walk_calls`` / ``_has_raise`` / ``_state_write_targets`` 都会看到
    ``try`` 后半部分（乃至 ``except``）的语句，于是小段的要点会引用
    **段外**的行号与代码 —— 讲稿说的和它摘的就不是同一段代码了。

    这正是本平台要消灭的那类错误，所以在切分阶段就用副本从结构上杜绝。
    ``end_lineno`` 跟着 ``keep_body`` 的末句走，保证行区间与摘录一致。
    """
    clone = copy.copy(stmt)
    body = list(keep_body)
    clone.body = body
    for attr in ("handlers", "orelse", "finalbody"):
        if hasattr(clone, attr):
            setattr(clone, attr, [])
    if body:
        last = body[-1]
        end = getattr(last, "end_lineno", None) or getattr(last, "lineno", None)
        if end:
            clone.end_lineno = int(end)
        end_col = getattr(last, "end_col_offset", None)
        if end_col is not None:
            clone.end_col_offset = end_col
    return clone


def _inner_body(stmt: ast.stmt) -> List[ast.stmt]:
    """复合语句的 body（用于下沉切分）。``try`` 只取 ``body``，不含 ``except`` 分支。

    只取 ``body`` 是刻意的：``except`` 分支是**另一条路径**，
    把它和主路径塞进同一段会让学生分不清哪句在说哪条路。
    当前版本不单独为 ``except`` 出段 —— 这是已知的覆盖缺口，
    写在 ``lesson.caveats`` 里，不假装讲到了。
    """
    if isinstance(stmt, (ast.Try, ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith)):
        body = list(getattr(stmt, "body", []) or [])
        return [s for s in body if not _is_docstring_stmt(s)]
    return []


# ============================================================
# 标题 / 要点 / 一句话的确定性生成
# ============================================================


def _build_symbol_index(graph: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """``函数名 → 它属于哪个能力点 / 哪个板块``（用于把调用翻译成业务语言）。

    重名时取 ``capability_id`` 最小的那个（确定性），并在值里记 ``ambiguous=True``，
    让讲解能如实说"这个名字在项目里指多个位置"。
    """
    index: Dict[str, Dict[str, str]] = {}
    domains = {
        str(d.get("domain_id") or ""): str(d.get("name_cn") or "")
        for d in (graph.get("domains") or [])
        if isinstance(d, dict)
    }
    for capability in sorted(
        (c for c in (graph.get("capabilities") or []) if isinstance(c, dict)),
        key=lambda c: str(c.get("capability_id") or ""),
    ):
        parent = str(capability.get("parent_id") or "")
        for member in capability.get("members") or []:
            if not isinstance(member, dict):
                continue
            symbol = str(member.get("symbol") or "")
            if not symbol:
                continue
            entry = {
                "capability_id": str(capability.get("capability_id") or ""),
                "capability_name": str(capability.get("name_cn") or ""),
                "name_status": str(capability.get("name_status") or ""),
                "section_id": parent,
                "section_name": domains.get(parent, ""),
                "role": str(member.get("role") or ""),
                "ambiguous": "true" if symbol in index else "false",
            }
            if symbol not in index:
                index[symbol] = entry
    return index


def _usable_title(name: str, name_status: str) -> bool:
    """这个能力名能不能拿去当**教学段标题**？

    不能的情况
    ----------
    - 空名；
    - ``name_status == "unconfirmed"``：引擎自己都没确认这个名字；
    - 名字里带「待归类 / 其他能力 / unclassified」：那是诚实降级的占位名
      （``capabilities.py`` Rule C），拿它当标题会写出
      「第 4 段：其他能力（待归类：advance、has_next、peek）」这种句子 ——
      标题要说"这一段在做什么"，不是"这些函数还没归类"。
    """
    if not name:
        return False
    if str(name_status).strip().lower() == "unconfirmed":
        return False
    return not any(token in name for token in _TITLE_REJECT_TOKENS)


def _title_for_group(
    group: Sequence[ast.stmt],
    symbol_index: Dict[str, Dict[str, str]],
) -> Tuple[str, str, str]:
    """给一组语句起一个**业务动作短语**式标题，并交代它是怎么来的。

    返回 ``(title, title_status, segment_kind)``。

    这是本模块最需要克制的地方：标题很容易变成"系统看懂了业务"的假象。
    所以标题来源只有三种，都如实标注：
    - ``from_capability_name``：命中了图谱里某个**已命名**能力点的中文名；
    - ``from_structure``：纯结构推导（"主动抛出异常"/"取值与准备变量"）。
    """
    raise_stmt = _has_raise(group)
    return_stmt = _has_return(group)
    first = group[0]

    # ---- 1. 分支优先：``if`` 就是分支，不管里面是 return 还是 raise ----
    #     ``if x < 0: raise`` 是**守卫子句**，把它归成"裸 raise"会丢掉"这是个分支"
    #     这个最关键的教学信息，所以分支判定排在 raise 之前。
    if isinstance(first, ast.If):
        condition = _clip(_safe_unparse(first.test), 24)
        if isinstance(first.body[0] if first.body else None, ast.Raise):
            title = f"前置校验不通过就中断（{condition}）" if condition else "前置校验不通过就中断"
        elif _has_return([first]):
            title = f"条件不满足就提前返回（{condition}）" if condition else "条件不满足就提前返回"
        else:
            entry = _first_named_call(group, symbol_index)
            title = entry or (f"条件判断（{condition}）" if condition else "条件判断")
        return title, TITLE_FROM_STRUCTURE if title.startswith(("前置", "条件")) else TITLE_FROM_CAPABILITY, KIND_BRANCH

    # ---- 2. 裸 raise / 裸 return ----
    if isinstance(first, ast.Raise):
        return "主动抛出异常（业务路径中断）", TITLE_FROM_STRUCTURE, KIND_RAISE
    if isinstance(first, ast.Return) and len(group) == 1:
        return "返回结果，函数结束", TITLE_FROM_STRUCTURE, KIND_RETURN

    # ---- 3. 其余：命中**已命名**能力点就用它的中文名 ----
    entry = _first_named_call(group, symbol_index)
    if entry:
        return entry, TITLE_FROM_CAPABILITY, KIND_CALL

    # ---- 4. 纯结构推导 ----
    if isinstance(first, (ast.For, ast.AsyncFor, ast.While)):
        return "循环处理", TITLE_FROM_STRUCTURE, KIND_LOOP
    if isinstance(first, ast.Try):
        return "容错处理（异常被接住）", TITLE_FROM_STRUCTURE, KIND_EXCEPTION
    if isinstance(first, (ast.With, ast.AsyncWith)):
        return "资源打开与释放", TITLE_FROM_STRUCTURE, KIND_PREPARE

    if _state_write_targets(group):
        return "更新状态", TITLE_FROM_STRUCTURE, KIND_STATE_CHANGE
    if _local_bindings(group):
        return "取值与准备变量", TITLE_FROM_STRUCTURE, KIND_PREPARE
    if raise_stmt is not None:
        return "主动抛出异常（业务路径中断）", TITLE_FROM_STRUCTURE, KIND_RAISE
    if return_stmt is not None:
        return "收尾并返回", TITLE_FROM_STRUCTURE, KIND_WRAP_UP
    return "顺序执行", TITLE_FROM_STRUCTURE, KIND_PREPARE


def _first_named_call(
    group: Sequence[ast.stmt], symbol_index: Dict[str, Dict[str, str]]
) -> str:
    """这一段里第一个**名字可用**的能力点中文名（没有就返回空串）。"""
    for call in _walk_calls(group):
        entry = symbol_index.get(_call_name(call))
        if entry and _usable_title(
            str(entry.get("capability_name") or ""), str(entry.get("name_status") or "")
        ):
            return str(entry["capability_name"])
    return ""


def _severity_rank(kind: str) -> int:
    """段种类的重要性排序 —— 用于合并时的标题拼接与「必看」判定。"""
    order = [
        KIND_RETURN, KIND_RAISE, KIND_EXCEPTION, KIND_BRANCH, KIND_STATE_CHANGE,
        KIND_LOOP, KIND_CALL, KIND_WRAP_UP, KIND_CONFIG_DATA, KIND_PREPARE,
    ]
    return order.index(kind) if kind in order else len(order)


def _compose_title(titles: List[str]) -> str:
    """把若干子标题拼成母本那样的复合标题（用 `` + `` 连接，去重保序）。"""
    unique: List[str] = []
    for title in titles:
        if title and title not in unique:
            unique.append(title)
    if not unique:
        return "顺序执行"
    if len(unique) == 1:
        return unique[0]
    return " + ".join(unique[:3])


# ============================================================
# 主入口
# ============================================================


def _annotate_evidence(lesson: "Lesson", graph: Dict[str, Any]) -> "Lesson":
    """给讲稿里**每一条证据**补上 ``evidence_id`` 与（能匹配到时）``fact_id``。

    为什么做成"讲稿生成完之后再统一补"而不是在生成时逐个传参
    --------------------------------------------------------
    证据是在十来个不同的要点分支里构造的（提前返回、符号释义、状态变化、
    参数阈值、变量用途、防御设计、收尾……）。给每个分支都传一份事实索引，
    等于把一个横切关注点抄十遍 —— 正是 README §13.6 第 9 条警告的
    "同一个不变量只允许有一个实现"。统一后处理只写一遍，且无法被漏掉。

    匹配规则
    --------
    用**行区间相交**匹配图谱事实：同一文件，且证据区间与事实区间有重叠。
    重叠时取跨度**最紧**的那条 fact（同分取 ``fact_id`` 升序）——
    宁可挂到更精确的事实上，也不要挂到一条覆盖整个函数的大范围事实上。
    匹配不到 → ``fact_id = ""``（**不编 id**）。

    注意：这里改的是 :class:`EvidenceRef` **实例**（dataclass）。
    写成 ``lesson.to_dict()`` 再改字典，改的是副本，等于没改 —— 这个坑踩过一次。
    """
    facts = [f for f in (graph.get("facts") or []) if isinstance(f, dict)]

    def lookup(file_rel: str, start: int, end: int) -> str:
        best_id = ""
        best_span: Optional[int] = None
        for fact in facts:
            if str(fact.get("file") or "") != file_rel:
                continue
            f_start = int(fact.get("start_line") or 0)
            f_end = int(fact.get("end_line") or f_start)
            if f_start <= 0:
                continue
            if f_start > end or f_end < start:
                continue
            fact_id = str(fact.get("fact_id") or "")
            if not fact_id:
                continue
            span = f_end - f_start
            if best_span is None or span < best_span or (span == best_span and fact_id < best_id):
                best_span = span
                best_id = fact_id
        return best_id

    def annotate(evidence: Sequence[EvidenceRef]) -> None:
        for item in evidence:
            item.evidence_id = _evidence_id(item.file, item.start_line, item.end_line)
            if not item.fact_id:
                item.fact_id = lookup(item.file, item.start_line, item.end_line)

    for segment in lesson.segments:
        for claim in segment.must_remember:
            annotate(claim.evidence)
        for claim in segment.know_enough:
            annotate(claim.evidence)
        if segment.one_sentence_summary is not None:
            annotate(segment.one_sentence_summary.evidence)
    return lesson


def _evidence_id(file_rel: str, start: int, end: int) -> str:
    """证据的稳定 id：``ev_<12 hex>``，由 ``file:start-end`` 派生。

    确定性要求：同一处代码两次生成得到同一个 id，所以**不用随机数、不用序号**
    （序号会随段数变化而漂移，教师挂在上面的审核意见就会错位）。
    """
    digest = _short_digest(f"{file_rel}:{start}-{end}", 12)
    return f"ev_{digest}"


def build_lesson(
    project_id: str,
    capability: Dict[str, Any],
    section: Dict[str, Any],
    graph: Dict[str, Any],
    source_root: str,
    tier: Dict[str, Any],
    lesson_number: int = 1,
) -> Lesson:
    """为一个能力点生成一课沉浸式讲解。

    参数
    ----
    capability:  ``modules.SectionCapability.to_dict()``
    section:     ``modules.Section.to_dict()``（取板块名做上下文）
    source_root: 项目源码根目录（绝对路径，**只用于读文件**，绝不写进契约）
    tier:        ``tiering.plan_for_level(...)``（提供段数/行数上限）
    """
    capability_name = str(capability.get("name_cn") or capability.get("capability_id") or "")
    section_name = str(section.get("name_cn") or "")
    graph = graph if isinstance(graph, dict) else {}
    symbol_index = _build_symbol_index(graph)

    max_segments = int(tier.get("segments_per_lesson_cap") or 20)
    max_lines = int(tier.get("statements_per_segment_cap") or 40)

    lesson = Lesson(
        lesson_id=f"lesson_{capability.get('capability_id')}",
        lesson_number=lesson_number,
        title=f"{capability_name}",
        capability_id=str(capability.get("capability_id") or ""),
        capability_name=capability_name,
        section_id=str(section.get("section_id") or ""),
        section_name=section_name,
        level=str(graph.get("level") or ""),
        source_hash=str(graph.get("source_hash") or ""),
        render=dict(RENDER_TEMPLATES),
    )

    members = [m for m in (capability.get("members") or []) if isinstance(m, dict)]
    members.sort(key=lambda m: (str(m.get("file") or ""), int(m.get("start_line") or 0), str(m.get("symbol") or "")))
    lesson.members_total = len(members)

    segments: List[Segment] = []
    covered: List[Dict[str, Any]] = []
    dropped_members: List[str] = []
    order = 0

    for member in members:
        if order >= max_segments:
            dropped_members.append(str(member.get("symbol") or ""))
            continue
        file_rel = str(member.get("file") or "")
        symbol = str(member.get("symbol") or "")
        if not file_rel or not symbol:
            dropped_members.append(symbol)
            continue
        abs_path = os.path.join(source_root, file_rel.replace("/", os.sep))
        source = ast_cache.get_source(abs_path)
        tree = ast_cache.get_tree(abs_path)
        if not source or tree is None:
            dropped_members.append(symbol)
            continue
        lines = source.splitlines()
        func = _find_function(tree, symbol)
        if func is None:
            dropped_members.append(symbol)
            continue

        groups = _group_statements(_own_body(func))
        groups = _merge_groups(groups, max_lines)
        groups = _split_oversized(groups, max_lines)

        member_span = (
            int(getattr(func, "lineno", 0) or 0),
            int(getattr(func, "end_lineno", 0) or 0),
        )
        member_segments: List[Segment] = []
        member_lead = (
            f"以下这段属于 {file_rel} 的 {symbol}()"
            f"（第 {member_span[0]}-{member_span[1]} 行）"
            if member_span[1]
            else f"以下这段属于 {file_rel} 的 {symbol}()"
        )

        # 先出「函数签名与职责说明」段：docstring 是作者写的职责，可信度最高
        if order < max_segments:
            order += 1
            header_segment = _build_header_segment(
                order=order,
                func=func,
                lines=lines,
                file_rel=file_rel,
                symbol=symbol,
                symbol_kind=_symbol_kind(tree, func),
                member_span=member_span,
                lead_in=member_lead,
            )
            member_segments.append(header_segment)
            segments.append(header_segment)

        for index, group in enumerate(groups):
            if order >= max_segments:
                break
            order += 1
            # 本函数的**第一段正文**也带一次 lead_in（头部段已经带过，
            # 但学生往下翻时仍需要一个"现在在读哪个函数"的锚）
            lead_in = member_lead if index == 0 else ""
            segment = _build_segment(
                project_id=project_id,
                order=order,
                group=group,
                func=func,
                lines=lines,
                file_rel=file_rel,
                symbol=symbol,
                symbol_kind=_symbol_kind(tree, func),
                symbol_index=symbol_index,
                capability_name=capability_name,
                section_name=section_name,
                member_span=member_span,
                lead_in=lead_in,
            )
            member_segments.append(segment)
            segments.append(segment)
        if member_segments:
            covered.append(
                {
                    "symbol": symbol,
                    "file": file_rel,
                    "start_line": int(member.get("start_line") or 0),
                    "end_line": int(member.get("end_line") or 0),
                    "segments": [s.segment_id for s in member_segments],
                    "truncated": order >= max_segments and len(member_segments) < len(groups),
                }
            )

    lesson.segments = segments
    lesson.members_covered = covered
    if dropped_members:
        lesson.truncated = True
        lesson.truncation_reason = (
            f"本级预算最多 {max_segments} 段，本能力点的 "
            f"{len(dropped_members)} 个成员函数未展开：{'、'.join(sorted(set(dropped_members)))}。"
            "未展开不等于没有实现 —— 证据仍可在板块页看到。"
        )

    # ---- 课前两段与课后收尾（对应母本 L1 / L2 / L4 / L5） ----
    lesson.intro = RENDER_TEMPLATES["lesson_open"]
    lesson.one_line_frame = _build_frame(capability_name, section_name, segments)
    lesson.summary_diagram = _build_summary_diagram(segments)
    lesson.lesson_recap = _build_recap(capability_name, section_name, segments)
    lesson.consolidate = RENDER_TEMPLATES["lesson_close"]
    lesson.next_action = "continue_reading"

    # ---- 审核状态：一律 needs_review，且不许自己给自己发通行证 ----
    lesson.review = {
        "status": "needs_review",
        # can_publish 由校验器（verify.py）决定；生成阶段恒为 False
        "can_publish": False,
        "generated_by": GENERATED_BY_RULES,
        "llm_claim_ratio": 0.0,
        "analysis_version": ALGORITHM_VERSION,
        "source_hash": lesson.source_hash,
        "blocking_issues": [
            "尚未通过确定性校验（scripts/verify 或 POST /verify）",
            "尚未经教师确认：段标题、业务含义均为引擎推断",
        ],
    }
    lesson.caveats = [
        "本课由 AST 规则确定性生成（无 LLM、无联网），同一份源码两次生成结果逐字节一致。",
        "段标题有两类来源：命中图谱能力点中文名（from_capability_name，该名本身为 inferred）"
        "或纯结构推导（from_structure）。标题**不是**代码事实，只是讲解顺序的抓手。",
        "分支真假恒为 depends_on_scenario：静态分析看不到输入，不敢替输入下结论。",
        "未通过校验与教师确认前，本课不进入「已确认」状态，界面上一直显示待确认标记。",
        # ↓ 已知覆盖缺口，如实列出（README §13.7 不承诺清单的做法）
        "已知覆盖缺口①：`except` 分支当前不单独成段。源码里的异常处理路径"
        "只有主路径被讲到，错误处理路径需要教师补充或等后续版本。",
        "已知覆盖缺口②：「知道就行」只对**模块级函数**与 `self.方法()` 做跨能力点指引；"
        "形如 `reader.read_regex()` 这类「库对象上的调用」引擎没有接收者类型信息，"
        "不做指引，也不猜它是什么。",
        "已知覆盖缺口③：段内如果出现同名函数，取的是行号最近的那个（确定性优先），"
        "并不保证就是运行时真正被调用的那个。",
    ]
    # 统一给每条证据补 evidence_id 与（能匹配到时）fact_id。
    # 放在返回前而不是生成时：证据在十来个要点分支里分别构造，
    # 逐个传索引等于把一个横切关注点抄十遍。
    _annotate_evidence(lesson, graph)
    return lesson


def _find_function(tree: ast.AST, symbol: str) -> Optional[ast.AST]:
    """按名字找函数/方法（同名时取行号最小的那个，确定性）。"""
    found: List[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol:
            found.append(node)
    if not found:
        return None
    found.sort(key=lambda n: int(getattr(n, "lineno", 0) or 0))
    return found[0]


def _symbol_kind(tree: ast.AST, func: ast.AST) -> str:
    """这个函数是类方法还是模块级函数 —— 靠 AST 父子关系判断，不靠名字猜。"""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for child in ast.walk(node):
                if child is func:
                    return "method"
    return "function"


def _build_segment(
    project_id: str,
    order: int,
    group: Sequence[ast.stmt],
    func: ast.AST,
    lines: List[str],
    file_rel: str,
    symbol: str,
    symbol_kind: str,
    symbol_index: Dict[str, Dict[str, str]],
    capability_name: str,
    section_name: str,
    member_span: Tuple[int, int] = (0, 0),
    lead_in: str = "",
) -> Segment:
    """把一组语句变成一个段（标题 + 摘录 + 证据 + 要点 + 一句话）。"""
    start = _span(group[0])[0]
    end = _span(group[-1])[1]
    excerpt = "\n".join(lines[start - 1 : end])
    title, title_status, kind = _title_for_group(group, symbol_index)

    segment = Segment(
        segment_id=f"seg_{order:03d}",
        order=order,
        title=title,
        title_status=title_status,
        header_text=RENDER_TEMPLATES["header_format"].format(
            order=order, title=title, start=start, end=end
        ),
        segment_kind=kind,
        file=file_rel,
        start_line=start,
        end_line=end,
        symbol=symbol,
        symbol_kind=symbol_kind,
        member_symbol=symbol,
        member_start_line=int(member_span[0]),
        member_end_line=int(member_span[1]),
        lead_in=lead_in,
        code_excerpt=excerpt,
        code_excerpt_hash=_sha256(excerpt),
    )

    # ---- 分支/返回的结构化事实 ----
    first = group[0]
    if isinstance(first, ast.If) or kind == KIND_RETURN:
        segment.branch_detail = _build_branch_detail(first, group, func, int(getattr(func, "end_lineno", 0) or 0))
    if kind == KIND_RETURN or (segment.branch_detail and segment.branch_detail.is_return):
        segment.emphasis_line = "这里是提前返回，非常关键！看到 return 就表示这条业务分支已经结束。"

    # ---- 行内教学注释 ----
    segment.line_annotations = _build_annotations(group, lines, kind, symbol_index)

    # ---- 要点 / 知道就行 / 一句话 ----
    segment.must_remember = _build_bullets(
        project_id, segment, group, func, file_rel, symbol, symbol_index,
        capability_name, section_name, lines,
    )
    segment.know_enough = _build_know_enough(
        project_id, segment, group, file_rel, symbol, symbol_index, capability_name, lines
    )
    segment.one_sentence_summary = _build_summary_claim(
        project_id, segment, kind, capability_name, start, end, file_rel, symbol, lines
    )
    return segment


def _header_span(func: ast.AST) -> Tuple[int, int]:
    """函数「头部」的行范围 = 签名（可能多行）+ docstring。

    没有 docstring 时取到第一条语句的前一行，这样多行签名不会被截断。
    """
    start = int(getattr(func, "lineno", 0) or 0)
    body = list(getattr(func, "body", []) or [])
    if body and _is_docstring_stmt(body[0]):
        end = int(getattr(body[0], "end_lineno", 0) or getattr(body[0], "lineno", start) or start)
    elif body:
        end = int(getattr(body[0], "lineno", start) or start) - 1
        if end < start:
            end = start
    else:
        end = int(getattr(func, "end_lineno", 0) or start)
    return start, end


def _build_header_segment(
    order: int,
    func: ast.AST,
    lines: List[str],
    file_rel: str,
    symbol: str,
    symbol_kind: str,
    member_span: Tuple[int, int],
    lead_in: str,
) -> Segment:
    """函数签名 + docstring 单独成段。

    为什么必须有这一段
    ------------------
    docstring 是**作者亲手写下的职责说明**，是整份讲稿里可信度最高的一句话
    （图谱里 ``objective_confidence = "from_docstring"`` 就是这个道理）。
    第一版把 docstring 直接跳过了，于是讲稿从函数中间开始讲，
    学生看不到"这个函数是干什么的"—— 而参考文档每一课开头都在交代这件事。

    **没有 docstring 时绝不替作者补一句**：如实说明"没有 docstring，
    职责只能从代码结构推断"，并把该段标为结构推导。
    """
    start, end = _header_span(func)
    excerpt = "\n".join(lines[start - 1 : end])
    title = "函数签名与职责说明"
    segment = Segment(
        segment_id=f"seg_{order:03d}",
        order=order,
        title=title,
        title_status=TITLE_FROM_STRUCTURE,
        header_text=RENDER_TEMPLATES["header_format"].format(
            order=order, title=title, start=start, end=end
        ),
        segment_kind=KIND_PREPARE,
        file=file_rel,
        start_line=start,
        end_line=end,
        symbol=symbol,
        symbol_kind=symbol_kind,
        member_symbol=symbol,
        member_start_line=int(member_span[0]),
        member_end_line=int(member_span[1]),
        lead_in=lead_in,
        code_excerpt=excerpt,
        code_excerpt_hash=_sha256(excerpt),
    )
    evidence = _evidence(file_rel, start, end, symbol, lines, "函数签名与 docstring 所在行")
    docstring = (ast.get_docstring(func) or "").strip()
    first_line = docstring.splitlines()[0].strip() if docstring else ""
    if first_line:
        segment.must_remember = [
            Claim(
                claim_id=f"seg_{order:03d}_c1",
                claim_text=(
                    f"作者在这里自己写明了职责：「{_clip(first_line, 60)}」——"
                    "这是**源码原文**（docstring），可信度最高，不是引擎的推断。"
                ),
                category=CATEGORY_SYMBOL_MEANING,
                evidence=[evidence],
                confidence="verified",
            )
        ]
        segment.one_sentence_summary = Claim(
            claim_id=f"seg_{order:03d}_summary",
            claim_text=f"{symbol}() 的职责由作者写在 docstring 里：{_clip(first_line, 50)}",
            category=CATEGORY_SYMBOL_MEANING,
            evidence=[evidence],
            confidence="verified",
        )
    else:
        segment.must_remember = [
            Claim(
                claim_id=f"seg_{order:03d}_c1",
                claim_text=(
                    f"{symbol}() **没有 docstring** —— 它的职责只能从代码结构推断。"
                    "引擎不替作者补一句职责说明，因为那句话没有证据。"
                ),
                category=CATEGORY_SYMBOL_MEANING,
                evidence=[evidence],
                confidence="verified",
            )
        ]
        segment.one_sentence_summary = Claim(
            claim_id=f"seg_{order:03d}_summary",
            claim_text=f"{symbol}() 没有 docstring；本课只讲它的代码结构，不猜它的业务意图。",
            category=CATEGORY_SYMBOL_MEANING,
            evidence=[evidence],
            confidence="verified",
        )
    return segment


def _build_branch_detail(
    first: ast.stmt, group: Sequence[ast.stmt], func: ast.AST, func_end: int
) -> BranchDetail:
    """分支段的核心事实：条件、是否有 return、返回后哪些行不执行、这是函数里第几个 return。"""
    detail = BranchDetail()
    if isinstance(first, ast.If):
        detail.condition_code = _clip(_safe_unparse(first.test), 80)
        detail.condition_line = int(getattr(first, "lineno", 0) or 0)
        detail.taken_path = "条件成立时执行本段"
    else:
        detail.condition_code = ""
        detail.condition_line = int(getattr(first, "lineno", 0) or 0)
        detail.taken_path = "顺序执行到此处"

    return_stmt = _has_return(group)
    raise_stmt = _has_raise(group)

    if return_stmt is not None:
        detail.is_return = True
        detail.is_terminal = True
        detail.return_at_line = int(getattr(return_stmt, "lineno", 0) or 0)
        detail.return_expr = _clip(_safe_unparse(return_stmt.value), 80)
        detail.return_ordinal_in_function = _return_ordinal(func, detail.return_at_line)
    elif raise_stmt is not None:
        detail.raises = True
        detail.is_terminal = True

    # 「后面的代码不会执行」——这句话只在真的提前结束时才说
    if detail.is_terminal:
        seg_end = _span(group[-1])[1]
        if func_end and func_end > seg_end:
            detail.skipped_start_line = seg_end + 1
            detail.skipped_end_line = func_end
    return detail


def _return_ordinal(func: ast.AST, line: int) -> int:
    """这个 return 是函数里的第几个（母本用「第 1 个 return / 最后一个 return」教学）。"""
    returns: List[int] = []
    for node in ast.walk(func):
        if isinstance(node, ast.Return):
            returns.append(int(getattr(node, "lineno", 0) or 0))
    returns.sort()
    try:
        return returns.index(line) + 1
    except ValueError:
        return 0


def _build_annotations(
    group: Sequence[ast.stmt],
    lines: List[str],
    kind: str,
    symbol_index: Dict[str, Dict[str, str]],
) -> List[LineAnnotation]:
    """给关键行加教学注释（母本的教学价值有一半在这上面）。"""
    annotations: List[LineAnnotation] = []

    # 1. return 行 —— 母本原话样式
    for stmt in group:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Return):
                line = int(getattr(node, "lineno", 0) or 0)
                original = _line_has_comment(lines, line)
                annotations.append(
                    LineAnnotation(
                        line=line,
                        text="← 直接返回，函数结束！" if not original else "",
                        role=ROLE_RETURN_MARKER,
                        is_original_comment=bool(original),
                    )
                )
            elif isinstance(node, ast.Raise):
                line = int(getattr(node, "lineno", 0) or 0)
                annotations.append(
                    LineAnnotation(
                        line=line,
                        text="← 抛出异常，这条业务路径在此中断",
                        role=ROLE_WARN,
                    )
                )

    # 2. 命中已知能力点的调用行
    for call in _walk_calls(group):
        name = _call_name(call)
        entry = symbol_index.get(name)
        if not entry:
            continue
        line = int(getattr(call, "lineno", 0) or 0)
        if any(a.line == line for a in annotations):
            continue
        annotations.append(
            LineAnnotation(
                line=line,
                text=f"← 调用「{entry.get('capability_name') or name}」",
                role=ROLE_KEY_CALL,
            )
        )
        if len(annotations) >= MAX_ANNOTATIONS_PER_SEGMENT:
            break

    # 3. 状态写入行
    if len(annotations) < MAX_ANNOTATIONS_PER_SEGMENT:
        for node in _assignment_nodes(group):
            for target in _assign_targets(node):
                if not isinstance(target, (ast.Attribute, ast.Subscript)):
                    continue
                line = int(getattr(node, "lineno", 0) or 0)
                if any(a.line == line for a in annotations):
                    continue
                label = target.attr if isinstance(target, ast.Attribute) else _safe_unparse(target)
                annotations.append(
                    LineAnnotation(
                        line=line,
                        text=f"← 写入状态 {label}",
                        role=ROLE_STATE_CHANGE,
                    )
                )
                break
            if len(annotations) >= MAX_ANNOTATIONS_PER_SEGMENT:
                break

    annotations.sort(key=lambda a: (a.line, a.role))
    return annotations[:MAX_ANNOTATIONS_PER_SEGMENT]


def _line_has_comment(lines: List[str], line: int) -> str:
    if 1 <= line <= len(lines):
        text = lines[line - 1]
        if "#" in text:
            return text.split("#", 1)[1].strip()
    return ""


def _evidence(
    file_rel: str,
    start: int,
    end: int,
    symbol: str,
    lines: Optional[List[str]] = None,
    reason: str = "",
    confidence: str = "verified",
) -> EvidenceRef:
    """构造一条证据。摘录与哈希都从**真实源码行**取，绝不手写。

    ``confidence`` 由调用方指定：``verified``（可由 AST / 行号直接证实）
    或 ``inferred``（推断，例如「这个外部调用不属于本能力点」这类边界判断）。

    **摘录必须非空**：空摘录的证据是"声称有证据"，校验器核不了，
    等于绕过了整个证据链。这一条由校验器的 ``V11`` 强制。
    """
    excerpt = ""
    if lines is not None and start >= 1 and end >= start and end <= len(lines):
        excerpt = "\n".join(lines[start - 1 : end])
    return EvidenceRef(
        file=file_rel,
        start_line=int(start),
        end_line=int(end),
        symbol=symbol,
        excerpt=excerpt,
        excerpt_hash=_sha256(excerpt) if excerpt else "",
        confidence=confidence,
        reason=reason,
    )


def _build_bullets(
    project_id: str,
    segment: Segment,
    group: Sequence[ast.stmt],
    func: ast.AST,
    file_rel: str,
    symbol: str,
    symbol_index: Dict[str, Dict[str, str]],
    capability_name: str,
    section_name: str,
    lines: List[str],
) -> List[Claim]:
    """生成「重点记什么」的要点（**每一条都绑定证据**）。

    生成顺序按教学价值排序（母本的分类学优先级）：
    控制流/提前返回 > 符号释义 > 状态变化 > 变量后续用途 > 参数阈值 > 防御设计 > 收尾
    """
    claims: List[Claim] = []
    counter = [0]

    def add(text: str, category: str, evidence: EvidenceRef, confidence: str = "verified") -> None:
        if len(claims) >= MAX_BULLETS:
            return
        counter[0] += 1
        claims.append(
            Claim(
                claim_id=f"{segment.segment_id}_c{counter[0]}",
                claim_text=text,
                category=category,
                evidence=[evidence],
                confidence=confidence,
            )
        )

    # 1. 提前返回 / 分支终止（母本最高价值的一类）
    detail = segment.branch_detail
    if detail and detail.is_terminal:
        if detail.is_return:
            text = (
                f"看到 `return` 就表示这条业务分支已经结束："
                f"第 {detail.return_at_line} 行一旦执行，函数立即返回，"
            )
            if detail.skipped_start_line:
                text += f"第 {detail.skipped_start_line}-{detail.skipped_end_line} 行一行都不会执行。"
            else:
                text += "它已经是函数的最后一步。"
            if detail.return_ordinal_in_function:
                text += f"这是函数里的第 {detail.return_ordinal_in_function} 个 return。"
        else:
            text = f"这里抛出异常，第 {detail.condition_line} 行的分支一旦命中就不再往下走。"
        add(
            text,
            CATEGORY_RETURN_EARLY_EXIT,
            _evidence(file_rel, detail.return_at_line or detail.condition_line,
                      detail.return_at_line or detail.condition_line, symbol, lines,
                      "return/raise 语句位置"),
        )

    # 2. 分支条件本身（条件是真的还是假的取决于输入 —— 如实说）
    if detail and detail.condition_code:
        add(
            f"分支条件是 `{detail.condition_code}`：它**是真是假取决于输入**，"
            "静态分析看不到运行数据，所以本课不替你判断走哪边，只把两条路都讲清楚。",
            CATEGORY_CONTROL_FLOW,
            _evidence(file_rel, detail.condition_line, detail.condition_line, symbol, lines,
                      "条件表达式所在行"),
        )

    # 3. 符号释义：这一段调用了哪个已知能力点
    seen_calls: List[str] = []
    for call in _walk_calls(group):
        name = _call_name(call)
        if not name or name in seen_calls:
            continue
        entry = symbol_index.get(name)
        if not entry:
            continue
        seen_calls.append(name)
        line = int(getattr(call, "lineno", 0) or 0)
        target_name = entry.get("capability_name") or name
        target_section = entry.get("section_name") or ""
        if _usable_title(target_name, str(entry.get("name_status") or "")):
            note = f"`{name}()` 是「{target_name}」的能力实现"
        else:
            # 「其他能力（待归类：…）」这类占位名不能当成"它是什么"来说 ——
            # 那是引擎的诚实降级产物（capabilities.py Rule C），
            # 直接引用会让学生以为系统认出了业务含义。
            note = (
                f"`{name}()` 在图谱里还没被归到具名能力点"
                f"（引擎暂时把它堆在「{target_name}」里）"
            )
        if target_section and target_section != section_name:
            note += f"（属于板块「{target_section}」）"
        note += " —— 本课会用到它，但它的内部实现不在本课范围。"
        if entry.get("ambiguous") == "true":
            note += "（注意：这个名字在项目里出现在多个位置，这里是按最小 capability_id 取的第一个。）"
        add(
            note,
            CATEGORY_SYMBOL_MEANING,
            _evidence(file_rel, line, line, symbol, lines, "调用点行号"),
        )

    # 4. 状态变化 / 局部变量绑定（两者措辞必须不同，见 _state_write_targets 的注释）
    for write in _state_write_targets(group):
        add(
            f"这一段会写入状态 `{write}` —— 状态变化是业务副作用，"
            "读代码时要专门盯住「谁改了它、谁在后面读它」。",
            CATEGORY_DATA_STRUCTURE,
            _evidence(file_rel, segment.start_line, segment.end_line, symbol, lines,
                      "状态写入所在段"),
        )
        break
    for local in _local_bindings(group):
        add(
            f"`{local}` 是这一段新绑定的**局部变量**（不是对象状态）—— "
            "它出了这个函数就不存在，所以它属于计算过程，不属于业务状态。",
            CATEGORY_DATA_STRUCTURE,
            _evidence(file_rel, segment.start_line, segment.end_line, symbol, lines,
                      "局部变量绑定所在段"),
        )
        break

    # 5. 参数/阈值（数字也是事实，母本会明确写出阈值）
    numeric = _numeric_comparisons(group)
    if numeric:
        line, code = numeric[0]
        add(
            f"这里出现了写死的比较阈值 `{code}` —— 阈值来自代码本身，"
            "不是估算出来的；改代码才会改它。",
            CATEGORY_PARAMETER_VALUE,
            _evidence(file_rel, line, line, symbol, lines, "数字字面量所在行"),
        )

    # 6. 变量后续用途（建立跨段关联）
    reads = _later_reads(func, segment.end_line)
    for name in _assigned_names(group):
        if name in reads:
            add(
                f"变量 `{name}` 在这一段被赋值，后面第 {reads[name]} 行还会用到它 —— "
                "所以不要只看这一段就下结论。",
                CATEGORY_VARIABLE_USAGE,
                _evidence(file_rel, segment.start_line, reads[name], symbol, lines,
                          "赋值段到后续读取行"),
            )
            break

    # 7. 防御设计（**只对 try/except 说"接住"**）—— 见 KIND_RAISE 的注释：
    #    第一版把 raise 也归到这里，于是对 `raise Error(...)` 写出了
    #    「异常被接住而不是往上抛」，是把抛出说成了捕获。
    if any(isinstance(stmt, (ast.Try,)) for stmt in group) and segment.segment_kind == KIND_EXCEPTION:
        add(
            "这是容错/降级设计：异常在这一段被 `except` **接住**，"
            "说明作者选择「这条路失败也要有结果」，而不是让异常冒到调用方。",
            CATEGORY_DEFENSIVE_DESIGN,
            _evidence(file_rel, segment.start_line, segment.end_line, symbol, lines,
                      "try/except 结构所在段"),
        )
    elif segment.segment_kind == KIND_RAISE:
        add(
            "这里是主动 `raise`：与「接住异常」相反，它是**把问题交出去**——"
            "调用方必须处理，否则整个操作失败。读业务时要把它当成一条「此路不通」的出口。",
            CATEGORY_DEFENSIVE_DESIGN,
            _evidence(file_rel, segment.start_line, segment.end_line, symbol, lines,
                      "raise 语句所在段"),
        )

    # 8. 收尾职责
    if segment.segment_kind == KIND_WRAP_UP or (detail and detail.is_return and not detail.skipped_start_line):
        add(
            "这是收尾返回：不管前面走了哪条分支，函数最终都从这里把结果交出去 —— "
            "返回格式统一是这条路径的设计目标。",
            CATEGORY_WRAP_UP_DUTY,
            _evidence(file_rel, segment.start_line, segment.end_line, symbol, lines,
                      "函数末尾的返回语句"),
        )

    if len(claims) < MIN_BULLETS:
        add(
            f"这一段是 `{symbol}` 里的顺序执行代码（第 {segment.start_line}-{segment.end_line} 行），"
            "没有分支、没有状态写入，属于准备或搬运数据；读懂它的输入输出就够了。",
            CATEGORY_DATA_STRUCTURE,
            _evidence(file_rel, segment.start_line, segment.end_line, symbol, lines,
                      "段内语句范围"),
        )
    return claims[:MAX_BULLETS]


def _later_reads(func: ast.AST, after_line: int) -> Dict[str, int]:
    """``变量名 → 之后第一次被读取的行号``（用于「后面还会用到」这条要点）。"""
    reads: Dict[str, int] = {}
    for node in ast.walk(func):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            line = int(getattr(node, "lineno", 0) or 0)
            if line > after_line and node.id not in reads:
                reads[node.id] = line
    return reads


def _build_know_enough(
    project_id: str,
    segment: Segment,
    group: Sequence[ast.stmt],
    file_rel: str,
    symbol: str,
    symbol_index: Dict[str, Dict[str, str]],
    capability_name: str,
    lines: List[str],
) -> List[Claim]:
    """「知道就行」：把不需要深入的外部调用分流出去（母本的高频动作）。

    **证据必须带真实摘录**：第一版这里手搓了一个只有 file/行号、没有摘录的证据，
    于是校验器核不了它（V03/V04 在摘录为空时跳过），
    等于「知道就行」这一整类要点**绕过了证据链**。
    现在统一走 :func:`_evidence`，由 `lines` 取真实源码并算哈希。
    """
    claims: List[Claim] = []
    external: List[str] = []
    for call in _walk_calls(group):
        name = _call_name(call)
        if not name or name in external:
            continue
        if name in symbol_index:
            continue
        func = call.func
        if isinstance(func, ast.Name):
            # Python 内置（len/print/int…）不是业务能力，提它只是噪音。
            if func.id in _PYTHON_BUILTINS:
                continue
        elif isinstance(func, ast.Attribute):
            # 只对 ``self.xxx()`` 说"不用进它的内部"。
            # ``match.groups()`` / ``reader.read_regex()`` 这类"库对象上的调用"
            # 当前不做跨能力点引用 —— 引擎没有接收者类型信息，硬说会变成猜。
            # 这是已知覆盖缺口，写在 lesson.caveats 里，不假装覆盖了。
            if not (isinstance(func.value, ast.Name) and func.value.id == "self"):
                continue
        else:
            continue
        external.append(name)
    external.sort()
    for index, name in enumerate(external[:2]):
        claims.append(
            Claim(
                claim_id=f"{segment.segment_id}_k{index + 1}",
                claim_text=(
                    f"`{name}()` 不在本能力点的成员里 —— 你不用进它的内部，"
                    "只要知道它是被借用的外部能力；要看它自己点开下面的证据跳转。"
                ),
                category=CATEGORY_SYMBOL_MEANING,
                evidence=[
                    _evidence(
                        file_rel,
                        segment.start_line,
                        segment.end_line,
                        symbol,
                        lines,
                        "外部调用点所在段（该函数不属于本能力点，故为推断边界）",
                        "inferred",
                    )
                ],
                confidence="inferred",
            )
        )
    return claims


def _build_summary_claim(
    project_id: str,
    segment: Segment,
    kind: str,
    capability_name: str,
    start: int,
    end: int,
    file_rel: str,
    symbol: str,
    lines: Optional[List[str]] = None,
) -> Claim:
    """「一句话概括」—— 主语是系统、动词是业务动作（母本的句式）。"""
    detail = segment.branch_detail
    is_early_return = bool(detail and detail.is_return and detail.skipped_start_line)
    if is_early_return:
        text = (
            f"命中这个条件就直接返回，这条业务分支到此结束，"
            f"后面第 {detail.skipped_start_line}-{detail.skipped_end_line} 行不再执行。"
        )
    elif detail and detail.is_return:
        # 没有"后面不执行的行" → 它就是函数最后一步，**不许**说成"命中条件"
        # （第一版对末尾 return 写出了"命中这个条件就直接返回"，而那里根本没有条件）
        text = "收尾：把这一段算出来的结果交出去，函数在这里结束。"
    elif detail and detail.raises:
        text = "这里是主动 `raise`：条件不满足就把问题抛出函数，由调用方负责处理。"
    elif kind == KIND_BRANCH:
        text = f"判断 `{_clip(detail.condition_code if detail else '', 32)}` 是否成立，决定接下来走哪条路。"
    elif kind == KIND_RAISE:
        text = "主动抛出异常：这条业务路径到此中断，问题交给调用方处理。"
    elif kind == KIND_EXCEPTION:
        text = "把可能出错的动作包起来，出错就走兜底路径，不让异常冒到调用方。"
    elif kind == KIND_LOOP:
        text = "对一批数据逐个做同样的处理，每一轮的处理逻辑与单条时一致。"
    elif kind == KIND_STATE_CHANGE:
        text = "把这一步算出来的结果写进对象状态，供后面读取。"
    elif kind == KIND_CALL:
        text = f"调用「{segment.title}」完成这一步的业务动作，拿到它的结果继续往下。"
    elif kind == KIND_WRAP_UP:
        text = "收尾：把结果统一交出去，函数在这里结束。"
    else:
        text = "做准备与取数：把后面要用到的值先算好、取好，这一步没有业务判断。"
    return Claim(
        claim_id=f"{segment.segment_id}_summary",
        claim_text=text,
        category=CATEGORY_CONTROL_FLOW,
        evidence=[_evidence(file_rel, start, end, symbol, lines, "本段代码范围")],
        confidence="verified",
    )


def _build_frame(capability_name: str, section_name: str, segments: List[Segment]) -> str:
    """课前定调句（母本 L2）。只陈述结构，不吹业务价值。"""
    kinds: List[str] = []
    for segment in segments:
        if segment.segment_kind not in kinds:
            kinds.append(segment.segment_kind)
    returns = sum(1 for s in segments if s.branch_detail and s.branch_detail.is_return)
    raises = sum(1 for s in segments if s.branch_detail and s.branch_detail.raises)
    parts = [f"「{capability_name}」"]
    if section_name and section_name != capability_name:
        parts.append(f"（属于板块「{section_name}」）")
    frame = "".join(parts) + f" 一共切成 {len(segments)} 段"
    exits: List[str] = []
    if returns:
        exits.append(f"{returns} 处提前返回")
    if raises:
        exits.append(f"{raises} 处守卫中断（raise）")
    if exits:
        frame += "，其中有 " + "、".join(exits) + " —— 这是本课要盯住的第一个重点。"
    else:
        frame += "，全部是顺序执行的步骤，没有提前出口。"
    return RENDER_TEMPLATES["lesson_frame_prefix"] + frame


def _build_summary_diagram(segments: List[Segment]) -> str:
    """课后路径表（母本 L4 的「一张图总结」，这里用等宽表格，保证确定性）。"""
    if not segments:
        return ""
    header = "本课路径（按执行顺序）"
    rows = [
        "| 段 | 内容 | 行号 | 执行后是否结束函数 |",
        "|---|---|---|---|",
    ]
    for segment in segments:
        detail = segment.branch_detail
        if detail and detail.is_return:
            ending = f"是（第 {detail.return_at_line} 行 return）"
        elif detail and detail.raises:
            ending = "是（抛异常中断）"
        else:
            ending = "否"
        rows.append(
            f"| {segment.order} | {segment.title} | {segment.start_line}-{segment.end_line} | {ending} |"
        )
    return header + "\n" + "\n".join(rows)


def _build_recap(
    capability_name: str, section_name: str, segments: List[Segment]
) -> List[str]:
    """课后「你需要记住的 N 个核心要点」（母本 L4 的固定收尾）。"""
    recap: List[str] = []
    returns = [s for s in segments if s.branch_detail and s.branch_detail.is_return]
    raises = [s for s in segments if s.branch_detail and s.branch_detail.raises]
    recap.append(
        f"「{capability_name}」一共 {len(segments)} 段，顺序执行；"
        "看到 `return` 就表示这条业务分支结束了，后面的段不再执行。"
    )
    exits: List[str] = []
    if returns:
        exits.append("、".join(f"第 {s.branch_detail.return_at_line} 行 return" for s in returns[:4]))
    if raises:
        exits.append("、".join(f"第 {s.branch_detail.condition_line} 行 raise" for s in raises[:4]))
    if exits:
        recap.append(
            f"本课有 {len(returns) + len(raises)} 处提前出口（{'；'.join(exits)}）——"
            "条件一旦命中，它后面的段就不会执行。这是理解这段业务的关键节点。"
        )
    else:
        recap.append("本课没有提前出口，所有段都会被走到 —— 这类函数靠的是步骤顺序，不是分支。")
    recap.append(
        "段标题中来自图谱能力点名字的那些是**引擎推断**（inferred），"
        "来自结构推导的（如「提前返回」）是**代码事实**（verified）—— 界面上有标记，别混着信。"
    )
    return recap
