"""业务词典（lexicon）—— 引擎里唯一允许出现业务词汇的地方。

README5 §3.2 的纪律：

    所有业务名词、动词、同义词、角色词都放 ``lexicon/*.json``。
    引擎代码里出现"预约""设备"就是 bug。

本包只负责**加载与匹配**，不承载任何业务判断逻辑。

数据文件
--------
- ``module_types.json``  模块类型关键词 + 类型→中文名映射（原 ``MODULE_TYPE_KEYWORDS`` / ``type_names``）
- ``core_keywords.json`` 核心度关键词（原 ``CORE_KEYWORDS``）
- ``flow_names.json``    类型 → 流程名模板（原 ``type_flow_names``）
- ``flow_steps.json``    流程步骤中文标签 + 兜底步骤模板
- ``method_verbs.json``  方法名动词 → 能力类别（原 ``_categorize_methods`` 的正则）
- ``lifecycle.json``     初始化/样例数据流程特征词（``engine/flow_filter.py`` 使用）

教师可以直接编辑这些 JSON 来适配自己学校的命名习惯，**不需要改代码**
（README5 §3.2）。缺失或损坏时回退到内置默认值，保证引擎不会因为词典问题崩掉。
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

__all__ = [
    "LEXICON_DIR",
    "load_lexicon",
    "module_types",
    "core_keywords",
    "flow_names",
    "flow_steps",
    "method_verbs",
    "lifecycle_markers",
    "capability_verbs",
    "entity_names",
    "entity_stopwords",
    "alias_groups",
    "role_terms",
    "clusters",
    "overload_threshold",
    "lexicon_source",
]

LEXICON_DIR = os.path.dirname(os.path.abspath(__file__))

_cache: Dict[str, Any] = {}
_source: Dict[str, str] = {}


def load_lexicon(name: str) -> Dict[str, Any]:
    """按名字加载词典 JSON；失败时返回空 dict（并在 ``lexicon_source`` 里记录）。"""
    if name in _cache:
        return _cache[name]

    path = os.path.join(LEXICON_DIR, f"{name}.json")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError("lexicon root must be an object")
        _cache[name] = data
        _source[name] = path
    except (OSError, ValueError) as exc:
        _cache[name] = {}
        _source[name] = f"{path} (加载失败: {type(exc).__name__})"
    return _cache[name]


def lexicon_source(name: Optional[str] = None):
    """返回词典来源路径，便于排查"到底用的是哪份词表"。"""
    if name is None:
        return dict(_source)
    return _source.get(name, "")


# ------------------------------------------------------------
# 各词典的便捷访问器
# ------------------------------------------------------------

def module_types() -> Dict[str, List[str]]:
    """模块类型 → 关键词列表。"""
    data = load_lexicon("module_types")
    return data.get("types", {})


def module_type_names() -> Dict[str, str]:
    """模块类型 → 中文模块名（用于 ``_generate_module_name``）。"""
    data = load_lexicon("module_types")
    return data.get("names", {})


def module_type_default() -> str:
    data = load_lexicon("module_types")
    return data.get("default_type", "management")


def core_keywords() -> List[str]:
    """核心度评分关键词。"""
    return list(load_lexicon("core_keywords").get("keywords", []))


def flow_names() -> Dict[str, str]:
    """模块类型 → 核心流程名。"""
    return load_lexicon("flow_names").get("names", {})


def flow_step_labels() -> List[Dict[str, Any]]:
    """流程步骤中文标签规则（``pattern`` + ``action_type``）。"""
    return list(load_lexicon("flow_steps").get("labels", []))


def flow_step_fallback() -> str:
    """无法判断动作类型时的兜底标签模板（``{module}`` 会被替换）。"""
    return load_lexicon("flow_steps").get(
        "fallback", "执行{module}的核心操作"
    )


def flow_final_step() -> str:
    """流程固定的最后一步。"""
    return load_lexicon("flow_steps").get("final_step", "返回结果")


def method_verbs() -> List[Dict[str, Any]]:
    """方法名动词分组：``{category, cn, patterns}``。"""
    return list(load_lexicon("method_verbs").get("groups", []))


def lifecycle_markers() -> List[str]:
    """初始化/样例数据流程特征词。"""
    return list(load_lexicon("lifecycle").get("markers", []))


# ------------------------------------------------------------
# Sprint 1 · 业务图谱引擎用到的词典
# ------------------------------------------------------------

def capability_verbs() -> Dict[str, Dict[str, Any]]:
    """能力动词类别：``{class_key: {names, cn, cluster}}``。"""
    return load_lexicon("verbs").get("classes", {})


def entity_names() -> Dict[str, Dict[str, Any]]:
    """业务对象：``{entity_key: {names, cn}}``。"""
    return load_lexicon("entities").get("entities", {})


def entity_stopwords() -> List[str]:
    """实体匹配时要忽略的通用词。"""
    return list(load_lexicon("entities").get("_stopwords", []))


def alias_groups() -> Dict[str, List[str]]:
    """同义词组：``{规范名: [别名...]}``。"""
    return load_lexicon("aliases").get("aliases", {})


def role_terms() -> List[str]:
    """角色/权限词（英文 + 中文）。"""
    data = load_lexicon("roles")
    return list(data.get("roles", [])) + list(data.get("roles_cn", []))


def clusters() -> Dict[str, Dict[str, Any]]:
    """能力簇：``{cluster_key: {cn, prefixes}}``。"""
    return load_lexicon("clusters").get("clusters", {})


def overload_threshold() -> int:
    """「职责过载」阈值：一个模块覆盖多少个簇算过重。"""
    try:
        return int(load_lexicon("clusters").get("overload_threshold", 3))
    except (TypeError, ValueError):
        return 3
