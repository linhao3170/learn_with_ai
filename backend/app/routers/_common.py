"""两个上传接口共用的工具（**不是路由**，不要在这里加 ``@router.*``）。

WO-02 拆分时，``_find_project_root`` 原本定义在 ``main.py`` 末尾，被
``POST /api/analyze`` 与 ``POST /api/logic-platform/analyze`` 两处调用。
拆成两个 router 之后它不能再住在其中一个里（那会让两个 router 互相依赖），
所以原样搬到本模块：**函数体逐字未改**。
"""

from __future__ import annotations

from pathlib import Path


def _find_project_root(py_files: list[Path]) -> Path:
    """Find the common parent directory of all Python files.

    If the common parent is a single-wrapper directory (contains only
    one subdirectory and no .py files), drill down one level.
    """
    if not py_files:
        raise ValueError("No Python files")

    common = py_files[0].parent
    for f in py_files[1:]:
        while common not in f.parents and common != f:
            common = common.parent
            if common == common.parent:
                break

    current = common
    while True:
        py_in_current = [p for p in current.iterdir() if p.suffix == ".py"]
        subdirs = [p for p in current.iterdir() if p.is_dir()]
        if not py_in_current and len(subdirs) == 1:
            current = subdirs[0]
        else:
            break

    return current
