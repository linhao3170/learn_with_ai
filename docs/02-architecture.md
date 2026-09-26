# 工程架构、目录与引擎设计（原 README 第七 ~ 九章）

> 更新触发：**很少改**（分层 / 目录 / 流水线 / 引擎模块 / 设计层口径变了才动） | 上次更新：阶段 2 全面模块化一轮（2026-09-26）
> 来源：原 `README.md` 第七、八、九章**整章搬移**；章节号不变（`§7` 七条设计原则、`§8.x` 流水线与词典、`§9.x` 设计层六维口径）。
> **读它的时机**：加模块 / 改目录 / 动引擎之前必读 —— `§7` 的七条原则**违反其中任何一条都算 bug**。
> 数据长什么样见 `docs/03-contracts.md`；接口与前端见 `docs/04-api-and-frontend.md`；现状与验收见 `docs/07-status-and-acceptance.md`。

---

## 七、设计原则（七条，违反其中任何一条都算 bug）

1. **单向依赖，不可倒挂。** 业务图谱由代码事实**派生**；业务层永远不反向依赖展示层。
   证据（代码图谱）是叶子，业务图谱是中间，教学 / 设计是上层。
2. **一切结论带置信度与证据。** `verified / inferred / unconfirmed` 三档；无证据不得进入学生视图。
3. **业务词汇外置，不进代码。** 所有业务名词、动词、同义词、角色词都放 `engine/lexicon/*.json`。
   **引擎代码里出现「预约」「设备」就是 bug**（有脚本门禁强制）。
4. **规则引擎判事实，教师判语义，LLM 只做映射与润色。** 任何「判定对错」的动作不得交给 LLM。
5. **可计算才评分。** 算不出来的维度返回 `not_evaluated`，**不许填 0 或填假分**。
6. **演示可复现，可降级。** 每个项目可带「教师种子图谱」；自动生成失败时降级到种子，且 UI 上标明来源。
7. **同一份输入，字节级相同输出。** 无随机、无网络、无 set 遍历顺序依赖；
   输出带 `algorithm_version` + `source_hash`。

---

## 八、分层架构、目录结构与业务图谱流水线

### 8.1 分层架构

```text
┌──────────────────────────────── 前端（Vue 3 + Tailwind）─────────────────────────────────┐
│  L5 教学与设计交互层                                                                       │
│  项目总览 │ 业务模块树 │ 模块卡片 │ 流程推演 │ 设计画布 │ 六维评审 │ 重构挑战 │ 能力报告   │
│  贯穿组件：证据弹窗 / 置信度徽章 / 复杂度徽章 / 教师审核条                                  │
└──────────────────────────────────────┬───────────────────────────────────────────────────┘
                                       │  统一契约 JSON（离线快照 与 在线 API 同一份契约）
┌──────────────────────────────────────▼───────────────────────────────────────────────────┐
│  L4 教学服务层  backend/app/                                                              │
│  teaching_service：图谱读取 / 学习会话 / 判题 / 阶段一覆盖度比对 / 设计提交 / 评审 / 教师审核 │
└──────────────────────────────────────┬───────────────────────────────────────────────────┘
┌──────────────────────────────────────▼───────────────────────────────────────────────────┐
│  L3 业务与设计引擎  engine/business_graph/ + engine/design/ + engine/teaching/  ★ 重设计主体 │
│  BusinessGraphBuilder（5 步流水线）· Lexicon · ModuleCardBuilder · BoundaryBuilder        │
│  ComplexityClassifier · FlowScenarioBuilder · DesignTaskBuilder                           │
│  RubricEngine · AlternativeAnalyzer · ReconstructAnalyzer · SeedMerger                    │
│  teaching/coverage（阶段一覆盖度比对，已实现；其余教学产物待建）                            │
└──────────────────────────────────────┬───────────────────────────────────────────────────┘
┌──────────────────────────────────────▼───────────────────────────────────────────────────┐
│  L2 代码证据层（已有，仅做小幅改造）                                                        │
│  CallGraph · StateTracker · FlowExtractor · DependencyStrength · Architecture             │
│  KeyImplementation · BusinessPriority(BLPS) · DesignPattern                               │
│  改造点：相对路径 · 流程过滤 · 名称外置 · 去掉 `_inferred_` 泄漏                            │
└──────────────────────────────────────┬───────────────────────────────────────────────────┘
┌──────────────────────────────────────▼───────────────────────────────────────────────────┐
│  L1 解析层（已有，不改）  engine/parser/ · project_parser.py   Python AST                   │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

**核心功能只有两个**：**业务逻辑分析**（把代码变成业务图谱）与**培训功能**（带学生从看懂走到会设计）。
其他都是外围。

### 8.2 目录结构（★ = 业务图谱 / 训练功能的核心）

```text
engine/
├── parser/                      # AST 解析 + 共享缓存（ast_cache.py：键含 mtime_ns + size）
├── analyzer/                    # 函数级分析（旧管线，与项目级调用图重复，待收敛；不是死代码）
├── project_analyzer/            # 项目级主链路（模块识别 / 核心流程 / 训练题 / 契约出口）
├── deep_analyzer/               # 项目级调用图 / 状态 / 流程 / 依赖强度 / 架构 / 关键实现 / BLPS
├── business_graph/              # ★ 业务逻辑分析核心（已实现）
│   ├── units.py                 #   第 1 步：结构单元采集
│   ├── domains.py               #   第 2 步：一级业务域聚类（含并查集合并）
│   ├── capabilities.py          #   第 3 步：二级功能点切分
│   ├── facts.py                 #   第 4 步：规则 / 状态 / 异常事实绑定
│   ├── cards.py                 #   第 5 步：模块卡片 + 边界 + 关系
│   ├── complexity.py            #   复杂度分级（结构定义 + level_basis）
│   ├── scenarios.py             #   三型流程场景（normal / exception / edge_case）
│   ├── seed_merger.py           #   教师种子图谱合并（locked 字段 + source 徽章）
│   ├── paths.py                 #   路径规范化的再导出（唯一实现在 engine/path_utils.py）
│   └── builder.py               #   流水线入口（BusinessGraphBuilder / build_business_graph）
├── business_logic/              # 纯数据契约层（models.py：12 个 dataclass，无算法）
├── lexicon/                     # ★ 业务词典 + 教学配置（20 份 JSON：15 通用 + 5 设计层）——唯一允许出现业务词的地方
├── flow_filter.py               # 生命周期流程统一降权 / 排序（唯一实现）
├── path_utils.py                # 路径规范化唯一实现
├── teaching/                    # ★ 培训功能·规则引擎能判的部分
│   ├── coverage.py              #   阶段一「项目认知」覆盖度比对 + 共用命中判定（归一化 / 键 / 匹配唯一实现）
│   └── card_coverage.py         #   阶段二「模块卡片学习」事实覆盖比对（复用 coverage 的命中判定）
├── design/                      # ★ 阶段四 / 五：设计任务 → 六维评审（Sprint 5 已实现）
│   ├── task_builder.py          #   分级设计任务（L1–L4）+ 学生视图 / 教师视图分离
│   ├── submission.py            #   design_submission.json 契约的唯一入口（幂等归一化）
│   ├── matcher.py               #   学生模块 ↔ 必备能力 的三分类匹配（复用 coverage 的命中判定）
│   ├── graph_checks.py          #   Tarjan SCC 环 / 孤岛 / 悬空边 / 层级 / 声明与画线
│   ├── alternatives.py          #   可接受替代结构与禁止合并项（没有教师清单时 available=False）
│   ├── rubric.py                #   六维可计算定义 + 权重归一化 + not_evaluated
│   └── feedback.py              #   信号码 → 中文模板的纯函数（唯一文案来源）
├── quiz/ · visualizer/          # 旧题目生成 / Mermaid 流程图
└── (待建) design/reconstruct.py # ★ 阶段六 重构挑战与影响范围（§9.3，未开始）
```

### 8.3 业务图谱构建流水线（`BusinessGraphBuilder`）

```text
代码证据（调用图 / 状态 / 流程 / 关键实现）
   │
   ├─ 第 1 步 结构单元采集        units.py        → Unit[]（verified）
   ├─ 第 2 步 一级业务域聚类      domains.py      → Domain[]（inferred）
   ├─ 第 3 步 二级功能点切分      capabilities.py → Capability[]（inferred）
   ├─ 第 4 步 事实绑定            facts.py        → 规则 / 状态 / 异常（verified）
   ├─ 第 5 步 卡片与关系          cards.py        → 卡片 + 边界 + 关系
   ▼
BusinessGraph（含置信度、证据、复杂度级别）
   │
   └─ seed_merger.py  ← 教师种子图谱（可覆盖自动结果，locked 字段最优先）
```

#### 8.3.1 第 1 步：结构单元采集（`verified`）

一个「单元」= 模块内的一个类，或一组顶层函数。每个单元记录：

```json
{"unit_id": "u_reservation_manager", "kind": "class",
 "symbol": "ReservationManager", "module": "reservation_manager",
 "file": "sample_projects/lab_safety_assistant/reservation_manager.py",
 "start_line": 11, "end_line": 190,
 "docstring_cn": "预约管理核心类",
 "file_docstring_cn": "预约管理模块",
 "methods": [{"symbol": "create_reservation", "start_line": 56, "end_line": 104, "is_public": true}],
 "state_writes": ["reservations", "_next_id", "labs"],
 "state_reads": ["labs", "reservations"],
 "calls_out": ["_check_conflict"], "called_by": ["app.initialize_sample_data"]}
```

> **路径纪律**：`file` 一律是**项目内相对路径**（POSIX 风格 `/`）。绝对路径不得进入任何契约。

#### 8.3.2 第 2 步：一级业务域聚类（`inferred` + 可解释投票）

对每个单元打分投票，**每个信号都记进 `evidence`**：

| 信号 | 权重 | 说明 |
|---|---|---|
| 文件级中文 docstring | 3 | 如「预约管理模块」→ **直接采纳为域名的首选候选** |
| 所在目录 / 包名 | 3 | 多包项目的主要信号；**只有目录足够小（≤5 个文件）才配当域** |
| 类名词根（剥离 `Manager/Service/Handler/Controller/Helper/Util/Checker`） | 2 | `ReservationManager` → `Reservation` |
| 文件名词根 | 2 | 同上 |
| 共享状态对象 | 3 | 两个单元都写 `self.reservations` → 强信号 |
| 模块级调用图社区（标签传播，确定性顺序） | 2 | 调用密集的单元归到一起 |

**合并规则：** 投票加和 ≥ 阈值（`MERGE_THRESHOLD`）的单元归入同一域（并查集合并）；
未达阈值则独占成域，`confidence: inferred-low`。

**编排类识别：** 若某单元满足 `state_writes == ∅` **且** 跨域出边 / 总出边 > 0.7 →
打 `role: orchestrator` 标签，**从「核心业务域」列表移出**，单独归入「系统装配」分区。
这样 `LabSafetyApp` 不会再被当成核心业务模块。

#### 8.3.3 第 3 步：二级功能点切分（`inferred`，**全系统最关键的一步**）

**输入：** 某域内所有单元的公开方法 + 私有方法。**对每个函数抽「能力签名」：**

```text
verb_class  ← 函数名词根 → lexicon/verbs.json → {create, query, validate, approve, reject,
                                                 cancel, submit, assign, notify, transition,
                                                 calculate, register, login, ...}
object      ← 函数名其余名词 + 状态写入目标 → lexicon/entities.json
能力键      = (verb_class, object)
```

**聚簇与后处理：**

| 步骤 | 规则 | 理由 |
|---|---|---|
| A | 同 `(verb_class, object)` 的函数进同一功能点 | 同一能力的不同实现 |
| B | 私有函数（`_check_conflict`）**并入唯一调用它的公开函数**所在功能点，角色标 `rule` | 避免二级模块碎成渣 |
| C | 同域内无法归类的函数合并成一个明确标注「待归类」的功能点 | 诚实标注，不硬编名字 |
| D | 若某域功能点数 > 8，按 `(verb 大类, object)` 再合并一轮 | 控制层级粒度 |
| E | 若某域功能点数 < 3 → 该域标 `hierarchy: flat`，**不硬拆** | 允许诚实降级 |

**命名顺序：** 中文 docstring 首句 → `动词中文 + 对象中文`（词典翻译）→ 原名（标 `name_status: unconfirmed`）。

**样例（`reservation_manager` 域）：**

| 二级功能点 | 成员函数 | 角色 | 证据 |
|---|---|---|---|
| 提交预约 | `create_reservation` | entry | `reservation_manager.py:56-104` |
| 冲突检测 | `_check_conflict` | rule | `reservation_manager.py:106-124` |
| 审批处理 | `approve_reservation` / `reject_reservation` | entry | `:126-151` |
| 取消预约 | `cancel_reservation` | entry | `:153-166` |
| 预约查询 | `get_user_reservations` / `get_lab_reservations` | entry | `:168-181` |
| 实验室登记 | `add_lab` / `list_labs` | entry | `:25-54, :183-190` |

#### 8.3.4 第 4 步：事实绑定（全部 `verified`）

把每个功能点成员函数里的 **`if` 条件 / `raise` / 状态写入**抽成事实：

```json
{"fact_id": "f_0007", "capability_id": "c_reservation_conflict", "kind": "business_rule",
 "text": "时间区间不能与已有预约重叠",
 "code": "if start < res_end and end > res_start",
 "file": "sample_projects/.../reservation_manager.py", "start_line": 122, "end_line": 122,
 "confidence": "verified"}
```

`kind` ∈ `business_rule` / `state_change` / `exception` / `precondition` / `guard`。

> **`text` 的中文描述如果无法从代码确定，就原样保留代码表达式并标 `verified_code_only`，
> 不许编业务含义。** 真实第三方项目上这条被大量用到（英文项目尤其如此）。

#### 8.3.5 第 5 步：卡片与关系

卡片字段与置信度的生成方式：

| 字段 | 生成方式 | 置信度 |
|---|---|---|
| `name_cn` | 见第 3 步命名顺序 | inferred |
| `objective` | 中文 docstring 首句；无则留空 | unconfirmed（需教师填） |
| `inputs` / `outputs` | 函数参数名 + 返回值 + 词典翻译 | inferred |
| `business_rules` / `state_changes` / `exceptions` | 第 4 步事实 | **verified** |
| `upstream` / `downstream` | 调用图的入边 / 出边聚合到功能点粒度 | **verified** |
| `does_not` | 见 8.6 | inferred → 待审核 |
| `evidence` | 成员函数 + 事实的行号 | **verified** |
| `role` | core / support / orchestrator | inferred |

### 8.4 词典设计（`engine/lexicon/*.json`）

**唯一允许出现业务词汇的地方**，教师可在不改代码的前提下编辑。
通用词典 / 教学配置共 15 份：`verbs` / `entities` / `aliases` / `roles` / `lifecycle` / `clusters` /
`module_types` / `core_keywords` / `flow_names` / `flow_steps` / `method_verbs` /
`architecture_tags` / `quiz_labels` / `structural_names` / `stage_questions`；
Sprint 5 的设计层另有 5 份（`design_dimensions` / `design_tasks` / `design_tasks.seed` /
`design_feedback` / `design_words`，见 §16.1 末），**合计 20 份 `.json`**。

> `stage_questions`（Sprint 4 新增）与 `structural_names` 都**不是业务词典**，而是**教学配置**：
> 前者放阶段二的五个问题文本与「问题 → 参与比对的卡片字段」映射，
> 后者放阶段一域名归一化要剥掉的结构性词（模块 / 管理 / 系统 / 的）。
> 放进 `lexicon/` 的理由是它们必须**可被教师改写**且**不许硬编码在引擎里**（审计门禁同样覆盖）。

```json
// verbs.json
{"version": "1.0",
 "classes": {
   "create":   {"names": ["create", "add", "register", "submit", "apply", "book", "new"], "cn": "提交/创建"},
   "query":    {"names": ["get", "find", "query", "list", "search", "fetch", "lookup"], "cn": "查询"},
   "validate": {"names": ["check", "verify", "validate", "detect", "ensure", "assert"], "cn": "校验/检测"},
   "approve":  {"names": ["approve", "confirm", "accept", "pass"], "cn": "审批通过"},
   "reject":   {"names": ["reject", "refuse", "deny"], "cn": "审批拒绝"},
   "cancel":   {"names": ["cancel", "abort", "revoke", "withdraw"], "cn": "取消"},
   "transition": {"names": ["complete", "close", "finish", "start", "activate"], "cn": "状态流转"}
 }}
```

```json
// lifecycle.json —— 用于过滤「初始化 / 样例数据」流程
{"version": "1.0",
 "patterns": ["initialize", "init", "bootstrap", "seed", "sample_data",
              "setup", "demo", "fixture", "populate"],
 "downweight": 0.2}
```

```json
// clusters.json —— 用于「职责过载」判断
{"version": "1.0",
 "clusters": {
   "identity":   ["register", "login", "logout", "authenticate", "authorize", "role"],
   "governance": ["approve", "reject", "assign", "review", "audit"],
   "integrity":  ["check", "validate", "verify", "detect"],
   "lifecycle":  ["create", "cancel", "complete", "close"],
   "inquiry":    ["get", "list", "search", "query"]
 }}
```

> **验收门禁**：`python scripts/audit_hardcoding.py --include-frontend` 必须 **0 命中、exit 0**。

### 8.5 复杂度分级引擎

七因子公式见第五章 5.1。**输出必须带明细**（否则就是个不可信的总分）：

```json
{"level": "L2", "raw": 27.4,
 "level_basis": {"domains": 5, "capabilities": 29, "roles": 4,
                 "approval_capabilities": 2, "state_fields": 9},
 "thresholds": {"L1": "<12", "L2": "12-40", "L3": "40-90", "L4": ">=90"},
 "breakdown": {"Domains": 3, "Capabilities": 11, "CrossDomainEdges": 4,
               "WrittenStateFields": 9, "BusinessBranches": 12, "ExternalEntries": 0, "RoleHits": 4},
 "algorithm_version": "complexity-1.0",
 "caveat": "阈值未经第三方项目校准，仅用于训练难度分层"}
```

### 8.6 「不负责什么」的三条生成规则（全部可解释）

1. **同级承担：** 同一域内被其他功能点承担的能力，反向写成本模块的「不负责」
   （例：「不负责审批结果判断」）；
2. **上游失败路径：** 若某能力在上游被前置校验挡掉（如 `create_reservation` 里的容量校验），
   则「容量校验」归于上游，冲突检测模块写「不负责人数容量校验」；
3. **越权预警：** 若某功能点也调用了其他域的状态写入，标记「越界耦合」，
   在卡片里写「当前实现中涉及 X 域状态，边界待教师确认」。

> 第 3 条是**教学亮点**：它不仅教边界，还**主动暴露真实项目里的边界模糊**。

### 8.7 流程与场景构建

**流程来源：** `FlowExtractor`（已有）+ 过滤。

**必须过滤掉生命周期流程：** 抽出共享工具 `engine/flow_filter.py` 的 `is_lifecycle_flow(flow)`，
命中 `lexicon/lifecycle.json` 的 `patterns` 则 `weight × 0.2`，**保留但不排第一**。
`flow_filter` 是**唯一实现**，`core_flows` / 流程列表 / BLPS 三处共用（`LIFECYCLE_FACTOR = 0.2`）。

**把流程提升到功能点粒度：** 流程步骤展示时映射成 `capability_id` 序列：

```json
{"flow_id": "fl_reservation_normal", "name_cn": "实验室预约（正常）", "scenario_type": "normal",
 "steps": [
   {"order": 1, "capability_id": "c_reservation_submit",  "action_cn": "提交预约",
    "evidence": [{"file": ".../reservation_manager.py", "start_line": 56, "end_line": 104}]},
   {"order": 2, "capability_id": "c_reservation_conflict","action_cn": "时间冲突检测",
    "evidence": [{"file": ".../reservation_manager.py", "start_line": 122, "end_line": 122}]}
 ],
 "involved_domains": ["d_lab_reservation"],
 "is_lifecycle": false, "confidence": "verified"}
```

**场景三型（对应第四章阶段三）：**

| 类型 | 生成方式 | 置信度 |
|---|---|---|
| `normal` | 主路径（无 `raise` 触发） | verified |
| `exception` | 取某个 `raise` 作为失败点，路径到该点终止 | verified |
| `edge_case` | 取边界条件（`>=`、`<=`、空集合、容量上限） | verified |

派生场景**要求 ≥2 步，否则不出**（凑不出就不出，不编造）。

> **不做的事**：不自动编自然语言场景描述。场景描述由**模板 + 代码事实**拼装
> （「当 `start >= end` 时，系统在提交预约时拒绝」），教师可改写。
> **不调 LLM 生成「业务故事」。**

### 8.8 教师种子图谱与合并机制（`seed_merger.py`）

**这是让演示稳定的关键工程决策。**

```text
seed: sample_projects/<p>/business_graph.seed.json   ← 教师 / 人工维护
auto: BusinessGraphBuilder 自动生成
merge 规则：
  1. 按 capability_id / domain_id 键对齐；
  2. seed 中 locked: true 的字段（name_cn / objective / does_not / parent_id / role）不可被 auto 覆盖；
  3. auto 新发现、seed 里没有的能力 → 追加，标 source: "auto"，confidence: inferred；
  4. seed 里存在、auto 未发现的能力 → 保留，标 source: "teacher"，
     并在审核界面提示「系统未能从代码中识别」；
  5. 每个节点带 source 徽章，UI 上**明确区分「教师审核版」与「系统推断版」**。
```

**为什么必须这样做：**

- 自动生成本身是研究性工作，短期内不可能在所有项目上达到可教的准确度；
- 但**演示不能翻车**，且**叙事不能说谎**；
- 于是：**演示用种子图谱（真话：「这是教师审核后的图谱」），自动生成能力作为已实现功能展示
  （真话：「系统能自动生成初始版本，待教师审核」）**。这既稳，又诚实。

> **现状（优先级 4 二轮更新）**：合并机制、测试与**种子文件**都齐了 ——
> `sample_projects/lab_safety_assistant/business_graph.seed.json` 是仓库里第一份，
> 内容是教师逐条确认的 **5 条域目标 + 3 条二级功能点目标**（`objective_confidence: "confirmed"`、
> `review_status: "approved"`，域的中文名同时被 `locked: ["name_cn"]` 锁住）。
> 合并后的实际效果（实测，见 §16.1 末）：
>
> | 观察点 | 加种子之前 | 加种子之后 |
> |---|---|---|
> | 图谱 `status` | `needs_review` | **`mixed`**（前端 `GRAPH_STATUS_META` 显示「部分已审核」，节点带「教师审核版」徽章） |
> | `source_hash` | `sha256:5bdd3e89…` | **不变**（`compute_source_hash` 只哈希被解析的 `.py`，所以填种子不会让已有审核失效） |
> | 阶段一 `objective_missing` | 4（比对键只有域名） | **0**（域目标文本进入比对键） |
> | 阶段二「待教师确认」卡片 | 8 张 | **0 张**（该项目的 8 张全部由教师给出了目标） |
> | 教师卡片 / 自动卡片 | 0 / 34 | **8 / 26** |
>
> **两个必须写清楚的边界**：① 域目标**必须填在 `module_cards[<domain_id>]` 里**，不能填在
> `domains[]` 里 —— 域对象根本没有 `objective` 字段，阶段一读的是卡片
> （`engine/teaching/coverage.py:188`）；② 域目标是**整句子串比对**，学生几乎不可能逐字命中，
> 所以它的价值是"让这个域从不可比对变成可比对"+"学生用自己的话描述目标时可能命中"，
> **不是"理解了就算命中"**（§4 阶段一末尾那条口径依然有效）。
>
> ⚠️ 还有一条纪律上的细节：`locked` 只对 `LOCKABLE_FIELDS` 生效，而
> **`objective_confidence` 不在其中** —— 它靠 merge 的"种子显式提供的其它字段照抄"那条规则生效，
> 所以必须**在种子里显式写 `"objective_confidence": "confirmed"`**；写成空串等于没填，
> 该字段仍会被判为「待教师确认」而不参与比对。

### 8.9 确定性保证（「可复现」卖点的技术落点）

| 要求 | 做法 |
|---|---|
| 聚类顺序稳定 | 所有迭代输入先按 `unit_id` / `capability_id` 字典序排序；禁止依赖 `set` 迭代顺序 |
| 文件遍历稳定 | `ProjectParser` 的 `os.walk` 结果 `sorted()` |
| **一次解析，多处复用** | `engine/parser/ast_cache.py`（键含 `mtime_ns` + `size`，改文件自动失效）；全链路只读一次、只 `ast.parse` 一次 |
| 无随机 | 禁止全局 `random.seed()`；需要随机时用独立的 `random.Random(seed)` 实例（默认 42），或直接用稳定键字典序 tie-break |
| **无 `set` 迭代顺序依赖** | 任何"`set` → 列表 → 拼进文本"的地方都必须 `sorted()`。**这条在优先级 4 二轮之前是假的**：`key_implementation.py` 用 `list(set(...))` 拼异常类型、`design_pattern_detector.py` 直接迭代 `instance_attributes`（`Set[str]`）拼证据文本，于是**同一个脚本在两个进程里产出的快照字节不同**（字符串哈希逐进程随机）。现已全部改为排序读取，并加了 `check_determinism.py --cross-process`（不同 `PYTHONHASHSEED` 各起一个子进程比对字节）——**同进程双跑查不出这一类问题**，见 §19.2 ⑳ |
| 无网络 | 引擎层不得发起任何网络请求（**含 LLM 调用**） |
| 浮点稳定 | 所有对外分数 `round(x, 1)`；阈值比较用整数计数 |
| 可追溯 | 每个产物带 `algorithm_version`；每个图带 `source_hash`（项目源文件 sha256 聚合） |
| 可验证 | 同一项目跑两次，`to_dict()` 结果**逐字节相同**（`scripts/check_determinism.py`）；**跨进程**同样要求逐字节相同（`--cross-process`，优先级 4 二轮新增） |

> **补充决策**：`engine/deep_analyzer/design_pattern_detector.py` 用 `try/except: continue` 吞异常，
> 且误报高。**决定：设计模式不进入学生主视图，也不作为评分维度**，
> 只在教师视图的「参考信息」里以 `inferred` 呈现。

---

## 九、设计层引擎（培训功能核心）——⚠️ 本章标题原写「尚未实现」，**已于 Sprint 5 落地**（见 §16.1）

> **状态口径以 §16.1 为准**：`engine/design/` 的 7 个文件（`task_builder` / `submission` /
> `matcher` / `graph_checks` / `alternatives` / `rubric` / `feedback`）都已实现并通过
> `test_design_rubric.py` 90/90 与 A11；**只有 §9.3 的 `reconstruct.py` 未开始**。
> 本章保留的是**设计口径**（当初为什么这么设计），不是"还没做"。

### 9.1 分级设计任务生成器（`engine/design/task_builder.py` —— 已实现，Sprint 5）

| 项目级别 | 任务类型 | 说明 |
|---|---|---|
| L1 | `module_identify` / `card_fill` / `flow_order` | 识别一级模块；给模块写释义；排一条主流程 |
| L2 | `module_split` / `card_fill` / `flow_design` | 一级 + 二级拆分；卡片填写；流程排序 |
| L3 | `multi_scenario` / `state_machine` / `boundary_refactor` / `compare` | 多场景推演；状态机设计；边界重构；两方案比较 |
| L4 | `full_design` / `multi_option` / `reconstruct` / `defense` | 完整架构设计；多方案权衡；重构挑战；答辩式总结 |

任务对象关键字段：`task_id` / `type` / `level` / `prompt` / `scenario` / `must_have[]`（含 `aliases`）/
`acceptable_alternatives[]` / `discouraged_patterns[]` / `forbidden_merges[]` / `required_relations[]` /
`required_edge_cases[]` / `rubric_weights` / `source: teacher_seed|auto_from_project` / `algorithm_version`。

> **`must_have` 从哪来？**
> ① 教师种子（`design_tasks.seed.json`，**首选**）；
> ② 从同类现有项目的域 / 能力清单**提炼 + 人工确认**；
> ③ **绝不**让 LLM 直接生成 `must_have` 并当成评分基准。
>
> **现状（优先级 3.5 一轮）**：① 已经有第一份真货 —— `lab_safety_assistant` 的
> `dt_lab_safety_assistant_L2_module_split`（10 项必备能力，逐项在种子的 `_evidence` 里
> 回指到源码文件与行号）；`python_dotenv` 仍然走 ②。
> ⚠️ **一个项目一旦有种子任务，它原有的自动任务就不再生成**（`task_builder.py:533-539`）——
> `lab_safety_assistant` 的设计任务因此由 3 个变 1 个。要给一个项目保留多道任务，就在种子里写多条。

### 9.2 RubricEngine：六维的可计算定义

> **这是整个培训功能里最容易做假的部分。** 下面的定义全部是确定性的、可复核的、无 LLM 参与。

#### 前置：学生模块 ↔ 必备能力的匹配（`matcher.py`）

```text
normalize(name) = 去掉『模块/管理/系统/的』→ 小写 → 全角转半角
match 优先级：
  ① 精确等于 name_cn 或任一 alias            → exact
  ② 一方包含另一方（长度 ≥ 2）                → contains
  ③ 中文 bigram + 英文 token 交集 / 并集 ≥ 0.5 → token
  ④ 未命中 → unrecognized_modules
```

**匹配结果必须三分类，绝不能二分类：**

| 类别 | 处理 |
|---|---|
| `matched` | 计入覆盖度 |
| `unrecognized` | **不计入覆盖度**，单独列为「系统未能识别，可能是命名不同，请教师 / 学生确认」 |
| `missing` | 明确未覆盖的必备能力 |

> **纪律**：反馈文案必须是「**未在设计中识别到**『设备状态』（可能是命名不同）」，
> 而不是「你漏了设备状态」。**词汇匹配必然有假阴性，措辞不能定罪。**

#### 六维可计算定义

| 维度 | 权重 | 可计算信号 | 不可计算时的状态 |
|---|---|---|---|
| **1 核心需求覆盖度** | 25% | `matched_must_have / total_must_have`；输出 matched / missing / unrecognized 三张清单 | `must_have` 为空 → `not_evaluated` |
| **2 模块职责清晰度** | 20% | ① `does_not` 空值率；② 单模块能力落在 `clusters.json` 中 ≥3 个不同簇 → 职责过载；③ 两个模块覆盖同一 `(verb_class, entity)` → 职责重叠；④ 模块数 : 覆盖能力数 ≥ 1:4 → 过粗 | 学生未填卡片 → `not_evaluated` |
| **3 层级结构合理性** | 15% | ① 一级模块数 vs 级别推荐区间；② 是否建立父子归属（只有一层且一级模块 > 8 → 建议分组）；③ 单子节点层级计数；④ 层级深度 > 3 → 过度分层 | 学生只画一层 → 降为「结构简化」提示，不给负分 |
| **4 依赖与流程完整性** | 20% | ① 有向图环检测（Tarjan SCC，输出环路径）；② `required_relations` 命中率；③ 无入边孤岛模块数；④ 连线指向不存在的模块（数据完整性）；⑤ 主流程是否可达「状态更新」节点 | 无连线 → `not_evaluated`（只报「未建立依赖关系」） |
| **5 异常与边界情况** | 10% | ① `required_edge_cases` 命中率（词典匹配）；② 学生卡片 `exceptions` 非空率；③ 是否出现「失败 / 拒绝 / 回滚 / 异常」词族 | 未填 → 按 0 计但标注 `not_filled` |
| **6 设计理由与证据** | 10% | **只衡量「可核查性」，不衡量「正确性」**：① 是否引用了图中真实存在的模块名；② 是否引用了 ≥1 条规则或状态；③ 声明的 `depends_on` 与画的边是否自洽；④ 字数是否在合理区间 | 未填 → `not_evaluated` |

> **优先级 3.5 一轮后，「哪些维度真的算得出来」在两个演示项目上不一样了**（别混着说）：
>
> | 维度 | `lab_safety_assistant`（有教师种子） | `python_dotenv`（自动提炼） |
> |---|---|---|
> | 1 核心需求覆盖度 | 按 **10 项教师确认的**必备能力算 | 按自动提炼的清单算（标「待教师确认」） |
> | 4 依赖与流程完整性 | **必备依赖命中率参与评分**（2 条） | 只报「本轮未评估」 |
> | 5 异常与边界情况 | **必备边界命中率参与评分**（2 个） | 只按「学生自己有没有给出异常」算 |
> | 结构偏好（替代结构 / 禁止合并） | **真的在判**（2 条替代结构 + 1 条禁止合并） | `available = False`，明确写「本轮不做结构偏好判定」 |
>
> 这一条决定了「设计层的分数有多少含金量」：**有种子那个项目的分数才是有依据的**。

#### 输出契约要点

```json
{"submission_id": "sub_001", "task_id": "dt_device_loan_L2",
 "evaluated_dimensions": 5, "total_dimensions": 6, "weights_renormalized": true,
 "overall_score": 71.5,
 "overall_note": "本轮评估覆盖 5/6 维，权重已按比例归一化；『层级结构合理性』因未建立层级关系未参与评分。",
 "dimensions": [
   {"key": "coverage", "name": "核心需求覆盖度", "weight": 0.25, "status": "evaluated", "score": 75.0,
    "findings": ["已覆盖 3/4 项必备能力：用户身份与权限、借用申请、设备状态"],
    "issues": ["missing:mh_return — 未在设计中识别到『归还处理』（可能是命名不同）"],
    "signals": [{"code": "COVERAGE_MISSING", "value": "mh_return"}]},
   {"key": "hierarchy", "name": "层级结构合理性", "weight": 0.15, "status": "not_evaluated",
    "score": null, "reason": "学生设计中所有模块均为一级，未建立父子关系",
    "issues": ["未建立层级关系，无法评估层级合理性；若模块数超过 8 个，建议分组"]}
 ],
 "algorithm_version": "rubric-1.0"}
```

#### 反馈生成（`feedback.py`）：信号码 → 中文模板，纯函数映射

| 信号码 | 模板 |
|---|---|
| `COVERAGE_MISSING` | 未在设计中识别到「{name}」（可能是命名不同），因此 {related_flow} 缺少承担者 |
| `CLARITY_OVERLOADED` | 「{module}」同时承担 {clusters} 三类职责，职责过重，建议拆分为 {suggest} |
| `CLARITY_OVERLAP` | 「{a}」与「{b}」都在做『{verb}{entity}』，职责重叠 |
| `CLARITY_NO_BOUNDARY` | 有 {n} 个模块未填写「不负责什么」，建议补上以明确边界 |
| `DEP_CYCLE` | 检测到循环依赖：{path}。循环依赖会让两个模块无法独立修改，建议引入第三方或反转依赖 |
| `DEP_ORPHAN` | 「{module}」没有任何模块依赖它，也没有依赖别人，需确认它在流程中的位置 |
| `EDGE_MISSING` | 未考虑『{case}』。例如设备已借出时应如何响应 |
| `RATIONALE_UNCHECKABLE` | 设计理由中提到的「{name}」不在你画的模块里，请确认两者是否一致 |

> **触发器与模板一一对应，模板不允许自由发挥。**
> 这样「反馈是硬编码的吧」这个问题就有了诚实且有力的答案：
> **反馈模板是固定的，但每一条是被学生设计里的哪个结构信号触发的，完全可复现、可讲清。**

### 9.3 重构挑战与影响范围（`reconstruct.py`，待建）

```text
输入：追加需求（模板化，如「现在增加教师审批」）
处理：
  1. 需求 → 结构变更描述（新增能力点 / 新增状态 / 新增角色）
  2. 计算「应受影响模块集合」：
       新增能力 → must_have 里语义最近的模块 + required_relations 指向的模块
       新增状态 → 状态写入该字段的现有能力点所在模块
       新增角色 → 涉及 identity / governance 簇的模块
  3. 学生提交改后设计 → 比对：新增模块数 / 新增或修改的依赖边 / 是否出现新的环 / must_have 覆盖度变化
  4. 输出：影响范围命中率 + 未识别到的连带影响 + 可扩展性评述（基于信号）
```

> **不做的事**：不自动判断「你的重构是否正确」。只报「你改了哪些、应改哪些没改、改完是否引入环」。

---
