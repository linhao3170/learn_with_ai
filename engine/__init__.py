"""
LearnWithAI 业务逻辑分析引擎

核心入口：BusinessLogicAnalyzer
"""

__version__ = "0.1.0"


def __getattr__(name):
    """延迟导入，避免模块未写完时报错"""
    if name == "parse_python":
        from .parser import parse_python

        return parse_python
    if name == "BusinessLogicAnalyzer":
        from .analyzer import BusinessLogicAnalyzer

        return BusinessLogicAnalyzer
    raise AttributeError(f"module 'engine' has no attribute {name!r}")
