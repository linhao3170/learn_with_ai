"""
项目解析器

遍历项目目录，解析所有 Python 文件，
输出项目级别的结构化信息。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from ..parser.python_parser import PythonParser, ParsedResult


@dataclass
class FileInfo:
    """单个 Python 文件的解析信息"""
    filepath: str
    filename: str
    module_name: str  # 模块名（相对路径，如 reservation_manager）
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

    def get_all_classes(self) -> List[dict]:
        """获取所有类及其所在文件"""
        result = []
        for f in self.files:
            for cls in f.parsed.classes:
                result.append({
                    "class_name": cls.name,
                    "module_name": f.module_name,
                    "filepath": f.filepath,
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
                    "start_line": func.start_line,
                    "end_line": func.end_line,
                    "docstring": func.docstring,
                })
        return result


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
        for root, dirs, files in os.walk(project_path):
            # 跳过常见的不需要解析的目录
            dirs[:] = [
                d for d in dirs
                if d not in (
                    "__pycache__", ".git", "venv", "env",
                    "node_modules", ".venv", "dist", "build",
                    "tests", "test",
                ) and not d.startswith(".")
            ]

            for f in files:
                if not f.endswith(".py"):
                    continue

                filepath = os.path.join(root, f)
                rel_path = os.path.relpath(filepath, project_path)
                # 模块名：去掉 .py，路径分隔符换成点
                module_name = rel_path[:-3].replace(os.sep, ".")

                try:
                    with open(filepath, "r", encoding="utf-8") as fh:
                        code = fh.read()

                    parsed = self.python_parser.parse(code)

                    file_info = FileInfo(
                        filepath=filepath,
                        filename=f,
                        module_name=module_name,
                        parsed=parsed,
                    )
                    info.files.append(file_info)

                    # 统计
                    info.total_lines += len(parsed.source_lines)
                    info.total_functions += len(parsed.get_all_functions())
                    info.total_classes += len(parsed.classes)

                except (SyntaxError, UnicodeDecodeError):
                    # 跳过解析失败的文件
                    continue

        info.total_files = len(info.files)
        return info
