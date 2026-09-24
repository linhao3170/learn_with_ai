"""
事实表导出器 —— 将代码分析结果转化为可审核的结构化事实清单。

核心思想：
  把"AI 的判断"变成"代码的事实陈列"。每条事实都有来源、有位置、有可信度，
  教师可以逐条审核，确认过的事实可以直接作为出题和评测的依据。

使用方式：
  # 方式一：直接分析项目目录
  python scripts/export_fact_table.py --project sample_projects/lab_safety_assistant

  # 方式二：从已有的分析 JSON 导入
  #   （deep_analysis.json 是规范 DeepAnalysisResult 形状，由 scripts/generate_deep_data.py 生成；
  #     scripts/test_deep_analyzer.py 的调试形状写在 deep_analysis_test.json，字段名不同，不要混用）
  python scripts/export_fact_table.py --input validation/results/deep_analysis.json

  # 指定输出路径和格式
  python scripts/export_fact_table.py --project path/to/project --output validation/fact_table.csv --format csv

输出字段：
  fact_id     事实编号 F0001, F0002 ...
  category    大类：调用链 / 状态变更 / 守卫条件 / 异常处理 / 设计特征 / 业务流程 / 模块架构 / 设计模式
  type        细类，如"调用链-跨模块"、"状态变更-属性写入"
  description 事实描述（中文，简洁明确）
  location    代码位置：文件路径:行号（可多条）
  confidence  可信度：verified（结构确定性结论）/ inferred（语义推断结论）
  evidence    证据说明：分析来源或具体依据
  source      数据来源：call_graph / state_tracker / key_implementation / flow_extractor / architecture / pattern_detector
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 修复 Windows 控制台中文/Unicode 编码问题
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ============================================================
# 数据结构
# ============================================================

@dataclass
class Fact:
    """一条可审核的事实。"""
    fact_id: str
    category: str       # 大类
    type: str           # 细类
    description: str    # 描述
    location: str       # 文件:行号
    confidence: str     # verified / inferred
    evidence: str       # 证据/依据
    source: str         # 数据来源模块

    def to_row(self) -> List[str]:
        return [
            self.fact_id,
            self.category,
            self.type,
            self.description,
            self.location,
            self.confidence,
            self.evidence,
            self.source,
        ]

    @staticmethod
    def headers() -> List[str]:
        return [
            "fact_id",
            "category",
            "type",
            "description",
            "location",
            "confidence",
            "evidence",
            "source",
        ]


# ============================================================
# 事实提取器
# ============================================================

class FactExtractor:
    """
    从分析结果中提取结构化事实。

    所有事实按可信度分为两级：
      - verified: 由 AST 直接解析得到，确定性 100%
        （调用关系、行号、状态读写、守卫条件、异常抛出、循环分支计数等）
      - inferred: 基于命名启发式或模式匹配推断，需人工确认
        （设计模式、算法类型、模块职责命名等）
    """

    def __init__(self, analysis: dict):
        self.analysis = analysis
        self.facts: List[Fact] = []
        self._counter = 0

    # ---- 工具方法 ----

    def _next_id(self) -> str:
        self._counter += 1
        return f"F{self._counter:04d}"

    def _add(self, **kwargs):
        self.facts.append(Fact(fact_id=self._next_id(), **kwargs))

    @staticmethod
    def _short_path(filepath: str) -> str:
        """把绝对路径转成相对路径，缩短显示。"""
        if not filepath:
            return ""
        basename = os.path.basename(filepath)
        parent = os.path.basename(os.path.dirname(filepath))
        if parent:
            return f"{parent}/{basename}"
        return basename

    @staticmethod
    def _clean_state_mutation_label(label: str) -> str:
        """清理状态变更描述中的 _inferred_ 推断标记，修正属性计数。"""
        import re
        # 找到最后一个冒号（属性列表前面）
        last_colon = label.rfind(":")
        if last_colon < 0:
            return label

        head = label[:last_colon]
        attrs_part = label[last_colon + 1:]

        # 提取所有属性名（含点号的复合属性）
        all_attrs = re.findall(r"[\w][\w\.]*", attrs_part)
        # 过滤掉 _inferred_ 相关的推断标记
        clean = [a for a in all_attrs if "_inferred_" not in a]
        n = len(clean)

        # 修正 head 里的数量和单复数
        attr_word = "attribute" if n == 1 else "attributes"
        new_head = re.sub(r"\d+\s+state\s+attribute\(s\)?", f"{n} state {attr_word}", head)
        new_head = re.sub(r"modifies\s+\d+", f"modifies {n}", new_head)

        return f"{new_head}: {', '.join(clean[:5])}"

    # ---- 1. 调用链事实 ----

    def extract_call_graph(self):
        """从调用图提取调用关系事实。"""
        cg = self.analysis.get("call_graph", {})
        nodes = cg.get("nodes", {})

        if not nodes:
            return

        # 收集所有边（去重：同一条 from->to 只记一次，取第一个行号）
        seen = set()
        edges_info = []

        for nid, node in nodes.items():
            for call in node.get("calls", []):
                key = (nid, call["to"])
                if key in seen:
                    continue
                seen.add(key)
                edges_info.append({
                    "from": nid,
                    "to": call["to"],
                    "type": call.get("type", "direct"),
                    "line": call.get("line", 0),
                    "from_filepath": node.get("filepath", ""),
                })

        # 按模块分组、按行号排序
        edges_info.sort(key=lambda e: (e["from"], e["line"]))

        for edge in edges_info:
            from_id = edge["from"]
            to_id = edge["to"]
            call_type = edge["type"]
            line_no = edge["line"]
            filepath = edge["from_filepath"]

            from_node = nodes.get(from_id, {})
            to_node = nodes.get(to_id, {})

            from_label = self._format_node_label(from_id, from_node)
            to_label = self._format_node_label(to_id, to_node)

            # 判断是否跨模块
            from_mod = from_id.split(":")[0]
            to_mod = to_id.split(":")[0]
            is_cross_module = from_mod != to_mod

            # 调用类型分类
            if call_type == "composite_attr":
                type_label = "跨组件调用"
            elif call_type == "self_method":
                type_label = "同类方法调用"
            elif call_type == "imported":
                type_label = "导入函数调用"
            else:
                type_label = "直接调用"

            category = "调用链-跨模块" if is_cross_module else "调用链-模块内"
            cross_note = "（跨模块）" if is_cross_module else ""

            loc = f"{self._short_path(filepath)}:{line_no}" if line_no else self._short_path(filepath)

            self._add(
                category="调用链",
                type=category,
                description=f"{from_label} 调用 {to_label}{cross_note}",
                location=loc,
                confidence="verified",
                evidence=f"调用类型: {call_type}",
                source="call_graph",
            )

        # 入口点事实
        for ep_id in cg.get("entry_points", []):
            ep_node = nodes.get(ep_id, {})
            if not ep_node:
                continue
            label = self._format_node_label(ep_id, ep_node)
            tags = ", ".join(ep_node.get("tags", []))
            loc = f"{self._short_path(ep_node.get('filepath', ''))}:{ep_node.get('start_line', 0)}"

            self._add(
                category="调用链",
                type="入口点",
                description=f"{label} 是系统入口点",
                location=loc,
                confidence="verified",
                evidence=f"出度 {len(ep_node.get('calls', []))}，标签: {tags or '无'}",
                source="call_graph",
            )

    @staticmethod
    def _format_node_label(node_id: str, node: dict) -> str:
        """把 node_id 格式化成易读的方法名。"""
        if ":" in node_id:
            _, rest = node_id.split(":", 1)
            return rest
        return node_id

    # ---- 2. 状态变更事实 ----

    def extract_state_analysis(self):
        """从状态追踪提取属性读写事实。"""
        state = self.analysis.get("state_analysis", {})

        if not state:
            return

        for class_key, cs in state.items():
            mod = cs.get("module", "")
            cls = cs.get("class", "")
            filepath = cs.get("filepath", "")
            short_path = self._short_path(filepath)

            class_label = f"{cls}"

            # 状态属性清单
            state_attrs = cs.get("state_attributes", [])
            if state_attrs:
                self._add(
                    category="状态变更",
                    type="状态属性",
                    description=f"{class_label} 拥有 {len(state_attrs)} 个状态属性: {', '.join(state_attrs[:6])}",
                    location=f"{short_path}",
                    confidence="verified",
                    evidence="从 __init__ 中提取的 self.xxx 赋值",
                    source="state_tracker",
                )

            # 字典型属性
            dict_attrs = cs.get("dict_like_attrs", [])
            if dict_attrs:
                self._add(
                    category="状态变更",
                    type="集合属性",
                    description=f"{class_label} 有 {len(dict_attrs)} 个集合型属性: {', '.join(dict_attrs)}",
                    location=f"{short_path}",
                    confidence="verified",
                    evidence="初始化为 dict/list/set 的属性",
                    source="state_tracker",
                )

            # 类常量
            constants = cs.get("class_constants", [])
            if constants:
                self._add(
                    category="状态变更",
                    type="类常量",
                    description=f"{class_label} 定义了 {len(constants)} 个常量: {', '.join(constants[:6])}",
                    location=f"{short_path}",
                    confidence="verified",
                    evidence="UPPER_CASE 命名的类级变量",
                    source="state_tracker",
                )

            # 每个方法的写操作
            method_writes = cs.get("method_writes", {})
            method_dict_writes = cs.get("method_dict_writes", {})

            # 收集所有有写操作的方法
            all_writer_methods = sorted(
                set(list(method_writes.keys()) + list(method_dict_writes.keys()))
            )

            for method_name in all_writer_methods:
                writes = method_writes.get(method_name, [])
                dict_writes = method_dict_writes.get(method_name, [])
                all_writes = sorted(set(writes + dict_writes))

                if not all_writes:
                    continue

                # 过滤掉 __inferred__ 这种推断标记，只显示真实属性名
                display_writes = [w for w in all_writes if not w.endswith("._inferred_")]
                if not display_writes:
                    display_writes = all_writes

                # 查找行号（从调用图节点里取）
                method_line = self._find_method_line(mod, cls, method_name)
                loc = f"{short_path}:{method_line}" if method_line else short_path

                self._add(
                    category="状态变更",
                    type="属性写入",
                    description=f"{class_label}.{method_name}() 修改 {len(display_writes)} 个属性: {', '.join(display_writes[:5])}",
                    location=loc,
                    confidence="verified",
                    evidence="AST 静态分析: self.attr = / self.attr.append() 等模式",
                    source="state_tracker",
                )

            # 纯查询方法（只读不写）
            method_reads = cs.get("method_reads", {})
            pure_query = []
            for method_name, reads in method_reads.items():
                if method_name.startswith("_") and method_name != "__init__":
                    continue
                writes = method_writes.get(method_name, [])
                dict_w = method_dict_writes.get(method_name, [])
                if reads and not writes and not dict_w:
                    pure_query.append(method_name)

            if pure_query:
                self._add(
                    category="状态变更",
                    type="查询方法",
                    description=f"{class_label} 有 {len(pure_query)} 个纯查询方法: {', '.join(pure_query[:5])}",
                    location=f"{short_path}",
                    confidence="verified",
                    evidence="方法体中只读取不修改状态属性",
                    source="state_tracker",
                )

    def _find_method_line(self, module: str, cls: Optional[str], method: str) -> int:
        """从调用图节点里查找方法的起始行号。"""
        cg = self.analysis.get("call_graph", {})
        nodes = cg.get("nodes", {})

        if cls:
            nid = f"{module}:{cls}.{method}"
        else:
            nid = f"{module}:{method}"

        node = nodes.get(nid)
        if node:
            return node.get("start_line", 0)
        return 0

    # ---- 3. 关键实现事实 ----

    def extract_key_implementations(self):
        """从关键实现分析提取设计特征、守卫条件、异常处理等事实。"""
        ki = self.analysis.get("key_implementations", {})
        impls = ki.get("implementations", [])

        if not impls:
            return

        for impl in impls:
            method_label = f"{impl.get('class', '')}.{impl.get('method', '')}"
            filepath = impl.get("filepath", "")
            short_path = self._short_path(filepath)
            start_line = impl.get("start_line", 0)
            end_line = impl.get("end_line", 0)
            loc = f"{short_path}:{start_line}-{end_line}"

            # 重要性评分
            score = impl.get("importance_score", 0)
            reasons = impl.get("importance_reasons", [])

            self._add(
                category="关键实现",
                type="核心方法",
                description=f"{method_label}() 是核心实现点（重要度 {score}）",
                location=loc,
                confidence="verified",
                evidence=f"入选原因: {'; '.join(reasons[:3])}",
                source="key_implementation",
            )

            # 设计特征（每条一个事实）
            for char in impl.get("design_characteristics", []):
                char_label = char.get("label", "")
                char_evidence = char.get("evidence", "")
                char_conf = char.get("confidence", "verified")
                char_cat = char.get("category", "")

                # 清理 state_mutation 类型中的 _inferred_ 推断标记
                if char_cat == "state_mutation":
                    char_label = self._clean_state_mutation_label(char_label)

                type_map = {
                    "guard_clause": "守卫条件",
                    "error_handling": "异常处理",
                    "state_mutation": "状态变更",
                    "algorithmic": "算法模式",
                    "recursion": "递归",
                    "orchestration": "编排调用",
                    "design_pattern": "设计模式",
                }
                type_label = type_map.get(char_cat, "设计特征")

                # 守卫条件和异常处理的行号更精确
                if char_cat in ("guard_clause", "error_handling") and char_evidence.startswith("lines "):
                    lines_str = char_evidence.replace("lines ", "")
                    char_loc = f"{short_path}: lines {lines_str}"
                else:
                    char_loc = loc

                self._add(
                    category="关键实现",
                    type=type_label,
                    description=f"{method_label}: {char_label}",
                    location=char_loc,
                    confidence=char_conf,
                    evidence=char_evidence,
                    source="key_implementation",
                )

            # 守卫条件明细
            for i, gc in enumerate(impl.get("guard_clauses", [])):
                guard_line = self._find_evidence_line(impl, "guard_clause", i)
                gc_loc = f"{short_path}:{guard_line}" if guard_line else loc

                self._add(
                    category="关键实现",
                    type="守卫子句",
                    description=f"{method_label}: {gc}",
                    location=gc_loc,
                    confidence="verified",
                    evidence="从 AST 检测到的前置检查 + 提前退出模式",
                    source="key_implementation",
                )

            # 异常抛出明细
            for i, err in enumerate(impl.get("error_handling", [])):
                err_line = self._find_evidence_line(impl, "error_handling", i)
                err_loc = f"{short_path}:{err_line}" if err_line else loc

                self._add(
                    category="关键实现",
                    type="异常抛出",
                    description=f"{method_label}: 抛出 {err}",
                    location=err_loc,
                    confidence="verified",
                    evidence="从 AST 检测到的 raise 语句",
                    source="key_implementation",
                )

            # 算法提示
            algo = impl.get("algorithm_hints", {})
            if algo:
                algo_detected = algo.get("detected", "")
                algo_conf = algo.get("confidence", "inferred")
                algo_reason = algo.get("reason", "")

                self._add(
                    category="关键实现",
                    type="算法特征",
                    description=f"{method_label}: {algo_detected}",
                    location=loc,
                    confidence=algo_conf,
                    evidence=algo_reason,
                    source="key_implementation",
                )

            # 复杂度指标
            complexity = impl.get("complexity", 0)
            loop_count = impl.get("loop_count", 0)
            branch_count = impl.get("branch_count", 0)

            self._add(
                category="关键实现",
                type="复杂度",
                description=f"{method_label}: 圈复杂度 {complexity}（循环 {loop_count}，分支 {branch_count}）",
                location=loc,
                confidence="verified",
                evidence="从 AST 直接计数：if/try 为分支，for/while 为循环",
                source="key_implementation",
            )

    @staticmethod
    def _find_evidence_line(impl: dict, ev_type: str, index: int) -> int:
        """从 evidence_refs 里找第 index 个指定类型的证据行号。"""
        refs = impl.get("evidence_refs", [])
        count = 0
        for ref in refs:
            if ref.get("type") == ev_type:
                if count == index:
                    return ref.get("line", 0)
                count += 1
        return 0

    # ---- 4. 业务流程事实 ----

    def extract_business_flows(self):
        """从业务流程提取流程步骤事实。"""
        flows = self.analysis.get("business_flows", [])

        if not flows:
            return

        for flow in flows:
            flow_name = flow.get("name", "")
            flow_desc = flow.get("description", "")
            modules = flow.get("modules_involved", [])
            cross_count = flow.get("cross_module_count", 0)
            importance = flow.get("business_importance", 0)
            steps = flow.get("steps", [])

            # 流程总览事实
            self._add(
                category="业务流程",
                type="流程总览",
                description=(
                    f"流程 '{flow_name}': 涉及 {len(modules)} 个模块，"
                    f"{len(steps)} 个步骤，{cross_count} 次跨模块调用"
                ),
                location=", ".join(modules),
                confidence="verified",
                evidence=f"入口: {flow.get('entry_node', '')}，业务重要度: {importance}",
                source="flow_extractor",
            )

            # 每个步骤一条事实
            for step in steps:
                step_method = step.get("method", "")
                step_class = step.get("class", "")
                step_module = step.get("module", "")
                step_line = step.get("line", 0)
                step_depth = step.get("depth", 0)
                is_cross = step.get("is_module_boundary", False)
                is_state = step.get("is_state_change", False)
                is_val = step.get("is_validation", False)

                label = f"{step_class}.{step_method}()" if step_class else f"{step_method}()"

                tags = []
                if is_cross:
                    tags.append("跨模块")
                if is_state:
                    tags.append("状态变更")
                if is_val:
                    tags.append("校验点")
                tag_str = f"（{', '.join(tags)}）" if tags else ""

                # 找文件路径
                cg = self.analysis.get("call_graph", {})
                nodes = cg.get("nodes", {})
                node_id = step.get("node_id", "")
                node = nodes.get(node_id, {})
                filepath = node.get("filepath", "")
                short_path = self._short_path(filepath)

                loc = f"{short_path}:{step_line}" if step_line and short_path else step_module

                self._add(
                    category="业务流程",
                    type="流程步骤",
                    description=f"{flow_name} · 步骤 {step_depth} 层: {label}{tag_str}",
                    location=loc,
                    confidence="verified",
                    evidence=f"调用类型: {step.get('call_type', '')}",
                    source="flow_extractor",
                )

    # ---- 5. 模块架构事实 ----

    def extract_architecture(self):
        """从模块架构提取分层、职责事实。"""
        arch = self.analysis.get("architecture", {})
        nodes = arch.get("nodes", {})
        edges = arch.get("edges", [])
        layers = arch.get("layers", [])

        if not nodes:
            # 试试 dependency_strength
            dep = self.analysis.get("dependency_strength", {})
            dep_modules = dep.get("modules", {})
            if dep_modules:
                self._extract_from_dependency_strength(dep)
            return

        # 分层事实
        if layers:
            layer_names = {
                "orchestration": "编排层",
                "business": "业务层",
                "support": "支撑层",
                "infrastructure": "基础设施层",
            }
            layer_label = " / ".join([layer_names.get(l, l) for l in layers])
            self._add(
                category="模块架构",
                type="分层架构",
                description=f"系统采用 {len(layers)} 层架构: {layer_label}",
                location="全局",
                confidence="verified",
                evidence="基于模块依赖方向和角色自动分层",
                source="architecture",
            )

        # 每个模块一条事实
        for mod_name, mod_node in nodes.items():
            layer = mod_node.get("layer", "")
            role = mod_node.get("role", "")
            method_count = mod_node.get("method_count", 0)
            resps = mod_node.get("responsibilities", [])

            layer_cn = {
                "orchestration": "编排层",
                "business": "业务层",
                "support": "支撑层",
                "infrastructure": "基础设施层",
            }.get(layer, layer)

            role_cn = {
                "orchestrator": "编排器",
                "core": "核心模块",
                "intermediate": "中间模块",
                "peripheral": "外围模块",
            }.get(role, role)

            resp_str = ", ".join(resps) if resps else "未命名"

            self._add(
                category="模块架构",
                type="模块分层",
                description=f"模块 {mod_name}: 位于{layer_cn}，角色为{role_cn}，{method_count} 个方法",
                location=mod_name,
                confidence="verified",
                evidence=f"推断职责: {resp_str}",
                source="architecture",
            )

        # 模块依赖边
        for edge in edges:
            from_mod = edge.get("from", "")
            to_mod = edge.get("to", "")
            edge_type = edge.get("type", "")
            strength = edge.get("strength", 0)
            call_count = edge.get("call_count", 0)

            type_cn = {
                "orchestration": "编排依赖",
                "data_flow": "数据流依赖",
                "utility": "工具依赖",
            }.get(edge_type, edge_type)

            self._add(
                category="模块架构",
                type="模块依赖",
                description=f"{from_mod} → {to_mod}（{type_cn}，强度 {strength:.2f}，{call_count} 次调用）",
                location=f"{from_mod} → {to_mod}",
                confidence="verified",
                evidence=f"基于调用图的依赖强度计算",
                source="architecture",
            )

    def _extract_from_dependency_strength(self, dep: dict):
        """当 architecture 不可用时，从 dependency_strength 提取模块事实。"""
        modules = dep.get("modules", {})
        edges = dep.get("edges", [])

        self._add(
            category="模块架构",
            type="模块统计",
            description=f"系统包含 {len(modules)} 个模块，{len(edges)} 条模块间依赖",
            location="全局",
            confidence="verified",
            evidence="从调用图汇总",
            source="dependency_strength",
        )

        for mod_name, mod in modules.items():
            role = mod.get("role", "")
            fan_in = mod.get("fan_in", 0)
            fan_out = mod.get("fan_out", 0)
            centrality = mod.get("centrality", 0)
            nodes_count = mod.get("internal_nodes", 0)

            role_cn = {
                "orchestrator": "编排器",
                "core": "核心模块",
                "intermediate": "中间模块",
                "peripheral": "外围模块",
            }.get(role, role)

            self._add(
                category="模块架构",
                type="模块角色",
                description=(
                    f"模块 {mod_name}: {role_cn}，{nodes_count} 个内部节点，"
                    f"入度 {fan_in}，出度 {fan_out}，中心性 {centrality:.1f}"
                ),
                location=mod_name,
                confidence="verified",
                evidence="基于调用图的中心性计算",
                source="dependency_strength",
            )

        for edge in dep.get("sorted_edges", [])[:20]:  # 只取前 20 条
            from_mod = edge.get("from_module", "")
            to_mod = edge.get("to_module", "")
            strength = edge.get("strength", 0)
            call_count = edge.get("call_count", 0)

            self._add(
                category="模块架构",
                type="模块依赖",
                description=f"{from_mod} → {to_mod}（依赖强度 {strength:.2f}，{call_count} 次调用）",
                location=f"{from_mod} → {to_mod}",
                confidence="verified",
                evidence=f"唯一方法数: {edge.get('unique_methods', 0)}",
                source="dependency_strength",
            )

    # ---- 6. 设计模式事实 ----

    def extract_design_patterns(self):
        """从设计模式检测提取模式事实（inferred 级别）。"""
        dp = self.analysis.get("design_patterns", {})
        patterns = dp.get("patterns", [])

        if not patterns:
            return

        for p in patterns:
            p_name = p.get("pattern_name", "")
            p_category = p.get("category", "")
            p_confidence = p.get("confidence", "medium")
            p_target = p.get("target_name", "")
            p_target_type = p.get("target_type", "")
            p_line = p.get("target_line", 0)
            p_desc = p.get("description", "")

            target_label = f"{p_target}" if p_target_type == "class" else f"{p_target}()"

            # 找文件路径
            filepath = ""
            if p_target_type == "class":
                state = self.analysis.get("state_analysis", {})
                for key, cs in state.items():
                    if cs.get("class") == p_target:
                        filepath = cs.get("filepath", "")
                        break

            short_path = self._short_path(filepath) if filepath else ""
            loc = f"{short_path}:{p_line}" if p_line and short_path else p_target

            self._add(
                category="设计模式",
                type=p_category,
                description=f"{target_label} 疑似使用 {p_name}",
                location=loc,
                confidence="inferred",
                evidence=p_desc,
                source="pattern_detector",
            )

    # ---- 主入口 ----

    def extract_all(self) -> List[Fact]:
        """提取所有事实并返回。"""
        self.extract_architecture()
        self.extract_call_graph()
        self.extract_state_analysis()
        self.extract_business_flows()
        self.extract_key_implementations()
        self.extract_design_patterns()
        return self.facts

    def summary(self) -> dict:
        """生成事实统计摘要。"""
        cats: Dict[str, int] = {}
        confs: Dict[str, int] = {}
        sources: Dict[str, int] = {}

        for f in self.facts:
            cats[f.category] = cats.get(f.category, 0) + 1
            confs[f.confidence] = confs.get(f.confidence, 0) + 1
            sources[f.source] = sources.get(f.source, 0) + 1

        return {
            "total": len(self.facts),
            "by_category": dict(sorted(cats.items(), key=lambda x: -x[1])),
            "by_confidence": confs,
            "by_source": sources,
        }


# ============================================================
# 输出工具
# ============================================================

def save_csv(facts: List[Fact], output_path: str):
    """保存为 CSV 文件（UTF-8 BOM，Excel 可直接打开中文）。"""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(Fact.headers())
        for fact in facts:
            writer.writerow(fact.to_row())


def save_json(facts: List[Fact], analysis: dict, summary: dict, output_path: str):
    """保存为 JSON 文件（含摘要信息）。"""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    result = {
        "project": analysis.get("project", {}),
        "summary": summary,
        "facts": [
            {
                "fact_id": f.fact_id,
                "category": f.category,
                "type": f.type,
                "description": f.description,
                "location": f.location,
                "confidence": f.confidence,
                "evidence": f.evidence,
                "source": f.source,
            }
            for f in facts
        ],
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


def save_excel(facts: List[Fact], analysis: dict, summary: dict, output_path: str):
    """保存为 Excel 文件（多 sheet，含按可信度着色）。"""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
    except ImportError:
        print("⚠️  未安装 openpyxl，跳过 Excel 导出。可运行: pip install openpyxl")
        return False

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    wb = openpyxl.Workbook()

    # ---- Sheet 1: 摘要 ----
    ws = wb.active
    ws.title = "摘要"

    project = analysis.get("project", {})
    ws.append(["项目名", project.get("name", "")])
    ws.append(["文件数", project.get("files", "")])
    ws.append(["代码行数", project.get("lines", "")])
    ws.append([])
    ws.append(["事实总数", summary["total"]])
    ws.append([])
    ws.append(["按可信度统计"])
    for conf, count in summary["by_confidence"].items():
        conf_cn = "verified（确定性结论）" if conf == "verified" else "inferred（推断结论）"
        ws.append([conf_cn, count])
    ws.append([])
    ws.append(["按类别统计"])
    for cat, count in summary["by_category"].items():
        ws.append([cat, count])
    ws.append([])
    ws.append(["按来源模块统计"])
    for src, count in summary["by_source"].items():
        ws.append([src, count])

    # 加粗标题行
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row):
        if row[0].value and row[0].value in (
            "项目名", "事实总数", "按可信度统计", "按类别统计", "按来源模块统计"
        ):
            row[0].font = Font(bold=True)

    # ---- Sheet 2: 全部事实 ----
    ws2 = wb.create_sheet("事实清单")
    ws2.append(Fact.headers())

    # 样式
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    verified_fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
    inferred_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")

    for cell in ws2[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(vertical="center")

    for fact in facts:
        row_num = ws2.max_row + 1
        ws2.append(fact.to_row())
        fill = verified_fill if fact.confidence == "verified" else inferred_fill
        for col in range(1, len(Fact.headers()) + 1):
            ws2.cell(row=row_num, column=col).fill = fill

    # 调整列宽
    col_widths = [10, 12, 16, 50, 30, 12, 35, 18]
    for i, w in enumerate(col_widths, 1):
        ws2.column_dimensions[get_column_letter(i)].width = w

    ws2.freeze_panes = "A2"
    ws2.auto_filter.ref = ws2.dimensions

    # ---- Sheet 3-N: 分类视图 ----
    categories = sorted(set(f.category for f in facts))
    for cat in categories:
        cat_facts = [f for f in facts if f.category == cat]
        sheet_name = cat[:31]  # Excel sheet 名最长 31 字符
        ws_cat = wb.create_sheet(sheet_name)
        ws_cat.append(Fact.headers())

        for cell in ws_cat[1]:
            cell.fill = header_fill
            cell.font = header_font

        for fact in cat_facts:
            row_num = ws_cat.max_row + 1
            ws_cat.append(fact.to_row())
            fill = verified_fill if fact.confidence == "verified" else inferred_fill
            for col in range(1, len(Fact.headers()) + 1):
                ws_cat.cell(row=row_num, column=col).fill = fill

        for i, w in enumerate(col_widths, 1):
            ws_cat.column_dimensions[get_column_letter(i)].width = w
        ws_cat.freeze_panes = "A2"

    wb.save(output_path)
    return True


# ============================================================
# 主程序
# ============================================================

def load_analysis_from_project(project_path: str) -> dict:
    """直接运行分析引擎，获取完整分析结果。"""
    from engine.project_analyzer.project_parser import ProjectParser
    from engine.deep_analyzer import DeepAnalyzer

    print(f"🔍 解析项目: {project_path}")
    parser = ProjectParser()
    project_info = parser.parse_project(project_path)
    print(f"   文件: {project_info.total_files}, 行: {project_info.total_lines}, 类: {project_info.total_classes}")

    print("⚙️  运行深层分析...")
    analyzer = DeepAnalyzer()
    result = analyzer.analyze(project_info)

    output = result.to_dict()
    output["project"] = {
        "name": project_info.project_name,
        "files": project_info.total_files,
        "lines": project_info.total_lines,
    }
    return output


def main():
    parser = argparse.ArgumentParser(description="事实表导出器 —— 从代码分析结果生成可审核的事实清单")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--project", help="项目目录路径（直接运行分析）")
    group.add_argument("--input", help="已有的分析结果 JSON 文件路径")

    parser.add_argument("--output", default="validation/fact_table.csv", help="输出文件路径")
    parser.add_argument("--format", choices=["csv", "json", "xlsx", "all"], default="csv",
                        help="输出格式（默认 csv）")
    args = parser.parse_args()

    # 1. 加载分析数据
    if args.project:
        project_path = os.path.abspath(args.project)
        if not os.path.isdir(project_path):
            print(f"❌ 项目目录不存在: {project_path}")
            sys.exit(1)
        analysis = load_analysis_from_project(project_path)
    else:
        input_path = os.path.abspath(args.input)
        if not os.path.isfile(input_path):
            print(f"❌ 输入文件不存在: {input_path}")
            sys.exit(1)
        print(f"📄 加载分析结果: {input_path}")
        with open(input_path, "r", encoding="utf-8") as f:
            analysis = json.load(f)

    project = analysis.get("project", {})
    print(f"   项目: {project.get('name', 'N/A')}, "
          f"文件: {project.get('files', 'N/A')}, "
          f"行: {project.get('lines', 'N/A')}")

    # 2. 提取事实
    print("\n📊 提取事实...")
    extractor = FactExtractor(analysis)
    facts = extractor.extract_all()
    summary = extractor.summary()

    # 3. 打印摘要
    print(f"\n{'='*60}")
    print(f"✅ 事实提取完成，共 {summary['total']} 条事实")
    print(f"{'='*60}")

    print(f"\n📈 可信度分布:")
    for conf, count in summary["by_confidence"].items():
        bar = "█" * (count // 2)
        conf_label = "verified（确定性）" if conf == "verified" else "inferred（推断）"
        print(f"   {conf_label:<20} {count:>4} 条  {bar}")

    print(f"\n📂 类别分布:")
    for cat, count in summary["by_category"].items():
        bar = "█" * (count // 2)
        print(f"   {cat:<14} {count:>4} 条  {bar}")

    # 4. 保存输出
    output_base = os.path.splitext(args.output)[0]
    fmt = args.format

    print(f"\n💾 保存结果...")

    if fmt in ("csv", "all"):
        csv_path = f"{output_base}.csv"
        save_csv(facts, csv_path)
        print(f"   CSV:  {csv_path}")

    if fmt in ("json", "all"):
        json_path = f"{output_base}.json"
        save_json(facts, analysis, summary, json_path)
        print(f"   JSON: {json_path}")

    if fmt in ("xlsx", "all"):
        xlsx_path = f"{output_base}.xlsx"
        ok = save_excel(facts, analysis, summary, xlsx_path)
        if ok:
            print(f"   Excel: {xlsx_path}")

    print(f"\n🎯 完成！{summary['total']} 条事实已导出。")
    print(f"   其中 verified: {summary['by_confidence'].get('verified', 0)} 条（可直接用作出题依据）")
    print(f"   inferred: {summary['by_confidence'].get('inferred', 0)} 条（需教师审核确认）")


if __name__ == "__main__":
    main()
