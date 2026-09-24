"""
模块分析器

从项目解析结果中识别模块边界、推断模块职责、
分析模块间依赖关系、提取核心业务流程。

P0-12（README5 §3.2）
---------------------
所有业务词汇（模块类型关键词、中文模块名、流程名、步骤标签、方法动词类别）
**已全部外置**到 ``engine/lexicon/*.json``。

本文件里不再出现"预约""设备""安全检查"这类业务词 ——
出现即是 bug，可用 ``scripts/audit_hardcoding.py`` 机器化检查。
教师可以在不改代码的前提下替换词典来适配自己学校的命名习惯。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple

from .project_parser import ProjectInfo
from .. import lexicon


@dataclass
class ModuleInfo:
    """模块信息"""
    module_id: str  # 模块标识
    name: str  # 模块名称（中文/可读）
    module_type: str  # 模块类型分类
    files: List[str] = field(default_factory=list)  # 包含的文件
    classes: List[dict] = field(default_factory=list)  # 包含的类
    description: str = ""  # 职责描述
    key_responsibilities: List[str] = field(default_factory=list)  # 主要职责列表
    depends_on: List[str] = field(default_factory=list)  # 依赖的其他模块
    depended_by: List[str] = field(default_factory=list)  # 被哪些模块依赖
    core_score: float = 0.0  # 核心度评分 0-1
    method_count: int = 0  # 方法总数
    class_count: int = 0  # 类数量


@dataclass
class ModuleDependency:
    """模块依赖关系"""
    from_module: str
    to_module: str
    dependency_type: str  # import / call / inheritance
    strength: int = 1  # 依赖强度


@dataclass
class CoreFlow:
    """核心业务流程"""
    flow_id: str
    name: str
    description: str
    steps: List[dict] = field(default_factory=list)  # 步骤列表
    involved_modules: List[str] = field(default_factory=list)  # 涉及的模块


class ModuleAnalyzer:
    """模块分析器"""

    def __init__(self):
        pass

    def analyze(self, project_info: ProjectInfo) -> Tuple[List[ModuleInfo], List[ModuleDependency], List[CoreFlow]]:
        """
        分析项目的模块结构

        Returns:
            (modules, dependencies, core_flows)
        """
        # 步骤 1：识别模块（按文件/类聚类）
        modules = self._identify_modules(project_info)

        # 步骤 2：推断模块职责
        self._infer_responsibilities(modules, project_info)

        # 步骤 3：分析模块依赖
        dependencies = self._analyze_dependencies(modules, project_info)

        # 步骤 4：计算核心度
        self._calculate_core_score(modules, dependencies)

        # 步骤 5：提取核心业务流程
        core_flows = self._extract_core_flows(modules, project_info)

        return modules, dependencies, core_flows

    def _identify_modules(self, project: ProjectInfo) -> List[ModuleInfo]:
        """
        识别项目模块

        策略：每个包含类的 Python 文件视为一个模块
        （简单项目的模块粒度，复杂项目需要更高级的聚类）
        """
        modules = []
        seen = set()

        all_classes = project.get_all_classes()

        for cls in all_classes:
            module_id = cls["module_name"]

            # 跳过纯聚合类（方法数 < 4 且主要做 import/组装，没有实质业务逻辑）
            # 比如 App 主入口类，它只是把模块组装起来，本身不是业务模块
            method_count = cls["method_count"]
            is_aggregator = (
                method_count <= 3
                and ("app" in module_id.lower() or "main" in module_id.lower())
            )
            if is_aggregator and len(all_classes) > 3:
                # 项目有多个模块时，聚合类不算独立模块
                continue

            if module_id in seen:
                # 已存在的模块，追加类
                for m in modules:
                    if m.module_id == module_id:
                        m.classes.append(cls)
                        m.class_count += 1
                        m.method_count += cls["method_count"]
                        if cls["filepath"] not in m.files:
                            m.files.append(cls["filepath"])
                        break
                continue

            seen.add(module_id)

            # 从文件名推断模块类型
            module_type = self._detect_module_type(module_id, cls.get("docstring") or "")
            module_name = self._generate_module_name(module_id, module_type)

            mod = ModuleInfo(
                module_id=module_id,
                name=module_name,
                module_type=module_type,
                files=[cls["filepath"]],
                classes=[cls],
                class_count=1,
                method_count=cls["method_count"],
            )
            modules.append(mod)

        # 如果模块太少（比如只有一个主类文件），也把纯函数文件加进去
        if len(modules) <= 1:
            for f in project.files:
                if f.module_name not in seen and f.parsed.functions:
                    modules.append(ModuleInfo(
                        module_id=f.module_name,
                        name=f.module_name + " 模块",
                        module_type="utils",
                        files=[f.filepath],
                        class_count=0,
                        method_count=len(f.parsed.functions),
                    ))

        return modules

    def _detect_module_type(self, module_name: str, docstring: str) -> str:
        """根据模块名和文档推断模块类型（词表来自 ``lexicon/module_types.json``）。"""
        name_lower = module_name.lower()
        doc_lower = docstring.lower()

        scores: Dict[str, int] = {}
        for mtype, keywords in lexicon.module_types().items():
            score = 0
            for kw in keywords:
                kw_lower = str(kw).lower()
                if kw_lower in name_lower:
                    score += 3  # 名字里有，权重高
                if kw_lower in doc_lower:
                    score += 2  # 文档里有
            scores[mtype] = score

        # 取最高分。
        # 注意：并列时取**词典里先出现的类型**（JSON 对象的键顺序是稳定的，
        # 因此结果仍然可复现）。这里**不能**按类型名字典序排序 ——
        # 那会让并列时 "management" 压过 "reservation"，改变既有行为。
        if not scores:
            return lexicon.module_type_default()
        best_type = max(scores, key=scores.get)
        if scores[best_type] > 0:
            return best_type

        return lexicon.module_type_default()

    def _generate_module_name(self, module_id: str, module_type: str) -> str:
        """生成易读的模块名称（映射来自 ``lexicon/module_types.json``）。

        ⚠️ 这份名字的置信度是 ``inferred``，必须可被教师改写。
        README5 Sprint 1 起由业务图谱引擎按"目录 + 类名 + 中文 docstring"生成，
        这里的映射表只作为兜底。
        """
        type_names = lexicon.module_type_names()
        if module_type in type_names:
            return type_names[module_type]

        # 从文件名生成
        base_name = module_id.split(".")[-1]
        base_name = base_name.replace("_", " ").title()
        return base_name + " Module"

    def _infer_responsibilities(self, modules: List[ModuleInfo], project: ProjectInfo):
        """推断每个模块的职责"""
        for mod in modules:
            responsibilities = []

            # 从类的 docstring 提取
            for cls in mod.classes:
                if cls.get("docstring"):
                    # 取第一行作为职责描述
                    first_line = cls["docstring"].strip().split("\n")[0]
                    if first_line and len(first_line) < 100:
                        responsibilities.append(first_line)

            # 从方法名推断
            method_names = []
            for cls in mod.classes:
                for m in cls.get("methods", []):
                    if not m.name.startswith("_"):
                        method_names.append(m.name)

            # 聚合方法类别
            categories = self._categorize_methods(method_names)
            for cat in categories:
                if cat not in responsibilities:
                    responsibilities.append(cat)

            mod.key_responsibilities = responsibilities[:6]  # 最多 6 条

            # 生成一句话描述
            if responsibilities:
                mod.description = responsibilities[0]
            else:
                mod.description = f"{mod.name}，提供相关业务功能"

    def _categorize_methods(self, method_names: List[str]) -> List[str]:
        """从方法名聚合出功能类别（规则来自 ``lexicon/method_verbs.json``）。

        ⚠️ README4 §3.2：这些是**内部信号**，不是"模块职责"。
        CRUD 那几个标签（``internal_only: true``）在展示职责时必须过滤掉，
        由 ``training_generator._business_text()`` 负责过滤。
        """
        categories: List[str] = []
        lowered = [m.lower() for m in method_names]

        for group in lexicon.method_verbs():
            patterns = group.get("patterns") or []
            label = group.get("cn", "")
            if not label or not patterns:
                continue
            if any(re.search(pattern, name) for pattern in patterns for name in lowered):
                if label not in categories:
                    categories.append(label)

        return categories

    def _analyze_dependencies(self, modules: List[ModuleInfo], project: ProjectInfo) -> List[ModuleDependency]:
        """分析模块间的依赖关系"""
        dependencies = []

        # 构建模块名 -> ModuleInfo 的映射
        mod_map = {m.module_id: m for m in modules}

        # 基于 import 分析依赖
        for file_info in project.files:
            current_module = file_info.module_name
            if current_module not in mod_map:
                continue

            for imp in file_info.parsed.imports:
                # 检查是否导入了项目内的其他模块
                imp_module = imp.module

                # 匹配其他模块
                for mod_id in mod_map:
                    if mod_id == current_module:
                        continue
                    # 简单匹配：import 的模块名是模块 id 的一部分，或反过来
                    if imp_module == mod_id or imp_module.endswith("." + mod_id) or mod_id.endswith("." + imp_module):
                        dep = ModuleDependency(
                            from_module=current_module,
                            to_module=mod_id,
                            dependency_type="import",
                            strength=len(imp.names) or 1,
                        )
                        dependencies.append(dep)

                        # 更新模块的依赖列表
                        if mod_id not in mod_map[current_module].depends_on:
                            mod_map[current_module].depends_on.append(mod_id)
                        if current_module not in mod_map[mod_id].depended_by:
                            mod_map[mod_id].depended_by.append(current_module)

        # 去重
        seen = set()
        unique_deps = []
        for dep in dependencies:
            key = (dep.from_module, dep.to_module, dep.dependency_type)
            if key not in seen:
                seen.add(key)
                unique_deps.append(dep)

        return unique_deps

    def _calculate_core_score(self, modules: List[ModuleInfo], dependencies: List[ModuleDependency]):
        """计算每个模块的核心度"""
        if not modules:
            return

        max_methods = max((m.method_count for m in modules), default=1)

        for mod in modules:
            score = 0.0

            # 因素 1：方法数量（代码量）
            size_score = min(mod.method_count / max_methods, 1.0)
            score += size_score * 0.3

            # 因素 2：被依赖数量（被越多模块依赖越核心）
            dep_score = min(len(mod.depended_by) / max(len(modules) - 1, 1), 1.0)
            score += dep_score * 0.3

            # 因素 3：关键词匹配（业务核心词，词表来自 lexicon/core_keywords.json）
            keyword_score = 0.0
            name_text = mod.module_id.lower() + " " + mod.description.lower()
            for kw in lexicon.core_keywords():
                if str(kw).lower() in name_text:
                    keyword_score += 0.2
            keyword_score = min(keyword_score, 1.0)
            score += keyword_score * 0.3

            # 因素 4：是否包含状态流转/流程（特征词同样来自词典）
            flow_markers = lexicon.load_lexicon("core_keywords").get(
                "flow_markers", []
            ) or ["流程", "审批", "状态"]
            has_flow = any(
                any(marker in r for marker in flow_markers)
                for r in mod.key_responsibilities
            )
            if has_flow:
                score += 0.1

            mod.core_score = round(min(score, 1.0), 2)

        # 按核心度排序
        modules.sort(key=lambda m: m.core_score, reverse=True)

    def _extract_core_flows(self, modules: List[ModuleInfo], project: ProjectInfo) -> List[CoreFlow]:
        """提取核心业务流程"""
        flows = []

        # 基于核心模块推断主要业务流程
        core_modules = [m for m in modules if m.core_score >= 0.4]

        for i, mod in enumerate(core_modules[:3]):
            flow = CoreFlow(
                flow_id=f"flow_{i+1}",
                name=self._generate_flow_name(mod),
                description=f"核心业务流程：{mod.description}",
                involved_modules=[mod.module_id],
            )

            # 从方法名推导流程步骤
            steps = self._derive_flow_steps(mod)
            flow.steps = steps

            flows.append(flow)

        return flows

    def _generate_flow_name(self, module: ModuleInfo) -> str:
        """生成流程名称（映射来自 ``lexicon/flow_names.json``，inferred 级别、教师可改）。"""
        names = lexicon.flow_names()
        if module.module_type in names:
            return names[module.module_type]
        template = lexicon.load_lexicon("flow_names").get(
            "fallback_template", "{module_name}核心流程"
        )
        return template.replace("{module_name}", module.name)

    def _derive_flow_steps(self, module: ModuleInfo) -> List[dict]:
        """从方法名推导流程步骤（规则来自 ``lexicon/flow_steps.json``）。"""
        steps: List[dict] = []

        step_order = 0
        for rule in lexicon.flow_step_labels():
            pattern = rule.get("pattern")
            label = rule.get("label", "")
            action_type = rule.get("action_type", "")
            if not pattern:
                continue
            for cls in module.classes:
                for method in cls.get("methods", []):
                    if re.search(pattern, method.name.lower()):
                        step_order += 1
                        steps.append({
                            "order": step_order,
                            "name": f"{label}：{method.name}",
                            "action_type": action_type,
                            "method": method.name,
                            "line": method.start_line,
                        })
                        break  # 每个类别只取第一个代表性方法
                else:
                    continue
                break  # 找到就跳出类循环

        # 如果步骤太少，补充通用步骤（模板来自词典）
        if not steps:
            fallback = lexicon.load_lexicon("flow_steps").get("fallback_steps") or []
            if fallback:
                steps = [
                    {
                        "order": item.get("order", index + 1),
                        "name": str(item.get("name", "")).replace("{module_name}", module.name),
                        "action_type": item.get("action_type", ""),
                    }
                    for index, item in enumerate(fallback)
                ]
            else:
                steps = [
                    {"order": 1, "name": lexicon.flow_step_fallback().replace("{module_name}", module.name), "action_type": "process"},
                    {"order": 2, "name": lexicon.flow_final_step(), "action_type": "return"},
                ]

        return steps
