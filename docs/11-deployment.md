# 部署说明（LearnWithAI）

> 更新触发：**启动方式 / 构建产物 / 端口 / 依赖 / 反向代理变了才动** | 上次更新：部署说明一轮（2026-09-26）
> 来源：`README.md` §0.3、`docs/06-runbook.md`（第二十章命令手册 + `§19.5` 环境约束）、`scripts/bootstrap.ps1`、
> `frontend/vite.config.js`、`frontend/src/api/client.js`、`backend/app/main.py`、`backend/app/services/project_store.py`
> **读它的时机**：要把项目装到一台新机器上 / 要在局域网里演示 / 要构建前端产物交给别人看 / 要判断"能不能扔到公网"。
> ⚠️ 这里只讲**怎么把已经能跑的东西装起来**：命令全表与排障见 `docs/06-runbook.md`，
> 现在做到哪一步见 `docs/07-status-and-acceptance.md` §16，实跑数字只认 `validation/acceptance_latest.md`（本文不手抄数字）。

---

## 二十五、部署说明

### 25.1 先看结论：现在支持哪些形态、哪些没做

| 部署形态 | 状态 | 依据 / 实测 |
|---|---|---|
| **A. 单机双进程**：后端 uvicorn + 前端 vite dev | ✅ 支持（默认路径） | `README.md` §0.3；部署说明一轮实测（见 §25.5） |
| **B. 前端静态产物 + 后端跨源直连** | ✅ 支持（本轮首次实测） | 构建成功、产物可被静态服务器送达、跨源请求被放行（见 §25.6） |
| 局域网内别的机器打开 | ⚠️ 可做，但**必须显式绑地址** | 前端 dev server 已经绑 `0.0.0.0`（`frontend/vite.config.js`）；后端启动命令默认只绑 `127.0.0.1`，要改 `--host 0.0.0.0` |
| 反向代理成同源单端口（nginx / Caddy） | ❌ 未做 | 仓库里没有任何反代配置文件；后端也**没有**把前端产物挂进来（`backend/app/main.py` 里没有 StaticFiles），所以同源只能靠外部反代自己配 |
| 容器化（Docker / docker-compose） | ❌ 未做 | 仓库里没有 Dockerfile，也没有 compose 文件 |
| HTTPS / 域名 / 真实账号体系 | ❌ 未做 | `backend/app/main.py` 模块头写着 no auth / no database / no task queue；登录是本地演示身份（`docs/features/login-and-quick-navigation.md`） |
| 进程守护 / 开机自启 / 多副本负载均衡 | ❌ 未做 | 没有 systemd / NSSM / supervisor 之类的配置，也没有共享存储层（见 §25.8） |
| **公网暴露** | ❌ **不要做** | 判题答案与教师接口都没有鉴权，理由与实测见 §25.10 |

> **一句话**：这是一个**单机部署的教学演示系统**。要上公网或多人同时用，先补鉴权、会话存储与反代（都还没做）。

### 25.2 拓扑与端口

```text
                     ┌──────────────────────────────┐
  浏览器 ───────────▶│ 前端（三选一）                │
                     │  ① vite dev   :5173（开发）   │
                     │  ② vite preview :4173（静态） │
                     │  ③ 任意静态服务器（托管 dist）│
                     └──────────────┬───────────────┘
                                    │ /api/*（① 走 proxy；② ③ 由 VITE_API_BASE 直连）
                                    ▼
                     ┌──────────────────────────────┐
                     │ 后端 FastAPI + uvicorn :8000  │
                     │  读：仓库内的快照与答案表      │
                     │  写：backend/data 下的产物     │
                     └──────────────────────────────┘
```

| 角色 | 启动方式 | 默认地址 | 说明 |
|---|---|---|---|
| 后端 | `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`（工作目录 `backend`） | `http://127.0.0.1:8000` | 判题 / 源码切片 / 业务图谱 / 教学阶段 / 业务逻辑分析平台都要它 |
| 前端（开发） | `npm run dev`（工作目录 `frontend`） | `http://127.0.0.1:5173` | `/api/*` 由 dev server 代理到后端（默认 `http://127.0.0.1:8000`），所以**同源**、不触发 CORS |
| 前端（静态产物） | `node node_modules/vite/bin/vite.js preview --port 4173` | `http://127.0.0.1:4173` | 只是把构建产物发出去；它**不代理** `/api`，跨源要靠构建时烘进去的 `VITE_API_BASE` |

⚠️ **后端不能只把 `backend/` 拷到别的机器上跑**：它按仓库目录定位数据 ——
`REPO_ROOT = Path(__file__).resolve().parents[3]`（`backend/app/services/project_store.py:42`），
再从 `frontend/public/demo` 读学生快照、从 `backend/data` 读答案表与平台项目。
**部署 = 部署整个仓库目录（去掉 `.venv`、`frontend/node_modules` 这些可再生的东西）。**

### 25.3 前置条件（作者本机实测值）

| 依赖 | 要求 | 实测 | 备注 |
|---|---|---|---|
| Python | 3.12（项目开发口径） | 3.12.0 | `scripts/bootstrap.ps1` 对低于 3.10 报"偏低"、低于 3.12 报"建议升级"，都是**警告不阻断**；找不到 python 才终止 |
| Node.js | 有即可（构建与 jsdom 走查要用） | 22.x | 没有 node 只影响前端：后端与 Python 脚本照常 |
| npm | 随 Node | 10.x | 装前端依赖用 |
| 操作系统 | Windows（脚本与文档目前都是 Windows 口径） | Windows + PowerShell 5.1 | macOS / Linux **没验过**：`bootstrap.ps1` 只有 PowerShell 版，命令要自己翻译（见 §25.13） |
| 磁盘 | 仓库 + 依赖 + 构建产物 | 前端产物约 4.89 MB（实测） | `frontend/node_modules` 与 `.venv` 是大头，都可再生 |

Python 依赖分两份：`requirements.txt`（引擎侧：astroid、radon）与
`backend/requirements.txt`（服务侧：fastapi、uvicorn[standard]、python-multipart）。**两份都要装**。

### 25.4 一次装齐：`scripts/bootstrap.ps1`

**新机器 / 刚克隆下来，第一步就跑它**（幂等、可重复跑、不硬编码本机路径）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1
```

它做四件事：① 前置检查 python / node / npm；② 建 `.venv` 并装两份 requirements；
③ 前端 `npm ci`（没有锁文件才回退 `npm install`）；④ 跑一次 `scripts/build_demo_snapshots.py`
（生成学生快照 + 后端答案表 + 证据源码副本）。

开关：

| 开关 | 作用 |
|---|---|
| （无） | 只装环境，不构建、不跑门禁 |
| `-Build` | 顺带构建前端产物：正式构建 + 走查 bundle（用的是 `node` 直调 vite 入口，绕开 `npm.ps1` 执行策略问题） |
| `-Verify` | 顺带跑三道门禁：`scripts/build_acceptance_report.py` / `scripts/verify_docs.py` / `scripts/verify_sprint0.py` |
| `-SkipFrontend` | 只装 Python 侧（不装 `frontend/node_modules`） |

```powershell
# 装齐 + 构建产物 + 跑门禁（演示机推荐这一条）
powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1 -Build -Verify

# ⚠️ 跑完先激活 .venv —— 之后所有 python 命令才是这个虚拟环境里的
.\.venv\Scripts\Activate.ps1
```

> 为什么依赖装进 `.venv` 而不装系统 python：作者本机两者恰好都装齐了，别人机器上不一定；
> 装进 `.venv` 才是"克隆下来就能重现"的做法（理由与实测见 `docs/06-runbook.md` §19.5）。

### 25.5 路径 A：单机双进程（默认；开发与答辩演示）

两个终端，各跑一个：

```powershell
# 终端 1 —— 后端（工作目录 backend）
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 终端 2 —— 前端（工作目录 frontend）
cd frontend
npm run dev            # → http://127.0.0.1:5173/
```

**本轮实测**（部署说明一轮，屏幕输出）：

```text
GET http://127.0.0.1:8000/api/health
→ {"status":"ok","version":"0.5.0","contract_version":"1.0"}
```

其他几个启动写法（都实测过，选一个用）：

```powershell
# 也支持从仓库根目录启动（模块名要带 backend. 前缀）
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# 让同一网段的其他机器能访问后端（配合防火墙放行 8000）
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

⚠️ **不要用 `python backend/app/main.py` 启动**：本轮实测它在仓库根目录直接报
`ModuleNotFoundError: No module named 'app'`（脚本里 `uvicorn.run("app.main:app", ...)` 那段
按"工作目录是 `backend/`"写的，见 `backend/app/main.py:782`）。要用必须先进 `backend/` 目录。
⚠️ **改了后端代码或 `engine/lexicon/*.json` 必须重启 uvicorn**：启动命令没有 `--reload`，
`load_lexicon()` 又是进程内缓存，不重启会表现成"新改动没生效"（`docs/06-runbook.md` §19.5）。

### 25.6 路径 B：前端静态产物 + 后端跨源直连（不跑 dev server）

**这一步部署说明一轮首次实测**（此前只验过走查 bundle，正式构建没验过）。

**① 构建产物**（在前端目录）：

```powershell
cd frontend

# 正式构建：产物进 frontend/dist（把 VITE_API_BASE 烘进 bundle）
$env:VITE_API_BASE = 'http://127.0.0.1:8000'
node node_modules/vite/bin/vite.js build

# 走查/自查 bundle（另一份产物，进 frontend/.smoke-dist，与正式构建互不覆盖）
node node_modules/vite/bin/vite.js build --config vite.smoke.config.js
```

**实测结果**：`2156 modules transformed`、`built in 11.27s`、退出码 0；
`frontend/dist` 合计 **4.89 MB**（含 `assets/`、`index.html`、以及从 `frontend/public/` 复制过来的 `demo/`，
所以**离线演示数据在静态产物里也在**）。

**② 静态服务器发送产物**（`vite preview` 只是其中一个选项，任何静态服务器都行）：

```powershell
# 在 frontend 目录
node node_modules/vite/bin/vite.js preview --port 4173 --strictPort

# 实测：GET http://127.0.0.1:4173/                       → 200，返回 index.html
#       GET http://127.0.0.1:4173/demo/project_analysis.json → 200，473914 字节（离线快照就位）
```

**③ 跨源必须被后端放行**（后端已经允许，但要知道为什么能通）：
后端 CORS 是 `allow_origins=["*"]` + `allow_credentials=True`（`backend/app/main.py:87`）。

```text
实测：GET http://127.0.0.1:8000/api/health  带上 Origin: http://127.0.0.1:4173
→ Access-Control-Allow-Origin: http://127.0.0.1:4173
→ Access-Control-Allow-Credentials: true
```

**⚠️ 三个必须知道的点**：

1. **`VITE_API_BASE` 是"构建时"烘进 bundle 的**，不是运行时读的 —— 换后端地址要**重新构建**
   （`frontend/src/api/client.js` 读的是 `import.meta.env.VITE_API_BASE`）。
   本轮实测：设了 `VITE_API_BASE=http://127.0.0.1:8000` 构建后，该字符串确实出现在 `frontend/dist/assets/` 的 JS 里。
2. **不设 `VITE_API_BASE` 时，产物走同源 `/api`** —— 也就是说它默认依赖"有一个反代把 `/api` 转到后端"。
   没有反代就会退化成**离线演示模式**（不是白屏，但判题、阶段二/四、覆盖报告都明确显示不可用，
   见 `README.md` §0.3 的离线/在线对照表）。
3. **后端不会托管前端产物**：`backend/app/main.py` 里没有 StaticFiles 挂载，
   "一个端口同时给页面和 API"这件事**本仓库没做**，要做得自己加反代。

### 25.7 装完之后怎么确认装对了（自检清单）

| 检查项 | 命令 / URL | 期望 |
|---|---|---|
| 后端活着 | `GET /api/health` | `{"status":"ok","version":"0.5.0","contract_version":"1.0"}`（本轮实测） |
| 演示项目在 | `GET /api/projects` | 2 个项目：`lab_safety_assistant`、`python_dotenv`，答案表与源码都在（本轮实测） |
| 平台项目在 | `GET /api/logic-platform/projects` | 同样是这 2 个（本轮实测） |
| 讲解层默认关 | `GET /api/logic-platform/narration-status` | `enabled: false`（未配 `LWAI_NARRATION_PROVIDER` → 纯确定性模式）（本轮实测） |
| 判题边界没被破坏 | 抓一下学生契约 | 学生视图里**没有** `correct_answers`；`?mode=teacher` 有（本轮实测，对照见 §25.10） |
| 静态产物能送出 | 静态服务器取 `/` 与 `/demo/project_analysis.json` | 都是 200（本轮实测） |
| 前端界面能开 | 浏览器打开前端地址 | 落在**系统主页面**（两大核心功能各占半屏），不是直接进训练页 —— ⚠️ **本轮没在真实浏览器里点过**，界面行为依据是项目已有的 jsdom 走查断言（`docs/07` §17.2） |
| 前后端真的接上了 | 前端里切一次项目 / 提交一次判题 | 不是"离线演示模式"横幅 —— 同上，**本轮只验到接口层，没做浏览器点击验证** |

**验收数字别抄本文**：跑 `python scripts/build_acceptance_report.py`，数字看 `validation/acceptance_latest.md`；
文档一致性由 `python scripts/verify_docs.py` 把关（exit 0 才算过）。

⚠️ **跑走查类验收时，8000 与 5173 必须同时在跑**：`scripts/browser_clickthrough.mjs` 的
`/demo/...` 请求走的是 **5173 的 dev server**（不是后端），默认 `--base http://127.0.0.1:5173`。
本轮实测：**只起后端、没起 dev server** 时，四条走查全部失败在
`waitFor 超时: 题目渲染`（在线 12/13、离线 13/14）—— 看起来像"前端坏了"，实际是 5173 没在听。
要跑完整验收组就写：
`python scripts/build_acceptance_report.py --with-backend --with-node`（两条都在线时才有意义）。

### 25.8 数据：部署时必须一起带上什么、运行时会写哪里

| 路径 | 读 / 写 | 内容 | 缺了会怎样 |
|---|---|---|---|
| `frontend/public/demo/` | 只读 | 默认演示项目的学生快照 + 证据源码副本 | 后端 `/api/projects` 少项目、判题与图谱都拿不到数据 |
| `backend/data/answer_keys/` | 只读 | 答案表（**唯一判题依据**，学生视图永不下发） | 判题不可用 |
| `backend/data/logic_platform/` 下两个 demo 项目 | 只读 | 业务逻辑分析平台的演示项目快照 | 平台页没有可分析项目 |
| `backend/data/logic_platform/lp_*` | **写** | 用户上传源码的副本 + 分析产物 | 每次上传都会新建目录；**不在 git 里**（涉及他人源码，见 `.gitignore`） |
| `backend/data/logic_platform/*/reviews.json` | **写** | 教师审核记录（绑定 `source_hash`） | 审核结论丢失 |

三条部署硬要求：

1. **运行账号必须对 `backend/data` 有写权限**（上传项目与审核记录都落在这里）；
2. **备份就备份 `backend/data`**（它是唯一"跑出来的、又不在 git 里"的东西；快照类数据都能用
   `python scripts/build_demo_snapshots.py` 再生）；
3. **`lp_*` 目录不要提交、也不要随手拷给别人** —— 那是用户上传的源码副本。

### 25.9 环境变量（全部可选，不设就是默认值）

| 变量 | 谁读 | 作用 | 不设时 |
|---|---|---|---|
| `VITE_API_BASE` | `frontend/src/api/client.js`（**构建时**） | 前端请求前缀，指向后端地址 | 走同源 `/api`（依赖反代） |
| `VITE_API_TARGET` | `frontend/vite.config.js`（dev 代理） | dev server 把 `/api` 代理到哪 | `http://127.0.0.1:8000` |
| `LWAI_NARRATION_PROVIDER` | `backend/app/services/narration_service.py` | 打开 LLM 讲解层（`openai-compatible`） | 关闭：平台以纯确定性模式运行（**默认**） |
| `LWAI_NARRATION_BASE_URL` | 同上 | 兼容 OpenAI 的接口地址 | 空 |
| `LWAI_NARRATION_API_KEY` | 同上 | 密钥 | 空（配了 provider 却没 key 会被判为不可用） |
| `LWAI_NARRATION_MODEL` | 同上 | 模型名 | `gpt-4o-mini` |
| `LWAI_NARRATION_TIMEOUT` | 同上 | 超时秒数 | 30 |

⚠️ **讲解层是可选加分项，不是部署必需**：它**默认关闭**，开着的时候必须如实说明
"这段讲解是模型生成的、判定仍然来自规则引擎"（`docs/05-logic-platform.md` §21.6 与 `docs/09` §21.8）。

### 25.10 安全边界：往局域网 / 公网部署之前必须读

| 事实 | 依据（实测） | 后果 |
|---|---|---|
| **接口层完全没有鉴权** | `backend/app/main.py` 模块头："no auth, no database, no task queue" | 谁能访问端口，谁就能用全部接口 |
| **`?mode=teacher` 会把答案下发** | 实测：`GET /api/projects/lab_safety_assistant/analysis?mode=teacher` 的响应里**有** `correct_answers`；同一个接口 `mode=student`（默认）响应里**没有** | 只要拿到 URL，任何人都能取走答案表 |
| 教师审核接口也没有鉴权 | `POST /api/teacher/logic-platform/.../review` 无任何凭据校验 | 任何人都能改"教师确认"状态 |
| 登录不是账号体系 | 用户名与登录状态只写 `localStorage['lwai.demo.user']`，密码**不发给后端** | 它只是一个演示入口，**不构成访问控制** |
| CORS 允许所有来源 | `allow_origins=["*"]` 且 `allow_credentials=True` | 任何网站都能在浏览器里调这个后端（跨源直连是"能用"的原因，也是"危险"的原因） |
| 数据目录无隔离 | 上传源码落在 `backend/data/logic_platform/lp_*`，多个使用者共用一个目录 | 多用户场景下**互相可见** |

**结论（部署建议，按可信度从高到低）**：

1. **只在本机**：`--host 127.0.0.1`（默认），最安全，演示够用；
2. **只在可信局域网、临时演示**：`--host 0.0.0.0` + 防火墙只放行需要的网段，
   并且**主动说明**"接口无鉴权、教师视图能取答案"——不要等别人发现；
3. **公网**：**现在不要做**。真要做，先补三件（都还没做）：接口鉴权与会话、教师接口的授权边界、
   反向代理 + HTTPS。**在此之前把答案表放到公网上，等于把评分依据公开。**

### 25.11 更新部署（改了东西之后要做什么）

| 改了什么 | 必须做什么 | 为什么 |
|---|---|---|
| 前端源码（`.vue` / `.js`） | 重新构建产物（§25.6 ①） | 静态产物与走查 bundle 都是**构建产物**，不重建就还在跑旧代码 |
| 后端代码（`backend/`） | **重启 uvicorn** | 启动命令没有 `--reload` |
| `engine/lexicon/*.json`（含教师种子） | **重启 uvicorn** | `load_lexicon()` 是进程内缓存 |
| 题目 / 演示数据 / 引擎口径 | 跑 `python scripts/build_demo_snapshots.py` | 答案表与题目按下标对应，改了题目必须重生成 |
| 依赖（两份 requirements 或 `package.json`） | 重跑 `scripts/bootstrap.ps1`（幂等） | `.venv` 与 `frontend/node_modules` 要跟上 |
| 只改文档 | 跑 `python scripts/verify_docs.py`（+ `python scripts/pack_docs.py` 重打包 `docs/_bundle.md`） | 文档门禁会核对路径 / 章节引用 / 版本号 / 数字 / 行号 |

### 25.12 部署相关的已知坑（都有实测记录，细节见手册）

| 现象 | 原因 / 绕法 |
|---|---|
| `npm` 报 `npm.ps1 cannot be loaded ... running scripts is disabled` | PowerShell 执行策略，与沙箱无关：改用 `npm.cmd`，或直接 `node node_modules/vite/bin/vite.js build` |
| 构建报 `spawn EPERM`（esbuild） | 受限（沙箱）会话里 esbuild 起不了子进程；放开进程权限的终端里重跑同一命令即可 |
| 端口被占（8000 / 5173 / 4173） | 先确认那个进程**确实是本项目的**，再决定重启；并发工作线场景下别误杀别人的服务。也可以显式给前端加 `VITE_API_TARGET` 指到别的后端端口 |
| 后端起了但"新接口 404、版本号还是旧的" | 8000 上跑着旧进程 —— 重启 uvicorn |
| 前端请求成功、脚本直发的请求 404 | dev server 的 `/api` 代理指向的还是旧端口：设 `VITE_API_TARGET` 指到新后端 |
| 静态产物打开是"离线演示模式" | 构建时没设 `VITE_API_BASE`，而同源 `/api` 又没人代理（§25.6 第 2 点） |
| `git` 报 `dubious ownership` 拒绝一切命令 | 每条命令带 `-c safe.directory=<仓库绝对路径>`，或一次性 `git config --global --add safe.directory <仓库绝对路径>` |
| 不要把原生程序输出接进 PowerShell 管道 | 受限模式下会报 `Access is denied`；要留档就写文件或交给后台任务 |

完整的沙箱与环境约束清单见 `docs/06-runbook.md` §19.5（**这是部署排障的第一份**）。

### 25.13 这一轮的实测口径与诚实边界

**实测过的（屏幕输出，不是推断）**：

- 后端按文档命令启动成功：`GET /api/health` 返回 `0.5.0`；`GET /api/projects` 两个项目、答案表与源码都在；
  `GET /api/logic-platform/projects` 两个项目；`narration-status` 为 `enabled: false`；
- 从仓库根目录启动（`backend.app.main:app`）**成功**；`python backend/app/main.py` **失败**（`ModuleNotFoundError: No module named 'app'`）；
- 前端**正式构建成功**（`2156 modules transformed`，11.27s，退出码 0）；产物合计 4.89 MB；
  `VITE_API_BASE` 确实被烘进 bundle；
- 静态服务器实测：`vite preview --port 4173` 下 `/` 返回 200、`/demo/project_analysis.json` 返回 200（473914 字节）；
- 跨源实测：带 `Origin` 的请求被回显 `Access-Control-Allow-Origin`；
- 判题边界实测：`mode=teacher` 有 `correct_answers`、默认 `mode=student` 没有；
- **反向对照（本轮真的踩到了）**：只起 8000、不起 5173 时，四条走查全部 FAIL 在
  `waitFor 超时: 题目渲染`；把 dev server 起回来之后同一条命令恢复通过 —— 这条负向对照说明
  "走查失败"与"前端代码有问题"不是一回事，先查 5173。

**明确没做 / 没验的**：

1. **没有在真实浏览器里点过前端**：本轮前端只验到"构建成功、产物能被静态服务器送出、跨源被放行"，
   界面行为（主页面、判题、阶段页）**没有做浏览器点击验证**，依据是项目已有的 jsdom 走查断言（`docs/07` §17.2）；
2. **没有验 macOS / Linux**：`bootstrap.ps1` 只有 PowerShell 版，Linux 上要手工建 `.venv`、装两份 requirements、`npm ci`、跑快照脚本，按 §25.4 的四步翻译；
3. **没有验真实反代**（nginx / Caddy 同源单端口）：仓库里没有配置，本文只说明"它没做"，没给经过验证的配置；
4. **没有验第二台机器或干净系统**（仍是同一台机器上的同一个 Python 与 Node，且 `.venv` 与 `frontend/node_modules` 本来就已经装好，
   所以"`bootstrap.ps1` 从零装一遍"这件事本轮**没有重新跑**，它的实测记录在克隆完整性一轮）；
5. **没有验 HTTPS / 域名 / 多副本**：都未实现；
6. **没有做压力与并发实测**：单进程 uvicorn、无共享存储，"多人同时用"**没有验证过**；
7. **没有验上传大项目**（平台上传走 AST 全量分析，耗时与内存没测）；
8. 本文引用的端口与命令**会在改动时漂移**：改端口、改构建方式、加反代之后，
   请按头部「更新触发」同步本文，并跑 `python scripts/verify_docs.py` 确认没有断链。
