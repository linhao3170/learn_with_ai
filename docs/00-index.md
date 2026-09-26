# 文档索引与 AI 交接协议

> 更新触发：**很少改**（文档增删 / 交接流程变化 / 门禁命令变化才动） | 上次更新：部署说明一轮（2026-09-26：新增 `docs/11-deployment.md` 并登记进清单）
> **这一份是给"接手的人或 AI 助手"的第一份文档**：读完它就知道该读什么、改哪里、怎么算改完、什么绝对不许做。
> 项目是什么见 `README.md`；现在做到哪一步见 `docs/07-status-and-acceptance.md`。

---

## 一、这个项目是什么（30 秒版）

**LearnWithAI**：把一份真实代码库变成「业务图谱 + 代码证据」，再用六阶段教学流程带学生从"看懂代码"走到"自己会设计"。

- **两半**：① 业务逻辑分析（代码 → 业务图谱，规则引擎、可复现、无 LLM 判定）；② 培训功能（六阶段：项目认知 / 模块卡片 / 流程推演 / 设计画布 / 六维评审 / 重构挑战）。
- **卖点**：可复现（同一输入字节级相同）、可定位（每个结论回指 `文件:行号`）、可沉淀（教师种子 + 词典外置）。
- **技术栈**：Python 3.12 + FastAPI（`backend/`）+ Vue 3 + Tailwind（`frontend/`）+ 纯规则引擎（`engine/`）。

---

## 二、文档清单（每份的职责 / 更新触发 / 依赖）

| 文档 | 职责（它唯一拥有的事实） | 更新触发 | 依赖 / 上游 |
|---|---|---|---|
| `README.md` | 定位一句话、**写作纪律（含"改完同步哪几处"对照表）**、五分钟上手、收尾语 | 每轮只改 1~3 行 | — |
| **`docs/00-index.md`**（本文） | 文档地图、**AI 交接协议**、门禁与完成定义、禁止事项、代码地图 | 文档增删 / 流程变化 | — |
| `docs/01-teaching-design.md` | 培养目标、双层图谱、多级模块、六阶段、复杂度分级、教师角色 | 很少改 | — |
| `docs/02-architecture.md` | 七条设计原则、分层架构、目录结构、图谱流水线、词典、设计层六维口径 | 很少改 | `01` |
| `docs/03-contracts.md` | 统一数据契约、**字段可见性矩阵**、附录 A 字段速查 | 契约变更时 | `02` |
| `docs/04-api-and-frontend.md` | 路由表、接口边界、页面信息架构、组件清单、交互契约 | 加接口 / 改页面时 | `03` |
| `docs/05-logic-platform.md` | 业务逻辑分析平台（流程 / 分级策略 / 四层防幻觉 / 路由 / 自检） | 该平台变动时 | `02` `03` |
| `docs/06-runbook.md` | 命令手册、产物生成、排障、沙箱与环境约束（`§19.5`） | 加脚本 / 环境变时 | 全部 |
| `docs/07-status-and-acceptance.md` | **现状台账 / 验收记录 / 下一步优先级（唯一权威）**、附录 B 早期数据 | **每轮** | 全部 |
| `docs/08-tech-debt.md` | 技术债台账、被真实数据纠正的设计错误、反直觉但必要的实现 | **每轮** | 全部 |
| `docs/09-discipline-and-defense.md` | 表述纪律（不许说 vs 应该说）、红线、风险、答辩动线与预案 | 很少改 | `07` |
| `docs/10-work-orders.md` | **并行工单与执行编排**：把 `§16.2` / `§16.3` / `§19.1` 里还没做的事拆成 `WO-01` ~ `WO-15` + 集成轮，写明独占文件、波次顺序、验收命令与发单模板（**它不是第二份「下一步」**，优先级以 `§18` 为准） | 工单增删 / 波次调整时 | `07` `08` |
| `docs/11-deployment.md` | **部署说明**（第二十五章）：支持 / 未做的部署形态、拓扑与端口、前置依赖、`bootstrap.ps1`、两条部署路径（单机双进程 / 静态产物 + 跨源）、装完自检、数据与可写目录、环境变量、**安全边界（无鉴权 → 不许上公网）**、更新部署与排障索引 | 启动方式 / 构建产物 / 端口 / 依赖 / 反代变了才动 | `06` `04` |
| `docs/90-archive.md` | 旧文档 / 旧代码与产物的处置记录（一次性历史） | 几乎不改 | — |
| `docs/features/_TEMPLATE.md` | **单个功能的设计卡模板**：目标 / 不变式 / 契约 / 判定口径 / 学生可见性 / 验收命令 / 诚实边界 / 待教师填 | 每做一个功能填一篇 | `02` `03` `07` |
| `docs/features/ui-shell-redesign.md` | **系统主页面与界面重设计**（默认落地页 / 两大核心功能大模块化 / 可折叠的来源依据 / 链式拉动与层进式动画） | 这个界面结构或动画约定变动时 | `04` `07` |
| `docs/features/evidence-fold.md` | **证据折叠与口径说明**（讲稿逐条证据与反幻觉面板明细默认收起 / 摘要常驻 + 详述收起 / 失败默认展开 / 折叠自查脚本） | 这个折叠口径或自查断言变动时 | `04` `05` `07` |
| `docs/features/login-and-quick-navigation.md` | **登录入口与统一搜索**（本地演示登录 / `/` 搜索 / 业务模块快捷跳转） | 登录、搜索或快捷跳转行为变动时 | `04` `07` |
| `docs/_bundle.md` | **机器生成**的单文件合集（`python scripts/pack_docs.py`），供一次性投喂；**不要手改** | 由脚本重建 | 全部 |

> **章节号刻意保持不变**：`§16.1` 仍然叫 16.1，只是住在 `docs/07`。
> 于是正文与代码里既有的 `§16.1` / `§19.2` / `§21.3` 这类引用仍然指得到东西 ——
> `scripts/verify_docs.py` 的 D2 会在**整个文档集**上解析引用，并报告跨文件引用的规模。
> 阶段 3 会把它们换成稳定 ID（`R-` / `D-` / `A-` 编号），替换完成前**不要重排章节号**。

---

## 三、AI 助手交接协议（接手前必读）

### 3.1 第一件事：先跑门禁，别先改代码

**换了机器 / 刚克隆下来**：先跑 `powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1`
把环境装齐（建 `.venv` + 装两份 requirements + 前端 npm ci + 生成演示快照），再跑下面这三条。

```bash
python scripts/build_acceptance_report.py    # 跑 13 个只读验收脚本 → validation/acceptance_latest.md（数字的唯一来源）
python scripts/verify_docs.py                # 文档门禁：路径 / 章节引用 / 版本号 / 数字 / 行号锚点（exit 1 = 有问题）
python scripts/verify_sprint0.py             # 总验收 A1–A11（进程内跑完，秒级到分钟级）
```

`validation/acceptance_latest.md` 是**最近一次实跑数字的唯一来源**。**不许**把数字抄进文档
（`verify_docs.py` 的 D4 会核对：文档里的数字与报告不一致就直接 ERROR）。看 `--list` 可知道哪些脚本没跑：

```bash
python scripts/build_acceptance_report.py --list
```

### 3.2 硬约束（违反即算 bug，不是"风格问题"）

1. **七条设计原则**（`docs/02-architecture.md` §7）：单向依赖、结论带置信度与证据、业务词汇外置、规则判事实 + 教师判语义 + LLM 只做映射润色、可计算才评分、演示可复现可降级、同一输入字节级相同输出。
2. **学生视图安全边界**（`docs/03-contracts.md` §10.5）：`correct_answers` / 内部 key（`mh_*`）/ `_inferred_` / 内部标记**一律不许进学生视图**；有断言与脚本在盯。
3. **算不出来不许填分**：算不出来的维度返回 `not_evaluated`（`score = null` + `reason`），唯一例外是"未填 → 按 0 计并标 `not_filled`"（`docs/02-architecture.md` §9.2）。
4. **判定不许交给 LLM**：LLM 只能做讲解/润色，且默认关闭；任何"对错判定"必须来自规则引擎或人。
5. **不许在自造样本上报告准确率**：`sample_projects/lab_safety_assistant` 是自造样本；准确率只能来自真实第三方项目的人工核对，而**人工判定列目前仍未填**（`docs/07` §18 优先级 2 有理由与触发条件）。
6. **不许出现两份"下一步"**：执行口径只有 `docs/07-status-and-acceptance.md` §18。
7. **不许把没做的说成做了**：做不到的直接写出来；这条是整个项目的纪律基础（`README.md` 顶部）。

### 3.3 一次改动的完成定义（缺一项就是没做完）

| # | 要求 | 证据 |
|---|---|---|
| 1 | 行为/代码改了 | 代码 diff |
| 2 | **跑了验收** | `python scripts/build_acceptance_report.py` 全绿；数字写进报告，不写进文档 |
| 3 | **同步了该同步的文档** | 对照 `README.md` 顶部「改完必须同步哪几处」表；每轮的现状/债/验收记进 `docs/07`、`docs/08` |
| 4 | **文档门禁通过** | `python scripts/verify_docs.py` exit 0 |
| 5 | **新增脚本/命令登记** | `docs/06-runbook.md` 工具表 + `docs/07` §17.2 命令清单 + `README.md` §0.3 |
| 6 | 新的判定口径/检查脚本 | **带负向对照**（故意造一个失败用例，确认它真能报错，见 `docs/08` §19.2 ⑱⑳ 的做法） |
| 7 | 轮次留痕 | 用「<主线名> 一轮」命名，不写"本轮"（`README.md` 顶部约定） |

### 3.4 禁止事项（这些做法在本仓库被明令禁止）

- ❌ 为了让演示好看而**填假分 / 编业务含义 / 编干扰项**（`docs/01` §4、`docs/02` §8.3、`docs/09` §13.1）。
- ❌ 把**没跑过的数字**写成"最近一次实跑"；把历史值裸写（要写就写「历史：<轮次>」）。
- ❌ 手抄验收数字到文档里（只允许写"见 `validation/acceptance_latest.md`"，或写经门禁核对过的数字）。
- ❌ 把自动划分的图谱说成"已验证的业务图谱"；把自造样本上的指标当成绩报。
- ❌ 在浏览器里另算一份分数/题目（会出现第二份定义，违反"只有一份实现"）。
- ❌ 重排章节号（会断掉一片引用，包括代码注释里的）；替换成稳定 ID 之前不动。
- ❌ 为了"架构漂亮"重写前端外壳（`docs/04` §12.2 明确：B 阶段是加分，不是必做）。
- ❌ 顺手删"看着像旧的"东西：`docs/90-archive.md` 的「查过但确认不能删」表列了不能删的项。

### 3.5 已知死指针（别当成待修 bug 盲改）

- **代码里约 196 处**引用已删除的旧文档（`README5 §3.2`、`README4 §9.2` 这类）。它们是历史出处标注，**不影响运行**；阶段 3 会统一换成稳定 ID。
- **约 92 处跨文件 `§X.Y` 引用**（README ↔ docs）—— 现在靠"章节号不变 + 全文档集解析"维持有效。
- `scripts/verify_docs.py` 会如实报告这两类的规模：先跑它，别猜。

### 3.6 代码地图（改之前先知道东西在哪）

| 目录 | 内容 | 关键入口 |
|---|---|---|
| `engine/parser/` | Python AST 解析 + 缓存 | `python_parser.py` / `ast_cache.py` |
| `engine/deep_analyzer/` | 项目级调用图 / 状态 / 流程 / 依赖强度 / 架构 / 关键实现 / BLPS | `project_call_graph.py` |
| `engine/business_graph/` | **业务图谱五步流水线**（单元 → 一级域 → 二级功能点 → 事实 → 卡片关系）+ 复杂度 + 场景 + 教师种子合并 | `builder.py` |
| `engine/teaching/` | 阶段一覆盖度、阶段二事实覆盖（**共用同一份命中判定**） | `coverage.py` |
| `engine/design/` | 阶段四 / 五：任务生成 / 匹配 / 结构检查 / 替代结构 / 契约归一化 / 六维评审 / 反馈渲染 | `rubric.py`（`reconstruct.py` **待建**） |
| `engine/logic_platform/` | 业务逻辑分析平台（分级 / 板块 / 讲稿 / 校验） | `tiering.py` / `verify.py` |
| `engine/lexicon/` | **唯一允许出现业务词的地方**（20 份 JSON，含教师种子） | — |
| `backend/app/` | FastAPI 路由（唯一路由文件 `main.py`）+ 教学服务 + 判定与答案表 | `main.py` / `services/teaching_service.py` |
| `frontend/src/` | Vue 3 页面与组件（无 `vue-router`，用 `v-if` 切换顶层视图与阶段） | `views/HomeView.vue`（**系统主页面，默认落地页**）/ `views/TrainingView.vue`（五阶段工作区）/ `components/StageDesign.vue` / `composables/useReveal.js`（层进式动画唯一实现） |
| `scripts/` | 验收、门禁、产物生成、报告工具 | `verify_sprint0.py` / `build_acceptance_report.py` / `verify_docs.py` |
| `validation/` | **证据层**：实测报告、事实表、人工核对模板（每个数字都要能回指到这里，**不许删**） | `acceptance_latest.md` |
| `sample_projects/` · `validation/{python_dotenv,flask,urllib3}` | 演示项目（1 个自造 + 3 个真实第三方） | — |

### 3.7 契约与版本（数字只有一个来源）

- **应用版本**：`backend/app/main.py` 的 `version=` —— 文档里不许自报第二个值（门禁 D3 会核对）。
- **契约版本**：`contract_version = "1.0"`（`engine/business_logic/models.py`）。
- **算法版本**：每个产物都带 `algorithm_version`（如 `orientation-coverage-1.0` / `card-coverage-1.0` / `design-matcher-1.0` / `rubric-1.0` / `complexity-1.1`），改算法口径就要动版本号。
- **源码版本**：产物带 `source_hash`；重新分析后哈希变化，旧的审核/结论必须标 `stale`，不许静默覆盖。

---

## 四、按任务选读（别一次读全部）

| 你要做的事 | 最小必读集 |
|---|---|
| 改一个已有功能的实现 | `docs/features/<该功能>.md`（若有）→ `docs/02-architecture.md` → `docs/03-contracts.md` §10.5 → `docs/07` §16 对应行 |
| 加一个新功能 | `docs/01`（它服务哪个阶段）→ `docs/02` §7/§8 → 新建 `docs/features/<功能>.md`（照 `_TEMPLATE.md`）→ 加验收脚本 → 登记 `docs/06` |
| 改接口 / 加路由 | `docs/04-api-and-frontend.md` → `docs/03` 契约 → `backend/app/main.py` |
| 改前端页面 | `docs/04` §12 → `frontend/src/` → 走查脚本 `scripts/browser_clickthrough.mjs` |
| 改业务图谱算法 | `docs/02` §8.3~§8.9（含确定性纪律）→ `engine/business_graph/` → `scripts/test_business_graph.py` + `check_determinism.py` |
| 改评分口径 | `docs/02` §9.2（六维定义与唯一例外）→ `docs/09` §13（不许说的话）→ `scripts/test_design_rubric.py` |
| 要让评委/答辩能讲 | `docs/09-discipline-and-defense.md` → `docs/07` §17 口径说明 |
| 排障（跑不起来） | `docs/06-runbook.md`（先看 §19.5 环境约束） |
| **换机器部署 / 局域网演示 / 判断能不能对外开** | `docs/11-deployment.md`（支持什么、怎么装、装完怎么验、**为什么现在不能上公网**） |
| 清理代码/产物 | `docs/90-archive.md` 的「不能删」表 + `docs/08` §19.1 台账 |

---

## 五、当前状态与下一步（指针，不重复内容）

- **做到哪一步了**：`docs/07-status-and-acceptance.md` §16（已完成 / 部分完成 / 未开始）。
- **验收最后怎么跑的**：`validation/acceptance_latest.md`（机器生成）。
- **还没做的**：阶段三（流程推演）与阶段六（重构挑战）、`engine/design/reconstruct.py`、`teaching_plan.json`、学习会话与存储层、教师 Gold Graph 编辑器、`vue-router` 深链、人工图谱核对（唯一能产出「准确率」的途径，已决定延后到引擎冻结之后）。
- **要把这些活同时派给多个 AI 助手**：看 `docs/10-work-orders.md` —— 逐条工单、每单的独占文件与验收命令、波次与并行规则、可直接复制的发单模板都在那一份里。
- **还没做的**：阶段三（流程推演）与阶段六（重构挑战）、`engine/design/reconstruct.py`、`teaching_plan.json`、学习会话与存储层、教师 Gold Graph 编辑器、`vue-router` 深链、人工图谱核对（唯一能产出「准确率」的途径，已决定延后到引擎冻结之后）。

---

## 六、把项目交给 AI 助手时的任务模板（可直接复制）

**投喂方式二选一**：① 把整个仓库给它；② 只能给文件时，给 `docs/_bundle.md`（单文件合集）或
"`docs/00-index.md` + 你要它改的那几份"。

```text
你在一个真实项目（LearnWithAI：把代码库变成业务图谱 + 六阶段教学设计训练）里工作。

先读 docs/00-index.md —— 里面有：文档地图、硬约束 7 条、一次改动的完成定义 7 项、禁止事项 8 条、
代码地图、以及"按任务选读"表。然后再读你这次要动的那几份文档。

【本次任务】<在这里写清要升级什么，例如：把阶段三「流程推演」从零落地>

【必须遵守】
1. 不要重排章节号（会断掉代码与文档里约 190 处 § 引用）；不要动 docs/90-archive.md 里"不能删"的东西。
2. 不许填假分 / 编业务含义 / 编干扰项；算不出来的维度一律 not_evaluated（唯一例外见 §9.2）。
3. 判定逻辑不许交给 LLM；LLM 只能做讲解与润色，且默认关闭。
4. 不许在自造样本 sample_projects/lab_safety_assistant 上报准确率。
5. 不许把没做的说成做了；做不到的直接写进文档的"诚实边界"。
6. 数字不许手抄：验收数字只认 validation/acceptance_latest.md。

【完成定义（缺一项就是没做完）】
1. 代码改了；
2. python scripts/build_acceptance_report.py 全绿（并在报告里体现新脚本）；
3. 按 README.md 顶部「改完必须同步哪几处」表同步文档（现状/债/验收写进 docs/07、docs/08）；
4. python scripts/verify_docs.py 退出码 0；
5. 新脚本登记进 docs/06-runbook.md 工具表 + docs/07 §17.2 + README.md §0.3；
6. 新写的检查要有**负向对照**（故意造一个失败用例证明它真会报错）；
7. 每做一个功能补一篇 docs/features/<功能>.md（照 _TEMPLATE.md）。

【交付格式】改动清单 + 每条改动对应的验收命令与实际输出 + 仍未做的部分（如实列出）。
```
