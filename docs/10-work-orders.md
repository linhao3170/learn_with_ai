# 并行工单与执行编排（多任务同时开工时的唯一发单口径）

> 更新触发：**工单增删 / 波次调整 / 文件归属变化 / 有工单做完时** | 上次更新：工单编排一轮（2026-09-26）
> 来源：`docs/07-status-and-acceptance.md` 的 `§16.2` / `§16.3` / `§18`（未做项与优先级）+ `docs/08-tech-debt.md` 的 `§19.1` / `§19.6`（技术债与交接事实）。
> **读它的时机**：要把"剩下没做的活"拆给一个或多个人 / AI 助手**同时开工**时。
> ⚠️ **它不是第二份「下一步」**：优先级与取舍的唯一权威仍是 `§18`（`docs/00-index.md` §3.2 第 6 条）。
> 本文件只做三件事：把 `§16.2` / `§16.3` / `§19.1` 里"还没做"的条目**拆成可独立执行的工单**、
> 写明**每单独占哪些文件**、排出**哪些能同时开、哪些必须等**。

---

## 二十二、总则：怎么用这份文档

### 22.1 它是什么 / 不是什么

| | 内容 |
|---|---|
| **是** | 工单表（`WO-01` ~ `WO-15` + 集成轮 `WO-90`）、每单的独占文件与验收命令、波次与依赖、发单模板、交付验收办法 |
| **不是** | 不是新优先级（`§18` 为准）；不是排期承诺；不是"这些事一定做得到"的保证 —— 做不到的逐条写在 `§24.2` 与每单的「诚实边界」 |
| **一句话口径** | 本文里写「待建 / 未开始 / 还没做」的东西，执行时**不许**被改口成"已做"（`docs/00-index.md` §3.2 第 7 条） |

### 22.2 每个执行者开工前必须读的东西

1. `docs/00-index.md` —— 交接协议、**硬约束 7 条**、**完成定义 7 项**、**禁止事项 8 条**、代码地图、按任务选读表；
2. 本文 `§22.3` ~ `§22.5`（完成定义、环境纪律、文件独占协议）；
3. 自己那一单的 `§23.x`，以及该单「必读」一栏列出的章节；
4. 要动的那个模块对应的 `docs/features/<功能>.md`（若有）。

**七条硬约束速查**（全文见 `§7`，违反任何一条都算 bug）：

1. 单向依赖不倒挂；2. 一切结论带置信度与证据；3. 业务词汇外置到 `engine/lexicon/*.json`（引擎代码里出现业务词即 bug）；
4. 规则引擎判事实、教师判语义、**LLM 只做映射与润色**（判定不许交给 LLM）；5. **可计算才评分**（算不出来 → `not_evaluated`，不许填 0）；
6. 演示可复现可降级；7. **同一输入字节级相同输出**（无随机、无网络、无 `set` 迭代顺序依赖）。

**另有两条本仓库特有的禁令**（`§16.4`）：代码模块 `modules` 与业务域 `business_domains` 的概念并存、两套调用图并存 ——
**这两项现在不要动**，任何工单都不许顺手"统一"它们。

### 22.3 完成定义（缺一项就是没做完）

沿用 `docs/00-index.md` §3.3 的 7 项，并追加**每条工单必须交回的四件东西**：

| # | 必须交回 | 反例（会被打回） |
|---|---|---|
| 1 | 改动清单：文件 + 改了什么 + 为什么 | "优化了若干逻辑" |
| 2 | **每条验收命令的原始输出**（粘贴屏幕输出，不许改写） | "已跑通，应该没问题" |
| 3 | 新增检查的**负向对照**：故意造一个失败用例 → 看到它报错 → 改回 → 通过（两次输出都贴） | "这个检查很严格" |
| 4 | 如实列出「仍未做 / 没验证到」的部分 | 只报好消息 |

**留痕纪律**：本轮改动统一写成「**WO-编号 一轮**」（例如「WO-10 一轮」），**不要只写"本轮"**（`README.md` 顶部约定）。

### 22.4 环境与命令纪律（这些坑都真的踩过，别重复踩）

| 现象 | 绕法 | 出处 |
|---|---|---|
| 把原生程序输出接进 PowerShell 管道（`python x.py \| Select-Object`）→ `Access is denied` | **不要用 `\|`**；要留档就写文件或丢给后台任务 | `§19.5` |
| `python x.py > log 2>&1` 可能**静默不执行**、退出码为空 | 以屏幕输出为准；或在 Python 进程内重定向 stdout | `§19.5` |
| git 报 `dubious ownership` / 子模块管道失败 | `git -c safe.directory=<仓库绝对路径> ...`，`status` 还要 `--ignore-submodules=all`（`validation/flask` 里有嵌套真实 `.git`） | `§19.5` |
| 改了 `engine/lexicon/*.json`（含教师种子）却"没生效" | `load_lexicon()` 是**进程内缓存** → 必须重启 uvicorn | `§19.5` |
| 改了后端路由却"新接口 404" | 启动命令**没有 `--reload`** → 重启 8000 上的 uvicorn | `§19.5` |
| `vite build` 报 `spawn EPERM` | 受限模式下 esbuild 必然起不来；**走查脚本本身不需要放开权限**；构建走查 bundle 要一次性放开进程权限 | `§19.5` |
| 走查拿着旧代码给你"通过" | 走查加载 `.smoke-dist` 产物：**改了 `.vue` 必须重建 bundle** | `§19.5` |
| 离线快照与验收报告对不上 | 改了题目 → **必须重跑** `python scripts/build_demo_snapshots.py`；旧管线冒烟会覆盖学生快照（`WO-04` 会根治它） | `§19.5`、`§17.2` |
| 引用的行号 / 数字第二天就对不上 | 多线并发时**引用前重新 grep / 重跑**；不要把"别人写到一半的状态"当成缺陷去修 | `§19.5` |

### 22.5 并行协议（文件独占 + 分支 + 合并）

**热文件清单**：下面这些文件被多条线同时盯上，是并行失败的唯一真实原因。

| 编号 | 文件 | 同波规则 |
|---|---|---|
| H1 | `backend/app/main.py` | **单持有者**（`WO-02` 拆掉这条瓶颈后，改为"各线各加自己的 router 文件 + 集成轮 include"） |
| H2 | `frontend/src/views/TrainingView.vue` | 单持有者（`WO-06` 之后新增阶段只改配置，不再碰它） |
| H3 | `frontend/src/views/HomeView.vue` | 单持有者（同上） |
| H4 | `frontend/src/App.vue` | 单持有者 |
| H5 | `scripts/browser_clickthrough.mjs` | **可多方，但每方只能在自己阶段的小节内追加断言**，并在交付说明里写清"加在哪一节" |
| H6 | `scripts/verify_sprint0.py` | **可多方，但按工单号升序追加新编号（A12 / A13 …）**，编号唯一 |
| H7 | `scripts/build_acceptance_report.py` | **集成轮独占**（新脚本登记由集成轮做） |
| H8 | `engine/teaching/__init__.py` | 包 docstring 里那份"尚未实现"清单：**集成轮独占** |
| H9 | `docs/07-status-and-acceptance.md` | **集成轮独占** |
| H10 | `docs/08-tech-debt.md` | **集成轮独占** |
| H11 | `README.md` | **集成轮独占** |
| H12 | `validation/acceptance_latest.json` / `.md` | 机器生成，**只有集成轮能重跑重生成** |
| H13 | `frontend/src/api/dataSource.js` | 新接口的数据通道：同波单持有者 |
| H14 | `engine/lexicon/*.json` | **按文件独占**（同波两条线不许写同一个 JSON） |
| H15 | `docs/00-index.md`、`docs/_bundle.md` | 集成轮独占（`_bundle.md` 是机器产物，不许手改） |

**五条规则**：

1. **每条工单一个 git 分支 + 一个 worktree**（`git worktree add ../lwai-wo10 -b wo-10`）。波次表里"前置"没满足之前不许开工。
2. **同波内每个热文件只有一个持有者**（波次表写死）。你**不是**持有者时不许碰它；需要它改，就把改动写进交付说明的**「集成轮待办」**一栏。
3. 下面六处**只有集成轮能改**：`docs/07`、`docs/08`、`README.md`、`docs/00-index.md`、`docs/_bundle.md`、`validation/acceptance_latest.*`。
4. 新增的功能设计卡（`docs/features/<功能>.md`）由**各线自己写**（照 `docs/features/_TEMPLATE.md`，头部要有「更新触发」行），
   但**登记进 `README.md` §0.4 与 `docs/00-index.md` 清单由集成轮做**（D7 要求两份入口都提到它）。
   ⇒ 因此各线本地跑 `python scripts/verify_docs.py` 时，**D7 可能会报"你新加的那份卡没被入口提到"，这是预期的**；
   **除它以外的 ERROR 必须为 0**。`docs/features/_TEMPLATE.md` 与 `docs/_bundle.md` 以 `_` 开头，不参与检查。
5. 合并顺序 = **波内工单号升序**；冲突由集成线解决。**禁止** force push、禁止删别人的分支、禁止直接改别人分支的文件。

### 22.6 波次与依赖总表

> 排序依据：**先解锁并行（基线 → 路由拆分 → 阶段编排外置）→ 再做功能 → 最后做会独占全仓的机械替换**。

| 波次 | 工单（可并行） | 该波热文件持有者 | 前置（不满足不许开工） |
|---|---|---|---|
| **W0** | `WO-01` 基线提交与仓库卫生 | 全部（只此一条线） | — |
| **W1** | `WO-02` 路由拆分 · `WO-03` 训练题遗留 · `WO-04` 门禁补强 · `WO-05` 教师种子备料 | H1 = `WO-02` | W0 完成（基线已提交） |
| **W2** | `WO-06` 阶段编排外置 · `WO-07` 学习会话与能力报告 · `WO-08` 设计模式复核 · `WO-09` 画布功能集 | H2/H3/H13 = `WO-06` | W1 集成完成 |
| **W3** | `WO-10` 阶段三 · `WO-11` 阶段六 · `WO-12` 教师工具链 · `WO-13` 覆盖度评分器与 Skill 报告 | H2/H3 = 无（阶段由配置驱动，见 `WO-06`） | W2 集成完成 |
| **W4** | `WO-14` vue-router 深链与 8 页信息架构 | H4 = `WO-14` | W3 集成完成（页面先存在，才谈路由） |
| **W5** | `WO-15` 稳定 ID 引用规范 | **全仓库（必须独占，单独一波）** | 全部功能工单做完（它会重写几乎所有文档与代码注释） |
| **每波之后** | `WO-90` 集成轮（**串行，一条线**） | H7/H8/H9/H10/H11/H12/H15 | 该波全部工单交付 |

**最短路径（时间不够时按这个顺序砍）**：
`WO-01` → `WO-02` → `WO-06` → `WO-10` → `WO-11` → `WO-12`（对应 `§18` 的"二档完整闭环"：阶段三 / 六 + 教师工具）。
`WO-08` / `WO-09` / `WO-13` / `WO-14` / `WO-15` 都是加分项，可以整单砍掉，**不影响一档能上台**。

> ⚠️ **`WO-02` 与 `WO-06` 不是为了"架构漂亮"**：它们是**并行的解锁项**。
> 不做 `WO-02`，每个要加接口的工单都得改同一个 `main.py`；不做 `WO-06`，每加一个教学阶段都要改 `TrainingView.vue` 与 `HomeView.vue` 两个文件，
> 于是 `WO-10` / `WO-11` 只能串行做。**想并行，就先做这两件。**

### 22.7 发单模板（复制给每个 GPT 会话，替换方括号）

```text
你在一个真实项目（LearnWithAI：把代码库变成业务图谱 + 六阶段教学设计训练）里工作。
仓库根目录：[D:\learn_with_ai]；你的工单：[WO-XX · 工单标题]。

【第一步：读】
1. docs/00-index.md（交接协议 / 硬约束 7 条 / 完成定义 7 项 / 禁止事项 8 条）
2. docs/10-work-orders.md 的 §22（总则、并行协议、环境纪律）与 §23.[你的工单号]（你的完整规格）
3. 你那一单「必读」一栏列出的章节

【你的独占范围】
只能改这些文件：[把该单「独占文件」一栏原样抄过来]
**不在这个列表里的文件一律不许改**（尤其是 README.md、docs/07-*.md、docs/08-*.md、docs/00-index.md、
scripts/build_acceptance_report.py、validation/acceptance_latest.*）——
需要它们改，就写进交付说明的「集成轮待办」一栏，由集成轮统一做。

【必须遵守】
1. 不许填假分 / 编业务含义 / 编干扰项；算不出来的维度一律 not_evaluated（唯一例外见 docs/02 §9.2）。
2. 判定逻辑不许交给 LLM；LLM 只能做讲解与润色，且默认关闭。
3. 不许在自造样本 sample_projects/lab_safety_assistant 上报准确率；仓库里没有任何实测准确率数字。
4. 不许把没做的说成做了；做不到的写进文档的「诚实边界」。
5. 数字不许手抄：验收数字只认 validation/acceptance_latest.md（由机器的报告产出）。
6. 不许重排章节号（会断掉一大片 § 引用，见 docs/00-index.md §3.4）。
7. 命令不许接 PowerShell 管道；改了 lexicon/路由要重启后端；改了题目要重跑 scripts/build_demo_snapshots.py。

【完成定义（缺一项算没做完）】
1. 代码改了；2. python scripts/build_acceptance_report.py 全绿；3. 按 README.md 顶部那张表同步该同步的文档
（但 docs/07、docs/08、README 由集成轮改，你只写「集成轮待办」清单）；
4. python scripts/verify_docs.py 除 D7（你新加的 feature 卡还没登记）外 ERROR 为 0；
5. 新脚本登记事项写进「集成轮待办」；6. 新增检查要有**负向对照**（故意造失败用例并贴出两次输出）；
7. 新功能补一篇 docs/features/<功能>.md（照 _TEMPLATE.md）；8. 本轮改动写成「WO-XX 一轮」。

【交付格式】
① 改动清单（文件 + 做了什么 + 为什么）；② 每条验收命令的**原始输出**；
③ 负向对照的前后两次输出；④ 「集成轮待办」清单；⑤ **仍未做 / 没验证到的部分（如实列出）**。
```

### 22.8 每单固定的字段（读法）

每张工单都按这九个字段写：**目标** / **为什么（证据）** / **前置** / **独占文件** / **必读** /
**判定口径与不变式** / **验收（命令 + 断言）** / **集成轮待办** / **诚实边界**。

---

## 二十三、逐条工单

### 23.1 WO-01 · 基线提交与仓库卫生（W0，独占全仓）

- **目标**：让所有并行线从**同一个已提交的基线**开工；清掉仓库根目录里没有任何引用、也不属于任何脚本产出的残留；修掉文档里已经过期的事实。
- **为什么**：`docs/08` `§19.6` 第 1 条记的是"仓库只有 1 个 initial commit、全部未跟踪"，而 2026-09-26 实测的状态是：
  **已有若干次提交（HEAD 是 `1d640fb`，2026-09-25 10:34），但最近几轮（UI 重设计 / 证据折叠 / 入口完善）的改动全都还没提交** ——
  `docs/` **整个目录**、新组件（`HomeView.vue` / `LoginDialog.vue` / `QuickSearch.vue` / `EvidenceFold.vue` 等）、
  新脚本（`verify_docs.py` / `build_acceptance_report.py` / `pack_docs.py` / `check_evidence_fold.mjs`）都还是 untracked；
  另有一批已删未提交（`README1.md`、`niu/` 下的旧样本文件）。
  在这种状态下开分支，worktree 里会缺文件、合并时会把该删的东西带回来。根目录还留着全仓 grep 零命中的产物；
  `sample_projects/flask_crud_demo` 只剩一个空的 `.git.bak`。**不先收拾，后面每条线都会踩到"基线里带着别人的半成品"。**
- **前置**：无。**这是唯一允许在没有任何前置的情况下动全仓的工单。**
- **独占文件**：仓库根目录、`.gitignore`、`docs/90-archive.md`、`docs/08`（仅 `§19.6` 那一条）。
- **必读**：`docs/00-index.md` §3.4（禁止事项，尤其"不许顺手删看着像旧的东西"）、`docs/90-archive.md`（旧产物处置表）、`§19.6`。
- **做什么**：
  1. **提交现状**：用 `git -c safe.directory=<仓库绝对路径> status --short --ignore-submodules=all` 看清工作区
     （2026-09-26 实测：`docs/` 整个目录、`HomeView.vue` / `LoginDialog.vue` / `QuickSearch.vue` / `EvidenceFold.vue` / `EvidenceNote.vue`、
     `verify_docs.py` / `build_acceptance_report.py` / `pack_docs.py` / `check_evidence_fold.mjs`、`validation/acceptance_latest.*` 都还是 untracked；
     另有一批已删未提交：`README1.md` 与 `niu/` 下的旧样本文件）。
     把尚未提交的那几轮改动（文档里记的 UI 重设计一轮 / 证据折叠一轮 / 入口完善一轮）作为一个或几个提交，message 逐轮写清。
     **这一步不许顺手改任何代码**；**`aud.m4s` / `vid.m4s` / `generated_assets_motion_tiles_20260926/` 不要提交**（留给第 2 步处理；**第 2 步已清理**）；`.ai_orchestrator`（编排器的运行产物目录）也不要提交。
  2. **清理无引用残留**：先全仓确认下列产物**没有任何代码 / 脚本 / 文档引用**，再删：
     根目录的 `aud.m4s`、`vid.m4s`、`generated_assets_motion_tiles_20260926/`、空目录 `assets/`（这四项**已清理**，登记在 `docs/90-archive.md` 附录 C.2）。
     **删之前必须在 `docs/90-archive.md` 的处置表里登记一行**（本仓库的纪律：清理要留痕，否则下一个人会以为丢了东西）。
  3. **补 `.gitignore`**：至少让同类产物（如 `*.m4s`）不再进仓库。
  4. **`flask_crud_demo` 的处置决定**（二选一，都要留痕）：① 明确"源码已丢失、不再恢复"，把 `.git.bak` 一并清掉，
     并在 `docs/90-archive.md` 与 `§19.6` 写明"自造样本只剩 1 个"；② 保留 `.git.bak` 并写清保留理由。**不许默默删，也不许留着不说。**
  5. **复核 `§19.6` 第 1 条**：工单编排一轮已按 2026-09-26 实测改写过一次（HEAD 是哪一次、哪些还没提交）；
     你提交完之后**再核一遍**，状态变了就再改一次，并在末尾保留一句"并行开工前先提交"。
- **验收**：`python scripts/verify_docs.py`（**exit 0**）；`python scripts/build_acceptance_report.py`（全部脚本通过）；
  `git status --ignore-submodules=all` 干净（除被忽略项）。三条命令的输出原样贴回。
- **集成轮待办**：无（本单就是基线的建立者）。
- **诚实边界**：本单**不改任何产品行为**。如果发现某个残留其实被某个脚本当作输入，**停下来**，把它写进交付说明而不是删掉。

### 23.2 WO-02 · 后端路由拆分（W1，独占 H1；并行的第一次解锁）

- **目标**：把 `backend/app/main.py` 里的全部路由按域拆到 `backend/app/routers/` 下的多个模块（**该目录待建**），
  `main.py` 只保留 app 创建、CORS、`version=` 与 `include_router`。
- **为什么**：`main.py` 是**唯一路由文件**，所有要加接口的工单都得改它 —— 这是并行开发最硬的瓶颈。
  拆完之后，每条线在自己的 `routers/<域>.py` 里加路由，集成轮只做一行 include。
- **前置**：`WO-01` 完成。
- **独占文件**：`backend/app/main.py`、`backend/app/routers/`（待建）、`backend/app/services/*`（仅在需要移动依赖时）。
- **必读**：`docs/04` §11.1（接口清单）、`§11.2`、`docs/00-index.md` §3.6（代码地图）、`docs/06` §19.5（重启后端那条）。
- **判定口径与不变式**：
  - **只搬移，不改行为**：路径、方法、请求体、响应字段、状态码、错误文案**逐字不变**；
  - `version=` **必须留在 `main.py`**（文档门禁 D3 就是读它，见 `docs/00-index.md` §3.7）；
  - 不许顺手改判定逻辑、不许顺手改字段名（那是别的工单的事）；
  - 拆完之后**每个 router 文件头部**写一句"它承载哪些路由 + 对应文档章节"，便于后来者定位。
- **验收**：`python scripts/verify_sprint0.py`（全绿）；后端起来后跑 `python scripts/test_logic_platform_api.py`（需要 8000 端口，见 `docs/05` §21.7）；
  `python scripts/verify_docs.py`（exit 0）；`python scripts/build_acceptance_report.py`（全绿）。
  **额外负向对照**：随便挑一个路由，把它的路径改错一个字符 → 该接口必须 404（证明你确实还在提供这些路由，而不是"看起来拆完了"）。
- **集成轮待办**：① `docs/04` §11.1 / §11.2 里那些 `main.py:行号` 形式的引用要改指新文件（否则文档门禁 D6 会说行号过期）；
  ② `docs/04` §11 开头"唯一路由文件"的说法要改成"路由按域分文件、`main.py` 只做装配"；③ `docs/00-index.md` §3.6 代码地图补 `backend/app/routers/`（**待建**，本单新建）。
- **诚实边界**：**如果你判断这次拆分风险大于收益**（比如离演示很近），可以**不做**，改为在交付说明里写清
  "`main.py` 仍由集成轮统一追加路由" —— 代价是后续工单不能自测自己的 HTTP 接口。**两种选择都要如实写出来，不要含糊。**

### 23.3 WO-03 · 训练题遗留：第 2 关出题与第 4 关干扰项（W1）

- **目标**：修掉两个已登记的遗留项：`python_dotenv` 第 2 关**一道题都不出**；第 4 关干扰项仍是**固定模板**。
- **为什么**：`§16.2` 的"训练题第 1/2/3/4 关"一行与 `§19.1` 台账里都记着这两条；代码里也留着一个 `TODO(Sprint 1)` 指向干扰项的派生方式。
- **前置**：`WO-01` 完成。
- **独占文件**：`engine/project_analyzer/training_generator.py`、`scripts/test_training_questions.py`、`engine/lexicon/quiz_labels.json`（若需文案）。
- **必读**：`§19.1` 第 4、5、14、15 条（出题的诚实纪律）、`§16.1` 末（第 1 关为什么不需要改、第 2 关的"够格"口径）、`docs/07` §17.2（顺序陷阱）。
- **判定口径与不变式**：
  - **凑不出就不出题，不许编造**：`§19.1` 第 4 条说的是"凑不出数据就**不出题**，不编造" —— 这条不许为了"看起来更好"而破。
    若 `python_dotenv` 第 2 关确实只有一个可用的业务语义文本，正确交付可能是"**如实输出为什么不出题**"，而不是硬凑一道。
  - 选项与干扰项**必须来源于真实数据**（模块文本 / 流程步骤标签 / 其他模块的真实实现），不许写死；
  - **确定性**：任何派生都要排序，不许依赖 `set` 迭代顺序（`§8.9`）；
  - 题目变了**必须重跑** `python scripts/build_demo_snapshots.py`（答案表与题目按下标对应）。
- **验收**：`python scripts/test_training_questions.py`（扩断言，含负向对照：注入一组"够格但无文本"的模块，断言**不出题**）；
  `python scripts/verify_sprint0.py`；重跑产物脚本后 `python scripts/build_acceptance_report.py` 全绿。走查断言按 `§22.5` 规则在 H5 对应小节内追加。
- **集成轮待办**：`docs/07` §16.2 那一行按实际结果改写（包含"**若仍不出题，原因是什么**"）。
- **诚实边界**：干扰项"更真实"不等于"更好"——若新干扰项会让某道题的正确答案不唯一，**宁可保留固定模板**并在文档里写清。

### 23.4 WO-04 · 门禁补强三件（W1）

- **目标**：把三条"只能靠人盯着"的纪律变成机器检查：① 旧管线冒烟覆盖学生快照的顺序陷阱；② 六阶段状态表与文档完成度表的一致性；③ 逻辑平台"口径文案 ↔ 引擎机制"的一致性。
- **为什么**：`§19.1` 第 22 条（⚠️ 未修）、`§19.1` 第 26 条（⚠️ 没有机器化办法）、`docs/features/ui-shell-redesign.md` §4 明写"把没做的说成做了"的**假阳**当前只能靠人。
- **前置**：`WO-01` 完成。
- **独占文件**：`scripts/test_project_analyzer.py`、`scripts/test_deep_analyzer.py`、`scripts/test_full_engine.py`、`scripts/build_demo_snapshots.py`、
  `scripts/verify_docs.py`、`scripts/check_stage_consistency.py`（**待建**）、`engine/logic_platform/verification_manifest.json`（**待建**）、
  `frontend/src/components/logic-platform/ImmersiveLesson.vue`、`frontend/src/components/logic-platform/VerificationPanel.vue`。
- **必读**：`§19.1` 第 22、26 条、`§19.4`（"同一句禁令写进文案就会踩断言"那条）、`docs/features/evidence-fold.md` §2 第 6 条、`docs/06` §19.5。
- **三件分别怎么做**：
  1. **顺序陷阱根治**：让旧管线冒烟（`test_project_analyzer.py` / `test_deep_analyzer.py` / `test_full_engine.py`）**不再写** `frontend/public/demo/` 下的学生快照，
     或者让它与 `build_demo_snapshots.py` 共用同一个写出函数。**验收方式本身要有断言**：跑冒烟前后对学生快照取 sha256，必须不变。
     负向对照：把冒烟改回覆盖写 → 该 sha256 断言必须 FAIL。
  2. **六阶段状态表一致性**：给 `frontend/src/views/HomeView.vue` 的阶段状态表与 `docs/07` `§16.3`（未开始清单）加机器检查
     （新脚本 `scripts/check_stage_consistency.py` 待建，或给 `verify_docs.py` 加一项）。负向对照：把某一阶段的 `status` 改成 `done` → 必须报错。
  3. **口径文案一致性**：把讲稿 / 反幻觉面板说明里提到的引擎机制做成**机器可读的唯一来源**
     （例如 `engine/logic_platform/verification_manifest.json` 待建：检查项、四条把关规则、`can_publish` 恒假），
     再写一个比对脚本（前端不能直接读 `engine/`，所以允许"由脚本读清单 + 读组件里的说明常量再比对"）。
- **验收**：三件各带负向对照；`python scripts/verify_docs.py` exit 0；`node scripts/check_evidence_fold.mjs` 仍全绿（它是折叠口径的常驻检查）。
- **集成轮待办**：`docs/06` §20.1 与 `docs/07` §17.2 登记新脚本；`§19.1` 第 22、26 条状态从"⚠️ 未修"改为"✅ 已加机器检查"（或如实写"部分修"）。
- **诚实边界**：**不许为了让文案通过而放宽断言**（`§19.4` 第 4 条的教训：放宽断言比改一句文案危险得多）。
  第 ③ 件如果做不到"派生"，就退成"比对 + 触发条件写在文档里"，并如实说明它抓不到什么。

### 23.5 WO-05 · `python_dotenv` 教师种子备料（W1，**含人工确认环节**）

- **目标**：给第三个真实项目补上两份教师种子：`validation/python_dotenv/business_graph.seed.json`（**待建**）与
  `engine/lexicon/design_tasks.seed.json` 里 `python_dotenv` 那一段（当前是空的）。它决定这个项目上"阶段一的目标比对、六维里四项"能不能真的算出来。
- **为什么**：`§16.2` 两行明写：`python_dotenv` 没有种子图谱、没有设计任务种子，所以那四项在它上面恒为「本轮未评估」；
  两个演示项目口径不同，**演示时必须说清是哪一个**。
- **前置**：`WO-01` 完成。
- **独占文件**：`validation/python_dotenv/business_graph.seed.json`（待建）、`engine/lexicon/design_tasks.seed.json`（**只加 `python_dotenv` 一段，不许动已有那段**）、
  `scripts/export_seed_candidates.py`（**待建**，产出人工确认用的候选清单）。
- **必读**：`§9.1`（`must_have` 从哪来，第 ③ 条：**绝不许 LLM 生成后当评分基准**）、`§8.8`（种子合并的两个坑）、`§13.2`（证据纪律）、`docs/03` 附录 A 的"教师种子图谱"一行。
- **判定口径与不变式**：
  - **AI 只产"候选 + 逐项源码证据"**（每条候选回指 `文件:行号`），**最终 `must_have` 与 `objective` 由人逐条确认**后才落盘；
  - 域目标**必须填在 `module_cards[<domain_id>]` 里**（域对象根本没有 `objective` 字段）；
  - `objective_confidence: "confirmed"` **必须显式写**（它不在可锁字段里，写成空串等于没填）；
  - 「一个项目一旦有种子任务，它原有的自动任务就不再生成」是**刻意行为**，别当 bug 修（`test_design_seed.py` 有断言钉着它）。
- **验收**：`python scripts/export_seed_candidates.py`（**待建**，产出候选清单，含逐项证据）；人确认记录；
  `python scripts/test_design_seed.py`、`python scripts/test_business_graph.py`、`python scripts/verify_sprint0.py`（A10/A11 的数字变化由机器报告产出，**不许手抄**）。
  负向对照：故意把候选清单里一条无证据的候选塞进种子 → 测试必须报出来（证明"证据回指"是被检查的）。
- **集成轮待办**：`docs/07` §16.2 的"种子图谱兜底 / 阶段四·五"两行按实际结果改写（含仍缺什么）；`docs/03` 附录 A 与 `docs/02` §8.8 的"已落地 1 个项目"改为 2 个（若确实做完）。
- **诚实边界**：**本单的交付物一半是人填的**。如果没人确认，正确交付是"候选清单 + 明确标注无人确认"，
  **绝不许**把 AI 生成的 `must_have` 标成 `confirmed`（那是 `§9.1` 第 ③ 条直接禁止的事）。

### 23.6 WO-06 · 阶段编排外置（W2，独占 H2/H3/H13；并行的第二次解锁）

- **目标**：把"有哪几个阶段、什么顺序、哪个能点、没做的那几个叫什么"从两个 Vue 文件的硬编码，搬成**配置 + 接口**。
- **为什么**：`§16.2` 明写「有哪几个阶段、按什么顺序」仍写在前端 `TrainingView.vue`，没有 `teaching_plan.json`；
  `§10.3` 把这份契约写成"待实现"；而 `docs/features/ui-shell-redesign.md` §4 承认"界面表 vs 文档表"没有任何断言。
  只要它还在前端硬编码，**每加一个阶段都要改 `TrainingView.vue` 与 `HomeView.vue`** → `WO-10` / `WO-11` 只能串行。
- **前置**：W1 集成完成（`WO-02` 之后加路由不再是瓶颈）。
- **独占文件**：`frontend/src/views/TrainingView.vue`、`frontend/src/views/HomeView.vue`、`frontend/src/api/dataSource.js`、
  `engine/lexicon/teaching_plan.json`（**待建**）、`engine/teaching/plan.py`（**待建**）、`scripts/test_teaching_plan.py`（**待建**）、`backend/app/routers/*`（新文件，若 `WO-02` 已落地）。
- **必读**：`docs/03` §10.3（`teaching_plan.json` 契约）、`docs/04` §12.1（8 页信息架构与当前五页签）、§12.2（A/B 两阶段决策）、`docs/features/ui-shell-redesign.md` §2 第 2 条与 §4。
- **判定口径与不变式**：
  - 契约形状照 `§10.3`：`stages[]`（`stage` / `key` / `name_cn` / `objective` / `task` / `items` / `questions` / `scoring`）；
  - **未落地的阶段不给入口**（渲染成 `disabled`，不写"即将上线"这类话）—— 这条是现存走查断言盯着的，不许破；
  - 阶段文案仍然**不许出现业务硬编码**（`audit_hardcoding.py --include-frontend` 必须 0 命中）；
  - 阶段编排里**不许出现任何分数口径**：打分与否由各阶段自己的 `scoring` 字段决定（阶段一/二/三是覆盖型，阶段四/五才有分数）。
- **验收**：`python scripts/test_teaching_plan.py`（**待建**，本单新建，含"配置改了页面跟着变，不用改代码"的断言）；
  `python scripts/verify_sprint0.py`（新增 A12：学习路线契约）；`python scripts/verify_docs.py` exit 0；
  走查里"主页面六阶段入口与完成度表一致（只有已落地的阶段可点）"这条**仍全绿**（H5 规则见 `§22.5`）。
  负向对照：在配置里把某一阶段标成已落地 → 页面上它必须变成可点（并在文档门禁里被 `WO-04` 的一致性检查抓到）。
- **集成轮待办**：`docs/03` §10.3 去掉"待实现"字样；`docs/04` §12.1 / §12.2 / §12.3 改为"阶段由配置驱动"；`docs/07` §16.2 那一行"教学路线写在前端"改为已完成；`docs/06` §20.1 登记新脚本。
- **诚实边界**：配置只解决"阶段清单与顺序"，**不解决**"每个阶段的判定口径"——那些仍归各自的引擎模块。
  不要把本单说成"六阶段可配置化已完成"。

### 23.7 WO-07 · 学习会话 + 存储层 + 能力报告（W2）

- **目标**：把学习会话从"只有浏览器 `localStorage`"升级成"后端有存储、能恢复、能出能力报告"。
- **为什么**：`§16.3` 列着"学习会话接口（`/api/sessions`）与存储层（当前只有 `localStorage`）"；
  `§11.4` 列着那几条待实现接口；`§12.1` 的第 ⑧ 页「能力报告」一个都没有；`docs/04` §12.6 第 6 条要求事件写入会话供能力报告使用。
- **前置**：W1 集成完成。
- **独占文件**：`backend/app/services/session_store.py`（**待建**）、`backend/app/routers/sessions.py`（**待建**）、`frontend/src/stores/learningSession.js`、
  `frontend/src/components/StageOrientation.vue`、`frontend/src/components/StageModuleCard.vue`、`engine/teaching/capability.py`（**待建**）、`scripts/test_session_store.py`（**待建**）。
  ⚠️ `StageDesign.vue` **不要碰**（它归 `WO-09`）。
- **必读**：`docs/04` §11.4（待实现接口清单）、`§11.5`（存储分期，**不许宣称超期能力**）、`§12.6`（交互契约六条）、`§12.7`（会话恢复契约）、`docs/03` §10.5。
- **判定口径与不变式**：
  - **会话恢复不许静默沿用**：`source_hash` 或 `contract_version` 不匹配 → 提示「教学材料已更新，请重新开始或继续（部分进度需重做）」；
  - **能力报告不许给"总分证明掌握"**：只汇总**行为与覆盖度**（读过什么、用了哪些提示、答了什么），
    措辞照 `§9.2` 那条纪律："**未识别到**"而不是"你漏了"；
  - 存储按 `§11.5` 的 **P1 口径**（文件 / SQLite），**不许**宣称有班级管理、多用户权限、跨设备会话；
  - 事件字段名沿用 `§12.6` 第 6 条：`viewed_evidence` / `hint_used` / `answered`。
- **验收**：`python scripts/test_session_store.py`（**待建**，本单新建：创建 / 恢复 / 事件写入 / 哈希变化时**拒绝**静默沿用）；
  `python scripts/verify_sprint0.py`（新增 A13：会话与事件）；走查按 `§22.5` 规则在对应小节追加事件断言。
  负向对照：把 `source_hash` 改掉再恢复会话 → 必须出现"教学材料已更新"提示，且**不**沿用旧进度。
- **集成轮待办**：`docs/04` §11.4 把已实现的四条从"待实现"表里移出并补进 §11.1；`§11.5` 的"P0（当前）"一行改为"P1"；`docs/07` §16.3 删掉对应条目；`docs/06` §20.1 登记新脚本。
- **诚实边界**：这是**本地演示级**的存储：无鉴权、无并发保证、无迁移机制。**不要**在页面或文档里把它写成"账号系统"。

### 23.8 WO-08 · 设计模式检测器：把决策钉成持续检查（W2）

- **目标**：在不伪造准确率的前提下，把 `§19.2` ⑱ 那条"决策必须被执行"变成**每次都能验证**的东西。
- **为什么**：`§19.1` 第 16 条仍是 🟡（检测器质量未提升）；⑱ 记录过"文档写着不进学生视图，代码里三条通路在违反它"，靠一次人工复核才发现。
- **前置**：W1 集成完成。
- **独占文件**：`engine/deep_analyzer/design_pattern_detector.py`、`scripts/probe_design_patterns.py`（**待建**）、`scripts/validate_contract.py`。
- **必读**：`§19.2` ⑱ 与它的规模证据、`docs/02` §8.9 末的补充决策、`docs/03` §10.5（学生视图边界）。
- **做什么**：
  1. 把当初读完即删的临时探针升级成**常驻脚本** `scripts/probe_design_patterns.py`（待建）：输出各项目上模式判定分布，**可复现**（排序、无随机）；
  2. 给 `validate_contract.py` 的"学生可见文本里不得出现设计模式结论"那一项**扩成三条通路各一条断言**
     （题干 `design_approach`、讲解 `importance_reasons`、分数影响），每条都做负向对照；
  3. 检测器本身：**只做"低置信度不计入 / 显式丢弃"这类可验证的改动**，**不许**用"看起来更准了"来宣称质量提升。
- **验收**：`python scripts/validate_contract.py --project sample_projects/lab_safety_assistant`（两个项目都要跑）；
  `python scripts/check_determinism.py --cross-process`；`python scripts/probe_design_patterns.py`（**待建**）连跑两次输出逐字节相同。
  负向对照：把模式名塞回题干 → `validate_contract.py` 必须 FAIL（贴两次输出）。
- **集成轮待办**：`§19.1` 第 16 条与 `§16.2`"设计模式识别"一行按实际改动更新；`docs/06` §20.1 登记新脚本。
- **诚实边界**：**误报率需要一个真值标注集才能说**，而 `§13.2` 禁止在自造样本上算准确率。
  所以本单**不产出任何准确率数字**；能说的是"三条泄漏通路现在有机器检查了"。

### 23.9 WO-09 · 画布功能集补全 + 状态抽取 + 事件埋点（W2）

- **目标**：补齐设计画布"没做的"那一串功能，并把画布状态从组件里抽出来。
- **为什么**：`docs/04` §12.4 末明写"**没做的**：拖拽成组、自动布局、撤销/重做、多选框选、连线类型选择（只有 `uses`）"；
  `§12.7` 明写"上表的四只 store 一只都还没建"，其中 `frontend/src/stores/designCanvas.js`（**待建**）正是画布那只；`§12.6` 第 6 条的事件埋点也还差画布这一块。
- **前置**：W1 集成完成。
- **独占文件**：`frontend/src/components/StageDesign.vue`、`frontend/src/stores/designCanvas.js`（**待建**）。
- **必读**：`docs/04` §12.4（技术选型：**不引第三方图库**）、§12.6（六条交互契约）、§12.7、`docs/02` §9.2（六维口径）。
- **判定口径与不变式**：
  - **不引第三方图库**（原生 drag + 手写 SVG），与既有实现保持一致；
  - **节点坐标存在数据里、连线路径由坐标算出**（不依赖 DOM 测量）——这是 jsdom 走查能断言的前提，不许改成读 DOM 尺寸；
  - 提交前**不渲染**任何报告 / 结论（`§12.6` 第 1 条）；未评估维度**不显示 0**；
  - 第 2 次提交的 `iteration` 必须递增（`§19.2` ⑯ 的老坑：先构造提交、再清空报告，顺序不能反）。
- **验收**：`scripts/browser_clickthrough.mjs` 第 16 节扩断言（按 `§22.5` 规则，只在自己的小节内追加）；
  `python scripts/test_design_rubric.py` 仍全绿；`python scripts/audit_hardcoding.py --include-frontend` 0 命中。
  负向对照：把"提交前不渲染报告"改回去 → 走查必须 FAIL。
- **集成轮待办**：`docs/04` §12.4 的"没做的"清单按实际结果改写；`§12.7` 的四只 store 状态更新；`docs/07` §16.2 相应行更新。
- **诚实边界**：撤销/重做与多选框选是**体验项**，不影响任何判定；别为了做它们而改动六维口径。

### 23.10 WO-10 · 阶段三「流程推演」全链路（W3）

- **目标**：把六阶段里唯一"完全没开始"的教学阶段从零落地：场景 → 学生排序 → **第一分歧点 + 证据**。
- **为什么**：`§16.3` 第一条就是它；`§10.3` 的 `teaching_plan.json` 里 `flow_sim` 只有一个空壳定义；
  `docs/04` §12.1 的 ④ 页「流程推演」一个都没有；`docs/01` §4 阶段三写了教学意图但没有任何实现。
- **前置**：W2 集成完成（尤其 `WO-06`：阶段入口必须由配置驱动，否则你会去改两个前端硬编码文件）。
- **独占文件**：`engine/teaching/flow_sim.py`（**待建**）、`engine/lexicon/flow_sim.json`（**待建**）、
  `frontend/src/components/StageFlowSim.vue`（**待建**）、`scripts/test_flow_sim.py`（**待建**）、`docs/features/flow-simulation.md`（**待建**）、
  `backend/app/routers/teaching.py`（**待建**，你新建；若 `WO-02` 未做，则 H1 由你独占）。
- **必读**：`docs/01` §4 阶段三（教学意图）、`docs/02` §8.7（三型场景怎么生成、**必须过滤生命周期流程**）、`§8.9`（确定性）、
  `docs/04` §12.1 ④ 与 §12.6（交互契约）、`docs/03` §10.5（可见性）、`§19.1` 第 6 条（"把初始化流程当核心业务流程"是教学性错误）。
- **判定口径与不变式**：
  - **不打分**：与阶段一 / 二同构，`scoring = order_only`、`has_score: false`；输出是"顺序差异 + 第一分歧点 + 每步证据"，
    **不是**"你错了"。要改成打分属于**新口径**，必须由人拍板并同步 `docs/01`（默认不做）；
  - **优先真实业务路径**：生命周期 / 初始化流程**不许**当答案（`§8.7` 唯一实现 `engine/flow_filter.py`，复用，不要另写一份）；
  - **学生先输出**：反馈区提交前一个节点都不渲染（`§12.6` 第 1 条）；
  - 场景与文案全部走词典（`engine/lexicon/`），**引擎代码里不许出现业务词**（`audit_hardcoding.py` 会抓）；
  - 三型场景（normal / exception / edge_case）派生**要求 ≥2 步，凑不出就不出**（`§8.7`）。
- **验收**：`python scripts/test_flow_sim.py`（**待建**，本单新建：不打分 / 不丢步 / 确定性 / 拒绝空提交 / **生命周期流程不当答案**）；
  `python scripts/verify_sprint0.py`（新增 A14：阶段三）；`python scripts/verify_docs.py` exit 0；
  走查新增阶段三小节（含"提交前不渲染反馈"与"离线如实报不可用"两类断言）。
  负向对照：把某个场景的答案换成一条 `initialize_*` 流程 → 测试必须 FAIL。
- **集成轮待办**：`docs/01` §4 阶段三加"已落地"段落与实现位置；`docs/03` 附录 A 加阶段三契约行；`docs/04` §11.1 / §12.1 / §12.3；
  `docs/07` §16.1 加完成度、**§16.3 删掉这一条**；`README` §0.2 完成度表；`HomeView` 的阶段状态表（若 `WO-06` 未做）；`docs/06` §20.1 登记新脚本。
- **诚实边界**：**不做中文分词**（同阶段一），所以给不出"你额外想到了哪些步骤"；
  学生顺序对了**不等于**理解了"哪个模块该承担哪种判断"（那要靠阶段二 / 四）。

### 23.11 WO-11 · 阶段六「重构挑战」与 `reconstruct.py`（W3）

- **目标**：落地六阶段最后一个：追加需求 → 学生改设计 → **影响范围命中**。
- **为什么**：`§16.3` 第二条；`docs/02` §9.3 把 `engine/design/reconstruct.py` 写成"待建"（`engine/design/` 其余七个文件都已实现）；
  `docs/04` §12.1 的 ⑦ 页一个都没有；它也是 `§18` 一档/二档表里"二档 = 一档 + 重构挑战 + 教师工具"的那一半。
- **前置**：W2 集成完成（同 `WO-10`：入口走配置）。
- **独占文件**：`engine/design/reconstruct.py`（**待建**）、`engine/lexicon/reconstruct_tasks.json`（**待建**）、
  `frontend/src/components/StageReconstruct.vue`（**待建**）、`scripts/test_reconstruct.py`（**待建**）、`docs/features/reconstruct-challenge.md`（**待建**）、`backend/app/routers/teaching.py`（**待建**）。
- **必读**：`docs/02` §9.3（四步算法与"不做的事"）、§9.1（任务生成与种子）、§9.2（六维口径里哪些维度会随重构变化）、`docs/04` §12.1 ⑦ 与 §12.6。
- **判定口径与不变式**：
  - **不判断"你的重构是否正确"**：只报"你改了哪些 / 应改哪些没改 / 改完是否引入环"（`§9.3` 原话）；
  - 影响范围计算必须**可复现**（排序 + 无随机 + 无 `set` 迭代顺序）；
  - 追加需求**模板化**，不许调 LLM 生成"业务故事"（`§8.7` 末条纪律同理）；
  - 复用既有能力，**不许另写第二套匹配**：模块 / 能力匹配走 `engine/design/matcher.py`，图检查走 `engine/design/graph_checks.py`。
- **验收**：`python scripts/test_reconstruct.py`（**待建**，本单新建：影响范围命中 / 未识别连带影响 / 引入环的检出 / 确定性）；
  `python scripts/check_determinism.py --cross-process`；`python scripts/verify_sprint0.py`（新增 A15）；走查新增阶段六小节。
  负向对照：故意交一份"只加了一个无关模块"的重构 → 影响范围命中率必须如实低，且**不许**编出"你做对了"的结论。
- **集成轮待办**：`docs/02` §9.3 从"待建"改为已实现（保留口径）；`docs/01` §4 阶段六加"已落地"段落；`docs/03` 附录 A 加契约行；
  `docs/04` §11.1 / §12.1 / §12.3；`docs/07` §16.1 + **§16.3 删掉这一条**；`README` §0.2；`docs/06` §20.1。
- **诚实边界**：影响范围是**基于已有信号**的推断，不是"真值"。报告里必须写清它认哪些信号、不认哪些（照 `§9.2` 的写法）。

### 23.12 WO-12 · 教师工具链：审核 `stale` + 图谱审核 + Gold Graph（W3）

- **目标**：把"教师是课程设计者"这一半从只有"关键实现确认"扩展成：图谱审核（确认 / 拒绝 / 改名）、**审核随源码变化的 `stale` 机制**、Gold Graph 编辑。
- **为什么**：`§16.2` 明写"教师审核：只覆盖关键实现；模块改名、图谱审核、Gold Graph 编辑器都没有"；
  `§6.1` 定了 `stale` 的语义；`§11.4` 列了四条待实现接口；**`§18` 优先级 2 把"人工核对"延后的技术理由正是"图谱审核的 `stale` 机制还没实现"**。
- **前置**：W2 集成完成。
- **独占文件**：`backend/app/services/review_store.py`（**待建**）、`backend/app/routers/teacher.py`（**待建**）、
  `engine/business_graph/seed_writer.py`（**待建**）、`frontend/src/components/TeacherReviewBar.vue`（**待建**）、
  `frontend/src/stores/teacherReview.js`（**待建**）、`scripts/test_review_store.py`（**待建**）、`docs/features/teacher-review.md`（**待建**）。
- **必读**：`docs/01` §6.1（四个审核状态与版本纪律）、`§6.2`（学生界面绝不能出现的东西）、`docs/02` §8.8（种子合并与两个坑）、
  `docs/03` §10.5、`docs/04` §11.4、`§18` 优先级 2 的"延后理由"一段。
- **判定口径与不变式**：
  - **`stale` 语义**：审核绑定 `analysis_version` + `source_hash` + `reviewed_by` + `reviewed_at` + `fields_locked`；
    重新分析后哈希变化 → **不许静默覆盖**，必须返回 `review_status = "stale"` 并提示"源码已变化，以下 N 项需复核"；
  - **写回 seed 必须确定性**：键序固定、缩进固定、UTF-8、末尾换行 —— 同一份审核连写两次，文件字节相同；
  - `source_hash` **只哈希被解析的 `.py`**：写种子 / 写审核**不许**让既有审核失效（`§8.8` 实测口径）；
  - 学生视图边界：**权重数值、完整 Gold Graph、`correct_answers` 一律不下发**（`§10.5`、`§6.2`）；
  - 教师改名写回 seed 之后，**必须重跑** `python scripts/build_demo_snapshots.py`（快照里带着图谱）。
- **验收**：`python scripts/test_review_store.py`（**待建**，本单新建：确认 / 拒绝 / 改名落地 / **哈希变化后变 `stale`** / 写出确定性）；
  `python scripts/verify_sprint0.py`（新增 A16）；`python scripts/verify_docs.py` exit 0；走查新增教师模式小节（含"学生视图看不到权重"的断言）。
  负向对照：改一个被解析的 `.py` 后重新分析 → 旧审核必须变 `stale`（改回来 → 恢复 `approved`）。
- **集成轮待办**：`docs/04` §11.4 把已实现接口移入 §11.1；`docs/01` §6.1 末的"现状：只有关键实现确认"改写；
  `docs/07` §16.2"教师审核"一行改写；`docs/08` §19.1 若涉及则更新；`docs/06` §20.1 登记新脚本。
- **诚实边界**：本单交付的是**工具**，不是"准确率"。人工核对那 184 行判定仍然只能由人填，
  而且按 `§18` 的决定要等到**引擎冻结之后**（否则判定会被后续改动作废）。**不许**把本单说成"准确率已经能报了"。

### 23.13 WO-13 · 覆盖度评分器 + 《Skill 失效点实测报告》（W3）

- **目标**：交付 `§16.3` 里最后两条：覆盖度评分器、Skill 失效点实测报告。
- **为什么**：`§16.3` 末条就是它们；`docs/01` §1.2 明写这份报告要覆盖五个维度，**并且写了那个可能不好看的结论**（"如果纯 Prompt 全都做到了，就应该停掉这个项目或只做 Skill 版本"）。
- **前置**：W2 集成完成。
- **独占文件**：`engine/teaching/coverage_score.py`（**待建**）、`scripts/test_coverage_score.py`（**待建**）、
  `scripts/run_skill_probe.py`（**待建**）、`validation/skill_failure_report.md`（**待建**）。
- **必读**：`docs/01` §1.2（五个维度与那条必须接受的结论）、§1.1（不是什么）、`docs/02` §7 第 5 条（可计算才评分）、`§9.2`（"未评估不填 0"的先例）、`docs/09` §13.1 / §13.7（不许说 vs 应该说）。
- **判定口径与不变式**：
  - 覆盖度评分器**不许造新判定**：它的输入就是既有三个阶段（一 / 二，以及 `WO-10` 之后的阶段三）的比对器输出；
  - **算不出来的维度返回 `not_evaluated`**（不许填 0，`§7` 第 5 条）；页面 / 报告里**不许出现"总分证明掌握"**这类结论；
  - Skill 失效点报告：**一致性维度需要"同一个问题问 10 次"**，这需要外部 LLM 调用。
    **如果环境无网络 / 无 API：只交付可复跑的报告骨架 + 需要人跑的步骤，并在报告里写"未实测"**。
- **验收**：`python scripts/test_coverage_score.py`（**待建**，本单新建：不打分越界 / `not_evaluated` 不填 0 / 确定性）；
  `python scripts/verify_docs.py` exit 0。负向对照：让某个阶段缺输入 → 该维度必须 `not_evaluated`，**不许**出现 0 或 null 以外的值。
- **集成轮待办**：`docs/07` §16.3 删掉对应两条（或改写成"骨架已就位、未实测"）；`docs/06` §20.1 登记新脚本；`docs/01` §1.2 若实测有结论则补一句（**没有实测就不许补**）。
- **诚实边界**：**本仓库里没有任何实测准确率数字**。Skill 报告如果只跑了骨架，就必须写成"骨架 + 未实测"，
  **绝不许**编造一致性 / 可定位性 / 大批量维度的实测结果。这一条没有商量余地（`§13.2`）。

### 23.14 WO-14 · vue-router 深链与 8 页信息架构（W4）

- **目标**：把 8 页信息架构变成可深链的路由（答辩时能直接跳页）。
- **为什么**：`docs/04` §12.1 明写"这 8 页信息架构还没做"；`§12.2` 把它定为 **B 阶段 = 加分，不是必做**；`§16.3` 也列着 `vue-router` 深链。
- **前置**：W3 集成完成（阶段三 / 六 / 能力报告的页面**先存在**，否则没有可路由的页）。
- **独占文件**：`frontend/src/App.vue`、`frontend/src/main.js`、`frontend/package.json`、`frontend/src/router/`（**待建**）。
- **必读**：`docs/04` §12.2（A/B 两阶段决策，**不要为了架构漂亮重写外壳**）、§12.1、`docs/00-index.md` §3.4（禁止重写前端外壳那条）。
- **判定口径与不变式**：
  - **A 方案必须保留**：`v-if` 切换的现有行为不许被推翻，路由是**增量**；
  - 深链必须能落到具体阶段（例如"直接打开某个阶段 URL 就落在那"），且**未落地的阶段仍然不给入口**；
  - 走查与演示动线不变（现有断言的**前置状态**不许因为默认落地页 / 路由变化而失效 —— `docs/features/ui-shell-redesign.md` §9 踩过这个坑）。
- **验收**：`node node_modules/vite/bin/vite.js build`（等价构建命令，需一次性放开进程权限，见 `docs/06` §19.5）成功；
  走查全绿（含新增的深链断言）；`python scripts/verify_docs.py` exit 0。
- **集成轮待办**：`docs/04` §12.1 / §12.2 改为已落地；`docs/00-index.md` §3.6 前端入口一行更新；`docs/07` §16.3 删掉对应条目。
- **诚实边界**：本单**不影响任何判定与分数**。若时间紧，**整单砍掉**（`§12.2` 明说 B 阶段是加分项）。

### 23.15 WO-15 · 稳定 ID 引用规范（W5，**必须独占全仓、单独一波**）

- **目标**：把"靠章节号不变维持的引用"换成稳定 ID（`R-` / `D-` / `A-` 编号），让以后拆文档 / 改章节不再断引用。
- **为什么**：`docs/00-index.md` §3.5 与 `§19.2` ㉑ 都记着这件事：代码里约 196 处指向**已删除**旧文档的引用、约 92 处跨文件 `§X.Y` 引用；
  `verify_docs.py` 的 D2 现在只统计不修，文档里写着"阶段 3 会换成稳定 ID"。
- **前置**：**全部功能工单做完**（它会重写几乎所有文档与代码注释）。
- **独占文件**：**全仓库**（尤其所有 `docs/**/*.md`、`README.md`、`engine/` 与 `backend/` 里的注释）。
- **必读**：`docs/00-index.md` §3.5、`§19.2` ㉑、`scripts/verify_docs.py` 的 D2 实现（它是这项检查的判据）。
- **判定口径与不变式**：
  - **不许重排章节号**（`§3.4` 明令；会断掉一大片引用，包括代码注释里的）；
  - 建立**映射表**：旧 `§X.Y` / `README5 §3.2` → 新的稳定 ID；映射表本身入库（否则下一次拆文档又会断）；
  - 替换要**分批 + 可回退**：文档一批、代码注释一批，每批跑一次门禁；
  - D2 改成认稳定 ID 之后，**悬空引用计数必须降到 0**（现在两类 WARN 都要消失）。
- **验收**：`python scripts/verify_docs.py` exit 0 且 D2 的 WARN 计数为 0；`python scripts/build_acceptance_report.py` 全绿；
  随机抽 10 处替换，逐条确认新 ID 指向的确实是原来那条事实。
- **集成轮待办**：`docs/00-index.md` §3.5"已知死指针"整节改写为"已换稳定 ID + 映射表位置"；`§19.2` ㉑ 的边界说明更新。
- **诚实边界**：这是**机械替换 + 人工核对**的活，**不要**顺手"改进"文档措辞 —— 本单只做引用形式的替换，
  文案改动会让 review 无法判断"这处是不是改错了"。

### 23.16 WO-90 · 集成轮（每一波之后，串行，**一条线**）

> 集成轮**不是**工单，是每波结束后的固定动作。它**是唯一**允许改 `docs/07`、`docs/08`、`README.md`、`docs/00-index.md`、
> `scripts/build_acceptance_report.py` 与重生成 `validation/acceptance_latest.*` 的环节。

**动作清单（按顺序做，不许跳）**：

1. **合并**该波全部分支（顺序 = 工单号升序），解决冲突；**禁止** force push、禁止覆盖别人的改动。
2. **接路由**：把各线新增的 router 一起 include 进 `backend/app/main.py`（`WO-02` 之后这一步是一行）。
3. **重跑数字来源**：`python scripts/build_acceptance_report.py` —— 这是**唯一**允许重生成 `validation/acceptance_latest.json` / `.md` 的地方。
4. **跑文档门禁**：`python scripts/verify_docs.py`，**必须 exit 0**（含 D7：把该波新增的 `docs/features/*.md` 登记进 `README.md` §0.4 与 `docs/00-index.md` 清单）。
5. **跑总验收**：`python scripts/verify_sprint0.py`（A1–A11 + 该波新增的 A1x），全绿。
6. **收「集成轮待办」**：逐条实现各线在交付说明里列出的待办（多数是文档同步）。
7. **登记新脚本**：`scripts/build_acceptance_report.py` 的脚本清单 + `docs/06` §20.1 + `docs/07` §17.2 + `README.md` §0.3 —— 四处都要有。
8. **同步状态表**：`docs/07` §16.1 / §16.2 / §16.3、`docs/08` §19.1 / §19.2 / §19.6、`README.md` §0.2 完成度表；
   若该波有阶段落地，**同时**改 `HomeView.vue` 的阶段状态表（两边必须同一轮改，`docs/features/ui-shell-redesign.md` §8 的要求）。
9. **重建单文件合集**：`python scripts/pack_docs.py` → `docs/_bundle.md`（机器产物，不许手改）。
10. **提交**并打标签（例如 `wave-1`）；下一波从新基线开分支。

**每波结束必须全绿的三条命令**（缺一条不算集成完成）：

```bash
python scripts/build_acceptance_report.py
python scripts/verify_docs.py
python scripts/verify_sprint0.py
```

---

## 二十四、发单方的验收办法与明确的"不派单"清单

### 24.1 怎么验一个 GPT 会话是真做完了（抽查三件）

| # | 抽查动作 | 不合格的样子 |
|---|---|---|
| 1 | 让它贴 `python scripts/verify_docs.py` 与 `python scripts/build_acceptance_report.py` 的**原始屏幕输出** | "已通过""应该没问题"；或只有结论没有输出 |
| 2 | 让它贴**负向对照的前后两次输出**（故意造失败 → 报错 → 改回 → 通过） | 只有正向输出；或说"这个检查很严格" |
| 3 | 随机挑它宣称"已实现"的一个字段，让它给出 `文件:行号`，你自己去看那一行 | 行号指不到东西（`verify_docs.py` 的 D6 就是查这个） |

**三条红旗**（出现任何一条，直接打回重做）：

- 只改了文档 / 只改了注释，产品代码没动；
- 把"算不出来"的维度填成了 0 或编了一个数字；
- **为了让断言通过而放宽断言**（`§19.4` 第 4 条：放宽断言比改文案危险得多）。

### 24.2 明确**不派给 AI**、或**当前环境做不到**的部分

| 项 | 为什么不派 / 为什么做不到 | 依据 |
|---|---|---|
| 人工核对业务图谱（域 + 功能点判定列）、《批量优先级复核表》 | **只能由人填**；而且已决定**延后到引擎冻结之后**（判定绑定 `source_hash`，现在填会被后续改动作废） | `§18` 优先级 2、`§19.6` 第 3 条 |
| 教师种子里 `must_have` / `objective` 的**最终确认** | `§9.1` 第 ③ 条：绝不许 LLM 生成后当评分基准（`WO-05` 只做候选备料） | `§9.1` |
| 像素级排版（谁更大 / 间距好不好看）、动画效果与方向时序 | jsdom 不走样式；本环境起不来无头 Chromium（命名管道被挡），**只能人眼看** | `docs/features/ui-shell-redesign.md` §7、`§19.5` |
| 低端机 / 移动端性能实测 | 没有设备，也没有可跑的浏览器环境 | 同上 |
| Skill 失效点报告里需要**外部 LLM 调用**的部分（一致性 / 批量一致性） | 引擎层本来就禁止网络调用；若无 API 就只能交付骨架并写"未实测" | `docs/02` §8.9、`docs/01` §1.2 |
| Java / JavaScript 支持 | **明确维持不做** | `§16.3` |
| `sample_projects/flask_crud_demo` 的源码 | 已丢失，只剩一个空的 `.git.bak`；只能做"决定不恢复" | `§19.6` 第 2 条 |
| `modules`（代码模块）与业务域的统一、两套调用图收敛 | **现在不要动**（`§16.4` 明写留给下一轮一并处理） | `§16.4` |

### 24.3 一句话总结怎么用

1. 先做 `WO-01`，把基线提交干净；
2. 按 `§22.6` 的波次表**一波一波开**，每波内部可以任意并行（遵守 `§22.5` 的文件独占）；
3. 每波收尾跑一次 `WO-90` 集成轮（串行，一条线）；
4. 每一单都用 `§22.7` 的模板发出去，收回来按 `§24.1` 抽查三件；
5. **`§18` 仍然是"下一步"的唯一权威** —— 本文只是它的执行分解，冲突时以 `§18` 为准。
