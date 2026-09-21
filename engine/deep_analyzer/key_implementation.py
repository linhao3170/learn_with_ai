"""
Key implementation analyzer.

Identifies the most important implementation details in a project and
extracts structured information about each: design approach, edge cases,
error handling, state mutations, and design patterns.

This powers Layer 3 (recommended implementation approach) analysis
with real code-derived evidence instead of keyword-templated answers.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple

from .project_call_graph import ProjectCallGraph, CallNode
from .state_tracker import StateAnalysis
from .design_pattern_detector import DesignPatternResult


@dataclass
class KeyImplementation:
    """A single key implementation point in the project."""
    node_id: str
    module_name: str
    class_name: Optional[str]
    method_name: str
    filepath: str
    start_line: int
    end_line: int

    # Why it is considered key
    importance_score: float = 0.0
    importance_reasons: List[str] = field(default_factory=list)

    # Implementation analysis
    design_approach: str = ""  # Deprecated: kept for backward compatibility
    design_characteristics: List[Dict[str, str]] = field(default_factory=list)
    edge_cases: List[str] = field(default_factory=list)
    error_handling: List[str] = field(default_factory=list)
    state_writes: List[str] = field(default_factory=list)
    state_reads: List[str] = field(default_factory=list)
    validation_checks: List[str] = field(default_factory=list)
    guard_clauses: List[str] = field(default_factory=list)
    null_checks: List[str] = field(default_factory=list)
    loop_patterns: List[str] = field(default_factory=list)
    recursion_depth: int = 0
    design_pattern: str = ""
    algorithm_type: str = ""  # Deprecated: kept for backward compatibility
    algorithm_hints: Dict[str, str] = field(default_factory=dict)

    # Structural metrics
    complexity: int = 0
    loop_count: int = 0
    branch_count: int = 0
    call_count_internal: int = 0

    # Tags for classification
    categories: List[str] = field(default_factory=list)

    # Evidence lines: precise code locations for each finding
    evidence_refs: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "module": self.module_name,
            "class": self.class_name,
            "method": self.method_name,
            "filepath": self.filepath,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "importance_score": round(self.importance_score, 2),
            "importance_reasons": self.importance_reasons,
            "design_approach": self.design_approach,  # Deprecated, kept for compatibility
            "design_characteristics": self.design_characteristics,
            "edge_cases": self.edge_cases,
            "error_handling": self.error_handling,
            "state_writes": self.state_writes,
            "state_reads": self.state_reads,
            "validation_checks": self.validation_checks,
            "guard_clauses": self.guard_clauses,
            "null_checks": self.null_checks,
            "loop_patterns": self.loop_patterns,
            "recursion_depth": self.recursion_depth,
            "design_pattern": self.design_pattern,
            "algorithm_type": self.algorithm_type,  # Deprecated, kept for compatibility
            "algorithm_hints": self.algorithm_hints,
            "complexity": self.complexity,
            "loop_count": self.loop_count,
            "branch_count": self.branch_count,
            "categories": self.categories,
            "evidence_refs": self.evidence_refs,
        }


@dataclass
class KeyImplementationResult:
    """Collection of all key implementations in a project."""
    implementations: List[KeyImplementation] = field(default_factory=list)

    @property
    def top_implementations(self) -> List[KeyImplementation]:
        return sorted(
            self.implementations,
            key=lambda k: k.importance_score,
            reverse=True,
        )

    def by_category(self, category: str) -> List[KeyImplementation]:
        return [k for k in self.implementations if category in k.categories]

    def to_dict(self) -> dict:
        return {
            "implementations": [k.to_dict() for k in self.top_implementations],
            "total": len(self.implementations),
            "categories": self._list_categories(),
        }

    def _list_categories(self) -> Dict[str, int]:
        cats: Dict[str, int] = {}
        for k in self.implementations:
            for c in k.categories:
                cats[c] = cats.get(c, 0) + 1
        return dict(sorted(cats.items(), key=lambda x: x[1], reverse=True))


class KeyImplementationAnalyzer:
    """
    Analyze code to find and describe key implementation points (Layer 3).

    Combines call graph data (which methods are on critical paths) with
    AST analysis (complexity, validation, error handling, loop patterns)
    and design pattern detection to identify the most important
    implementation details for teaching.
    """

    def __init__(self, call_graph: ProjectCallGraph,
                 state_analysis: Optional[StateAnalysis] = None,
                 design_patterns: Optional[DesignPatternResult] = None):
        self.graph = call_graph
        self.state = state_analysis
        self.patterns = design_patterns
        self.result = KeyImplementationResult()
        self._source_lines: List[str] = []

    def analyze(self, max_results: int = 10) -> KeyImplementationResult:
        """Run the full key implementation analysis."""
        for nid, node in self.graph.nodes.items():
            if node.kind != "method":
                continue
            if node.name.startswith("__") and node.name != "__init__":
                continue
            if node.name == "__init__":
                continue

            ki = self._analyze_method(node)
            if ki and ki.importance_score > 0:
                self.result.implementations.append(ki)

        self.result.implementations = self.result.top_implementations[:max_results]
        return self.result

    def _analyze_method(self, node: CallNode) -> Optional[KeyImplementation]:
        """Analyze a single method for key implementation characteristics."""
        ki = KeyImplementation(
            node_id=node.node_id,
            module_name=node.module_name,
            class_name=node.class_name,
            method_name=node.name,
            filepath=node.filepath,
            start_line=node.start_line,
            end_line=node.end_line,
        )

        try:
            with open(node.filepath, "r", encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)
            self._source_lines = source.splitlines()
        except (SyntaxError, UnicodeDecodeError):
            self._source_lines = []
            return None

        method_ast = self._find_method_ast(tree, node.class_name, node.name)
        if not method_ast:
            return None

        self._analyze_structure(method_ast, ki)
        self._analyze_error_handling(method_ast, ki)
        self._analyze_validation(method_ast, ki)
        self._analyze_guard_clauses(method_ast, ki)
        self._analyze_null_checks(method_ast, ki)
        self._analyze_loop_patterns(method_ast, ki)
        self._analyze_recursion(method_ast, node, ki)
        self._analyze_state(node, ki)
        ki.design_pattern = self._match_design_pattern(node, ki)
        ki.algorithm_hints = self._infer_algorithm_hints(node, ki)
        ki.algorithm_type = ki.algorithm_hints.get("detected", "")  # Backward compatibility
        ki.design_characteristics = self._extract_design_characteristics(node, ki)
        ki.design_approach = "; ".join([c["label"] for c in ki.design_characteristics])  # Backward compatibility
        self._score_importance(node, ki)
        ki.categories = self._classify(node, ki)

        return ki

    def _find_method_ast(self, tree: ast.AST, class_name: Optional[str],
                         method_name: str) -> Optional[ast.AST]:
        """Find the AST node for a specific method."""
        if class_name:
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    for item in node.body:
                        if (isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                                and item.name == method_name):
                            return item
            return None
        else:
            for node in ast.iter_child_nodes(tree):
                if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and node.name == method_name):
                    return node
            return None

    def _analyze_structure(self, func_ast: ast.AST, ki: KeyImplementation):
        """Analyze structural complexity: loops, branches, try blocks."""
        loops = 0
        branches = 0

        for node in ast.walk(func_ast):
            if isinstance(node, (ast.For, ast.While, ast.AsyncFor)):
                loops += 1
            if isinstance(node, ast.If):
                branches += 1
            if isinstance(node, ast.Try):
                branches += 2
            if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                loops += 1

        ki.loop_count = loops
        ki.branch_count = branches
        ki.complexity = branches + loops + 1
        ki.call_count_internal = len([
            c for c in ast.walk(func_ast) if isinstance(c, ast.Call)
        ])

    def _analyze_error_handling(self, func_ast: ast.AST, ki: KeyImplementation):
        """Analyze exceptions raised, caught, and edge case handling."""
        errors = []
        edge_cases = []

        for node in ast.walk(func_ast):
            if isinstance(node, ast.Raise):
                exc_name = self._get_exception_name(node.exc)
                exc_msg = self._get_exception_msg(node.exc)
                if exc_name:
                    desc = f"{exc_name}: {exc_msg}" if exc_msg else exc_name
                    errors.append(desc)
                    ki.evidence_refs.append({
                        "type": "error_handling",
                        "description": desc,
                        "line": node.lineno,
                    })

            if isinstance(node, ast.Try):
                caught_types = []
                for handler in node.handlers:
                    if handler.type:
                        if isinstance(handler.type, ast.Name):
                            caught_types.append(handler.type.id)
                        elif isinstance(handler.type, ast.Attribute):
                            caught_types.append(handler.type.attr)
                        elif isinstance(handler.type, ast.Tuple):
                            for elt in handler.type.elts:
                                if isinstance(elt, ast.Name):
                                    caught_types.append(elt.id)
                if caught_types:
                    desc = "Catches " + ", ".join(caught_types) + " exception(s)"
                    edge_cases.append(desc)
                else:
                    desc = "bare except (catches all exceptions)"
                    edge_cases.append(desc)
                ki.evidence_refs.append({
                    "type": "exception_catch",
                    "description": desc,
                    "line": node.lineno,
                })

        ki.error_handling = list(dict.fromkeys(errors))[:8]
        if edge_cases:
            ki.edge_cases = list(dict.fromkeys(ki.edge_cases + edge_cases))

    def _get_exception_name(self, exc_node) -> str:
        if not exc_node:
            return ""
        if isinstance(exc_node, ast.Call):
            if isinstance(exc_node.func, ast.Name):
                return exc_node.func.id
            if isinstance(exc_node.func, ast.Attribute):
                return exc_node.func.attr
        if isinstance(exc_node, ast.Name):
            return exc_node.id
        return ""

    def _get_exception_msg(self, exc_node) -> str:
        if not exc_node or not isinstance(exc_node, ast.Call):
            return ""
        if exc_node.args and isinstance(exc_node.args[0], ast.Constant):
            val = exc_node.args[0].value
            if isinstance(val, str):
                if len(val) > 60:
                    val = val[:57] + "..."
                return val
        return ""

    def _analyze_validation(self, func_ast: ast.AST, ki: KeyImplementation):
        """Identify validation checks in the method body."""
        checks = []
        for node in ast.walk(func_ast):
            if isinstance(node, ast.If):
                check_desc = self._describe_if_condition(node.test)
                if check_desc and self._is_validation_check(node):
                    checks.append(check_desc)
        ki.validation_checks = checks[:8]

    def _describe_if_condition(self, test_node) -> str:
        """Try to describe what an if condition is checking."""
        if isinstance(test_node, ast.Compare):
            left = self._ast_to_str(test_node.left)
            op_map = {
                ast.Eq: "==", ast.NotEq: "!=",
                ast.Lt: "<", ast.LtE: "<=",
                ast.Gt: ">", ast.GtE: ">=",
                ast.In: "in", ast.NotIn: "not in",
                ast.Is: "is", ast.IsNot: "is not",
            }
            parts = [left]
            for i, op in enumerate(test_node.ops):
                op_str = op_map.get(type(op), "?")
                right = self._ast_to_str(test_node.comparators[i]) if i < len(test_node.comparators) else "?"
                parts.append(f"{op_str} {right}")
            return " ".join(parts)

        if isinstance(test_node, ast.BoolOp):
            op_name = "and" if isinstance(test_node.op, ast.And) else "or"
            values = [self._ast_to_str(v) for v in test_node.values]
            return f" {op_name} ".join(values)

        if isinstance(test_node, ast.UnaryOp) and isinstance(test_node.op, ast.Not):
            return f"not {self._ast_to_str(test_node.operand)}"

        if isinstance(test_node, ast.Call):
            return self._ast_to_str(test_node)

        return self._ast_to_str(test_node)

    def _is_validation_check(self, if_node: ast.If) -> bool:
        for stmt in if_node.body:
            if isinstance(stmt, ast.Raise):
                return True
            if isinstance(stmt, ast.Return):
                return True
        return False

    def _analyze_guard_clauses(self, func_ast: ast.AST, ki: KeyImplementation):
        """Detect guard clause patterns: early returns / raises before main logic."""
        guards = []
        if not hasattr(func_ast, "body"):
            return
        for stmt in func_ast.body:
            if isinstance(stmt, ast.If):
                has_early_exit = any(
                    isinstance(s, (ast.Return, ast.Raise))
                    for s in stmt.body
                )
                if has_early_exit:
                    condition_desc = self._describe_if_condition(stmt.test) or "condition check"
                    exit_type = "early return" if any(isinstance(s, ast.Return) for s in stmt.body) else "raise"
                    guard_desc = f"{condition_desc} -> {exit_type}"
                    guards.append(guard_desc)
                    ki.evidence_refs.append({
                        "type": "guard_clause",
                        "description": guard_desc,
                        "line": stmt.lineno,
                    })
        ki.guard_clauses = guards[:8]
        if guards:
            ki.edge_cases = list(dict.fromkeys(ki.edge_cases + guards))

    def _analyze_null_checks(self, func_ast: ast.AST, ki: KeyImplementation):
        """Detect None / empty / existence checks."""
        null_checks = []
        for node in ast.walk(func_ast):
            if isinstance(node, ast.If):
                check_desc = self._describe_if_condition(node.test)
                if not check_desc:
                    continue
                check_lower = check_desc.lower()
                is_null_check = (
                    "none" in check_lower
                    or " is " in check_lower
                    or "not in" in check_lower
                )
                if is_null_check:
                    null_checks.append(check_desc)
        ki.null_checks = list(dict.fromkeys(null_checks))[:8]

    def _analyze_loop_patterns(self, func_ast: ast.AST, ki: KeyImplementation):
        """Identify iteration patterns."""
        patterns = []
        for node in ast.walk(func_ast):
            if isinstance(node, (ast.For, ast.While)):
                pattern = self._classify_loop(node)
                if pattern:
                    patterns.append(pattern)
        ki.loop_patterns = list(dict.fromkeys(patterns))[:5]

    def _classify_loop(self, loop_node: ast.AST) -> str:
        has_append = False
        has_break = False
        has_search_cond = False
        has_accumulator = False

        for node in ast.walk(loop_node):
            if isinstance(node, ast.Break):
                has_break = True
            if isinstance(node, ast.If):
                has_search_cond = True
            if isinstance(node, ast.AugAssign):
                if isinstance(node.target, ast.Name):
                    has_accumulator = True
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr in ("append", "add", "extend"):
                    has_append = True

        if has_break and has_search_cond:
            return "search traversal (early exit on match)"
        if has_accumulator:
            return "accumulation / aggregation"
        if has_append:
            return "collection / transformation"
        if isinstance(loop_node, ast.For):
            return "sequential traversal"
        if isinstance(loop_node, ast.While):
            return "conditional loop"
        return "loop"

    def _analyze_recursion(self, func_ast: ast.AST, node: CallNode, ki: KeyImplementation):
        """Detect if a method calls itself (direct recursion)."""
        method_name = node.name
        call_count = 0
        for n in ast.walk(func_ast):
            if isinstance(n, ast.Call):
                if isinstance(n.func, ast.Attribute):
                    if n.func.attr == method_name:
                        if isinstance(n.func.value, ast.Name) and n.func.value.id == "self":
                            call_count += 1
                elif isinstance(n.func, ast.Name) and n.func.id == method_name:
                    call_count += 1
        if call_count > 0:
            ki.recursion_depth = call_count
            ki.evidence_refs.append({
                "type": "recursion",
                "description": f"recursive call(s): {call_count}",
                "line": func_ast.lineno if hasattr(func_ast, "lineno") else 0,
            })

    def _ast_to_str(self, node) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = self._ast_to_str(node.value)
            return f"{base}.{node.attr}"
        if isinstance(node, ast.Subscript):
            base = self._ast_to_str(node.value)
            return f"{base}[...]"
        if isinstance(node, ast.Constant):
            val = node.value
            if isinstance(val, str):
                return f"'{val[:20]}'"
            return str(val)
        if isinstance(node, ast.Call):
            return self._ast_to_str(node.func) + "()"
        return "..."

    def _analyze_state(self, node: CallNode, ki: KeyImplementation):
        if not self.state or not node.class_name:
            return
        cs = self.state.get_class_state(node.module_name, node.class_name)
        if not cs:
            return
        ki.state_writes = cs.method_writes.get(node.name, [])
        ki.state_reads = cs.method_reads.get(node.name, [])
        dict_writes = cs.method_dict_writes.get(node.name, [])
        if dict_writes:
            ki.state_writes = list(set(ki.state_writes + dict_writes))

    def _extract_design_characteristics(self, node: CallNode, ki: KeyImplementation) -> List[Dict[str, str]]:
        """Extract design characteristics as evidence-backed facts, not inferences."""
        characteristics = []

        # Guard clauses (verified from AST)
        if len(ki.guard_clauses) >= 3:
            guard_lines = [ref["line"] for ref in ki.evidence_refs if ref["type"] == "guard_clause"]
            characteristics.append({
                "category": "guard_clause",
                "label": f"guard-clause style ({len(ki.guard_clauses)} pre-checks)",
                "evidence": f"lines {', '.join(map(str, guard_lines[:3]))}" if guard_lines else "detected",
                "confidence": "verified"
            })
        elif ki.guard_clauses:
            guard_lines = [ref["line"] for ref in ki.evidence_refs if ref["type"] == "guard_clause"]
            characteristics.append({
                "category": "guard_clause",
                "label": f"{len(ki.guard_clauses)} pre-flight validations",
                "evidence": f"lines {', '.join(map(str, guard_lines))}" if guard_lines else "detected",
                "confidence": "verified"
            })

        # Error handling (verified from AST)
        if ki.error_handling:
            error_lines = [ref["line"] for ref in ki.evidence_refs if ref["type"] == "error_handling"]
            exc_types = list(set([e.split(":")[0] for e in ki.error_handling]))
            characteristics.append({
                "category": "error_handling",
                "label": f"raises {len(exc_types)} exception type(s): {', '.join(exc_types[:3])}",
                "evidence": f"lines {', '.join(map(str, error_lines[:3]))}" if error_lines else "detected",
                "confidence": "verified"
            })

        # State mutation (verified from state tracker)
        if ki.state_writes:
            characteristics.append({
                "category": "state_mutation",
                "label": f"modifies {len(ki.state_writes)} state attribute(s): {', '.join(ki.state_writes[:3])}",
                "evidence": "from state tracker",
                "confidence": "verified"
            })

        # Loop patterns (verified from AST)
        if ki.loop_patterns:
            for lp in set(ki.loop_patterns[:2]):
                characteristics.append({
                    "category": "algorithmic",
                    "label": lp,
                    "evidence": f"{ki.loop_count} loop(s) detected",
                    "confidence": "verified"
                })

        # Recursion (verified from AST)
        if ki.recursion_depth > 0:
            rec_lines = [ref["line"] for ref in ki.evidence_refs if ref["type"] == "recursion"]
            characteristics.append({
                "category": "recursion",
                "label": "recursive implementation",
                "evidence": f"{ki.recursion_depth} recursive call(s)" + (f" at line {rec_lines[0]}" if rec_lines else ""),
                "confidence": "verified"
            })

        # Multi-step orchestration (structural metric)
        if ki.call_count_internal >= 5:
            characteristics.append({
                "category": "orchestration",
                "label": f"multi-step orchestration ({ki.call_count_internal} internal calls)",
                "evidence": "from call count",
                "confidence": "verified"
            })

        # Design pattern (from detector, needs confirmation)
        if ki.design_pattern:
            characteristics.append({
                "category": "design_pattern",
                "label": f"uses {ki.design_pattern}",
                "evidence": "from pattern detector",
                "confidence": "inferred"
            })

        if not characteristics:
            characteristics.append({
                "category": "general",
                "label": "general business logic",
                "evidence": "no distinctive structural features",
                "confidence": "verified"
            })

        return characteristics

    def _match_design_pattern(self, node: CallNode, ki: KeyImplementation) -> str:
        if not self.patterns:
            return ""
        class_name = node.class_name
        if not class_name:
            return ""
        for p in self.patterns.patterns:
            if p.target_type == "class" and p.target_name == class_name:
                return p.pattern_name
        return ""

    def _infer_algorithm_hints(self, node: CallNode, ki: KeyImplementation) -> Dict[str, str]:
        """Infer algorithm type with confidence level and reasoning."""
        name_lower = node.name.lower()
        detected = ""
        reason_parts = []

        # High confidence: structural evidence
        if ki.recursion_depth > 0:
            detected = "recursion"
            reason_parts.append(f"{ki.recursion_depth} recursive call(s)")
            confidence = "verified"
        elif ki.loop_count >= 2 and len(ki.state_writes) >= 2:
            detected = "state machine transition"
            reason_parts.append(f"{ki.loop_count} loops + {len(ki.state_writes)} state writes")
            confidence = "verified"
        elif ki.loop_count > 0 and not ki.state_writes:
            detected = "pure computation / statistics"
            reason_parts.append(f"{ki.loop_count} loop(s), no state mutation")
            confidence = "verified"
        elif ki.guard_clauses and not ki.loop_count:
            detected = "conditional checks (no loops)"
            reason_parts.append(f"{len(ki.guard_clauses)} guard clauses, no loops")
            confidence = "verified"
        # Medium confidence: name + structure
        elif any(w in name_lower for w in ("search", "find", "lookup", "query")):
            if ki.loop_count > 0:
                detected = "search / lookup"
                reason_parts.append(f"method name contains '{[w for w in ['search', 'find', 'lookup', 'query'] if w in name_lower][0]}' + has loop")
                confidence = "inferred"
            else:
                detected = "direct lookup"
                reason_parts.append("method name + no loops")
                confidence = "inferred"
        elif "conflict" in name_lower or "overlap" in name_lower:
            detected = "interval overlap detection"
            reason_parts.append("method name contains 'conflict' or 'overlap'")
            if ki.loop_count > 0:
                reason_parts.append("+ has loop")
            confidence = "inferred"
        elif any(w in name_lower for w in ("validate", "check", "verify")):
            detected = "rule validation"
            reason_parts.append(f"method name contains '{[w for w in ['validate', 'check', 'verify'] if w in name_lower][0]}'")
            confidence = "inferred"
        elif any(w in name_lower for w in ("sort", "order", "rank")):
            detected = "sorting"
            reason_parts.append("method name suggests sorting")
            confidence = "inferred"
        else:
            detected = "general business logic"
            reason_parts.append("no distinctive algorithmic pattern")
            confidence = "verified"

        return {
            "detected": detected,
            "confidence": confidence,
            "reason": "; ".join(reason_parts) if reason_parts else "from structural analysis"
        }

    def _score_importance(self, node: CallNode, ki: KeyImplementation):
        """Score how important this implementation is for teaching."""
        score = 0.0
        reasons = []

        if ki.complexity >= 5:
            score += 3.0
            reasons.append("high complexity implementation")
        elif ki.complexity >= 3:
            score += 2.0
            reasons.append("medium complexity")

        if len(ki.validation_checks) >= 3:
            score += 2.0
            reasons.append("multiple boundary validations")
        elif len(ki.validation_checks) >= 1:
            score += 1.0
            reasons.append("includes boundary validation")

        if len(ki.error_handling) >= 3:
            score += 1.5
            reasons.append("comprehensive error handling")
        elif len(ki.error_handling) >= 1:
            score += 0.5
            reasons.append("includes exception raises")

        if len(ki.state_writes) >= 3:
            score += 2.0
            reasons.append("modifies multiple state attributes")
        elif len(ki.state_writes) >= 1:
            score += 1.0
            reasons.append("has state mutation")

        in_degree = len(node.called_by)
        if in_degree >= 3:
            score += 2.0
            reasons.append("core method called by many")
        elif in_degree >= 1:
            score += 0.5

        out_degree = len(node.calls) if hasattr(node, "calls") else 0
        if out_degree >= 4:
            score += 1.5
            reasons.append("orchestrates multiple sub-steps")
        elif out_degree >= 2:
            score += 0.5

        if node.docstring and len(node.docstring) > 50:
            score += 0.5

        if not node.name.startswith("_"):
            score += 0.5
        else:
            if ki.complexity >= 5:
                score += 0.5
                reasons.append("core private implementation (high complexity)")
            else:
                score -= 0.5

        if ki.loop_count >= 2:
            score += 1.0
            reasons.append("contains core algorithmic logic")
        elif ki.loop_count >= 1:
            score += 0.5

        if ki.design_pattern:
            score += 1.0
            reasons.append(f"demonstrates {ki.design_pattern}")

        if len(ki.edge_cases) >= 3:
            score += 1.0
            reasons.append("well-considered edge cases")
        elif len(ki.edge_cases) >= 1:
            score += 0.5

        if ki.recursion_depth > 0:
            score += 1.0
            reasons.append("recursive implementation (key teaching point)")

        ki.importance_score = score
        ki.importance_reasons = reasons

    def _classify(self, node: CallNode, ki: KeyImplementation) -> List[str]:
        cats = []
        name_lower = node.name.lower()

        if ki.validation_checks or "check" in name_lower or "validate" in name_lower:
            cats.append("validation")
        if ki.state_writes:
            cats.append("state_mutation")
        if ki.loop_count > 0:
            cats.append("algorithmic")
        if ki.error_handling:
            cats.append("error_handling")
        if ki.guard_clauses:
            cats.append("guard_clause")
        if ki.recursion_depth > 0:
            cats.append("recursion")
        if "conflict" in name_lower:
            cats.append("conflict_detection")
        if any(w in name_lower for w in ("create", "add", "register")):
            cats.append("creation")
        if any(w in name_lower for w in ("approve", "reject", "cancel", "close")):
            cats.append("state_transition")
        if ki.design_pattern:
            cats.append("design_pattern")

        if not cats:
            cats.append("general")

        return cats
