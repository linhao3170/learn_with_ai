# 实测验证专区

> D1 产出物 · 用于校赛初赛的真实项目验证

从 GitHub / PyPI 选取的 3 个真实第三方 Python 项目，覆盖不同规模。
所有项目均为广泛使用的开源项目，非教学 demo，非自造。

## 快速开始

```bash
# 1. 为某个项目生成事实表
python scripts/export_fact_table.py --project validation/python_dotenv --output validation/results/python_dotenv_facts.csv --format all

# 2. 生成核对模板（手动核对时用）
python scripts/validation_report.py --template --source validation/results/python_dotenv_facts.csv --output validation/results/python_dotenv_check.csv

# 3. 核对完成后，生成验证报告
python scripts/validation_report.py --input validation/results/python_dotenv_check.csv --output validation/results/python_dotenv_report.md --project python-dotenv

# 4. 生成三个项目的跨项目汇总报告
python validation/generate_cross_project_report.py
```

## 项目列表

### 1. python-dotenv · 小型

| 项 | 值 |
|---|---|
| 行数 | 1,112 行（实测 1,112 行） |
| Python 文件数 | 8 个 |
| 来源 | PyPI / [theskumar/python-dotenv](https://github.com/theskumar/python-dotenv) |
| 版本 | 1.2.3 |
| 类型 | 工具库 |
| 用途 | 从 `.env` 文件加载环境变量的工具 |
| 已提取事实 | 189 条（verified 189 / inferred 0） |

**验证重点**：小型项目、命名相对规范、结构简单。
测试引擎在小规模代码上是否能准确识别模块职责和调用关系。

### 2. Flask · 中型

| 项 | 值 |
|---|---|
| 行数 | 9,513 行（src 目录） |
| Python 文件数 | 24 个 |
| 来源 | [pallets/flask](https://github.com/pallets/flask) |
| 版本 | 主分支（2025 年） |
| 类型 | Web 框架 |
| 用途 | Python 最流行的微型 Web 框架 |
| 已提取事实 | 488 条（verified 470 / inferred 18） |

**验证重点**：多包结构、跨文件调用、类继承体系、装饰器模式。
Flask 有清晰的分层（app / ctx / globals / helpers 等），适合测试模块划分和调用链分析。

### 3. urllib3 · 中大型

| 项 | 值 |
|---|---|
| 行数 | 12,275 行（src/urllib3 目录） |
| Python 文件数 | 35 个 |
| 来源 | [urllib3/urllib3](https://github.com/urllib3/urllib3) |
| 版本 | 主分支（2025 年） |
| 类型 | HTTP 客户端库 |
| 用途 | 功能强大的 HTTP 客户端，requests 库的底层依赖 |
| 已提取事实 | 719 条（verified 696 / inferred 23） |

**验证重点**：中大型项目的模块划分、状态管理、连接池等复杂逻辑。
urllib3 有较多的状态读写操作和连接管理逻辑，适合测试状态变更追踪能力。

## 汇总数据

| 项目 | 代码行数 | 文件数 | 事实总数 | verified | inferred | 确定性占比 |
|------|---------|--------|---------|----------|----------|-----------|
| python-dotenv | 1,112 | 8 | 189 | 189 | 0 | 100% |
| flask | 9,513 | 24 | 488 | 470 | 18 | 96.3% |
| urllib3 | 12,275 | 35 | 719 | 696 | 23 | 96.8% |
| **合计** | **22,900** | **67** | **1,396** | **1,355** | **41** | **97.1%** |

> 详细数据见 [cross_project_report.md](cross_project_report.md)

## 验证计划

见 README2.md 的 D2-D4 章节。每个项目按固定流程跑：

1. 运行事实表导出器，生成结构化事实清单
2. 在事实表基础上，人工逐条核对，标记错误类型
3. 用验证报告工具自动汇总错误率和错误分布

### 核对流程

1. **生成事实表**：`export_fact_table.py` 从代码分析结果提取结构化事实
2. **生成核对模板**：`validation_report.py --template` 在事实表基础上加 `is_error` / `error_type` / `notes` 三列
3. **人工核对**：逐条审核事实，错误的标记 `is_error=1` 并填写错误类型
4. **生成报告**：`validation_report.py` 自动统计错误率、错误类型分布，输出 Markdown 报告
5. **跨项目汇总**：`generate_cross_project_report.py` 生成三项目横向对比报告

## 统计口径

- 行数统计：排除 `__pycache__`、`.git`、`test`、`tests` 目录
- 仅统计 `.py` 文件
- 空行和注释计入总行数（与项目实际规模一致）

### 错误类型分类

| 类型代码 | 说明 |
|---------|------|
| module_miscluster | 模块划分错误（聚类错了/漏了/多了） |
| call_missing | 调用链遗漏 |
| call_wrong | 调用链错误（错调用/解析不了动态调用） |
| state_false_positive | 状态读写误报 |
| state_false_negative | 状态读写漏报 |
| module_desc_wrong | 模块职责描述与代码不符 |
| approach_wrong | 实现思路推断错误 |
| pattern_false_positive | 设计模式误报 |
| flow_missing | 业务流程遗漏 |
| flow_wrong | 业务流程步骤错误 |
| other | 其他错误 |

## 注意

这些项目仅用于内部验证分析引擎的准确率，不作为产品的一部分。
答辩时引用的是"在 N 个真实第三方项目上的实测结果"，不是这些项目本身。

## 文件结构

```
validation/
├── reviewer/                    # 交互式事实审核工作台
│   ├── index.html               # 审核页面（直接浏览器打开即可）
│   └── app.js                   # 审核功能脚本
├── python_dotenv/              # 验证项目 1：小型
├── flask/                      # 验证项目 2：中型
├── urllib3/                    # 验证项目 3：中大型
├── results/                    # 分析结果输出目录
│   ├── python_dotenv_facts.csv    # python-dotenv 事实表
│   ├── python_dotenv_facts.json   # python-dotenv 事实表（JSON）
│   ├── flask_facts.csv            # flask 事实表
│   ├── flask_facts.json           # flask 事实表（JSON）
│   ├── urllib3_facts.csv          # urllib3 事实表
│   └── urllib3_facts.json         # urllib3 事实表（JSON）
├── generate_cross_project_report.py  # 跨项目汇总报告生成器
├── cross_project_report.md           # 跨项目汇总报告
├── error_distribution.csv            # 已有错误分布（早期版本）
├── error_summary_for_submission.md   # 已有错误摘要（早期版本）
└── README.md                         # 本文件
```

## 审核工具使用

### 网页审核工作台（推荐）

直接用浏览器打开 `validation/reviewer/index.html`：

1. 点击"导入事实表 CSV"，选择 `results/` 目录下的事实表文件
2. 左侧按类别/可信度/审核状态筛选
3. 点击单条事实，右侧弹出详情面板
4. 一键标记"确认正确"或"标记错误"，填写错误类型和备注
5. 支持键盘快捷键：
   - `↑` / `k` 上一条
   - `↓` / `j` 下一条
   - `y` 确认正确并跳到下一条
   - `n` 标记错误
6. 完成后点击"导出审核结果"下载带标记的 CSV
7. 点击"生成报告"查看实时统计

### 命令行工具

见上方"快速开始"部分。
