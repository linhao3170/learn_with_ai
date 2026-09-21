# 强化功能使用指南

本文档介绍为初赛准备的三个高性价比强化功能。

---

## 强化 1：事实表导出器 ⭐⭐⭐⭐⭐

### 功能说明

从深度分析结果中提取所有可验证的事实，导出为 CSV 和 Excel 格式，用作申报材料的核心附件。

### 使用方法

```bash
# 使用默认输入（frontend/public/demo/deep_analysis.json）
python scripts/export_fact_table.py

# 指定输入文件和输出前缀
python scripts/export_fact_table.py path/to/analysis.json output_name
```

### 输出文件

- **fact_table.csv** - CSV 格式，可用 Excel 打开
- **fact_table.xlsx** - Excel 格式（需要安装 openpyxl：`pip install openpyxl`）

### 输出格式

| 事实ID | 类型 | 描述 | 文件位置 | 可信度 | 证据来源 |
|--------|------|------|----------|--------|----------|
| F0001 | 跨模块调用 | app:LabSafetyApp.initialize → user_manager:UserManager.register | app → user_manager | verified | 调用类型: composite_attr |
| F0019 | 设计特征-guard_clause | register: guard-clause style (4 pre-checks) | user_manager.py:17 | verified | lines 35, 38, 42 |
| F0029 | 算法特征 | register: conditional checks (no loops) | user_manager.py:17 | verified | 4 guard clauses, no loops |

### 统计信息

脚本会自动生成统计摘要：
- 总事实数
- 按类型分布（跨模块调用、状态变更、设计特征等）
- 按可信度分布（verified / inferred）

### 材料中的使用

**在申报材料中这样写：**

> **数据来源与可信度**
>
> 我们从分析结果中提取了 N 条可验证的事实（见附件：fact_table.xlsx），每条事实包含：
> - 事实编号（可追溯）
> - 类型分类
> - 具体描述
> - 代码位置（文件名:行号）
> - 可信度级别（verified/inferred）
> - 证据来源
>
> 其中 X% 为 verified 级别（从 AST 直接解析，可机械验证），Y% 为 inferred 级别（需教师审核确认）。

---

## 强化 2：教师审核界面 Mock ⭐⭐⭐⭐

### 功能说明

在前端添加"教师审核模式"，让教师可以逐条确认或拒绝推断类结论。审核状态保存在 localStorage，刷新后不丢失。

### 使用方法

1. 启动前端：`cd frontend && npm run dev`
2. 打开浏览器访问分析页面
3. 切换到 **Key Impls** 标签页
4. 开启顶部的"教师审核模式"开关
5. 展开任意一个关键实现
6. 在底部看到审核区域：
   - 点击 **✓ 确认准确** - 标记为已确认
   - 点击 **✗ 标记错误** - 标记为已拒绝
   - 已审核的可以点"撤销"恢复

### 审核逻辑

- **仅对 inferred 级别的结论进行审核**（黄色标签）
- **verified 级别无需审核**（绿色标签，从代码结构直接验证）
- 审核状态存储在浏览器本地，不需要后端

### 审核统计

开启审核模式后，顶部会显示：
- 已确认数量（绿色圆点）
- 已拒绝数量（红色圆点）

### 材料中的使用

**截图要点：**
1. 审核模式开关打开的状态
2. 一个已确认的实现（绿色边框）
3. 一个已拒绝的实现（红色边框）
4. 顶部的统计数字

**在申报材料中这样写：**

> **教师审核机制**
>
> 系统将分析结论分为两级：
> - **verified**（已验证）：从代码结构直接提取，机械可验证（如：4 个守卫条件、3 处状态变更）
> - **inferred**（待确认）：基于启发式推断，需教师审核（如：算法类型推断）
>
> 教师可在界面中逐条审核 inferred 级别的结论：
> - 点击"确认准确"后，该结论升级为教师确认级别
> - 点击"标记错误"后，该结论折叠并标注为不准确
> - 所有审核记录持久化保存，可追溯
>
> （见截图：教师审核界面）

---

## 强化 3：错误类型归类器 ⭐⭐⭐⭐⭐

### 功能说明

在 D2-D4 实测验证时，记录和归类发现的错误，最终生成错误类型分布表。

### 使用流程

#### 1. 查看可用的错误类型

```bash
python scripts/error_classifier.py types
```

输出：
```
dynamic_call              - 动态调用解析失败
module_boundary           - 模块边界误判
pattern_false_positive    - 设计模式误报
state_tracking_miss       - 状态追踪漏报
semantic_inference        - 语义推断错误
algorithm_inference       - 算法类型推断错误
cross_file_call           - 跨文件调用追踪失败
other                     - 其他
```

#### 2. 实测时记录错误

每发现一个错误，立即记录：

```bash
python scripts/error_classifier.py add <项目名> <事实编号> <错误类型> <原因>
```

示例：
```bash
python scripts/error_classifier.py add lab_safety 调用链#5 dynamic_call "getattr动态调用无法静态解析"
python scripts/error_classifier.py add project_a 模块#2 module_boundary "单文件内两个类职责不同"
python scripts/error_classifier.py add project_b 模式#1 pattern_false_positive "误判为策略模式"
```

#### 3. 完成实测后生成报告

```bash
python scripts/error_classifier.py report
```

### 输出文件

生成 3 个文件：

1. **validation/error_log.json** - 原始错误日志（每条错误的完整记录）
2. **validation/error_distribution.csv** - 错误类型分布表（CSV 格式）
3. **validation/error_summary_for_submission.md** - 材料用摘要（Markdown 格式）

### 报告内容

#### 错误类型分布表

| 错误类型 | 出现次数 | 占比 | 是否可修 | 典型案例 |
|---------|---------|------|---------|---------|
| 动态调用解析失败 | 12 | 35% | [X] 架构限制 | getattr 动态调用 |
| 模块边界误判 | 8 | 24% | [OK] 可调优 | 单文件多模块 |
| 设计模式误报 | 7 | 21% | [OK] 可调优 | Strategy 误报 |
| 状态追踪漏报 | 5 | 15% | [!] 部分可修 | 嵌套层级 >2 |
| 其他 | 2 | 6% | - | - |

#### 按项目分布

| 项目名 | 错误数 | 占比 |
|-------|-------|------|
| lab_safety | 15 | 44% |
| project_a | 12 | 35% |
| project_b | 7 | 21% |

### 材料中的使用

**直接将 `error_summary_for_submission.md` 的内容复制到申报材料的"实测结果"章节。**

它已经包含：
- 总错误数和测试项目数
- 错误类型分布表
- 关键发现（可修复比例、架构限制比例等）
- 我们的应对措施

**核心卖点：**

> **我们不回避错误。** 以上所有错误都是在真实项目上实测发现的，每条都能回溯到具体案例。
>
> - X% 的错误可通过优化修复，已列入改进计划
> - Y% 的错误是静态分析的架构限制（动态调用、反射），这是业界共识
> - 所有语义推断类结论已标注为 `inferred`，前端用黄色显示，教师可逐条确认

---

## 实战建议

### 时间分配（假设有 2.5 天余量）

| 时间 | 任务 | 产出 |
|------|------|------|
| 半天 | 跑一遍 lab_safety，导出事实表 | fact_table.xlsx（材料附件 1） |
| 半天 | 找 2-3 个真实项目，记录错误 | error_log.json |
| 半天 | 生成错误分布报告 | error_distribution.csv（材料附件 2） |
| 1 天 | 截图审核界面，写入材料 | 审核界面截图 + 文字说明 |

### 材料结构建议

```
附录 A：事实表（fact_table.xlsx）
  - 说明：从 lab_safety_assistant 项目提取的 73 条可验证事实
  - 用途：证明"数据从哪来"

附录 B：错误类型分析（error_distribution.csv）
  - 说明：在 N 个真实项目上实测的错误归类
  - 用途：证明"准确率怎么样 + 我们诚实"

第 X 章：教师审核机制
  - 截图 1：审核模式开关
  - 截图 2：确认/拒绝按钮
  - 截图 3：审核统计
  - 说明：如何让教师逐条审核推断结论
```

### 答辩时可能的问题

**Q: 你们的数据是怎么来的？**
> 请看附录 A 的事实表，每条事实都标注了来源（行号、证据、可信度）。比如 F0019 这条"4 个守卫条件"，代码在 user_manager.py 的第 35、38、42 行，可以直接验证。

**Q: 准确率怎么样？**
> 请看附录 B 的错误分布表。我们在 N 个真实项目上实测，发现了 M 个错误，其中 X% 是架构限制（动态调用），Y% 可通过优化修复。我们不回避错误，因为教育场景讲错比不讲危害更大。

**Q: 教师怎么知道哪些结论可信？**
> 我们把结论分两级：verified（绿色，可机械验证）和 inferred（黄色，需教师审核）。教师可以在界面里逐条点"确认"或"拒绝"，状态会保存。（打开界面演示）

---

## 技术细节

### 强化 1：事实表导出器

**提取逻辑：**
- 从 `call_graph.edges` 提取跨模块调用
- 从 `state_analysis.classes` 提取状态变更
- 从 `business_flows` 提取流程步骤
- 从 `key_implementations` 提取设计特征

**只导出 verified 级别的事实，inferred 的不进表。**

### 强化 2：教师审核界面

**存储格式：**
```json
{
  "user_manager:UserManager.register": "confirmed",
  "reservation_manager:ReservationManager.create_reservation": "rejected"
}
```

存储在 `localStorage['teacher_review_status']`，key 是 `impl.node_id`。

### 强化 3：错误类型归类器

**错误类型定义：**
每个类型有 3 个属性：
- `name`: 显示名称
- `fixable`: True/False/'partial' - 是否可修复
- `reason`: 修复说明或限制原因

**日志格式：**
```json
[
  {
    "project": "lab_safety",
    "fact_id": "调用链#5",
    "error_type": "dynamic_call",
    "reason": "getattr动态调用无法静态解析",
    "timestamp": "2024-01-15T10:30:00"
  }
]
```

---

## 常见问题

### Q: 事实表导出失败怎么办？

检查输入文件是否存在：
```bash
ls frontend/public/demo/deep_analysis.json
```

如果没有，先运行分析：
```bash
python scripts/test_deep_analyzer.py
```

### Q: Excel 导出说缺少 openpyxl？

安装依赖：
```bash
pip install openpyxl
```

CSV 格式不需要额外依赖，可以直接用 Excel 打开。

### Q: 审核状态丢失了？

审核状态存在浏览器的 localStorage，清除浏览器缓存会丢失。建议截图保存审核结果。

### Q: 错误记录文件在哪？

在项目根目录的 `validation/error_log.json`。如果不存在，第一次添加错误时会自动创建。

---

## 总结

这三个强化功能的核心价值：

1. **事实表** → 回答"数据从哪来"
2. **教师审核** → 回答"教师怎么用"
3. **错误归类** → 回答"准确率怎么样"

**它们是初赛材料的核心附件，不是锦上添花，是雪中送炭。**

如果时间不够，至少做强化 1 和强化 3（共 1.5 天），它们是书面材料的必需品。

强化 2 是演示用的，如果没有现场演示环节，优先级可以降低（但截图还是要放材料里）。
