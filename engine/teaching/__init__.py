"""教学层（``engine/teaching/``）—— 培训功能里""规则引擎能判的部分""。

定位（对应分层架构 L3 的 ``engine/teaching/``）：

    培训功能分两半：**规则引擎判事实**、教师判语义。
    本包只做前半部分，且只做**可计算、可复核、无 LLM** 的那部分。

当前已实现
----------
- ``coverage``：阶段一「项目认知」的覆盖度比对器
  （学生自由文本 → 命中了哪些一级业务域 / 漏了哪些，不打分）。
- ``card_coverage``：阶段二「模块卡片学习」的事实覆盖比对器
  （逐张卡片 + 五个问题 → 命中了卡片上哪些已核实的事实 / 漏了哪些，不打分；
  题目与「问题 → 字段」映射在 ``engine/lexicon/stage_questions.json``，
  命中判定复用 ``coverage`` 的那一份，见 ``coverage.prepare_text`` / ``key_hit``）。

尚未实现（不要在这里假装有）
----------------------------
- 学习路线生成（``teaching_plan.json``）；
- 阶段三「业务流程推演」及以后（推演 / 设计画布 / 六维评审 / 重构挑战）；
- 能力报告（需要学习会话事件，当前事件只存在前端 ``localStorage``）。

纪律（与培养方案一致）
----------------------
1. 不判对错、不打分：算不出来的维度返回 `not_evaluated`，不许填 0 或假分；
2. 无证据不比对：置信度未确认的字段不参与比对，并写清原因；
3. 无随机、无网络、无 LLM；同一份输入两次调用输出逐字节相同。
"""

from __future__ import annotations

from engine.teaching import card_coverage, coverage

__all__ = ["card_coverage", "coverage"]
