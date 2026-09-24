/**
 * P0-13 · 双通道数据源（API 优先 / 静态快照回落）
 *
 * 为什么需要它：
 *   答辩/演示现场不一定能起后端（端口占用、防火墙、忘记启动）。README5 §2.1-6 要求"演示可复现、可降级"，
 *   所以前端必须有且只有一处知道"没有 API 时数据从哪来"——就是这里（以前 `/demo/...` 散落在 App.vue、
 *   TrainingView.vue、SourceViewerModal.vue 三处）。
 *
 * 通道约定：
 *   - `mode === 'api'`    ：探测到后端 /api/health 可用，所有数据走 FastAPI（判题、讲解可用）。
 *   - `mode === 'offline'`：后端不可用，回落静态快照（`frontend/public/demo/**`）。
 *     离线模式下**判题与讲解不可用**，UI 必须如实告知（"离线演示模式"），不许编造分数。
 *
 * 快照路径规则（两个 demo 项目已经在磁盘上，见任务说明）：
 *   lab_safety_assistant → /demo/project_analysis.json          + /demo/source/<rel>
 *   python_dotenv        → /demo/projects/python_dotenv/project_analysis.json
 *                                                               + /demo/projects/python_dotenv/source/<rel>
 *   为了不写死项目名，这里按"候选列表依次尝试"实现：先试 `/demo/projects/<id>/...`，再试 `/demo/...`。
 */
import { ref, readonly } from 'vue'
// 显式写 .js 后缀：Vite 两种写法都支持，但带后缀的模块能在纯 Node 下被直接 import，
// 便于对本模块的双通道逻辑做无浏览器验证。
import { getHealth, listProjects as apiListProjects, getAnalysis, getSourceSlice, submitAnswer as apiSubmitAnswer, getBusinessGraph as apiGetBusinessGraph, getModuleCard as apiGetModuleCard, evaluateOrientation as apiEvaluateOrientation, getModuleCardTask as apiGetModuleCardTask, evaluateModuleCard as apiEvaluateModuleCard, getDesignTasks as apiGetDesignTasks, getDesignTask as apiGetDesignTask, evaluateDesign as apiEvaluateDesign, getLogicPlatformProjects as apiGetLogicPlatformProjects, getLogicPlatformNarrationStatus as apiGetLogicPlatformNarrationStatus, getLogicPlatformAnalysis as apiGetLogicPlatformAnalysis, getLogicPlatformSize as apiGetLogicPlatformSize, getLogicPlatformSections as apiGetLogicPlatformSections, getLogicPlatformSection as apiGetLogicPlatformSection, getLogicPlatformLessons as apiGetLogicPlatformLessons, getLogicPlatformLesson as apiGetLogicPlatformLesson, verifyLogicPlatformLesson as apiVerifyLogicPlatformLesson, requestLogicPlatformNarration as apiRequestLogicPlatformNarration, getLogicPlatformSource as apiGetLogicPlatformSource, reviewLogicPlatformLesson as apiReviewLogicPlatformLesson, uploadForLogicPlatform as apiUploadForLogicPlatform } from './client.js'

// ---------------------------------------------------------------------------
// 1) 所有 `/demo/**` 字面量集中在这里（App.vue 的旧 demo 也不例外）
// ---------------------------------------------------------------------------

export const DEFAULT_PROJECT_ID = 'lab_safety_assistant'

/** 离线模式下项目切换器的静态列表（与 /demo 目录下真实存在的快照一一对应）。 */
export const DEMO_PROJECTS = [
  { project_id: 'lab_safety_assistant', project_name: 'lab_safety_assistant' },
  { project_id: 'python_dotenv', project_name: 'python_dotenv' },
]

/** 旧版 student_manager 函数级 demo 的两个静态文件（App.vue 的分析分支仍在使用，降级保留）。 */
export const LEGACY_DEMO_PATHS = {
  analysis: '/demo/analysis_output.json',
  code: '/demo/student_manager.py',
}

/** 快照候选路径（按优先级排列，第一个能解析且 project_id 匹配的胜出）。 */
export function snapshotCandidates(projectId) {
  const id = projectId || DEFAULT_PROJECT_ID
  return [
    `/demo/projects/${id}/project_analysis.json`,
    '/demo/project_analysis.json',
  ]
}

/** 离线源码候选路径（同样是"项目目录优先，扁平 demo 目录兜底"）。 */
export function offlineSourceCandidates(projectId, relPath) {
  const id = projectId || DEFAULT_PROJECT_ID
  const clean = String(relPath || '').replace(/^\/+/, '')
  return [
    `/demo/projects/${id}/source/${clean}`,
    `/demo/source/${clean}`,
  ]
}

// ---------------------------------------------------------------------------
// 2) 模块级响应式状态（单例，所有组件共享同一份 mode）
// ---------------------------------------------------------------------------

/** 'api' | 'offline' —— 初始按 offline 渲染，探测成功后切到 api。 */
const mode = ref('offline')
/** degraded = 当前处于降级（离线）状态，UI 据此显示横幅。 */
const degraded = ref(true)
/** 最近一次降级原因（给横幅/排查用，不展示技术细节也可以）。 */
const lastError = ref('')
/** 后端契约版本（来自 /api/health），用于会话失效判断的辅助信息。 */
const apiContractVersion = ref('')

function setApiMode(contractVersion = '') {
  mode.value = 'api'
  degraded.value = false
  lastError.value = ''
  if (contractVersion) apiContractVersion.value = contractVersion
}

function setOfflineMode(reason) {
  mode.value = 'offline'
  degraded.value = true
  lastError.value = reason || '后端不可用'
}

// ---------------------------------------------------------------------------
// 3) 静态文件读取小工具（带超时；离线路径也不允许无限等待）
// ---------------------------------------------------------------------------

const STATIC_TIMEOUT_MS = 4000

async function fetchTextWithTimeout(url, timeout = STATIC_TIMEOUT_MS) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)
  try {
    const resp = await fetch(url, { signal: controller.signal })
    if (!resp.ok) return { ok: false, error: `HTTP ${resp.status}`, status: resp.status }
    return { ok: true, data: await resp.text() }
  } catch (e) {
    return { ok: false, error: e?.message || '静态资源读取失败' }
  } finally {
    clearTimeout(timer)
  }
}

/**
 * 静态资源是不是"SPA 回落页"（HTML），而不是真正的内容。
 * 用于离线通道：dev server / 静态服务器常常对不存在的文件回 index.html + 200，
 * 必须把这种情况识别出来，否则会把 HTML 当成源码或当成快照。
 */
export function looksLikeHtml(text) {
  const head = String(text ?? '').slice(0, 200).trim().toLowerCase()
  return head.startsWith('<!doctype html') || head.startsWith('<html')
}

/**
 * 按窗口切分离线源码，模拟后端 `?start=&end=` 的"上下文窗口"语义
 * （后端 window_start/window_end 是 start-5 / end+5 的上下文，这里保持一致，弹窗渲染逻辑就能统一）。
 */
export function sliceSourceText(text, start, end) {
  const all = String(text ?? '').split('\n')
  const total = all.length
  const hasRange = Number.isFinite(start) && start > 0
  let from = 1
  let to = total
  if (hasRange) {
    const e = Number.isFinite(end) && end >= start ? end : start
    from = Math.max(1, Math.floor(start) - 5)
    to = Math.min(total, Math.floor(e) + 5)
  }
  const lines = []
  for (let n = from; n <= to; n++) lines.push({ number: n, text: all[n - 1] ?? '' })
  return {
    total_lines: total,
    window_start: from,
    window_end: to,
    lines,
  }
}

// ---------------------------------------------------------------------------
// 4) 对外接口
// ---------------------------------------------------------------------------

/**
 * 探测后端是否可用。可用 → mode='api'。
 * @returns {Promise<boolean>}
 */
export async function probeApi() {
  const res = await getHealth()
  if (res.ok && res.data?.status === 'ok') {
    setApiMode(res.data.contract_version || '')
    return true
  }
  setOfflineMode(res.ok ? '健康检查返回异常' : res.error)
  return false
}

/**
 * 列出可选项目：在线用 API，离线用静态列表。
 * @returns {Promise<{ok:true, data:{projects:Array, source:'api'|'offline'}}>}
 */
export async function listProjects() {
  const res = await apiListProjects()
  if (res.ok && Array.isArray(res.data?.projects)) {
    setApiMode()
    return { ok: true, data: { projects: res.data.projects, source: 'api' } }
  }
  setOfflineMode(res.error)
  return { ok: true, data: { projects: DEMO_PROJECTS, source: 'offline' }, error: res.error }
}

/**
 * 加载完整分析契约（student 模式，P0-11：不下发答案）。
 * 先试 API；失败后依次试静态快照候选路径，并且**校验 project_id 一致**（避免加载到别的项目）。
 * @returns {Promise<{ok:boolean, data?:object, source?:'api'|'offline', error?:string}>}
 */
export async function loadContract(projectId) {
  const id = projectId || DEFAULT_PROJECT_ID

  const res = await getAnalysis(id, { mode: 'student' })
  // 后端明确回 404（项目不存在）时也回落快照：离线包里有这个项目就照样能演示。
  if (res.ok && res.data) {
    setApiMode(res.data.contract_version || '')
    return { ok: true, data: res.data, source: 'api' }
  }

  const reason = res.error || 'API 不可用'
  let lastErr = reason
  for (const url of snapshotCandidates(id)) {
    const snap = await fetchTextWithTimeout(url)
    if (!snap.ok) {
      lastErr = snap.error
      continue
    }
    // 静态服务器常对"文件不存在"回 200 + index.html；这种情况要认出来，否则报错原因会误导成"不是合法 JSON"
    if (looksLikeHtml(snap.data)) {
      lastErr = `${url} 不存在（静态服务器回的是 HTML 回落页）`
      continue
    }
    let parsed = null
    try {
      parsed = JSON.parse(snap.data)
    } catch {
      lastErr = `${url} 不是合法 JSON`
      continue
    }
    // 关键校验：快照必须就是所选项目，否则宁可报错也不显示错项目的内容。
    if (parsed?.project_id && parsed.project_id !== id) {
      lastErr = `${url} 的 project_id=${parsed.project_id} 与所选项目不一致`
      continue
    }
    setOfflineMode(reason)
    return { ok: true, data: parsed, source: 'offline', error: reason }
  }

  setOfflineMode(reason)
  return { ok: false, error: `${reason}；静态快照也不可用（${lastErr}）` }
}

/**
 * 取业务图谱（Sprint 2 新增）。
 *
 * 通道规则与 loadContract 完全一致，但有两个**契约差异**必须在这里抹平：
 *   1. 后端 `GET /api/projects/{id}/business-graph` 把图谱**摊平**返回（顶层就是 domains/capabilities…）；
 *      静态快照里它挂在 `project_analysis.json` 的 `business_graph` 字段下。
 *   2. 旧快照（Sprint 1 之前生成的）根本没有这个字段 —— 这时必须**如实报错**，
 *      不能让 UI 渲染一个空图谱假装"这个项目没有业务模块"。
 *
 * @returns {Promise<{ok:boolean, data?:object, source?:'api'|'offline', error?:string}>}
 */
export async function loadBusinessGraph(projectId) {
  const id = projectId || DEFAULT_PROJECT_ID

  const res = await apiGetBusinessGraph(id)
  if (res.ok && res.data) {
    const graph = res.data.business_graph || res.data
    setApiMode(graph.contract_version || '')
    return { ok: true, data: graph, source: 'api' }
  }

  const reason = res.error || 'API 不可用'
  let lastErr = reason
  for (const url of snapshotCandidates(id)) {
    const snap = await fetchTextWithTimeout(url)
    if (!snap.ok) {
      lastErr = snap.error
      continue
    }
    if (looksLikeHtml(snap.data)) {
      lastErr = `${url} 不存在（静态服务器回的是 HTML 回落页）`
      continue
    }
    let parsed = null
    try {
      parsed = JSON.parse(snap.data)
    } catch {
      lastErr = `${url} 不是合法 JSON`
      continue
    }
    // 与 loadContract 同样的项目一致性校验：宁可报错也不显示别的项目的图谱
    if (parsed?.project_id && parsed.project_id !== id) {
      lastErr = `${url} 的 project_id=${parsed.project_id} 与所选项目不一致`
      continue
    }
    if (!parsed?.business_graph) {
      lastErr = `${url} 里没有 business_graph 字段（Sprint 1 之前的旧快照）`
      continue
    }
    setOfflineMode(reason)
    return { ok: true, data: parsed.business_graph, source: 'offline', error: reason }
  }

  setOfflineMode(reason)
  return { ok: false, error: `${reason}；静态快照也不可用（${lastErr}）` }
}

/**
 * 取单张模块卡片（Sprint 2 新增）。
 *
 * 正常情况下卡片就在图谱的 `module_cards[id]` 里（BusinessGraphView 直接用那份，零请求）；
 * 这个函数是**兜底通道**：图谱里缺这张卡片时问后端 `/business-graph/cards/{module_id}`。
 *
 * 注意这里**不按 mode 预判**：卡片接口本来就只有后端有，先发请求再判结果，
 * 才不会因为"会话当前处于离线标记"而把一个可达的后端当成不可达（实测踩过：契约 404 会让
 * 整个数据源被标成 offline，于是这里的兜底通道被无谓地关掉了）。
 * 只有**网络层失败**（超时/连接被拒）才回落到"离线演示模式"的措辞；后端明确 404 时如实报错。
 */
export async function loadModuleCard(projectId, moduleId) {
  if (!moduleId) return { ok: false, error: '缺少 module_id' }
  const res = await apiGetModuleCard(projectId || DEFAULT_PROJECT_ID, moduleId)
  if (res.ok && res.data) {
    setApiMode(res.data.contract_version || '')
    return { ok: true, data: res.data.business_graph_card || res.data.card || res.data, source: 'api' }
  }
  if (res.status === 404 || res.status === 400) {
    return { ok: false, error: res.error || `图谱里没有模块 ${moduleId}` }
  }
  setOfflineMode(res.error)
  return { ok: false, error: `后端不可用（离线演示模式）：${res.error || '模块卡片请求失败'}` }
}

/**
 * 取源码窗口。API 模式走后端（服务端已做上下文切分），离线模式读静态源码文件并在前端切分。
 * 失败时返回明确错误，调用方必须显式展示（P0-09：不许静默渲染空白）。
 * @returns {Promise<{ok:boolean, data?:object, source?:string, error?:string}>}
 */
export async function getSource(projectId, path, start, end) {
  if (!path) return { ok: false, error: '缺少文件路径' }

  if (mode.value === 'api') {
    const res = await getSourceSlice(projectId, path, start, end)
    if (res.ok && res.data) {
      return { ok: true, data: { ...res.data, display_path: path }, source: 'api' }
    }
    // 后端 404（文件缺失/越界）时不要偷偷换源，直接如实报错。
    if (res.status === 404) {
      return { ok: false, error: res.error || `项目中找不到该文件：${path}` }
    }
    setOfflineMode(res.error)
  }

  let lastErr = ''
  for (const url of offlineSourceCandidates(projectId, path)) {
    const r = await fetchTextWithTimeout(url)
    if (!r.ok) {
      lastErr = r.error
      continue
    }
    /*
     * 关键判据（实测踩到过）：
     *   Vite dev server 对**不存在的路径**会回 200 + index.html（SPA 回落），而不是 404。
     *   于是"候选 1 = /demo/projects/<id>/source/<path>"这种多半不存在的路径会拿到 526 字节的
     *   HTML（17 行），前端却当成源码窗口切出来 → 弹窗显示"该文件没有可显示的内容"，
     *   学生以为"项目没提供源码"。（离线跳转 lab_safety_assistant 时 100% 复现。）
     *   所以拿到 HTML 就当作"这条候选没有命中"，继续试下一条。
     */
    if (looksLikeHtml(r.data)) {
      lastErr = `${url} 返回的是 HTML 回落页，不是源码`
      continue
    }
    const sliced = sliceSourceText(r.data, start, end)
    return {
      ok: true,
      data: {
        file: path,
        display_path: path,
        resolved_file: url,
        ...sliced,
      },
      source: 'offline',
    }
  }
  setOfflineMode(lastErr)
  return { ok: false, error: '该项目未提供源码，无法跳转' }
}

/**
 * 提交答案判分（P0-11：正确答案只在后端）。
 * 离线模式**不判分**——返回 ok:false + offline:true，由 UI 显示"离线演示模式：无法判分"。
 * @returns {Promise<{ok:boolean, data?:object, offline?:boolean, error?:string}>}
 */
export async function submitAnswer(projectId, index, selected) {
  if (mode.value !== 'api') {
    return { ok: false, offline: true, error: '离线演示模式：无法判分' }
  }
  const res = await apiSubmitAnswer(projectId, index, selected)
  if (res.ok && res.data) return { ok: true, data: res.data }
  if (res.status === 404 || res.status === 400) {
    // 后端明确拒绝：这是真错误，不要伪装成"离线"。
    return { ok: false, error: res.error || '判题请求被后端拒绝' }
  }
  setOfflineMode(res.error)
  return { ok: false, offline: true, error: '离线演示模式：无法判分' }
}

/**
 * 阶段一「项目认知」覆盖度比对（Sprint 3）。
 *
 * **只走在线通道**，理由与判题一致（README5 §10.3 的边界纪律 + P0-11）：
 * 判定口径必须只有一份实现（`engine/teaching/coverage.py`），前端不自己算一份，
 * 所以离线时**如实说不可用**，而不是编一个覆盖清单出来。
 *
 * 错误分级（与 submitAnswer 一致）：
 *   - 离线（mode !== 'api'）→ `{ok:false, offline:true}`，UI 显示"离线演示模式：覆盖度报告不可用"；
 *   - 后端明确 400/404（空提交、超长、项目缺图谱）→ `{ok:false}` + 后端原文，**不伪装成离线**；
 *   - 网络层失败 → 标 offline 并回落措辞。
 *
 * @returns {Promise<{ok:boolean, data?:object, offline?:boolean, error?:string}>}
 */
export async function evaluateOrientationCoverage(projectId, text) {
  if (mode.value !== 'api') {
    return { ok: false, offline: true, error: '离线演示模式：覆盖度报告不可用（规则比对在后端执行）' }
  }
  const res = await apiEvaluateOrientation(projectId, text)
  if (res.ok && res.data) return { ok: true, data: res.data }
  if (res.status === 400 || res.status === 404) {
    return { ok: false, error: res.error || '覆盖度比对请求被后端拒绝' }
  }
  setOfflineMode(res.error)
  return { ok: false, offline: true, error: '离线演示模式：覆盖度报告不可用（规则比对在后端执行）' }
}

/**
 * 旧版（student_manager 函数级）demo 的静态数据。App.vue 的"分析详情"分支使用。
 * 放在这里是为了让全仓库只有这一个文件知道 `/demo/...` 的具体文件名。
 * @returns {Promise<{ok:boolean, data?:{analysis:object, code:string}, error?:string}>}
 */
export async function loadLegacyDemo() {
  const [dataRes, codeRes] = await Promise.all([
    fetchTextWithTimeout(LEGACY_DEMO_PATHS.analysis),
    fetchTextWithTimeout(LEGACY_DEMO_PATHS.code),
  ])
  if (!dataRes.ok || !codeRes.ok) {
    return { ok: false, error: '旧版演示数据不可用' }
  }
  try {
    return { ok: true, data: { analysis: JSON.parse(dataRes.data), code: codeRes.data } }
  } catch (e) {
    return { ok: false, error: `旧版演示数据解析失败：${e?.message || e}` }
  }
}

/**
 * 阶段二「模块卡片学习」的任务包（Sprint 4）。
 *
 * **只走在线通道**，理由与阶段一 / 判题完全一致：题目文本与「问题 → 参与比对的字段」映射
 * 都存在后端（`engine/lexicon/stage_questions.json` + `business_graph`）。
 * 离线时**如实说不可用**，而不是在前端写死一套题目 —— 那样"换项目不改代码"就不成立了。
 *
 * @returns {Promise<{ok:boolean, data?:object, offline?:boolean, error?:string}>}
 */
export async function loadModuleCardTask(projectId) {
  if (mode.value !== 'api') {
    return { ok: false, offline: true, error: '离线演示模式：模块卡片任务不可用（题目由后端从业务图谱派生）' }
  }
  const res = await apiGetModuleCardTask(projectId)
  if (res.ok && res.data) return { ok: true, data: res.data }
  if (res.status === 400 || res.status === 404) {
    return { ok: false, error: res.error || '后端拒绝了任务请求' }
  }
  setOfflineMode(res.error)
  return { ok: false, offline: true, error: '离线演示模式：模块卡片任务不可用（题目由后端从业务图谱派生）' }
}

/**
 * 阶段二事实覆盖比对（Sprint 4）。
 *
 * 与阶段一同样的错误分级：
 *   - 离线 → `{ok:false, offline:true}`，UI 显示"离线演示模式：事实覆盖报告不可用"；
 *   - 后端明确 400/404（空提交 / 未知问题标识 / 卡片不存在）→ `{ok:false}` + 后端原文，
 *     **不伪装成离线**；
 *   - 网络层失败 → 标 offline 并回落措辞。
 *
 * @returns {Promise<{ok:boolean, data?:object, offline?:boolean, error?:string}>}
 */
export async function evaluateModuleCardCoverage(projectId, moduleId, answers) {
  if (mode.value !== 'api') {
    return { ok: false, offline: true, error: '离线演示模式：事实覆盖报告不可用（规则比对在后端执行）' }
  }
  const res = await apiEvaluateModuleCard(projectId, moduleId, answers)
  if (res.ok && res.data) return { ok: true, data: res.data }
  if (res.status === 400 || res.status === 404) {
    return { ok: false, error: res.error || '事实覆盖比对请求被后端拒绝' }
  }
  setOfflineMode(res.error)
  return { ok: false, offline: true, error: '离线演示模式：事实覆盖报告不可用（规则比对在后端执行）' }
}

/**
 * 阶段四「设计画布」（Sprint 5 / README §18 优先级 3）：任务清单 / 取题 / 评审。
 *
 * **三个都只走在线通道**，理由与阶段一 / 二完全一致：
 *   - 题干、需求简报、必备能力清单、六维评审全部由后端从业务图谱与词典派生
 *     （`engine/design/` 是纯函数、确定性、无 LLM），前端**不自己算一份**；
 *   - 离线时如实说「设计任务不可用」，而不是在前端写死题干 —— 那样"换项目不改代码"就不成立了。
 *
 * 画布本身（拖节点、连线）是**学生的输入**，不是判定，所以它在离线时也能画；
 * 但离线时拿不到题干、提交后也拿不到评审，UI 必须明说（不许编分数）。
 */

/**
 * 设计任务清单（按项目复杂度级别给类型）。
 * @returns {Promise<{ok:boolean, data?:object, offline?:boolean, error?:string}>}
 */
export async function listDesignTasks(projectId) {
  if (mode.value !== 'api') {
    return { ok: false, offline: true, error: '离线演示模式：设计任务不可用（任务由后端从业务图谱派生）' }
  }
  const res = await apiGetDesignTasks(projectId)
  if (res.ok && res.data) return { ok: true, data: res.data }
  if (res.status === 400 || res.status === 404) {
    return { ok: false, error: res.error || '后端拒绝了设计任务清单请求' }
  }
  setOfflineMode(res.error)
  return { ok: false, offline: true, error: '离线演示模式：设计任务不可用（任务由后端从业务图谱派生）' }
}

/**
 * 取一道设计任务（学生视图）。
 * @param {string} projectId
 * @param {string} [taskId]
 * @returns {Promise<{ok:boolean, data?:object, offline?:boolean, error?:string}>}
 */
export async function loadDesignTask(projectId, taskId) {
  if (mode.value !== 'api') {
    return { ok: false, offline: true, error: '离线演示模式：设计任务不可用（题干与需求简报由后端下发）' }
  }
  const res = await apiGetDesignTask(projectId, taskId)
  if (res.ok && res.data) return { ok: true, data: res.data }
  if (res.status === 400 || res.status === 404) {
    return { ok: false, error: res.error || '后端拒绝了设计任务请求' }
  }
  setOfflineMode(res.error)
  return { ok: false, offline: true, error: '离线演示模式：设计任务不可用（题干与需求简报由后端下发）' }
}

/**
 * 提交设计并取六维评审报告。
 *
 * 错误分级（与阶段一 / 二一致）：
 *   - 离线 → `{ok:false, offline:true}`（"离线演示模式：评审不可用"）；
 *   - 后端明确 400/404（空画布、未命名模块、任务不存在）→ `{ok:false}` + 后端原文，
 *     **不伪装成离线**；
 *   - 网络层失败 → 标 offline 并回落措辞。
 *
 * @returns {Promise<{ok:boolean, data?:object, offline?:boolean, error?:string}>}
 */
export async function evaluateDesignSubmission(projectId, taskId, submission) {
  if (mode.value !== 'api') {
    return { ok: false, offline: true, error: '离线演示模式：六维评审不可用（判定在后端执行）' }
  }
  const res = await apiEvaluateDesign(projectId, taskId, submission)
  if (res.ok && res.data) return { ok: true, data: res.data }
  if (res.status === 400 || res.status === 404) {
    return { ok: false, error: res.error || '设计评审请求被后端拒绝' }
  }
  setOfflineMode(res.error)
  return { ok: false, offline: true, error: '离线演示模式：六维评审不可用（判定在后端执行）' }
}

// ---------------------------------------------------------------------------
// 5.5) 业务逻辑分析平台（lp-1.0）—— 三个通道的纪律与上面完全一致
// ---------------------------------------------------------------------------
/**
 * 为什么这一组**没有离线回落**：
 *   大小分析、板块划分、课程生成、证据校验**全部在后端执行**（AST + 规则引擎）。
 *   静态快照里只有 business_graph，没有 lp-1.0 的 size / tier / sections / lessons 载荷，
 *   所以离线时唯一诚实的做法是**说不可用**，而不是在前端临时拼一份看板出来
 *   （那会造出第二套口径，而"把推断说成事实"正是这个项目的红线）。
 *
 * 错误分级（与 submitAnswer / evaluateOrientationCoverage 逐条一致）：
 *   - 离线（mode !== 'api'）→ `{ok:false, offline:true, error:'离线演示模式：…'}`；
 *   - 后端明确 400/404/409/410/503 → `{ok:false, error:<detail>}`，**不带 offline 标记**：
 *     这是真错误（能力点超出本级课程预算、文件不存在、路径越界、讲解层未启用），
 *     必须把后端的中文原文交给界面显示；
 *   - 网络层失败 → `setOfflineMode(res.error)` 之后返回带 offline 标记的措辞。
 */
const LP_EXPLICIT_STATUSES = [400, 404, 409, 410, 503]

function lpOffline(error) {
  return { ok: false, offline: true, error }
}

/** 分析类请求统一的"离线"文案（点明"在后端执行"这个原因，不含糊）。 */
const LP_OFFLINE_MSG = {
  projects: '离线演示模式：演示项目列表不可用（列表由后端扫描已有快照得出）',
  analysis: '离线演示模式：项目大小与业务板块不可用（AST 分析与板块划分在后端执行）',
  size: '离线演示模式：大小分析不可用（定级与分流策略由后端计算）',
  sections: '离线演示模式：业务板块看板不可用（板块划分在后端执行）',
  section: '离线演示模式：板块分析不可用（板块划分在后端执行）',
  lessons: '离线演示模式：课程索引不可用（讲稿由后端生成）',
  lesson: '离线演示模式：沉浸式讲稿不可用（讲稿与校验都在后端生成）',
  verify: '离线演示模式：重新校验不可用（校验要重新读后端磁盘上的源码）',
  narration: '离线演示模式：AI 讲解不可用（讲解层在后端，且默认关闭）',
  review: '离线演示模式：教师审核不可用（审核记录写在后端）',
  upload: '离线演示模式：项目分析不可用（AST 分析在后端执行，浏览器里不另算一份）',
}

/**
 * 逻辑平台的可选项目列表。
 * @returns {Promise<{ok:boolean, data?:object, offline?:boolean, error?:string}>}
 */
export async function listLogicPlatformProjects() {
  if (mode.value !== 'api') return lpOffline(LP_OFFLINE_MSG.projects)
  const res = await apiGetLogicPlatformProjects()
  if (res.ok && res.data) return { ok: true, data: res.data, source: 'api' }
  if (LP_EXPLICIT_STATUSES.includes(res.status)) return { ok: false, error: res.error || '后端拒绝了项目列表请求' }
  setOfflineMode(res.error)
  return lpOffline(LP_OFFLINE_MSG.projects)
}

/**
 * 讲解层状态（这个平台有没有用 AI）。它本身只是一个状态查询，但同样只走在线通道。
 * @returns {Promise<{ok:boolean, data?:object, offline?:boolean, error?:string}>}
 */
export async function loadLogicPlatformNarrationStatus() {
  if (mode.value !== 'api') return lpOffline('离线演示模式：讲解层状态未知（状态由后端上报）')
  const res = await apiGetLogicPlatformNarrationStatus()
  if (res.ok && res.data) return { ok: true, data: res.data, source: 'api' }
  if (LP_EXPLICIT_STATUSES.includes(res.status)) return { ok: false, error: res.error || '后端拒绝了讲解层状态请求' }
  setOfflineMode(res.error)
  return lpOffline('离线演示模式：讲解层状态未知（状态由后端上报）')
}

/**
 * 项目主载荷：大小分级 + 分流策略 + 业务板块看板。
 * @param {string} analysisId 演示项目 id 或上传得到的 lp_*
 * @param {{force?: boolean}} [options]
 */
export async function loadLogicPlatformAnalysis(analysisId, { force = false } = {}) {
  if (!analysisId) return { ok: false, error: '缺少 analysis_id' }
  if (mode.value !== 'api') return lpOffline(LP_OFFLINE_MSG.analysis)
  const res = await apiGetLogicPlatformAnalysis(analysisId, { force })
  if (res.ok && res.data) return { ok: true, data: res.data, source: 'api' }
  if (LP_EXPLICIT_STATUSES.includes(res.status)) return { ok: false, error: res.error || '后端拒绝了分析请求' }
  setOfflineMode(res.error)
  return lpOffline(LP_OFFLINE_MSG.analysis)
}

/** 只有 size 对象（大小 + 分流策略）。 */
export async function loadLogicPlatformSize(analysisId) {
  if (!analysisId) return { ok: false, error: '缺少 analysis_id' }
  if (mode.value !== 'api') return lpOffline(LP_OFFLINE_MSG.size)
  const res = await apiGetLogicPlatformSize(analysisId)
  if (res.ok && res.data) return { ok: true, data: res.data, source: 'api' }
  if (LP_EXPLICIT_STATUSES.includes(res.status)) return { ok: false, error: res.error || '后端拒绝了大小分析请求' }
  setOfflineMode(res.error)
  return lpOffline(LP_OFFLINE_MSG.size)
}

/** 只有板块看板对象。 */
export async function loadLogicPlatformSections(analysisId) {
  if (!analysisId) return { ok: false, error: '缺少 analysis_id' }
  if (mode.value !== 'api') return lpOffline(LP_OFFLINE_MSG.sections)
  const res = await apiGetLogicPlatformSections(analysisId)
  if (res.ok && res.data) return { ok: true, data: res.data, source: 'api' }
  if (LP_EXPLICIT_STATUSES.includes(res.status)) return { ok: false, error: res.error || '后端拒绝了板块看板请求' }
  setOfflineMode(res.error)
  return lpOffline(LP_OFFLINE_MSG.sections)
}

/** 单个业务板块（板块卡片 + 能力点 + 成员行号）。 */
export async function loadLogicPlatformSection(analysisId, sectionId) {
  if (!analysisId) return { ok: false, error: '缺少 analysis_id' }
  if (!sectionId) return { ok: false, error: '缺少 section_id' }
  if (mode.value !== 'api') return lpOffline(LP_OFFLINE_MSG.section)
  const res = await apiGetLogicPlatformSection(analysisId, sectionId)
  if (res.ok && res.data) return { ok: true, data: res.data, source: 'api' }
  if (LP_EXPLICIT_STATUSES.includes(res.status)) return { ok: false, error: res.error || `后端找不到板块 ${sectionId}` }
  setOfflineMode(res.error)
  return lpOffline(LP_OFFLINE_MSG.section)
}

/** 课程索引：哪些能力点已经生成过讲稿。 */
export async function loadLogicPlatformLessons(analysisId) {
  if (!analysisId) return { ok: false, error: '缺少 analysis_id' }
  if (mode.value !== 'api') return lpOffline(LP_OFFLINE_MSG.lessons)
  const res = await apiGetLogicPlatformLessons(analysisId)
  if (res.ok && res.data) return { ok: true, data: res.data, source: 'api' }
  if (LP_EXPLICIT_STATUSES.includes(res.status)) return { ok: false, error: res.error || '后端拒绝了课程索引请求' }
  setOfflineMode(res.error)
  return lpOffline(LP_OFFLINE_MSG.lessons)
}

/**
 * 一课的沉浸式讲稿。
 *
 * **409 必须原样显示**：那是"这个能力点超出本级课程预算、本次没有讲"的结论，
 * 属于平台的诚实边界，不是可以吞掉的噪声 —— 所以它走 `{ok:false, error}` 而不是离线措辞。
 */
export async function loadLogicPlatformLesson(analysisId, capabilityId, { regenerate = false } = {}) {
  if (!analysisId) return { ok: false, error: '缺少 analysis_id' }
  if (!capabilityId) return { ok: false, error: '缺少 capability_id' }
  if (mode.value !== 'api') return lpOffline(LP_OFFLINE_MSG.lesson)
  const res = await apiGetLogicPlatformLesson(analysisId, capabilityId, { regenerate })
  if (res.ok && res.data) return { ok: true, data: res.data, source: 'api' }
  if (LP_EXPLICIT_STATUSES.includes(res.status)) return { ok: false, error: res.error || '后端拒绝了讲稿请求' }
  setOfflineMode(res.error)
  return lpOffline(LP_OFFLINE_MSG.lesson)
}

/** 重新校验一课：后端**重新读磁盘源码**逐字符比对，不复用讲稿里的旧结论。 */
export async function verifyLogicPlatformLesson(analysisId, capabilityId) {
  if (!analysisId) return { ok: false, error: '缺少 analysis_id' }
  if (!capabilityId) return { ok: false, error: '缺少 capability_id' }
  if (mode.value !== 'api') return lpOffline(LP_OFFLINE_MSG.verify)
  const res = await apiVerifyLogicPlatformLesson(analysisId, capabilityId)
  if (res.ok && res.data) return { ok: true, data: res.data, source: 'api' }
  if (LP_EXPLICIT_STATUSES.includes(res.status)) return { ok: false, error: res.error || '后端拒绝了校验请求' }
  setOfflineMode(res.error)
  return lpOffline(LP_OFFLINE_MSG.verify)
}

/**
 * 请求 LLM 讲解（默认关闭）。
 * 503 时后端给的是"平台默认关闭讲解层 + 如何启用"的中文说明，**原样返回**给界面。
 */
export async function requestLogicPlatformNarration(analysisId, capabilityId, provider) {
  if (!analysisId) return { ok: false, error: '缺少 analysis_id' }
  if (!capabilityId) return { ok: false, error: '缺少 capability_id' }
  if (mode.value !== 'api') return lpOffline(LP_OFFLINE_MSG.narration)
  const res = await apiRequestLogicPlatformNarration(analysisId, capabilityId, provider)
  if (res.ok && res.data) return { ok: true, data: res.data, source: 'api' }
  if (LP_EXPLICIT_STATUSES.includes(res.status)) return { ok: false, error: res.error || '后端拒绝了讲解请求' }
  setOfflineMode(res.error)
  return lpOffline(LP_OFFLINE_MSG.narration)
}

/**
 * 教师审核一课（确认 / 拒绝 / 重置，可细化到单条断言）。
 * 审核记录绑定当前 source_hash：源码一变旧审核自动 stale，系统不沿用。
 */
export async function reviewLogicPlatformLesson(analysisId, capabilityId, payload) {
  if (!analysisId) return { ok: false, error: '缺少 analysis_id' }
  if (!capabilityId) return { ok: false, error: '缺少 capability_id' }
  if (mode.value !== 'api') return lpOffline(LP_OFFLINE_MSG.review)
  const res = await apiReviewLogicPlatformLesson(analysisId, capabilityId, payload)
  if (res.ok && res.data) return { ok: true, data: res.data, source: 'api' }
  if (LP_EXPLICIT_STATUSES.includes(res.status)) return { ok: false, error: res.error || '后端拒绝了审核请求' }
  setOfflineMode(res.error)
  return lpOffline(LP_OFFLINE_MSG.review)
}

/**
 * 投入一个项目（.py / .zip）并拿到分析载荷。
 *
 * 上传**没有离线通道**：AST 分析在后端执行，浏览器里不另算一份。
 * 失败时后端的中文 detail（例如"只支持 .py 单文件或 .zip 压缩包。"）原样返回。
 */
export async function uploadLogicPlatformProject(file) {
  if (!file) return { ok: false, error: '没有收到文件' }
  if (mode.value !== 'api') return lpOffline(LP_OFFLINE_MSG.upload)
  const res = await apiUploadForLogicPlatform(file)
  if (res.ok && res.data) return { ok: true, data: res.data, source: 'api' }
  if (LP_EXPLICIT_STATUSES.includes(res.status)) return { ok: false, error: res.error || '后端拒绝了上传' }
  setOfflineMode(res.error)
  // 上传超时/断网这两种在客户端是同一个 catch 分支，措辞里把后端原文也带上，便于排查。
  return lpOffline(`${LP_OFFLINE_MSG.upload}（${res.error || '连接失败'}）`)
}

/**
 * 逻辑平台的源码切片（证据跳转的落点）。
 *
 * 与 `getSource()` 的差别：这个平台有**自己的 source 路由**
 * （`/api/logic-platform/{id}/source`），而且它**刻意不做 basename 兜底** ——
 * 跳错文件的危害比跳不过去大得多（引擎侧的原话）。
 * 返回结构与 `getSource()` 一致，所以同一个 SourceViewerModal 可以直接复用。
 *
 * @returns {Promise<{ok:boolean, data?:object, source?:string, offline?:boolean, error?:string}>}
 */
export async function loadLogicPlatformSource(analysisId, path, start, end) {
  if (!path) return { ok: false, error: '缺少文件路径' }
  if (mode.value !== 'api') return lpOffline('离线演示模式：源码回看不可用（逻辑平台没有静态快照通道）')

  const res = await apiGetLogicPlatformSource(analysisId, String(path).replace(/\\/g, '/'), start, end)
  if (res.ok && res.data) {
    return { ok: true, data: { ...res.data, display_path: path }, source: 'api' }
  }
  // 400（路径越界）/404（文件不存在）都是后端明确结论，不许偷偷换源，直接如实报错。
  if (res.status === 400 || res.status === 404) {
    return { ok: false, error: res.error || `项目中找不到该文件：${path}` }
  }
  setOfflineMode(res.error)
  return lpOffline(`离线演示模式：源码回看不可用（${res.error || '连接失败'}）`)
}

// ---------------------------------------------------------------------------
// 6) URL 深链（?project=<id>）：读 + 写都在这里，TrainingView 不直接碰 history
// ---------------------------------------------------------------------------
/** 从当前 URL 读取 `?project=`；非法/缺失时返回空串。 */
export function readProjectFromUrl() {
  try {
    const id = new URLSearchParams(window.location.search).get('project')
    return id ? String(id).trim() : ''
  } catch {
    return ''
  }
}

/** 把选中的项目写回 URL（replaceState：不产生历史堆积，但可复制链接直达）。 */
export function writeProjectToUrl(projectId) {
  try {
    const url = new URL(window.location.href)
    if (projectId) url.searchParams.set('project', projectId)
    else url.searchParams.delete('project')
    window.history.replaceState({}, '', url.toString())
  } catch {
    /* history 不可用（如 file:// 或沙箱）时静默降级，不影响训练流程 */
  }
}

/** 组合式入口：希望在组件里 `const ds = useDataSource()` 时使用。 */
export function useDataSource() {
  return {
    mode: readonly(mode),
    degraded: readonly(degraded),
    lastError: readonly(lastError),
    apiContractVersion: readonly(apiContractVersion),
    probeApi,
    listProjects,
    loadContract,
    loadBusinessGraph,
    loadModuleCard,
    getSource,
    submitAnswer,
    evaluateOrientationCoverage,
    loadModuleCardTask,
    evaluateModuleCardCoverage,
    listDesignTasks,
    loadDesignTask,
    evaluateDesignSubmission,
    // 业务逻辑分析平台（lp-1.0）——只走在线通道，离线时如实说不可用
    listLogicPlatformProjects,
    loadLogicPlatformNarrationStatus,
    loadLogicPlatformAnalysis,
    loadLogicPlatformSize,
    loadLogicPlatformSections,
    loadLogicPlatformSection,
    loadLogicPlatformLessons,
    loadLogicPlatformLesson,
    verifyLogicPlatformLesson,
    requestLogicPlatformNarration,
    reviewLogicPlatformLesson,
    loadLogicPlatformSource,
    uploadLogicPlatformProject,
    loadLegacyDemo,
    readProjectFromUrl,
    writeProjectToUrl,
    demos: DEMO_PROJECTS,
    defaultProjectId: DEFAULT_PROJECT_ID,
  }
}

/** 非组件上下文（例如 store）里需要读当前模式时使用。 */
export function currentMode() {
  return mode.value
}
