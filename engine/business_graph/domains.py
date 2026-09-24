"""
第 2 步：一级业务域聚类（README5 §3.1 第 2 步）

输入：``Unit[]``（verified）
输出：``Domain[]``（inferred，可解释）

为什么要"投票"而不是"聚类算法一把梭"
--------------------------------------
README4/README5 的纪律是：**结论必须可解释、可复现、可被教师推翻**。
所以这里不用需要调参的社区发现，而是让每个信号投一票，并把票记进 ``evidence``：

| 信号 | 权重 | 说明 |
|---|---|---|
| 文件级中文 docstring | 3 | 中文项目里常见 "预约管理模块"，**最可靠的中文名来源** |
| 目录 / 包名 | 3 | 多包项目的主要信号 |
| 类名词根（剥离 Manager/Service/...） | 2 | ``ReservationManager`` → ``Reservation`` |
| 文件名 | 2 | 同上 |
| 共享状态对象 | 3 | 两个单元都写 ``self.reservations`` → 强信号 |
| 模块级调用图社区（标签传播，确定性顺序） | 2 | 调用密集的单元归到一起 |

合并阈值可调；**达不到阈值就诚实退化**：单元独占成域，标 ``confidence: inferred-low``。

另外做一件 README5 §3.1 特别要求的事：**编排类识别**。
满足 ``state_writes == ∅ 且 跨域出边比例 > 0.7`` 的单元打 ``role: orchestrator``，
从"核心业务域"里移出去 —— 修掉"系统编排模块被当成核心业务模块"这个教学错误。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .. import lexicon
from .units import Unit, edge_target

#: 类名后缀（剥离后剩下的词根才是业务对象候选）
_CLASS_SUFFIXES = (
    "manager", "service", "handler", "controller", "helper", "util", "utils",
    "checker", "factory", "builder", "repository", "dao", "gateway", "client",
    "processor", "provider", "store", "registry", "validator", "resolver",
)

#: 合并阈值：两个键的信号得分达到这个分数才合并
MERGE_THRESHOLD = 4

#: 一个目录里最多有多少个文件时，才允许"整个目录 = 一个业务域"。
#:
#: 这一条是被 urllib3 逼出来的：它是 `src/urllib3/*.py` 的**扁平包**布局，
#: 42 个文件全在同一个目录里，于是"取目录最后一段当包名"的方案
#: 把整个项目塞进了**一个**域（2 域 / 14 功能点 / 11536 行，明显不合理）。
#:
#: 语义上的区别很清楚：**目录是"域"还是"包"，看它是不是一个大杂烩**。
#: 超过这个数量就退回"按标识符词根分"，再交给合并步骤去聚。
MAX_FILES_PER_DIR_AS_DOMAIN = 5

#: 合并时**不算数**的词元 —— 这些是架构后缀/通用词，共有没有任何含义。
#: 第一版没过滤，"用户管理/预约管理/设备管理"因为都含 `manager`（+2）
#: 又都写 `_next_id`（+3）就被合并成了一个域，5 个业务域塌成 2 个。
_MERGE_STOPWORDS = frozenset({
    "manager", "service", "handler", "controller", "helper", "util", "utils",
    "checker", "factory", "builder", "repository", "store", "base", "main",
    "app", "core", "common", "mixin", "abstract", "impl", "interface", "model",
    "entity", "dto", "data", "result", "value", "item", "obj", "object", "type",
    "test", "tests", "misc",
})

_CAMEL_RE = re.compile(r"(?<!^)(?=[A-Z])")


def _is_bookkeeping_state(attr: str) -> bool:
    """是否是"记账式"状态（自增 id、缓存标记等），不构成业务对象。

    ``_next_id`` / ``_current_user`` 这类私有属性在几乎所有 Manager 里都存在，
    拿它当"共享业务状态"来合并域会把不相干的模块粘在一起。
    """
    name = str(attr)
    return name.startswith("_")


def _tokenize(text: str) -> List[str]:
    """把标识符切成小写词元。"""
    if not text:
        return []
    parts = _CAMEL_RE.sub("_", str(text))
    return [p for p in re.split(r"[^0-9A-Za-z\u4e00-\u9fff]+", parts.lower()) if p]


def _root_of(name: str) -> str:
    """剥离常见架构后缀，得到业务词根。"""
    tokens = _tokenize(name)
    while tokens and tokens[-1] in _CLASS_SUFFIXES:
        tokens.pop()
    return "_".join(tokens) if tokens else str(name).lower()


def _dir_key(file_rel: str) -> str:
    """目录键：取相对路径的父目录（无目录则为空串）。"""
    if "/" not in file_rel:
        return ""
    return file_rel.rsplit("/", 1)[0]


def _package_name(dir_key: str) -> str:
    """把目录路径压成一个可比较的包名（取最后一段）。"""
    if not dir_key:
        return ""
    return dir_key.split("/")[-1]


@dataclass
class DomainSignal:
    """一条可解释的聚类依据。"""
    signal: str
    value: str
    weight: int
    detail: str = ""

    def to_dict(self) -> dict:
        return {"signal": self.signal, "value": self.value, "weight": self.weight, "detail": self.detail}


@dataclass
class Domain:
    """一级业务域（inferred）。"""
    domain_id: str
    name_cn: str
    name_status: str                 # "from_docstring" | "from_lexicon" | "from_identifier"
    role: str                        # core | support | orchestrator
    level: int = 1
    parent_id: Optional[str] = None
    units: List[str] = field(default_factory=list)
    evidence: List[DomainSignal] = field(default_factory=list)
    confidence: str = "inferred"
    children: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "domain_id": self.domain_id,
            "name_cn": self.name_cn,
            "name_status": self.name_status,
            "role": self.role,
            "level": self.level,
            "parent_id": self.parent_id,
            "children": self.children,
            "units": self.units,
            "evidence": [e.to_dict() for e in self.evidence],
            "confidence": self.confidence,
        }


def _domain_key_for_unit(unit: Unit, files_per_dir: Optional[Dict[str, int]] = None) -> Tuple[str, List[DomainSignal]]:
    """给一个单元算出它的"归属键"和投票证据。

    优先级刻意做成"中文 docstring > 目录 > 标识符词根"：
    中文项目里作者写下的"预约管理模块"比任何英文切词都准。
    """
    signals: List[DomainSignal] = []

    # 1) 文件级中文 docstring（只取含中文且长度合理的）
    doc = unit.file_docstring or ""
    if doc and re.search(r"[\u4e00-\u9fff]", doc) and len(doc) <= 30:
        signals.append(DomainSignal("file_docstring_cn", doc, 3, "文件级中文 docstring"))
        return f"doc::{doc}", signals

    # 2) 目录 / 包名 —— 但只在"这个目录足够小、像一个业务域"时才用
    dir_key = _dir_key(unit.file)
    package = _package_name(dir_key)
    dir_size = (files_per_dir or {}).get(dir_key, 1)
    if package and package not in ("src", "lib", "app", "code") and dir_size <= MAX_FILES_PER_DIR_AS_DOMAIN:
        signals.append(DomainSignal("package", package, 3, f"目录 {dir_key}（{dir_size} 个文件）"))
        return f"pkg::{package}", signals

    # 3) 类名/文件名词根
    root = _root_of(unit.symbol if unit.kind == "class" else unit.module.split(".")[-1])
    if root:
        detail = f"来自 {unit.symbol or unit.module}"
        if package and dir_size > MAX_FILES_PER_DIR_AS_DOMAIN:
            detail += f"（目录 {dir_key} 有 {dir_size} 个文件，太大不宜整体当域）"
        signals.append(DomainSignal("identifier_root", root, 2, detail))
    return f"root::{root or unit.unit_id}", signals


def _prettify_identifier(raw: str) -> str:
    """把标识符变成可读名字，但**不要把缩写拆碎**。

    ``BaseHTTPConnection`` 直接按驼峰切词会得到 "Base H T T P Connection"（很难看）。
    这里把连续的单字符词元（含 ``HTTP2`` 这种带数字的）合并回一个缩写词：
    → "Base HTTP Connection" / "HTTP2 Probe Cache"。
    """
    tokens = _tokenize(raw)

    def _is_acronym_piece(token: str) -> bool:
        if len(token) == 1 and token.isalpha():
            return True
        # HTTP2 / TLS1 这类"短且带数字"的也算缩写的一部分
        return len(token) <= 2 and any(ch.isdigit() for ch in token)

    merged: List[str] = []
    buffer: List[str] = []
    for token in tokens:
        if _is_acronym_piece(token):
            buffer.append(token)
            continue
        if buffer:
            merged.append("".join(buffer).upper())
            buffer = []
        merged.append(token.capitalize())
    if buffer:
        merged.append("".join(buffer).upper())
    return " ".join(merged)


def _name_for_key(key: str, units: List[Unit], signals: List[DomainSignal]) -> Tuple[str, str]:
    """把归属键翻成中文域名，并说明名字的来源（inferred 必须可追溯）。"""
    if key.startswith("doc::"):
        return key[len("doc::"):], "from_docstring"
    if key.startswith("pkg::"):
        package = key[len("pkg::"):]
        # 包名先查同义词，再回退成可读标识符
        for canonical, aliases in lexicon.alias_groups().items():
            if package in aliases or package == canonical:
                return canonical, "from_lexicon"
        return package.replace("_", " "), "from_identifier"
    if key.startswith("root::"):
        root = key[len("root::"):]
        # 用 entities 词典把英文词根翻成中文（认得出来才翻，不硬凑）
        for entity_key, spec in lexicon.entity_names().items():
            names = [str(n).lower() for n in spec.get("names", [])]
            if root in names or root.replace("_", "") in [n.replace("_", "") for n in names]:
                return f"{spec.get('cn', entity_key)}业务域", "from_lexicon"
        return _prettify_identifier(root), "from_identifier"
    return key, "from_identifier"


def _is_ctor(name: str) -> bool:
    """是否是构造函数之类的"装配"方法。"""
    return name in {"__init__", "__post_init__", "__new__", "__init_subclass__"}


def _business_state_writes(unit: Unit) -> List[str]:
    """单元真正持有的**业务**状态。

    为什么要把构造函数排掉：``LabSafetyApp.__init__`` 里写的是
    ``self.user_manager = UserManager()`` 这类**装配**（把各模块接起来），
    不是业务状态。第一版没排掉它，于是这个明显的编排类被当成"有状态的核心业务域"，
    README5 §3.1 要求的 orchestrator 识别一个都没命中。
    """
    writes = []
    for method in unit.methods:
        if _is_ctor(method.symbol):
            continue
        for attr in method.state_writes:
            if attr not in writes:
                writes.append(attr)
    return writes


def _is_orchestrator(unit: Unit, module_call_targets: Dict[str, set]) -> bool:
    """编排类判定：自己不持有业务状态，主要工作是调用**多个其它模块**。

    这里刻意做得**保守**。第一版只要"无状态 + 跨模块调用比例 > 0.7"就判定，
    结果 python-dotenv 这种库项目里 16 个域有 10 个被判成"系统装配" ——
    因为库里很多类天然没有状态，"无状态"根本不能证明它是编排者。

    现在额外要求：跨到 **≥3 个不同的其它模块**，且几乎不调用自己模块内部的东西。
    """
    if _business_state_writes(unit):
        return False
    calls_out = module_call_targets.get(unit.unit_id, set())
    if len(calls_out) < 3:
        return False

    own_module = unit.module
    external_modules = set()
    internal_calls = 0
    for target in calls_out:
        # 调用目标形如 "module:Class.method" 或 "module.func"
        module_part = str(target).split(":", 1)[0]
        if module_part == own_module or module_part.endswith("." + own_module):
            internal_calls += 1
        else:
            external_modules.add(module_part)

    return len(external_modules) >= 3 and internal_calls <= 1


# ------------------------------------------------------------
# 域合并（README5 §3.1 第 2 步的"合并规则"）
# ------------------------------------------------------------
# 第一版只做了"投票出初始键"，**忘了真正合并** —— 于是 python-dotenv 里
# 每个类都成了一个"业务域"（Atom / Binding / Position / Literal / Original ... 16 个）。
# 业务域应该是"业务区域"，不是"一个类"。
#
# 合并依据（每个信号都记进 evidence）：
#   · 同一个文件                  +3   （一个文件里的多个类是同一个模块的实现细节）
#   · 共享被写的状态对象           +3
#   · 单元之间存在调用             +2
#   · 词根有共同词元               +2
# 两个键的得分 >= MERGE_THRESHOLD 就合并。

def _merge_scores(groups: Dict[str, List[Unit]], call_pairs: set) -> Dict[Tuple[str, str], Tuple[int, List[str]]]:
    """算出所有键两两之间的合并得分与理由。"""
    keys = sorted(groups)
    scores: Dict[Tuple[str, str], Tuple[int, List[str]]] = {}

    file_sets = {k: {u.file for u in groups[k]} for k in keys}
    state_sets = {
        k: {a for u in groups[k] for a in u.state_writes if not _is_bookkeeping_state(a)}
        for k in keys
    }
    token_sets = {
        k: {
            t for u in groups[k]
            for t in _tokenize(u.symbol) + _tokenize(u.module.split(".")[-1])
            if t not in _MERGE_STOPWORDS
        }
        for k in keys
    }

    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            score = 0
            reasons: List[str] = []

            # 同一个文件 = 同一个模块的实现细节，是最强的合并依据（+4，单独就够）
            if file_sets[a] & file_sets[b]:
                score += 4
                reasons.append("same_file")

            shared_state = state_sets[a] & state_sets[b]
            if shared_state:
                score += 3
                reasons.append("shared_state:" + ",".join(sorted(shared_state)[:2]))

            if (a, b) in call_pairs or (b, a) in call_pairs:
                score += 2
                reasons.append("call_adjacent")

            # 共享词元只给 +1：它是最弱的信号。
            # 曾经给 +2，于是 `app.py`（tokens: lab, safety）和"安全检查模块"（token: safety）
            # 因为"调用相邻 +2"和"共享词元 +2"凑满 4 分被合并 —— 系统装配域直接消失了。
            shared_tokens = token_sets[a] & token_sets[b]
            if shared_tokens:
                score += 1
                reasons.append("shared_token:" + ",".join(sorted(shared_tokens)[:2]))

            if score:
                scores[(a, b)] = (score, reasons)
    return scores


def _union_find_merge(keys: List[str], scores: Dict[Tuple[str, str], Tuple[int, List[str]]]) -> Dict[str, str]:
    """按得分降序合并（并查集），返回 ``key -> 代表键``。"""
    parent = {k: k for k in keys}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: str, y: str) -> None:
        rx, ry = find(x), find(y)
        if rx == ry:
            return
        # 代表键取字典序较小者，保证可复现
        keep, drop = sorted((rx, ry))
        parent[drop] = keep

    for (a, b), (score, _reasons) in sorted(
        scores.items(), key=lambda kv: (-kv[1][0], kv[0])
    ):
        if score >= MERGE_THRESHOLD:
            union(a, b)
    return {k: find(k) for k in keys}


def build_domains(units: Sequence[Unit], call_graph=None) -> List[Domain]:
    """第 2 步：把单元聚成一级业务域。

    Returns:
        ``Domain`` 列表，按 ``domain_id`` 排序（可复现）。
    """
    # 先把每个单元的"归属键"算出来
    # 需要先知道每个目录有多大，才能判断"目录能不能当域"
    files_per_dir: Dict[str, int] = {}
    for unit in units:
        dir_key = _dir_key(unit.file)
        files_per_dir[dir_key] = files_per_dir.get(dir_key, 0) + 1

    grouped: Dict[str, List[Unit]] = {}
    key_signals: Dict[str, List[DomainSignal]] = {}
    for unit in sorted(units, key=lambda u: u.unit_id):
        key, signals = _domain_key_for_unit(unit, files_per_dir)
        grouped.setdefault(key, []).append(unit)
        key_signals.setdefault(key, []).extend(signals)

    # 共享状态对象：写同一组 state attr 的单元倾向同一个域（并对已有分组投票）
    state_to_units: Dict[str, List[str]] = {}
    for unit in units:
        for attr in unit.state_writes:
            state_to_units.setdefault(attr, []).append(unit.unit_id)

    # 模块级调用目标（用于编排类判定）
    module_call_targets: Dict[str, set] = {}
    for unit in units:
        targets = set()
        for method in unit.methods:
            for called in method.calls_out:
                targets.add(called)
        # 加上调用图里的出边（更全）
        module_call_targets[unit.unit_id] = targets
    if call_graph is not None:
        for node_id, node in (getattr(call_graph, "nodes", {}) or {}).items():
            owner = None
            for unit in units:
                if unit.kind == "class" and node_id.startswith(f"{unit.module}:{unit.symbol}."):
                    owner = unit
                    break
                if unit.kind == "functions" and node_id.startswith(f"{unit.module}:") and "." not in node_id.split(":", 1)[1]:
                    owner = unit
                    break
            if owner is None:
                continue
            bucket = module_call_targets.setdefault(owner.unit_id, set())
            for call in (getattr(node, "calls", []) or []):
                target = edge_target(call)
                if target:
                    bucket.add(str(target).split(":", 1)[-1])

    # ---- 真正的合并：先按信号给键两两打分，再并查集合并 ----
    # 没有这一步的话，python-dotenv 里每个类都会变成一个"业务域"。
    call_pairs = set()
    unit_key = {}
    for key, members in grouped.items():
        for unit in members:
            unit_key[unit.unit_id] = key
    for unit in units:
        src_key = unit_key.get(unit.unit_id)
        if not src_key:
            continue
        for target in sorted(module_call_targets.get(unit.unit_id, set())):
            target_symbol = str(target).split(":")[-1].split(".")[-1]
            for other in units:
                if other.unit_id == unit.unit_id:
                    continue
                if any(m.symbol == target_symbol for m in other.methods):
                    dst_key = unit_key.get(other.unit_id)
                    if dst_key and dst_key != src_key:
                        call_pairs.add(tuple(sorted((src_key, dst_key))))

    merge_scores = _merge_scores(grouped, call_pairs)
    representative = _union_find_merge(sorted(grouped), merge_scores)

    merged_groups: Dict[str, List[Unit]] = {}
    merged_signals: Dict[str, List[DomainSignal]] = {}
    merge_reasons: Dict[str, List[str]] = {}
    for key in sorted(grouped):
        rep = representative[key]
        merged_groups.setdefault(rep, []).extend(grouped[key])
        merged_signals.setdefault(rep, []).extend(key_signals.get(key, []))
        # 记录合并理由（可解释、可被教师推翻）
        for (a, b), (score, reasons) in merge_scores.items():
            if {a, b} == {rep, key} or (rep in (a, b) and key in (a, b)):
                merge_reasons.setdefault(rep, []).extend(
                    f"{r}({score})" for r in reasons if r not in merge_reasons.get(rep, [])
                )

    grouped = merged_groups
    key_signals = merged_signals

    domains: List[Domain] = []
    for index, key in enumerate(sorted(grouped), start=1):
        members = sorted(grouped[key], key=lambda u: u.unit_id)
        signals = list(key_signals.get(key, []))

        # 合并理由也进 evidence —— 让"为什么这几个类被当成一个业务域"可追溯
        for reason in sorted(set(merge_reasons.get(key, [])))[:4]:
            signals.append(DomainSignal("merge", reason, 2, "域合并依据"))

        # 共享状态信号
        shared: Dict[str, List[str]] = {}
        for attr, unit_ids in sorted(state_to_units.items()):
            in_domain = [u for u in unit_ids if any(m.unit_id == u for m in members)]
            if len(in_domain) >= 2:
                shared[attr] = sorted(in_domain)
        for attr, unit_ids in list(sorted(shared.items()))[:3]:
            signals.append(DomainSignal(
                "shared_state", attr, 3, f"{len(unit_ids)} 个单元共享该状态",
            ))

        name_cn, name_status = _name_for_key(key, members, signals)

        roles = []
        for unit in members:
            roles.append("orchestrator" if _is_orchestrator(unit, module_call_targets) else "core")
        if roles and all(r == "orchestrator" for r in roles):
            role = "orchestrator"
            # 编排类域的名字用**结构性名称**（"系统装配"），不用文件 docstring ——
            # 作者写的是"实验室安全助手系统 - 主入口"，那是项目名而不是业务域。
            structural = lexicon.load_lexicon("structural_names").get("domain_names", {})
            name_cn = structural.get("orchestrator", name_cn)
            name_status = "from_structural_role"
        elif any(r == "orchestrator" for r in roles):
            role = "core"          # 混合域按业务域处理，编排单元在第 3 步被单独标注
        else:
            role = "core"

        # 单元数只有 1 且没有任何中文/词典信号 → 诚实标低置信度
        confidence = "inferred"
        strong = [s for s in signals if s.weight >= 3]
        if len(members) == 1 and not strong:
            confidence = "inferred-low"

        domain_id = f"d_{re.sub(r'[^0-9a-z]+', '_', key.split('::')[-1].lower()).strip('_') or index}"
        domains.append(Domain(
            domain_id=domain_id,
            name_cn=name_cn,
            name_status=name_status,
            role=role,
            units=[u.unit_id for u in members],
            evidence=signals,
            confidence=confidence,
        ))

    # domain_id 去重（不同 key 可能 sanitize 成同名）
    seen: Dict[str, int] = {}
    for domain in sorted(domains, key=lambda d: d.domain_id):
        if domain.domain_id in seen:
            seen[domain.domain_id] += 1
            domain.domain_id = f"{domain.domain_id}_{seen[domain.domain_id]}"
        else:
            seen[domain.domain_id] = 1

    # 显示名去重：结构性名称（"系统装配"）在大型项目里会重复出现多次
    # （urllib3 曾有 9 个域都叫"系统装配"），在界面上无法区分。
    # 重名时补上目录/单元限定。
    name_counts: Dict[str, int] = {}
    for domain in domains:
        name_counts[domain.name_cn] = name_counts.get(domain.name_cn, 0) + 1
    unit_by_id = {u.unit_id: u for u in units}
    for domain in sorted(domains, key=lambda d: d.domain_id):
        if name_counts.get(domain.name_cn, 0) <= 1:
            continue
        members = [unit_by_id[u] for u in domain.units if u in unit_by_id]
        qualifier = ""
        if members:
            first = sorted(members, key=lambda u: u.unit_id)[0]
            qualifier = first.file.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        if qualifier:
            domain.name_cn = f"{domain.name_cn}（{qualifier}）"

    domains.sort(key=lambda d: d.domain_id)
    return domains
