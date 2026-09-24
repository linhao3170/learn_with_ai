"""
路径规范化 —— **全仓库唯一的实现**（README5 §4.2 的"路径纪律"）

对外契约里**只能出现项目内相对路径**（POSIX 风格）。

为什么必须是唯一实现
--------------------
这条纪律一开始在两个地方各写了一份：``ProjectAnalyzer`` 一份、
``engine/business_graph/paths.py`` 一份。结果只给其中一份加了"幂等"修正，
另一份就把**已经相对的** ``safety_checker.py`` 又当成"相对当前工作目录"算了一次，
产出 ``../../safety_checker.py`` —— 图谱里 1054 处路径全部失真，前端跳转直接失效。

教训：**同一个不变量只允许有一个实现。**
``engine/business_graph/paths.py`` 现在只是对本模块的再导出
（保持 README5 §13.2 记录的模块名仍然可用）。

幂等要求
--------
``to_rel`` **绝对路径才转换、相对路径原样返回**。图谱里两类路径混在一起：
一部分来自 ``ProjectInfo.rel_path``（已经是相对的），一部分来自调用图节点（绝对的），
所以转换函数必须能安全地重复施加。
"""

from __future__ import annotations

import os
import re
from typing import Callable, Optional

#: 值是纯路径的键名
PATH_KEYS = frozenset({"filepath", "file", "display_path", "source_file", "source_path"})
#: 值是 ``path:line`` 形式的键名
LOCATION_KEYS = frozenset({"location"})

_LOCATION_RE = re.compile(r"^(?P<path>.+?):(?P<start>\d+)(?:-(?P<end>\d+))?$")


def build_relativizer(project_path: str, rel_by_abs: Optional[dict] = None) -> Callable[[str], str]:
    """构造一个 "绝对路径 → 项目内相对路径" 的函数。

    **必须是幂等的**。这一点是前端走查逼出来的：图谱里有一部分路径本来就来自
    ``ProjectInfo.rel_path``（已经是相对的，如 ``safety_checker.py``），
    另一部分来自调用图（绝对的）。如果无脑对每个 ``file`` 键做 ``os.path.relpath``，
    已经相对的 ``safety_checker.py`` 会被当成"相对当前工作目录"再算一次，
    结果变成 ``../../../safety_checker.py`` —— 前端跳转直接失效。

    所以：**绝对路径才转换，相对路径原样返回。**
    """
    mapping = dict(rel_by_abs or {})
    drive_re = re.compile(r"^[A-Za-z]:")

    def to_rel(path: str) -> str:
        if not path:
            return ""
        raw = str(path)
        normalized = raw.replace("\\", "/")
        if normalized in mapping:
            return mapping[normalized]
        try:
            np = os.path.normpath(raw)
        except (TypeError, ValueError):
            return normalized
        if np in mapping:
            return mapping[np]

        # 已经是相对路径 → 幂等返回（去掉可能的 "./" 前缀，统一 POSIX 分隔符）
        if not os.path.isabs(np) and not drive_re.match(np):
            if normalized.startswith("./"):
                normalized = normalized[2:]
            return normalized

        try:
            rel = os.path.relpath(np, project_path)
        except (TypeError, ValueError):
            return normalized
        return rel.replace(os.sep, "/").replace("\\", "/")

    return to_rel


def relativize_location(value: str, to_rel: Callable[[str], str]) -> str:
    """把 ``D:\\proj\\a.py:88`` 改写成 ``a.py:88``。"""
    match = _LOCATION_RE.match(str(value))
    if match:
        path = to_rel(match.group("path"))
        tail = match.group("start") + ("-" + match.group("end") if match.group("end") else "")
        return f"{path}:{tail}"
    if len(value) > 2 and (":" in value[:3] or value.startswith("/")):
        return to_rel(value)
    return value


def relativize_paths(obj, to_rel: Callable[[str], str]) -> None:
    """就地把契约里所有路径字段改写成项目内相对路径（原地修改，无返回值）。"""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str):
                if key in PATH_KEYS:
                    obj[key] = to_rel(value)
                elif key in LOCATION_KEYS:
                    obj[key] = relativize_location(value, to_rel)
            elif isinstance(value, (dict, list)):
                relativize_paths(value, to_rel)
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                relativize_paths(item, to_rel)
