"""
项目级业务逻辑分析器主入口

整合项目解析、模块分析、训练生成，
输出完整的项目级分析结果。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from .project_parser import ProjectParser, ProjectInfo, to_rel_path
from .module_analyzer import ModuleAnalyzer, ModuleInfo, ModuleDependency, CoreFlow
from .training_generator import TrainingGenerator, TrainingSet
from ..deep_analyzer import DeepAnalyzer
from ..flow_filter import sort_flows_business_first

#: 对外契约版本；前端启动时校验，不匹配就拒绝渲染（README5 §4.1）
CONTRACT_VERSION = "1.0"

# 路径规范化**不再在本文件实现** —— 统一走 engine/path_utils.py。
# 这里曾经有过第二份实现，而且是唯一没有"幂等"修正的那一份：
# 它把已经相对的 `safety_checker.py` 又当绝对路径算了一次，
# 产出 `../../safety_checker.py`，图谱里 1054 处路径全部失真。
from ..path_utils import build_relativizer, relativize_paths as _relativize_paths  # noqa: E402


@dataclass
class ProjectAnalysisResult:
    """项目级完整分析结果"""
    project_name: str = ""
    project_path: str = ""      # 绝对路径 —— 仅引擎内部使用，不进对外契约
    overview: dict = field(default_factory=dict)
    modules: list = field(default_factory=list)
    dependencies: list = field(default_factory=list)
    core_flows: list = field(default_factory=list)
    training: dict = field(default_factory=dict)
    deep_analysis: dict = field(default_factory=dict)
    #: Sprint 1：业务图谱（README5 §4.2）—— 业务逻辑分析的核心产物
    business_graph: dict = field(default_factory=dict)
    #: 判题答案表 —— **只在后端使用**，不进入 to_dict()（P0-11）
    training_answer_key: dict = field(default_factory=dict)

    def to_dict(self, include_answers: bool = False) -> dict:
        """输出对外契约。

        P0-10：**不再输出 ``project_path``（开发机绝对路径）**，
        改为输出 ``project_id``（= 项目目录名）与 ``contract_version``。
        前端拿到的任何路径都必须是项目内相对路径（POSIX 风格）。

        P0-11：``include_answers=False``（默认，学生视图）时，训练题里
        **既不含 ``correct_answers``，也不含 ``explanation``** ——
        因为讲解里会直接把正确答案列出来（例如第 1 关会点名哪几个是业务模块）。
        两者都由后端判题接口在"学生已作答"之后才返回；
        ``include_answers=True`` 只用于教师预览模式（README3 §6.5）。
        """
        training = self.training
        if isinstance(training, dict) and not include_answers:
            hidden = ("correct_answers", "explanation")
            training = {
                **training,
                "questions": [
                    {k: v for k, v in q.items() if k not in hidden}
                    for q in training.get("questions", [])
                ],
            }

        return {
            "contract_version": CONTRACT_VERSION,
            "project_id": self.project_name,
            "project_name": self.project_name,
            "overview": self.overview,
            "modules": self.modules,
            "dependencies": self.dependencies,
            "core_flows": self.core_flows,
            "training": training,
            "deep_analysis": self.deep_analysis,
            # Sprint 1：业务图谱。它是"业务逻辑分析"的正式产物，
            # 前面的 modules/core_flows 是代码视角，这里是**业务视角**。
            "business_graph": self.business_graph,
        }

    def to_json(self, indent: int = 2, include_answers: bool = False) -> str:
        return json.dumps(
            self.to_dict(include_answers=include_answers),
            ensure_ascii=False,
            indent=indent,
            default=str,
        )


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

        # 记录绝对路径 → 相对路径的映射（P0-10）
        # 必须在生成训练题之前准备好，因为题目的代码证据也要用相对路径。
        rel_by_abs = {}
        for f in project_info.files:
            rel_by_abs[os.path.normpath(f.filepath)] = f.rel_path
            rel_by_abs[f.filepath.replace("\\", "/")] = f.rel_path

        # 用**共享实现**构造（幂等：绝对路径才转，相对路径原样返回）。
        # 不要再在本文件里自己写一份 —— 见文件顶部的注释。
        _to_rel = build_relativizer(project_info.project_path, rel_by_abs)

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
            core_flows = self._convert_deep_flows(
                deep_result.business_flows, deep_result.call_graph
            )

        # P0-06：把"初始化 / 样例数据"流程排到末尾（保留不删）。
        # 之前 core_flows[0] 常常是 `... Initialization Flow`，
        # 被 TrainingView 和第 3 关当成"最核心的业务流程"，属于教学性错误。
        core_flows = sort_flows_business_first(core_flows)

        # 用真实调用依赖替换 import 推断的依赖
        deep_deps = deep_result.module_dependencies
        if deep_deps:
            dependencies = self._convert_deep_dependencies(deep_deps)

        # 步骤 4：生成训练题
        # P0-10：把路径格式化函数注入生成器，避免题干/讲解里出现开发机绝对路径
        self.training_generator.set_path_formatter(_to_rel)
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

        # 记录绝对路径 → 相对路径的映射（P0-10）
        # 注意：该映射已在 analyze() 开头构建（生成训练题之前就需要它）。

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
                # P0-10：对外契约里只出现项目内相对路径
                "files": [_to_rel(p) for p in m.files],
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

        # 核心流程（P0-10：步骤里的 file 也要是项目内相对路径）
        def _rel_step(step: dict) -> dict:
            if "file" in step and step["file"]:
                return {**step, "file": _to_rel(step["file"])}
            return step

        result.core_flows = [
            {
                "flow_id": f.flow_id,
                "name": f.name,
                "description": f.description,
                "steps": [_rel_step(s) for s in f.steps],
                "involved_modules": f.involved_modules,
            }
            for f in core_flows
        ]

        # 深度分析完整数据（供前端高级视图使用）
        # P0-10：整棵 deep_analysis 里的 filepath / location 也必须是项目内相对路径，
        # 否则前端会把 `D:\learn_with_ai\...` 这样的开发机路径显示给评委。
        deep_dict = deep_result.to_dict()
        _relativize_paths(deep_dict, _to_rel)
        result.deep_analysis = deep_dict

        # 创建问题（P0-10：题目里的代码位置必须是相对路径）
        training_dict = training.to_dict()
        # P0-10：题目的 evidence 里也不能出现开发机绝对路径
        _relativize_paths(training_dict, _to_rel)
        result.training = training_dict
        # P0-11：答案表单独保存，供后端判题使用；不会出现在 to_dict() 的契约里
        result.training_answer_key = training.answer_key()

        # ---- Sprint 1：业务图谱（五步流水线 + 复杂度 + 流程场景 + 教师种子合并）----
        # 放在最后，因为它依赖单元/调用图/状态/流程的全部结果。
        # 用 try 包住：业务图谱是"增量能力"，它失败不应该让整条分析链路报错
        # （宁可降级为"本次没有业务图谱"，也不要把演示搞崩）。
        try:
            from ..business_graph import build_business_graph

            business_graph = build_business_graph(project_info, deep_result)
            _relativize_paths(business_graph, _to_rel)
            result.business_graph = business_graph
        except Exception as exc:  # pragma: no cover - 兜底
            result.business_graph = {
                "contract_version": CONTRACT_VERSION,
                "project_id": project_info.project_name,
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
                "caveats": ["业务图谱生成失败，本次分析结果不含业务图谱。"],
            }

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

    def _convert_deep_flows(self, flows: list, call_graph=None) -> list:
        """将 BusinessFlow 转换为 CoreFlow 格式，保持向后兼容。

        P0-10：每个步骤额外带上 ``file``（调用图里的节点文件路径），
        这样"流程推演"题也能给出可点击的代码证据。
        """
        from .module_analyzer import CoreFlow

        node_file = {}
        if call_graph is not None:
            for node_id, node in (getattr(call_graph, "nodes", {}) or {}).items():
                node_file[node_id] = getattr(node, "filepath", "") or ""

        core_flows = []
        for flow in flows:
            steps = []
            for step in flow.steps:
                steps.append({
                    "step_id": step.step_id,
                    "node_id": step.node_id,
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
                    "file": node_file.get(step.node_id, ""),
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
