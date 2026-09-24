/**
 * P0-03 · 学习会话（Pinia + localStorage 持久化）
 *
 * 存什么（README5 §6.7 的会话恢复契约，先落地最小可用子集）：
 *   { session_id, project_id, contract_version, stage, answers, hints_used, viewed_evidence, updated_at }
 *
 * 三条纪律：
 *   1. **按 project_id 分命名空间**：`lwai.session.<project_id>`，换项目不会串进度；
 *   2. **不静默沿用**：加载时若 localStorage 里的 `project_id` 或 `contract_version` 与当前契约不一致，
 *      直接丢弃并给出原因（README5 §6.7："教学材料已更新，请重新开始"）；
 *   3. 只记事件，不做判分：判分结果来自后端（P0-11），本 store 只负责"谁答了什么、用了几次提示、看过哪些证据"，
 *      这些都是后续"能力报告"的原始信号。
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const KEY_PREFIX = 'lwai.session.'
const KEY_LAST_ACTIVE = 'lwai.session.__last_active__'

/** 生成一个足够唯一的会话 id（不引第三方 uuid 依赖）。 */
function newSessionId() {
  const rand = Math.random().toString(36).slice(2, 10)
  return `sess_${Date.now().toString(36)}_${rand}`
}

function emptyState(projectId = '', contractVersion = '') {
  return {
    session_id: newSessionId(),
    project_id: projectId,
    contract_version: contractVersion,
    stage: 'level:1',
    answers: {},        // { [questionIndex]: { selected: string[], result: 'correct'|'partial'|'wrong'|'ungraded', graded: boolean, at: ISO } }
    hints_used: {},     // { [level]: number }  每层提示各消耗一次计数
    viewed_evidence: [], // [{ path, start, end, at }]  打开过的证据（源码弹窗）
    updated_at: new Date().toISOString(),
  }
}

export const useLearningSession = defineStore('learningSession', () => {
  const state = ref(emptyState())

  /** 会话层面的提示语（例如"进度已丢弃"），TrainingView 直接显示。 */
  const notice = ref('')
  /** 是否成功恢复了上一次的进度（UI 可以用来提示"已恢复"）。 */
  const restored = ref(false)

  const answeredCount = computed(() => Object.keys(state.value.answers || {}).length)
  const hintTotal = computed(() =>
    Object.values(state.value.hints_used || {}).reduce((sum, n) => sum + (Number(n) || 0), 0),
  )
  const evidenceCount = computed(() => (state.value.viewed_evidence || []).length)

  function storageKey(projectId) {
    return `${KEY_PREFIX}${projectId}`
  }

  function persist() {
    state.value.updated_at = new Date().toISOString()
    try {
      localStorage.setItem(storageKey(state.value.project_id), JSON.stringify(state.value))
      // 记录"最后活跃项目"，用于跨项目时给出更清楚的说明（不是判分依据）
      localStorage.setItem(KEY_LAST_ACTIVE, state.value.project_id)
    } catch (e) {
      // localStorage 被禁用（隐私模式）时不影响训练流程，只丢失持久化能力
      console.warn('[learningSession] 持久化失败：', e?.message || e)
    }
  }

  function readStored(projectId) {
    try {
      const raw = localStorage.getItem(storageKey(projectId))
      return raw ? JSON.parse(raw) : null
    } catch {
      return null
    }
  }

  /**
   * 加载/恢复会话。
   * @param {string} projectId 当前契约的 project_id
   * @param {string} contractVersion 当前契约的 contract_version
   * @returns {{restored:boolean, discardedReason:string}}
   */
  function restoreFor(projectId, contractVersion) {
    notice.value = ''
    restored.value = false

    if (!projectId) {
      state.value = emptyState(projectId, contractVersion)
      return { restored: false, discardedReason: '' }
    }

    const stored = readStored(projectId)

    // 情形 A：存储里的 project_id 与当前项目不一致（键被手动改过 / 旧版本结构）
    if (stored && stored.project_id && stored.project_id !== projectId) {
      discardFor(projectId, contractVersion, `本地进度属于项目「${stored.project_id}」，与当前项目「${projectId}」不一致，已丢弃，请重新开始。`)
      return { restored: false, discardedReason: notice.value }
    }

    // 情形 B：契约版本变化 —— 题目/模块可能已经变了，沿用旧答案会得到错误结论
    if (stored && stored.contract_version && contractVersion && stored.contract_version !== contractVersion) {
      discardFor(projectId, contractVersion, `教学材料已更新（契约 ${stored.contract_version} → ${contractVersion}），旧进度不再适用，已丢弃，请重新开始。`)
      return { restored: false, discardedReason: notice.value }
    }

    // 情形 C：正常恢复
    if (stored) {
      state.value = { ...emptyState(projectId, contractVersion), ...stored, project_id: projectId, contract_version: contractVersion }
      restored.value = true
      return { restored: true, discardedReason: '' }
    }

    // 情形 D：没有本项目进度 —— 顺便告知"另一个项目另有一份进度"，避免用户以为进度丢了
    try {
      const last = localStorage.getItem(KEY_LAST_ACTIVE)
      const lastRecord = last ? readStored(last) : null
      if (last && last !== projectId && lastRecord?.answers && Object.keys(lastRecord.answers).length) {
        notice.value = `检测到项目「${last}」的进度单独保存在本地，当前项目「${projectId}」从零开始。`
      }
    } catch {
      /* ignore */
    }

    state.value = emptyState(projectId, contractVersion)
    persist()
    return { restored: false, discardedReason: '' }
  }

  /**
   * 丢弃指定项目的本地进度并给出原因（同时清掉存储，避免下次再撞上）。
   * 注意：必须显式传入 projectId —— 否则 store 还是空状态时会把 key 算成 `lwai.session.undefined`。
   */
  function discardFor(projectId, contractVersion, reason) {
    try {
      if (projectId) localStorage.removeItem(storageKey(projectId))
    } catch {
      /* ignore */
    }
    state.value = emptyState(projectId, contractVersion)
    restored.value = false
    notice.value = reason
    console.warn('[learningSession] 进度已丢弃：', reason)
  }

  /** 丢弃"当前项目"的本地进度（对外接口）。 */
  function discard(reason) {
    discardFor(state.value.project_id, state.value.contract_version, reason)
  }

  /** 事件：答题（含后端判分结果；离线时 result='ungraded'）。 */
  function recordAnswer(index, { selected, result, graded }) {
    state.value.answers[index] = {
      selected: Array.isArray(selected) ? selected : [selected],
      result: result || 'ungraded',
      graded: !!graded,
      at: new Date().toISOString(),
    }
    persist()
  }

  /** 事件：使用一次提示（每条提示消耗一次计数，README5 §6.6-5）。 */
  function recordHint(level) {
    const key = String(level)
    state.value.hints_used[key] = (state.value.hints_used[key] || 0) + 1
    persist()
  }

  /** 事件：打开一条证据（源码弹窗），供能力报告统计"看过哪些证据"。 */
  function recordEvidence(path, start, end) {
    if (!path) return
    const entry = { path, start: start || null, end: end || null, at: new Date().toISOString() }
    const list = state.value.viewed_evidence
    const last = list[list.length - 1]
    // 同一位置连续打开不重复记录
    if (!last || last.path !== entry.path || last.start !== entry.start) {
      list.push(entry)
      if (list.length > 200) list.splice(0, list.length - 200)
    }
    persist()
  }

  /** 事件：切换阶段（例如 'level:2' / 'result'）。 */
  function setStage(stage) {
    state.value.stage = stage
    persist()
  }

  /** 清空本项目的作答进度（保留 session_id，等价于"重新训练"）。 */
  function resetProgress() {
    state.value.answers = {}
    state.value.hints_used = {}
    state.value.viewed_evidence = []
    state.value.stage = 'level:1'
    persist()
  }

  return {
    state,
    notice,
    restored,
    answeredCount,
    hintTotal,
    evidenceCount,
    restoreFor,
    discard,
    recordAnswer,
    recordHint,
    recordEvidence,
    setStage,
    resetProgress,
  }
})
