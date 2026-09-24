/**
 * 业务逻辑分析平台（lp-1.0）· 前端状态
 * ======================================
 * 为什么要有这个 store：这个平台的流程是**有顺序的六步**
 * （投入项目 → 分析大小 → 按大小分流 → 板块看板 → 板块分析 → 沉浸式讲稿），
 * 每一步的产物都要留给下一步用（例如讲稿要 section_id / capability_id，
 * 校验要 lesson_id），散在组件里迟早会出现"用上了上一个项目的讲稿"这种事。
 *
 * 三条纪律（照抄 learningSession / analysis 的写法，但立场更硬）
 * ------------------------------------------------------------
 * 1. **不缓存可被判为过期的结论**。大小、板块、讲稿都绑定 `source_hash`：
 *    源码一变，旧的看板/讲稿就不再是"当前源码的结论"。所以本 store
 *    **只把 analysisId 与"上次看到哪个板块"写进 localStorage**，
 *    载荷一律每次重新取 —— 宁可贵一次请求，也不显示可能过期的结论。
 * 2. **错误分级原样保留**。dataSource 返回的 `offline === true` 与
 *    `{ok:false, error}` 是两种不同的东西（前者是"没后端"，后者是"后端明确拒绝"），
 *    这个区别在这里不许被抹平，两个字段分别存。
 * 3. **不做任何判定**。这里没有分数、没有级别推断、没有"进度"：
 *    级别与预算来自后端，校验来自后端，`can_publish` 只有教师审核才会变。
 *    本 store 只负责把契约搬来搬去。
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  currentMode,
  probeApi,
  listLogicPlatformProjects,
  loadLogicPlatformNarrationStatus,
  loadLogicPlatformAnalysis,
  loadLogicPlatformSection,
  loadLogicPlatformLessons,
  loadLogicPlatformLesson,
  verifyLogicPlatformLesson,
  requestLogicPlatformNarration,
  reviewLogicPlatformLesson,
  uploadLogicPlatformProject,
} from '../api/dataSource'

// 与 learningSession 同样的"手写 localStorage"风格（不引第三方持久化插件）。
const KEY_PREFIX = 'lwai.logicplatform.'
const KEY_LAST = `${KEY_PREFIX}__last__`

/**
 * 六个阶段。`intake` 是入口，`lesson` 是终点（沉浸式讲稿）。
 * 这是**流程位置**，不是权限，也不是状态机 —— 允许自由跳回去重看。
 */
const STAGES = ['intake', 'size', 'sections', 'section', 'lesson']

function readJSON(key, fallback) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}

function writeJSON(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch (e) {
    // 隐私模式下 localStorage 不可用：只丢持久化能力，不影响分析流程
    console.warn('[logicPlatform] 持久化失败：', e?.message || e)
  }
}

export const useLogicPlatformStore = defineStore('logicPlatform', () => {
  // -------------------------------------------------------------------------
  // 状态
  // -------------------------------------------------------------------------
  /** 当前分析的 id：演示项目 id（如 python_dotenv）或上传得到的 lp_* */
  const analysisId = ref('')
  /** 主载荷：{platform_version, project_id, project_name, size, sections, caveats} */
  const analysis = ref(null)
  /** 课程索引：{lessons: {capabilityId: {...}}} */
  const lessonsIndex = ref(null)
  /** 当前打开的讲稿（一课的完整契约） */
  const currentLesson = ref(null)
  /** 最近一次「重新校验」的返回：{lesson_id, capability_id, report, summary} */
  const verification = ref(null)
  /** 讲解层状态（这个平台有没有用 AI）—— 由后台上报，默认 enabled:false */
  const narrationStatus = ref(null)
  /** 可选项目列表 */
  const projects = ref([])

  const loading = ref(false)
  const lessonLoading = ref(false)
  const verifying = ref(false)
  const narrating = ref(false)
  const uploading = ref(false)

  /** 最近一次失败的**文字**（后端原文优先）。 */
  const error = ref('')
  /** 最近一次失败是不是"没后端"（离线演示模式）——与 error 分开存，UI 措辞不同。 */
  const offline = ref(false)

  /** 当前阶段：intake | size | sections | section | lesson */
  const stage = ref('intake')

  /**
   * 选中板块的详情。
   * 优先用 `GET /{id}/sections/{sid}` 的返回；这个接口不可用时回落到主载荷里的同一份数据，
   * 并在 sectionNotice 里说明回落原因（不冒充"接口正常"）。
   */
  const sectionDetail = ref(null)
  const sectionNotice = ref('')
  const selectedSectionId = ref('')

  /** 正在查看的能力点 id（讲稿 / 校验 / 审核都围绕它）。 */
  const currentCapabilityId = ref('')

  /** 讲解层请求的结果提示（例如 503 的中文原文），与 error 分开，避免互相覆盖。 */
  const narrationNotice = ref('')

  // -------------------------------------------------------------------------
  // 派生数据（全部来自契约，前端不补一个字段）
  // -------------------------------------------------------------------------
  const size = computed(() => analysis.value?.size || null)
  const tier = computed(() => size.value?.tier || null)
  const board = computed(() => analysis.value?.sections || null)
  const sections = computed(() => (Array.isArray(board.value?.sections) ? board.value.sections : []))
  const boardBudget = computed(() => board.value?.budget || null)
  const projectName = computed(() => analysis.value?.project_name || analysisId.value || '（未命名项目）')

  const currentSection = computed(() => {
    if (!selectedSectionId.value) return null
    // 板块详情接口优先；它挂了就退回主载荷（同一份引擎产物，不是另一套口径）
    if (sectionDetail.value?.section_id === selectedSectionId.value) return sectionDetail.value
    return sections.value.find((s) => s.section_id === selectedSectionId.value) || null
  })

  /** 主载荷与板块载荷各自带 caveats，合并展示（去重，顺序保留）。 */
  const caveats = computed(() => {
    const out = []
    for (const line of [...(analysis.value?.caveats || []), ...(board.value?.caveats || [])]) {
      const text = String(line || '').trim()
      if (text && !out.includes(text)) out.push(text)
    }
    return out
  })

  const sizeCaveats = computed(() => (Array.isArray(size.value?.caveats) ? size.value.caveats : []))

  const isOffline = computed(() => currentMode() !== 'api')

  // -------------------------------------------------------------------------
  // 小工具
  // -------------------------------------------------------------------------
  function clearError() {
    error.value = ''
    offline.value = false
  }

  function fail(res, fallback = '请求失败') {
    error.value = res?.error || fallback
    offline.value = res?.offline === true
    return { ok: false, offline: offline.value, error: error.value }
  }

  /**
   * 与后端"当前是否可达"对齐。
   *
   * `mode` 是 dataSource 里的模块级单例，初始值是 'offline'，只有探测过才会变 'api'。
   * 如果用户从首页直接进这个平台（没走过训练页），这里不补一次探测的话，
   * 数据源会把"还没探测"当成"离线"，于是页面显示"离线演示模式"——
   * 那是**另一种不诚实**（把能用的后端说成不能用）。所以这里补一次真实探测。
   */
  async function ensureProbed() {
    if (currentMode() === 'api') return true
    return await probeApi()
  }

  function persist() {
    writeJSON(KEY_LAST, { analysis_id: analysisId.value, section_id: selectedSectionId.value })
  }

  function restore() {
    const saved = readJSON(KEY_LAST, null)
    return {
      analysisId: String(saved?.analysis_id || ''),
      sectionId: String(saved?.section_id || ''),
    }
  }

  // -------------------------------------------------------------------------
  // 动作：列表 / 阶段
  // -------------------------------------------------------------------------
  /** 把 store 的失败信号与 dataSource 的离线信号都当作失败（调用方只看 ok）。 */
  async function loadProjects() {
    const res = await listLogicPlatformProjects()
    if (!res.ok) return fail(res, '无法获取演示项目列表')
    projects.value = Array.isArray(res.data?.projects) ? res.data.projects : []
    return { ok: true, data: projects.value }
  }

  function setStage(next) {
    if (!STAGES.includes(next)) return
    stage.value = next
    clearError()
  }

  // -------------------------------------------------------------------------
  // 动作：分析主载荷
  // -------------------------------------------------------------------------
  /**
   * 选定一个项目并加载主载荷（大小 + 分流 + 板块看板）。
   * @param {string} id analysis_id
   * @param {{force?: boolean}} [options] force=true 时后端重算
   */
  async function selectProject(id, { force = false } = {}) {
    if (!id) return { ok: false, error: '缺少 analysis_id' }
    await ensureProbed()

    analysisId.value = id
    loading.value = true
    clearError()
    // 换项目 = 换结论：上一个项目的板块 / 讲稿 / 校验一律清掉，绝不跨项目复用
    currentLesson.value = null
    verification.value = null
    sectionDetail.value = null
    selectedSectionId.value = ''
    currentCapabilityId.value = ''
    sectionNotice.value = ''
    narrationNotice.value = ''
    lessonsIndex.value = null
    persist()

    const res = await loadLogicPlatformAnalysis(id, { force })
    loading.value = false

    if (!res.ok) {
      analysis.value = null
      stage.value = 'intake'
      return fail(res, '无法加载项目分析')
    }

    analysis.value = res.data
    stage.value = 'size'

    // 课程索引与讲解层状态都只是"补充信息"，拿不到不影响主流程：
    // 如实记下来（loadLessonsIndex / loadNarrationStatus 内部已有自己的错误措辞），
    // 但**不覆盖**主载荷成功这个事实。
    await Promise.all([loadLessonsIndex({ quiet: true }), loadNarrationStatus({ quiet: true })])
    return { ok: true, data: analysis.value }
  }

  /** 重新取一次主载荷（force=true 让后端重算，而不是读缓存）。 */
  async function reloadAnalysis({ force = true } = {}) {
    if (!analysisId.value) return { ok: false, error: '还没有选项目' }
    loading.value = true
    clearError()
    const res = await loadLogicPlatformAnalysis(analysisId.value, { force })
    loading.value = false
    if (!res.ok) return fail(res, '无法重新加载项目分析')
    analysis.value = res.data
    return { ok: true, data: analysis.value }
  }

  /** 课程索引（哪些能力点已经生成过讲稿）。 */
  async function loadLessonsIndex({ quiet = false } = {}) {
    if (!analysisId.value) return { ok: false, error: '还没有选项目' }
    const res = await loadLogicPlatformLessons(analysisId.value)
    if (!res.ok) {
      if (!quiet) fail(res, '无法获取课程索引')
      else console.warn('[logicPlatform] 课程索引不可用：', res.error)
      return { ok: false, error: res.error }
    }
    lessonsIndex.value = res.data
    return { ok: true, data: res.data }
  }

  /** 讲解层状态（enabled 默认 false —— 页面要如实说出来）。 */
  async function loadNarrationStatus({ quiet = false } = {}) {
    const res = await loadLogicPlatformNarrationStatus()
    if (!res.ok) {
      if (!quiet) fail(res, '无法获取讲解层状态')
      else console.warn('[logicPlatform] 讲解层状态不可用：', res.error)
      return { ok: false, error: res.error }
    }
    narrationStatus.value = res.data
    return { ok: true, data: res.data }
  }

  // -------------------------------------------------------------------------
  // 动作：板块
  // -------------------------------------------------------------------------
  /**
   * 打开一个板块。
   *
   * 先问专属接口 `GET /{id}/sections/{sid}`（只取这一块，载荷更小）；
   * 接口不可用时回落到主载荷里的同一份板块数据，并把回落原因写进 sectionNotice ——
   * 界面会显示这句话。**不冒充接口正常**，也不因此显示空白。
   */
  async function selectSection(sectionId) {
    if (!sectionId) return { ok: false, error: '缺少 section_id' }
    selectedSectionId.value = sectionId
    sectionDetail.value = null
    sectionNotice.value = ''
    currentLesson.value = null
    verification.value = null
    narrationNotice.value = ''
    clearError()
    stage.value = 'section'
    persist()

    const res = await loadLogicPlatformSection(analysisId.value, sectionId)
    if (res.ok && res.data) {
      sectionDetail.value = res.data
      return { ok: true, data: res.data }
    }

    const local = sections.value.find((s) => s.section_id === sectionId) || null
    if (local) {
      // 主载荷里就有这一块，界面照样能看；但把"接口没成功"这件事说出来。
      sectionNotice.value = `板块详情接口未成功（${res.error || '未知原因'}），当前显示的是分析载荷里的同一份板块数据。`
      return { ok: true, data: local, degraded: true }
    }
    return fail(res, `无法打开板块 ${sectionId}`)
  }

  function backToBoard() {
    stage.value = 'sections'
    clearError()
  }

  // -------------------------------------------------------------------------
  // 动作：讲稿
  // -------------------------------------------------------------------------
  /**
   * 打开一课（沉浸式学习业务逻辑）。
   *
   * 失败时**不清理 error**：后端 409 的 detail（"超出本级课程预算…"）
   * 就是要给学生看的那句结论，必须留在 error 里由界面原样显示。
   *
   * @param {string} capabilityId
   * @param {{regenerate?: boolean}} [options]
   */
  async function openLesson(capabilityId, { regenerate = false } = {}) {
    if (!capabilityId) return { ok: false, error: '缺少 capability_id' }
    currentCapabilityId.value = capabilityId
    currentLesson.value = null
    verification.value = null
    narrationNotice.value = ''
    clearError()
    stage.value = 'lesson'
    lessonLoading.value = true

    const res = await loadLogicPlatformLesson(analysisId.value, capabilityId, { regenerate })
    lessonLoading.value = false

    if (!res.ok) return fail(res, '无法生成讲稿')
    currentLesson.value = res.data
    // 讲稿自带一份 verification；同时刷新课程索引（刚生成的课会进索引）
    loadLessonsIndex({ quiet: true })
    return { ok: true, data: res.data }
  }

  /** 关闭讲稿，回到板块（保留板块选择）。 */
  function closeLesson() {
    currentLesson.value = null
    verification.value = null
    currentCapabilityId.value = ''
    narrationNotice.value = ''
    clearError()
    stage.value = selectedSectionId.value ? 'section' : 'sections'
  }

  /**
   * 重新校验当前讲稿。后端会**重新从磁盘读源码**逐字符比对，
   * 所以这是"现在这一刻引用是否仍然成立"的证据，而不是复用讲稿里的旧结论。
   */
  async function reverify() {
    if (!currentCapabilityId.value) return { ok: false, error: '还没有打开讲稿' }
    verifying.value = true
    clearError()
    const res = await verifyLogicPlatformLesson(analysisId.value, currentCapabilityId.value)
    verifying.value = false
    if (!res.ok) return fail(res, '重新校验失败')
    verification.value = res.data
    // 校验报告里的 review 才是"刚刚这一刻"的状态，合回讲稿，页面不会同时显示两套结论
    if (currentLesson.value && res.data?.report) {
      currentLesson.value = { ...currentLesson.value, verification: res.data.report }
      if (res.data.report.can_publish !== undefined && currentLesson.value.review) {
        currentLesson.value.review = {
          ...currentLesson.value.review,
          verification_passed: !!res.data.report.can_publish,
          verified_checks: res.data.report.counts?.passed ?? currentLesson.value.review.verified_checks,
          failed_checks: res.data.report.counts?.failed ?? currentLesson.value.review.failed_checks,
        }
      }
    }
    return { ok: true, data: res.data }
  }

  /**
   * 请求 LLM 讲解（默认关闭）。
   * 503 的中文原文写进 narrationNotice（**不是 error**）：它是"平台默认不用 AI"的
   * 一个说明，不是故障，但同样必须让评审看见。
   */
  async function requestNarration(provider) {
    if (!currentCapabilityId.value) return { ok: false, error: '还没有打开讲稿' }
    narrating.value = true
    narrationNotice.value = ''
    const res = await requestLogicPlatformNarration(analysisId.value, currentCapabilityId.value, provider)
    narrating.value = false
    if (!res.ok) {
      narrationNotice.value = res.error || '讲解请求失败'
      return { ok: false, error: narrationNotice.value, offline: res.offline === true }
    }
    narrationNotice.value = res.data?.outcome?.message || res.data?.outcome?.reason || '讲解已合入讲稿（仍需教师确认）。'
    if (res.data?.lesson) currentLesson.value = res.data.lesson
    return { ok: true, data: res.data }
  }

  /**
   * 教师审核（确认 / 拒绝 / 重置）。
   * `can_publish` 只有走这条路才会变 true —— 引擎永远不会自己置 true。
   */
  async function reviewLesson(payload) {
    if (!currentCapabilityId.value) return { ok: false, error: '还没有打开讲稿' }
    clearError()
    const res = await reviewLogicPlatformLesson(analysisId.value, currentCapabilityId.value, payload)
    if (!res.ok) return fail(res, '审核请求失败')
    // 审核返回的是 review 片段，不是完整讲稿：重新取一次讲稿，避免本地拼出
    // 一个"看起来像审核结果"的赝品（stale 判定只有后端会算）。
    await loadLessonsIndex({ quiet: true })
    const fresh = await loadLogicPlatformLesson(analysisId.value, currentCapabilityId.value)
    if (fresh.ok) currentLesson.value = fresh.data
    return { ok: true, data: res.data }
  }

  // -------------------------------------------------------------------------
  // 动作：投入项目（上传 .py / .zip）
  // -------------------------------------------------------------------------
  /**
   * 上传一个项目并直接进入大小分析。
   *
   * 上传**没有离线通道**：分析在后端执行，浏览器里不另算一份。
   * 失败（含后端 400 的中文 detail）原样保留在 error 里由界面显示。
   */
  async function uploadProject(file) {
    if (!file) return { ok: false, error: '没有收到文件' }
    await ensureProbed()
    uploading.value = true
    clearError()
    const res = await uploadLogicPlatformProject(file)
    uploading.value = false
    if (!res.ok) return fail(res, '上传分析失败')
    // 上传接口返回的就是完整 analysis 载荷：直接用它，不再多打一次请求。
    analysisId.value = res.data?.project_id || ''
    analysis.value = res.data
    selectedSectionId.value = ''
    currentLesson.value = null
    verification.value = null
    stage.value = 'size'
    persist()
    await Promise.all([loadLessonsIndex({ quiet: true }), loadNarrationStatus({ quiet: true })])
    return { ok: true, data: res.data }
  }

  // -------------------------------------------------------------------------
  // 动作：复位
  // -------------------------------------------------------------------------
  /** 回到"投入项目"这一步（不删 localStorage 里的记忆，只清当前会话的载荷）。 */
  function reset() {
    analysisId.value = ''
    analysis.value = null
    lessonsIndex.value = null
    currentLesson.value = null
    verification.value = null
    sectionDetail.value = null
    selectedSectionId.value = ''
    currentCapabilityId.value = ''
    sectionNotice.value = ''
    narrationNotice.value = ''
    loading.value = false
    lessonLoading.value = false
    stage.value = 'intake'
    clearError()
  }

  return {
    // state
    analysisId,
    analysis,
    lessonsIndex,
    currentLesson,
    verification,
    narrationStatus,
    projects,
    loading,
    lessonLoading,
    verifying,
    narrating,
    uploading,
    error,
    offline,
    stage,
    selectedSectionId,
    sectionDetail,
    sectionNotice,
    currentCapabilityId,
    narrationNotice,
    // getters
    size,
    tier,
    board,
    sections,
    boardBudget,
    projectName,
    currentSection,
    caveats,
    sizeCaveats,
    isOffline,
    // actions
    ensureProbed,
    loadProjects,
    setStage,
    selectProject,
    reloadAnalysis,
    loadLessonsIndex,
    loadNarrationStatus,
    selectSection,
    backToBoard,
    openLesson,
    closeLesson,
    reverify,
    requestNarration,
    reviewLesson,
    uploadProject,
    reset,
    restore,
  }
})

/** 供外部（例如首页按钮）判断要不要提示"上次看到哪"。 */
export const LOGIC_PLATFORM_STORAGE_PREFIX = KEY_PREFIX
