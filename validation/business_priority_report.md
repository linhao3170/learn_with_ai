# lab_safety_assistant · 业务优先级报告

> 这是一份用于确定教学顺序和人工审核顺序的排序报告，不是代码正确率报告。

- 算法：Evidence-aware Business Logic Priority Score（BLPS-1.0）
- 节点数：39
- 流程数：6
- 平均位置证据完整度：100.0%
- 待审核提示：2

## 核心节点（Top 10）

| 排名 | 方法 | 模块 | 分数 | 代码位置 | 原因 |
|---:|---|---|---:|---|---|
| 1 | `add_check_item` | safety_checker | 69.4 | `D:\learn_with_ai\sample_projects\lab_safety_assistant\safety_checker.py:29` | 参与高重要度业务流程、会改变业务状态、位于跨模块边界 |
| 2 | `add_equipment` | equipment_manager | 68.1 | `D:\learn_with_ai\sample_projects\lab_safety_assistant\equipment_manager.py:24` | 参与高重要度业务流程、会改变业务状态、位于跨模块边界 |
| 3 | `add_lab` | reservation_manager | 68.1 | `D:\learn_with_ai\sample_projects\lab_safety_assistant\reservation_manager.py:25` | 参与高重要度业务流程、会改变业务状态、位于跨模块边界 |
| 4 | `register` | user_manager | 66.7 | `D:\learn_with_ai\sample_projects\lab_safety_assistant\user_manager.py:17` | 参与高重要度业务流程、会改变业务状态、位于跨模块边界 |
| 5 | `initialize_sample_data` | app | 65.3 | `D:\learn_with_ai\sample_projects\lab_safety_assistant\app.py:27` | 参与高重要度业务流程、会改变业务状态、位于跨模块边界 |
| 6 | `_create_hazard` | safety_checker | 57.7 | `D:\learn_with_ai\sample_projects\lab_safety_assistant\safety_checker.py:107` | 调用图结构中心、会改变业务状态 |
| 7 | `_find_hazard` | safety_checker | 49.3 | `D:\learn_with_ai\sample_projects\lab_safety_assistant\safety_checker.py:156` | 调用图结构中心 |
| 8 | `perform_check` | safety_checker | 46.7 | `D:\learn_with_ai\sample_projects\lab_safety_assistant\safety_checker.py:59` | 会改变业务状态 |
| 9 | `create_reservation` | reservation_manager | 45.7 | `D:\learn_with_ai\sample_projects\lab_safety_assistant\reservation_manager.py:56` | 会改变业务状态 |
| 10 | `assign_hazard` | safety_checker | 45.1 | `D:\learn_with_ai\sample_projects\lab_safety_assistant\safety_checker.py:127` | 会改变业务状态 |

## 业务流程优先级

| 流程 | 优先级 | 审核提示 | 原因 |
|---|---:|---:|---|
| LabSafetyApp Initialization Flow | 88.0 | 0.0 | 业务重要度高、跨模块协作明显、包含状态变更、存在校验步骤 |
| SafetyChecker Execution Flow | 51.0 | 0.0 | 包含状态变更、存在校验步骤 |
| ReservationManager Create / Submit Flow | 37.6 | 0.0 | 包含状态变更、存在校验步骤 |
| SafetyChecker Assignment Flow | 27.9 | 65.0 | 包含状态变更、状态变更但未发现显式校验 |
| SafetyChecker Completion / Close Flow | 27.9 | 65.0 | 包含状态变更、状态变更但未发现显式校验 |
| UserManager has_permission Flow | 24.2 | 0.0 | 存在校验步骤 |

## 证据缺口（需要教师先看）

| 严重度 | 类型 | 流程 | 位置 | 说明 |
|---|---|---|---|---|
| high | state_change_without_validation | flow_4 | `D:\learn_with_ai\sample_projects\lab_safety_assistant\safety_checker.py:127` | 该流程包含状态写入，但当前提取结果没有发现校验步骤，建议教师先审核边界条件。 |
| high | state_change_without_validation | flow_5 | `D:\learn_with_ai\sample_projects\lab_safety_assistant\safety_checker.py:142` | 该流程包含状态写入，但当前提取结果没有发现校验步骤，建议教师先审核边界条件。 |

## 算法口径

- 节点评分：`S_node=100*(0.35*C+0.25*R+0.20*M+0.10*B+0.10*E)`
- 加权 PageRank：`PR(v)=(1-d)/N+d*sum(PR(u)*w_uv/sum(w_ux)); cross-module edge weight=1.2`
- 约束：score 是可复现的排序信号；verified 事实仍以 AST、状态追踪和行号证据为准
