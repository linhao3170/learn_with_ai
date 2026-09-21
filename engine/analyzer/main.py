"""
业务逻辑分析引擎主入口

整合解析层、模式识别、调用图、知识点提取，
输出完整的业务逻辑分析结果。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

from ..parser.python_parser import PythonParser, ParsedResult
from .pattern_detector import PatternDetector, PatternMatch
from .call_graph import CallGraph, build_call_graph
from .knowledge_extractor import KnowledgeExtractor, KnowledgePoint


@dataclass
class ModuleOverview:
    """模块概览"""
    name: str = ""
    description: str = ""
    primary_purpose: str = ""  # 主要用途
    complexity_level: str = "beginner"  # beginner / intermediate / advanced
    total_functions: int = 0
    total_classes: int = 0
    total_lines: int = 0
    key_patterns: List[str] = field(default_factory=list)


@dataclass
class MainFlowStep:
    """主流程步骤"""
    step: int
    description: str
    related_function: str = ""
    line_start: int = 0
    line_end: int = 0


@dataclass
class AnalysisResult:
    """完整的业务逻辑分析结果"""

    # 概览
    overview: ModuleOverview = field(default_factory=ModuleOverview)

    # 结构信息
    classes: List[Dict[str, Any]] = field(default_factory=list)
    functions: List[Dict[str, Any]] = field(default_factory=list)
    imports: List[Dict[str, Any]] = field(default_factory=list)

    # 业务模式
    patterns: List[Dict[str, Any]] = field(default_factory=list)
    pattern_summary: Dict[str, int] = field(default_factory=dict)  # pattern_id -> count

    # 调用图
    call_graph: Dict[str, Any] = field(default_factory=dict)

    # 主流程（关键函数执行顺序的逻辑梳理）
    main_flow: List[MainFlowStep] = field(default_factory=list)

    # 知识点
    knowledge_points: List[Dict[str, Any]] = field(default_factory=list)
    knowledge_categories: Dict[str, int] = field(default_factory=dict)

    # 难度评估
    difficulty_score: float = 0.0  # 1-5

    def to_dict(self) -> Dict[str, Any]:
        """转为可 JSON 序列化的字典"""
        d = {
            "overview": asdict(self.overview),
            "classes": self.classes,
            "functions": self.functions,
            "imports": self.imports,
            "patterns": self.patterns,
            "pattern_summary": self.pattern_summary,
            "call_graph": self.call_graph,
            "main_flow": [asdict(s) for s in self.main_flow],
            "knowledge_points": self.knowledge_points,
            "knowledge_categories": self.knowledge_categories,
            "difficulty_score": round(self.difficulty_score, 1),
        }
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


class BusinessLogicAnalyzer:
    """
    业务逻辑分析器

    输入：Python 源码
    输出：完整的业务逻辑分析结果（结构化 JSON）
    """

    def __init__(self):
        self.parser = PythonParser()
        self.pattern_detector = PatternDetector()
        self.knowledge_extractor = KnowledgeExtractor()

    def analyze(self, source_code: str, module_name: str = "main") -> AnalysisResult:
        """
        分析 Python 源码的业务逻辑

        Args:
            source_code: Python 源码字符串
            module_name: 模块名（用于显示）

        Returns:
            AnalysisResult 完整分析结果
        """
        # 步骤 1：解析 AST
        parsed = self.parser.parse(source_code)

        # 步骤 2：业务模式识别
        patterns = self.pattern_detector.detect(parsed)

        # 步骤 3：调用图
        call_graph = build_call_graph(parsed)

        # 步骤 4：知识点提取
        knowledge = self.knowledge_extractor.extract(parsed, patterns)

        # 步骤 5：组装结果
        result = AnalysisResult()

        # --- 结构信息 ---
        result.imports = [
            {
                "module": imp.module,
                "names": imp.names,
                "line": imp.line,
                "is_from": imp.is_from,
            }
            for imp in parsed.imports
        ]

        result.classes = [
            {
                "name": cls.name,
                "start_line": cls.start_line,
                "end_line": cls.end_line,
                "docstring": cls.docstring,
                "bases": cls.bases,
                "methods": [
                    {
                        "name": m.name,
                        "start_line": m.start_line,
                        "end_line": m.end_line,
                        "docstring": m.docstring,
                        "parameters": m.parameters,
                        "is_async": m.is_async,
                        "if_count": m.if_count,
                        "loop_count": m.loop_count,
                        "try_count": m.try_count,
                        "raise_count": m.raise_count,
                        "call_count": m.call_count,
                    }
                    for m in cls.methods
                ],
            }
            for cls in parsed.classes
        ]

        result.functions = [
            {
                "name": f.name,
                "start_line": f.start_line,
                "end_line": f.end_line,
                "docstring": f.docstring,
                "parameters": f.parameters,
                "is_method": f.is_method,
                "is_async": f.is_async,
                "if_count": f.if_count,
                "loop_count": f.loop_count,
                "try_count": f.try_count,
                "raise_count": f.raise_count,
                "call_count": f.call_count,
                "called_functions": f.called_functions,
            }
            for f in parsed.functions
        ]

        # --- 业务模式 ---
        result.patterns = [
            {
                "pattern_id": p.pattern_id,
                "pattern_name": p.pattern_name,
                "category": p.category,
                "confidence": p.confidence,
                "score": round(p.score, 2),
                "target_type": p.target_type,
                "target_name": p.target_name,
                "target_line": p.target_line,
                "sub_type": p.sub_type,
                "description": p.description,
                "evidence": [
                    {
                        "description": e.description,
                        "line_start": e.line_start,
                        "line_end": e.line_end,
                        "evidence_type": e.evidence_type,
                    }
                    for e in p.evidence
                ],
            }
            for p in patterns
        ]

        for p in patterns:
            result.pattern_summary[p.pattern_id] = (
                result.pattern_summary.get(p.pattern_id, 0) + 1
            )

        # --- 调用图 ---
        result.call_graph = call_graph.to_dict()

        # --- 主流程推导 ---
        result.main_flow = self._derive_main_flow(parsed, patterns, call_graph)

        # --- 知识点 ---
        result.knowledge_points = [
            {
                "id": kp.id,
                "name": kp.name,
                "category": kp.category,
                "difficulty": kp.difficulty,
                "description": kp.description,
                "related_lines": kp.related_lines,
                "related_functions": kp.related_functions,
            }
            for kp in knowledge
        ]

        for kp in knowledge:
            result.knowledge_categories[kp.category] = (
                result.knowledge_categories.get(kp.category, 0) + 1
            )

        # --- 概览 ---
        all_funcs = parsed.get_all_functions()
        total_lines = len(parsed.source_lines)

        # 主要用途：从模式中推断
        primary_patterns = [p for p in patterns if p.score >= 0.6]
        if primary_patterns:
            primary_purpose = primary_patterns[0].pattern_name
        else:
            primary_purpose = "通用 Python 代码"

        # 难度评估
        difficulty = self._calculate_difficulty(parsed, patterns, knowledge)
        result.difficulty_score = difficulty

        level_map = {1: "beginner", 2: "beginner", 3: "intermediate", 4: "advanced", 5: "advanced"}

        result.overview = ModuleOverview(
            name=module_name,
            description=parsed.module_docstring or "",
            primary_purpose=primary_purpose,
            complexity_level=level_map.get(round(difficulty), "intermediate"),
            total_functions=len(all_funcs),
            total_classes=len(parsed.classes),
            total_lines=total_lines,
            key_patterns=list({p.pattern_name for p in patterns if p.score >= 0.5}),
        )

        return result

    def _derive_main_flow(
        self,
        parsed: ParsedResult,
        patterns: List[PatternMatch],
        call_graph: CallGraph,
    ) -> List[MainFlowStep]:
        """
        推导主流程步骤

        策略：从入口函数出发，按 CRUD 逻辑顺序或调用顺序排列核心函数
        """
        steps = []
        all_funcs = parsed.get_all_functions()

        # 策略 1：CRUD 顺序（C -> R -> U -> D）
        crud_order = {"C": 1, "R": 2, "U": 3, "D": 4}
        crud_funcs = []
        for p in patterns:
            if p.pattern_id == "crud" and p.target_type == "function" and p.sub_type:
                sub = p.sub_type
                if sub in crud_order:
                    crud_funcs.append(
                        (crud_order[sub], p.target_name, p.target_line, f"实现 {sub} 操作：{p.target_name}")
                    )

        if crud_funcs:
            crud_funcs.sort(key=lambda x: x[0])
            for i, (_, name, line, desc) in enumerate(crud_funcs):
                # 找函数结束行
                func_obj = next((f for f in all_funcs if f.name == name), None)
                end_line = func_obj.end_line if func_obj else line
                steps.append(
                    MainFlowStep(
                        step=i + 1,
                        description=desc,
                        related_function=name,
                        line_start=line,
                        line_end=end_line,
                    )
                )

        # 如果 CRUD 不够 3 步，补充其他关键函数
        if len(steps) < 3:
            other_patterns = [p for p in patterns if p.pattern_id != "crud" and p.target_type == "function"]
            for p in other_patterns[:5]:
                if not any(s.related_function == p.target_name for s in steps):
                    func_obj = next((f for f in all_funcs if f.name == p.target_name), None)
                    end_line = func_obj.end_line if func_obj else p.target_line
                    steps.append(
                        MainFlowStep(
                            step=len(steps) + 1,
                            description=f"{p.pattern_name}：{p.target_name}",
                            related_function=p.target_name,
                            line_start=p.target_line,
                            line_end=end_line,
                        )
                    )

        # 重新编号
        for i, s in enumerate(steps):
            s.step = i + 1

        return steps

    def _calculate_difficulty(
        self,
        parsed: ParsedResult,
        patterns: List[PatternMatch],
        knowledge: List[KnowledgePoint],
    ) -> float:
        """
        计算代码整体难度（1-5）

        维度：
        - 代码量
        - 控制流复杂度（if/loop/try 数量）
        - 知识点难度分布
        - 业务模式的复杂度
        """
        all_funcs = parsed.get_all_functions()
        total_lines = len(parsed.source_lines)

        # 1. 代码量分（最多 1.5 分）
        if total_lines < 50:
            line_score = 0.5
        elif total_lines < 150:
            line_score = 1.0
        elif total_lines < 300:
            line_score = 1.3
        else:
            line_score = 1.5

        # 2. 控制流复杂度（最多 1.5 分）
        total_if = sum(f.if_count for f in all_funcs)
        total_loop = sum(f.loop_count for f in all_funcs)
        total_try = sum(f.try_count for f in all_funcs)
        total_raise = sum(f.raise_count for f in all_funcs)

        complexity = total_if + total_loop * 1.5 + total_try * 2 + total_raise
        if complexity < 5:
            ctrl_score = 0.5
        elif complexity < 15:
            ctrl_score = 1.0
        elif complexity < 30:
            ctrl_score = 1.3
        else:
            ctrl_score = 1.5

        # 3. 知识点难度（最多 1.5 分）
        if not knowledge:
            kp_score = 0.5
        else:
            avg_difficulty = sum(kp.difficulty for kp in knowledge) / len(knowledge)
            kp_score = (avg_difficulty / 5) * 1.5

        # 4. 业务模式多样性（最多 0.5 分）
        unique_categories = set(p.category for p in patterns)
        pattern_score = min(len(unique_categories) * 0.1, 0.5)

        total = line_score + ctrl_score + kp_score + pattern_score
        return max(1.0, min(5.0, total))
