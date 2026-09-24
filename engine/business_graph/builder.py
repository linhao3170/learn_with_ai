"""
业务图谱构建流水线（README5 §3.1 的编排入口）

```text
build_business_graph(project_info, deep_result, project_path)
   ├─ 1) collect_units           结构单元        (verified)
   ├─ 2) build_domains           一级业务域      (inferred)
   ├─ 3) build_capabilities      二级功能点      (inferred)
   ├─ 4) bind_facts              规则/状态/异常  (verified)
   ├─ 5) build_relations/build_cards  卡片与关系
   ├─    compute_complexity      复杂度分级
   ├─    build_flows             流程与三型场景
   └─    merge_graph             教师种子合并（种子优先）
   ▼
business_graph 契约（README5 §4.2）
```

不变量（会被测试盯着）
----------------------
- ``contract_version`` / ``algorithm_version`` / ``source_hash`` 一定存在；
- 所有 ``file`` 都是**项目内相对路径**（POSIX），没有开发机绝对路径；
- 两次运行 **逐字节一致**（无随机、无 set 顺序依赖、无网络）。
"""

from __future__ import annotations

import hashlib
import os
from typing import Any, Dict, List, Optional

from . import capabilities as capabilities_mod
from . import cards as cards_mod
from . import complexity as complexity_mod
from . import domains as domains_mod
from . import facts as facts_mod
from . import paths
from . import scenarios as scenarios_mod
from . import seed_merger
from . import units as units_mod

ALGORITHM_VERSION = "bg-1.0"
CONTRACT_VERSION = "1.0"


def compute_source_hash(project_info) -> str:
    """项目源码哈希：相对路径 + 内容，聚合后的 sha256。

    用途：教师审核结果绑定源码版本；源码变了就提示重新审核（README3 §9.1）。
    """
    digest = hashlib.sha256()
    for file_info in sorted(project_info.files, key=lambda f: f.rel_path):
        digest.update(file_info.rel_path.encode("utf-8"))
        digest.update(b"\0")
        lines = getattr(file_info.parsed, "source_lines", None) or []
        digest.update("\n".join(lines).encode("utf-8"))
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()[:32]


class BusinessGraphBuilder:
    """五步流水线 + 复杂度 / 流程场景 / 种子合并。"""

    def __init__(self, max_flows: int = 6):
        self.max_flows = max_flows

    def build(
        self,
        project_info,
        deep_result=None,
        project_path: Optional[str] = None,
        seed: Optional[dict] = None,
    ) -> dict:
        """构建业务图谱，返回可直接进契约的 dict。"""
        project_path = project_path or getattr(project_info, "project_path", "")

        call_graph = getattr(deep_result, "call_graph", None)
        state_analysis = getattr(deep_result, "state_analysis", None)
        core_flows = []
        if deep_result is not None:
            for flow in (getattr(deep_result, "business_flows", []) or []):
                core_flows.append(flow)

        # ---- 第 1 步：结构单元 ----
        units = units_mod.collect_units(project_info, call_graph, state_analysis)

        # ---- 第 2 步：一级业务域 ----
        domains = domains_mod.build_domains(units, call_graph)

        # ---- 第 3 步：二级功能点 ----
        capabilities, hierarchy_by_domain = capabilities_mod.build_capabilities(units, domains)

        # ---- 第 4 步：事实绑定 ----
        facts = facts_mod.bind_facts(capabilities, units, project_info)

        # ---- 第 5 步：关系 + 卡片 ----
        relations, downstream, upstream = cards_mod.build_relations(
            capabilities, call_graph, state_analysis
        )
        domain_cards, capability_cards = cards_mod.build_cards(
            domains, capabilities, facts, units, relations, downstream, upstream, hierarchy_by_domain
        )

        # ---- 复杂度分级 ----
        complexity = complexity_mod.compute_complexity(domains, capabilities, facts, units, relations)

        # ---- 流程与三型场景 ----
        # 传一张 node_id -> 相对路径的表：deep 的 FlowStep dataclass 不带文件字段，
        # 不传的话流程步骤的 file 会全是空串，前端就没法从流程跳源码。
        node_files: Dict[str, str] = {}
        for node_id, node in (getattr(call_graph, "nodes", {}) or {}).items():
            filepath = getattr(node, "filepath", "") or ""
            if filepath:
                node_files[node_id] = filepath
        flows = scenarios_mod.build_flows(
            core_flows, capabilities, facts, domains, self.max_flows, node_files
        )

        module_cards: Dict[str, dict] = {}
        for key in sorted(domain_cards):
            module_cards[key] = domain_cards[key].to_dict()
        for key in sorted(capability_cards):
            module_cards[key] = capability_cards[key].to_dict()

        payload: Dict[str, Any] = {
            "contract_version": CONTRACT_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "project_id": getattr(project_info, "project_name", ""),
            "project_name": getattr(project_info, "project_name", ""),
            "source_hash": compute_source_hash(project_info),
            "level": complexity.level,
            "complexity": complexity.to_dict(),
            "domains": [d.to_dict() for d in sorted(domains, key=lambda d: d.domain_id)],
            "capabilities": [c.to_dict() for c in sorted(capabilities, key=lambda c: (c.parent_id, c.capability_id))],
            "module_cards": module_cards,
            "module_relations": [r.to_dict() for r in relations],
            "facts": [f.to_dict() for f in facts],
            "flows": [f.to_dict() for f in flows],
            "hierarchy": hierarchy_by_domain,
            "orchestrators": sorted([d.domain_id for d in domains if d.role == "orchestrator"]),
            "status": "needs_review",
            "caveats": [
                "domain / capability 的划分与命名是 inferred，必须经教师审核后才进学生视图；",
                "objective 与 does_not 默认是 unconfirmed，规则引擎给不出业务含义时不编；",
                "复杂度阈值未经第三方项目校准。",
            ],
        }

        # ---- 教师种子合并（种子优先） ----
        if seed is None and project_path:
            seed = seed_merger.load_seed(project_path)
        merged, report = seed_merger.merge_graph(payload, seed)
        if report.get("seed_loaded"):
            merged["status"] = "mixed"

        # ---- 路径纪律：产出方自己负责（README5 §4.2）----
        # 调用图节点里的 filepath 是绝对路径，会顺着 relations / flows / facts 漏出去。
        # 以前靠 ProjectAnalyzer 事后清理，但本包可以独立调用，所以在这里再收一道。
        rel_by_abs = {}
        for file_info in getattr(project_info, "files", []) or []:
            rel_by_abs[os.path.normpath(file_info.filepath)] = file_info.rel_path
            rel_by_abs[str(file_info.filepath).replace("\\", "/")] = file_info.rel_path
        to_rel = paths.build_relativizer(project_path or "", rel_by_abs)
        paths.relativize_paths(merged, to_rel)

        return merged


def build_business_graph(project_info, deep_result=None, project_path: Optional[str] = None,
                         seed: Optional[dict] = None) -> dict:
    """便捷函数：一步构建业务图谱。"""
    return BusinessGraphBuilder().build(project_info, deep_result, project_path, seed)
