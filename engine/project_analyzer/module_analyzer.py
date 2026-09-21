"""
模块分析器

从项目解析结果中识别模块边界、推断模块职责、
分析模块间依赖关系、提取核心业务流程。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple

from .project_parser import ProjectInfo


# 模块类型关键词（用于职责推断）
MODULE_TYPE_KEYWORDS = {
    "user_management": ["user", "account", "auth", "login", "register", "权限", "用户", "账户", "认证"],
    "reservation": ["reservation", "booking", "order", "appointment", "预约", "订单", "预订"],
    "equipment": ["equipment", "device", "machine", "tool", "device", "设备", "器材", "仪器"],
    "safety_check": ["safety", "check", "inspect", "hazard", "security", "安全", "检查", "隐患"],
    "data_persistence": ["storage", "repository", "dao", "database", "db", "存储", "数据库"],
    "api": ["api", "route", "view", "controller", "handler", "接口", "路由"],
    "utils": ["util", "helper", "common", "tools", "工具", "通用"],
    "management": ["manager", "管理", "处理"],
}

# 核心度评分关键词
CORE_KEYWORDS = [
    "reservation", "booking", "order", "business", "workflow", "process",
    "预约", "订单", "流程", "业务",
]


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
        """根据模块名和文档推断模块类型"""
        name_lower = module_name.lower()
        doc_lower = docstring.lower()

        scores = {}
        for mtype, keywords in MODULE_TYPE_KEYWORDS.items():
            score = 0
            for kw in keywords:
                kw_lower = kw.lower()
                if kw_lower in name_lower:
                    score += 3  # 名字里有，权重高
                if kw_lower in doc_lower:
                    score += 2  # 文档里有
            scores[mtype] = score

        # 取最高分
        best_type = max(scores, key=scores.get)
        if scores[best_type] > 0:
            return best_type

        return "management"  # 默认

    def _generate_module_name(self, module_id: str, module_type: str) -> str:
        """生成易读的模块名称"""
        # 中文模块名称映射
        type_names = {
            "user_management": "用户管理模块",
            "reservation": "预约管理模块",
            "equipment": "设备管理模块",
            "safety_check": "安全检查模块",
            "data_persistence": "数据持久化模块",
            "api": "接口模块",
            "utils": "工具模块",
            "management": "管理模块",
        }

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
        """从方法名聚合出功能类别"""
        categories = []

        # CRUD 类
        add_methods = [m for m in method_names if re.search(r"(add|create|insert|new|register)", m.lower())]
        delete_methods = [m for m in method_names if re.search(r"(delete|remove|drop|clear|deactivate)", m.lower())]
        update_methods = [m for m in method_names if re.search(r"(update|modify|edit|change|set)", m.lower())]
        get_methods = [m for m in method_names if re.search(r"(get|find|query|search|list|fetch|lookup)", m.lower())]

        if add_methods:
            categories.append("新增/创建操作")
        if delete_methods:
            categories.append("删除/停用操作")
        if update_methods:
            categories.append("更新/修改操作")
        if get_methods:
            categories.append("查询/获取操作")

        # 业务流程类
        if any(re.search(r"(approve|reject|cancel|confirm)", m.lower()) for m in method_names):
            categories.append("审批流程管理")
        if any(re.search(r"(check|verify|validate|detect|conflict)", m.lower()) for m in method_names):
            categories.append("校验与检测")
        if any(re.search(r"(borrow|return|lend)", m.lower()) for m in method_names):
            categories.append("借还管理")
        if any(re.search(r"(assign|allocate|assign)", m.lower()) for m in method_names):
            categories.append("资源分配")
        if any(re.search(r"(login|logout|auth|permission|role)", m.lower()) for m in method_names):
            categories.append("认证与权限")
        if any(re.search(r"(maintenance|repair|fix)", m.lower()) for m in method_names):
            categories.append("维护管理")
        if any(re.search(r"(safety|hazard|inspect|check)", m.lower()) for m in method_names):
            categories.append("安全检查")

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

            # 因素 3：关键词匹配（业务核心词）
            keyword_score = 0.0
            name_text = mod.module_id.lower() + " " + mod.description.lower()
            for kw in CORE_KEYWORDS:
                if kw in name_text:
                    keyword_score += 0.2
            keyword_score = min(keyword_score, 1.0)
            score += keyword_score * 0.3

            # 因素 4：是否包含状态流转/流程
            has_flow = any(
                "流程" in r or "审批" in r or "状态" in r
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
        """生成流程名称"""
        type_flow_names = {
            "reservation": "实验室预约流程",
            "user_management": "用户注册登录流程",
            "equipment": "设备借用归还流程",
            "safety_check": "安全检查与整改流程",
        }
        return type_flow_names.get(module.module_type, f"{module.name}核心流程")

    def _derive_flow_steps(self, module: ModuleInfo) -> List[dict]:
        """从方法名推导流程步骤"""
        steps = []

        # 按业务逻辑顺序排列方法
        flow_patterns = [
            (r"(add|create|register|new)", "创建/提交", "submit"),
            (r"(check|verify|validate|conflict)", "校验/检测", "validate"),
            (r"(approve|confirm|accept)", "审批/确认", "approve"),
            (r"(reject|refuse|deny)", "拒绝/驳回", "reject"),
            (r"(update|modify)", "更新/修改", "update"),
            (r"(cancel|withdraw)", "取消/撤回", "cancel"),
            (r"(complete|finish|close)", "完成/关闭", "complete"),
            (r"(get|list|find|query)", "查询/查看", "query"),
        ]

        step_order = 0
        for pattern, label, action_type in flow_patterns:
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

        # 如果步骤太少，补充通用步骤
        if not steps:
            steps = [
                {"order": 1, "name": f"初始化{module.name}", "action_type": "init"},
                {"order": 2, "name": "执行核心操作", "action_type": "process"},
                {"order": 3, "name": "返回结果", "action_type": "return"},
            ]

        return steps
