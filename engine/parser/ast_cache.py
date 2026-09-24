"""
共享 AST / 源码缓存（P0-14）

背景
----
同一次分析里，同一份源码会被多个分析器反复读取并 ``ast.parse``：

- ``project_analyzer/project_parser.py``
- ``deep_analyzer/project_call_graph.py``（两处）
- ``deep_analyzer/state_tracker.py``
- ``deep_analyzer/key_implementation.py``（按方法遍历，重复度最高）
- ``deep_analyzer/design_pattern_detector.py``

历史上一个文件最多被读 + 解析 5 次以上。本模块把它们收敛成"每个文件一次"。

设计要点
--------
1. **缓存键为 ``(绝对路径, mtime_ns, size)``**，所以文件被修改后缓存自动失效，
   不会出现"改了代码还用旧 AST"的静默错误；
2. **失败也会被记住**（语法错误 / 编码错误），避免同一个坏文件被反复重试并反复打印；
3. **返回 ``None`` 而不是抛异常**，与现有各分析器的"跳过该文件"行为保持一致；
4. **不引入任何全局可变语义**：只有缓存，且缓存内容只由文件系统决定，
   因此同一份输入仍然得到同一份输出（满足 README5 第 3.9 节的确定性要求）。
5. 提供 ``stats()`` / ``clear()``，便于脚本验证"是否真的只解析了一次"。
"""

from __future__ import annotations

import ast
import os
import threading
from typing import Dict, Optional, Tuple

__all__ = ["get_source", "get_tree", "clear", "stats", "CacheKey"]

CacheKey = Tuple[str, int, int]

_source_cache: Dict[CacheKey, str] = {}
_tree_cache: Dict[CacheKey, ast.AST] = {}
_failure_cache: Dict[CacheKey, str] = {}
_stats = {"source_hits": 0, "source_misses": 0, "tree_hits": 0, "tree_misses": 0}
_lock = threading.RLock()


def _make_key(path: str) -> Optional[CacheKey]:
    """按 (绝对路径, mtime_ns, size) 构造缓存键；文件不存在时返回 None。"""
    try:
        abspath = os.path.abspath(path)
        stat = os.stat(abspath)
    except OSError:
        return None
    return (abspath, stat.st_mtime_ns, stat.st_size)


def get_source(path: str) -> Optional[str]:
    """
    读取文件源码（带缓存）。

    Returns:
        源码字符串；文件不存在、编码错误或读取失败时返回 ``None``。
    """
    key = _make_key(path)
    if key is None:
        return None

    with _lock:
        if key in _source_cache:
            _stats["source_hits"] += 1
            return _source_cache[key]
        if key in _failure_cache:
            return None

    try:
        with open(key[0], "r", encoding="utf-8") as fh:
            source = fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        with _lock:
            _failure_cache[key] = f"read failed: {type(exc).__name__}"
            _stats["source_misses"] += 1
        return None

    with _lock:
        _source_cache[key] = source
        _stats["source_misses"] += 1
    return source


def get_tree(path: str) -> Optional[ast.AST]:
    """
    解析文件为 AST（带缓存，复用 :func:`get_source` 的结果）。

    Returns:
        ``ast.Module``；语法错误或读取失败时返回 ``None``。
    """
    key = _make_key(path)
    if key is None:
        return None

    with _lock:
        if key in _tree_cache:
            _stats["tree_hits"] += 1
            return _tree_cache[key]
        if key in _failure_cache:
            return None

    source = get_source(path)
    if source is None:
        return None

    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError) as exc:
        with _lock:
            _failure_cache[key] = f"parse failed: {type(exc).__name__}"
            _stats["tree_misses"] += 1
        return None

    with _lock:
        _tree_cache[key] = tree
        _stats["tree_misses"] += 1
    return tree


def clear() -> None:
    """清空所有缓存（脚本/测试在分析不同项目之间调用）。"""
    with _lock:
        _source_cache.clear()
        _tree_cache.clear()
        _failure_cache.clear()
        for name in _stats:
            _stats[name] = 0


def stats() -> dict:
    """返回缓存统计，便于验证"同一文件只解析一次"。"""
    with _lock:
        return {
            **_stats,
            "cached_sources": len(_source_cache),
            "cached_trees": len(_tree_cache),
            "failures": len(_failure_cache),
        }
