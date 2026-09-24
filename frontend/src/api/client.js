/**
 * P0-13 · 后端 API 客户端（薄封装，无第三方依赖）
 *
 * 约定（很重要）：
 *  1. 每个函数**永不抛异常**，统一返回 `{ ok: true, data }` 或 `{ ok: false, error }`。
 *     调用方（组件/store）因此不需要 try/catch，失败即"降级信号"，交给 dataSource 决定回落到快照。
 *  2. 每个请求都有超时（默认 4s，AbortController）。后端没启动时，浏览器会立刻 connection refused，
 *     后端卡住时则是 4s 超时——两种情况都会被归一成 `{ ok:false }`，UI 侧表现为进入离线演示模式。
 *  3. baseURL：优先 `import.meta.env.VITE_API_BASE`（生产/独立部署），否则同源 `/api`
 *     （开发环境由 vite.config.js 的 server.proxy 转发到 http://127.0.0.1:8000）。
 *
 * 已核实的契约（后端已实现，勿改）：
 *   GET  /api/health                                  → {status, version, contract_version}
 *   GET  /api/projects                                → {projects:[{project_id, project_name, contract_version, ...}]}
 *   GET  /api/projects/{id}/analysis?mode=student|teacher
 *        student 模式下 training.questions[*] 没有 correct_answers / explanation（P0-11）
 *   GET  /api/projects/{id}/business-graph            → 业务图谱本体（不含外包一层 business_graph）
 *   GET  /api/projects/{id}/business-graph/cards/{module_id} → 单张模块卡片
 *   GET  /api/projects/{id}/source?path=&start=&end=   → {file, resolved_file, total_lines, lines:[{number,text}]}
 *   POST /api/projects/{id}/checkpoints/{index}/answer  body {selected:["A","C"]}
 *        → {question_index, result:"correct|partial|wrong", matched, missing, extra, explanation, knowledge_points, question_type}
 *        正确答案本身永不下发。
 *   POST /api/projects/{id}/teaching/orientation/coverage body {text:"..."}
 *        → 阶段一覆盖度报告（covered/missed/not_comparable + counts + caveats，无分数字段）
 *   GET  /api/projects/{id}/teaching/module-card/task
 *        → 阶段二任务包（questions + cards，全部由 business_graph 派生；不下发任何比对键）
 *   POST /api/projects/{id}/teaching/module-card/coverage body {module_id, answers:{question_id: text}}
 *        → 阶段二事实覆盖报告（每个问题的 matched_keys/missed_keys + counts + caveats，无分数字段）
 *   GET  /api/projects/{id}/teaching/design/tasks
 *        → 阶段四设计任务清单（按复杂度级别给类型；不含必备能力全文与评分权重）
 *   GET  /api/projects/{id}/teaching/design/task?task_id=&mode=teacher|student
 *        → 一道设计任务（题干 + 需求简报）；mode=teacher 才下发 must_have / rubric_weights
 *   POST /api/projects/{id}/teaching/design/evaluate body {task_id, submission}
 *        → 阶段四/五的六维评审报告（算不出来的维度 status=not_evaluated 且 score=null）
 *
 * 业务逻辑分析平台（lp-1.0，见文件末尾那一节）：
 *   GET  /api/logic-platform/projects                  → {projects:[{project_id, project_name}]}
 *   GET  /api/logic-platform/narration-status          → {enabled, reason, config, caveats, ...}
 *   GET  /api/logic-platform/{id}/analysis             → 主载荷（size + tier + sections 看板）
 *   GET  /api/logic-platform/{id}/size|sections        → 主载荷的切片
 *   GET  /api/logic-platform/{id}/sections/{sid}       → 单个业务板块
 *   GET  /api/logic-platform/{id}/lessons[/{cap}]      → 课程索引 / 一课沉浸式讲稿
 *   POST /api/logic-platform/{id}/lessons/{cap}/verify → 重跑确定性校验
 *   POST /api/logic-platform/{id}/lessons/{cap}/narration → 可选 LLM 讲解（默认关闭，503）
 *   GET  /api/logic-platform/{id}/source?path=&start=&end= → 源码切片（与 /api/projects/{id}/source 同结构）
 *   POST /api/teacher/logic-platform/{id}/lessons/{cap}/review → 教师确认 / 拒绝
 *   POST /api/logic-platform/analyze（multipart，字段名 file）→ 与 analysis 同结构
 */

const DEFAULT_TIMEOUT_MS = 4000

// 解出 API 基地址：去掉结尾的 `/`，保证拼出来的是 `${base}/projects`。
const RAW_BASE = (import.meta.env && import.meta.env.VITE_API_BASE) || ''
export const API_BASE = String(RAW_BASE).replace(/\/+$/, '')
export const API_TIMEOUT_MS = DEFAULT_TIMEOUT_MS

function buildUrl(path) {
  return `${API_BASE}${path}`
}

/**
 * 统一的 fetch 封装：超时 + 错误归一化 + JSON 解析容错。
 * @returns {Promise<{ok:true,data:any}|{ok:false,error:string,status?:number}>}
 */
async function request(path, { method = 'GET', body = null, timeout = DEFAULT_TIMEOUT_MS } = {}) {
  const controller = new AbortController()
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeout)

  try {
    const resp = await fetch(buildUrl(path), {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    })

    // 后端用 HTTP 404 + JSON detail 表示"文件不存在/路径越界"，需要把 detail 带给 UI。
    if (!resp.ok) {
      let detail = ''
      try {
        const payload = await resp.json()
        detail = payload?.detail || ''
      } catch {
        /* 非 JSON 错误体：忽略，用状态码兜底 */
      }
      return { ok: false, error: detail || `HTTP ${resp.status}`, status: resp.status }
    }

    const data = await resp.json()
    return { ok: true, data }
  } catch (e) {
    if (timedOut) return { ok: false, error: `请求超时（${timeout}ms）` }
    return { ok: false, error: e?.message || '网络请求失败' }
  } finally {
    clearTimeout(timer)
  }
}

/** GET /api/health —— 双通道探测：能拿到 contract_version 才算"在线"。 */
export function getHealth(opts = {}) {
  return request('/api/health', opts)
}

/** GET /api/projects —— 项目列表，供项目切换器使用。 */
export function listProjects(opts = {}) {
  return request('/api/projects', opts)
}

/**
 * GET /api/projects/{id}/analysis
 * @param {string} projectId
 * @param {{mode?: 'student'|'teacher'}} [options] 默认 student（不下发答案，P0-11）
 */
export function getAnalysis(projectId, { mode = 'student', ...opts } = {}) {
  if (!projectId) return Promise.resolve({ ok: false, error: '缺少 project_id' })
  return request(`/api/projects/${encodeURIComponent(projectId)}/analysis?mode=${encodeURIComponent(mode)}`, opts)
}

/**
 * GET /api/projects/{id}/business-graph —— 业务图谱（Sprint 1 的产出，README5 §13.2）。
 * 注意：后端这个接口把图谱**摊平**返回（顶层就是 contract_version / domains / capabilities…），
 * 不套一层 `business_graph`；而静态快照里它是 `project_analysis.json` 的一个字段。
 * 这个差异由 dataSource.loadBusinessGraph() 统一抹平，调用方拿到的永远是图谱本体。
 */
export function getBusinessGraph(projectId, opts = {}) {
  if (!projectId) return Promise.resolve({ ok: false, error: '缺少 project_id' })
  return request(`/api/projects/${encodeURIComponent(projectId)}/business-graph`, opts)
}

/** GET /api/projects/{id}/business-graph/cards/{module_id} —— 单张业务模块卡片。 */
export function getModuleCard(projectId, moduleId, opts = {}) {
  if (!projectId || !moduleId) return Promise.resolve({ ok: false, error: '缺少 project_id 或 module_id' })
  return request(
    `/api/projects/${encodeURIComponent(projectId)}/business-graph/cards/${encodeURIComponent(moduleId)}`,
    opts,
  )
}

/**
 * GET /api/projects/{id}/source —— 按**项目内相对路径**取源码窗口。
 * @param {string} projectId
 * @param {string} path 项目内相对路径（POSIX `/`），例如 `reservation_manager.py`
 * @param {number} [start] 1-based 起始行
 * @param {number} [end]   1-based 结束行
 */
export function getSourceSlice(projectId, path, start, end, opts = {}) {
  if (!projectId || !path) return Promise.resolve({ ok: false, error: '缺少 project_id 或 path' })
  const qs = new URLSearchParams({ path: String(path) })
  if (Number.isFinite(start) && start > 0) qs.set('start', String(Math.floor(start)))
  if (Number.isFinite(end) && end > 0) qs.set('end', String(Math.floor(end)))
  return request(`/api/projects/${encodeURIComponent(projectId)}/source?${qs.toString()}`, opts)
}

/**
 * POST /api/projects/{id}/checkpoints/{index}/answer —— 唯一合法的判题通道（P0-11）。
 * 后端只回 result / matched / missing / extra / explanation，永不回正确答案。
 * @param {string} projectId
 * @param {number} index 题目下标（0-based）
 * @param {string[]} selected 选中的选项 id
 */
export function submitAnswer(projectId, index, selected, opts = {}) {
  if (!projectId || !Number.isInteger(index)) {
    return Promise.resolve({ ok: false, error: '缺少 project_id 或 question_index' })
  }
  return request(`/api/projects/${encodeURIComponent(projectId)}/checkpoints/${index}/answer`, {
    method: 'POST',
    body: { selected: Array.isArray(selected) ? selected : [selected] },
    ...opts,
  })
}

/**
 * POST /api/projects/{id}/teaching/orientation/coverage —— 阶段一「项目认知」覆盖度比对（Sprint 3）。
 *
 * 学生提交一段自由文本，后端用 **纯规则**（`engine/teaching/coverage.py`）算出
 * "回答里提到了哪些一级业务域、漏了哪些"，**不打分、不给标准答案**。
 *
 * 响应：`{report_version, algorithm_version, scoring:"coverage_only", has_score:false,
 *        counts, covered[], missed[], not_comparable[], supporting_domains[], caveats[]}`
 *
 * @param {string} projectId
 * @param {string} text 学生回答原文（空提交会被后端拒绝：400）
 */
export function evaluateOrientation(projectId, text, opts = {}) {
  if (!projectId) return Promise.resolve({ ok: false, error: '缺少 project_id' })
  return request(`/api/projects/${encodeURIComponent(projectId)}/teaching/orientation/coverage`, {
    method: 'POST',
    body: { text: String(text ?? '') },
    ...opts,
  })
}

/**
 * GET /api/projects/{id}/teaching/module-card/task —— 阶段二「模块卡片学习」的任务包（Sprint 4）。
 *
 * 返回五个问题（题目来自后端词典）+ 本项目全部模块卡片（来自 business_graph）。
 * **不含任何比对键**：学生提交之前，页面上不该出现比对的答案。
 *
 * @param {string} projectId
 */
export function getModuleCardTask(projectId, opts = {}) {
  if (!projectId) return Promise.resolve({ ok: false, error: '缺少 project_id' })
  return request(`/api/projects/${encodeURIComponent(projectId)}/teaching/module-card/task`, {
    method: 'GET',
    ...opts,
  })
}

/**
 * POST /api/projects/{id}/teaching/module-card/coverage —— 阶段二事实覆盖比对（Sprint 4）。
 *
 * 学生提交五个回答，后端用**纯规则**（`engine/teaching/card_coverage.py`）算出
 * 「每个问题提到了卡片上哪些已核实的事实、哪些没有」，**不打分**；
 * 置信度为 `unconfirmed` 的字段不参与比对，报告会提示「该卡片待教师确认」。
 *
 * 响应：`{report_version, algorithm_version, scoring:"fact_coverage_only", has_score:false,
 *        module, card_needs_review, unconfirmed_fields, counts, questions[], caveats[]}`
 *
 * @param {string} projectId
 * @param {string} moduleId 卡片 id（二级功能点或一级域）
 * @param {Record<string,string>} answers 问题标识 → 学生回答原文（空提交会被后端拒绝：400）
 */
export function evaluateModuleCard(projectId, moduleId, answers, opts = {}) {
  if (!projectId) return Promise.resolve({ ok: false, error: '缺少 project_id' })
  if (!moduleId) return Promise.resolve({ ok: false, error: '缺少 module_id' })
  return request(`/api/projects/${encodeURIComponent(projectId)}/teaching/module-card/coverage`, {
    method: 'POST',
    body: { module_id: String(moduleId), answers: answers && typeof answers === 'object' ? answers : {} },
    ...opts,
  })
}

/**
 * GET /api/projects/{id}/teaching/design/tasks —— 阶段四「设计画布」的任务清单（Sprint 5）。
 *
 * 按项目复杂度级别（L1–L4）给出可用任务类型；清单里**不含**必备能力全文与评分权重
 * （README §10.5 字段可见性矩阵：那两项只在教师视图 / 服务端存在）。
 *
 * @param {string} projectId
 */
export function getDesignTasks(projectId, opts = {}) {
  if (!projectId) return Promise.resolve({ ok: false, error: '缺少 project_id' })
  return request(`/api/projects/${encodeURIComponent(projectId)}/teaching/design/tasks`, {
    method: 'GET',
    ...opts,
  })
}

/**
 * GET /api/projects/{id}/teaching/design/task —— 取一道设计任务（Sprint 5）。
 *
 * 学生视图（默认）只给题干、场景、需求简报与「本次有几项必备能力」；
 * `mode='teacher'` 才返回完整版（含 `must_have` / `rubric_weights` / `required_relations` /
 * `forbidden_merges`）—— 与判题接口的 `?mode=teacher` 是同一条边界纪律。
 *
 * @param {string} projectId
 * @param {string} [taskId] 缺省时后端给默认任务；给了但不认识 → 404（不静默退回默认题）
 * @param {{mode?: 'student'|'teacher'}} [options]
 */
export function getDesignTask(projectId, taskId, { mode = 'student', ...opts } = {}) {
  if (!projectId) return Promise.resolve({ ok: false, error: '缺少 project_id' })
  const qs = new URLSearchParams({ mode: String(mode) })
  if (taskId) qs.set('task_id', String(taskId))
  return request(
    `/api/projects/${encodeURIComponent(projectId)}/teaching/design/task?${qs.toString()}`,
    { method: 'GET', ...opts },
  )
}

/**
 * POST /api/projects/{id}/teaching/design/evaluate —— 设计层六维评审（Sprint 5 / README §18 优先级 3）。
 *
 * 学生提交 `design_submission`（README §10.4 契约：modules / relations / flow_designs /
 * design_rationale），后端用**纯规则**（`engine/design/rubric.py`）算六维：
 * 覆盖度 / 职责清晰度 / 层级合理性 / 依赖完整性 / 异常边界 / 理由可核查性。
 *
 * **算不出来的维度返回 `status:"not_evaluated"` 且 `score: null`，不填 0**；
 * 反馈是「信号码 → 中文模板」的纯函数映射，每条都能追溯到触发它的结构信号。
 * 空画布会被后端拒绝（400）：空提交不是「0 分设计」。
 *
 * @param {string} projectId
 * @param {string} taskId 必须是存在且当前正在作答的那道题
 * @param {object} submission design_submission 对象
 */
export function evaluateDesign(projectId, taskId, submission, opts = {}) {
  if (!projectId) return Promise.resolve({ ok: false, error: '缺少 project_id' })
  if (!taskId) return Promise.resolve({ ok: false, error: '缺少 task_id' })
  return request(`/api/projects/${encodeURIComponent(projectId)}/teaching/design/evaluate`, {
    method: 'POST',
    body: { task_id: String(taskId), submission: submission && typeof submission === 'object' ? submission : {} },
    ...opts,
  })
}

// ===========================================================================
// 业务逻辑分析平台（lp-1.0）
// ===========================================================================
/**
 * 这一节有**两处刻意偏离**上面默认约定的地方，两处都有具体原因：
 *
 * 1. **超时不是 4s**。默认的 4s 是为"后端没起时尽快进入离线演示模式"设计的；
 *    本平台的分析要跑 AST 解析 → 业务图谱聚类 → 板块划分 → 课程预算裁剪，
 *    4s 会把一个正在正常工作（只是慢）的后端误判成"离线"。所以：
 *    分析类请求 30s，上传 120s。慢 ≠ 不可用，这两件事必须分开。
 *
 * 2. **上传必须手写 fetch**。`request()` 的实现里写死了
 *    `JSON.stringify(body)` + `Content-Type: application/json`，
 *    而 `POST /api/logic-platform/analyze` 收的是 `UploadFile`（multipart）。
 *    这里**刻意不设 Content-Type**：multipart 的 boundary 只能由浏览器生成，
 *    手写 'multipart/form-data' 会让后端收不到文件。错误归一化保持同一套纪律。
 */

/** 分析类请求的超时（见上面第 1 条）。 */
export const LOGIC_PLATFORM_TIMEOUT_MS = 30000
/** 上传 + 全量分析的超时（AST + 图谱 + 板块划分，实测单文件项目也要数秒）。 */
export const LOGIC_PLATFORM_UPLOAD_TIMEOUT_MS = 120000

/** 从错误响应里解出后端的 `detail`（FastAPI 的中文说明），拿不到就退回状态码。 */
async function unwrapErrorDetail(resp) {
  let detail = ''
  try {
    const payload = await resp.json()
    detail = payload?.detail || ''
  } catch {
    /* 非 JSON 错误体：忽略，用状态码兜底（与 request() 一致） */
  }
  return detail || `HTTP ${resp.status}`
}

/**
 * POST /api/logic-platform/analyze —— 上传一个项目（.py 单文件 / .zip 压缩包）。
 *
 * 与 `request()` 的差别只有两处（见本节开头的说明）：FormData + 长超时。
 * 返回契约与 `GET /{analysisId}/analysis` 完全一致（同一个 analysis 载荷）。
 *
 * @param {File|Blob} file 浏览器 File 对象（字段名固定为 `file`）
 * @param {{timeout?: number}} [options]
 * @returns {Promise<{ok:true,data:any}|{ok:false,error:string,status?:number}>}
 */
export async function uploadForLogicPlatform(file, { timeout = LOGIC_PLATFORM_UPLOAD_TIMEOUT_MS } = {}) {
  if (!file) return { ok: false, error: '没有收到文件' }

  const controller = new AbortController()
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeout)

  try {
    const form = new FormData()
    // 字段名必须叫 file：后端签名是 `file: UploadFile = File(...)`。
    form.append('file', file, file.name || 'upload.zip')

    const resp = await fetch(buildUrl('/api/logic-platform/analyze'), {
      method: 'POST',
      body: form,
      signal: controller.signal,
      // 这里**不写 headers**：让浏览器自己带 multipart boundary。
    })

    if (!resp.ok) {
      return { ok: false, error: await unwrapErrorDetail(resp), status: resp.status }
    }
    const data = await resp.json()
    return { ok: true, data }
  } catch (e) {
    if (timedOut) return { ok: false, error: `分析超时（${timeout}ms）：项目较大时后端需要更久，请稍后重试` }
    return { ok: false, error: e?.message || '网络请求失败' }
  } finally {
    clearTimeout(timer)
  }
}

/** GET /api/logic-platform/projects —— 可做平台分析的演示项目（后端扫描已有快照得出）。 */
export function getLogicPlatformProjects(opts = {}) {
  return request('/api/logic-platform/projects', opts)
}

/**
 * GET /api/logic-platform/narration-status —— 讲解层状态。
 *
 * 界面用它**如实**告诉评审"这个平台到底有没有用 AI"。默认 `enabled:false`
 * （确定性事实层与证据校验完全不依赖模型）。
 */
export function getLogicPlatformNarrationStatus(opts = {}) {
  return request('/api/logic-platform/narration-status', opts)
}

/**
 * GET /api/logic-platform/{analysisId}/analysis —— 主载荷。
 * @param {string} analysisId 演示项目 id（如 python_dotenv）或上传后得到的 lp_*
 * @param {{force?: boolean}} [options] force=true 时后端重算（默认读缓存）
 */
export function getLogicPlatformAnalysis(analysisId, { force = false, ...opts } = {}) {
  if (!analysisId) return Promise.resolve({ ok: false, error: '缺少 analysis_id' })
  const qs = force ? '?force=true' : ''
  return request(`/api/logic-platform/${encodeURIComponent(analysisId)}/analysis${qs}`, {
    timeout: LOGIC_PLATFORM_TIMEOUT_MS,
    ...opts,
  })
}

/** GET /api/logic-platform/{analysisId}/size —— 只有 size 对象（大小 + 分流策略）。 */
export function getLogicPlatformSize(analysisId, opts = {}) {
  if (!analysisId) return Promise.resolve({ ok: false, error: '缺少 analysis_id' })
  return request(`/api/logic-platform/${encodeURIComponent(analysisId)}/size`, {
    timeout: LOGIC_PLATFORM_TIMEOUT_MS,
    ...opts,
  })
}

/** GET /api/logic-platform/{analysisId}/sections —— 只有板块看板对象。 */
export function getLogicPlatformSections(analysisId, opts = {}) {
  if (!analysisId) return Promise.resolve({ ok: false, error: '缺少 analysis_id' })
  return request(`/api/logic-platform/${encodeURIComponent(analysisId)}/sections`, {
    timeout: LOGIC_PLATFORM_TIMEOUT_MS,
    ...opts,
  })
}

/** GET /api/logic-platform/{analysisId}/sections/{sectionId} —— 单个业务板块。 */
export function getLogicPlatformSection(analysisId, sectionId, opts = {}) {
  if (!analysisId) return Promise.resolve({ ok: false, error: '缺少 analysis_id' })
  if (!sectionId) return Promise.resolve({ ok: false, error: '缺少 section_id' })
  return request(
    `/api/logic-platform/${encodeURIComponent(analysisId)}/sections/${encodeURIComponent(sectionId)}`,
    { timeout: LOGIC_PLATFORM_TIMEOUT_MS, ...opts },
  )
}

/** GET /api/logic-platform/{analysisId}/lessons —— 已生成过的课程索引（哪些能力点有讲稿）。 */
export function getLogicPlatformLessons(analysisId, opts = {}) {
  if (!analysisId) return Promise.resolve({ ok: false, error: '缺少 analysis_id' })
  return request(`/api/logic-platform/${encodeURIComponent(analysisId)}/lessons`, {
    timeout: LOGIC_PLATFORM_TIMEOUT_MS,
    ...opts,
  })
}

/**
 * GET /api/logic-platform/{analysisId}/lessons/{capabilityId} —— 一课的沉浸式讲稿。
 *
 * 注意：能力点超出本级课程预算时后端回 **409**，detail 必须原样显示
 * （"这次没讲"是一个结论，不许吞掉）。
 *
 * @param {{regenerate?: boolean}} [options] regenerate=true 才重算（讲稿是确定性的）
 */
export function getLogicPlatformLesson(analysisId, capabilityId, { regenerate = false, ...opts } = {}) {
  if (!analysisId) return Promise.resolve({ ok: false, error: '缺少 analysis_id' })
  if (!capabilityId) return Promise.resolve({ ok: false, error: '缺少 capability_id' })
  const qs = regenerate ? '?regenerate=true' : ''
  return request(
    `/api/logic-platform/${encodeURIComponent(analysisId)}/lessons/${encodeURIComponent(capabilityId)}${qs}`,
    { timeout: LOGIC_PLATFORM_TIMEOUT_MS, ...opts },
  )
}

/**
 * POST /api/logic-platform/{analysisId}/lessons/{capabilityId}/verify
 * → `{lesson_id, capability_id, report, summary}`，**重新从磁盘读源码**逐字符比对。
 */
export function verifyLogicPlatformLesson(analysisId, capabilityId, opts = {}) {
  if (!analysisId) return Promise.resolve({ ok: false, error: '缺少 analysis_id' })
  if (!capabilityId) return Promise.resolve({ ok: false, error: '缺少 capability_id' })
  return request(
    `/api/logic-platform/${encodeURIComponent(analysisId)}/lessons/${encodeURIComponent(capabilityId)}/verify`,
    { method: 'POST', timeout: LOGIC_PLATFORM_TIMEOUT_MS, ...opts },
  )
}

/**
 * POST /api/logic-platform/{analysisId}/lessons/{capabilityId}/narration
 * 请求 LLM 润色讲解。**平台默认关闭**：未配置时后端回 503 + 中文原因，
 * 前端必须原样显示，不许伪装成"生成过了"。
 */
export function requestLogicPlatformNarration(analysisId, capabilityId, provider, opts = {}) {
  if (!analysisId) return Promise.resolve({ ok: false, error: '缺少 analysis_id' })
  if (!capabilityId) return Promise.resolve({ ok: false, error: '缺少 capability_id' })
  const body = provider ? { provider: String(provider) } : {}
  return request(
    `/api/logic-platform/${encodeURIComponent(analysisId)}/lessons/${encodeURIComponent(capabilityId)}/narration`,
    { method: 'POST', body, timeout: LOGIC_PLATFORM_TIMEOUT_MS, ...opts },
  )
}

/**
 * GET /api/logic-platform/{analysisId}/source —— 源码切片（证据跳转的落点）。
 * 返回结构与 `/api/projects/{id}/source` 一致，所以 SourceViewerModal 可以直接复用。
 */
export function getLogicPlatformSource(analysisId, path, start, end, opts = {}) {
  if (!analysisId || !path) return Promise.resolve({ ok: false, error: '缺少 analysis_id 或 path' })
  const qs = new URLSearchParams({ path: String(path) })
  if (Number.isFinite(start) && start > 0) qs.set('start', String(Math.floor(start)))
  if (Number.isFinite(end) && end > 0) qs.set('end', String(Math.floor(end)))
  return request(
    `/api/logic-platform/${encodeURIComponent(analysisId)}/source?${qs.toString()}`,
    { timeout: LOGIC_PLATFORM_TIMEOUT_MS, ...opts },
  )
}

/**
 * POST /api/teacher/logic-platform/{analysisId}/lessons/{capabilityId}/review —— 教师确认 / 拒绝。
 *
 * body 契约：`{status: 'confirmed'|'rejected'|'reset', reviewer, note, claims:{claimId:{decision,note}}}`
 * 审核记录绑定**当前 source_hash**：源码一变，这份审核就变 stale，
 * 系统不会沿用失效的审核结论（这正是这个接口存在的意义）。
 */
export function reviewLogicPlatformLesson(analysisId, capabilityId, payload, opts = {}) {
  if (!analysisId) return Promise.resolve({ ok: false, error: '缺少 analysis_id' })
  if (!capabilityId) return Promise.resolve({ ok: false, error: '缺少 capability_id' })
  const body = {
    status: String(payload?.status || ''),
    reviewer: String(payload?.reviewer || '教师'),
    note: String(payload?.note || ''),
    claims: payload?.claims && typeof payload.claims === 'object' ? payload.claims : {},
  }
  return request(
    `/api/teacher/logic-platform/${encodeURIComponent(analysisId)}/lessons/${encodeURIComponent(capabilityId)}/review`,
    { method: 'POST', body, timeout: LOGIC_PLATFORM_TIMEOUT_MS, ...opts },
  )
}
