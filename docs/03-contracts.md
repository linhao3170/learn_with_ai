# 统一数据契约（原 README 第十章 + 附录 A）

> 更新触发：**契约字段变更时**（加字段 / 改字段名 / 改可见性） | 上次更新：阶段 2 全面模块化一轮（2026-09-26）
> 来源：原 `README.md` 第十章与附录 A **整章搬移**；章节号不变（`§10.2` 业务图谱契约、`§10.5` 字段可见性矩阵、`附录 A` 字段速查）。
> **读它的时机**：改任何产物 / 接口字段之前必读。`§10.5` 的可见性矩阵是**学生视图的安全边界**（内部标记与答案不许进学生视图）。
> 产出方在 `docs/02-architecture.md`；消费方（接口 / 前端）在 `docs/04-api-and-frontend.md`。

---

## 十、统一数据契约

### 10.1 为什么必须统一

**曾有三套并存**的命名，前端无法确定契约：

| 来源 | 模块名字段 | 集合字段 | 「不负责」字段 |
|---|---|---|---|
| `engine/business_logic/models.py` | `name` | `modules` | `not_responsible` |
| 规格文档（旧 README3 §6.1） | `name_cn` | `module_cards` | `does_not` |
| 培养方案（旧 README4 §3.2） | 中文表头 | — | 「不负责什么」 |

**收敛决定（已实施）：以 `engine/business_logic/models.py` 为骨架，统一 `snake_case`。**

> **兼容策略**：`to_dict()` 输出**规范字段**（`name_cn` / `does_not` / `module_cards`，便于教师和前端理解）；
> Python 属性名保持 `name` / `not_responsible`（改动最小）。**在 `to_dict()` 里做一次映射，两全其美。**
> 同时 `contract_version`（当前 `"1.0"`）字段由前端启动时校验，不匹配就拒绝渲染并提示。

### 10.2 `business_graph.json`（规范性契约）

```json
{
  "contract_version": "1.0",
  "algorithm_version": "bg-1.0",
  "graph_id": "bg_lab_safety_001",
  "project_id": "lab_safety_assistant",
  "project_name": "实验室安全助手",
  "source_hash": "sha256:...",
  "level": "L2",
  "complexity": {"level": "L2", "raw": 27.4, "breakdown": {}, "algorithm_version": "complexity-1.0"},
  "domains": [
    {"domain_id": "d_lab_reservation", "name_cn": "实验室使用管理", "level": 1, "role": "core",
     "parent_id": null, "children": ["c_reservation_submit", "c_reservation_conflict"],
     "source": "teacher|auto", "confidence": "inferred",
     "evidence": [{"file": "sample_projects/lab_safety_assistant/reservation_manager.py",
                   "start_line": 1, "end_line": 6, "signal": "file_docstring_cn"}]}
  ],
  "module_cards": {
    "c_reservation_conflict": {
      "module_id": "c_reservation_conflict", "name_cn": "时间冲突检测", "level": 2,
      "parent_id": "d_lab_reservation", "entity": "reservation", "verb_class": "validate",
      "objective": "防止同一实验室同一时间被重复预约", "objective_confidence": "unconfirmed",
      "inputs": ["实验室编号", "开始时间", "结束时间"],
      "outputs": ["可预约", "冲突"],
      "business_rules": [
        {"fact_id": "f_0007", "text": "时间区间不能与已有预约重叠",
         "code": "if start < res_end and end > res_start",
         "file": "sample_projects/lab_safety_assistant/reservation_manager.py",
         "start_line": 122, "confidence": "verified"}
      ],
      "state_changes": [], "exceptions": [], "preconditions": [],
      "upstream_modules": ["c_reservation_submit"], "downstream_modules": ["c_reservation_approve"],
      "does_not": ["不负责审批结果判断", "不负责人数容量校验"],
      "does_not_confidence": "inferred",
      "members": [{"symbol": "_check_conflict", "role": "rule",
                   "file": "sample_projects/lab_safety_assistant/reservation_manager.py",
                   "start_line": 106, "end_line": 124}],
      "evidence": [{"file": "sample_projects/lab_safety_assistant/reservation_manager.py",
                    "start_line": 106, "end_line": 124}],
      "confidence": "inferred", "review_status": "needs_review", "source": "auto"
    }
  },
  "module_relations": [
    {"from": "c_reservation_submit", "to": "c_reservation_conflict", "type": "calls",
     "count": 1, "evidence": [{"file": "...", "start_line": 86, "end_line": 86}], "confidence": "verified"}
  ],
  "orchestrators": ["app"],
  "status": "draft|needs_review|approved|rejected"
}
```

> **契约要点**：`file` 一定是项目内相对路径（POSIX `/`）；`business_rules` 是**对象数组**
> （不是字符串数组），因为每条规则必须带 `fact_id` 和行号。

### 10.3 `teaching_plan.json`（学习路线，待实现）

```json
{"contract_version": "1.0", "plan_id": "tp_lab_001", "project_id": "lab_safety_assistant", "level": "L2",
 "stages": [
   {"stage": 1, "key": "overview", "name_cn": "项目认知",
    "objective": "能回答这个项目为什么需要这些模块",
    "task": {"type": "free_text", "prompt": "用自己的话说说这个项目为什么需要这四个业务模块",
             "scoring": "coverage_only", "coverage_source": ["d_lab_reservation.objective"]},
    "estimated_minutes": 10},
   {"stage": 2, "key": "module_card", "name_cn": "模块卡片学习",
    "items": ["c_reservation_conflict", "c_reservation_submit"],
    "questions": ["它要解决什么问题？", "它接收什么输入？", "它输出什么结果？",
                  "它改变了什么状态？", "它为什么不应该和其他模块合并？"],
    "scoring": "fact_coverage_only"},
   {"stage": 3, "key": "flow_sim", "name_cn": "业务流程推演", "scenario_ids": ["fs_normal", "fs_conflict"]},
   {"stage": 4, "key": "design_canvas", "name_cn": "模块设计", "task_id": "dt_device_loan_L2"},
   {"stage": 5, "key": "review", "name_cn": "评审与反馈"},
   {"stage": 6, "key": "reconstruct", "name_cn": "需求变化重构", "challenge_id": "rc_add_teacher_approval"}
 ],
 "total_estimated_minutes": 75}
```

> **阶段一 / 二都没有走这份 `teaching_plan.json`（据实说明）**：Sprint 3 的阶段一**直接从
> `business_graph` 派生页面内容**（域树 / 域目标 / 复杂度 / 置信度）；Sprint 4 的阶段二
> 把**题目文本与「问题 → 比对字段」映射外置到了 `engine/lexicon/stage_questions.json`**，
> 由 `GET /teaching/module-card/task` 下发给前端——前端不认识任何一个问题，
> 换问法不用改前端代码。
> 也就是说：**阶段二的"可配置"是用词典实现的，不是用这份 `teaching_plan.json`**。
> 代价是「一共几个阶段、按什么顺序」目前写在 `TrainingView.vue` 里。
> 等阶段三落地时再决定要不要抽出 `teaching_plan.json`——**在那之前不要假装它存在**。

### 10.4 `design_submission.json`

```json
{"contract_version": "1.0", "submission_id": "sub_001", "session_id": "sess_001",
 "task_id": "dt_device_loan_L2", "iteration": 2,
 "modules": [
   {"module_id": "m1", "name": "用户权限", "level": 1, "parent_id": null,
    "objective": "管理身份与权限", "inputs": ["用户凭证"], "outputs": ["允许/拒绝"],
    "does_not": "不负责设备状态", "business_rules": ["角色必须包含所需权限"],
    "state_changes": [], "exceptions": [], "depends_on": []}
 ],
 "relations": [{"from": "m3", "to": "m1", "type": "uses"}],
 "flow_designs": [], "design_rationale": "...", "saved_at": "2026-01-01T00:00:00Z"}
```

### 10.5 字段可见性矩阵（安全边界）

| 字段 | 学生视图 | 教师视图 | 说明 |
|---|---|---|---|
| `must_have` / `required_relations` / `forbidden_merges` | ❌ | ✅ | 完整 Gold Graph 只给教师 |
| `rubric_weights` 数值 | ❌ | ✅ | 学生只看到维度名与反馈 |
| `correct_answers` / `explanation` | ❌ **绝不下发** | ✅（`?mode=teacher`） | 判题必须走后端 |
| `confidence` | ✅ | ✅ | 学生必须知道哪些是推断 |
| `unconfirmed` 的模块名与 objective | ⚠️ 显示但标「待教师确认」 | ✅ | 可配置为隐藏 |
| 其他学生的提交 | ❌ | ✅ | |
| 内部异常堆栈 / `_inferred_` 等实现标记 | ❌ | ⚠️ 仅调试模式 | |

---

## 附录 A · 契约字段速查

| 契约 | 文件 / 产物 | 关键字段 |
|---|---|---|
| 业务图谱 | `business_graph` 字段 / `GET /api/projects/{id}/business-graph` | `contract_version` · `algorithm_version` · `source_hash` · `level` · `complexity` · `domains[]` · `module_cards{}` · `module_relations[]` · `orchestrators[]` · `status`（`needs_review` / **`mixed`**（有教师种子图谱时）/ `approved`）· `seed_report{seed_loaded,locked_fields,teacher_kept[],auto_kept[],unmatched_auto[]}`（有种子时） |
| 教师种子图谱 | `sample_projects/<project>/business_graph.seed.json`（**被分析项目目录内**，非 lexicon） | `domains[]`（`domain_id` `name_cn` `role` `locked[]`）· `module_cards{}`（`objective` + **`objective_confidence: "confirmed"`**（必须显式写，它不在 `LOCKABLE_FIELDS` 里）`review_status` `locked[]`）；合并后节点带 `source`（`teacher` / `auto`），域目标**只能填在 `module_cards[<domain_id>]`**（阶段一读的是卡片，见 §8.8） |
| 模块卡片 | `module_cards[module_id]` | `name_cn` · `objective`(+`_confidence`) · `inputs` · `outputs` · `business_rules[]`（对象数组，带 `fact_id` / `code` / `file` / `start_line`）· `state_changes` · `exceptions` · `preconditions` · `upstream_modules` · `downstream_modules` · `does_not` · `members[]` · `evidence[]` · `confidence` · `review_status` · `source` |
| 事实 | `business_rules` / `state_changes` / `exceptions` / `preconditions` / `guard` | `fact_id` · `kind` · `text` · `code` · `file` · `start_line` · `end_line` · `confidence` |
| 阶段一覆盖度报告 | `POST /api/projects/{id}/teaching/orientation/coverage` | `report_version` · `algorithm_version`（`orientation-coverage-1.0`）· `source_hash` · `stage` · `scoring`（恒为 `coverage_only`）· `has_score`（恒为 `false`）· `empty_input` · `input{chars,normalized_chars}` · `counts{core_domains,comparable_domains,covered,missed,not_comparable,supporting_domains,objective_missing}` · `covered[]` · `missed[]` · `not_comparable[]` · `supporting_domains[]` · `caveats[]` |
| 阶段一覆盖清单条目 | `covered[]` / `missed[]` | `domain_id` · `name_cn` · `role` · `confidence` · `name_status` · `matched_keys[]`（`key` / `origin` / `origin_confidence` / `detail`）· `keys_considered[]` · `capability_ids[]` |
| 阶段二任务包 | `GET /api/projects/{id}/teaching/module-card/task` | `task_version`（`1.0`）· `algorithm_version`（`card-coverage-1.0`）· `contract_version` · `project_id` · `project_name` · `source_hash` · `level` · `stage` · `stage_name_cn` · `scoring`（`fact_coverage_only`）· `has_score`（恒为 `false`）· `answer_prompt_cn` · `answer_max_chars` · `answer_total_max_chars` · `question_spec_source` · `questions[]`（`question_id` / `text_cn` / `placeholder_cn`，来自 `lexicon/stage_questions.json`）· `cards[]` · `counts` · `caveats[]`；**不下发任何比对键** |
| 阶段二事实覆盖报告 | `POST /api/projects/{id}/teaching/module-card/coverage` | 请求体 `{module_id, answers:{question_id: text}}`；响应 `report_version` · `algorithm_version` · `contract_version` · `project_id` · `source_hash` · `stage` · `stage_name_cn` · `scoring` · `has_score`（恒为 `false`）· `module` · `card_needs_review` · `unconfirmed_fields[]` · `empty_input` · `unknown_question_ids[]` · `counts{questions,comparable_questions,questions_with_hits,not_comparable_questions,matched_keys,unmatched_keys,unconfirmed_fields,empty_answers}` · `questions[]`（`question_id` · `text_cn` · `answer_chars` · `empty_answer` · `comparable` · `not_comparable_reason` · `matched_keys[]` · `missed_keys[]` · `keys_considered[]` · `field_results[]`）· `caveats[]`（含"提到 ≠ 理解""规则条件类键未命中不构成答错证据"） |
| 学习路线（待实现） | `teaching_plan.json` | `stages[]`（`stage` `key` `name_cn` `objective` `task` `items` `questions` `scoring`）· `total_estimated_minutes` |
| 设计任务（**Sprint 5 已实现**） | `GET /api/projects/{id}/teaching/design/task`（完整版见 `engine/design/task_builder.py`；种子文件 `engine/lexicon/design_tasks.seed.json`） | `task_version`（`1.0`）· `algorithm_version`（`design-task-1.0`）· `contract_version` · `task_id` · `project_id` · `source_hash` · `level`(+`level_label`/`level_desc`) · `type` · `type_name_cn` · `goal_cn` · `prompt_cn` · `scenario_cn` · `brief{mode,text_cn,items[],flow_names[],capability_names[],counts}` · `brief_includes` · `must_have[]`（`key` `name_cn` `aliases[]` `cluster` `verb_class` `entity` `related_flow` `source`）· `must_have_source`（`teacher_seed` / `auto_from_project`）· `must_have_confirmed` · `needs_review` · `required_relations[]`（`from_key` `to_key` `reason_cn`）· `required_edge_cases[]` · `forbidden_merges[]`（`a` `b` `reason_cn`）· `acceptable_alternatives[]`（`alternative_id` `name_cn` `merge_keys[]` / `separate_keys[]`）· `rubric_weights{}` · `order`；**学生视图只留题干 / 简报 / `must_have_count` / `dimension_names` / `caveats`，其余一律不下发** |
| 设计提交 | `design_submission.json`（§10.4） | `submission_id` · `task_id` · `iteration` · `modules[]`（`module_id` `name` `level` `parent_id` `objective` `inputs[]` `outputs[]` `does_not[]` `business_rules[]` `state_changes[]` `exceptions[]` `depends_on[]`）· `relations[]`（`from` `to` `type`）· `flow_designs[]` · `design_rationale`；兼容 `name_cn` 与字符串型 `does_not`（归一化后只留一种写法） |
| 六维评估结果（**Sprint 5 已实现**） | `POST /api/projects/{id}/teaching/design/evaluate`（`engine/design/rubric.py`） | `report_version` · `algorithm_version`（`rubric-1.0`）· `contract_version` · `project_id` · `source_hash` · `task_id` · `task_type` · `level` · `submission_id` · `iteration` · `scoring`（`rubric_six_dimensions`）· `has_score`（`true`）· `evaluated_dimensions` · `total_dimensions` · `weights_renormalized` · `overall_score`（**可算维度为 0 时是 `null`**）· `overall_note` · `weights[]`（`key` `weight` `normalized_weight` `score`）· `dimensions[]`（`key` `name` `weight` `status` `score`（未评估为 `null`）`definition_cn` `findings[]` `issues[]` `signals[]` `reason` `not_filled` `counts` `deduction`）· `signals[]`（`code` `dimension` `params` `penalty`）· `matching{counts,matched[],missing[],unrecognized_modules[]}` · `graph_checks{counts,cycles[],orphans[],dangling_edges[],declared_vs_drawn[],max_depth,children[]}` · `alternatives{available,reason_cn,accepted,accepted_alternative,accepted_alternative_ids[],violations[]}`（`violations[]` 每条是 `a` `b`（**中文显示名，直接进学生界面**）`a_key` `b_key`（种子里的原始 key，供教师排查）`reason_cn` `code`） · `submission_issues[]` · `alternatives_issues[]` · `submission_warnings{unknown_fields[],truncated}` · `caveats[]` |
| 证据 | 全链路 | `fact_id` · `file`（项目内相对路径）· `start_line` · `end_line` · `symbol` · `confidence` · `reason` |
| 模型层 | `engine/business_logic/models.py` | 12 个 dataclass：`BusinessModule` · `BusinessGraph` · `BusinessFlowStep` · `BusinessFlow` · `GoldGraph` · `StudentModule` · `DesignSubmission` · `DimensionScore` · `EvaluationResult` · `TrainingStage` · `TrainingPlan` · `FlowScenario`（`CONTRACT_VERSION = "1.0"`，实测 `@dataclass` 12 个） |

**字段命名纪律**：Python 属性名用 `name` / `not_responsible`，`to_dict()` 输出规范字段
`name_cn` / `does_not` / `module_cards`。**前端只认规范字段。**

---
