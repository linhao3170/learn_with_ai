"""学生设计图的纯结构检查（README §9.2 第 3 / 4 维的可计算信号）。

这个模块只做一件事：**把学生画的图变成一组可复现的结构信号**。
它不判断业务对错，也不给分数 —— 分数在 ``rubric.py``，文案在
``engine/lexicon/design_feedback.json``。

包含的检查
==========
- ``build_graph``：把 ``modules``（含每张卡片的 ``depends_on`` 声明）与 ``relations``（画布上画的边）
  合成一张有向图，并**分开记录每条边的来源**（``drawn`` / ``declared``）——
  「你声明的依赖」和「你画的线」是两件事，第 6 维正是要查两者是否自洽；
- ``detect_cycles``：Tarjan 强连通分量；SCC 大小 > 1 或自环即为环，输出**具体环路径**；
- ``orphan_modules``：既没有出边也没有入边的模块；
- ``dangling_edges``：指向不存在的模块的边（数据完整性问题）；
- ``max_depth`` / ``children_count``：层级深度与每个父模块的子节点数；
- ``declared_vs_drawn``：声明与画线不一致的模块清单。

四条纪律
========
1. **确定性**：节点按「提交顺序」稳定排列，Tarjan 用显式栈（不递归，避免深图爆栈），
   结果不含 ``set`` 遍历顺序依赖；同一份输入两次调用输出逐字节相同。
2. **不静默容错**：指向不存在的模块的边不会被丢掉，而是进 ``dangling_edges``
   （丢掉就等于把学生画的线悄悄改了）。
3. **不判语义**：环就说环、孤岛就说孤岛，不说「这个设计不好」。
4. **无外部依赖**：不引第三方图库（README §12.4 的同一条理由：仓库里没有图库依赖，
   有的话也会随 mermaid 升级消失）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

__all__ = [
    "ALGORITHM_VERSION",
    "EDGE_SOURCE_DRAWN",
    "EDGE_SOURCE_DECLARED",
    "build_graph",
    "detect_cycles",
    "orphan_modules",
    "dangling_edges",
    "self_loops",
    "module_depths",
    "max_depth",
    "children_count",
    "declared_vs_drawn",
    "analyze_graph",
]

ALGORITHM_VERSION = "design-graph-checks-1.0"

#: 边的来源标记
EDGE_SOURCE_DRAWN = "drawn"
EDGE_SOURCE_DECLARED = "declared"


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _as_list(value: Any) -> List[str]:
    """把 str / list 统一成字符串列表（``does_not`` / ``depends_on`` 在契约里两种写法都出现过）。"""
    if isinstance(value, (list, tuple)):
        return [_text(item) for item in value if _text(item)]
    if value is None:
        return []
    text = _text(value)
    return [text] if text else []


def build_graph(
    modules: Sequence[Dict[str, Any]],
    relations: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """合成学生设计的有向图。

    :param modules: 归一化后的模块清单（每项带 ``module_id``）
    :param relations: 画布上画的边（``{from, to, type}``）
    :returns: ``{"nodes": [...], "edges": [...], "adjacency": {...}, "reverse": {...},
              "unknown_edge_targets": [...]}``

    边的 ``sources`` 是**列表**：同一条边既可能被画出来、也被声明过，
    这时它同时带 ``drawn`` 与 ``declared``（这样「声明与画线是否自洽」才查得清）。
    """
    modules = [m for m in (modules or []) if isinstance(m, dict)]
    nodes: List[Dict[str, Any]] = []
    node_ids: List[str] = []
    for index, module in enumerate(modules):
        module_id = _text(module.get("module_id")) or f"m{index + 1}"
        nodes.append(
            {
                "module_id": module_id,
                "name": _text(module.get("name") or module.get("name_cn")),
                "level": module.get("level"),
                "parent_id": _text(module.get("parent_id")) or None,
            }
        )
        node_ids.append(module_id)
    known = set(node_ids)

    # 边的收集：先按「画出来的」，再按「声明的」，顺序稳定（提交顺序）
    edges: List[Dict[str, Any]] = []
    index_by_pair: Dict[Tuple[str, str], int] = {}

    def _add_edge(source: str, target: str, edge_type: str, origin: str) -> None:
        if not source or not target:
            return
        pair = (source, target)
        if pair in index_by_pair:
            edge = edges[index_by_pair[pair]]
            if origin not in edge["sources"]:
                edge["sources"].append(origin)
            return
        index_by_pair[pair] = len(edges)
        edges.append(
            {
                "from": source,
                "to": target,
                "type": edge_type,
                "sources": [origin],
            }
        )

    for relation in relations or []:
        if not isinstance(relation, dict):
            continue
        _add_edge(
            _text(relation.get("from")),
            _text(relation.get("to")),
            _text(relation.get("type")) or "uses",
            EDGE_SOURCE_DRAWN,
        )

    for module in modules:
        if not isinstance(module, dict):
            continue
        source = _text(module.get("module_id"))
        for target in _as_list(module.get("depends_on")):
            _add_edge(source, target, "uses", EDGE_SOURCE_DECLARED)

    adjacency: Dict[str, List[str]] = {node_id: [] for node_id in node_ids}
    reverse: Dict[str, List[str]] = {node_id: [] for node_id in node_ids}
    unknown_targets: List[str] = []
    for edge in edges:
        if edge["from"] not in known:
            unknown_targets.append(edge["from"])
        if edge["to"] not in known:
            unknown_targets.append(edge["to"])
            continue
        if edge["to"] not in adjacency[edge["from"]]:
            adjacency[edge["from"]].append(edge["to"])
        if edge["from"] not in reverse[edge["to"]]:
            reverse[edge["to"]].append(edge["from"])

    # 去重但保持首次出现顺序
    seen: List[str] = []
    for item in unknown_targets:
        if item not in seen:
            seen.append(item)

    return {
        "algorithm_version": ALGORITHM_VERSION,
        "nodes": nodes,
        "node_ids": node_ids,
        "known_ids": known,
        "edges": edges,
        "adjacency": adjacency,
        "reverse": reverse,
        "unknown_edge_targets": seen,
    }


# ============================================================
# Tarjan 强连通分量（显式栈，不递归）
# ============================================================

def detect_cycles(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    """有向图环检测：返回强连通分量里的环（含自环），每条带**具体路径**。

    实现是 Tarjan SCC 的显式栈版本：节点按 ``graph["node_ids"]`` 稳定顺序访问，
    不存在递归深度限制，也不依赖 ``set`` 的遍历顺序。

    返回项::

        {"modules": ["m1","m2"], "path": "模块A → 模块B → 模块A", "self_loop": false}
    """
    adjacency = graph.get("adjacency") or {}
    node_ids = list(graph.get("node_ids") or [])
    names = {node["module_id"]: node["name"] for node in graph.get("nodes") or []}

    index_of: Dict[str, int] = {}
    low: Dict[str, int] = {}
    on_stack: Dict[str, bool] = {}
    stack: List[str] = []
    counter = [0]
    components: List[List[str]] = []

    for root in node_ids:
        if root in index_of:
            continue
        # 迭代式 Tarjan：work 项 = (节点, 下一个待访问邻居的下标)
        work: List[List[Any]] = [[root, 0]]
        while work:
            node, child_index = work[-1]
            if child_index == 0:
                index_of[node] = counter[0]
                low[node] = counter[0]
                counter[0] += 1
                stack.append(node)
                on_stack[node] = True

            neighbours = adjacency.get(node) or []
            advanced = False
            while child_index < len(neighbours):
                child = neighbours[child_index]
                child_index += 1
                if child not in index_of:
                    work[-1][1] = child_index
                    work.append([child, 0])
                    advanced = True
                    break
                if on_stack.get(child):
                    low[node] = min(low[node], index_of[child])
            if advanced:
                continue

            work[-1][1] = child_index
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index_of[node]:
                component: List[str] = []
                while True:
                    member = stack.pop()
                    on_stack[member] = False
                    component.append(member)
                    if member == node:
                        break
                component.sort(key=lambda item: node_ids.index(item) if item in node_ids else 0)
                components.append(component)

    cycles: List[Dict[str, Any]] = []
    for component in components:
        if len(component) > 1:
            cycles.append(
                {
                    "modules": list(component),
                    "path": _cycle_path(component, adjacency, names),
                    "self_loop": False,
                }
            )
        elif len(component) == 1 and component[0] in (adjacency.get(component[0]) or []):
            cycles.append(
                {
                    "modules": list(component),
                    "path": _cycle_path(component, adjacency, names, self_loop=True),
                    "self_loop": True,
                }
            )
    return cycles


def _display(names: Dict[str, str], module_id: str) -> str:
    name = names.get(module_id) or ""
    return name or module_id


def _cycle_path(
    component: Sequence[str],
    adjacency: Dict[str, List[str]],
    names: Dict[str, str],
    self_loop: bool = False,
) -> str:
    """把强连通分量写成一条可读的环路径（沿真实边走出来，不编造顺序）。"""
    if self_loop:
        node = component[0]
        label = _display(names, node)
        return f"{label} → {label}"

    members = set(component)
    start = component[0]
    path: List[str] = [start]
    visited = {start}
    current = start
    while len(path) <= len(component):
        nxt = ""
        for candidate in adjacency.get(current) or []:
            if candidate in members and candidate not in visited:
                nxt = candidate
                break
        if not nxt:
            # 回到起点即闭合成环；否则按分量顺序补全（仍来自真实成员，不编造）
            break
        path.append(nxt)
        visited.add(nxt)
        current = nxt
    for member in component:
        if member not in visited:
            path.append(member)
            visited.add(member)
    path.append(start)
    return " → ".join(_display(names, node) for node in path)


# ============================================================
# 孤岛 / 悬空边 / 自环
# ============================================================

def orphan_modules(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    """既没有出边也没有入边的模块（孤立节点）。"""
    out: List[Dict[str, Any]] = []
    for node in graph.get("nodes") or []:
        module_id = node["module_id"]
        if not (graph["adjacency"].get(module_id) or []) and not (graph["reverse"].get(module_id) or []):
            out.append(dict(node))
    return out


def self_loops(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    """自己指向自己的边（单节点强连通分量）。"""
    out: List[Dict[str, Any]] = []
    for edge in graph.get("edges") or []:
        if edge["from"] == edge["to"]:
            out.append(edge)
    return out


def dangling_edges(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    """指向不存在的模块的边（数据完整性问题，**不许静默丢弃**）。"""
    known = graph.get("known_ids") or set()
    out: List[Dict[str, Any]] = []
    for edge in graph.get("edges") or []:
        if edge["from"] not in known or edge["to"] not in known:
            out.append(edge)
    return out


# ============================================================
# 层级
# ============================================================

def children_count(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    """每个父模块直接挂了多少个子模块（按节点顺序稳定输出）。"""
    counts: Dict[str, int] = {}
    order: List[str] = []
    for node in graph.get("nodes") or []:
        parent = node.get("parent_id")
        if not parent:
            continue
        if parent not in counts:
            counts[parent] = 0
            order.append(parent)
        counts[parent] += 1
    return [{"module_id": parent, "children": counts[parent]} for parent in order]


def module_depths(graph: Dict[str, Any]) -> Dict[str, int]:
    """每个模块的层级深度（根 = 1）。``parent_id`` 成环时按已访问集合截断，不死循环。"""
    parents = {node["module_id"]: node.get("parent_id") for node in graph.get("nodes") or []}
    depths: Dict[str, int] = {}

    for module_id in graph.get("node_ids") or []:
        chain: List[str] = []
        current: Optional[str] = module_id
        seen: List[str] = []
        while current and current not in seen:
            seen.append(current)
            chain.append(current)
            current = parents.get(current)
        depths[module_id] = max(1, len(chain))
    return depths


def max_depth(graph: Dict[str, Any]) -> int:
    """整张图的最大层级深度（全是根时 = 1）。"""
    depths = module_depths(graph)
    return max(depths.values()) if depths else 0


def declared_vs_drawn(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    """第 6 维信号 ③：声明了 ``depends_on`` 却没画线（或反之）的模块。

    ⚠️ **只在两边都非空且不一致时报**（这一条是跑起来才发现的口径问题）：
    画布上画的线本身就是「依赖声明」，所以

    - 只画线、不填 ``depends_on``（画布用户的常态）→ **不算不一致**；
    - 只填 ``depends_on``、不画线（纯文本提交）→ **不算不一致**；
    - 两边都给了、内容却不同 → 这才是真的自相矛盾。

    否则每个用画布的学生都会因为「没填卡片字段」被扣分，那是假阳性
    （README §19.2 的教训：别用一条看起来合理的规则去误伤真实用法）。

    返回 ``{"module_id", "name", "declared": [...], "drawn": [...]}``，
    两个列表里装的是**另一个模块的显示名**（已解析，取不到就退回 id）。
    """
    names = {node["module_id"]: node["name"] or node["module_id"] for node in graph.get("nodes") or []}
    declared: Dict[str, List[str]] = {}
    drawn: Dict[str, List[str]] = {}
    for edge in graph.get("edges") or []:
        source = edge["from"]
        if EDGE_SOURCE_DECLARED in edge["sources"]:
            declared.setdefault(source, []).append(names.get(edge["to"], edge["to"]))
        if EDGE_SOURCE_DRAWN in edge["sources"]:
            drawn.setdefault(source, []).append(names.get(edge["to"], edge["to"]))

    out: List[Dict[str, Any]] = []
    for module_id in graph.get("node_ids") or []:
        declared_list = declared.get(module_id, [])
        drawn_list = drawn.get(module_id, [])
        if not declared_list or not drawn_list:
            continue
        if sorted(declared_list) != sorted(drawn_list):
            out.append(
                {
                    "module_id": module_id,
                    "name": names.get(module_id, module_id),
                    "declared": declared_list,
                    "drawn": drawn_list,
                }
            )
    return out


def analyze_graph(
    modules: Sequence[Dict[str, Any]],
    relations: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """一次性跑完全部结构检查（rubric 与测试都用这一个入口）。"""
    graph = build_graph(modules, relations)
    cycles = detect_cycles(graph)
    orphans = orphan_modules(graph)
    dangling = dangling_edges(graph)
    loops = self_loops(graph)
    depths = module_depths(graph)
    return {
        "algorithm_version": ALGORITHM_VERSION,
        "graph": graph,
        "cycles": cycles,
        "orphans": orphans,
        "dangling_edges": dangling,
        "self_loops": loops,
        "children": children_count(graph),
        "depths": depths,
        "max_depth": max_depth(graph),
        "declared_vs_drawn": declared_vs_drawn(graph),
        "edge_count": len(graph.get("edges") or []),
        "counts": {
            "nodes": len(graph.get("nodes") or []),
            "edges": len(graph.get("edges") or []),
            "cycles": len(cycles),
            "orphans": len(orphans),
            "dangling_edges": len(dangling),
            "self_loops": len(loops),
        },
    }
