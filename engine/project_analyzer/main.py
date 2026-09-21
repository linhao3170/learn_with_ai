"""
项目级业务逻辑分析器主入口

整合项目解析、模块分析、训练生成，
输出完整的项目级分析结果。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .project_parser import ProjectParser, ProjectInfo
from .module_analyzer import ModuleAnalyzer, ModuleInfo, ModuleDependency, CoreFlow
from .training_generator import TrainingGenerator, TrainingSet
from ..deep_analyzer import DeepAnalyzer


@dataclass
class ProjectAnalysisResult:
    """项目级完整分析结果"""
    project_name: str = ""
    project_path: str = ""
    overview: dict = field(default_factory=dict)
    modules: list = field(default_factory=list)
    dependencies: list = field(default_factory=list)
    core_flows: list = field(default_factory=list)
    training: dict = field(default_factory=dict)
    deep_analysis: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "project_path": self.project_path,
            "overview": self.overview,
            "modules": self.modules,
            "dependencies": self.dependencies,
            "core_flows": self.core_flows,
            "training": self.training,
            "deep_analysis": self.deep_analysis,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, default=str)


class ProjectAnalyzer:
    """项目级业务逻辑分析器"""

    def __init__(self):
        self.project_parser = ProjectParser()
        self.module_analyzer = ModuleAnalyzer()
        self.training_generator = TrainingGenerator(seed=42)
        self.deep_analyzer = DeepAnalyzer(max_flows=10, max_flow_depth=6)

    def analyze(self, project_path: str) -> ProjectAnalysisResult:
        """
        分析一个项目目录

        Args:
            project_path: 项目路径

        Returns:
            ProjectAnalysisResult 完整分析结果
        """
        # 步骤 1：解析项目
        project_info = self.project_parser.parse_project(project_path)

        # 步骤 2：模块分析
        modules, dependencies, core_flows = self.module_analyzer.analyze(project_info)

        # 步骤 3：深度业务逻辑分析（调用图 + 流程提取 + 状态追踪 + 依赖强度）
        deep_result = self.deep_analyzer.analyze(project_info)

        # 用深度分析数据增强模块信息（角色、中心度、真实依赖、入口点）
        self._enhance_modules_with_deep_data(modules, deep_result)

        # 补充深度分析发现但 module_analyzer 漏掉的模块（如 orchestrator）
        self._add_missing_modules_from_deep(modules, deep_result, project_info)

        # 用真实调用链流程替换关键词拼凑的流程
        if deep_result.business_flows:
            core_flows = self._convert_deep_flows(deep_result.business_flows)

        # 用真实调用依赖替换 import 推断的依赖
        deep_deps = deep_result.module_dependencies
        if deep_deps:
            dependencies = self._convert_deep_dependencies(deep_deps)

        # 步骤 4：生成训练题
        training = self.training_generator.generate(
            modules, core_flows,
            project_name=project_info.project_name,
            project_description="",
            key_implementations=deep_result.key_implementations,
        )

        # 组装结果
        result = ProjectAnalysisResult(
            project_name=project_info.project_name,
            project_path=project_info.project_path,
        )

        # 概览
        result.overview = {
            "total_files": project_info.total_files,
            "total_lines": project_info.total_lines,
            "total_classes": project_info.total_classes,
            "total_functions": project_info.total_functions,
            "module_count": len(modules),
            "core_module_count": sum(1 for m in modules if m.core_score >= 0.5),
        }

        # 模块列表
        result.modules = [
            {
                "module_id": m.module_id,
                "name": m.name,
                "type": m.module_type,
                "description": m.description,
                "responsibilities": m.key_responsibilities,
                "class_count": m.class_count,
                "method_count": m.method_count,
                "core_score": m.core_score,
                "depends_on": m.depends_on,
                "depended_by": m.depended_by,
                "files": m.files,
                "classes": [
                    {
                        "name": c["class_name"],
                        "method_count": c["method_count"],
                        "start_line": c["start_line"],
                        "end_line": c["end_line"],
                        "docstring": c.get("docstring"),
                    }
                    for c in m.classes
                ],
            }
            for m in modules
        ]

        # 依赖关系
        result.dependencies = [
            {
                "from": d.from_module,
                "to": d.to_module,
                "type": d.dependency_type,
                "strength": d.strength,
            }
            for d in dependencies
        ]

        # 核心流程
        result.core_flows = [
            {
                "flow_id": f.flow_id,
                "name": f.name,
                "description": f.description,
                "steps": f.steps,
                "involved_modules": f.involved_modules,
            }
            for f in core_flows
        ]

        # 深度分析完整数据（供前端高级视图使用）
        result.deep_analysis = deep_result.to_dict()

        # 训练题
        result.training = training.to_dict()

        return result

    def _enhance_modules_with_deep_data(self, modules: list, deep_result) -> None:
        """
        用深度分析数据增强关键词推断的模块信息。
        添加角色分类、中心度、真实依赖关系、入口点等。
        """
        deep_modules = {m["module_id"]: m for m in deep_result.modules}

        for mod in modules:
            deep_mod = deep_modules.get(mod.module_id)
            if not deep_mod:
                continue
            # 用调用图中心度替换关键词评分
            mod.core_score = deep_mod["centrality"]
            # 用真实角色替换关键词分类（orchestrator/core/peripheral）
            mod.module_type = deep_mod["role"]
            # 用真实调用依赖替换 import 推断
            mod.depends_on = deep_mod["depends_on"]
            mod.depended_by = deep_mod["depended_by"]
            # 方法数使用调用图的节点数
            if deep_mod["internal_nodes"]:
                mod.method_count = deep_mod["internal_nodes"]

    def _add_missing_modules_from_deep(self, modules: list, deep_result, project_info) -> None:
        """
        补充深度分析发现但 module_analyzer 漏掉的模块。
        典型场景：orchestrator / app 主入口模块被当成"聚合器"过滤掉了。
        """
        from .module_analyzer import ModuleInfo

        existing_ids = {m.module_id for m in modules}

        for deep_mod in deep_result.modules:
            mod_id = deep_mod["module_id"]
            if mod_id in existing_ids:
                continue

            # 跳过没有内部节点的空模块
            if deep_mod["internal_nodes"] == 0:
                continue

            # 从 project_info 里找对应的类信息
            classes = []
            for f in project_info.files:
                if f.module_name == mod_id:
                    for cls in f.parsed.classes:
                        classes.append({
                            "class_name": cls.name,
                            "method_count": len(cls.methods),
                            "start_line": cls.start_line,
                            "end_line": cls.end_line,
                            "docstring": cls.docstring,
                        })

            # 根据角色生成模块名称和职责
            role = deep_mod["role"]
            if role == "orchestrator":
                name = "系统编排模块"
                desc = "负责系统初始化、业务流程编排、模块协调"
                responsibilities = ["系统初始化", "业务流程编排", "模块协调", "全局状态管理"]
            elif role == "core":
                name = mod_id.replace("_", " ") + " 模块"
                desc = f"核心业务模块（{mod_id}）"
                responsibilities = ["核心业务逻辑"]
            else:
                name = mod_id.replace("_", " ") + " 模块"
                desc = f"支撑模块（{mod_id}）"
                responsibilities = ["辅助功能"]

            new_mod = ModuleInfo(
                module_id=mod_id,
                name=name,
                module_type=role,
                files=[f.filepath for f in project_info.files if f.module_name == mod_id],
                classes=classes,
                class_count=len(classes),
                method_count=deep_mod["internal_nodes"],
                description=desc,
                key_responsibilities=responsibilities,
                depends_on=deep_mod["depends_on"],
                depended_by=deep_mod["depended_by"],
                core_score=deep_mod["centrality"],
            )
            modules.append(new_mod)

    def _convert_deep_flows(self, flows: list) -> list:
        """将 BusinessFlow 转换为 CoreFlow 格式，保持向后兼容。"""
        from .module_analyzer import CoreFlow

        core_flows = []
        for flow in flows:
            steps = []
            for step in flow.steps:
                steps.append({
                    "step_id": step.step_id,
                    "name": step.method_name,
                    "module": step.module_name,
                    "class": step.class_name,
                    "method": step.method_name,
                    "order": step.step_order,
                    "depth": step.depth,
                    "is_module_boundary": step.is_module_boundary,
                    "is_state_change": step.is_state_change,
                    "is_validation": step.is_validation,
                    "description": step.description,
                    "line": step.line_number,
                })

            cf = CoreFlow(
                flow_id=flow.flow_id,
                name=flow.name,
                description=flow.description,
                steps=steps,
                involved_modules=flow.modules_involved,
            )
            core_flows.append(cf)
        return core_flows

    def _convert_deep_dependencies(self, deep_deps: list) -> list:
        """将深度分析的模块依赖转换为 ModuleDependency 格式。"""
        from .module_analyzer import ModuleDependency

        result = []
        for dep in deep_deps:
            md = ModuleDependency(
                from_module=dep["from"],
                to_module=dep["to"],
                dependency_type="call",
                strength=int(dep["strength"] * 10),
            )
            # 携带详细数据供下游使用
            md.call_count = dep["call_count"]
            md.unique_methods = dep["unique_methods"]
            md.strength_score = dep["strength"]
            result.append(md)
        return result
