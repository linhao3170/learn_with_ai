"""
业务图谱引擎（Business Graph Engine）—— README5 Sprint 1 / §3.1

职责
----
把「代码证据」翻译成「业务结构的初始版本」：

```text
代码证据（调用图 / 状态 / 流程 / 关键实现）
   │
   ├─ 第 1 步 结构单元采集        units.py        → Unit[]      (verified)
   ├─ 第 2 步 一级业务域聚类      domains.py      → Domain[]    (inferred)
   ├─ 第 3 步 二级功能点切分      capabilities.py → Capability[](inferred)
   ├─ 第 4 步 事实绑定            facts.py        → 规则/状态/异常 (verified)
   ├─ 第 5 步 卡片与关系          cards.py        → ModuleCard / Relation
   ├─          复杂度分级         complexity.py   → L1–L4 + 七维明细
   ├─          流程与场景         scenarios.py    → 业务流 + 三型场景
   └─          种子图谱合并       seed_merger.py  → 教师版覆盖自动版
   ▼
BusinessGraph（带置信度、证据、复杂度；逐字节可复现）
```

三条纪律（必须遵守，否则这个层就变成"猜业务"）
------------------------------------------------
1. **词汇外置**：引擎代码里不出现任何业务词，全部走 ``engine/lexicon/``（README5 §3.2）。
2. **置信度分层**：结构/调用/行号是 ``verified``；聚类与命名是 ``inferred``；
   需要业务理解的（模块目标、"不负责什么"）是 ``unconfirmed``，等教师审核。
3. **可复现**：所有迭代按稳定键排序，不用随机、不用网络、不依赖 set 顺序；
   同一份代码两次运行必须逐字节一致（``scripts/check_determinism.py`` 会验证）。
"""

from __future__ import annotations

from .builder import BusinessGraphBuilder, build_business_graph

__all__ = ["BusinessGraphBuilder", "build_business_graph"]
