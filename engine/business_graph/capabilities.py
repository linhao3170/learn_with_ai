"""
第 3 步：二级功能点切分（README5 §3.1 第 3 步）—— **全系统最关键的一步**

问题
----
现有引擎只有"一文件一类 = 一个模块"的扁平结构，没有任何二级功能点。
而 README4 第三章要求的正是"一级业务域 → 二级功能模块 → 动作/规则/状态"三级。
二级模块给不出来，"业务模块树"就是空话。

做法（确定性、可解释、无 LLM）
------------------------------
对域内每个函数抽一个「能力签名」：

```text
verb_class ← 函数名词根 → lexicon/verbs.json     （create / query / validate / approve / ...）
entity     ← 函数名其余名词 + 它写入的状态目标 → lexicon/entities.json
能力键     = (verb_class, entity)
```

然后按能力键聚簇，并有四条后处理规则：

| 规则 | 内容 | 理由 |
|---|---|---|
| A | 同 ``(verb_class, entity)`` 的函数进同一功能点 | 同一能力的不同实现 |
| B | 私有函数并入**唯一调用它的公开函数**所在功能点，角色标 ``rule`` | 否则二级模块会碎成渣（``_check_conflict`` 不该独立成一个模块） |
| C | 无人调用也无人被调用的孤立函数单独成功能点，标低置信度 | 诚实标注"没看出来它属于哪" |
| D | 域内功能点 > 8 时，按 ``(verb 大类, entity)`` 再合并一轮 | 控制层级粒度 |
| E | 域内功能点 < 3 时，域标 ``hierarchy: flat``，**不硬拆** | 允许诚实退化 |

命名顺序：中文 docstring 首句 → ``动词中文 + 对象中文``（词典翻译）→ 原名 + ``name_status: unconfirmed``。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .. import lexicon
from .domains import Domain
from .units import Unit, UnitMethod

#: 一个域内功能点超过这个数量就再合并一轮
MAX_CAPABILITIES_PER_DOMAIN = 8

#: 少于这个数量就标 hierarchy=flat（不硬拆多级）
MIN_CAPABILITIES_FOR_HIERARCHY = 3

_CAMEL_RE = re.compile(r"(?<!^)(?=[A-Z])")

#: 动词大类：把细粒度能力类别收敛成"大类"，用于规则 D 的二次合并
_VERB_BROAD = {
    "create": "write",
    "update": "write",
    "delete": "write",
    "transition": "write",
    "cancel": "write",
    "approve": "decide",
    "reject": "decide",
    "notify": "side_effect",
    "query": "read",
    "calculate": "read",
    "validate": "guard",
    "serialize": "transform",
    "configure": "setup",
    "identity": "guard",
}


def _tokens(text: str) -> List[str]:
    if not text:
        return []
    return [t for t in re.split(r"[^0-9A-Za-z\u4e00-\u9fff]+", _CAMEL_RE.sub("_", str(text)).lower()) if t]


def _verb_match(symbol: str) -> Optional[Tuple[str, str, str]]:
    """从函数名里认出能力动词。

    Returns:
        ``(verb_class, cn, cluster)``；认不出来返回 ``None``。
    """
    lowered = symbol.lower()
    tokens = _tokens(symbol)
    head = tokens[0] if tokens else lowered

    best: Optional[Tuple[str, str, str]] = None
    for verb_class, spec in sorted(lexicon.capability_verbs().items()):
        names = [str(n).lower() for n in spec.get("names", [])]
        cn = spec.get("cn", verb_class)
        cluster = spec.get("cluster", "lifecycle")
        # 先比词元（更精确），再比前缀包含（兜底）
        if head in names:
            return verb_class, cn, cluster
        if any(lowered.startswith(n) or n in tokens for n in names):
            if best is None:
                best = (verb_class, cn, cluster)
    return best


def _entity_match(symbol: str, state_targets: Sequence[str]) -> Optional[Tuple[str, str]]:
    """从函数名与状态写入目标里认出业务对象。

    优先级刻意做成"函数名 > 状态目标"：
    ``borrow_equipment`` 写的是 ``borrow_records``（→ 借还），但**函数名里的对象**
    才是它真正操作的东西（``equipment`` → 设备）。第一版把两者混在一个集合里
    按字典序取，于是"借用设备"被归成了"借还"这种对象，切分结果很别扭。

    Returns:
        ``(entity_key, cn)``；认不出来返回 ``None``。
    """
    stopwords = {s.lower() for s in lexicon.entity_stopwords()}
    name_tokens = {t for t in _tokens(symbol) if t not in stopwords}
    state_tokens: Set[str] = set()
    for target in state_targets:
        for token in _tokens(str(target).split(".")[0]):
            if token not in stopwords:
                state_tokens.add(token)

    def _hits(tokens: Set[str]) -> List[Tuple[str, str]]:
        found: List[Tuple[str, str]] = []
        for entity_key, spec in sorted(lexicon.entity_names().items()):
            names = {str(n).lower() for n in spec.get("names", [])}
            if tokens & names:
                found.append((entity_key, spec.get("cn", entity_key)))
        return found

    for candidate in (_hits(name_tokens), _hits(state_tokens)):
        if candidate:
            return candidate[0]     # 已按 entity_key 排序，稳定可复现
    return None


@dataclass
class CapabilityMember:
    """二级功能点的成员函数。"""
    symbol: str
    role: str                  # entry | rule | helper
    file: str
    start_line: int
    end_line: int
    is_public: bool = True
    state_writes: List[str] = field(default_factory=list)
    state_reads: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "role": self.role,
            "file": self.file,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "is_public": self.is_public,
            "state_writes": self.state_writes,
            "state_reads": self.state_reads,
        }


@dataclass
class Capability:
    """二级功能点（inferred，成员为 verified）。"""
    capability_id: str
    name_cn: str
    name_status: str
    parent_id: str
    level: int = 2
    entity: str = ""
    entity_cn: str = ""
    verb_class: str = ""
    verb_cn: str = ""
    #: 大类合并后的粗粒度动词（未合并时为空串）
    verb_broad: str = ""
    cluster: str = ""
    members: List[CapabilityMember] = field(default_factory=list)
    confidence: str = "inferred"
    role: str = "core"

    def to_dict(self) -> dict:
        return {
            "capability_id": self.capability_id,
            "name_cn": self.name_cn,
            "name_status": self.name_status,
            "parent_id": self.parent_id,
            "level": self.level,
            "entity": self.entity,
            "entity_cn": self.entity_cn,
            "verb_class": self.verb_class,
            "verb_cn": self.verb_cn,
            "verb_broad": self.verb_broad,
            "cluster": self.cluster,
            "members": [m.to_dict() for m in self.members],
            "confidence": self.confidence,
            "role": self.role,
            "member_confidence": "verified",
        }


def _methods_of(unit: Unit) -> List[UnitMethod]:
    return sorted(unit.methods, key=lambda m: (m.file, m.start_line, m.symbol))


def _callers_index(units: Sequence[Unit]) -> Dict[str, Set[str]]:
    """``symbol -> 调用它的符号集合``（用于把私有函数并进唯一的公开调用者）。"""
    index: Dict[str, Set[str]] = {}
    for unit in units:
        for method in unit.methods:
            for called in method.calls_out:
                name = str(called).split(".")[-1]
                index.setdefault(name, set()).add(method.symbol)
    return index


def _name_capability(verb_cn: str, entity_cn: str, fallback_symbol: str) -> Tuple[str, str]:
    """给功能点起中文名，并说明名字来源。"""
    if entity_cn and verb_cn:
        # 组合成"提交预约"这类中文名：动词在前，对象在后
        verb_map = {
            "提交/创建": "提交", "查询/读取": "查询", "校验/检测": "校验",
            "审批通过": "审批", "审批拒绝": "拒绝", "取消/撤回": "取消",
            "更新/修改": "修改", "状态流转": "流转", "删除/移除": "删除",
            "认证与权限": "权限校验", "通知/告警": "通知", "统计/计算": "统计",
            "序列化/格式化": "格式化", "配置/装配": "配置",
        }
        head = verb_map.get(verb_cn, verb_cn)
        return f"{head}{entity_cn}", "from_lexicon"
    if entity_cn:
        return f"{entity_cn}相关操作", "from_lexicon"
    if verb_cn:
        return f"{verb_cn}操作", "from_lexicon"
    return fallback_symbol, "unconfirmed"


def build_capabilities(units: Sequence[Unit], domains: Sequence[Domain]) -> Tuple[List[Capability], Dict[str, str]]:
    """第 3 步：把每个一级域切成二级功能点。

    Returns:
        ``(capabilities, hierarchy_by_domain)``
        ``hierarchy_by_domain`` 取值 ``"nested"`` 或 ``"flat"``（诚实退化）。
    """
    unit_by_id = {u.unit_id: u for u in units}
    callers = _callers_index(units)

    capabilities: List[Capability] = []
    hierarchy_by_domain: Dict[str, str] = {}

    for domain in sorted(domains, key=lambda d: d.domain_id):
        members_units = [unit_by_id[u] for u in domain.units if u in unit_by_id]
        all_methods: List[UnitMethod] = []
        for unit in members_units:
            all_methods.extend(_methods_of(unit))

        # ---- 规则 A：按 (verb_class, entity) 聚簇 ----
        # dunder 方法（__init__ / __str__ ...）是 Python 的语言管路，不是业务能力 ——
        # 第一版把它们也切成了功能点（出现过叫"__init__"的二级模块）。
        def _is_business_method(m: UnitMethod) -> bool:
            return not (m.symbol.startswith("__") and m.symbol.endswith("__"))

        groups: Dict[Tuple[str, str], List[UnitMethod]] = {}
        unclassified: List[UnitMethod] = []
        for method in all_methods:
            if not _is_business_method(method):
                continue
            verb = _verb_match(method.symbol)
            entity = _entity_match(method.symbol, method.state_writes)
            if verb is None and entity is None:
                unclassified.append(method)
                continue
            verb_class = verb[0] if verb else "misc"
            entity_key = entity[0] if entity else "general"
            groups.setdefault((verb_class, entity_key), []).append(method)

        # ---- 规则 D：过多就按大类再合并一轮 ----
        # 关键：合并**只改归属键，不丢具体动词** —— 第一版把 verb_class 直接换成大类，
        # 于是出现了 "decide"/"read"/"write" 这种粗到没有信息量的能力名。
        verb_detail: Dict[Tuple[str, str], List[str]] = {}
        if len(groups) > MAX_CAPABILITIES_PER_DOMAIN:
            broad: Dict[Tuple[str, str], List[UnitMethod]] = {}
            for (verb_class, entity_key), method_list in sorted(groups.items()):
                broad_key = (_VERB_BROAD.get(verb_class, verb_class), entity_key)
                broad.setdefault(broad_key, []).extend(method_list)
                verb_detail.setdefault(broad_key, [])
                if verb_class not in verb_detail[broad_key]:
                    verb_detail[broad_key].append(verb_class)
            groups = broad

        # ---- 规则 B：私有函数并入调用它的公开函数所在组 ----
        # 建 symbol -> (verb_class, entity_key) 映射
        owner_of: Dict[str, Tuple[str, str]] = {}
        for key, method_list in sorted(groups.items()):
            for method in method_list:
                if method.is_public:
                    owner_of[method.symbol] = key

        for method in list(unclassified) + [m for ms in groups.values() for m in ms if not m.is_public]:
            if method.is_public:
                continue
            for caller in sorted(callers.get(method.symbol, set())):
                if caller in owner_of:
                    target_key = owner_of[caller]
                    method_list = groups.setdefault(target_key, [])
                    if method not in method_list:
                        method_list.append(method)
                    if method in unclassified:
                        unclassified.remove(method)
                    break

        # ---- 规则 C：仍无法归属的函数 —— 同一域内**合并成一个**"待归类"功能点 ----
        # 第一版给每个孤立函数单独建一个功能点，python-dotenv 上立刻冒出十个
        # 叫 `dotenv_values` / `peek` / `has_next` 的"二级模块"，纯噪声。
        # 诚实的做法是：合成一个明确标注"待教师归类"的功能点，把符号列出来。
        if unclassified:
            groups.setdefault(("misc", "unclassified"), []).extend(
                sorted(unclassified, key=lambda m: (m.file, m.start_line, m.symbol))
            )

        # ---- 组装 ----
        domain_caps: List[Capability] = []
        for (verb_class, entity_key), method_list in sorted(groups.items()):
            method_list = sorted(method_list, key=lambda m: (m.file, m.start_line, m.symbol))
            if not method_list:
                continue

            verb_spec = lexicon.capability_verbs().get(verb_class, {})
            entity_spec = lexicon.entity_names().get(entity_key, {})
            verb_cn = verb_spec.get("cn", "") if verb_spec else ""
            entity_cn = entity_spec.get("cn", "") if entity_spec else ""
            cluster = verb_spec.get("cluster", "") if verb_spec else ""

            # 大类合并过的组：把具体动词挂到明细字段上，命名优先用具体动词，
            # 并用所有具体动词的 cluster 集合（便于后面判断职责过载）
            details = sorted(verb_detail.get((verb_class, entity_key), []))
            verb_broad = ""
            if details:
                primary = lexicon.capability_verbs().get(details[0], {})
                if primary:
                    verb_cn = primary.get("cn", verb_cn) or verb_cn
                # naming 用具体动词拼：合并组里可能既有"提交"又有"取消"，
                # 只报第一个会误导（曾出现把 cancel+create 的组叫成"取消预约"）。
                verb_cns = []
                for detail in details[:2]:
                    cn = lexicon.capability_verbs().get(detail, {}).get("cn", "")
                    if cn and cn not in verb_cns:
                        verb_cns.append(cn)
                if verb_cns:
                    verb_cn = "/".join(verb_cns)
                clusters = sorted({
                    lexicon.capability_verbs().get(d, {}).get("cluster", "")
                    for d in details
                } - {""})
                cluster = ",".join(clusters)
                verb_broad = verb_class
                verb_class = details[0]        # 对外暴露**具体**动词，大类单独放 verb_broad

            # 命名：优先用唯一成员的 docstring（作者自己写的），否则用词典组合
            doc_names = [m.docstring for m in method_list if m.docstring and re.search(r"[\u4e00-\u9fff]", m.docstring)]
            if verb_class == "misc" and entity_key == "unclassified":
                symbols = "、".join(m.symbol for m in method_list[:4])
                more = f" 等 {len(method_list)} 个" if len(method_list) > 4 else ""
                name_cn, name_status = f"其他能力（待归类：{symbols}{more}）", "unconfirmed"
            elif len(method_list) == 1 and doc_names:
                name_cn, name_status = doc_names[0][:20], "from_docstring"
            else:
                name_cn, name_status = _name_capability(verb_cn, entity_cn, method_list[0].symbol)

            members = []
            for method in method_list:
                if not method.is_public:
                    role = "rule"
                elif method.state_writes or method.state_reads:
                    role = "entry"
                else:
                    role = "entry"
                members.append(CapabilityMember(
                    symbol=method.symbol,
                    role=role,
                    file=method.file,
                    start_line=method.start_line,
                    end_line=method.end_line,
                    is_public=method.is_public,
                    state_writes=method.state_writes,
                    state_reads=method.state_reads,
                ))

            confidence = "inferred"
            if verb_class == "misc" and entity_key.startswith("orphan_"):
                confidence = "inferred-low"
            elif not verb_cn and not entity_cn and name_status != "from_docstring":
                confidence = "inferred-low"

            # entry 全是私有函数（只有规则、没有入口）→ 说明切分可能不理想
            if not any(m.is_public for m in members):
                confidence = "inferred-low"

            cap_id_seed = f"{domain.domain_id}_{verb_class}_{entity_key}"
            cap_id = "c_" + re.sub(r"[^0-9a-z]+", "_", cap_id_seed.lower()).strip("_")

            domain_caps.append(Capability(
                capability_id=cap_id,
                name_cn=name_cn,
                name_status=name_status,
                parent_id=domain.domain_id,
                entity=entity_key if entity_key != "general" else "",
                entity_cn=entity_cn,
                verb_class=verb_class,
                verb_cn=verb_cn,
                verb_broad=verb_broad,
                cluster=cluster,
                members=members,
                confidence=confidence,
            ))

        # ---- 规则 E：太少就诚实标 flat ----
        hierarchy_by_domain[domain.domain_id] = (
            "nested" if len(domain_caps) >= MIN_CAPABILITIES_FOR_HIERARCHY else "flat"
        )

        domain.children = [c.capability_id for c in sorted(domain_caps, key=lambda c: c.capability_id)]
        capabilities.extend(domain_caps)

    # capability_id 去重 + 稳定排序
    seen: Dict[str, int] = {}
    for cap in sorted(capabilities, key=lambda c: (c.parent_id, c.capability_id)):
        if cap.capability_id in seen:
            seen[cap.capability_id] += 1
            cap.capability_id = f"{cap.capability_id}_{seen[cap.capability_id]}"
        else:
            seen[cap.capability_id] = 1

    capabilities.sort(key=lambda c: (c.parent_id, c.capability_id))
    return capabilities, hierarchy_by_domain
