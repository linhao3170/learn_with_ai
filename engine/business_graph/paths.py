"""
路径规范化（再导出）

**真正的实现在 ``engine/path_utils.py``** —— 保留这个模块名只是为了
README5 §13.2 的记录仍然成立，以及让 ``business_graph`` 内部 import 路径稳定。

⚠️ 不要再在这里写第二份实现。曾经就是因为有两份，只修了一份，
导致图谱里 1054 处路径变成 ``../../safety_checker.py``。
"""

from __future__ import annotations

from ..path_utils import (  # noqa: F401  (对外再导出)
    LOCATION_KEYS,
    PATH_KEYS,
    build_relativizer,
    relativize_location,
    relativize_paths,
)

__all__ = [
    "PATH_KEYS",
    "LOCATION_KEYS",
    "build_relativizer",
    "relativize_location",
    "relativize_paths",
]
