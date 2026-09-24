"""
项目解析器

遍历项目目录，解析所有 Python 文件，
输出项目级别的结构化信息。

路径纪律（P0-10 / README5 §4.2）
--------------------------------
``FileInfo.filepath`` 是**绝对路径**，只允许在引擎内部使用，
**绝不能进入任何对外契约**（前端会把开发机路径 `D:\\...` 显示给评委）。

对外契约一律使用 ``rel_path``：项目内相对路径，统一使用 POSIX 分隔符 ``/``，
例如 ``sample_projects/lab_safety_assistant/reservation_manager.py``。

确定性（P0-14 / README5 §3.9）
------------------------------
``os.walk`` 的返回顺序依赖文件系统，会让模块列表顺序与 ``flow_{i+1}`` 编号漂移。
这里对 ``dirs`` 与 ``files`` 都排序，保证同一份代码得到同一份输出。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from ..parser.python_parser import PythonParser, ParsedResult
from ..parser.ast_cache import get_source, get_tree


def to_rel_path(filepath: str, project_path: str) -> str:
    """把绝对路径转换成项目内相对路径（POSIX 风格），用于所有对外契约。"""
    rel = os.path.relpath(filepath, project_path)
    return rel.replace(os.sep, "/").replace("\\", "/")


#: 遍历时跳过的目录名。
#:
#: 除了原本就有的虚拟环境/缓存目录，这里补上了 **docs / examples / benchmarks**：
#: 它们是"仓库的一部分"，但不是"产品的业务逻辑"。
#: 第三方验证时真的抓到了这个问题 —— flask 的 `docs/conf.py`、
#: `examples/tutorial/flaskr`、`examples/javascript/js_example`、
#: `examples/celery/src/task_app` 被当成了 4 个业务域，凭空多出 20% 的域。
#: 教师如果确实想分析示例代码，可以单独把那个目录当作项目上传。
SKIP_DIRS = frozenset({
    "__pycache__", ".git", "venv", "env", ".venv", "node_modules",
    "dist", "build", "tests", "test",
    "docs", "doc", "docs_src", "examples", "example", "samples",
    "benchmarks", "benchmark", "htmlcov", ".tox", ".nox", ".eggs",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
})


@dataclass
class FileInfo:
    """单个 Python 文件的解析信息"""
    filepath: str    # 绝对路径（仅引擎内部使用，不进契约）
    rel_path: str    # 项目内相对路径（POSIX 风格，进契约）
    filename: str
    module_name: str  # 模块名（相对路径点分，如 reservation_manager）
    parsed: ParsedResult


@dataclass
class ProjectInfo:
    """项目级解析结果"""
    project_path: str
    project_name: str
    files: List[FileInfo] = field(default_factory=list)
    total_files: int = 0
    total_lines: int = 0
    total_functions: int = 0
    total_classes: int = 0

    def rel_path_of(self, filepath: str) -> str:
        """把任意文件路径规范成项目内相对路径；不在项目内时原样返回（POSIX 化）。"""
        if not filepath:
            return ""
        normalized = filepath.replace("\\", "/")
        project_root = self.project_path.replace("\\", "/").rstrip("/")
        if normalized.startswith(project_root + "/"):
            return normalized[len(project_root) + 1:]
        return to_rel_path(filepath, self.project_path)

    def get_all_classes(self) -> List[dict]:
        """获取所有类及其所在文件"""
        result = []
        for f in self.files:
            for cls in f.parsed.classes:
                result.append({
                    "class_name": cls.name,
                    "module_name": f.module_name,
                    "filepath": f.filepath,
                    "rel_path": f.rel_path,
                    "start_line": cls.start_line,
                    "end_line": cls.end_line,
                    "docstring": cls.docstring,
                    "method_count": len(cls.methods),
                    "methods": cls.methods,
                })
        return result

    def get_all_functions(self) -> List[dict]:
        """获取所有顶层函数"""
        result = []
        for f in self.files:
            for func in f.parsed.functions:
                result.append({
                    "func_name": func.name,
                    "module_name": f.module_name,
                    "filepath": f.filepath,
                    "rel_path": f.rel_path,
                    "start_line": func.start_line,
                    "end_line": func.end_line,
                    "docstring": func.docstring,
                })
        return result

    def get_source(self, rel_path: str) -> Optional[str]:
        """按项目内相对路径取源码，供证据切片接口使用（P0-09）。

        只接受项目内的相对路径；任何试图越出项目根目录的路径都返回 ``None``。
        """
        if not rel_path:
            return None
        candidate = os.path.normpath(os.path.join(self.project_path, rel_path))
        root = os.path.normpath(self.project_path)
        if not candidate.startswith(root + os.sep) and candidate != root:
            return None
        return get_source(candidate)


class ProjectParser:
    """项目级解析器"""

    def __init__(self):
        self.python_parser = PythonParser()

    def parse_project(self, project_path: str) -> ProjectInfo:
        """
        解析一个项目目录下的所有 Python 文件

        Args:
            project_path: 项目根目录路径

        Returns:
            ProjectInfo 项目解析结果
        """
        project_path = os.path.abspath(project_path)
        project_name = os.path.basename(project_path.rstrip(os.sep))

        info = ProjectInfo(
            project_path=project_path,
            project_name=project_name,
        )

        # 遍历所有 .py 文件
        # P0-14：dirs 与 files 都排序，保证跨平台/跨文件系统得到同一顺序
        for root, dirs, files in os.walk(project_path):
            # 跳过不需要解析的目录（清单见模块顶部的 SKIP_DIRS）
            dirs[:] = sorted(
                d for d in dirs
                if d not in SKIP_DIRS and not d.startswith(".")
            )

            for f in sorted(files):
                if not f.endswith(".py"):
                    continue

                filepath = os.path.join(root, f)
                rel_path = to_rel_path(filepath, project_path)
                # 模块名：去掉 .py，路径分隔符换成点
                module_name = rel_path[:-3].replace("/", ".")

                # P0-14：走共享缓存，同一文件在一次分析里只读一次、只解析一次
                source = get_source(filepath)
                if source is None:
                    # 读取失败 / 编码错误 —— 跳过该文件
                    continue

                try:
                    parsed = self.python_parser.parse(source)
                except (SyntaxError, ValueError):
                    # 跳过解析失败的文件
                    continue

                file_info = FileInfo(
                    filepath=filepath,
                    rel_path=rel_path,
                    filename=f,
                    module_name=module_name,
                    parsed=parsed,
                )
                info.files.append(file_info)

                # 统计
                info.total_lines += len(parsed.source_lines)
                info.total_functions += len(parsed.get_all_functions())
                info.total_classes += len(parsed.classes)

        info.total_files = len(info.files)
        return info

