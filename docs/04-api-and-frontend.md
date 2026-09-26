# 后端接口与前端架构（原 README 第十一、十二章）

> 更新触发：**加 / 改路由或改页面结构时** | 上次更新：WO-02 一轮（2026-09-26）
> 来源：原 `README.md` 第十一、十二章**整章搬移**；章节号不变（`§11.1` 已实现接口表、`§11.4` 待实现接口、`§12.1` 页面信息架构…）。
> **读它的时机**：加接口 / 加页面之前必读。
> ⚠️ **应用版本号只有一个来源**：`backend/app/main.py` 的 `version=`；文档不许自报另一个值（`verify_docs.py` 的 D3 会核对）。
> 业务逻辑分析平台那一套独立路由见 `docs/05-logic-platform.md`；跑起来的命令见 `docs/06-runbook.md`。

---

## 十一、后端接口（FastAPI，已实现）

**路由按域分文件**：`backend/app/routers/` 下的 `projects.py`（项目 / 图谱 / 源码切片）、
`grading.py`（判题）、`teaching.py`（阶段一 / 二 / 四·五 六个接口）、`analysis.py`（上传即分析）、
`logic_platform.py`（业务逻辑分析平台 13 个路由）；**`backend/app/main.py` 只做装配**
（app 创建 / CORS / `version=` / `include_router`）—— WO-02 一轮拆的，口径见
`docs/10-work-orders.md` §23.2。应用版本 `0.5.0`，契约版本 `1.0`。
**版本号只有一个来源**：`backend/app/main.py` 的 `version=`，本文档不再自报另一个值
（`scripts/verify_docs.py` 会核对这一条）。
启动：`cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`。

### 11.1 已实现接口

| 方法 | 路径 | 作用 |
|---|---|---|
| `GET` | `/api/health` | 健康检查（返回 `contract_version`） |
| `GET` | `/api/projects` | 项目列表（含是否有快照 / 答案表 / 源码） |
| `GET` | `/api/projects/demo` | 默认演示项目学生契约（兼容旧路径） |
| `GET` | `/api/projects/{id}/analysis?mode=student\|teacher` | 契约快照；`teacher` 模式才补回 `correct_answers` / `explanation` |
| `GET` | `/api/projects/{id}/business-graph` | 业务图谱 |
| `GET` | `/api/projects/{id}/business-graph/cards/{module_id}` | 单张模块卡片 |
| `GET` | `/api/projects/{id}/source?path=&start=&end=` | **源码切片**（只接受项目内相对路径；越界 / 缺失返回 404，不静默失败） |
| `GET` | `/api/projects/{id}/source-by-location?location=a.py:88-120` | 用引擎的 `location` 串取源码 |
| `POST` | `/api/projects/{id}/checkpoints/{i}/answer` | **后端判题**（不返回答案本身） |
| `POST` | `/api/projects/{id}/teaching/orientation/coverage` | **阶段一覆盖度比对**（自由文本 → 覆盖清单，不打分；`backend/app/routers/teaching.py:28`） |
| `GET` | `/api/projects/{id}/teaching/module-card/task` | **阶段二任务包**：五个问题 + 本项目全部模块卡片；**不下发任何比对键**（`backend/app/routers/teaching.py:50`） |
| `POST` | `/api/projects/{id}/teaching/module-card/coverage` | **阶段二事实覆盖比对**（逐问 matched / missed，不打分；`backend/app/routers/teaching.py:67`） |
| `GET` | `/api/projects/{id}/teaching/design/tasks` | **阶段四任务清单**：按复杂度级别（L1–L4）给任务类型；不含必备能力全文与权重（`backend/app/routers/teaching.py:92`） |
| `GET` | `/api/projects/{id}/teaching/design/task?task_id=&mode=` | **取一道设计任务**（题干 + 需求简报）；`mode=teacher` 才下发 `must_have` / 权重（`backend/app/routers/teaching.py:106`） |
| `POST` | `/api/projects/{id}/teaching/design/evaluate` | **阶段四 / 五：设计层六维评审**（`design_submission` → 六维报告；算不出来的维度 `not_evaluated`；`backend/app/routers/teaching.py:128`） |
| `POST` | `/api/analyze` | 上传 `.py` / `.zip` 实时分析 |
| `POST` | `/api/analyses/{analysis_id}/checkpoints/{i}/answer` | 实时分析结果的判题（`live_` 前缀） |

> 应用版本已升到 **`0.5.0`**（`backend/app/main.py`）：Sprint 3 加阶段一两个路由、Sprint 4 加阶段二两个路由、
> **Sprint 5 加阶段四 / 五三个路由**、**Sprint 6 加业务逻辑分析平台 13 个路由**（见第二十一章）。
> 「训练链路」接口总数 **17 个**（就是上表 17 行）；业务逻辑分析平台另有 **13 个**路由
> （`/api/logic-platform/*` 12 个 + 教师审核 1 个），**全应用合计 30 个**。
> 两者共用同一份 `business_graph`，不各自造一套。

### 11.2 判题的实现要点

```text
前端只拿到：checkpoint_id, 题干, 选项, node_id
前端提交：{answer}
后端判：  ├ 可判定题 → 比对 TracePlan / 事实表（纯规则，不调 LLM）
          ├ 覆盖度题 → 文本 → 事实关键词命中（不判对错，只回覆盖清单）
          └ 设计题   → RubricEngine
返回：    {result: correct|partial|wrong|coverage_only, hint, explanation, next_node,
           facts_covered: [], facts_missed: []}
```

> **上面这条「覆盖度题」分支的实现状态要说清楚**（2026-09 核实）：
> `project_store.grade_answer()`（`backend/app/services/project_store.py:272`）**只做选项集合比对**，
> 它没有、也不该有文本覆盖度分支；**文本覆盖度比对单独走教学通道，而且是两条**：
>
> | 阶段 | 接口 | 判定实现 | 口径 |
> |---|---|---|---|
> | 阶段一 | `POST /teaching/orientation/coverage` | `engine/teaching/coverage.py`（`orientation-coverage-1.0`） | `scoring = coverage_only` |
> | 阶段二 | `POST /teaching/module-card/coverage` | `engine/teaching/card_coverage.py`（`card-coverage-1.0`） | `scoring = fact_coverage_only` |
> | 阶段四 / 五 | `POST /teaching/design/evaluate` | `engine/design/rubric.py`（`rubric-1.0`） | `scoring = rubric_six_dimensions`（**有分数**） |
>
> 返回字段也不是 `facts_covered/facts_missed`，而是 `covered[] / missed[] / not_comparable[] / counts / caveats`
> （阶段二为逐问 `matched_keys / missed_keys / not_comparable_reason`；设计层为六维 `dimensions[]` + `signals[]`；字段见附录 A）。
> **旧文档里"覆盖度题由判题接口返回"的说法与代码不符，以本节为准。**
> 三条通道共用同一套命中判定（`coverage.py` 的 `prepare_text` / `add_comparison_key` / `key_hit`，
> 设计层经 `engine/design/matcher.py` 复用），**只有一个实现**——这是纪律，不是巧合。
> 另：`grade_answer()` 里**没有**「设计题 → RubricEngine」这条分支，设计评审单独走
> `POST /teaching/design/evaluate`（上面那段伪代码是设计意图，不是现状）。

### 11.3 答案的存放与边界

- 答案表只存后端：`backend/data/answer_keys/<project_id>.json`（教师预览才下发）；
- **学生契约里既没有 `correct_answers` 也没有 `explanation`**——讲解会直接点名正确答案；
- **离线模式在数据层面就无法判分**，不是 UI 上的一句免责声明。

### 11.4 待实现接口（P1 / P2）

| 方法 | 路径 | 作用 |
|---|---|---|
| `POST` / `GET` | `/api/sessions`、`/api/sessions/{sid}` | 学习会话创建与恢复 |
| `POST` | `/api/sessions/{sid}/events` | 记录阅读 / 看证据 / 提示 / 答题 |
| `POST` | `/api/sessions/{sid}/design-submissions` | 提交设计 → 返回六维评估（**内容已实现**：判定在 `engine/design/rubric.py`；缺的是"绑到会话"这层壳，见 16.3） |
| `PUT` | `/api/sessions/{sid}/design-submissions/{sub_id}` | 提交修订版 → 返回改进对比（**对比已在页面上实现**：第 2 次提交显示与上一轮对比；缺的是服务端留档） |
| `POST` | `/api/teacher/projects/{id}/business-graph/review` | 确认 / 拒绝 / 改名（写回 seed，记审核人与时间） |
| `PUT` | `/api/teacher/projects/{id}/business-graph` | 保存整图（含 `locked` 字段） |
| `POST` | `/api/teacher/gold-graphs` | 创建标准业务图谱 |
| `PUT` | `/api/teacher/design-tasks/{task_id}` | 编辑 `must_have` / alternatives / 权重（**当前只能改文件**：`engine/lexicon/design_tasks.seed.json`，没有在线编辑接口） |
| `GET` | `/api/teacher/projects/{id}/review-status` | 待审核项统计与源码哈希变更提示 |

### 11.5 存储策略（分期，不许宣称超期能力）

| 阶段 | 存储 | 能做什么 | 不能宣称什么 |
|---|---|---|---|
| P0（当前） | `localStorage` | 演示会话恢复、设计草稿、教师审核标记 | ❌ 不能宣称有班级管理 |
| P1 | 文件 / SQLite | 项目、图谱、教学计划、提交、事件 | ❌ 不能宣称有多用户权限 |
| P2 | SQLite + 账号 | 班级、作业、学生进度看板 | — |

> 后端现状最诚实的一句话：**FastAPI 骨架 + 分析接口 + 演示数据接口（无鉴权、无数据库、无任务队列）。**

---

## 十二、前端架构

### 12.1 页面信息架构（8 页，对应第四章六阶段）

```text
① 项目总览 Overview        → 项目要解决什么 / 服务哪些角色 / 一级域 / 复杂度徽章
② 业务模块树 ModuleTree    → 一级域 → 二级功能点 → 动作，可展开；点击进卡片
③ 模块卡片 ModuleCard      → 卡片全字段 + 事实证据 + 五问作答区
④ 流程推演 FlowSim         → 场景选择 → 拖拽排序 → 第一分歧点 + 证据
⑤ 设计画布 DesignCanvas    → 拖拽建模块 / 连线 / 填卡 / 提交
⑥ 六维评审 RubricReport    → 六维明细 + 状态（已评估 / 未评估）+ 改进建议 + 迭代对比
⑦ 重构挑战 Reconstruct     → 追加需求 → 改设计 → 影响范围命中
⑧ 能力报告 CapabilityReport→ 行为与覆盖度汇总（不给「总分证明掌握」）
   贯穿：证据弹窗 / 置信度徽章 / 复杂度徽章 / 教师审核条
```

> **这 8 页信息架构还没做**（`vue-router` 深链属于 B 阶段，见 16.3）。
> 当前是「A 方案」：在 `TrainingView.vue` 里用页签切**五个阶段**——
> **项目认知（阶段一）/ 模块卡片（阶段二）/ 设计画布（阶段四 + 五）/ 训练关卡（四关训练，默认）/ 业务图谱**。
> 五个阶段都是 `v-if` 懒挂载：只做训练时不发图谱请求，也不会把图谱正文混进训练页文本
> （浏览器走查用 body 文本做断言，混进来会造成假失败）。
>
> **UI 重设计一轮起，默认落地页是「系统主页面」**（`frontend/src/views/HomeView.vue`）：
> `App.vue` 的 `currentView` 初值是 `home`，它只回答一个问题——"这个系统能做哪两件事、从哪儿进去"。
> 两大核心功能各占半屏（培训系统 · 六阶段 / 业务逻辑分析平台），六阶段入口里**只有已落地的阶段可点**
> （未开始的渲染成 `disabled`，不给入口），次级入口收成小模块，「来源依据与口径」默认收起
> （证据一条都没删，只是不在第一屏）。
> **工作区内部的默认阶段仍是「训练关卡」**：主页面靠 `TrainingView.vue` 的 `initial-stage`
> （取值 `orientation` / `module-card` / `design` / `training` / `graph`）落到指定阶段，
> 省略时等价于 `training`，所以既有走查与演示动线不变。
> 工作区里那五个页签按**模块层级**分成两组：「**阶段主线**」= 六阶段教学（① 项目认知 /
> ② 模块卡片 / ④⑤ 设计画布）、「**项目视图**」= 训练关卡 + 业务图谱；`data-test` 钩子一个没改。
> 原来直接铺在页签旁边的口径说明收进可折叠抽屉（`data-test="stage-scope-toggle"` /
> `stage-scope-body`），内容按当前阶段切换。
>
> 浏览器走查（`scripts/browser_clickthrough.mjs`）随之按**真实用户路径**走：先断言主页面
> （默认落地、两大核心功能的入口、六阶段只给已落地的按钮、来源依据默认收起且能展开收起），
> 点进培训工作区后再跑原有环节，工作区那 13 个环节的断言一个字没改。
> UI 重设计一轮实跑：在线 **109/109**（`lab_safety_assistant` / `python_dotenv` 各一次）、
> 离线 **55/55**（旧值 99/99 与 45/45）——**走查属 `node` 组，验收报告默认不跑、不含它的数字**，
> 口径见 `docs/07-status-and-acceptance.md` §17.2 与 `validation/acceptance_latest.md` 的「本次未跑」表。
>
> 对应关系（据实，别混）：`项目总览 ①` ≈ 阶段一（已做，但不是独立页面）；
> `模块卡片 ③` ≈ 阶段二的作答区（已做，但没有 `ModuleCardEditor` 那种编辑能力）；
> **`设计画布 ⑤` 与 `六维评审 ⑥` 已做**（`StageDesign.vue`：拖拽建模块 / 连线 / 填卡 / 提交 / 六维明细 / 迭代对比，
> 但它是页签里的一个视图，不是独立路由页面）；
> `业务模块树 ②` 目前并进「业务图谱」页签；`④ 流程推演 / ⑦ 重构挑战 / ⑧ 能力报告` **一个都没有**。

### 12.2 路由决策

**现状**：没有 `vue-router`；`App.vue` 用 `currentView` 在**四个顶层视图**之间切换——
`home`（系统主页面，UI 重设计一轮起是**默认值**）/ `training`（培训工作区，内含五个阶段页签）/
`logic-platform`（业务逻辑分析平台）/ `analysis`（旧版函数级分析详情）；
`DeepAnalysisView` 嵌在 `TrainingView.vue` 里；`UploadView.vue` 已作为死代码删除。

**决策：分两步，不要一次性重写外壳。**

| 阶段 | 做法 | 成本 |
|---|---|---|
| **A（已做）** | 保留 `App.vue` 外壳；顶层多了一个默认视图 `home`（`HomeView.vue`：两大核心功能 + 次级入口 + 可折叠的证据抽屉）；在 `TrainingView` 内引入**阶段状态机**，用 `v-if` 切换子组件（当前**五个**页签：`orientation` 项目认知 / `module-card` 模块卡片 / `design` 设计画布（阶段四·五）/ `training` 训练关卡 / `graph` 业务图谱；页签按模块层级分「阶段主线 / 项目视图」两组，`initial-stage` 决定进工作区时落哪个阶段，**默认仍是 `training`**）。**工作区内部的机制没有变** | 低 |
| **B（时间允许再做）** | 引入 `vue-router`，把 8 个阶段变成可深链的路由（答辩时能直接跳页） | 中 |

> **A 阶段是必做，B 阶段是加分。** 不要为了「架构漂亮」重写外壳。

### 12.3 组件清单与复用判定

入口层补充：`HomeView.vue` 现在复用 `LoginDialog.vue` 提供本地演示登录，复用 `QuickSearch.vue` 提供 `/` 快捷搜索。搜索结果只引用已有契约和页面状态；选中业务模块时通过 `TrainingView.initialModuleId` → `BusinessGraphView.initialModuleId` 打开已有模块卡片，不改变图谱数据或判定逻辑。登录的本地存储边界与诚实说明见 `docs/features/login-and-quick-navigation.md`。

| 组件 | 现状 | 判定 |
|---|---|---|
| `App.vue` / `AppHeader` / `Sidebar` | 可用；`App.vue` 现在切**四个顶层视图**（`home` 系统主页面（默认）/ `training` 培训工作区 / `logic-platform` / `analysis`） | **复用** |
| `HomeView.vue` | 🆕 **新**（UI 重设计一轮）：**系统主页面**（App 的默认落地页）。顶部条 + 身份区（定位一句话 + 项目切换器 + 契约事实条：当前项目 / 契约版本 / 训练题数 / 业务模块数，全部来自 `loadContract`）→ 两大核心功能各占半屏（`home-core-training` 培训系统 · 六阶段 / `home-core-logic` 业务逻辑分析平台 · 六步流程 + 三句口径立场）→ 次级入口小模块（业务图谱 / 函数级分析详情 / 来源依据与口径）→ 「来源依据与口径」默认收起（5 组依据 + 本次运行的实际来源，**证据一条没删，只是不在第一屏**）。页面自己**不算任何业务结论**：数字只用契约字段与数据源模式判定 | **复用**（页面层入口） |
| `TrainingView.vue` | 四关固定题外壳 + 阶段切换（共五个页签）。UI 重设计一轮：① 五个页签按**模块层级**分**两组**——「阶段主线」（① 项目认知 / ② 模块卡片 / ④⑤ 设计画布）+「项目视图」（训练关卡 / 业务图谱），`data-test` 钩子一个没改；② 原来直接铺在页签旁边的口径说明收进可折叠抽屉（`stage-scope-toggle` / `stage-scope-body`，内容按当前阶段切换）；③ 新增 `initial-stage` prop（`orientation` / `module-card` / `design` / `training` / `graph`，**默认仍是 `training`**），系统主页面的六阶段入口靠它直接落到对应阶段；④ 答题卡的题面与选项按 `--i` 层次滑入 | **拆分**：外壳保留为阶段容器，业务内容外移 |
| `StageOrientation.vue` | ✅ 已实现（Sprint 3）：阶段一项目地图 + 自由文本作答 + 覆盖清单（提交前不渲染反馈） | **复用** |
| `StageModuleCard.vue` | ✅ 已实现（Sprint 4）：阶段二卡片选择 + 五问作答 + 逐问事实覆盖清单；题目与字段映射来自后端的 `stage_questions` 词典 | **复用** |
| `BusinessGraphView.vue` | ✅ 已实现：域树 / 功能点 / 卡片面板 / 流程场景 / 证据弹窗 | **复用** |
| `ModuleCardPanel.vue` | ✅ 已实现：`objective` / `does_not` / 四类事实 / 上下游 | **复用** |
| `ComplexityBadge.vue` | ✅ 已实现：级别 + 七维明细 + 公式 + 阈值表 | **复用** |
| `ConfidenceBadge.vue` | ✅ 已实现（`verified \| inferred \| inferred-low \| unconfirmed`） | **复用** |
| `FlowScenarioList.vue` | ✅ 已实现：三型场景 + 生命周期流程排最后 | **复用** |
| `SourceViewerModal.vue` | ✅ 已改造：完整相对路径 + 行号区间 + API / 离线徽章；失败显式报错 | **复用** |
| `DeepAnalysisView.vue` | 深度分析 + 业务优先级 + 教师审核（2082 行，最大文件） | **复用**，作为「证据 / 理解层」入口 |
| `FlowchartView.vue`（mermaid） | 只读渲染 | **复用**为流程示意图；**不用于画布** |
| `QuizView` / `OverviewView` / `KnowledgeView` / `PatternsView` / `CodeView` | 服务于旧函数级 demo | **降级保留**，不进主叙事 |
| `stores/learningSession.js` | ✅ 已实现：会话按 `project_id` 持久化 | **复用** |
| `composables/useReveal.js` | 🆕 **新**（UI 重设计一轮）：**层进式动画的唯一实现**（`armLayeredReveal(root, opts)` / `useLayeredReveal(rootRef, {watchSource})`）。约定：**默认可见**——只有浏览器支持 `IntersectionObserver` 时才给 `[data-layer]` 元素加 `.layer-armed`、进入视口时加 `.is-in`；不支持时什么都不做（内容照样完整可见，不会白屏）。视觉规则在 `src/style.css` 的 `[data-layer]` 一节，含 `prefers-reduced-motion` 兜底 | **复用**（主页面 / 培训工作区 / 逻辑平台共用） |
| `StageDesign.vue` | ✅ 已实现（Sprint 5）：`DesignCanvas`（原生 drag + 手写 SVG）/ 模块卡片编辑 / `RubricReport`（六维报告）/ 迭代对比**合并在这一个组件里** | **复用**（当初 §12.3 列为「待建」的这三件已随它落地） |
| `logic-platform/EvidenceFold.vue` + `EvidenceNote.vue` | 🆕 **新**（证据折叠一轮）：折叠容器 + 口径说明。`EvidenceFold` 的约定是**收起用 `.drawer-body`（高度归零），不是 `v-if`** —— 收起状态下内容仍在 DOM 里（`data-open` 只是状态标记）；数量写在折叠头上；`defaultOpen` 只在"这里出事了"时置真（被拦截的断言 / 有失败的校验明细）。`EvidenceNote` 的约定是**摘要常驻 + 详述收起**，它刻意不接收"是否显示"（口径说明不许被关掉）。两个组件同时被 `ImmersiveLesson.vue` 与 `VerificationPanel.vue` 复用 | **复用**（逻辑平台讲稿页 / 反幻觉面板） |
| `ModuleCardEditor` | ✅ 已实现（并入 `StageDesign.vue` 的右侧编辑面板） | **复用** |
| **待建** `FlowSimulation` / `ReconstructChallenge` / `CapabilityReport` / `TeacherReviewBar` | — | 新增（阶段三 / 阶段六 / 能力报告 / 教师工具条） |

> **样式成本评估（据事实）**：Tailwind + `tailwind.config.js` 的 token + `src/style.css` 的语义类
> （`.glass-card` / `.tab-btn` / `.tree-item` / `.code-line` / `.quiz-option` / `.stat-number` / `.progress-bar` …）
> 已经能保证**观感一致**，成本低。但仓库**没有**布局壳、表单、表格、时间线、树、画布基础组件——
> 每页的**结构**都要新写。估算时按「结构成本高、样式成本低」来算。仅暗色单主题。

### 12.4 设计画布技术选型

| 方案 | 成本 | 风险 | 建议 |
|---|---|---|---|
| **原生 HTML5 drag + 手写 SVG 连线** | 低（1 个组件内完成） | 需自己处理坐标、命中测试；移动端不友好 | ✅ **首选**——仓库已有先例：`DeepAnalysisView` 的架构图 / 调用图 / 状态机、`TrainingView` 的雷达图**都是手写 SVG** |
| `@vue-flow/core` | 中（加 1 个直接依赖） | 需与暗色主题适配 | 🟡 备选 |
| `mermaid` 渲染 | 低 | **只读，不能拖拽** | ❌ 不用于画布 |

> ⚠️ `package-lock.json` 里出现的 `cytoscape`、`d3`、`dagre`、`katex` **全是 `mermaid` 的传递依赖**，
> 不能被当成可用依赖直接 import（升级 mermaid 就会消失）。

**画布最小功能集（一档）：**
添加模块（双击空白处）→ 拖动节点；双击改名；节点右上角删除；
从节点边缘拖到另一节点建立有向连线（SVG 贝塞尔 + 箭头）；点击连线选中并删除；
选中节点 → 右侧卡片编辑面板；「提交」→ 生成 `design_submission.json` → 调评审接口 → 显示六维结果；
修改后再次提交 → `iteration + 1`，显示与上一轮的对比。

> **以上最小功能集已实现**（Sprint 5，`frontend/src/components/StageDesign.vue`），
> 并且**每一条都有走查断言**（`scripts/browser_clickthrough.mjs` 第 16 节）：
> 加节点 / 改名回写 / 拖动建立 SVG 连线 / 点线选中后按钮变「删除选中连线」/ 填卡片 / 提交 /
> 六维渲染 / 未评估维度不显示 0 / 第 2 次提交 iteration 递增且出现对比条。
> 节点坐标存在数据里、连线路径由坐标算出（不依赖 DOM 测量），所以在 jsdom 里也能被断言。
> **没做的**：拖拽成组、自动布局、撤销/重做、多选框选、连线类型选择（只有 `uses`）。

### 12.5 证据查看器（「可定位」的技术落点）

```text
1. 契约里的 file 一律为项目内相对路径（POSIX /）；
2. 优先走后端 GET /api/projects/{id}/source?path=&start=&end=；
3. 演示环境（离线）走 /demo/projects/{project_id}/source/<相对路径>，
   并在前端按同一 start-5 / end+5 窗口切分；
4. 弹窗顶部显示【完整相对路径 + 行号区间】，不只显示文件名；
5. 找不到文件 → 明确报「该项目未提供源码，无法跳转」，不许静默失败。
```

### 12.6 「学生先输出，系统后反馈」的交互契约

所有训练页必须满足（否则训练退化成阅读）：

1. 先渲染问题与输入区，**隐藏任何答案 / 结论**（反馈区域在提交前不渲染）；
2. 学生提交后，才渲染反馈区域；
3. 反馈区域必须先给「你提到了什么」（覆盖清单），再给「你还没提到什么」；
4. 任何「推断级」的参考答案都必须带徽章，并注明「待教师确认」；
5. 提示分层：第 1 层指向范围 → 第 2 层指向模块 → 第 3 层指向字段；每层都消耗一次提示计数；
6. 所有事件写入会话（`viewed_evidence` / `hint_used` / `answered`），供能力报告使用。

> **第一条与第三条的第一个落点：阶段一「项目认知」（Sprint 3）与阶段二「模块卡片学习」（Sprint 4）**。
> 它们把这份契约变成了可被脚本检查的事实：
> 反馈区在提交前**一个 DOM 节点都没有**（`StageOrientation.vue:145` 的 `v-if="report"`，
> 阶段二同构），走查脚本在提交前直接断言 `[data-test="orientation-report"]` 不存在；
> 提交后先给「你已经提到的」，再给「你还没有提到的」，
> **两份清单之外没有分数、没有标准答案**（`data-test="orientation-no-score"` /
> `module-card-no-score`）。
> 阶段二还额外满足第 4 条：卡片上 `unconfirmed` 的字段不参与比对，页面显示
> `module-card-needs-review`「该卡片待教师确认」。
> 阶段三~六仍只有契约，没有实现——**不要把这一条读成"六阶段都做到了"**。

### 12.7 状态管理（Pinia）与会话恢复

已有：`stores/analysis.js`、`stores/quiz.js`、`stores/learningSession.js`。
待建：`businessGraph.js`（图谱 + 选中模块 + 置信度过滤）、`designCanvas.js`（nodes / edges / dirty）、
`rubric.js`（最近一次评估 + 历史对比）、`teacherReview.js`（审核模式 + 审核状态）。

> **Sprint 5 的现状**：设计画布的状态（`nodes` / `edges` / `rationale` / `selection`）**仍在组件内**
> （`StageDesign.vue`），草稿持久化沿用阶段一的同构做法
> （`localStorage['lwai.design.draft.<project_id>.<task_id>']`），**没有建 `designCanvas.js` / `rubric.js`**；
> 迭代对比用的是组件内的 `history` 数组，不跨刷新。
> 也就是说：**上表的四只 store 一只都还没建**，别把这里读成"已经抽出来了"。

**会话恢复契约：**

```json
{"session_id": "...", "project_id": "...", "business_graph_version": "bg-1.0",
 "source_hash": "sha256:...", "stage": "design_canvas",
 "answers": {}, "design": {}, "evaluation_history": [], "updated_at": "..."}
```

`source_hash` 或 `contract_version` 不匹配 → 提示「教学材料已更新，请重新开始或继续（部分进度需重做）」，
**不静默沿用**。

---

# 第三部分 · 纪律、边界与对外表述
