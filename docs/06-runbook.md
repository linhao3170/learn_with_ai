# 运行、验收与排障手册（原 README 第二十章 + §19.5）

> 更新触发：**新增脚本或环境结论变了** | 上次更新：部署说明一轮（2026-09-26：头部加部署文档入口）
> 来源：原 `README.md` 第二十章（工具与命令手册）+ 从技术债文档搬来的 `§19.5`（沙箱与环境约束 —— 它是手册内容，不是债）。
> **读它的时机**：第一次跑起来 / 要跑验收 / 环境报错时。
> ⚠️ **"怎么把项目装到另一台机器上"不在这里** —— 见 `docs/11-deployment.md`（第二十五章：部署形态 / 端口 / 构建产物 / 安全边界）；
> 本文负责命令全表与排障（尤其 `§19.5`）。
> ⚠️ 这里只放"怎么跑、跑出什么、为什么跑不起来"；**实跑数字不在这里手抄** ——
> 见 `validation/acceptance_latest.md`（由 `python scripts/build_acceptance_report.py` 生成），`python scripts/verify_docs.py` 会核对。

---

## 二十、工具与命令手册

### 20.1 验收 / 自检脚本

| 脚本 | 作用 |
|---|---|
| `scripts/bootstrap.ps1` | **一键环境引导（克隆完整性一轮新增）—— 克隆之后的第一步**：前置检查 python / node / npm → 建 `.venv` → 装 `requirements.txt` 与 `backend/requirements.txt` → 前端 npm ci → 跑 `scripts/build_demo_snapshots.py`。幂等、可重复跑、**不硬编码本机路径**（路径从脚本自身位置推）。开关：`-Build` 顺带构建 `frontend/dist` 与走查 bundle、`-Verify` 顺带跑三道门禁、`-SkipFrontend` 只装 Python 侧。**依赖装进 `.venv` 而不是系统 python** —— 作者机器上两者恰好都装齐了，别人机器上不一定（理由与实测见 §19.5） |
| `scripts/verify_sprint0.py` | **总验收**：一进程内跑完 A1–A11（契约 / 确定性 / 硬编码 / 契约层 / AST 缓存 / 产物 / 答案可见性 / 判题 / 阶段一覆盖度报告 / 阶段二事实覆盖报告 / **阶段四设计层六维评审**） |
| `scripts/test_business_graph.py` | 图谱引擎测试：结构不变量 / 确定性 / 质量下限 / 教学正确性（编排类不当核心域、dunder 不成功能点、生命周期排最后）/ 教师种子合并 |
| `scripts/test_teaching_coverage.py` | 阶段一覆盖度比对器测试：不打分（逐键扫描分数字段）/ 不丢域 / unconfirmed 不参与比对 / 英文整词匹配 / 确定性 / 无网络导入 |
| `scripts/test_teaching_card_coverage.py` | 阶段二事实覆盖比对器测试：合成用例 + 两个真实项目；题目来自词典配置 / 卡片不丢 / 不打分 / 待确认字段不比对 / 复用同一份命中判定 |
| `scripts/test_design_rubric.py` | **设计层六维评审测试**：三分类匹配（含「形近名字不叠加」）/ 命中方式 / not_evaluated 且不许填 0 / **空提交不给总分** / 环与悬空边 / 声明与画线只在两边都非空时报 / `issues == render_issues(signals)` 恒等式 / 可见性矩阵 / 教师种子注入（含禁止合并与可接受替代结构）/ 确定性 / 归一化幂等 / 复用 `audit_hardcoding.py` 做业务词审计 |
| `scripts/test_training_questions.py` | **第 2/3/4 关「一关多题」出题覆盖测试**（优先级 4 一轮新增第 2 关、二轮扩到第 3/4 关）：够格对象各一道 / 选项全部来自真实数据（第 2 关=模块文本、第 3 关=流程步骤标签）/ 第 3 关有业务流时绝不问生命周期流程 / 第 4 关按重要度取前 N 且干扰项逐题轮换 / 4 选 1 且与答案表逐题一致 / 标题可区分 / 关卡顺序 / 确定性 / 上限 / CRUD 标签不当职责 |
| `scripts/test_design_seed.py` | **教师种子验收测试**（优先级 3.5 一轮新增）：**不注入任何种子**，直接读仓库里的 `design_tasks.seed.json` —— 种子被读到（`teacher_seed` / `needs_review = false`）/ `(verb_class, entity)` 不重复 / 三份清单齐全且引用的 key 都存在 / 依赖与替代结构不互相打架 / 学生视图不泄漏（含简报里不列必备能力）/ **合规设计不被误判、违规设计三条信号全部被抓住** / 文案里没有残留占位符与 `mh_*` 内部 key / 只影响有种子那个项目 / 确定性 |
| `scripts/validate_business_graph.py` | 多项目验证 + 生成人工核对模板（**脚本不填判定列**），`--emit-review` |
| `scripts/graph_review_report.py` | **人工核对结果统计器**（优先级 2 备料一轮新增）：读回第 6 节「人工判定」列 → 划分错误率 / 命名不当率（域与功能点分开报）/ 漏填清单 / 非法取值 / 表格结构检查。**退出码 0 = 判定列填满且取值合法**（它的 1 是"还没人填"，不是"跑挂了"） |
| `scripts/validate_contract.py` | 契约校验：绝对路径 / 答案泄漏 / 内部标记 / 相对路径 / `source` 字段 / **学生可见文本里不得出现设计模式检测器的结论**（第 9 项，优先级 4 一轮新增） |
| `scripts/check_determinism.py` | 同进程双跑逐字段比对，输出第一处差异路径；**`--cross-process`**（优先级 4 二轮新增）用不同 `PYTHONHASHSEED` 各起一个子进程**逐字节**比对 —— 同进程双跑查不出「`set` 迭代顺序」那一类问题（见 §19.2 ⑳） |
| `scripts/build_demo_snapshots.py` | 一键生成「学生快照 + 后端答案表 + 证据源码副本」，支持多项目。⚠️ **改了题目必须重跑它**（答案表与题目按下标对应）；⚠️ **旧管线冒烟会覆盖它写的学生快照**，见 §17.2 的顺序陷阱 |
| `scripts/audit_hardcoding.py` | 业务词审计：引擎侧失败、前端侧提示；`--include-frontend` 连前端一起判失败 |
| `scripts/build_acceptance_report.py` | **验收报告生成器（阶段 0 新增）**：**默认组**的 13 个只读验收脚本在**一个进程内**跑（不启子进程、不用管道）；`--with-node` 那一组的 4 条走查会起 **node 子进程，但输出走临时文件、不走管道**（同一条沙箱纪律，见 §19.5）。它把每个脚本的「通过/总数」解析成 `validation/acceptance_latest.json` / `.md` —— **文档引用数字的唯一来源**。默认不跑需要后端 / node / 走查 bundle 的条目，也**不跑会覆盖产物或人工判定模板的脚本**（`--with-backend` / `--with-node` / `--with-manual` / `--with-order-trap` 显式开启，原因逐条打印） |
| `scripts/verify_docs.py` | **文档门禁（阶段 0 新增，阶段 2 扩到 7 项）**：D1 反引号路径必须真实存在（当行写「待建 / 已删除 / 还没做」的除外）；D2 `§X.Y` 与「第 N 章」必须在**整个文档集**上解析得到标题（并报告跨文件引用规模）；D3 文档里的应用版本号必须等于 `backend/app/main.py`；D4 文档里的验收数字必须与验收报告一致、已淘汰的旧总数不许裸写；D5 每篇 `docs/*.md` 要有「更新触发」行；D6 `文件:行号` 必须指得到东西（行号不越界，且同一行的路径 / 标识符要出现在被引行号附近）；D7 **文档清单完整性**（`docs/` 下每份文档都要被 `docs/00-index.md` 与 `README.md` 提到，清单里写的路径必须真实存在）。**退出码 1 = 有 ERROR** |
| `scripts/pack_docs.py` | **文档打包器（阶段 2 新增）**：按 `docs/00-index.md` 的清单顺序把模块化文档拼成**单文件** `docs/_bundle.md`，用于"一次性交给 AI 助手做全面升级"的场景；同时核对"清单 ↔ 磁盘"是否一致（索引里列了却没有 / 磁盘上有却没进清单都会报出来）。`--list` 只看顺序不写文件。**产物不要手改**（`verify_docs.py` 按 `_` 前缀跳过它） |
| `scripts/browser_clickthrough.mjs` | jsdom 真实 DOM 点击走查（真实组件 + 真实 HTTP），`--offline` 验证离线降级；断言覆盖**系统主页面**（两大核心功能入口 / 未开始阶段不给入口 / 来源依据默认收起且能展开收起）、训练判分与离线降级、业务图谱、阶段一 / 二、**阶段四的 28 条断言**（加节点 / 改名 / 拖拽连线 / 填卡 / 提交 / 六维渲染 / 未评估不显示 0 / 必备能力不下发 / iteration 递增）。**项数口径**：UI 重设计一轮起是「在线 109 条 / 离线 55 条」（旧值 99 / 45 是 Sprint 5 口径），实跑记录见 `docs/07` §17.2 |
| `scripts/browser_walkthrough.ps1` | 旧的无头 Chrome 走查方案（已被 `.mjs` 取代） |
| `scripts/check_evidence_fold.mjs` | **证据折叠自查**（证据折叠一轮新增）：用**后端真实讲稿载荷**在 jsdom 里单独挂载 `ImmersiveLesson` / `VerificationPanel`，断言「摘要常驻 + 详述收起但内容仍在 DOM 里 / 逐条证据与教师标注收起但一条不少 / 被拦截的断言与有失败的明细**默认展开** / 计数徽章与发布闸门常驻 / 翻开后证据仍能跳源码、教师确认仍生效」。**自带负向对照**（一个用 `v-if` 收起的对照组件，同一条断言必须 FAIL）。前置：后端在跑 + 走查 bundle 已构建（`frontend/vite.smoke.config.js`）；**不在** `build_acceptance_report.py` 的 13 个脚本里（与走查同属"显式开启"那一类），实跑口径见 `docs/07` §17.2 与 `docs/features/evidence-fold.md` |

### 20.2 产物生成脚本

| 脚本 | 作用 |
|---|---|
| `scripts/build_demo_snapshots.py` | 一键生成「学生快照 + 后端答案表 + 证据源码副本」，支持多项目 |
| `scripts/export_domain_review_worksheet.py` | **域核对工作纸**（优先级 2 备料一轮新增）→ `validation/graph_review_worksheet.md`：每个域摊开成一张卡片（能力点 / 成员函数 `文件:行` / 聚类依据 / 涉及文件），供人工判定时对照。**只对真实第三方项目**，自造样本自动跳过；`--pilot <project>` 产出只含一级域的试点纸 `validation/pilot_review_<project>.md`（+ 引擎问题清单模板）。输出逐字节可复现 |
| `scripts/generate_deep_data.py` | 产出 `validation/results/deep_analysis.json` |
| `scripts/test_deep_analyzer.py` | 深分析冒烟，产出 `deep_analysis_test.json`（**与上者不共用路径**，避免互相覆盖） |
| `scripts/generate_web_data.py` | 生成旧函数级 demo 数据 `frontend/public/demo/analysis_output.json` |

### 20.3 材料与报告工具

**① 事实表导出器**（`scripts/export_fact_table.py`）

```bash
python scripts/export_fact_table.py                                   # 默认读 frontend/public/demo/deep_analysis.json
python scripts/export_fact_table.py path/to/analysis.json output_name
```

- 输出 `fact_table.csv` / `fact_table.xlsx`（`.xlsx` 需要 `pip install openpyxl`）；
- 表头：`事实ID | 类型 | 描述 | 文件位置 | 可信度 | 证据来源`；
- 来源：`call_graph.edges`（跨模块调用）/ `state_analysis.classes`（状态变更）/
  `business_flows`（流程步骤）/ `key_implementations`（设计特征）；
- **硬规则：只导出 `verified` 级别的事实，`inferred` 的不进表。**

**② 错误类型归类器**（`scripts/error_classifier.py`）

```bash
python scripts/error_classifier.py types
python scripts/error_classifier.py add <项目名> <事实编号> <错误类型> <原因>
python scripts/error_classifier.py report
```

八类错误代码：`dynamic_call` / `module_boundary` / `pattern_false_positive` /
`state_tracking_miss` / `semantic_inference` / `algorithm_inference` / `cross_file_call` / `other`。
输出 `validation/error_log.json`、`validation/error_distribution.csv`、
`validation/error_summary_for_submission.md`。

**③ 业务优先级报告**（BLPS-1.0）

```bash
python scripts/export_business_priority.py --input <json> --output validation/business_priority_report.md
python scripts/batch_priority_report.py <p1> <p2> --output validation/batch_priority_review.md
```

两个脚本都**只导出、不重算分数，也不编造准确率**。

**④ 教师审核界面（现有实现的操作路径）**

```text
1. 启动前端 → 2. 打开分析页面 → 3. 切到关键实现标签页 → 4. 打开顶部「教师审核模式」开关
→ 5. 展开任意一个关键实现 → 6. 底部出现审核区：✓ 确认准确 / ✗ 标记错误 / 撤销
```

- **只对 `inferred` 级别的结论审核**（`verified` 无需审核）；
- 状态存在 `localStorage['teacher_review_status']`，key 是 `impl.node_id`；
- 清浏览器缓存会丢（这是 P0 阶段已知限制）。

**⑤ 业务图谱划分的人工核对（优先级 2，产出「准确率」的唯一途径）**

```bash
# 1) 生成/刷新核对模板（⚠️ 覆盖写：要重跑就先跑，再填）
python scripts/validate_business_graph.py \
  --output validation/business_graph_validation.md \
  --json-output validation/business_graph_metrics.json --emit-review

# 2) 生成判断材料（每个域摊开：能力点 / 成员函数 文件:行 / 聚类依据 / 涉及文件）
python scripts/export_domain_review_worksheet.py     # → validation/graph_review_worksheet.md

# 3) 人填 validation/business_graph_validation.md 第 6 节的「人工判定」列
#    四个词：正确 / 命名不当 / 划分错误 / 无法判定

# 4) 读回统计（退出码 0 = 判定列填满且取值合法）
python scripts/graph_review_report.py --verbose \
  --output validation/business_graph_review_summary.md \
  --json-output validation/business_graph_review.json
```

- **待判定规模**：3 个真实第三方项目 = **37 行域 + 147 行功能点 = 184 行**；
  建议**先填 37 行域**（统计口径的分母是总域数，填完就能产出两个可对外报的数字）；
- **两个比率分开报**：业务图谱划分错误率（`划分错误 / 总域数`）、
  模块命名不当率（`命名不当 / 总域数`）——**不与「事实错误率」混报、域与功能点不相加**；
- **自造样本不参与**：`sample_projects/lab_safety_assistant` 的核对模板是脚本刻意不生成的。

**⑥ 事实层的人工核对（附录 B 的「事实错误率」，与 ⑤ 是两回事）**

```bash
# 1) 生成核对模板（在事实表基础上加 is_error / error_type / notes 三列）
python scripts/validation_report.py --template \
  --source validation/results/python_dotenv_facts.csv \
  --output validation/results/python_dotenv_facts_check.csv

# 2) 浏览器直接打开工作台（file:// 即可，不需要服务器）
#    validation/reviewer/index.html → 导入上面的 CSV → 逐条确认/标记错误 → 导出 *_checked.csv

# 3) 生成报告（错误率 + 错误类型分布）
python scripts/validation_report.py --input validation/results/python_dotenv_checked.csv --project python_dotenv
```

三个项目的事实表 CSV 都在 `validation/results/`（`python_dotenv` / `flask` / `urllib3`）。

---

### 19.5 沙箱 / 环境约束（写给后来的人）

- **禁止通过管道捕获原生程序输出**：`python xxx | Select-Object` 会让 `python.exe` 报
  `Access is denied`。所以 `scripts/verify_sprint0.py` 用**进程内调用**而不是逐个跑子脚本。
  （优先级 3.5 一轮复现了一次：同一条带管道的命令在 `workspace-write` 下被拒，同一会话放开权限后原样执行成功 ——
  也就是说**这条限制来自沙箱模式，不是命令本身写错了**。诊断口径：报错信息后面会跟
  `[sandbox: file access denied under <mode> mode]`。）
- **无头浏览器渲染不出来**：Chromium 的多进程 IPC 需要命名管道，被沙箱挡住。
  所以浏览器走查改用 **jsdom + 真实浏览器版 bundle + 真实 HTTP**（`scripts/browser_clickthrough.mjs`）。
- `npm run build` / `npm run dev` 需要 esbuild `spawn` 子进程 → 受限模式下报 `spawn EPERM`；
  跑构建需要在放开进程权限的终端里执行。
- **`npm` 这个命令本身可能先死在执行策略上**（优先级 3.5 一轮实测）：PowerShell 报
  `npm.ps1 cannot be loaded because running scripts is disabled on this system`，
  与 esbuild / 沙箱都无关。绕法：用 `npm.cmd`，或**直接调 node 入口**
  （`node node_modules/vite/bin/vite.js`），README 里的 `vite build` 等价命令就是这么来的。
- **改了 `engine/lexicon/*.json`（含教师种子）也必须重启 uvicorn**（优先级 3.5 一轮实测踩到）：
  `load_lexicon()` 是**进程内缓存**（`engine/lexicon/__init__.py` 的模块级 `_cache`，首次加载后不再读盘），
  加上启动命令没有 `--reload`，于是一个**先于改动启动**的后端会同时持有
  ① 旧的引擎代码 ② 空的种子缓存 —— 表现是「种子写好了却不生效」，
  而 `python scripts/test_design_seed.py` 在同一台机器上却全绿（它每次都是新进程）。
  **判定方法：`GET /api/projects/{id}/teaching/design/tasks` 看 `needs_review` 与任务数**，
  对不上就先重启后端再怀疑代码。
  （对比：**教师种子图谱** `business_graph.seed.json` **不需要重启** —— 它由
  `build_demo_snapshots.py` 烘进学生快照，而 `project_store.load_snapshot()` 每次请求都读磁盘。）
- ⚠️ **旧管线冒烟脚本会覆盖学生快照**（优先级 4 二轮实测踩到，属顺序陷阱不是环境限制）：
  `python scripts/test_project_analyzer.py` 会把 `frontend/public/demo/project_analysis.json`
  重写一遍，而它写出的内容与 `scripts/build_demo_snapshots.py` **不完全相同**
  （同一轮实测两者 sha256 不同，差异在 `deep_analysis` 的若干文本字段上）。
  后果：**跑完冒烟之后，离线快照就不再是 A6/A7 验过的那一份**。
  正确顺序是：产物脚本 → 三项验收 → 旧管线冒烟 → **再跑一次产物脚本**（或把冒烟放在最前）。
  根治办法（改脚本让两者写不同路径）这一轮没做：改动面比收益大，先如实记录。
- `.ps1` 文件**必须带 UTF-8 BOM**：Windows PowerShell 5.1 会把无 BOM 的 UTF-8 按 ANSI 解码，
  中文被误解后可能变成引号 / 花括号，导致「Missing closing '}'」这类假语法错误。
- 本仓库的 git 可能报 `dubious ownership` 并拒绝一切命令（仓库属主是 `BUILTIN\Administrators`、
  而当前用户不匹配时就会这样，连 `git status` 都不给跑）：
  绕法是每条命令都带 `-c safe.directory=<仓库绝对路径>`，或一次性执行
  `git config --global --add safe.directory <仓库绝对路径>`。
- **克隆完整性一轮已解除「`git status` 必须加 `--ignore-submodules=all`」这条**（原记录在此处，现更新为历史）：
  当时 `validation/flask` 是一个**嵌套真实 `.git` 的 gitlink**（索引里 mode `160000`、仓库里没有 `.gitmodules`），
  于是 `git status` 会去子模块里跑 `status --porcelain=2`，在受限沙箱下报
  `error: cannot create standard output pipe for status: Permission denied`；
  同时**克隆下来的 `validation/flask` 是一个空目录** —— 三个真实第三方验证项目缺一个，
  手册里那几条依赖它的命令在别人的机器上跑不通。
  这一轮把 `validation/flask/.git` 改名为 `validation/flask/.git.bak`（**与 `validation/urllib3` 同一惯例**，
  且 `.git.bak` 命中根 `.gitignore` 的 `*.bak` 规则），并把 236 个源码文件纳入跟踪。
  实测结果：`git status` 不再需要 `--ignore-submodules=all`，`git ls-files -s` 里**不再有任何 gitlink**。
  ⚠️ 这条改动的**代价**要写清：`validation/flask` 从此是"仓库里的一份源码快照"，
  不再跟随上游 `pallets/flask` 更新（快照点：`d73fa1c`，与 `validation/urllib3` 的处置一致）。
- **`node.exe` 能不能跑，取决于沙箱当时的模式；但 `esbuild` 一定跑不了**（Sprint 3 / Sprint 4 两次实测）：
  - Sprint 4 的 `workspace-write` 会话里 **`node` 本身可以跑**：`node -e`、
    `node scripts/browser_clickthrough.mjs`（jsdom 走查）都正常完成，**不需要放开权限**；
  - 但 `vite build` / `vite dev`（含 `npm run dev`）会 `spawn` 子进程并走管道 stdio，
    在同一个模式下**必然**报 `Error: spawn EPERM`（`esbuild/lib/main.js` 的 `ensureServiceIsRunning`）。
    构建走查 bundle 需要**一次性放开进程权限**（Sprint 3 时连 `node.exe` 都被拒，更严）。
  - 结论：**先直接跑走查，不要因为"vite 起不来"就以为整条前端验收都跑不了**。
- **改了后端路由之后，必须重启 8000 上的 uvicorn**（Sprint 4 实测踩到）：
  文档里的启动命令**没有 `--reload`**，旧进程会一直按老代码应答，
  表现为"新接口 404、`/api/health` 还是旧版本号"，很容易误判成代码没生效（或前端写错路径）。
- **Sprint 5 实测补充（同一类坑，但这次更容易骗过自己）**：
  - esbuild 的 `spawn EPERM` 结论**复现了**：`node node_modules/vite/bin/vite.js build --config vite.smoke.config.js`
    在 `workspace-write` 下必然失败，需要一次性放开进程权限；**而 `node scripts/browser_clickthrough.mjs`
    本身不需要放开权限**（它只跑 jsdom，不 spawn）。
  - 走查加载的是 **`.smoke-dist` 构建产物**，不是 dev server 的源码：
    **改了 `.vue` 却不重建 bundle，走查会拿着旧代码给你"通过"或"失败"**
    （Sprint 5 真的踩了一次：修完 iteration 后不重建就重跑，看到的仍是旧行为）。
  - 8000 上可能已经有人占着**旧版本**的后端：新代码起在 8001、dev server 的 `/api` 代理却仍指向 8000
    （`vite.config.js` 的 `VITE_API_TARGET`，默认 `http://127.0.0.1:8000`），
    表现是"组件自己的请求成功、走查脚本直接发的请求 404"。
    正确做法：给 dev server 显式指定 `VITE_API_TARGET=http://127.0.0.1:8001`，别去杀别人的进程。
  重启前先确认那个进程确实是本项目的后端（并发工作线场景下别误杀别人的服务）。
- **用 PowerShell 的 `Invoke-RestMethod` 发中文 JSON 会乱码**：Sprint 3 测新接口时，
  请求体里的中文被按非 UTF-8 编码送出，服务端收到的文本对不上任何比对键，
  于是**覆盖清单"看起来"是 0 命中**——差点当成判定器的 bug。
  测中文接口请用 UTF-8 明确的客户端（`python -c` + `urllib` 已验证可复现）。
  另外 `Invoke-RestMethod` 读中文响应也可能显示成乱码（显示问题，不是数据问题）。
- **`python ... > log 2>&1` 有时会生成空日志且不返回退出码**：Sprint 3 遇到过一次，
  直接不带重定向跑同一条命令就正常。判断验收结果时**以屏幕输出为准**。
- **优先级 4 一轮又踩到两个同类坑**：
  - PowerShell 里 `python scripts\xxx.py > $null` 会**静默不执行**（`$LASTEXITCODE` 为空、
    产物 mtime 不变）——"看起来跑过了"其实一次都没跑。要么不加重定向（以屏幕输出为准），
    要么在 **python 进程内**重定向 stdout（`contextlib.redirect_stdout`）并把结尾几行打印出来；
    注意有些脚本会直接调 `sys.stdout.reconfigure(...)`，用 `StringIO` 接会 `AttributeError`，
    得套一个带空 `reconfigure()` 的子类。
  - `npm run build` 在本机被 **PowerShell 执行策略**挡住（`npm.ps1 cannot be loaded because
    running scripts is disabled`）—— 这跟沙箱无关，用 README 里那条等价命令即可：
    `node node_modules/vite/bin/vite.js build`。
- **本项目可能有多条工作线在同一个工作区并发开发**（Sprint 3 / Sprint 4 实测如此）：
  整理文档时会遇到"上一秒读到的状态、下一秒就变了"，甚至后台服务被新版进程顶掉
  （表现为自己的 uvicorn 退出码 1，**不是崩溃**——日志里先有一串正常 200，然后进程消失）。
  所以：**引用行号与数字前先重新 grep / 重跑**；改动共享文件（`README.md`、`main.py`）前
  先看 mtime；不要把"并发对方写到一半的状态"当成缺陷去"修"。
- **UI 重设计一轮复现与新增的两条环境结论**：
  - 「esbuild 必 EPERM」**第三次复现**：`node node_modules/vite/bin/vite.js build --config vite.smoke.config.js`
    在 `workspace-write` 下 `Error: spawn EPERM`（`esbuild` 的 `ensureServiceIsRunning`），
    一次性放开进程权限后**同一条命令**成功（2148 modules transformed，10.31s）；
    而**走查脚本本身在 `workspace-write` 下跑得好好的** —— 结论没变：先跑走查，别因为 `vite build` 失败就以为前端验收跑不了。
  - **新坑：不要把原生程序的输出接进 PowerShell 管道**。`node xxx.js 2>&1 | Select-Object -Last 25`
    会直接失败，报 `Program 'node.exe' failed to run: Access is denied`（同一条命令不带管道就正常跑完）。
    同一个会话里 `node --version` 也是好的 —— 所以它**不是**"node 被禁"，而是管道那一层。
    要留档就把输出交给 `job_output`（后台任务）或写成文件，不要用 `|` 兜。
