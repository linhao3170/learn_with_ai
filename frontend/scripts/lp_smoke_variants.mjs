/**
 * 临时验证脚本 2（跑完即删）：只验证"诚实降级"的四条路径
 * ======================================================
 *   1. level_known=false + graph_status=failed → 不显示级别、不把"没有值"说成 0；
 *   2. 离线（/api 全部连接失败）→ 显示离线横幅，且**没有任何板块卡片**（不编一份看板）；
 *   3. 讲稿接口 409 → 后端 detail 原样显示；
 *   4. 上传失败（400 detail）→ detail 原样显示。
 */
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'
import path from 'node:path'

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const SMOKE_DIST = path.join(FRONTEND, '.smoke-dist')
const frontendRequire = createRequire(path.join(FRONTEND, 'package.json'))
const { JSDOM } = frontendRequire('jsdom')

const results = []
const record = (name, ok, detail = '') => {
  results.push({ name, ok: !!ok, detail: String(detail) })
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  — ' + detail : ''}`)
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
async function waitFor(label, fn, timeout = 8000, interval = 40) {
  const deadline = Date.now() + timeout
  for (;;) {
    let v
    try { v = fn() } catch { v = null }
    if (v) return v
    if (Date.now() > deadline) throw new Error(`waitFor 超时: ${label}`)
    await sleep(interval)
  }
}

const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

/** 起一个全新的 jsdom 应用实例，用给定的路由函数处理 /api。 */
async function boot(routeFn, passInit = false) {
  const dom = new JSDOM('<!doctype html><html><body><div id="app"></div></body></html>', {
    url: 'http://127.0.0.1:5173/',
    pretendToBeVisual: true,
  })
  const { window } = dom
  const g = globalThis
  g.window = window
  g.document = window.document
  g.location = window.location
  g.history = window.history
  g.localStorage = window.localStorage
  g.sessionStorage = window.sessionStorage
  g.getComputedStyle = window.getComputedStyle.bind(window)
  g.requestAnimationFrame = window.requestAnimationFrame.bind(window)
  g.cancelAnimationFrame = window.cancelAnimationFrame.bind(window)
  for (const key of ['navigator', 'HTMLElement', 'HTMLInputElement', 'HTMLSelectElement', 'Element', 'Node', 'Event', 'MouseEvent', 'KeyboardEvent', 'CustomEvent', 'MutationObserver', 'SVGElement', 'DocumentFragment', 'NodeList', 'DOMParser', 'XMLHttpRequest', 'FormData', 'Text', 'Comment', 'HTMLDocument', 'CSSStyleDeclaration']) {
    const value = key === 'navigator' ? window.navigator : window[key]
    if (!value) continue
    try { Object.defineProperty(g, key, { value, writable: true, configurable: true }) } catch { /* ignore */ }
  }
  const calls = []
  const stub = async (input, init = {}) => {
    const url = typeof input === 'string' ? input : (input?.url || String(input))
    const method = String(init?.method || 'GET').toUpperCase()
    calls.push(`${method} ${url}`)
    return passInit ? routeFn(url, method, init) : routeFn(url, method)
  }
  g.fetch = stub
  window.fetch = stub

  const entry = path.join(SMOKE_DIST, 'app.js')
  const { mount } = await import(`file://${entry.replace(/\\/g, '/')}`)
  mount(window.document.getElementById('app'))
  const q = (sel) => window.document.querySelector(sel)
  const qa = (sel) => Array.from(window.document.querySelectorAll(sel))
  const click = (el) => {
    if (!el) throw new Error('click: 元素不存在')
    el.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true, view: window }))
  }
  const txt = (sel) => (q(sel)?.textContent || '').replace(/\s+/g, ' ').trim()
  await waitFor('挂载', () => window.document.getElementById('app').children.length > 0)
  return { window, q, qa, click, txt, calls, bodyText: () => window.document.body.textContent || '' }
}

const BASE_SECTION = {
  section_id: 'sec_x', name_cn: '板块X', name_status: 'inferred', role: 'core', level: 1, confidence: 'inferred',
  is_core: true, objective: '目标', objective_confidence: 'inferred', does_not: ['不负责 A'],
  review_status: 'needs_review', source: 'auto', card: {}, evidence: [],
  capabilities: [{
    capability_id: 'cap_x', name_cn: '能力X', name_status: 'inferred', parent_id: 'sec_x', level: 2,
    entity: 'x', entity_cn: 'X', verb_class: 'do', verb_cn: '做', cluster: 'c', confidence: 'inferred',
    member_confidence: 'verified', members: [], card: {}, evidence: [], is_core: true,
    importance: [1, 0, 0, 0], importance_reasons: ['参与 1 条业务流程'],
    counts: { members: 0 }, walkthrough: { state: 'available', available: true, reason: '' },
  }],
  counts: { capabilities: 1, members: 0, walkthrough_available: 1, walkthrough_total: 1 },
}

function analysisWith({ levelKnown, level, graphStatus, graphError }) {
  return {
    platform_version: 'lp-1.0', project_id: 'lp_broken', project_name: 'lp_broken',
    size: {
      algorithm_version: 'size-1.0', level, level_known: levelKnown, level_label: levelKnown ? '多模块项目' : '',
      level_desc: '', level_basis: ['图谱不可用，无法计算七维信号'],
      structure: { total_files: 1, total_lines: 10 },
      structure_rows: [{ key: 'total_lines', label: '代码行数', value: 10, unit: '行', source: 'ast', note: '空行计入' }],
      complexity: {}, tier: {
        level, level_known: levelKnown, fallback_level: levelKnown ? null : 'L1',
        tier_label: '全量展开', section_budget: null, capability_budget: null, walkthrough_capability_budget: null,
        walkthrough_selection: 'all', segments_per_lesson_cap: 24, statements_per_segment_cap: 40,
        analysis_depth: 'full', rationale: '回退档说明', student_note: '', algorithm_version: 'tiering-1.0',
        caveat: '分级预算是工程常数。',
      },
      size_basis: ['1 个文件'], source_hash: 'sha256:zz', graph_status: graphStatus, graph_error: graphError,
      caveats: ['图谱失败时板块不可用。'],
    },
    sections: {
      board_version: 'boards-1.0', algorithm_version: 'sections-1.0', project_id: 'lp_broken', project_name: 'lp_broken',
      level, sections: [], budget: { tier_label: '全量展开', walkthrough_selection: 'all', section_budget: { budget: null, total: 0, shown: 0, truncated: false }, capability_budget: { budget: null, total: 0, shown: 0, truncated: false }, walkthrough_budget: { budget: null, total: 0, shown: 0, truncated: false, eligible_pool: 'all_capabilities' }, segments_per_lesson_cap: 24, statements_per_segment_cap: 40, analysis_depth: 'full' },
      counts: { sections: 0, sections_shown: 0, core_sections: 0, capabilities: 0, capabilities_shown: 0, core_capabilities: 0, members: 0, members_shown: 0, walkthrough_available: 0, walkthrough_requested: 0 },
      source_hash: 'sha256:zz', caveats: ['板块划分为引擎推断，需教师确认。'],
    },
    caveats: ['平台 caveat。'],
  }
}

async function scenarioUnknownLevel() {
  const analysis = analysisWith({ levelKnown: false, level: '', graphStatus: 'failed', graphError: '图谱构建失败：AST 解析在第 12 行中断' })
  const app = await boot((url) => {
    const p = url.replace(/^https?:\/\/[^/]+/, '')
    if (p.startsWith('/api/health')) return json({ status: 'ok', contract_version: '1.0' })
    if (p === '/api/logic-platform/projects') return json({ projects: [{ project_id: 'lp_broken', project_name: 'lp_broken' }] })
    if (p === '/api/logic-platform/narration-status') return json({ enabled: false, reason: '未启用', config: {}, llm_in_critical_path: false, detached_from_engine: true, caveats: [] })
    if (/\/analysis$/.test(p)) return json(analysis)
    if (/\/lessons$/.test(p)) return json({ lessons: {} })
    return json({ detail: `桩未实现 ${p}` }, 404)
  })
  const { q, qa, click, txt } = app
  click(await waitFor('按钮', () => q('[data-test="go-logic-platform"]')))
  await waitFor('项目卡', () => q('[data-test="logic-project-card"]'))
  click(q('[data-test="logic-project-card"]'))
  await waitFor('大小报告', () => q('[data-test="logic-size"]'))

  record('level_known=false：不显示级别徽章', !q('[data-test="logic-size"] [data-test="complexity-badge"]'))
  record('level_known=false：显式说明未定级', !!q('[data-test="logic-size-level-unknown"]'), txt('[data-test="logic-size-level-unknown"]').slice(0, 50))
  record('level_known=false：不显示级别文本块', !q('[data-test="logic-size-level"]'))
  record('图谱失败：显式说明 + 后端原文', !!q('[data-test="logic-graph-failed"]') && txt('[data-test="logic-graph-failed"]').includes('AST 解析在第 12 行中断'))
  record('图谱失败：AST 行仍然显示且带来源', qa('[data-test="logic-structure-row"]').length === 1 && q('[data-test="logic-structure-row"]').getAttribute('data-source') === 'ast')
  record('回退档被标注为回退（不是本项目级别结论）', !!q('[data-test="logic-tier-unknown-level"]'), txt('[data-test="logic-tier-unknown-level"]'))
  record('口径与边界仍然可见', !!q('[data-test="logic-size-caveats"]'))

  click(q('[data-test="logic-to-sections"]'))
  await waitFor('看板空态', () => q('[data-test="logic-board-empty"]'))
  record('板块为空时如实说明，不编板块', !!q('[data-test="logic-board-empty"]'), txt('[data-test="logic-board-empty"]').slice(0, 40))
}

async function scenarioOffline() {
  const app = await boot(() => { throw new TypeError('fetch failed') })
  const { q, qa, click, txt } = app
  click(await waitFor('按钮', () => q('[data-test="go-logic-platform"]')))
  await waitFor('离线横幅', () => q('[data-test="logic-platform-offline-banner"]'))
  record('离线：平台级横幅说明"分析在后端执行"', txt('[data-test="logic-platform-offline-banner"]').includes('后端执行'), txt('[data-test="logic-platform-offline-banner"]').slice(0, 60))
  await waitFor('列表错误', () => q('[data-test="logic-project-list-error"]'))
  record('离线：项目列表如实报错（不是空列表假象）', txt('[data-test="logic-project-list-error"]').includes('离线演示模式'), txt('[data-test="logic-project-list-error"]').slice(0, 50))
  record('离线：没有任何板块卡片', qa('[data-test="logic-section-card"]').length === 0)
  record('离线：没有大小报告/编造的级别', !q('[data-test="logic-size"]'))
}

async function scenarioLesson409() {
  const analysis = analysisWith({ levelKnown: true, level: 'L2', graphStatus: 'ok', graphError: '' })
  analysis.sections.sections = [BASE_SECTION]
  analysis.sections.counts = { sections: 1, sections_shown: 1, core_sections: 1, capabilities: 1, capabilities_shown: 1, core_capabilities: 1, members: 0, members_shown: 0, walkthrough_available: 1, walkthrough_requested: 1 }
  const detail = '能力点 cap_x 超出本级（全量展开）沉浸式课程预算（最多 0 个能力点），本次未生成课程。'
  const app = await boot((url) => {
    const p = url.replace(/^https?:\/\/[^/]+/, '')
    if (p.startsWith('/api/health')) return json({ status: 'ok', contract_version: '1.0' })
    if (p === '/api/logic-platform/projects') return json({ projects: [{ project_id: 'lp_x', project_name: 'lp_x' }] })
    if (p === '/api/logic-platform/narration-status') return json({ enabled: false, reason: '未启用', config: {}, llm_in_critical_path: false, detached_from_engine: true, caveats: [] })
    if (/\/analysis$/.test(p)) return json(analysis)
    if (/\/sections\/[^/]+$/.test(p)) return json(BASE_SECTION)
    if (/\/lessons\/[^/]+$/.test(p)) return json({ detail }, 409)
    if (/\/lessons$/.test(p)) return json({ lessons: {} })
    return json({ detail: `桩未实现 ${p}` }, 404)
  })
  const { q, click, txt } = app
  click(await waitFor('按钮', () => q('[data-test="go-logic-platform"]')))
  await waitFor('项目卡', () => q('[data-test="logic-project-card"]'))
  click(q('[data-test="logic-project-card"]'))
  await waitFor('大小', () => q('[data-test="logic-size"]'))
  click(q('[data-test="logic-to-sections"]'))
  await waitFor('板块卡', () => q('[data-test="logic-section-card"]'))
  click(q('[data-test="logic-section-card"]'))
  await waitFor('板块分析', () => q('[data-test="logic-section"]'))
  click(q('[data-test="logic-walkthrough-start"]'))
  await waitFor('讲稿错误态', () => q('[data-test="logic-lesson-error"]'))
  record('409 的 detail 原样显示在讲稿位置', txt('[data-test="logic-lesson-error"]').includes('超出本级'), txt('[data-test="logic-lesson-error"]').slice(0, 70))
  record('409 时不会渲染讲稿组件', !q('[data-test="immersive-lesson"]'))
}

async function scenarioUpload() {
  let seen = null
  const app = await boot((url, method, init) => {
    const p = url.replace(/^https?:\/\/[^/]+/, '')
    if (p.startsWith('/api/health')) return json({ status: 'ok', contract_version: '1.0' })
    if (p === '/api/logic-platform/projects') return json({ projects: [] })
    if (p === '/api/logic-platform/narration-status') return json({ enabled: false, reason: '未启用', config: {}, llm_in_critical_path: false, detached_from_engine: true, caveats: [] })
    if (p === '/api/logic-platform/analyze' && method === 'POST') {
      seen = init
      return json({ detail: '只支持 .py 单文件或 .zip 压缩包。' }, 400)
    }
    return json({ detail: `桩未实现 ${p}` }, 404)
  }, true)
  const { window, q, click, txt } = app
  click(await waitFor('按钮', () => q('[data-test="go-logic-platform"]')))
  await waitFor('上传区', () => q('[data-test="logic-upload-zone"]'))

  const input = q('[data-test="logic-file-input"]')
  const file = new window.File(['print(1)\n'], 'demo.py', { type: 'text/x-python' })
  Object.defineProperty(input, 'files', { value: [file], configurable: true })
  input.dispatchEvent(new window.Event('change', { bubbles: true }))
  await waitFor('选中文件', () => q('[data-test="logic-upload-submit"]'))
  record('选中 .py 后出现「开始分析」', !!q('[data-test="logic-upload-picked"]'), txt('[data-test="logic-upload-picked"]'))

  click(q('[data-test="logic-upload-submit"]'))
  await waitFor('上传错误', () => q('[data-test="logic-upload-error"]'))
  record('上传用 multipart（FormData），且没手写 Content-Type', !!seen && !!seen.body && !seen.headers, seen ? `body=${seen.body?.constructor?.name} headers=${JSON.stringify(seen.headers ?? null)}` : '没有捕获到请求')
  record('上传的 multipart 里有 file 字段', !!seen?.body?.get?.('file'), seen?.body?.get?.('file')?.name || '')
  record('后端 400 的 detail 原样显示', txt('[data-test="logic-upload-error"]').includes('只支持 .py 单文件或 .zip 压缩包。'), txt('[data-test="logic-upload-error"]'))
}

async function main() {
  if (!existsSync(path.join(SMOKE_DIST, 'app.js'))) {
    console.error('找不到 .smoke-dist/app.js')
    process.exit(2)
  }
  const scenarios = [
    ['未定级 + 图谱失败', scenarioUnknownLevel],
    ['离线', scenarioOffline],
    ['讲稿 409', scenarioLesson409],
    ['上传（multipart + 400 detail）', scenarioUpload],
  ]
  for (const [name, fn] of scenarios) {
    console.log(`\n---- 场景：${name} ----`)
    try {
      await fn()
    } catch (e) {
      record(`场景「${name}」异常`, false, e?.message || String(e))
    }
  }
  const failed = results.filter((r) => !r.ok)
  console.log(`\n=== ${results.length - failed.length}/${results.length} 通过 ===`)
  for (const f of failed) console.log(` - ${f.name}: ${f.detail}`)
  process.exit(failed.length ? 1 : 0)
}

main()
