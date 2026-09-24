"""反馈生成：**信号码 → 中文模板的纯函数映射**（README §9.2 ``feedback.py``）。

为什么必须这么写（README §4 阶段五的原话）
==========================================
「每一条反馈都必须能追溯到一个可计算信号。不允许出现『模型觉得这个设计不够优雅』
这类无依据反馈。」所以：

- ``rubric.py`` 只产出**信号**（``{"code": ..., "params": {...}}``）；
- 人类可读的句子**只**由本模块从 ``engine/lexicon/design_feedback.json`` 渲染出来；
- 报告里的 ``issues`` 与 ``signals`` **不是两份数据**：``issues`` 恒等于本模块对
  ``signals`` 的渲染结果（测试逐条断言这条恒等式）。

纪律
====
1. **模板是固定的，触发条件是可复现的**：这句话就是「反馈是硬编码的吧」的诚实答案
   —— 模板固定，但每一条是被学生设计里的哪个结构信号触发的，完全可复现、可讲清。
2. **缺参数不留空括号**：占位符缺值时用 ``params`` 里给的降级短语填；一个都没给就填
   ``（该值不可用）``，绝不留 ``「」`` 这种看起来像系统算了个空的输出。
3. **未知信号码不编文案**：返回 ``[未定义反馈模板: XXX]`` 这种**显式标记**，
   并在 ``unknown_codes()`` 里可查。测试断言 rubric 用到的每个码都在词典里，
   所以正常路径下这个标记永远不会出现。
4. **纯函数**：不读文件（词典只在首次加载时读一次并缓存）、不依赖时间 / 随机 / 网络。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from engine.lexicon import lexicon_source, load_lexicon

__all__ = [
    "ALGORITHM_VERSION",
    "TEMPLATE_PLACEHOLDER_FALLBACK",
    "UNKNOWN_CODE_TEMPLATE",
    "templates",
    "template_source",
    "render",
    "render_issues",
    "unknown_code",
    "signal",
]

ALGORITHM_VERSION = "design-feedback-1.0"

#: 占位符一个值都没给时的填充物（不是空串：空串会渲染成「未识别到『』」）
TEMPLATE_PLACEHOLDER_FALLBACK = "（该值不可用）"

#: 未知信号码的显式标记模板（**不编文案**）
UNKNOWN_CODE_TEMPLATE = "[未定义反馈模板: {code}]"

_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def templates() -> Dict[str, str]:
    """信号码 → 中文模板（来自 ``engine/lexicon/design_feedback.json``）。"""
    data = load_lexicon("design_feedback")
    raw = data.get("templates") or {}
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items()}


def template_source() -> str:
    """模板词典的来源路径（排查「到底用的哪份文案」用）。"""
    return lexicon_source("design_feedback")


def unknown_code(code: Any) -> bool:
    """该信号码在词典里有没有对应的中文模板。"""
    return str(code) not in templates()


def render(code: Any, params: Optional[Dict[str, Any]] = None) -> str:
    """把一个信号渲染成一句中文（纯函数）。

    :param code: 信号码（如 ``DEP_CYCLE``）
    :param params: 占位符取值（如 ``{"path": "A → B → A"}``）
    :returns: 渲染后的中文；未知信号码返回显式标记而不是编出来的文案
    """
    key = str(code)
    template = templates().get(key)
    if template is None:
        return UNKNOWN_CODE_TEMPLATE.format(code=key)

    values = params if isinstance(params, dict) else {}

    def _replace(match: "re.Match[str]") -> str:
        name = match.group(1)
        if name in values:
            value = values[name]
            if isinstance(value, (list, tuple)):
                text = "、".join(str(item) for item in value)
            else:
                text = str(value)
            return text if text.strip() else TEMPLATE_PLACEHOLDER_FALLBACK
        return TEMPLATE_PLACEHOLDER_FALLBACK

    return _PLACEHOLDER_RE.sub(_replace, template)


def render_issues(signals: Any) -> List[str]:
    """把一组信号渲染成 ``issues`` 清单（报告里的 ``issues`` 恒等于这个函数的输出）。"""
    out: List[str] = []
    for item in signals or []:
        if not isinstance(item, dict):
            continue
        out.append(render(item.get("code"), item.get("params")))
    return out


def signal(code: str, **params: Any) -> Dict[str, Any]:
    """构造一个信号（rubric 与测试共用同一个构造器，字段名不会两边不一致）。"""
    return {"code": str(code), "params": {key: value for key, value in params.items()}}
