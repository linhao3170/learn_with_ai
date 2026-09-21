"""
业务模式识别引擎

借鉴 bandit 的插件式规则架构，将每种业务模式定义为一条可注册的规则。
每条规则接收一个函数/类的解析结果，返回匹配度和证据。

当前支持的业务模式：
- CRUD (Create/Read/Update/Delete)
- 数据验证 (data_validation)
- 异常处理 (error_handling)
- 文件操作 (file_operation)
- 数据持久化 (data_persistence)
- 统计计算 (statistical_calculation)
- 批量处理 (batch_processing)
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Dict, Any

from ..parser.python_parser import ParsedResult, FunctionInfo, ClassInfo


# 置信度等级
CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"


@dataclass
class Evidence:
    """匹配证据：能回指到源码行号"""
    description: str
    line_start: int
    line_end: int
    evidence_type: str = "code"  # code / docstring / naming


@dataclass
class PatternMatch:
    """模式匹配结果"""
    pattern_id: str
    pattern_name: str
    category: str  # 大类：如 CRUD、验证、IO等
    confidence: str  # high/medium/low
    score: float  # 0-1 匹配度
    target_type: str  # function / class / module
    target_name: str
    target_line: int
    evidence: List[Evidence] = field(default_factory=list)
    sub_type: Optional[str] = None  # 子类型，如 CRUD 的 C/R/U/D
    description: str = ""


@dataclass
class BusinessPattern:
    """业务模式定义"""
    pattern_id: str
    name: str
    category: str
    description: str
    detector: Callable  # 检测函数


class PatternDetector:
    """
    业务模式检测器

    采用注册式架构，类似 bandit 的插件机制。
    每种模式是一个独立的检测函数，可动态注册/禁用。
    """

    def __init__(self):
        self._patterns: Dict[str, BusinessPattern] = {}
        self._register_default_patterns()

    def register(self, pattern: BusinessPattern):
        """注册一个业务模式"""
        self._patterns[pattern.pattern_id] = pattern

    def unregister(self, pattern_id: str):
        """注销一个业务模式"""
        self._patterns.pop(pattern_id, None)

    def list_patterns(self) -> List[BusinessPattern]:
        """列出所有已注册的模式"""
        return list(self._patterns.values())

    def detect(self, parsed_result: ParsedResult) -> List[PatternMatch]:
        """
        对解析结果运行所有模式检测

        Args:
            parsed_result: 解析结果

        Returns:
            所有匹配结果列表
        """
        matches: List[PatternMatch] = []

        # 对每个函数运行检测
        for func in parsed_result.get_all_functions():
            for pattern in self._patterns.values():
                try:
                    result = pattern.detector(func, parsed_result, "function")
                    if result and result.score > 0:
                        matches.append(result)
                except Exception:
                    # 单个规则失败不影响整体
                    pass

        # 对每个类运行检测（聚合判断）
        for cls in parsed_result.classes:
            for pattern in self._patterns.values():
                try:
                    result = pattern.detector(cls, parsed_result, "class")
                    if result and result.score > 0:
                        matches.append(result)
                except Exception:
                    pass

        # 按分数排序
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches

    def _register_default_patterns(self):
        """注册内置的默认业务模式"""
        self.register(_make_crud_pattern())
        self.register(_make_data_validation_pattern())
        self.register(_make_error_handling_pattern())
        self.register(_make_file_operation_pattern())
        self.register(_make_data_persistence_pattern())
        self.register(_make_statistical_pattern())
        self.register(_make_batch_processing_pattern())


# ============================================================
# 以下是各模式的检测函数
# ============================================================

def _make_crud_pattern() -> BusinessPattern:
    """CRUD 模式检测"""

    def detect(target, parsed: ParsedResult, target_type: str) -> Optional[PatternMatch]:
        if target_type == "function":
            name = target.name.lower()
            sub_type = None
            score = 0.0
            evidence = []

            # Create
            if re.search(r"(add|create|insert|new|register)", name):
                sub_type = "C"
                score = 0.6
                evidence.append(
                    Evidence(
                        description=f"函数名包含新增语义: {target.name}",
                        line_start=target.start_line,
                        line_end=target.start_line,
                        evidence_type="naming",
                    )
                )
                # 如果还有 raise 验证，加分
                if target.raise_count > 0:
                    score += 0.2
                    evidence.append(
                        Evidence(
                            description=f"包含 {target.raise_count} 处参数校验异常",
                            line_start=target.start_line,
                            line_end=target.end_line,
                            evidence_type="code",
                        )
                    )

            # Delete
            elif re.search(r"(delete|remove|drop|clear)", name):
                sub_type = "D"
                score = 0.6
                evidence.append(
                    Evidence(
                        description=f"函数名包含删除语义: {target.name}",
                        line_start=target.start_line,
                        line_end=target.start_line,
                        evidence_type="naming",
                    )
                )

            # Update
            elif re.search(r"(update|modify|edit|change|set_)", name):
                sub_type = "U"
                score = 0.6
                evidence.append(
                    Evidence(
                        description=f"函数名包含更新语义: {target.name}",
                        line_start=target.start_line,
                        line_end=target.start_line,
                        evidence_type="naming",
                    )
                )

            # Read
            elif re.search(r"(get|find|query|search|fetch|list|show|lookup)", name):
                sub_type = "R"
                score = 0.55
                evidence.append(
                    Evidence(
                        description=f"函数名包含查询语义: {target.name}",
                        line_start=target.start_line,
                        line_end=target.start_line,
                        evidence_type="naming",
                    )
                )
                if target.loop_count > 0:
                    score += 0.15
                    evidence.append(
                        Evidence(
                            description="包含循环遍历逻辑",
                            line_start=target.start_line,
                            line_end=target.end_line,
                            evidence_type="code",
                        )
                    )

            if sub_type and score > 0:
                confidence = CONFIDENCE_HIGH if score >= 0.7 else CONFIDENCE_MEDIUM
                return PatternMatch(
                    pattern_id="crud",
                    pattern_name="CRUD 数据操作",
                    category="data_operation",
                    confidence=confidence,
                    score=min(score, 1.0),
                    target_type="function",
                    target_name=target.name,
                    target_line=target.start_line,
                    evidence=evidence,
                    sub_type=sub_type,
                    description=f"该函数实现了 CRUD 中的 {sub_type} 操作",
                )

        elif target_type == "class":
            # 类级别的 CRUD 判断：看方法名集合
            method_names = [m.name.lower() for m in target.methods]
            crud_flags = {
                "C": any(re.search(r"(add|create|insert|new|register)", n) for n in method_names),
                "R": any(re.search(r"(get|find|query|search|fetch|list|show)", n) for n in method_names),
                "U": any(re.search(r"(update|modify|edit|change|set_)", n) for n in method_names),
                "D": any(re.search(r"(delete|remove|drop|clear)", n) for n in method_names),
            }
            count = sum(1 for v in crud_flags.values() if v)
            if count >= 2:
                score = 0.3 + count * 0.15
                present = [k for k, v in crud_flags.items() if v]
                return PatternMatch(
                    pattern_id="crud",
                    pattern_name="CRUD 数据操作",
                    category="data_operation",
                    confidence=CONFIDENCE_HIGH if count >= 3 else CONFIDENCE_MEDIUM,
                    score=min(score, 1.0),
                    target_type="class",
                    target_name=target.name,
                    target_line=target.start_line,
                    evidence=[
                        Evidence(
                            description=f"类中包含 CRUD 操作: {', '.join(present)}",
                            line_start=target.start_line,
                            line_end=target.end_line,
                            evidence_type="naming",
                        )
                    ],
                    sub_type="".join(present),
                    description=f"该类是一个 CRUD 管理器，包含 {count} 种操作: {', '.join(present)}",
                )

        return None

    return BusinessPattern(
        pattern_id="crud",
        name="CRUD 数据操作",
        category="data_operation",
        description="增删改查类数据操作",
        detector=detect,
    )


def _make_data_validation_pattern() -> BusinessPattern:
    """数据验证模式检测"""

    def detect(target, parsed: ParsedResult, target_type: str) -> Optional[PatternMatch]:
        if target_type != "function":
            return None

        score = 0.0
        evidence = []

        # 有 raise 和 if 的组合
        if target.if_count > 0 and target.raise_count > 0:
            # 验证型：if 检查 + raise 报错
            validation_patterns = min(target.if_count, target.raise_count)
            score = min(0.3 + validation_patterns * 0.15, 1.0)
            evidence.append(
                Evidence(
                    description=f"包含 {target.if_count} 个条件判断和 {target.raise_count} 个异常抛出",
                    line_start=target.start_line,
                    line_end=target.end_line,
                    evidence_type="code",
                )
            )

        # 函数名提示
        name = target.name.lower()
        if re.search(r"(valid|check|verify|assert|validate)", name):
            score += 0.2
            evidence.append(
                Evidence(
                    description=f"函数名包含验证语义: {target.name}",
                    line_start=target.start_line,
                    line_end=target.start_line,
                    evidence_type="naming",
                )
            )

        if score >= 0.4:
            confidence = CONFIDENCE_HIGH if score >= 0.7 else CONFIDENCE_MEDIUM
            return PatternMatch(
                pattern_id="data_validation",
                pattern_name="数据验证",
                category="validation",
                confidence=confidence,
                score=min(score, 1.0),
                target_type="function",
                target_name=target.name,
                target_line=target.start_line,
                evidence=evidence,
                description="该函数包含输入数据合法性校验逻辑",
            )
        return None

    return BusinessPattern(
        pattern_id="data_validation",
        name="数据验证",
        category="validation",
        description="对输入数据进行合法性校验",
        detector=detect,
    )


def _make_error_handling_pattern() -> BusinessPattern:
    """异常处理模式检测"""

    def detect(target, parsed: ParsedResult, target_type: str) -> Optional[PatternMatch]:
        if target_type != "function":
            return None

        if target.try_count == 0:
            return None

        score = min(0.5 + target.try_count * 0.1, 1.0)
        evidence = [
            Evidence(
                description=f"包含 {target.try_count} 个 try/except 异常处理块",
                line_start=target.start_line,
                line_end=target.end_line,
                evidence_type="code",
            )
        ]

        confidence = CONFIDENCE_HIGH if target.try_count >= 2 else CONFIDENCE_MEDIUM
        return PatternMatch(
            pattern_id="error_handling",
            pattern_name="异常处理",
            category="robustness",
            confidence=confidence,
            score=score,
            target_type="function",
            target_name=target.name,
            target_line=target.start_line,
            evidence=evidence,
            description="该函数包含异常捕获和处理逻辑",
        )

    return BusinessPattern(
        pattern_id="error_handling",
        name="异常处理",
        category="robustness",
        description="try/except 异常捕获与处理",
        detector=detect,
    )


def _make_file_operation_pattern() -> BusinessPattern:
    """文件操作模式检测"""

    def detect(target, parsed: ParsedResult, target_type: str) -> Optional[PatternMatch]:
        if target_type != "function":
            return None

        called = [c.lower() for c in target.called_functions]
        file_keywords = ["open", "read", "write", "close", "readlines", "writelines"]
        matches = [k for k in file_keywords if k in called]

        # 函数名判断
        name = target.name.lower()
        name_hint = bool(re.search(r"(file|load|save|read|write|import|export)", name))

        score = 0.0
        evidence = []

        if matches:
            score = 0.5 + len(matches) * 0.1
            evidence.append(
                Evidence(
                    description=f"调用了文件操作函数: {', '.join(matches)}",
                    line_start=target.start_line,
                    line_end=target.end_line,
                    evidence_type="code",
                )
            )

        if name_hint:
            score += 0.15
            evidence.append(
                Evidence(
                    description=f"函数名包含文件操作语义: {target.name}",
                    line_start=target.start_line,
                    line_end=target.start_line,
                    evidence_type="naming",
                )
            )

        # 从 import 检查
        for imp in parsed.imports:
            if imp.module in ("json", "csv", "pickle", "io"):
                if name_hint or matches:
                    score += 0.1
                    evidence.append(
                        Evidence(
                            description=f"导入了 {imp.module} 模块用于数据持久化",
                            line_start=imp.line,
                            line_end=imp.line,
                            evidence_type="code",
                        )
                    )

        if score >= 0.5:
            confidence = CONFIDENCE_HIGH if score >= 0.8 else CONFIDENCE_MEDIUM
            return PatternMatch(
                pattern_id="file_operation",
                pattern_name="文件操作",
                category="io",
                confidence=confidence,
                score=min(score, 1.0),
                target_type="function",
                target_name=target.name,
                target_line=target.start_line,
                evidence=evidence,
                description="该函数涉及文件读写操作",
            )
        return None

    return BusinessPattern(
        pattern_id="file_operation",
        name="文件操作",
        category="io",
        description="文件读写、数据导入导出",
        detector=detect,
    )


def _make_data_persistence_pattern() -> BusinessPattern:
    """数据持久化模式（文件/数据库存储）"""

    def detect(target, parsed: ParsedResult, target_type: str) -> Optional[PatternMatch]:
        if target_type != "function":
            return None

        called = [c.lower() for c in target.called_functions]

        # json.load / json.dump 等序列化操作
        persistence_funcs = ["load", "dump", "loads", "dumps", "connect", "execute", "commit"]
        matches = [c for c in called if c in persistence_funcs]

        name = target.name.lower()
        name_hint = bool(re.search(r"(save|load|store|persist|serialize|deserialize)", name))

        score = 0.0
        evidence = []

        if matches and ("json" in [i.module for i in parsed.imports] or name_hint):
            score = 0.6 + len(matches) * 0.1
            evidence.append(
                Evidence(
                    description=f"包含序列化/持久化操作: {', '.join(matches)}",
                    line_start=target.start_line,
                    line_end=target.end_line,
                    evidence_type="code",
                )
            )

        if score >= 0.6:
            return PatternMatch(
                pattern_id="data_persistence",
                pattern_name="数据持久化",
                category="io",
                confidence=CONFIDENCE_MEDIUM,
                score=min(score, 1.0),
                target_type="function",
                target_name=target.name,
                target_line=target.start_line,
                evidence=evidence,
                description="该函数涉及数据的持久化存储或加载",
            )
        return None

    return BusinessPattern(
        pattern_id="data_persistence",
        name="数据持久化",
        category="io",
        description="将数据保存到磁盘或从磁盘加载",
        detector=detect,
    )


def _make_statistical_pattern() -> BusinessPattern:
    """统计计算模式检测"""

    def detect(target, parsed: ParsedResult, target_type: str) -> Optional[PatternMatch]:
        if target_type != "function":
            return None

        called = [c.lower() for c in target.called_functions]
        stat_funcs = ["sum", "avg", "average", "mean", "max", "min", "len", "count", "sorted"]
        matches = [c for c in called if c in stat_funcs]

        name = target.name.lower()
        name_hint = bool(
            re.search(r"(average|avg|mean|sum|total|stat|calc|compute|ratio|percent)", name)
        )

        score = 0.0
        evidence = []

        if matches and target.loop_count > 0:
            score = 0.4 + min(len(matches) * 0.08, 0.3)
            evidence.append(
                Evidence(
                    description=f"在循环中使用了统计函数: {', '.join(set(matches))}",
                    line_start=target.start_line,
                    line_end=target.end_line,
                    evidence_type="code",
                )
            )
        elif name_hint and (target.loop_count > 0 or matches):
            score = 0.4

        if name_hint:
            score += 0.15
            evidence.append(
                Evidence(
                    description=f"函数名包含统计计算语义: {target.name}",
                    line_start=target.start_line,
                    line_end=target.start_line,
                    evidence_type="naming",
                )
            )

        if score >= 0.5:
            return PatternMatch(
                pattern_id="statistical_calculation",
                pattern_name="统计计算",
                category="algorithm",
                confidence=CONFIDENCE_MEDIUM,
                score=min(score, 1.0),
                target_type="function",
                target_name=target.name,
                target_line=target.start_line,
                evidence=evidence,
                description="该函数包含统计计算逻辑",
            )
        return None

    return BusinessPattern(
        pattern_id="statistical_calculation",
        name="统计计算",
        category="algorithm",
        description="求和、平均、最大最小等统计计算",
        detector=detect,
    )


def _make_batch_processing_pattern() -> BusinessPattern:
    """批量处理模式检测"""

    def detect(target, parsed: ParsedResult, target_type: str) -> Optional[PatternMatch]:
        if target_type != "function":
            return None

        name = target.name.lower()
        name_hint = bool(re.search(r"(batch|bulk|all|list|foreach|process|import)", name))

        score = 0.0
        evidence = []

        # 有循环 + 有数据结构操作
        if target.loop_count >= 1 and target.if_count >= 1:
            score = 0.3
            evidence.append(
                Evidence(
                    description=f"包含 {target.loop_count} 个循环和 {target.if_count} 个条件判断",
                    line_start=target.start_line,
                    line_end=target.end_line,
                    evidence_type="code",
                )
            )

        if name_hint and target.loop_count > 0:
            score += 0.3
            evidence.append(
                Evidence(
                    description=f"函数名包含批量处理语义: {target.name}",
                    line_start=target.start_line,
                    line_end=target.start_line,
                    evidence_type="naming",
                )
            )

        if score >= 0.5:
            return PatternMatch(
                pattern_id="batch_processing",
                pattern_name="批量处理",
                category="algorithm",
                confidence=CONFIDENCE_MEDIUM,
                score=min(score, 1.0),
                target_type="function",
                target_name=target.name,
                target_line=target.start_line,
                evidence=evidence,
                description="该函数对集合数据进行批量处理",
            )
        return None

    return BusinessPattern(
        pattern_id="batch_processing",
        name="批量处理",
        category="algorithm",
        description="对多条数据进行遍历和处理",
        detector=detect,
    )


def detect_patterns(source_code: str) -> List[PatternMatch]:
    """便捷函数：检测代码中的业务模式"""
    from ..parser import parse_python

    parsed = parse_python(source_code)
    detector = PatternDetector()
    return detector.detect(parsed)
