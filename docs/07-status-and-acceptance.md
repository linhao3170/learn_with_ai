# 现状与验收（原 README 第十六 ~ 十八章 + 附录 B）

> 更新触发：**每轮**（改了功能行为 / 跑了验收 / 调了优先级就要动这份） | 上次更新：部署说明一轮（2026-09-26：§16.1 末补部署文档与正式构建实测）
> 来源：原 `README.md` 的 §16 / §17 / §18 / 附录 B **整章搬移，逐字未改**；章节号保持不变，
> 所以 `§16.1` / `§17.2` / `§18` 这类引用（README 正文、代码注释、脚本里都有）仍然解析得到这里。
> **数字规矩**：验收数字**不许手抄** —— 以 `validation/acceptance_latest.md` 为唯一来源
> （由 `python scripts/build_acceptance_report.py` 生成），`python scripts/verify_docs.py` 会逐条核对。
> **这里是本仓库唯一权威的「下一步」**：§18 的优先级体系是执行口径，不许再出现第二份互相冲突的下一步
> （理由见附录 C 里 `README1.md` 被移出仓库那一条）。

---

## 十六、现状：已完成 / 部分完成 / 未开始

> **这一章是给「下一次」写的。** 凡是与本章冲突的旧描述，以本章为准。
> 上一轮开发已暂停，所有改动都落在磁盘上并经过机器化验证。

### 16.1 ✅ 已完成并可复用

**解析层与代码证据层**（真正的资产，不要重写）

| 组件 | 文件 | 可靠性 |
|---|---|---|
| AST 基础解析（类 / 函数 / docstring / 行号 / import） | `engine/parser/python_parser.py` | **确定** |
| 项目级调用图（跨文件 / 跨模块、复合属性） | `engine/deep_analyzer/project_call_graph.py` | **确定** |
| 状态读写追踪（支持字典 key 路径） | `engine/deep_analyzer/state_tracker.py` | **确定** |
| 依赖强度（真实调用次数） | `engine/deep_analyzer/dependency_strength.py` | **确定** |
| 模块架构分层 | `engine/deep_analyzer/module_architecture.py` | **推断**（边界需人看） |
| 业务流程提取（入口点 BFS） | `engine/deep_analyzer/flow_extractor.py` | **推断**（入口识别靠启发式） |
| 关键实现解析（**已做 `verified` / `inferred` 分层 + 行号**） | `engine/deep_analyzer/key_implementation.py` | 结构指标确定；语义推断带依据 |
| 业务优先级 BLPS-1.0 | `engine/deep_analyzer/business_priority.py` | 可用，公式可解释 + 证据缺口 |
| 设计模式识别 | `engine/deep_analyzer/design_pattern_detector.py` | **误报高** → 不进学生视图、不作评分维度 |
| 训练题生成（**业务词已全部外置**） | `engine/project_analyzer/training_generator.py` | 可用，但仍是四关题型（待替换） |

> **这张表应该成为项目对外材料的核心附件。**
> 敢把自己引擎的可靠性分级公开，本身就是最强的信任信号。

**业务图谱引擎（重设计那一轮的主体，已实现）**

- `engine/business_graph/`：五步流水线（单元 → 一级域 → 二级功能点 → 事实 → 卡片 / 关系）
  + 复杂度分级 + 三型场景 + 教师种子合并；
- `engine/lexicon/`：**20 份** JSON（15 份通用词典 / 教学配置 + 5 份设计层 `design_*`，见 §8.4 与 §16.1 末），**引擎里 0 处业务硬编码**（脚本门禁实跑：引擎 62 个 .py 文件 0 命中）；
- `engine/flow_filter.py`：生命周期流程降权（唯一实现）；
- `engine/path_utils.py`：路径规范化（唯一实现，幂等）；
- `engine/parser/ast_cache.py`：一次解析多处复用；
- `engine/business_logic/`：统一数据契约层（**12 个 dataclass** + `contract_version`；附录 A 有逐字段表）。

**后端**

- FastAPI 应用（应用版本 `0.5.0`，来源 `backend/app/main.py`；**训练链路 17 个接口 + 业务逻辑分析平台 13 个路由 = 30 个**，见第十一章）；
- 判题在后端，**答案不下发**；答案表存 `backend/data/answer_keys/`；
- 源码切片接口只接受项目内相对路径，越界返回 404；
- 一键盘点：`scripts/build_demo_snapshots.py` 生成「学生快照 + 答案表 + 证据源码副本」。

**前端**

- **系统主页面（默认落地页）**：两大核心功能（培训系统 / 业务逻辑分析平台）各占半屏、次级入口收成小模块、
  **来源依据与口径默认收起**（证据不删，只是不抢第一屏）；UI 重设计一轮新增，详见 16.1 末；
- 双通道数据源（API 优先 / 离线快照回落，且明确显示离线状态）；
- 业务图谱视图（域树 / 模块卡片 / 复杂度徽章 / 置信度徽章 / 三型场景 / 证据跳转）；
- 判题反馈组件（反馈区只在提交后渲染）；
- 项目切换器 + `?project=` 深链 + 会话恢复（按 `project_id` 持久化）；
- 教师审核界面（关键实现逐条确认 / 拒绝，状态持久化）。

**培训功能 · 阶段一「项目认知」（Sprint 3）**

| 组件 | 文件 | 说明 |
|---|---|---|
| 覆盖度比对器 | `engine/teaching/coverage.py` | 纯规则、无 LLM、无网络、确定性；`algorithm_version = orientation-coverage-1.0`；**同时是命中判定的唯一实现**（`prepare_text` / `add_comparison_key` / `key_hit`，阶段二复用） |
| 结构性词表 | `engine/lexicon/structural_names.json` | 域名归一化要剥掉的「模块 / 管理 / 系统 / 的」（**不在代码里硬编码**，审计 0 命中） |
| 教学服务 | `backend/app/services/teaching_service.py` | 只做入口校验（空提交 / 超长 / 缺图谱）与编排，判定逻辑不在这一层 |
| 接口 | `backend/app/main.py:255` | `POST /api/projects/{id}/teaching/orientation/coverage` |
| 前端视图 | `frontend/src/components/StageOrientation.vue` | 项目地图 + 自由文本作答 + 覆盖清单；反馈区 `v-if="report"` |
| 阶段入口 | `frontend/src/views/TrainingView.vue` | 页签「项目认知」，`v-if` 懒挂载 |
| 测试 | `scripts/test_teaching_coverage.py`（22/22，Sprint 4 后重跑仍全绿）、`scripts/verify_sprint0.py`（A9） | 不打分 / 不丢域 / 确定性 / 拒绝空提交 / 无网络导入 |

**培训功能 · 阶段二「模块卡片学习」（Sprint 4）**

| 组件 | 文件 | 说明 |
|---|---|---|
| 事实覆盖比对器 | `engine/teaching/card_coverage.py` | 逐问 `matched_keys / missed_keys / not_comparable_reason`；`algorithm_version = card-coverage-1.0`，`scoring = fact_coverage_only`，`has_score: false`；**命中判定复用阶段一那一份**，本模块只加「问题 → 卡片字段」映射 |
| 教学配置词典 | `engine/lexicon/stage_questions.json` | 五个问题的文本 + 「问题 → 参与比对的卡片字段」映射；教师改问法 / 换字段**不用改引擎也不用改前端** |
| 教学服务 | `backend/app/services/teaching_service.py` | `build_module_card_task_for_project` / `evaluate_module_card_for_project` |
| 接口 | `backend/app/main.py:281` / `:298` | `GET .../teaching/module-card/task`（**不下发比对键**）、`POST .../teaching/module-card/coverage` |
| 前端视图 | `frontend/src/components/StageModuleCard.vue` | 卡片选择 + 五问作答 + 逐问覆盖清单；`module-card-needs-review` 显式提示待确认字段 |
| 测试 | `scripts/test_teaching_card_coverage.py`（40/40）、`scripts/verify_sprint0.py`（A10）、`scripts/browser_clickthrough.mjs`（阶段二 23 条断言） | 题目来自配置 / 卡片不丢 / 不打分 / 待确认不比对；走查 **99/99**（`lab_safety_assistant`，Sprint 5 后重跑）、71/71（`python_dotenv`，**历史：Sprint 4 实跑、Sprint 5 未在此项目重跑**）、离线 **45/45** |

> **A10 的实测口径**（`verify_sprint0.py` 实跑输出）：**2 个项目、64 张卡片通过，
> 其中 17 张含待教师确认字段**（历史：优先级 4 二轮给 `lab_safety_assistant` 加种子图谱之前是 25 张）。
> 也就是说"哪些字段不参与比对"这件事在真实数据上确实被大量用到。

**两个阶段共有的四条硬约束（都已被脚本覆盖）**

1. **不打分**：报告里没有 `score` / `correct` 这类字段（测试逐键扫描），页面明示「本阶段不打分」；
2. **不丢域 / 不丢卡片**：每个核心域、每张卡片必须恰好落进"命中 / 未命中 / 未参与比对"之一；
3. **未确认不比对**：置信度为 `unconfirmed` 的字段不参与比对，进 `not_comparable` 并写明原因；
4. **学生先输出**：提交前反馈区**一个 DOM 节点都没有**。

**辅助工具**：事实表导出器、错误类型归类器、业务优先级报告导出、实测验证报告生成（见第二十章）。

**培训功能 · 阶段四「设计画布」+ 阶段五「六维评审」（Sprint 5）**

| 组件 | 文件 | 说明 |
|---|---|---|
| 分级任务生成器 | `engine/design/task_builder.py` | 按项目复杂度级别（L1–L4）给任务类型；题干 / 简报口径在 `engine/lexicon/design_tasks.json`；**学生视图与教师视图由同一个函数产出**（`build_design_task(..., teacher_mode=)`） |
| 匹配器 | `engine/design/matcher.py` | 学生模块 ↔ 必备能力 **三分类**（`matched` / `missing` / `unrecognized`）；归一化与命中判定**复用阶段一** `coverage.py`；`algorithm_version = design-matcher-1.0` |
| 结构检查 | `engine/design/graph_checks.py` | Tarjan SCC 环检测（带路径）/ 自环 / 孤岛 / 悬空边 / 层级深度 / 声明与画线是否自洽；`design-graph-checks-1.0` |
| 替代结构 | `engine/design/alternatives.py` | 可接受替代结构与禁止合并项；**没有教师清单时 `available=False`**（不把「没判」说成「没命中」） |
| 契约归一化 | `engine/design/submission.py` | `design_submission.json`（§10.4）的唯一入口；幂等；未知字段如实记录 |
| 六维评审 | `engine/design/rubric.py` | 六维可计算定义（§9.2）；`algorithm_version = rubric-1.0`、`scoring = rubric_six_dimensions`、`has_score = true`；**算不出来的维度 `score = null` + `reason`，不参与权重归一化** |
| 反馈渲染 | `engine/design/feedback.py` | **信号码 → 中文模板的纯函数**（模板在 `engine/lexicon/design_feedback.json`）；报告里的 `issues` 恒等于 `render_issues(signals)` |
| 词典（5 份） | `engine/lexicon/design_{dimensions,tasks,tasks.seed,feedback,words}.json` | 维度与权重、扣分表、任务模板、教师种子（**优先级 3.5 一轮起有 `lab_safety_assistant` 一份确认版**）、反馈模板、异常词族 |
| 教学服务 | `backend/app/services/teaching_service.py` | `list_design_tasks_for_project` / `build_design_task_for_project` / `evaluate_design_for_project`（只做入口校验与编排） |
| 接口 | `backend/app/main.py:327` / `:341` / `:363` | `GET .../teaching/design/tasks`、`GET .../teaching/design/task`、`POST .../teaching/design/evaluate` |
| 前端视图 | `frontend/src/components/StageDesign.vue` | 原生 drag + 手写 SVG 画布 + 卡片编辑面板 + 六维报告 + 迭代对比 |
| 测试 | `scripts/test_design_rubric.py`（**90/90**）、`scripts/verify_sprint0.py`（A11）、`scripts/browser_clickthrough.mjs`（阶段四 28 条断言） | 三分类 / not_evaluated / 空提交不给 0 分 / 可见性矩阵 / 教师种子 / 确定性 / 画布交互 |

> **Sprint 5 的实测口径**（屏幕输出，不是推断）：
> `verify_sprint0.py` **14/14**（A1–A11）、`test_design_rubric.py` **90/90**（合成用例 + 2 个真实项目）、
> 走查 **99/99（在线）** 与 **45/45（离线）**、`test_teaching_coverage.py` 22/22 与
> `test_teaching_card_coverage.py` 40/40 **重跑仍全绿**（证明复用阶段一判定没有改变旧口径）、
> `audit_hardcoding.py` 引擎 **62 个文件 0 命中**（新增的设计层文件也在扫描范围内；历史：Sprint 5 当时记录的是 54 个，之后脚本数又增加）。

> **Sprint 5 已知的口径边界（必须随报告一起说）**：
> ① 自动生成任务的必备能力清单来自**本项目自身图谱**（`must_have_source = auto_from_project`，
> `needs_review = true`），因此**存在「照着本项目现有结构抄」的捷径**，且清单本身未经教师确认；
> ② `required_relations` / `required_edge_cases` / `forbidden_merges` / `acceptable_alternatives`
> **只能来自教师种子**（这在 Sprint 5 时是空的），所以这几项在**自动任务**上一律「本轮未评估」，
> 引擎**不编**一份出来（**优先级 3.5 一轮已为 `lab_safety_assistant` 补上种子，见 16.1 末**）；
> ③ 第 5 维「异常与边界」在自动任务下只按「学生自己有没有给出异常」计算；
> ④ 匹配是词表匹配（exact / contains / bigram+token），**必然有假阴性**，所以措辞是
> 「未在设计中识别到」，不是「你漏了」。

**训练题第 2 关「模块职责」覆盖（优先级 4 一轮）**

| 组件 | 文件 | 说明 |
|---|---|---|
| 出题器 | `engine/project_analyzer/training_generator.py` | `_generate_level2` 返回**一列表**：项目里每个"够格"的业务模块各出一道四选一（够格 = 有非空业务语义文本 + 能从其他业务模块凑出 3 个不同干扰项）；凑不出就**不出这一题**，不编造。上限 `_MAX_LEVEL2_QUESTIONS = 4` |
| 题目标题 | 同上 | 改成 `第2关：模块职责·<模块名>`。理由：前端把标题当**关卡标签与雷达维度名**（`TrainingView.vue` 会把「第N关：」前缀剥掉），重名就分不清哪一关是哪一题 |
| 前端去重 | `frontend/src/views/TrainingView.vue` | 同一题型出现多题后，答错建议去重显示一次（原来会同一句建议出现 4 次） |
| 测试 | `scripts/test_training_questions.py`（**53/53**，优先级 4 二轮由 31 扩到 53） | 覆盖 / 不编造（选项全部可回指到真实模块文本）/ 4 选 1 且与答案表逐题一致 / 标题可区分 / 关卡顺序 1→2…→3→4 / 确定性 / 上限 / CRUD 标签不当职责 / 编排与支撑模块不作为主体 |

> **优先级 4 一轮的实测口径（两个演示项目，屏幕输出）**：
> `lab_safety_assistant` 训练题 **4 → 7 道**（第 2 关 4 道：设备管理 / 预约管理 / 安全检查 / 用户管理模块，
> 改造前只问核心度最高的**那一个**）；`python_dotenv` **3 道不变**——
> 它只有 2 个业务模块、其中 1 个的业务语义文本是空的，凑不出 3 个真实干扰项，
> 于是第 2 关**一道都不出**（诚实退化，不是漏做）。
> 全量验收在同一轮重跑：`verify_sprint0.py` 14/14、`test_business_graph.py` 161/161、
> 阶段一 22/22、阶段二 40/40、设计层 90/90、`check_determinism.py` 两项目一致、
> `audit_hardcoding.py --include-frontend` 0 命中、`validate_contract.py` 两项目 + 两份快照全通过、
> 前端 `vite build` 2139 modules transformed（16.30s）。

**教师设计任务种子（优先级 3.5 一轮）**

| 组件 | 文件 | 说明 |
|---|---|---|
| 教师种子（**第一次有真货**） | `engine/lexicon/design_tasks.seed.json` | `lab_safety_assistant` 一份 `review_status: "confirmed"` 的任务：**10 项必备能力** + **2 条必备依赖** + **2 个必备边界** + **2 条可接受替代结构** + **1 条禁止合并项**。逐项源码出处写在种子自己的 `_evidence` 里（`user_manager.py:61-118`、`reservation_manager.py:56-166`、`equipment_manager.py:24-144`、`safety_checker.py:29-154`），引擎不读这段、只给人复核 |
| 种子读取 | `engine/design/task_builder.py:134` / `:451` | 按 `project_id` 取种子；命中即 `must_have_source = teacher_seed`、`needs_review = false`、`must_have_confirmed = true`。**引擎侧一行没改**——3.5 这一轮交付的就是数据 |
| 反馈文案修正（本轮副产物） | `engine/design/alternatives.py` | 禁止合并的 `violations` 早先把种子里的内部 key（`mh_*`）直接渲染给学生（`StageDesign.vue` 的「禁止合并」列表用的就是 `a` / `b`）。改成 `a` / `b` = **中文显示名**、原始 key 另存 `a_key` / `b_key`。见 §19.2 ⑲ |
| 测试 | `scripts/test_design_seed.py`（**33/33**） | **不注入任何东西**，直接读仓库里这份种子文件跑两份真实提交：合规设计（每项能力一个模块 + 连成链 + 写上两个边界）不被误判；违规设计（合并该分开的能力 + 不写边界）**三条信号全部被抓住**；另测「种子只影响有种子那个项目」「学生视图不泄漏」「简报不列必备能力」「文案里没有残留占位符与 `mh_*` 内部 key」 |

> **这 10 项必备能力是哪些**（顺序即种子里的顺序，也是「一项能力一个模块、连成链」的推荐顺序）：
> 用户身份与权限校验 · 预约冲突检测 · 提交预约申请 · 预约审批 · 取消预约 ·
> 设备状态更新 · 设备借出与归还 · 设备入库 · 安全检查执行 · 隐患整改与关闭。
> 覆盖 4 个 core 域（用户管理 / 预约管理 / 设备管理 / 安全检查），**编排域 `系统装配` 不在其中**；
> `(verb_class, entity)` 两两不重复（`test_design_rubric.py` 与 `test_design_seed.py` 都断言这条）。

> **优先级 3.5 一轮的实测口径（屏幕输出，不是推断）**：
> `test_design_seed.py` **33/33**（新增）；`verify_sprint0.py` **14/14**
> （A11 由「2 个项目、**6 个任务**」变成「2 个项目、**4 个任务**」——
> `lab_safety_assistant` 的 3 个自动任务被 1 个种子任务取代，这是设计不是 bug）；
> `test_design_rubric.py` **90/90**（合成用例 + 两个真实项目，未被种子改动破坏）；
> `test_business_graph.py` 161/161、阶段一 22/22、阶段二 40/40、`test_training_questions.py` 31/31（**历史：这一轮当时的口径，优先级 4 二轮已扩到 53/53**）、
> `check_determinism.py` 两项目一致、`audit_hardcoding.py --include-frontend` 引擎 0 / 前端 0、
> `validate_contract.py` **两个项目**全通过。
>
> **走查这一轮真的重跑了（与优先级 4 一轮不同）**：在线 **99/99**（`--project lab_safety_assistant`）、
> 在线 **99/99**（`--project python_dotenv`，**这一次阶段四的断言落在有种子那个项目上**）、
> 离线 **45/45**。跑之前确认了两件事：① `.smoke-dist` 比 `frontend/src` 下所有文件都新
> （本轮**没有改任何前端文件**，所以 bundle 是当前的，不需要重建）；② 8000 上的后端**必须先重启** ——
> 旧进程里 `load_lexicon` 已经把**空的**种子缓存住了，不重启的话"种子没生效"是假象（见 §19.5）。
> 走查里能直接看到种子生效的三条：**「项目 lab_safety_assistant：1 个任务」**、
> **「必备能力 10 项」**、**「『必备能力清单待教师确认』徽章 = 后端标注无需复核」**（徽章如实消失），
> 以及「教师视图 10 项 / 页面 0 处」——**必备能力名一个都没漏进 DOM**。

**教师种子图谱（优先级 4 二轮）**

| 组件 | 文件 | 说明 |
|---|---|---|
| 教师种子图谱（**仓库里第一份**） | `sample_projects/lab_safety_assistant/business_graph.seed.json` | 教师确认的 **5 条域目标 + 3 条二级功能点目标**（`objective_confidence: "confirmed"`、`review_status: "approved"`），域的中文名用 `locked: ["name_cn"]` 锁住。逐条出处写在顶层 `_evidence`（`safety_checker.py:1-5`、`app.py:1-5`、`user_manager.py:1-6`、`equipment_manager.py:1-16`、`reservation_manager.py:1-6`）。**文件位置就在被分析的项目目录里**，`project_parser.py:167` 会跳过非 `.py`、`compute_source_hash` 只哈希 `.py`，所以放这里既不会被当成源码、也不会改变 `source_hash` |
| 合并机制（**已有，未改**） | `engine/business_graph/seed_merger.py` | 按 id 对齐、种子优先、节点带 `source`（`teacher` / `auto`），图谱 `status` 变 `mixed`。前端 `ModuleCardPanel.vue:25` / `StageModuleCard.vue:118` 早就支持「教师审核版」徽章（`utils/businessGraph.js` 的 `SOURCE_META` / `GRAPH_STATUS_META`）——**这一轮补的是数据，不是 UI** |
| 实测效果 | 见 §8.8 的对照表 | `objective_missing` 4 → **0**；待教师确认卡片 8 → **0**；教师/自动卡片 0/34 → **8/26**；`source_hash` 不变 |

**人工核对辅助工具（优先级 2 备料一轮）**

> 这一轮**没有改任何引擎 / 后端 / 前端代码**：优先级 2 要的是「人来判」，
> 所以这一轮补的是**判断材料**与**验收工具**，不碰任何判定逻辑。

| 组件 | 文件 | 说明 |
|---|---|---|
| 判断材料生成器 | `scripts/export_domain_review_worksheet.py` → `validation/graph_review_worksheet.md`（98997 字节 / 527 行） | 每个域一张卡片：角色 / 置信度 / 命名词根来源 / 单元数 / **聚类依据** / **涉及文件** / **该域下每个能力点的成员函数（`文件:行`）**。项目清单与「哪些是自造样本」**复用 `validate_business_graph.py` 的同一份定义**（不另写一份），自造样本自动跳过。输出无时间戳、无 set 顺序依赖 → **逐字节可复现** |
| 核对结果统计器（= 验收命令） | `scripts/graph_review_report.py` | 读回第 6 节「人工判定」列 → **划分错误率 / 命名不当率**（域与功能点**分开报**，分母都是总行数，照抄 README 口径）+ 漏填清单 + 非法取值清单 + **表格结构检查**。它能发现"手工编辑把 `\|` 多写/少写了一个"，并给出**文件行号** |
| 口径纪律 | 同上 | 只统计人填的那一列，**不产生任何新判断**；`无法判定` 计入分母（不许把没判的悄悄从分母拿掉），另给一个**明确标注为"非 README 口径"**的参考值（排除 `无法判定` 之后的比例），因为评委会问"排除判不了的那些之后呢" |

> **优先级 2 备料一轮的实测口径（屏幕输出）**：
> 待判定 **37 行域 + 147 行功能点 = 184 行**（与 §17.4 的汇总一致：6+12+19 / 24+54+69）。
> 统计器三条路径都做了对照：① 真实模板（未填）→ 退出码 **1**，打印「还没填的行 **184** 处」；
> ② 用测试值填满并轮转四种判定（域 37 行 = 正确 10 / 命名不当 9 / 划分错误 9 / 无法判定 9）
> → 退出码 **0**，算出划分错误率 **24.3%（9/37）**、命名不当率 **24.3%（9/37）**、
> 参考值 **32.1%（9/28）**——与手算一致；③ 故意在某行少写一个 `|` → 退出码 **1**，
> 并指出「文件第 95 行（`d_binding`）列数是 6，应为 8」。另测：填「对」这类非法取值 → 退出码 1 并单列出来。
> **注意**：这个统计器**不进上面那套自检清单** —— 它的退出码是验收语义（人没填就是 1），
> 与 `verify_sprint0.py` 那类"环境正确就必然通过"的脚本不是一回事。

**训练题第 3 / 4 关「一关多题」（优先级 4 二轮）**

| 组件 | 文件 | 说明 |
|---|---|---|
| 第 3 关逐流程出题 | `engine/project_analyzer/training_generator.py`（`_generate_level3`） | 按 `flow_filter.sort_flows_business_first` 的**唯一排序口径**逐条流程出题（第一条与旧行为一致），上限 `_MAX_LEVEL3_QUESTIONS = 4`。**只在一条业务流都没有时才退回生命周期流程**（拿初始化流程当核心业务教是教学性错误）。凑不出 3 个真实干扰项就跳过，不编造 |
| 第 4 关逐实现出题 | 同上（`_generate_level4_deep` / `_level4_question_for`） | 逐条关键实现出题，上限 `_MAX_LEVEL4_QUESTIONS = 3`（**比 2/3 关小**：这一关的干扰项还是**固定模板**，题越多"认出那几句反模式"的套路收益越大）。多题之间**轮换干扰项三元组**（4 条里取 3 条，4 种组合） |
| 标题可区分 | 同上（`_unique_question_title`） | 第 3/4 关标题带上流程名 / 方法名（`第3关：流程推演·<流程名>`、`第4关：关键实现·<方法名>`），同名时追加 `#2`。理由与 §19.2 ⑰ 同：前端把标题当**关卡标签与雷达维度名** |
| 前端（**零改动**） | `frontend/src/views/TrainingView.vue` | 雷达维度与关卡列表本来就是"一题一维"（`radarDims = questions.map(...)`），答错建议按 `question_type` 去重（`ADVICE_BY_TYPE`），所以多题不需要改前端 |
| 测试 | `scripts/test_training_questions.py`（**53/53**，由 31 项扩到 53 项） | 第 3 关：够格流程各一道 / **有业务流时绝不问生命周期流程** / 选项全部由真实步骤标签拼成（不编造）/ 4 选 1 且与答案表逐题一致；第 4 关：按重要度取前 N 条且不重复 / **干扰项逐题轮换**（至少两种组合）/ 证据为项目内相对路径 |

> **为什么第 1 关不用改（这是一个结论，不是漏做）**：第 1 关的题面是
> 「下列哪些是本项目的核心业务模块」的**多选**，正确项 = 该项目的**全部**业务模块，
> 干扰项 = 编排 / 支撑模块 —— 也就是说**它一道题就已经覆盖了所有业务模块**，
> "只出一题"在这个题型下是完备的。真正缺覆盖的是第 2/3/4 关（一关只问一个对象），
> 这才是两轮扩展的对象。
>
> **优先级 4 二轮的实测口径（屏幕输出，不是推断）**：
> 训练题 `lab_safety_assistant` **7 → 12 道**（第 1 关 1 + 第 2 关 4 + 第 3 关 4 + 第 4 关 3，
> 第 3 关由"只问主流程"变成问 4 条不同的业务流，第 4 关由 1 条变成 3 条关键实现）；
> `python_dotenv` **3 → 8 道**（1 + 0 + 4 + 3；第 2 关仍诚实退化为 0 道）。
> 全量验收：`verify_sprint0.py` 14/14、`test_training_questions.py` **53/53**、
> `test_business_graph.py` 161/161、阶段一 22/22、阶段二 40/40、设计层 90/90、
> 教师任务种子 33/33、`check_determinism.py`（同进程 + **跨进程**）两项目一致、
> `audit_hardcoding.py --include-frontend` 引擎 0 / 前端 0、`validate_contract.py` **两个项目**全通过、
> 旧管线三个冒烟脚本退出码 0；走查在线 **99/99** ×2 + 离线 **45/45**。
> ⚠️ **改题目必须同时重建答案表**：`build_demo_snapshots.py` 一起产出学生快照 + 后端答案表，
> 只重跑其一就会出现"题目 12 道、答案表 7 条"的错位（判题按下标）。

**文档门禁与验收报告（阶段 0 一轮，2026-09-26）**

> 这一轮**没有改任何引擎 / 后端 / 前端行为**：交付的是两个脚本 + 一次对文档的事实修正
> （改的是文档说了假话的地方，不是改口径）。起因是审计实测：文档里手抄了 **13 个不同的
> 最近一次测试总数、共 108 处**，其中 4 个已淘汰的值还留在正文 13 处；应用版本号在同一份
> 文档里有 **3 个值**（当前值 `0.5.0`，另有 `0.3.0` / `0.4.0` 两个**历史值**）；`main.py` 的行号引用
> **10 处全错**。

| 组件 | 文件 | 说明 |
|---|---|---|
| 验收报告生成器 | `scripts/build_acceptance_report.py` | **默认组**的 13 个只读验收脚本在**一个进程内**跑（不启子进程、不用管道）；`--with-node` 的 4 条走查另起 node 子进程、输出走临时文件而不是管道（理由见 §19.5）。它解析每个脚本屏幕输出里的「通过/总数」，产出 `validation/acceptance_latest.json`（机器读）+ `.md`（人读）。总计解析有四种口径（总结行 / 逐行相加 / `[PASS]` 行计数 / 无总计只报退出码），**来源逐条记在报告的 `total_source` 里**。默认组**只读**：会覆盖产物或人工判定模板的脚本（`validate_business_graph.py --emit-review`、`graph_review_report.py`、旧管线冒烟）默认不跑，且**原因逐条打印**，不会被静默跳过 |
| 文档门禁 | `scripts/verify_docs.py` | 6 项检查：**D1** 反引号里的路径必须真实存在（当行明写「待建 / 已删除 / 不存在」或写进允许清单的除外；已按附录 C 处置的旧文档只记 WARN）；**D2** `§X.Y` 与「第 N 章」必须解析到真实标题（同时统计代码里指向**已删除旧文档**的引用 —— 当前 196 处，阶段 2 用稳定 ID 处理）；**D3** 文档里的应用版本必须等于 `backend/app/main.py` 的值；**D4** 文档里的验收数字必须与验收报告一致、已淘汰的旧总数不许裸写；**D5** 拆分后每篇 `docs/*.md` 要有「更新触发」行；**D6** `文件:行号` 必须指得到东西（越界或锚点不在附近即报错） |
| 本轮修掉的事实性错误 | `README.md` | 应用版本号的 3 处**历史值**（`0.3.0` / `0.4.0`）统一改为当前值 `0.5.0`，并写明唯一来源；§9 标题原写「尚未实现」而实际 Sprint 5 已落地；**`文件:行号` 引用 10 处过期**（阶段一覆盖度接口在 `main.py` 里的旧值 `241` 实为 `255`、模块卡片两个路由的 `267`/`284` 实为 `281`/`298`、设计层三个路由的 `318`/`334`/`356` 实为 `327`/`341`/`363`、§4 里的 `main.py` 旧值 `228`；另有一处 `coverage.py` 里的 `evaluate_orientation` 旧值行号也已改正）；A3 扫描文件数 `54→62`（4 处）；A10 待确认卡片 `25→17`、`lab_safety_assistant` 的 `8→0`（3 处）；`lexicon` 份数 `15→20`、`models.py` dataclass `13→12`（含附 A 只列了 9 个类名）、前端页签 `四个→五个`；§0.4 导航把「工具与命令手册」写成第十九章（实为第二十章）；把 2 处指向**不存在子节**的引用（原写成 `7.7`）改成「§七 第 7 条」；§17.2 的 `13/13`、`71/71`、`41/41`、`31/31` 等旧总数按「改成当前值或写明历史」逐条处理 |
| 负向对照（纪律要求） | — | D6 做过一次负向对照：故意把 `coverage.py` 里那处行号写回过期值 → 门禁报 ERROR 且退出码 1；改回正确行号后 exit 0。D4 的正向证据是它本轮真的抓到了 `13/13` / `71/71` / `41/41` / `31/31` 四类旧值 |

> **本轮边界（别把它说成已经做完的事）**：数字**仍然写在文档里**，只是从此**被脚本核对**；
> 「文档里只准写『见验收报告』、彻底不再手抄数字」这一步**阶段 1 也没做**（阶段 1 只搬文件），
> 它是阶段 2 的收尾项。
> 代码里 196 处指向已删除旧文档的引用（`README5 §3.2` 这类）本轮**只统计不修**，
> 阶段 2 会换成稳定 ID（`R-` / `D-` / `A-` 编号）。

**文档拆分阶段 1（2026-09-26，上一轮）**

> 这一轮**只搬文档，不改任何代码与行为**，搬的是"每轮都会变"的那三块。
> （下表里的文件名已是阶段 2 改名后的名字。）

| 动作 | 结果 |
|---|---|
| 搬出「现状与验收」 | 原 README 的 **§16 + §17 + §18 + 附录 B** 整章搬到 `docs/07-status-and-acceptance.md`（本就是您正在读的这份），**章节号保持不变**，所以 `§16.1` / `§17.2` / `§18` 这类既有引用（README 正文、代码注释、脚本里都有）仍然解析得到 |
| 搬出「技术债与复盘」 | 原 §19 整章 → `docs/08-tech-debt.md`（`§19.1` ~ `§19.6` 不变） |
| 搬出「历史存档」 | 原附录 C（含 C.1）→ `docs/90-archive.md` |
| README 变薄 | **3484 行 → 2425 行（−1059 行）**；第一 ~ 十五章、第二十章、第二十一章、附录 A **一字未改**；原位置留「已移出的章节」映射表 + §0.4 文档导航改写 |
| 换行与完整性 | 四份文档全部 **LF**（CR=0）；搬移后逐行比对原 README，**内容零丢失**（唯一"找不到"的 14 行就是本轮故意改写的顶部纪律块与导航表） |
| 门禁适配 | `verify_docs.py` 的 D2 改成在**整个文档集**上解析章节引用，并新报一类 WARN「跨文件引用」（当时 README ←32 / docs/04 ←31 / docs/05 ←29） |
| 一次性的搬移脚本 | `scripts/_move_docs_phase1.py` **用完即删**（与 §19.2 那条"临时脚本读完即删"同一做法），不登记进工具表 |

**文档拆分阶段 2：全面模块化（2026-09-26，本轮）**

> 这一轮同样**只搬文档、只加门禁，不改任何代码与行为**；目标是"把项目整体一次性交给 AI 助手也能接得住"。

| 动作 | 结果 |
|---|---|
| 剩余章节全部切出 | 第一 ~ 六章 → `docs/01-teaching-design.md`；第七 ~ 九章 → `docs/02-architecture.md`；第十章 + 附录 A → `docs/03-contracts.md`；第十一、十二章 → `docs/04-api-and-frontend.md`；第二十一章 → `docs/05-logic-platform.md`；第二十章 + `§19.5` → `docs/06-runbook.md`；第十三 ~ 十五章 + `§21.8` → `docs/09-discipline-and-defense.md`。**逐字搬移、章节号全部保持不变** |
| 两处跨文件搬移（带占位） | `§19.5`（沙箱 / 环境约束）从技术债文档搬到运行手册 —— 它是手册内容不是债，原地留 `§19.5` 占位与指针；`§21.8`（平台专属表述纪律）并入 `docs/09`，原地留占位 |
| README 变成纯入口 | **2425 行 → 约 215 行**（只留：定位一句话、**写作纪律与"改完同步哪几处"对照表**、0.1~0.4 速览与文档导航、项目文档集清单、收尾语） |
| 新增「AI 交接入口」 | **`docs/00-index.md`**：项目 30 秒版、文档清单（职责 / 更新触发 / 依赖）、**硬约束 7 条**、**一次改动的完成定义 7 项**、**禁止事项 8 条**、已知死指针、代码地图、契约与版本来源、**按任务选读表**。这就是"一次性交给 AI"要给它看的第一份 |
| 新增功能设计卡模板 | `docs/features/_TEMPLATE.md`：目标 / 不变式（逐条要写"谁在盯"）/ 契约 / 判定口径 / 学生可见性 / 验收命令 + 负向对照 / 诚实边界 / 待教师填的数据 / 踩过的坑。**一个功能一篇** |
| 新增打包器 | `scripts/pack_docs.py` → `docs/_bundle.md`（按索引顺序拼成单文件，含清单一致性核对）。只能给一个文件时用它 |
| 新增门禁项 | `verify_docs.py` 增加 **D7 文档清单完整性**（`docs/` 下每份都要被 `docs/00-index.md` 与 `README.md` 提到；清单里写的路径必须存在），并把 `_` 前缀文件（打包产物 / 模板）排除在检查之外 |
| 改名（ASCII 文件名，便于跨平台与投喂） | `docs/04-现状与验收.md` → `docs/07-status-and-acceptance.md`、`docs/05-技术债与复盘.md` → `docs/08-tech-debt.md`、`docs/90-历史存档.md` → `docs/90-archive.md` |
| 完整性核对 | 拆分前 3572 行 → 拆分后 3661 行；逐行比对"有内容的行"，**改名前的内容零丢失**（40 处"找不到"全部是改名引用与两处刻意改写的导航块） |
| 一次性脚本 | `scripts/_split_docs_phase2.py` **用完即删**，不登记进工具表 |

> **本轮之后的文档地图**：`README.md`（入口）+ `docs/00-index.md`（交接）+ `docs/01` ~ `docs/09`（分工）
> + `docs/90`（历史）+ `docs/features/_TEMPLATE.md`（功能卡模板）+ `docs/_bundle.md`（产物）。
> **仍未做的**：`docs/features/<功能>.md` 的实际内容（模板已就位，每个功能补一篇是持续工作）；
> 稳定 ID 引用规范（把 196 处旧文档死指针与约 190 处跨文件 `§` 引用换成 `R-` / `D-` / `A-` 编号）。

**系统主页面与界面重设计（UI 重设计一轮，2026-09-26）**

> 这一轮**只改前端呈现层**：引擎 / 后端 / 契约 / 判定口径一行没动，`algorithm_version` 一个没变。
> 起因是排版与功能优先级有问题 —— 打开前端直接落在训练页头部 + 一条平级的五个页签 + 一屏口径说明，
> 第一次看的人看不出"这系统有两大块、我该点哪个"；证据（来源与口径）又和主功能抢第一屏。

| 动作 | 文件 | 说明 |
|---|---|---|
| **新增系统主页面，并成为默认落地页** | `frontend/src/views/HomeView.vue`（新） | 身份区（定位一句话 + 项目切换器 + 契约事实条）→ **两大核心功能各占半屏**（培训系统 · 六阶段 / 业务逻辑分析平台）→ 次级入口（小模块：业务图谱 / 函数级分析详情 / 来源依据）→ **来源依据与口径（默认收起）**。事实条上的项目 / 契约版本 / 题数 / 模块数全部来自 `loadContract`，页面自己不算任何业务结论 |
| 顶层视图增一个入口 | `frontend/src/App.vue` | `currentView` 初值 `training` → `home`；培训工作区顶部条加「← 返回系统主页面」（`data-test="back-home"`）；`go-logic-platform` 从训练头部移到主页面 |
| 六阶段入口**只给已落地的阶段** | `frontend/src/views/HomeView.vue` | 阶段一 / 二 / 四·五 可点（`data-test="home-stage-entry"`）；阶段三（流程推演）/ 阶段六（重构挑战）渲染成 `disabled` 的 `data-test="home-stage-todo"`，**不给入口**。状态表的依据就是本节 16.1 / 16.3 与 `README.md` §0.2 —— 界面与完成度表是同一件事，而走查那条断言**钉到具体是哪几个 stage key**（不是只数个数），并做过负向对照（把 `flow-sim` 临时标成 `done` → 断言立刻 FAIL） |
| **链式拉动 + 层进式动画** | `frontend/src/style.css`（新增一节）、`frontend/tailwind.config.js`（7 组关键帧）、`frontend/src/composables/useReveal.js`（新） | 链式拉动：主页面两大核心之间的 `.chain-rail`（入场 `chain-pull-left/right` + 链节依次点亮 + 光点沿链跑动）、六阶段竖链 `.stage-row`（停在某一格时"拉动下一格"，纯 CSS `:hover` + 相邻兄弟选择器）。层进式：`[data-layer]` + `.stagger-item`（`--i` 排延迟）由 `useReveal.js` 在进入视口时逐层点亮 |
| 动画的两条硬约定 | `frontend/src/composables/useReveal.js`、`frontend/src/style.css` | ① **默认可见**：只有浏览器支持 `IntersectionObserver` 时才武装 `[data-layer]`；JS 没跑到 / 不支持 / jsdom 走查环境里内容**照样完整可见**，不会白屏。② 尊重 `prefers-reduced-motion`（媒体查询里全关入场动画） |
| 工作区排版分层 | `frontend/src/views/TrainingView.vue` | 五个页签按**模块层级**分成「阶段主线」（① 项目认知 / ② 模块卡片 / ④⑤ 设计画布）与「项目视图」（训练关卡 / 业务图谱），`data-test` 钩子一个没改；原来铺在页签旁的判定口径说明收进可折叠抽屉（`data-test="stage-scope-toggle"` / `stage-scope-body`，按当前阶段换内容）；新增 `initial-stage` prop（**缺省仍是 `training`**），主页面上的阶段入口靠它直接落到对应阶段；答题卡的题面与选项按 `--i` 层次滑入 |
| 平台页的流程与立场 | `frontend/src/views/LogicPlatformView.vue` | 六步流程改成一条链（`data-test="logic-flow-card"`，`logic-stage-step` 仍是六条）；口径立场横幅 `logic-mode-banner` 从"铺满一行"改成"一行摘要 + 可展开的完整口径"（`logic-stance-body`，**三句话一句没删**）；每个阶段面板外套一层 `data-layer` wrapper |
| 走查按**真实用户路径**走 | `scripts/browser_clickthrough.mjs` | 新增 10 条主页面断言，并改成"先落在主页面 → 点进培训工作区 → 后面 13 个环节的断言一个字没改"。刻意**不断言像素尺寸**：jsdom 不测样式，用"谁在里面"断言比用"谁更大"可靠 |

> **UI 重设计一轮的实测口径（屏幕输出，不是推断）**：
> 走查在线 **109/109**（`--project lab_safety_assistant`）、在线 **109/109**（`--project python_dotenv`）、
> 离线 **55/55**；`frontend/scripts/lp_smoke.mjs` **42/42**（项数未变，命令见 `docs/05` §21.8）；
> 走查 bundle 重建（**2148 modules transformed**，10.31s）；
> 只读验收 `python scripts/build_acceptance_report.py` 实跑 **13/13 个脚本通过**（数字见 `validation/acceptance_latest.md`，
> 其中 `audit_hardcoding.py --include-frontend` 前端 48 个文件 0 命中 —— 新增的 `HomeView.vue` 没有引入业务硬编码）。
> 旧值 99/99（在线）与 45/45（离线）是 **Sprint 5** 的口径，本轮不再是当前值。
>
> **这一轮明确没做的**：① 像素级排版（谁更大、间距好不好看）**没有任何自动检查** ——
> 走查断言的是 DOM 结构与文本，不是样式；② 动画只在真实浏览器里跑，jsdom 里根本没有 CSS；
> ③ 没有做低端机 / 长列表 / 连续切页签的性能验证；④ 没有引入 `vue-router`（B 阶段仍未做）。

**证据折叠与口径说明（证据折叠一轮，2026-09-26）**

> 接在 UI 重设计一轮后面收拾**平台页里最密的那两块**。起因是两个实际问题：
> ① **太密** —— 一条断言下面挂着 1~4 个 `文件:行号` 按钮 + 三个徽章 + 两个教师标注按钮，
> 反幻觉面板的逐项校验明细一铺就是 25~145 条，主结论被淹掉；
> ② **边界没写在证据旁边** —— 平台确实在抓幻觉，但"抓到哪一层、抓不到哪一层"原先只在
> 代码注释与文档里，**看讲稿的人看不到**，"引用对得上"很容易被读成"业务解释也是对的"。
> 这一轮**同样只改前端呈现层**：引擎 / 后端 / 契约 / 判定口径一行没动。

| 动作 | 文件 | 说明 |
|---|---|---|
| **新增两个可复用组件** | `frontend/src/components/logic-platform/EvidenceFold.vue`（新）、`EvidenceNote.vue`（新） | `EvidenceFold`：折叠容器，**收起用 `.drawer-body` 把高度归零，不是 `v-if`** —— 内容始终在 DOM 里；数量写在折叠头上；`defaultOpen` 留给"这里出事了"（被拦截 / 有失败）。`EvidenceNote`：**摘要常驻 + 详述收起**的口径说明，**不接收"是否显示"**（口径不许被关掉） |
| 讲稿：逐条断言证据与教师标注收起 | `frontend/src/components/logic-platform/ImmersiveLesson.vue` | 每条 `must_remember` 断言下面，`文件:行号` 证据按钮 + 「确认 / 有问题」收进 `data-test="claim-fold-<claim_id>"`；**置信度 / 生成主体 / 已拦截徽章常驻**（判断该用多严的眼光看它靠的就是这三个）；**被拦截的断言默认展开**；新增常驻摘要 + 完整口径（`data-test="lesson-evidence-note"`）；`claim-evidence` / `claim-review-actions` 等既有钩子一个没删 |
| 反幻觉面板：明细与被拦截清单收起 | `frontend/src/components/logic-platform/VerificationPanel.vue` | 逐项校验明细收进 `logic-checks-fold`（**`failed > 0` 时默认展开**）、被拦截 id 清单收进 `logic-rejected-ids-fold`（**"有几条被拦"常驻在折叠头与计数徽章上**）；结论 / 发布闸门 / 计数 / `blocking_issues` 一律常驻；原来铺在标题下的整段口径改成常驻摘要 + 完整口径（`logic-verification-note`） |
| **口径说明写的每一句都要对得上代码** | 两个组件的说明常量 + 组件头注释 | 说明里的机制逐条标注实现位置：机械复核的检查项在 `engine/logic_platform/verify.py`、模型的四条把关规则在 `engine/logic_platform/narration.py`、`can_publish` 恒为假在 `apply_verification`、重新校验重读磁盘在 `_read_lines`、`stale` 在 `backend/app/services/logic_platform_service.py` 的 `_apply_reviews`。**这条没有机器化断言，靠上面这张对照表人工复核**（见 `docs/features/evidence-fold.md` §2 第 6 条） |
| **新增折叠自查（带负向对照）** | `scripts/check_evidence_fold.mjs`（新）+ `frontend/evidence-check-entry.js`（新）+ `frontend/smoke-entry.js` | 用**后端真实讲稿载荷**在 jsdom 里单独挂载两个组件，断言"摘要常驻 / 收起但内容仍在 DOM 里 / 逐条证据一条不少 / 失败默认展开 / 翻开后仍能跳源码与确认"。**自带负向对照**：一个用 `v-if` 收起的对照组件，同一条断言必须 FAIL（否则那三条"内容仍在 DOM 里"的断言可能就是永远绿的假断言） |

> **证据折叠一轮的实测口径（屏幕输出，不是推断）**：
> `node scripts/check_evidence_fold.mjs` **全绿**（默认 27 条断言 + `N1` 负向对照如预期 FAIL）；
> 回归：走查在线 **109/109**（`--project lab_safety_assistant`）、在线 **109/109**（`--project python_dotenv`）、
> 离线 **55/55**（**三项与 UI 重设计一轮完全一致，说明呈现层改动没有碰既有机契约**）；
> `frontend/scripts/lp_smoke.mjs` **42/42**、`frontend/scripts/test_immersive_render.mjs` **全部通过**
> （后者是既有断言，其中"证据跳转按钮存在"这条直接证明了**收起状态下证据仍在渲染出来的 DOM 里**）；
> 只读验收 `python scripts/build_acceptance_report.py` **13/13 个脚本通过**
> （其中 `audit_hardcoding.py --include-frontend` **50 个文件 0 命中** —— 新增的两个组件没有引入业务硬编码）；
> `python scripts/verify_docs.py` **exit 0**。数字见 `validation/acceptance_latest.md`。
>
> **这一轮明确没做的**：① "折叠"的像素级效果（第一屏到底清爽了多少）**没有自动检查**，jsdom 不走样式，**要人眼看**；
> ② 没有在真实浏览器里点过（本环境起不来无头 Chromium，见 `docs/06` §19.5），点击是在 jsdom 里派发真实事件验证的；
> ③ 没有做长讲稿（段上限 24 段 × 每段 40 条陈述）展开全部折叠区的性能实测；
> ④ 说明文案与引擎真实机制的一致性**没有门禁**（只有人复核的对照表）。

**仓库卫生与基线（WO-01 一轮 + W0 集成轮，2026-09-26）**：这一轮**不改任何产品行为**，交付的是"所有并行线从同一个已提交的基线开工"：把此前几轮（阶段 0 / 文档拆分阶段 1·2 / UI 重设计 / 证据折叠 / 入口完善）**只在工作区里的改动**按轮次分次提交，并在 W0 集成轮打成标签 **`wave-0`**；清掉根目录零引用残留（已清理：`aud.m4s` / `vid.m4s` / `generated_assets_motion_tiles_20260926/` / 空目录 `assets/`）与 `sample_projects/flask_crud_demo` 的空壳（源码确认丢失、决定不恢复）。`.gitignore` 补上 `*.m4s` / `generated_assets_*` / `.ai_orchestrator/` 三条规则。清理登记见 `docs/90-archive.md` 附录 C.2，交接事实见 `docs/08` §19.6，顺带抓到的门禁缺陷见 `docs/08` §19.1 第 28 条。三条验收命令的原始输出见该轮交付说明；**明确没做的**：没有 push（`origin/master` 仍停在 `1d640fb`）。

**克隆完整性一轮（2026-09-26）：让「别人克隆下来」等于「作者本机」**

> 起因是一条验收标准：**别人 `git clone` 之后跑一条命令，应当拿到和作者本机一样的进度与数据。**
> 实测下来克隆会缺四样东西，缺哪一样都会让手册里的命令在别人机器上直接跑不通。
> 这一轮**不改任何产品行为、不改任何判定口径**，改的全是"仓库里到底有没有那份东西"。

| 缺什么 | 为什么会缺 | 这一轮怎么修 |
|---|---|---|
| `validation/flask` 的**全部源码** | 它在索引里是 gitlink（mode `160000`），而仓库**没有 `.gitmodules`** → 克隆下来是个**空目录**；于是三个真实第三方验证项目（`python_dotenv` / `flask` / `urllib3`）少一个 | `validation/flask` 里的 `.git` 改名为 `.git.bak`（**与 `validation/urllib3` 同一惯例**），把 236 个源码文件纳入跟踪。顺带解除了"`git status` 必须加 `--ignore-submodules=all`"这条老约束（见 `docs/06` §19.5） |
| `validation/results/` 的**事实表与深分析产物** | 根 `.gitignore` 里的 `results/` 是"任何层级叫 results 都排掉"的无差别规则，把**证据层**一起排掉了；而手册 §20.3 ⑥ 是把其中的 `python_dotenv_facts.csv` 当**输入**用的 | 加一条放行规则（见下方代码块），10 个文件纳入跟踪 |
| 业务逻辑分析平台的 **demo 项目快照** | 整个 `backend/data/logic_platform/` 被忽略（**原意是对的**：挡住用户上传件） | 改成"忽略子项 + 逐项放行"：只放行 `lab_safety_assistant` 与 `python_dotenv` —— 这两个的 `meta.json` 里 `source_kind` 是 `demo`、**没有 source/ 副本**、`source_root_rel` 指向仓库内**已跟踪的相对路径**、不含任何绝对路径 |
| **一条装环境的命令** | 原先 §0.3 直接从 `cd D:\learn_with_ai` 开始，隐含"作者机器上一切已装好"，README 里也没有 clone 步骤 | 新增 `scripts/bootstrap.ps1`（前置检查 → 建 `.venv` → 装两份 requirements → 前端 npm ci → 跑 `build_demo_snapshots.py`），并在 `README.md` §0.3 补上「从零克隆」一段 |

其中那条放行规则的写法有个**实测踩到的坑**（已并入 `docs/08` §19.1 第 29 条）：
忽略整个父目录后再用 `!` 放行子目录**是不生效的**（git 的规则：父目录被排除时，子目录上的放行不生效），
必须写成"忽略子项 + 逐项放行"：

```gitignore
backend/data/logic_platform/*
!backend/data/logic_platform/lab_safety_assistant/
!backend/data/logic_platform/python_dotenv/
```

**故意不进来、且必须继续不进来的**：`backend/data/logic_platform/` 下那 6 个 lp_ 前缀项目
（`source_kind` 是 `upload`，`source/` 里是**用户上传源码的副本** —— 提交它等于把别人上传的代码公开出去）、
`.venv`、`frontend/node_modules/`、`frontend/dist/`、`frontend/.smoke-dist/`（都可再生，加 `-Build` 一条命令就能重建）。
**这一轮明确没做的**：① 没有把任何运行产物塞进仓库去换"看起来完整"；
② `validation/urllib3` 按它自己 `.gitignore` 的 `.*` 规则仍不含点文件（沿用原有处置，这一轮没动它）；
③ 前端构建产物仍靠 `-Build` 现场生成，**没有**提交 `dist`。

**顺带修掉一个「克隆下来装不上」的根因（本轮第二次提交）**：全新克隆里 `npm ci` **必然失败** ——
`frontend/package-lock.json` 里没有 `jsdom`，而 `package.json` 声明的 `^24.1.3` 又与本机实际在跑的
**29.1.1** 对不上（`npm ls --depth=0` 直接标 `invalid`）。修法是把声明改成与实跑一致的 `^29.1.1`
再重建锁文件；实测**既有包 0 个版本变化**、新增 38 个是 jsdom 29 的依赖子树、删掉的 50 个是 P0-16
早已记录的死依赖树，`npm ci` 在**全新克隆**里通过。台账见 `docs/08` §19.1 第 30 条。

**本轮实测：全新克隆（从 GitHub 拉，不是本地目录）**

| 检查项 | 实测结果 |
|---|---|
| 克隆下来的跟踪文件数 | 688（= 本地的 431 + flask 236 + 证据层 10 + demo 11），**0 个 gitlink** |
| 以前会缺的那三块 | `validation/flask` 的源码、`validation/results/` 的 10 个证据文件、两个 `source_kind=demo` 的平台项目 —— **全部就位** |
| 隐私红线 | 克隆里 `lp_` 前缀的上传件目录数：**0**（仍被忽略） |
| 克隆后 `git status` | 干净可跑，**不需要** `--ignore-submodules=all`（老约束确实解除了） |
| 那"一条命令" | `powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1` **退出码 0** |
| `npm ci` | **通过**；装出来的 `jsdom@29.1.1` 与作者本机**一致**（修复前装到的是 24.1.3 —— 这就是第 30 条那个缺陷的实证） |
| 克隆里跑默认验收组 | 全部通过，**逐项数字与作者本机相同**（含依赖 flask 源码的 `scripts/test_business_graph.py` —— 它的 4 个验证项目里就有 `validation/flask`，修复前那是个空目录） |
| 克隆里构建走查 bundle + 跑走查 | 构建成功；走查 **109 条断言全部通过**（用的是克隆自己装出来的依赖、克隆自己构建的产物） |

> 临时克隆目录验完即删，可 1:1 重现（`git clone` + 上面那条 bootstrap）。
> **明确没验的**：① 没在第二台机器或干净系统上验（仍是同一台机器、同一个 python 与 node 版本）；
> ② 克隆里的产物构建只验了走查 bundle，**没有**验 `frontend/dist` 的正式构建；
> ③ 没验 macOS / Linux（脚本与文档目前都是 Windows 口径，`bootstrap.ps1` 也只有 PowerShell 版）。

**部署说明一轮（2026-09-26）：把「怎么装到另一台机器上」写成一份文档，并补上正式构建的实测**

> 起因是**仓库里根本没有一份部署说明**：`README.md` §0.3 讲的是"作者本机怎么跑"，
> `docs/06-runbook.md` 是命令手册与排障，两者都**没有**回答"换一台机器要装什么、起哪几个进程、
> 前端产物怎么构建、能不能放到局域网/公网"。于是新增 `docs/11-deployment.md`（第二十五章），
> 并顺手补掉了上一轮明确留下的那条空档 —— **正式构建（`frontend/dist`）此前没验过**。
> 这一轮**只加文档、不改任何产品行为、不改任何判定口径**。

| 这一轮补上什么 | 依据 / 实测 |
|---|---|
| 支持 / 未做的部署形态一次说清 | 未做：容器化、反向代理、HTTPS、鉴权、进程守护、多副本（依据是仓库里确实没有这些文件，且 `backend/app/main.py` 模块头写着 no auth） |
| **前端正式构建首次实测** | `node node_modules/vite/bin/vite.js build`：`2156 modules transformed`、`built in 11.27s`、退出码 0；`frontend/dist` 合计 **4.89 MB**；设了 `VITE_API_BASE` 之后该字符串确实出现在产物的 JS 里（构建时烘入） |
| **静态托管路径实测** | `vite preview --port 4173`：`/` 返回 200；`/demo/project_analysis.json` 返回 200（473914 字节）；带 `Origin` 的跨源请求被后端回显 `Access-Control-Allow-Origin` |
| 启动方式的两种写法 | 从仓库根目录 `python -m uvicorn backend.app.main:app ...` **成功**；`python backend/app/main.py` **失败**（`ModuleNotFoundError: No module named 'app'`） |
| **安全边界写成部署前置条件** | 实测 `?mode=teacher` 的响应里有 `correct_answers`，默认 `mode=student` 没有；接口层无鉴权 → 文档明写"只在本机或可信局域网用，**现在不要上公网**" |
| 数据与可写目录 | 后端按仓库目录定位数据（`project_store.py:42` 的 `parents[3]`），所以**不能只拷 `backend/`**；唯一"跑出来又不在 git 里"的是 `backend/data` |
| **完整验收组重跑通过** | `python scripts/build_acceptance_report.py --with-backend --with-node` **全部通过（18/18）**：含 4 条走查（在线 109/109 ×2、离线 55/55 ×2）与平台接口测试 37/37；数字以 `validation/acceptance_latest.md` 为准 |
| **负向对照：走查失败≠前端坏了** | 中途只起了 8000 后端、没起 5173 dev server，四条走查**全部** FAIL 在 `waitFor 超时: 题目渲染`；把 dev server 起回来，同一条命令**恢复通过**。原因：走查的 `/demo/...` 请求走 5173（`scripts/browser_clickthrough.mjs` 默认 `--base http://127.0.0.1:5173`），与后端无关。这条已写进 `docs/11-deployment.md` §25.7 |

> **这一轮明确没做的**：① 没有验真实反向代理（nginx / Caddy 同源单端口）—— 仓库里没有配置，只说明了"没做"；
> ② 没有验 macOS / Linux；③ 没有验第二台机器（也没重跑 `bootstrap.ps1` 从零装一遍，
> 它的实测证据在克隆完整性一轮）；④ 没有做并发/压力实测；
> ⑤ **没有把前端产物提交进仓库**（仍靠现场构建，`frontend/dist` 不在 git 里）；
> ⑥ 部署文档里的命令与端口**没有机器化门禁**（`verify_docs.py` 只保证路径不悬空、数字不漂移，
> 不保证"这条命令真的能起服务"）—— 靠本表这轮实测留痕；
> ⑦ **没有在真实浏览器里渲染过**：界面行为仍是 jsdom 走查的结论（本轮跑过、全绿），CSS 与像素级效果仍未验。

### 16.2 ⚠️ 部分完成

**入口完善一轮（2026-09-26）**：系统首页新增本地演示登录窗口（可游客继续）、`/` 快捷搜索和业务模块快捷跳转。搜索直接复用现有契约与图谱卡片，不新增业务判定；登录明确标注为本地演示身份。编译验证：`node node_modules/vite/bin/vite.js build` 通过。完整边界见 `docs/features/login-and-quick-navigation.md`。

| 项 | 现状 |
|---|---|
| 前端业务图谱 | 已作为**培训工作区里的一个阶段**接入（UI 重设计一轮后，工作区内的五个阶段分成「阶段主线」项目认知 / 模块卡片 / 设计画布 与「项目视图」训练关卡 / 业务图谱两组，见 §12.1），**但还没有独立的 8 阶段信息架构**（无 `vue-router` 深链）。UI 重设计一轮新增的**系统主页面**只是多了一个默认落地页与功能优先级分层，不改变这个结论 |
| 培训阶段一「项目认知」 | 页面与判定链路已落地；**但比对键目前实际只有域名**——两个演示项目的域 `objective` 全是空串（引擎不编业务含义），所以"命中"暂时只代表提到了模块名。教师填上 `objective` 后会自动参与比对，无需改代码 |
| 培训阶段二「模块卡片学习」 | 引擎 / 后端已通过机器化验收（A10 + 40/40）；**前端走查已复核**：UI 重设计一轮实跑在线 **109/109**（两个项目各一次）、离线 **55/55**（历史：Sprint 5 的走查口径是 99/99 与 45/45；`python_dotenv` 的 71/71 是 Sprint 4 实跑）（走查里断言"题目文本与后端下发的一致""卡片一张不少""提交前不渲染覆盖清单"）。另有一条口径偏差已写进 §4 阶段二：培养方案原话是"比对 `verified` 字段"，实现是"只挡 `unconfirmed`"，理由是不允许两套"未确认"判定 |
| 阶段一 / 二的教学路线 | 阶段二的问题与外置映射在 `lexicon/stage_questions.json`；但**「有哪几个阶段、按什么顺序」仍写在前端**（`TrainingView.vue`），没有 `teaching_plan.json`（见 10.3 的说明） |
| 阶段一的会话记录 | 草稿存 `localStorage['lwai.orientation.draft.<project_id>']`；**报告不持久化**（图谱 `source_hash` 变了以后旧结论就是错的），刷新后重算 |
| 教师审核 | 只覆盖关键实现；**模块改名、图谱审核、Gold Graph 编辑器都没有** |
| 种子图谱兜底 | ✅ 优先级 4 二轮已落地 `sample_projects/lab_safety_assistant/business_graph.seed.json`（5 条域目标 + 3 条二级目标，教师确认）。**仍未做的**：`python_dotenv` 没有种子图谱（它继续走纯自动结果 `needs_review`）；`does_not` / `inputs` / `outputs` 这些可锁字段这一轮**没有**由教师填写，仍用自动结果 |
| 训练题第 1/2/3/4 关 | ✅ 优先级 4 一轮修第 2 关（每个够格业务模块一道）、二轮修第 3/4 关（每条业务流程 / 每条关键实现一道），实测 `lab_safety_assistant` **4 → 7 → 12 道**。**第 1 关不需要改**（它是多选，一道题已覆盖全部业务模块，见 16.1 末的说明）。**仍未做的**：`python_dotenv` 第 2 关仍一道不出（只有一个可用的业务语义文本）、第 4 关干扰项仍是固定模板 |
| 设计模式识别 | 检测器启发式质量**仍未提升**（维持「不进学生视图 / 不作评分维度」的决策，理由与证据见 §19.2 第 ⑱ 条）。**但优先级 4 一轮发现该决策此前并没有被真正执行**——模式名通过 `design_approach` / `importance_reasons` 进了学生题干与讲解，还给了重要性 +1.0 分；已修好并加了机器检查（`validate_contract.py` 第 9 项） |
| 死资源清理 | ✅ 已完成（`UploadView.vue`、旧 deep_analysis 快照、`@vueuse/*`、无用 assets 已清理） |
| 阶段四 / 五「设计画布 + 六维评审」 | 引擎 / 后端 / 前端 / 走查均已落地（见 16.1 的 Sprint 5 表）。**优先级 3.5 一轮给 `lab_safety_assistant` 补上了教师确认过的种子**，所以 `required_relations` / `required_edge_cases` / `forbidden_merges` / `acceptable_alternatives` 在这个项目上**真的参与判定了**；`python_dotenv` 没有种子，仍是自动提炼（`auto_from_project`、标「待教师确认」），那四项在它上面依旧「本轮未评估」。**两个项目的口径不同，对外要说清是哪一个**。仍未做的：`python_dotenv` 的种子、多条种子任务（一个项目有种子后自动任务不再生成，见下方新增行） |
| 设计画布的状态管理 | 画布状态（nodes / edges / rationale）在组件内 + `localStorage['lwai.design.draft.<project_id>.<task_id>']`，**没有** `stores/designCanvas.js`（README §12.7 列的那只 store 仍未建）；报告**不持久化**（理由与阶段一同：`source_hash` 变了旧结论就是错的） |
| 教师种子的覆盖面（优先级 3.5 一轮新增） | 只有 `lab_safety_assistant` **一个**项目有种子。而且 `task_builder.py:533-539` 的语义是「**有种子就只返回种子任务**」，所以该项目的设计任务由 3 个变 1 个 —— 这是刻意的（教师给了权威任务就不再生成自动任务），但**要给学生多道任务就得在种子里写多条**，目前只写了 1 条。`test_design_seed.py` 用一条断言把这个行为钉住了，避免以后被当成 bug"修"掉 |

### 16.3 ❌ 未开始

- 培训阶段三（流程推演的画布化）与阶段六（重构挑战）；
- `engine/design/reconstruct.py`（重构挑战与影响范围，§9.3，**待建**）—— **`engine/design/` 的其余七个文件已实现**（任务生成 / matcher / graph_checks / alternatives / submission / rubric / feedback）；
- 学习路线契约 `teaching_plan.json` 与 `engine/teaching/` 的其余产物（能力报告）；
- 学习会话接口（`/api/sessions`）与存储层（当前只有 `localStorage`）；
- 教师工具（Gold Graph 编辑器、词典编辑、权重调整在线接口）；
  —— **种子文件都已落地**：`design_tasks.seed.json` 有 `lab_safety_assistant` 的确认版（优先级 3.5 一轮），
  `business_graph.seed.json` 也有（优先级 4 二轮）；两个项目**都还缺**另一份（`python_dotenv` 两份都没有）；
- `vue-router` 深链（B 阶段）；
- Java / JavaScript 支持（**维持不做**）；
- 覆盖度评分器与 Skill 失效点实测报告。

### 16.4 两个「概念并存」的遗留问题（现在不要动）

- **代码模块（`modules`，8 类固定词表）与业务域（`business_graph.domains`）并存**：
  训练题还在用前者。长期应统一到业务域，但**现在不要动**，留给下一轮一并处理。
- **两套调用图**：`engine/analyzer/call_graph.py`（单文件、按名字匹配）与
  `engine/deep_analyzer/project_call_graph.py`（项目级）。
  前者**不是死代码**，它被函数级管线与旧分析视图消费。正确做法是**收敛到项目级调用图**，而不是删掉它。

---

## 十七、机器化验收：命令与结果

### 17.1 一条命令跑完自检

```bash
python scripts/verify_sprint0.py
```

**最近一次运行结果（阶段 0 一轮实跑，机器产出）：`14/14 项通过`**

> 这一段与 §17.2 的所有数字都由 `python scripts/build_acceptance_report.py` 实跑产出，
> 并被 `python scripts/verify_docs.py` 核对（对不上就 exit 1）。**完整记录**见
> `validation/acceptance_latest.md`（人读）/ `validation/acceptance_latest.json`（机器读）
> —— 那两个文件是**机器生成的，不要手改**。

| 编号 | 验收项 | 结果 |
|---|---|---|
| A1 | 契约校验（无绝对路径 / 无 `correct_answers` / 无 `_inferred_` / 模块文件为相对路径 / **学生可见文本里无设计模式结论**） | 两个项目全部 PASS |
| A2 | **同一份代码双跑输出逐字节一致**（同进程双跑） | 两个项目一致；**跨进程**另由 `check_determinism.py --cross-process` 覆盖（优先级 4 二轮新增，A2 本身查不出这一类） |
| A3 | 引擎代码里没有业务硬编码 | **扫描 62 个文件，命中 0 处，解析错误 0 个**（`build_acceptance_report.py` 实跑口径；历史：优先级 4 一轮时是 54 个，Sprint 5 后新增设计层文件） |
| A4 | `engine/business_logic` 可导入、契约别名正确、坏引用已清除 | PASS |
| A5 | AST 缓存生效，每个文件只解析一次 | 6 个文件：source `6 miss / 40 hit`，tree `6 miss / 88 hit` |
| A6 | 两个演示项目的快照 / 答案表 / 源码副本齐全 | PASS |
| A7 | 学生快照无答案与讲解，教师模式补回 | PASS |
| A8 | 后端判题正确且不泄漏答案本身 | PASS |
| A9 | **阶段一覆盖度报告：不打分 / 不丢域 / 确定性 / 拒绝空提交** | 2 个项目通过 |
| A10 | **阶段二事实覆盖报告：题目来自配置 / 卡片不丢 / 不打分 / 待确认不比对** | 2 个项目、**64 张卡片**通过（其中 **17 张**含待教师确认字段 —— 优先级 4 二轮加种子图谱后由 25 降到 17，`lab_safety_assistant` 的 8 张归零） |
| A11 | **阶段四设计层六维评审：可见性 / not_evaluated / 确定性 / 入口校验** | 2 个项目、**4 个任务**通过（优先级 3.5 一轮：由 6 变 4，因为 `lab_safety_assistant` 的 3 个自动任务被 1 个教师种子任务取代） |

### 17.2 全部验收命令

```bash
# —— 环境引导（克隆之后的第一步；作者本机依赖已装齐，可跳过）——
powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1   # 建 .venv + 装依赖 + npm ci + 生成演示快照
#   开关：-Build 顺带构建 frontend/dist 与走查 bundle；-Verify 顺带跑下面那三道门禁；-SkipFrontend 只装 Python 侧

# —— 文档门禁（阶段 0 新增；先跑它，再跑别的，能立刻知道文档有没有说过头）——
python scripts/build_acceptance_report.py       # 跑 13 个只读验收脚本 → validation/acceptance_latest.json / .md
python scripts/verify_docs.py                   # 核对文档：路径 / 章节引用 / 版本号 / 数字 / 行号 / 文档清单（7 项）
python scripts/pack_docs.py                     # 按索引顺序把 docs/ 拼成单文件 docs/_bundle.md（一次性交付用）

# —— 引擎侧 ——
python scripts/verify_sprint0.py                # 总验收（A1–A11；最近一次实跑见 validation/acceptance_latest.md）
python scripts/test_business_graph.py           # 业务图谱引擎测试（161/161 项通过，4 个项目）
python scripts/test_teaching_coverage.py        # 阶段一覆盖度比对器（Sprint 5 后重跑仍 22/22，2 个项目）
python scripts/test_teaching_card_coverage.py   # 阶段二事实覆盖比对器（Sprint 5 后重跑仍 40/40，2 个项目 + 合成用例）
python scripts/test_design_rubric.py            # 设计层六维评审（Sprint 5：90/90，合成用例 + 2 个真实项目 + 纯规则/业务词审计）
python scripts/test_training_questions.py       # 第 2/3/4 关「一关多题」（优先级 4 二轮：53/53，2 个真实项目 + 合成边界）
python scripts/test_design_seed.py              # 教师设计任务种子（优先级 3.5 一轮：33/33，直接读仓库里的种子文件）
python scripts/check_determinism.py --cross-process   # 跨进程逐字节一致（优先级 4 二轮：不同 PYTHONHASHSEED 各起一个子进程）
python scripts/validate_business_graph.py \
  --output validation/business_graph_validation.md \
  --json-output validation/business_graph_metrics.json --emit-review
python scripts/validate_contract.py --project sample_projects/lab_safety_assistant
python scripts/check_determinism.py          # 同进程双跑，逐字段比对
python scripts/audit_hardcoding.py --include-frontend   # 0 命中，exit 0

# —— 前端 ——
cd frontend && npm run build                 # Sprint 5 后实跑成功（2139 modules transformed，15.59s；等价的 node node_modules/vite/bin/vite.js build）
cd frontend && node node_modules/vite/bin/vite.js build --config vite.smoke.config.js   # 走查 bundle（UI 重设计一轮实跑：2148 modules transformed；历史：Sprint 5 是 2135）
node scripts/browser_clickthrough.mjs --project lab_safety_assistant             # UI 重设计一轮实跑 109/109（含 10 条主页面断言）；历史：Sprint 5 实跑 99/99
node scripts/browser_clickthrough.mjs --project python_dotenv                    # UI 重设计一轮实跑 109/109；历史：Sprint 4 实跑 71/71、Sprint 5 未在此项目上重跑
node scripts/browser_clickthrough.mjs --project lab_safety_assistant --offline   # UI 重设计一轮实跑 55/55；历史：Sprint 5 实跑 45/45（含 4 条设计层离线断言）

# —— 逻辑平台的前端自测（需要后端；命令清单也见 docs/05-logic-platform.md §21.7）——
node frontend/scripts/test_immersive_render.mjs   # 讲稿 SSR 渲染自测（证据折叠一轮实跑：全部通过）
node frontend/scripts/lp_smoke.mjs                # 六步流程点击流自测（证据折叠一轮实跑：42/42）
node scripts/check_evidence_fold.mjs              # 证据折叠自查（证据折叠一轮新增：实跑全绿，含 1 条负向对照）

# —— 旧管线冒烟（保持通过）——
python scripts/test_project_analyzer.py
python scripts/test_deep_analyzer.py
python scripts/test_full_engine.py
```

> ⚠️ 口径说明（**别把没跑过的数字当成跑过的**）：
> - **Sprint 5 后实跑的（下面这些数字都是屏幕输出，不是推断）**：
>   `verify_sprint0.py`（**14/14**，A1–A11）、`test_design_rubric.py`（**90/90**）、
>   `test_teaching_coverage.py`（22/22 —— 设计层复用它的命中判定后**重跑仍全绿**）、
>   `test_teaching_card_coverage.py`（40/40 —— 同上）、
>   走查 bundle 重建（2135 modules transformed）、**`npm run build`（2139 modules transformed，15.59s）**、
>   走查在线 **99/99** 与离线 **45/45**。
> - **Sprint 4 实跑、Sprint 5 未重跑的**：`test_business_graph.py`（161/161）、
>   `check_determinism.py`、`validate_contract.py`、`audit_hardcoding.py --include-frontend`、
>   旧管线三个冒烟脚本、`validate_business_graph.py`。
>   其中 `audit_hardcoding.py` 的引擎侧口径在 Sprint 5 被 A3 覆盖（**62 个文件 0 命中**，
>   比 Sprint 4 的 46 个多了新增的 8 个设计层文件），
>   `test_design_rubric.py` 里也**复用同一个审计脚本**检查了 `engine/design/`；
>   但**前端侧（含新组件 `StageDesign.vue`）没有重跑**。
> - **优先级 4 二轮实跑的（下面这些数字都是屏幕输出，不是推断）**：
>   `test_training_questions.py`（**53/53**，由 31 项扩到 53 项；训练题 `lab_safety_assistant`
>   **7 → 12 道**、`python_dotenv` **3 → 8 道**）、`verify_sprint0.py`（**14/14**；
>   A10 的「含待教师确认字段」由 25 变 **17**）、`test_business_graph.py`（161/161）、
>   阶段一 22/22、阶段二 40/40、设计层 90/90、教师任务种子 33/33、
>   `check_determinism.py`（同进程一致；**`--cross-process` 也一致**，并做了负向对照）、
>   `audit_hardcoding.py --include-frontend`（引擎 0 / 前端 0）、
>   `validate_contract.py`（**两个项目**各自全通过）、旧管线三个冒烟脚本（退出码 0）、
>   `build_demo_snapshots.py` **连续三次**产出的学生快照 sha256 完全相同（修复跨进程不确定性之后）。
>   走查：在线 **99/99**（`lab_safety_assistant`）、在线 **99/99**（`python_dotenv`，阶段一/二落在有种子图谱的 `lab_safety_assistant` 上）、
>   离线 **45/45**。本轮**没有改任何前端文件**，`.smoke-dist` 仍是最新的，所以没有重建 bundle。
> - ⚠️ **两条顺序陷阱（优先级 4 二轮踩到，务必按这个顺序跑）**：
>   ① **改题目之后必须重跑 `build_demo_snapshots.py`** —— 学生快照与后端答案表是它一起产出的，
>   只重跑一半就会出现"题目 12 道 / 答案表 7 条"的错位（判题按下标）；
>   ② **旧管线冒烟（`test_project_analyzer.py`）会覆盖 `frontend/public/demo/project_analysis.json`**，
>   而且它写的版本与产物脚本**不完全相同**（实测同一轮里 sha256 不同）—— 所以它是**产物脚本之后的步骤**，
>   跑过它之后要再跑一次 `build_demo_snapshots.py`，否则离线快照不是 A6/A7 验过的那一份。
> - **优先级 3.5 一轮实跑的（下面这些数字都是屏幕输出，不是推断）**：
>   `test_design_seed.py`（**33/33**，新增）、`verify_sprint0.py`（**14/14**，其中 A11 由 6 个任务变 **4 个**）、
>   `test_design_rubric.py`（90/90）、`test_business_graph.py`（161/161）、阶段一 22/22、阶段二 40/40、
>   `test_training_questions.py`（31/31，**历史：这一轮当时的口径，优先级 4 二轮已扩到 53/53**）、`check_determinism.py`（两个项目一致）、
>   `audit_hardcoding.py --include-frontend`（引擎 0 / 前端 0）、
>   `validate_contract.py`（**两个项目**，各自全通过）。
>   走查**这一轮重跑了**：在线 **99/99**（`lab_safety_assistant`）、在线 **99/99**（`python_dotenv`，
>   阶段四落在有种子那个项目上）、离线 **45/45**；本轮未改任何前端文件，`.smoke-dist`
>   （2026-09-24 12:27 构建）比 `frontend/src` 下所有文件都新，所以**没有重建 bundle**
>   （这一点与前两轮不同：那两轮都重建了）。

**人工核对（优先级 2）的两个命令 —— 它们不是"自检"，退出码取决于人有没有填**

```bash
# ① 生成判断材料（每个域摊开成一张卡片：能力点 / 成员函数 / 文件:行 / 聚类依据）
python scripts/export_domain_review_worksheet.py
#    → validation/graph_review_worksheet.md（覆盖 3 个真实第三方项目，跳过自造样本）

# ①' 只做一个项目的试点（一级域）：填判定 + 记引擎问题
python scripts/export_domain_review_worksheet.py --pilot validation/python_dotenv
#    → validation/pilot_review_python_dotenv.md

# ② 填完 validation/business_graph_validation.md 第 6 节的「人工判定」列之后，读回统计
python scripts/graph_review_report.py --verbose
#    → 划分错误率 / 命名不当率（域与功能点两个分母分开报）
#    → 顺带检查：有没有漏填的行、有没有非法取值、表格有没有被编辑坏
```

> ⚠️ **这两个命令不能放进上面那套"应当全部通过"的自检清单**：
> `graph_review_report.py` 的退出码是**验收语义**（0 = 判定列填满且取值合法），
> 判定列没填之前它**必然**退出码 1，且那个 1 是"还没人填"、不是"跑挂了"。
> 实测（优先级 2 备料一轮）：未填时退出码 1 并打印「还没填的行 **184** 处」；
> 填满且取值合法时退出码 0；把某行的 `|` 少写一个时退出码 1 并指出
> 「文件第 95 行（`d_binding`）列数是 6，应为 8」。
>
> ⚠️ **重新生成核对模板会冲掉已填的判定**（`validate_business_graph.py` 是覆盖写）：
> 要重跑模板，就**先**跑，再填；或者把填好的那份另存一个文件名。
> - **优先级 4 一轮实跑的**：`verify_sprint0.py`（**14/14**）、`test_training_questions.py`（**31/31**，新增）、
>   `test_business_graph.py`（161/161 —— 39×4 + 种子合并 5）、阶段一 22/22、阶段二 40/40、设计层 90/90、
>   `check_determinism.py`（两个项目一致）、`audit_hardcoding.py --include-frontend`（引擎 0 / 前端 0）、
>   `validate_contract.py`（两个项目 + 两份快照，含新增的第 9 项）、
>   `npm run build` 的等价命令 **2139 modules transformed（16.30s）**、
>   旧管线三个冒烟脚本（`test_project_analyzer.py` / `test_deep_analyzer.py` / `test_full_engine.py`）全部退出码 0。
> - **优先级 4 一轮没有重跑的（据实说明，别引用成跑过的）**：`node scripts/browser_clickthrough.mjs`（在线 99/99 / 离线 45/45
>   **在当时仍是 Sprint 5 的数字** —— 优先级 3.5 一轮已经补跑，见上；「只差起后端 + dev server」这一步也补上了）。原因有三条，缺一不可：① 走查加载的是 `.smoke-dist` **构建产物**，这一轮前端改过两个
>   `.vue`，不重建 bundle 就是拿旧代码跑；② 重建 bundle 与 dev server 都要 esbuild `spawn` 子进程，
>   在 `workspace-write` 下必然 `spawn EPERM`（这一轮跑 `vite build` 时复现，一次性放开权限才成功）；
>   ③ 走查需要 8000 端口上的后端与 5173 上的 dev server 同时在线。
>   **这一轮已做的**：两个 bundle 都重建了（`vite build` 2139 modules / 16.30s；
>   `vite build --config vite.smoke.config.js` **2135 modules / 13.12s**），
>   所以 `.smoke-dist` 与当前源码一致，下次跑走查不会拿到旧代码 —— **只差**起后端 + dev server 这两步。
>   另外走查的断言**不覆盖训练关卡**（它走的是阶段一 / 二 / 四与业务图谱），
>   所以这一轮两处改动（第 2 关出题、模式名不进学生文本）本来就不在它的断言范围内 ——
>   **不能拿它"没跑"当成"改动没验证"**：这两处分别由 `test_training_questions.py` 与
>   `validate_contract.py`（含负向对照）覆盖。
> - `node scripts/browser_clickthrough.mjs --project python_dotenv` 这一条 **Sprint 5 没有重跑**：
>   Sprint 5 只在 `lab_safety_assistant` 上跑了在线 / 离线两个场景。
>   但阶段四的断言在 lab_safety 那次运行时，**页面已经被前面的步骤切到了 `python_dotenv`**
>   （走查的深链步骤会切项目），所以那批设计层断言实际上是在 python_dotenv 上跑通的 ——
>   与阶段二 Sprint 4 的口径偏差是同一类情况，**据实写在这里，不当作"两个项目都跑过"**。
>   **→ 优先级 3.5 一轮把这个缺口补上了**：两个方向都跑了，各 99/99；
>   而且 `--project python_dotenv` 那一次**恰好让阶段四的断言落在有教师种子的
>   `lab_safety_assistant` 上**（种子生效的三条证据见 16.1 末）。这一组数字因此不再有口径偏差。
> - 走查项数的口径又变了（71/71 → 99/99）：Sprint 5 新增了 28 条阶段四断言
>   （离线场景 41/41 → 45/45 新增 4 条），所以"项数变多"是加了断言，不是原来有 28 项在失败。
> - **UI 重设计一轮的口径又变了（99/99 → 109/109、45/45 → 55/55）**：这一轮给走查新增了
>   **10 条系统主页面断言**，并把走查改成"先落在主页面 → 点进培训工作区"——
>   默认落地页从"训练关卡"变成了系统主页面，走查就必须按**真实用户路径**走，
>   否则它测的是一条用户已经不走的路径（这也是这一轮唯一改动走查脚本的理由）。
>   实跑：在线 **109/109**（`--project lab_safety_assistant`）、在线 **109/109**（`--project python_dotenv`）、
>   离线 **55/55**。跑之前重建了走查 bundle（`vite build --config vite.smoke.config.js`，
>   **2148 modules transformed**，10.31s），并确认 8000 上的后端与 5173 上的 dev server 同时在线。
>   `frontend/scripts/lp_smoke.mjs`（平台接线自测）同轮重跑 **42/42**（命令见 `docs/05` §21.8）。
> - **这一轮的走查真的抓到了一个真问题**（已记进 `docs/08` §19.1）：新写的"判分边界"文案里出现了
>   答案字段名（写成"答案（`correct_answers`）不下发"的禁令句式），于是
>   `DOM 中不含 correct_answers 字段名` 那条断言直接判 FAIL。修法是**改页面文案，不是放宽断言** ——
>   那条断言有意做得很粗（对整个 `documentElement` 做正则），它宁可误报也不该被文案牵着走。
>
> 引用任何数字前先重跑对应命令（这也是 13.2 证据纪律第 3 条的要求）。

### 17.3 演示用的两个项目

| project_id | 来源 | 规模 | 业务图谱 |
|---|---|---|---|
| `lab_safety_assistant` | 自造教学样本（默认） | 784 行 | 5 域 / 29 功能点 / L2 |
| `python_dotenv` | **真实第三方** | 1,112 行 | 6 域 / 24 功能点 / L2 |

切换方式：`?project=python_dotenv`（也是答辩时的深链）。

**阶段二的卡片规模（`GET .../teaching/module-card/task` 实测）**：

| project_id | 卡片总数（一级域 + 二级功能点） | 其中含「待教师确认」字段 | 首个卡片默认打开 |
|---|---:|---:|---|
| `lab_safety_assistant` | 34（5 + 29） | **0**（历史：加教师种子图谱之前是 8） | `d_1` 安全检查模块 |
| `python_dotenv` | 30（6 + 24） | 17 | `d_atom` Atom |

> 「含待教师确认字段」= 该卡片至少有一个字段的置信度是 `unconfirmed`（这些字段**不参与比对**，
> 页面会直接标出来）。**当前两个项目合计 64 张卡片里 17 张属于这一类**（A10 的实测数字；
> 历史：优先级 4 二轮加种子图谱之前是 25 张，`lab_safety_assistant` 的 8 张归零）。
> 也就是说**"哪些内容还不能比"在还没有教师种子的项目上仍然是常态**（`python_dotenv` 17/30）——
> 这正是不许编业务含义的代价，也是必须原样告诉学生的地方。

> 自造样本的一级业务域恰好是样本里写的那四个域 + 一个装配域：
> `安全检查模块 · 用户管理模块 · 设备管理模块 · 预约管理模块 · 系统装配（orchestrator）`。
> 这四个名字**不是写死的**——它们来自每个文件首行的中文 docstring，
> 引擎把「文件级中文 docstring」当作最强的命名信号。

### 17.4 第三方项目验证（真实、未参与规则调试）

```bash
python scripts/validate_business_graph.py \
  --output validation/business_graph_validation.md \
  --json-output validation/business_graph_metrics.json --emit-review
```

| 项目 | 类型 | 行数 | 域 | 功能点 | 事实 | 关系 | 流程 | 级别 |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `sample_projects/lab_safety_assistant` | **自造样本** | 784 | 5 | 29 | 133 | 8 | 6 | L2 |
| `validation/python_dotenv` | 真实第三方 | 1,112 | 6 | 24 | 74 | 3 | 8 | L2 |
| `validation/flask` | 真实第三方 | ~9.5k | 12 | 54 | 459 | 23 | 9 | L3 |
| `validation/urllib3` | 真实第三方 | ~13.4k | 19 | 69 | 1,044 | 22 | 8 | L3 |

**真实第三方项目数：3 个** ✅（累计约 **2.4 万行**，67 个源文件）。

**可机器判定的指标（4 个项目全部达标）**

| 指标 | 结果 | 说明 |
|---|---|---|
| 成员带行号 | **100%** | 每条功能点成员都能回指代码 —— 「可定位」站得住 |
| 二级卡片带证据 | **100%** | 每张卡片都有出处 |
| 事实带行号 | **100%** | 133 / 74 / 459 / 1044 条事实全部可核验 |
| 同进程双跑逐字节一致 | **✅ 4/4** | 「可复现」站得住 |
| 引擎业务硬编码 | **0 命中** | 业务词全部外置到 lexicon |

#### 真实第三方项目上的**短板**（必须如实写进材料）

| 短板 | 数据 | 说明 |
|---|---|---|
| **域名来源** | flask：docstring 0 / lexicon 0 / identifier 8 / structural 4；urllib3 同构 | 真实第三方项目是英文的、没有中文 docstring，域名的「作者原话」这条路走不通，只能退回**英文标识符词根**（如 `Base HTTP Connection`）。**中文命名能力目前只在中文项目上成立** |
| **待归类功能点** | flask **15/54（27.8%）**、urllib3 **19/69（27.5%）** | 词典覆盖不住这些项目的命名风格（`peek` / `has_next` / `advance` / `run_command`…）。这些功能点被合并成一个明确标注「待归类」的节点，而不是硬编一个名字 |
| **flat 层级域** | flask 7/12、urllib3 5/19 | 域内可识别能力不足 3 个时**诚实退化**为单层，不硬拆多级 |
| **objective 待教师填** | flask 21/54（38.9%）、urllib3 28/69（40.6%） | 设计使然：业务含义规则引擎给不出就不编 |
| **`inferred-low` 占比** | urllib3 域 6/19、功能点 29/69 | 置信度分层在真实项目上确实被大量用到——这些内容**不能直接进学生视图** |

#### ⚠️ 这份报告里**没有「准确率」**

这是刻意的，也是证据纪律的硬要求：

- 脚本只算**可机器判定**的部分（覆盖率、证据完整度、确定性、退化率）；
- **「划分对不对」必须人工核对**。报告第 6 节已生成人工核对模板
  （每个域 / 功能点一行，留出「人工判定」列，**脚本不填**）；
- 统计口径写清楚了：`划分错误 / 总域数` 才是「业务图谱划分错误率」，
  它和「事实错误率」**不是一回事，不能混着报**；
- **自造样本（lab_safety_assistant）在报告里被显著标注，且不生成核对模板**——
  它的规则就是照着它调的，等于训练集成绩。

> **现在可以说**：「在 3 个未参与规则调试的真实第三方项目上跑通了业务图谱生成，累计约 2.4 万行；
> 事实层证据完整度 100%；输出可复现（同进程双跑逐字节一致）；引擎里 0 处业务硬编码。」
>
> **不能说**：任何**准确率**数字 —— 那个数字还没有人工核对出来。

---

## 十八、下一步：主线优先级

> 排序原则来自「先清障 → 再建能力 → 再上界面 → 最后教师与重构」。
> 前 4 步（清障、契约接通、图谱引擎、图谱前端）已完成；第 5 步的**阶段一 / 二已完成（Sprint 3 / 4）**，
> **第 5 步里最难的「设计层」也已完成（Sprint 5，优先级 3）**，
> **优先级 3.5（设计任务种子）与优先级 4（种子图谱 + 第 3/4 关出题）各完成一轮**。
> **接下来按优先级 2（人工核对，必须由人填）→ 优先级 5 走。**
> ⚠️ 优先级 2 是**唯一**能产出「准确率」的途径，而准确率是评委必问项；
> 它只能由人逐行填（脚本只生成模板，`§17.4` 说明了为什么）。
> **逐条执行口径不在本节**：本节只给**优先级**（做什么、为什么、什么条件下做）。
> 把其中"还没做"的条目拆成"谁做 / 独占哪些文件 / 怎么验收 / 哪些能同时开"的是 `docs/10-work-orders.md`；
> **它不含优先级判断，冲突时一律以本节为准**（`docs/00-index.md` §3.2 第 6 条：不许出现两份「下一步」）。

### 优先级 1 · 模块卡片进教学流程（P1-07 / P1-08）—— 阶段一 / 二均已完成，下一步接优先级 3

- **为什么**：业务图谱已经现成（接口和快照里都有），但**教学流程里还没用上**；
  现在学生做的还是「四关选择题」，训练目标没变。这是投入产出比最高的一步。
- **做什么**：
  1. ~~阶段一「项目认知」~~ ✅ **已完成（Sprint 3）**：展示一级业务域 + 复杂度，
     学生用自己的话写「这个项目为什么需要这些模块」，系统**只输出覆盖度报告，不打分**。
     实现见 `engine/teaching/coverage.py` + `frontend/src/components/StageOrientation.vue`；
  2. ~~阶段二「模块卡片学习」~~ ✅ **已完成（Sprint 4）**：逐张卡片 + 五个问题（解决什么 / 输入 / 输出 /
     改变什么状态 / **为什么不合并**），系统只做**事实覆盖比对**，卡片本身 `unconfirmed`
     的字段不参与判分，改提示「该卡片待教师确认」。
     实现见 `engine/teaching/card_coverage.py` + `engine/lexicon/stage_questions.json` +
     `frontend/src/components/StageModuleCard.vue`。
     **确实复用了阶段一的命中判定**（`coverage.py` 的 `prepare_text` / `add_comparison_key` /
     `key_hit`），没有另写第二套 —— 这条要求已满足。
- **验收**：换一份项目数据，阶段一 / 二的题目与卡片内容全部来自 `business_graph`，页面不改代码 ✅
  （阶段一走查在 `python_dotenv` 上跑通；阶段二题目与字段映射来自词典，前端不认识任何业务字段——
  走查直接断言**页面上的题目文本与后端 `task` 接口返回的逐条一致**，且**卡片数一张不少**；
  两个在线场景各跑 **99/99**（`lab_safety_assistant`，Sprint 5 后重跑）与 71/71（`python_dotenv`，**历史：Sprint 4 实跑**），其中阶段二那一段落在的正是**另一个项目**上）；
  两个阶段**都没有分数**，只有覆盖清单 ✅（A9 / A10 逐键扫描 + 测试断言）。
- **注意**：12.6 的交互契约（学生先输出、系统后反馈）是硬要求，反馈区域必须在提交前不渲染 ✅
  （阶段一走查断言提交前 `[data-test="orientation-report"]` 不存在；
  阶段二走查同样断言 `[data-test="module-card-report"]` 不存在，且**卡片内容默认收起**、
  由学生主动点 `[data-test="module-card-reveal"]` 展开——理由见 §4 阶段二末尾）。
- **遗留的两件事**（都属于"能不能上台"的级别）：
  ① 域 `objective` 全空 → 阶段一的覆盖度实际只用域名比对，**教师填目标后才有真正的"理解覆盖度"**；
  ② 「有哪几个阶段、按什么顺序」仍写在前端 `TrainingView.vue`，没有 `teaching_plan.json`
     （见 10.3 的取舍说明；阶段二已经把**问题文本**外置到词典，剩下的是阶段编排）。

### 优先级 2 · 人工核对业务图谱 —— 便宜且直接决定能不能上台

- **为什么**：这是**唯一**能产出「准确率」这个数字的途径，而「准确率」是评委必问项。
  模板已经生成好了（`validation/business_graph_validation.md` 第 6 节，每个域 / 功能点一行）。
- **做什么**：按模板逐行填「正确 / 命名不当 / 划分错误 / 无法判定」；
  统计口径是 `划分错误 / 总域数`，**不要**和「事实错误率」混着报。
- **验收**：报告第 6 节的「人工判定」列被填满，并算出两个独立的数字：
  业务图谱**划分**错误率、模块**命名**不当率。
- **注意**：自造样本 `lab_safety_assistant` **不许**用来报准确率
  （它的核对模板是脚本**刻意不生成**的，见 §17.4）。
- **现状（优先级 2 备料一轮实测）**：待判定的行是 **37 行域 + 147 行功能点 = 184 行**，
  **全部为空** —— 脚本不填，只能由人填。
  **⏸️ 这一项已决定主动延后到「引擎冻结之后」，理由与触发条件见本节末尾**（不是漏做）。
- **已具备的操作路径（优先级 2 备料一轮补齐的两个工具）**：
  1. `python scripts/export_domain_review_worksheet.py` →
     `validation/graph_review_worksheet.md`：把 37 个域各自摊开成一张卡片
     （**能力点 / 成员函数带 `文件:行` / 聚类依据 / 涉及文件**），
     回答「这一堆函数在业务上是不是同一个模块」时不用在表格与源码之间来回找；
  2. 填完判定列后 `python scripts/graph_review_report.py --verbose`：
     读回人工判定 → 两个比率 + 漏填清单 + 非法取值清单 + 表格结构检查，退出码即验收结论。
  3. **试点模式**（`--pilot <project>`）：只做一个项目的一级域，产出
     `validation/pilot_review_<project>.md`（填判定表 + 判断材料 + **引擎问题清单模板**）。
     用于在正式核对之前校准工期、检验判定词好不好用、并产出一份**不随哈希失效**的引擎待改清单。
  **建议分批**：统计口径的分母是**总域数**，所以**先填完 37 行域就能产出两个可对外报的数字**，
  147 行功能点是第二批（分母不同，单独报、不许与域相加）。
- ⚠️ **两条操作纪律**：① **重新生成模板会冲掉已填的判定**（覆盖写）——要重跑就先跑再填，
  或把填好的那份另存文件名；② 四个判定词之外的值会被统计器判为非法（例如填「对」），
  它**不会**替你猜意思。

#### ⏸️ 决定：这一项**主动延后**（2026-09-24，优先级 2 备料一轮记录）

> 这不是"漏做"，是**明确决定排在后面**。写在这里是因为 §19.2 ⑱ 那类事故的成因正是
> 「文档里有一条待办、谁也没执行、也没人发现」——所以"决定不做/延后"必须留痕。

**延后的理由（技术性的，不是偷懒）**

1. **人工判定的结论绑定 `source_hash`**：README §6.1 的纪律就是"重新分析后如果哈希变化，
   旧审核不能静默覆盖新结果，必须返回 `stale`"。而**图谱审核的 `stale` 机制还没实现**
   （§16.2：目前只有「关键实现确认 / 拒绝」落了地）。
   ⇒ 现在填 184 行，没有机制帮你判断"引擎改过之后哪些还成立"，**只能全部重做**。
2. **引擎还在改，而且改的正是聚类与命名这一层**（优先级 4 二轮就动过
   `design_pattern_detector` / `key_implementation` 的输出；词典与聚类信号更容易被后续功能改动波及）。
   凡是能改变 `domain_id` / 域名 / 成员归属的改动，都会让已填的判定失效。
3. ⇒ 正确顺序是：**先完善功能 → 引擎冻结 → 再做正式核对**，总工时最省。

**延后不阻塞上台**（这一条有文档依据，不是自我安慰）

- §13.7 不承诺清单本来就写着「不承诺自动理解所有项目的真实业务含义」
  「不承诺不经教师审核就能生成可直接用于课程的教学材料」；
- §13.1 给了替代表述：❌「分析准确率 95%」→ ✅「事实层来自 AST 直接解析，可复现；
  语义层标注为待确认」；
- §18 那份「明确不许上台的半成品」只有四项（六维填假分 / 自动图谱未标待审核 /
  反馈说不清信号 / 画布只能拖不能提交）——**里面没有"没有准确率数字"这一项**。

**延后期间可以说 / 不能说（口径以 §17.4 为准）**

| ✅ 可以说（都是实测） | ❌ 不能说 |
|---|---|
| 事实层证据完整度 100%（133 / 74 / 459 / 1044 条事实全部可核验） | 「分析准确率 X%」（§13.1 明令） |
| 输出可复现：同进程 + **跨进程**逐字节一致 | 「我们比 ChatGPT 更准」 |
| 引擎里 0 处业务硬编码（62 个文件 0 命中，一次实跑见 `validation/acceptance_latest.md`） | 把自动划分说成"已验证的业务图谱" |
| 在 3 个未参与规则调试的真实第三方项目上跑通（约 2.4 万行） | 把自造样本上的指标当成绩报（§13.2） |
| 诚实退化率如实报（flat 域 / 待归类功能点 / `inferred-low` 占比） | 「覆盖清单命中 = 学生答对了」（§13.7） |

**重新启动的触发条件（写死，免得又变成"没人记得"）**

> 当**聚类 / 命名 / 词典这一层不再变动**（即"引擎冻结"）时，重新开启正式核对：
> 跑 §20.3 ⑤ 那四步，填满 184 行 → `graph_review_report.py` 退出码 0 → 出两个数字。
> **在那之前不要开填**，因为结果会作废。

**延后期间先做的一件小事：试点核对（本轮已备好）**

```bash
python scripts/export_domain_review_worksheet.py --pilot validation/python_dotenv
#   → validation/pilot_review_python_dotenv.md（6 行域 + 判断材料 + 引擎问题清单模板）
```

它**不是统计**（正式数字只认填满的 `business_graph_validation.md`），目的是产出三样
**不随 `source_hash` 失效**的东西：① 校准每行耗时（推算 184 行的真实工期）；
② 验证四个判定词在实际代码上好不好用（不好用就现在改口径）；
③ **引擎待改清单** —— 这份清单直接就是"完善系统功能"的输入项。

### 优先级 3 · 设计层（P1-09 / P1-10）—— 差异化最直观的交互 —— ✅ 已完成（Sprint 5）

- ~~设计画布（原生 drag + 手写 SVG，**不引第三方图库**）+ 模块卡片编辑器 + RubricEngine~~ ✅
  实现见 `frontend/src/components/StageDesign.vue` + `engine/design/`（7 个模块，见 §16.1）。
- RubricEngine 的硬规则**逐条落地、且逐条有断言**：
  - **算不出来的维度返回 `not_evaluated`，不许填 0** ✅（`score = null` + `reason`，
    且**不参与权重归一化**；A11 与 `test_design_rubric.py` 各有一条断言；
    页面上显示「本轮未评估」而不是 0 分，走查有断言）；
  - **唯一的例外写清楚了**：「异常与边界」维在「学生未填」时按 0 计并标注 `not_filled`
    （README §9.2 原话）——因为那是「还没有填」，不是「算不出来」；
  - 「未识别」与「未覆盖」严格区分 ✅（`matched` / `missing` / `unrecognized` 三分类，各一张清单，
    措辞是「未在设计中识别到」而不是「你漏了」）；
  - 第 6 维只衡量「理由可核查性」，不衡量「正确性」✅（只查四件事：引用的名字在不在图上 /
    有没有引用规则或状态 / `depends_on` 与画线是否自洽 / 字数是否在合理区间）；
  - 反馈必须是「信号码 → 中文模板」的纯函数映射 ✅（报告里 `issues` **恒等于**
    `feedback.render_issues(signals)`，测试逐维断言这条恒等式）。
- **比一档做得多的部分（也为它多付了代价）**：六维**全部**实现，凡是本轮算不出来的才显示未评估；
  另加了 `submission.py`（契约归一化；README §16.3 的文件清单里没有它，已在 §16.1 登记）。
- **如实说清没做的**：`reconstruct.py`（阶段六 重构挑战）没做；
  教师种子当时为空 → 依赖命中率 / 必备边界 / 禁止合并 / 可接受替代结构这几项
  **在当时的演示项目上是「本轮未评估」**（**优先级 3.5 一轮已给 `lab_safety_assistant` 补上，
  见下一节**）。

### 优先级 3.5 · 给设计层补教师种子 —— ✅ 已完成一轮（优先级 3.5 一轮，2026-09-24）

- **为什么**：Sprint 5 之后，六维里对外最有说服力的那几项（必备依赖命中率、必备边界命中率、
  可接受替代结构、禁止合并项）**全部依赖教师种子**。种子为空时它们诚实地显示「本轮未评估」，
  于是评委能看到的只有结构类信号（覆盖度 / 职责 / 层级 / 依赖结构 / 理由可核查性）。
- ~~**做什么**：按 `engine/lexicon/design_tasks.seed.json` 里已经写好的 schema，
  为 `lab_safety_assistant` 写一份**教师审核过的**任务：`must_have` + 两条必备依赖 +
  两个必备边界 + 一组可接受替代结构，并标 `review_status: "confirmed"`。~~ ✅
  **交付的是数据，引擎侧一行没改**：10 项必备能力（逐项在种子的 `_evidence` 里回指源码行号）+
  2 条必备依赖 + 2 个必备边界（`时间冲突` / `重复借用`）+ 2 条可接受替代结构 +
  1 条禁止合并项 + 1 个 `review_status: "confirmed"` 的任务，见 16.1 末。
- ~~**验收**：任务的 `must_have_source` 变成 `teacher_seed`、`needs_review = false`（页面上不再出现
  「待教师确认」徽章），且 `ALT_ACCEPTED` / `DEP_REQUIRED_MISSING` / `EDGE_REQUIRED_MISSING`
  这三个信号**能被真实触发**（不是只能靠测试注入种子来触发）。~~ ✅ **全部达成，且有机器化证据**：
  `scripts/test_design_seed.py`（**33/33**）**不注入任何东西**，直接读仓库里这份种子文件、
  在真实项目上跑两份真实提交 —— 合规设计不被误判（`ALT_ACCEPTED` 出现，两条 `*_REQUIRED_MISSING` 不出现），
  违规设计三条信号全部被抓住；`needs_review = false` 与徽章消失则由走查断言
  （「徽章 = 后端标注无需复核」）在**渲染层**确认。
- **纪律**：种子里的 `must_have` 必须**由人写**，不许让 LLM 生成后当成评分基准（§9.1 第 ③ 条）。
  → 本轮就是这么做的：AI 只把候选清单与**逐项源码证据**摆出来，十项能力、两条依赖、两个边界、
  两条替代结构与那条禁止合并项**由教师（用户）逐项确认后**才标 `confirmed`。
- **这一轮还顺手抓到并修了一个真问题**：禁止合并的反馈文案把种子里的内部 key（`mh_*`）
  直接印给学生（前端「禁止合并」列表用的就是同一个字段）。修法与复盘见 §19.2 ⑲。
- **仍未做的**：`python_dotenv` 没有种子；`lab_safety_assistant` 只有 1 条种子任务
  （想给学生多道任务就得在种子里写多条，见 16.2 新增行）。

### 优先级 4 · 补种子图谱与训练题遗留项 —— ✅ 已完成两轮（一轮 2026-09-24 / 二轮 2026-09-24）

- ~~为 `lab_safety_assistant` 落地 `business_graph.seed.json`（教师审核版，
  演示稳定性靠它，且 UI 要标来源徽章）~~ ✅ **优先级 4 二轮已完成**：
  `sample_projects/lab_safety_assistant/business_graph.seed.json`（5 条域目标 + 3 条二级目标，
  教师逐条确认）。实测效果：图谱 `status` 由 `needs_review` 变 **`mixed`**（前端「部分已审核」+
  节点「教师审核版」徽章）、`source_hash` **不变**、阶段一 `objective_missing` **4 → 0**、
  阶段二待确认卡片 **8 → 0**（全项目 25 → **17**）。见 §8.8 与 §16.1 末。
  **仍未做的**：`python_dotenv` 没有种子图谱；`does_not` / `inputs` / `outputs` 仍用自动结果。
- ~~训练题第 2 关「一道题只问一个模块」的限制~~ ✅ **优先级 4 一轮已修**（4 → 7 道）。
  ~~第 1/3/4 关各自只出一题~~ ✅ **优先级 4 二轮已修第 3/4 关**：
  第 3 关按 `flow_filter` 的唯一排序口径**逐条业务流程**出题（上限 4），
  第 4 关**逐条关键实现**出题（上限 3，干扰项逐题轮换）——
  实测 `lab_safety_assistant` **7 → 12 道**、`python_dotenv` **3 → 8 道**；
  `scripts/test_training_questions.py` 由 31 项扩到 **53/53**。
  **第 1 关经复核不需要改**（多选题型，一道题已覆盖全部业务模块），这条结论写在 §16.1 末。
- ~~设计模式检测器的启发式质量（若仍不做，就维持决策并写清楚）~~ ✅ **优先级 4 一轮做了复核并维持决策**：
  检测器质量没有提升，但发现决策**此前没有被真正执行**（模式名进了学生题干、还参与重要性打分），
  已修好 + 加了机器检查。证据与理由见 §19.2 第 ⑱ 条。
- **二轮顺带抓到的两个问题**（都不是计划内的，是"跑起来才发现"）：
  ① **跨进程不确定性**：同一个 `build_demo_snapshots.py` 连续两次跑出的学生快照 sha256 不同
  （`set` → 列表 → 拼进文本），直接违反 §七 第 7 条（同一份输入，字节级相同输出）；已修 + 加了
  `check_determinism.py --cross-process`（含负向对照），见 §19.2 ⑳；
  ② **旧管线冒烟会覆盖学生快照**，且写的版本与产物脚本不同；已写进 §17.2 与 §19.5 的顺序陷阱。

### 优先级 5 · 更后面的事

- 学习会话接口与 P1 存储层；第 7 步教师 Gold Graph 编辑器 + 审核固化；
- 重构挑战与能力报告；`vue-router` 深链；
- 更复杂的代码证据、运行验证、埋点、多语言。

### 一档 / 二档取舍（时间不够时）

| 档位 | 内容 | 能讲的故事 |
|---|---|---|
| **一档（最低可上台）** | 清障 + 图谱引擎（种子兜底）+ 图谱前端 + 阶段一 / 二 + 设计层「可计算维度」版 | 「我们从代码自动生成业务图谱，教师审核后用六维框架指导学生设计」（**阶段一 / 二已就位，设计层是缺口**） |
| **二档（完整闭环）** | 一档 + 重构挑战 + 教师工具 | 加上「重构挑战验证思维迁移」和「教师成为课程设计者」 |

**明确不许上台的半成品：** 六维里填假分的维度、自动生成图谱但未标注「待审核」、
反馈模板但说不清触发信号、画布只能拖不能提交。

---

## 附录 B · 早期一轮实测数据（事实层口径）

> **口径警告**：这一组数字来自**更早一轮的「事实表」实测**，
> 与第十七章的业务图谱验证**是两套不同的口径，不能混着报、不能相加**。
> 保留它是因为它是「事实错误率」这个指标目前唯一的实测来源。

**总体（3 个真实第三方项目）**

| 指标 | 数值 |
|---|---|
| 项目数 / 行数 / 文件数 | 3 个 / 22,900 行 / 67 文件 |
| 抽取事实总数 | 1,396 条（`verified` 1,355 / `inferred` 41） |
| 确定性占比 | **97.1%** |
| 分项目 | python-dotenv 1,112 行 8 文件 189 事实；flask 9,513 行 24 文件 488 事实；urllib3 12,275 行 35 文件 719 事实 |
| 类别分布 | 调用链 594 / 关键实现 255 / 状态变更 248 / 业务流程 191 / 模块结构 83 / 设计模式 25 |
| 错误类型（人工抽查 2 个项目，共 **6 处**） | 动态调用解析失败 3（50.0%）/ 模块边界误判 1（16.7%）/ 设计模式误报 1（16.7%）/ 算法类型推断错误 1（16.7%） |

来源文件：`validation/cross_project_report.md`、`validation/error_summary_for_submission.md`、
`validation/error_distribution.csv`、`validation/error_log.json`。

> ⚠️ **不要把这份数据和业务图谱的指标混着说**：
> 这里的 97.1% 是「事实抽取的确定性占比」，**不是准确率**；
> 「错误类型分布」只有 6 条人工抽查样本，**样本量太小，不能当比例结论用**。
>
> ⚠️ 早期的强化功能手册里有一张「错误类型分布示例表」（34 条 / 35% / 24% …），
> **那是示例数据，不是实测值**，已在删除旧文档时一并丢弃。

### BLPS-1.0（业务逻辑优先级）公式

**实现**：`engine/deep_analyzer/business_priority.py`；
导出：`scripts/export_business_priority.py`、`scripts/batch_priority_report.py`。

```text
加权 PageRank：跨模块边权重 × 1.2，阻尼系数 d = 0.85
  迭代到相邻两轮 L1 差 < 1e-9 或达到 100 轮 → 同一份代码得到同一排序

节点优先级：
  S_node = 100 × (0.35·C + 0.25·R + 0.20·M + 0.10·B + 0.10·E)
  C = 归一化 PageRank；R = 流程参与度；M = 状态写入；B = 跨模块；E = 证据完整度

流程优先级：
  S_flow = 100 × (0.45·I + 0.20·M_f + 0.15·V_f + 0.10·B_f + 0.10·E_f)

生命周期 / 样例数据流程降权：入口名或流程名命中
  initialize / bootstrap / seed / sample_data / setup → 乘以 q = 0.2

审核提示（只表示「应该先人工看」，不表示代码一定有错）：
  Risk_review = 100 × (0.65·1[M_f > 0 ∧ V_f = 0] + 0.35·(1 − E_f))
```

> BLPS 的定位是**教师推荐讲解顺序的参考信号**，
> **不是**「系统自动发现真实核心业务」——对外表述必须按这个口径说。

---
