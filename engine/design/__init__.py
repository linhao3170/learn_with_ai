"""设计层引擎（``engine/design/``）—— 培养方案第四章 阶段四 / 五的落地。

职责
----
把「学生自己画的模块设计」变成一份**可复现、可定位、可讲清**的六维评审报告：

```text
design_task（分级任务，README §9.1）
   │
   ├─ matcher.py        学生模块 ↔ 必备能力 的三分类匹配（exact / contains / token）
   ├─ graph_checks.py   环 / 孤岛 / 悬空边 / 层级 / 声明与画线是否自洽（Tarjan SCC）
   ├─ alternatives.py   可接受替代结构与禁止合并项
   ├─ submission.py     design_submission.json 的归一化（§10.4 契约的唯一入口）
   ▼
rubric.py                六维评审（§9.2 的可计算定义）
   ▼
feedback.py              信号码 → 中文模板（唯一的文案来源）
```

六条纪律（与阶段一 / 二同源，全部可被脚本检查）
=============================================
1. **算不出来就返回 ``not_evaluated``**，附原因、``score = null``、不参与权重归一化，
   **不许填 0 或填假分**（设计原则第五条）。唯一例外是「异常与边界」维：
   学生没填 → 按 0 计并标注 ``not_filled``（README §9.2 明写的口径），
   因为那是「还没有填」，不是「算不出来」。
2. **「未识别」与「未覆盖」严格区分**，措辞不定罪（词汇匹配必然有假阴性）。
3. **第 6 维只衡量「理由可核查性」，不衡量「正确性」**。
4. **反馈 = 信号码 → 中文模板的纯函数映射**：报告里 ``issues`` 恒等于
   ``feedback.render_issues(signals)``（测试逐条断言）。
5. **业务词外置**：引擎代码里 0 处业务硬编码，题干 / 维度 / 扣分 / 文案全在
   ``engine/lexicon/design_*.json``。
6. **确定性**：无随机、无网络、无 LLM、无时间依赖；同一份输入两次调用逐字节一致。

本包**不做**什么
================
- 不判「哪个设计更好」：六维之外的偏好（优雅、直觉上的可扩展性）不进分数；
- 不判「学生是否理解了业务」：那是教师与答辩环节；
- 不调 LLM：任何「判定对错」的动作都不交给模型（设计原则第四条）。
"""

from __future__ import annotations

from .alternatives import evaluate_alternatives
from .feedback import render as render_feedback
from .graph_checks import analyze_graph
from .matcher import match_modules
from .rubric import ALGORITHM_VERSION as RUBRIC_ALGORITHM_VERSION
from .rubric import evaluate_design, report_signature
from .submission import normalize_submission, structural_issues
from .task_builder import (
    build_design_task,
    list_design_tasks,
    must_have_from_graph,
    resolve_task,
)

__all__ = [
    "RUBRIC_ALGORITHM_VERSION",
    "analyze_graph",
    "build_design_task",
    "evaluate_alternatives",
    "evaluate_design",
    "list_design_tasks",
    "match_modules",
    "must_have_from_graph",
    "normalize_submission",
    "render_feedback",
    "report_signature",
    "resolve_task",
    "structural_issues",
]
