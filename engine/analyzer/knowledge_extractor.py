"""
知识点提取器

从代码分析结果中提取教学知识点，用于：
- 知识点标注（给每段代码打上学习标签）
- 题目生成（按知识点出题目）
- 学习路径推荐
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional

from ..parser.python_parser import ParsedResult, FunctionInfo
from .pattern_detector import PatternMatch


@dataclass
class KnowledgePoint:
    """知识点"""
    id: str
    name: str
    category: str  # 大类：基础语法/数据结构/算法/设计模式/异常处理 等
    difficulty: int  # 1-5 难度等级
    related_lines: List[int] = field(default_factory=list)  # 相关行号
    related_functions: List[str] = field(default_factory=list)  # 相关函数
    description: str = ""


# 知识点定义表
KNOWLEDGE_MAP = {
    # --- 基础语法 ---
    "basic.class": ("类与对象", "基础语法", 2, "面向对象编程的基本概念：类定义、实例化"),
    "basic.function": ("函数定义", "基础语法", 1, "函数的定义、参数、返回值"),
    "basic.condition": ("条件判断", "基础语法", 1, "if/elif/else 条件语句"),
    "basic.loop": ("循环结构", "基础语法", 1, "for/while 循环语句"),
    "basic.dict": ("字典操作", "基础语法", 2, "字典的增删改查、遍历"),
    "basic.list": ("列表操作", "基础语法", 1, "列表的增删改查、遍历"),
    # --- 进阶语法 ---
    "adv.exception": ("异常处理", "进阶语法", 3, "try/except/raise 异常捕获与抛出"),
    "adv.decorator": ("装饰器", "进阶语法", 4, "函数装饰器的使用与原理"),
    "adv.comprehension": ("推导式", "进阶语法", 2, "列表/字典推导式"),
    "adv.generator": ("生成器", "进阶语法", 4, "yield 生成器函数"),
    # --- 数据验证 ---
    "validation.boundary": ("边界检查", "数据验证", 2, "输入参数的边界条件检查"),
    "validation.type": ("类型校验", "数据验证", 2, "使用 isinstance 等进行类型检查"),
    "validation.custom": ("自定义校验", "数据验证", 3, "业务逻辑层面的数据合法性验证"),
    # --- 设计模式 ---
    "pattern.crud": ("CRUD 模式", "设计模式", 2, "增删改查的数据管理模式"),
    "pattern.manager": ("管理器模式", "设计模式", 3, "集中管理某类资源的设计模式"),
    "pattern.singleton": ("单例模式", "设计模式", 3, "确保类只有一个实例的设计模式"),
    # --- 文件与IO ---
    "io.file": ("文件操作", "IO与持久化", 2, "文件的打开、读取、写入、关闭"),
    "io.json": ("JSON 序列化", "IO与持久化", 2, "JSON 格式的序列化与反序列化"),
    "io.context": ("上下文管理器", "IO与持久化", 3, "with 语句与上下文管理器"),
    # --- 算法 ---
    "algo.statistics": ("统计算法", "算法", 2, "求和、平均值、最大最小值等统计计算"),
    "algo.search": ("查找算法", "算法", 2, "线性查找、二分查找"),
    "algo.sort": ("排序算法", "算法", 3, "各类排序算法"),
}


class KnowledgeExtractor:
    """知识点提取器"""

    def extract(
        self,
        parsed: ParsedResult,
        patterns: List[PatternMatch],
    ) -> List[KnowledgePoint]:
        """
        从解析结果和模式匹配中提取知识点
        """
        points: Dict[str, KnowledgePoint] = {}

        def _add(kp_id: str, line: int = 0, func: str = ""):
            if kp_id not in KNOWLEDGE_MAP:
                return
            if kp_id not in points:
                name, category, difficulty, desc = KNOWLEDGE_MAP[kp_id]
                points[kp_id] = KnowledgePoint(
                    id=kp_id,
                    name=name,
                    category=category,
                    difficulty=difficulty,
                    description=desc,
                )
            if line and line not in points[kp_id].related_lines:
                points[kp_id].related_lines.append(line)
            if func and func not in points[kp_id].related_functions:
                points[kp_id].related_functions.append(func)

        # 1. 从类和函数结构提取
        if parsed.classes:
            for cls in parsed.classes:
                _add("basic.class", cls.start_line, cls.name)
                # 多方法的类 = 管理器模式
                if len(cls.methods) >= 4:
                    _add("pattern.manager", cls.start_line, cls.name)

        for func in parsed.get_all_functions():
            _add("basic.function", func.start_line, func.name)

            # 控制流相关
            if func.if_count > 0:
                _add("basic.condition", func.start_line, func.name)
            if func.loop_count > 0:
                _add("basic.loop", func.start_line, func.name)
            if func.try_count > 0:
                _add("adv.exception", func.start_line, func.name)
            if func.raise_count > 0:
                _add("adv.exception", func.start_line, func.name)

            # 验证相关
            if func.if_count > 0 and func.raise_count > 0:
                _add("validation.boundary", func.start_line, func.name)
                _add("validation.custom", func.start_line, func.name)

            # 装饰器
            if func.decorators:
                _add("adv.decorator", func.start_line, func.name)

            # 字典/列表操作（从被调函数名推断）
            called_lower = [c.lower() for c in func.called_functions]
            if any(c in ("append", "extend", "insert", "pop", "remove", "sort") for c in called_lower):
                _add("basic.list", func.start_line, func.name)
            if any(c in ("get", "keys", "values", "items", "update") for c in called_lower):
                _add("basic.dict", func.start_line, func.name)

            # 统计计算
            if any(c in ("sum", "avg", "average", "mean", "max", "min", "len") for c in called_lower):
                if func.loop_count > 0:
                    _add("algo.statistics", func.start_line, func.name)

        # 2. 从业务模式提取
        for p in patterns:
            if p.pattern_id == "crud":
                _add("pattern.crud", p.target_line, p.target_name)
            elif p.pattern_id == "data_validation":
                _add("validation.custom", p.target_line, p.target_name)
                _add("validation.boundary", p.target_line, p.target_name)
            elif p.pattern_id == "error_handling":
                _add("adv.exception", p.target_line, p.target_name)
            elif p.pattern_id == "file_operation":
                _add("io.file", p.target_line, p.target_name)
            elif p.pattern_id == "data_persistence":
                _add("io.json", p.target_line, p.target_name)
                _add("io.context", p.target_line, p.target_name)
            elif p.pattern_id == "statistical_calculation":
                _add("algo.statistics", p.target_line, p.target_name)
            elif p.pattern_id == "batch_processing":
                _add("basic.loop", p.target_line, p.target_name)

        # 3. 从导入提取
        for imp in parsed.imports:
            if imp.module == "json":
                _add("io.json", imp.line)
            elif imp.module in ("csv", "pickle"):
                _add("io.file", imp.line)

        # 排序：按难度 + 类别
        result = list(points.values())
        result.sort(key=lambda kp: (kp.difficulty, kp.category, kp.name))
        return result


def extract_knowledge(parsed: ParsedResult, patterns: List[PatternMatch]) -> List[KnowledgePoint]:
    """便捷函数：提取知识点"""
    return KnowledgeExtractor().extract(parsed, patterns)
