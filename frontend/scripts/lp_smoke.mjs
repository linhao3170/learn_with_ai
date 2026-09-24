/**
 * 业务逻辑分析平台 · 端到端点击流自测（jsdom）
 * ============================================
 * 目的：不启动任何服务器，用 jsdom + 真实浏览器版 Vue 打包产物，
 * 配合**按契约造出来的**桩响应，把「业务逻辑分析平台」的六步流程真点一遍：
 *
 *   投入项目 → 大小分析 → 分流策略 → 板块看板 → 板块分析 → 沉浸式讲稿 → 校验与审核
 *
 * 它验证的是**接线**（界面有没有真的按契约渲染、按钮有没有真的发出正确的请求），
 * 而不是引擎算得对不对 —— 引擎那部分由 `scripts/test_logic_platform.py` 负责。
 * 两者互补：桩数据保证界面断言稳定，真实数据保证引擎结论可靠。
 *
 * 其中三条断言值得单独点名（它们是本项目的诚实纪律在界面上的落点）：
 *   1. 截断可见 —— 超出预算的能力点必须显示原文原因，不许静默少给；
 *   2. `can_publish` 不许被当成"已发布"，`blocking_issues` 必须常驻可见；
 *   3. 页面上**不许出现**「AI 智能分析」「准确率」这类话术（有专门一条断言在扫）。
 *
 * 用法
 * ----
 *   cd frontend
 *   node node_modules/vite/bin/vite.js build --config vite.smoke.config.js
 *   node scripts/lp_smoke.mjs
 *
 * 前置：`.smoke-dist` 必须存在（上面第一步生成）。
 * 退出码：0 = 全部通过；1 = 有失败项。
 */
import { existsSync, readdirSync } from 'node:fs'
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

// ---------------------------------------------------------------------------
// 桩数据（严格按任务说明里的契约形状）
// ---------------------------------------------------------------------------
const CLAIM_OK = {
  claim_id: 'claim_ok', claim_text: '读取会先建一个空字典', category: 'state',
  evidence: [{ fact_id: 'f1', file: 'dotenv/main.py', start_line: 85, end_line: 85, symbol: 'read_dotenv', excerpt: 'values = {}', excerpt_hash: 'sha256:x', confidence: 'verified', reason: 'AST 直出' }],
  confidence: 'verified', verified: true, reject_reason: '',
}
const CLAIM_INF = {
  claim_id: 'claim_inf', claim_text: '它不负责校验业务含义', category: 'boundary',
  evidence: [], confidence: 'inferred', verified: true, reject_reason: '',
}
const CLAIM_BAD = {
  claim_id: 'claim_bad', claim_text: '文件缺失时会抛异常', category: 'exception',
  evidence: [], confidence: 'needs_review', verified: false, reject_reason: '引用的第 120 行超出了函数范围',
}

const LESSON_VERIFICATION = {
  verify_version: 'verify-1.0', algorithm_version: 'verify-1.0', lesson_id: 'lesson_cap_read_file', can_publish: true,
  counts: { checks: 2, passed: 1, failed: 1, skipped: 0, rejected_claims: 1, rejected_segments: 0 },
  checks: [
    { check_id: 'code_excerpt_hash', check_name: '代码摘录与磁盘源码逐字符一致', scope: 'segment', target_id: 'seg_2', status: 'fail', file: 'dotenv/main.py', line: 99, detail: '磁盘上第 99 行与讲稿不一致' },
    { check_id: 'evidence_range', check_name: '证据行号落在文件范围内', scope: 'lesson', target_id: 'lesson_cap_read_file', status: 'pass', file: 'dotenv/main.py', line: 84, detail: 'ok' },
  ],
  rejected_claim_ids: ['claim_bad'], rejected_segment_ids: [], caveats: ['校验只证明引用一致，不证明业务解释正确。'],
}

const LESSON = {
  lesson_version: 'lesson-1.0', algorithm_version: 'walkthrough-1.0', lesson_id: 'lesson_cap_read_file', lesson_number: 1,
  title: '读取环境文件', capability_id: 'cap_read_file', capability_name: '读取环境文件',
  section_id: 'sec_read', section_name: '读取与解析', level: 'L2',
  intro: '你不需要记住每一行，只需要记住这条业务路径。',
  one_line_frame: '一句话先定调：读取 = 找文件 → 解析 → 写回内存。',
  segments: [{
    segment_id: 'seg_1', order: 1, title: '准备工作', title_status: 'from_structure',
    header_text: '第 1 段：准备工作（84-87 行）', segment_kind: 'prepare',
    source: { file: 'dotenv/main.py', display_path: 'dotenv/main.py', start_line: 84, end_line: 87, symbol: 'read_dotenv', symbol_kind: 'function', extra_ranges: [], member_symbol: 'read_dotenv', member_start_line: 84, member_end_line: 97 },
    code_excerpt: 'def read_dotenv(path):\n    values = {}\n    return values',
    code_excerpt_hash: 'sha256:aaa',
    line_annotations: [{ line: 84, text: '入口函数', role: 'explain', is_original_comment: false }],
    lead_in: '以下这段属于 dotenv/main.py 的 read_dotenv()（第 84-87 行）',
    emphasis_line: '',
    branch_detail: null,
    must_remember: [CLAIM_OK, CLAIM_BAD],
    know_enough: [CLAIM_INF],
    one_sentence_summary: CLAIM_OK,
  }],
  summary_diagram: '| 段落 | 内容 |\n|---|---|\n| 1 | 准备 |',
  lesson_recap: ['读取 = 找文件 + 解析 + 写回内存'],
  consolidate: '把这一段自己在纸上画一遍。',
  next_action: '打开源码对照看一遍',
  members_covered: [{ symbol: 'read_dotenv', file: 'dotenv/main.py', start_line: 84, end_line: 97, segments: ['seg_1'], truncated: false }],
  members_total: 1, truncated: false, truncation_reason: '', source_hash: 'sha256:abc123',
  review: {
    status: 'needs_review', can_publish: false, verification_passed: false, verified_checks: 1, failed_checks: 1,
    generated_by: 'ast_rule_engine', llm_claim_ratio: 0.0, analysis_version: 'lp-1.0', source_hash: 'sha256:abc123',
    blocking_issues: ['尚未经教师确认，不得作为教学材料发布。'],
    human_review: { status: 'stale', stale: true, reviewer: '张老师', updated_at: '2026-01-01T00:00:00Z', claims: { claim_ok: { decision: 'confirm', note: '' } }, note: '看过一遍' },
  },
  caveats: ['本课只覆盖 1 个成员函数。'],
  render: {
    header_format: '第 {order} 段：{title}（{start}-{end} 行）',
    header_format_alt: '第 {start}-{end} 行：{title}',
    bullets_heading: '重点记什么：',
    summary_heading: '一句话概括： ',
    know_enough_heading: '知道就行：',
    lesson_recap_heading: '你现在需要记住的 {n} 个核心要点：',
    lesson_open: 'open', lesson_frame_prefix: '一句话先定调：', lesson_close: 'close',
  },
  verification: LESSON_VERIFICATION,
}

const CAP_OK = {
  capability_id: 'cap_read_file', name_cn: '读取环境文件', name_status: 'inferred', parent_id: 'sec_read', level: 2,
  entity: 'file', entity_cn: '文件', verb_class: 'read', verb_cn: '读取', cluster: 'io',
  confidence: 'inferred', member_confidence: 'verified',
  members: [{ symbol: 'read_dotenv', role: 'entry', file: 'dotenv\\main.py', start_line: 84, end_line: 97, is_public: true, state_writes: ['values'], state_reads: [] }],
  card: {}, evidence: [{ file: 'dotenv/main.py', start_line: 84, end_line: 97, symbol: 'read_dotenv', signal: 'def' }],
  is_core: true, importance: [3, 12, 4, 2],
  importance_reasons: ['参与 3 条业务流程（如「加载配置」）', '含 12 条业务边界事实（异常 2 / 前置判断 6 / 业务规则 4）', '写入 4 个状态字段', '由 2 个函数构成'],
  counts: { members: 1, flows: 3, rules: 4, guards: 6, exceptions: 2, state_writes: 4 },
  walkthrough: { state: 'available', available: true, reason: '进入本级沉浸式课程预算：核心度排名靠前。' },
}
const CAP_OVER = {
  capability_id: 'cap_parse_line', name_cn: '解析单行', name_status: 'inferred', parent_id: 'sec_read', level: 2,
  entity: 'line', entity_cn: '行', verb_class: 'parse', verb_cn: '解析', cluster: 'io',
  confidence: 'inferred', member_confidence: 'verified',
  members: [{ symbol: 'parse_line', role: 'rule', file: 'dotenv/main.py', start_line: 60, end_line: 70, is_public: false, state_writes: [], state_reads: ['values'] }],
  card: {}, evidence: [],
  is_core: false, importance: [0, 2, 0, 1], importance_reasons: ['未参与已知流程，也没有边界事实 —— 核心度排序靠后'],
  counts: { members: 1, flows: 0, rules: 1, guards: 1, exceptions: 0, state_writes: 0 },
  walkthrough: { state: 'beyond_budget', available: false, reason: '超出本级（全量板块 + 全量课程）沉浸式课程预算（最多 1 个能力点），本次未生成课程。板块分析与证据仍然完整可看。' },
}

const SECTION_READ = {
  section_id: 'sec_read', name_cn: '读取与解析', name_status: 'inferred', role: 'core', level: 1,
  confidence: 'inferred', is_core: true,
  objective: '把 .env 文件读成键值对', objective_confidence: 'inferred',
  does_not: ['不负责写回文件', '不负责校验业务含义'],
  review_status: 'needs_review', source: 'auto',
  card: { does_not_confidence: 'inferred' },
  evidence: [{ file: 'dotenv/main.py', start_line: 10, end_line: 12, signal: 'member:entry' }],
  capabilities: [CAP_OK, CAP_OVER],
  counts: { capabilities: 2, members: 3, walkthrough_available: 1, walkthrough_total: 2 },
}
const SECTION_CLI = {
  section_id: 'sec_cli', name_cn: '命令行入口', name_status: 'inferred', role: 'orchestrator', level: 1,
  confidence: 'inferred-low', is_core: false,
  objective: '', objective_confidence: 'unconfirmed',
  does_not: [], review_status: 'needs_review', source: 'auto',
  card: {}, evidence: [],
  capabilities: [{
    capability_id: 'cap_cli_main', name_cn: '命令行主流程', name_status: 'inferred', parent_id: 'sec_cli', level: 2,
    entity: 'cli', entity_cn: '命令行', verb_class: 'run', verb_cn: '运行', cluster: 'cli',
    confidence: 'inferred', member_confidence: 'verified',
    members: [{ symbol: 'main', role: 'entry', file: 'cli.py', start_line: 30, end_line: 44, is_public: true, state_writes: [], state_reads: [] }],
    card: {}, evidence: [],
    is_core: false, importance: [1, 0, 0, 1], importance_reasons: ['参与 1 条业务流程'],
    counts: { members: 1, flows: 1, rules: 0, guards: 0, exceptions: 0, state_writes: 0 },
    walkthrough: { state: 'beyond_budget', available: false, reason: '本级采用核心优先策略，该能力点所属域不是核心域，本次不生成课程。' },
  }],
  counts: { capabilities: 1, members: 1, walkthrough_available: 0, walkthrough_total: 1 },
}

const ANALYSIS = {
  platform_version: 'lp-1.0', project_id: 'python_dotenv', project_name: 'python_dotenv',
  size: {
    size_version: 'size-1.0', algorithm_version: 'size-1.0', project_id: 'python_dotenv', project_name: 'python_dotenv',
    level: 'L2', level_known: true, level_label: '多模块项目', level_desc: '10 个以内模块、结构清晰。',
    level_basis: ['一级业务域 2 个', '二级功能点 3 个'],
    structure: { total_files: 2, total_lines: 900 },
    structure_rows: [
      { key: 'total_lines', label: '代码行数', value: 900, unit: '行', source: 'ast', note: '空行与注释计入' },
      { key: 'capabilities', label: '二级功能点', value: 3, unit: '个', source: 'business_graph', note: '来自图谱聚类' },
    ],
    complexity: {
      level: 'L2', level_label: '多模块项目', level_desc: '多模块项目', algorithm_version: 'complexity-1.0',
      breakdown: { domains: 2 }, weights: { domains: 2 }, level_basis: ['一级业务域 2 个'], caveat: '阈值待校准。',
    },
    tier: {
      level: 'L2', level_label: '多模块项目', level_known: true, fallback_level: null,
      tier_label: '全量板块 + 全量课程', section_budget: null, capability_budget: null,
      walkthrough_capability_budget: 12, walkthrough_selection: 'all',
      segments_per_lesson_cap: 20, statements_per_segment_cap: 40, analysis_depth: 'full',
      rationale: '板块数量还看得完，但能力点开始变多。', student_note: '板块全部展开。',
      algorithm_version: 'tiering-1.0', caveat: '分级预算（展开数量 / 课程数量 / 段行上限）是工程常数，待实测校准。',
    },
    size_basis: ['2 个 Python 文件', '900 行'],
    source_hash: 'sha256:abcd1234abcd1234abcd1234', graph_status: 'ok', graph_error: '',
    caveats: ['规模数字来自 AST 与图谱两层，口径见 structure_rows 的 source 列。'],
  },
  sections: {
    board_version: 'boards-1.0', algorithm_version: 'sections-1.0',
    project_id: 'python_dotenv', project_name: 'python_dotenv', level: 'L2',
    sections: [SECTION_READ, SECTION_CLI],
    budget: {
      tier_label: '全量板块 + 全量课程', walkthrough_selection: 'all',
      section_budget: { budget: null, total: 2, shown: 2, truncated: false },
      capability_budget: { budget: null, total: 3, shown: 3, truncated: false },
      walkthrough_budget: { budget: 1, total: 3, shown: 1, truncated: true, eligible_pool: 'all_capabilities' },
      segments_per_lesson_cap: 20, statements_per_segment_cap: 40, analysis_depth: 'full',
    },
    counts: { sections: 2, sections_shown: 2, core_sections: 1, capabilities: 3, capabilities_shown: 3, core_capabilities: 2, members: 5, members_shown: 5, walkthrough_available: 1, walkthrough_requested: 1 },
    source_hash: 'sha256:abcd1234abcd1234abcd1234',
    caveats: ['板块划分与命名由引擎推断，需教师确认。'],
  },
  caveats: ['平台 caveat：级别只影响讲多少，不影响事实判定。'],
}

const SOURCE = {
  file: 'dotenv/main.py', resolved_file: 'dotenv/main.py', total_lines: 120, start: 84, end: 97,
  window_start: 79, window_end: 102,
  lines: [{ number: 84, text: 'def read_dotenv(path):' }, { number: 85, text: '    values = {}' }],
}

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

function route(url, method) {
  const u = String(url)
  const pathOnly = u.replace(/^https?:\/\/[^/]+/, '')
  if (pathOnly.startsWith('/api/health')) return jsonResponse({ status: 'ok', version: '0.5.0', contract_version: '1.0' })
  if (pathOnly === '/api/logic-platform/projects') return jsonResponse({ projects: [{ project_id: 'python_dotenv', project_name: 'python_dotenv' }] })
  if (pathOnly === '/api/logic-platform/narration-status') {
    return jsonResponse({
      enabled: false, reason: 'LLM 讲解层未启用：平台默认关闭它，确定性事实层与证据校验不依赖任何模型。',
      config: {}, llm_in_critical_path: false, detached_from_engine: true,
      caveats: ['讲解层只改写措辞，不产生任何事实。'],
    })
  }
  if (/^\/api\/logic-platform\/[^/]+\/analysis/.test(pathOnly)) return jsonResponse(ANALYSIS)
  if (/^\/api\/logic-platform\/[^/]+\/sections\/[^/]+$/.test(pathOnly)) {
    const sid = pathOnly.split('/').pop()
    const found = [SECTION_READ, SECTION_CLI].find((s) => s.section_id === sid)
    return found ? jsonResponse(found) : jsonResponse({ detail: `板块 ${sid} 不存在` }, 404)
  }
  if (/^\/api\/logic-platform\/[^/]+\/sections$/.test(pathOnly)) return jsonResponse(ANALYSIS.sections)
  if (/^\/api\/logic-platform\/[^/]+\/lessons\/[^/]+\/verify$/.test(pathOnly)) {
    return jsonResponse({
      lesson_id: LESSON.lesson_id, capability_id: CAP_OK.capability_id,
      report: LESSON_VERIFICATION,
      summary: { can_publish: false, conclusion: '机械复核未通过：1 项失败（代码摘录与磁盘源码不一致）。', counts: LESSON_VERIFICATION.counts, failing_checks: ['code_excerpt_hash'] },
    })
  }
  if (/^\/api\/logic-platform\/[^/]+\/lessons\/[^/]+\/narration$/.test(pathOnly)) {
    return jsonResponse({ detail: 'LLM 讲解层未启用。平台默认关闭它：确定性事实层与证据校验不依赖任何模型。' }, 503)
  }
  if (/^\/api\/logic-platform\/[^/]+\/lessons\/[^/]+$/.test(pathOnly)) return jsonResponse(LESSON)
  if (/^\/api\/logic-platform\/[^/]+\/lessons$/.test(pathOnly)) return jsonResponse({ lessons: { cap_read_file: { capability_id: 'cap_read_file', section_id: 'sec_read', generated: true, can_publish: false, review_status: 'needs_review', segments: 1 } } })
  if (/^\/api\/logic-platform\/[^/]+\/source/.test(pathOnly)) return jsonResponse(SOURCE)
  if (pathOnly === '/api/projects') return jsonResponse({ projects: [{ project_id: 'python_dotenv', project_name: 'python_dotenv' }] })
  // 其余（训练契约、静态快照）一律 404：本脚本只验证逻辑平台这条路
  return jsonResponse({ detail: `桩：未实现 ${method} ${pathOnly}` }, 404)
}

async function main() {
  const entry = path.join(SMOKE_DIST, 'app.js')
  if (!existsSync(entry)) {
    console.error('找不到 .smoke-dist/app.js，请先构建 smoke bundle')
    process.exit(2)
  }

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
  const stubFetch = async (input, init = {}) => {
    const url = typeof input === 'string' ? input : (input?.url || String(input))
    const method = String(init?.method || 'GET').toUpperCase()
    calls.push(`${method} ${url}`)
    return route(url, method)
  }
  g.fetch = stubFetch
  window.fetch = stubFetch

  const { mount } = await import(`file://${entry.replace(/\\/g, '/')}`)
  const container = window.document.getElementById('app')
  mount(container)

  const q = (sel) => window.document.querySelector(sel)
  const qa = (sel) => Array.from(window.document.querySelectorAll(sel))
  const click = (el) => {
    if (!el) throw new Error('click: 元素不存在')
    el.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true, view: window }))
  }
  const txt = (sel) => (q(sel)?.textContent || '').replace(/\s+/g, ' ').trim()

  try {
    await waitFor('App 挂载', () => container.children.length > 0)
    record('App 挂载成功', true, `#app 子节点 ${container.children.length} 个`)

    const btn = await waitFor('首页按钮', () => q('[data-test="go-logic-platform"]'))
    record('首页有「业务逻辑分析平台 →」入口', !!btn, txt('[data-test="go-logic-platform"]'))
    click(btn)

    await waitFor('平台根节点', () => q('[data-test="logic-platform"]'))
    record('顶层视图 logic-platform 渲染', true)
    record('六步流程可见', qa('[data-test="logic-stage-step"]').length === 6, qa('[data-test="logic-stage-step"]').map((e) => e.getAttribute('data-stage')).join(' → '))
    record('口径立场横幅可见', !!q('[data-test="logic-mode-banner"]'), txt('[data-test="logic-mode-banner"]').slice(0, 60))

    // ---- 投入项目 ----
    await waitFor('项目卡片', () => q('[data-test="logic-project-card"]'))
    record('投入项目：卡片列表渲染', qa('[data-test="logic-project-card"]').length === 1, q('[data-test="logic-project-card"]').getAttribute('data-project-id'))
    record('上传区复用 .upload-zone', !!q('[data-test="logic-upload-zone"]')?.classList.contains('upload-zone'))
    click(q('[data-test="logic-project-card"]'))

    // ---- 大小分析 ----
    await waitFor('大小报告', () => q('[data-test="logic-size"]'))
    record('进入大小分析', q('[data-test="logic-platform"]').getAttribute('data-stage') === 'size')
    record('复杂度徽章复用既有组件', !!q('[data-test="logic-size"] [data-test="complexity-badge"]'), txt('[data-test="logic-size"] [data-test="complexity-badge"]'))
    const rows = qa('[data-test="logic-structure-row"]')
    record('结构表含 source 列', rows.length === 2 && rows.every((r) => !!r.getAttribute('data-source')), rows.map((r) => `${r.getAttribute('data-row-key')}=${r.getAttribute('data-source')}`).join(', '))
    record('每一项都带来源徽章与口径说明', qa('[data-test="logic-structure-source"]').length === 2 && txt('[data-test="logic-structure-row"]').includes('空行与注释计入'))
    record('定级依据可见', qa('[data-test="logic-level-basis"] li').length === 2)
    record('分流策略可见', !!q('[data-test="logic-tier"]') && qa('[data-test="logic-tier-budget"]').length === 3, txt('[data-test="logic-tier"] .text-lg') )
    record('tier.caveat 原样显示', (txt('[data-test="logic-tier-caveat"]') || '').includes('工程常数'))
    record('size caveats 可折叠可见', !!q('[data-test="logic-size-caveats"]') && qa('[data-test="logic-caveat-item"]').length >= 1)
    click(q('[data-test="logic-to-sections"]'))

    // ---- 板块看板 ----
    await waitFor('板块看板', () => q('[data-test="logic-board"]'))
    const cards = qa('[data-test="logic-section-card"]')
    record('板块看板网格渲染', cards.length === 2, cards.map((c) => c.getAttribute('data-section-id')).join(', '))
    record('截断可见（课程预算 1/3）', qa('[data-test="logic-truncation-item"]').length >= 1, txt('[data-test="logic-truncation-item"]'))
    record('卡片带核心度与课程覆盖计数', !!q('[data-test="logic-section-core"]') && qa('[data-test="logic-section-walkthrough-count"]').length === 2, txt('[data-test="logic-section-walkthrough-count"]'))
    click(cards[0])

    // ---- 板块分析 ----
    await waitFor('板块分析', () => q('[data-test="logic-section"]'))
    record('板块分析渲染（走 /sections/{id} 接口）', calls.some((c) => c.includes('/sections/sec_read')), calls.filter((c) => c.includes('/sections')).join(' | '))
    record('「不负责什么」独立突出', qa('[data-test="logic-section-does-not"] [data-test="logic-does-not-item"]').length === 2, txt('[data-test="logic-section-does-not"] li'))
    record('能力点列表渲染', qa('[data-test="logic-capability"]').length === 2)
    const reasons = qa('[data-test="logic-importance-reasons"]')
    record('排序理由可解释（非黑箱分数）', reasons.length === 2 && txt('[data-test="logic-importance-reasons"]').includes('参与 3 条业务流程'), txt('[data-test="logic-importance-reasons"] li'))
    record('原始 4 维信号 + 明确"不压成分数"', !!q('[data-test="logic-importance-raw"]') && txt('[data-test="logic-importance-raw"]').includes('不把它压成一个分数'))
    record('成员行号可点（证据跳转入口）', qa('[data-test="logic-member-evidence"]').length === 2, txt('[data-test="logic-member-evidence"]'))
    record('可进入学习的能力点有按钮', qa('[data-test="logic-walkthrough-start"]').length === 1)
    record('超出预算的能力点显示原文原因', qa('[data-test="logic-walkthrough-beyond-budget"]').length === 1, txt('[data-test="logic-walkthrough-beyond-budget"]').slice(0, 80))

    // 证据跳转 → SourceViewerModal
    click(q('[data-test="logic-member-evidence"]'))
    await waitFor('源码弹窗', () => q('.source-viewer-modal'))
    record('证据跳转打开复用的 SourceViewerModal', txt('.source-viewer-modal .font-mono').includes('dotenv/main.py'), calls.filter((c) => c.includes('/logic-platform/python_dotenv/source')).join(' | '))
    click(window.document.querySelector('.source-viewer-modal button'))

    // ---- 沉浸式讲稿 ----
    click(q('[data-test="logic-walkthrough-start"]'))
    await waitFor('沉浸式讲稿', () => q('[data-test="immersive-lesson"]'))
    record('讲稿按契约挂载（另一位工程师的组件）', qa('[data-test="lesson-segment"]').length === 1, txt('[data-test="immersive-lesson"] h2'))
    record('render.header_format 字面量被使用', txt('[data-test="segment-header"]') === '第 1 段：准备工作（84-87 行）', txt('[data-test="segment-header"]'))
    record('被拦截的断言仍显示且标红', !!q('[data-test="logic-claim-intercepted"]'), txt('[data-test="logic-claim-intercepted"]'))
    record('ClaimBadge 显示置信度/生成方', !!q('[data-test="logic-claim-badge"]') && !!q('[data-test="claim-source-badge"]'))

    // ---- 反幻觉面板 ----
    await waitFor('反幻觉面板', () => q('[data-test="logic-verification-panel"]'))
    record('反幻觉面板渲染', true)
    record('can_publish 未被当成"已发布"', q('[data-test="logic-publish-gate"]').getAttribute('data-can-publish') === 'false' && txt('[data-test="logic-publish-gate"]').includes('尚未发布'))
    record('blocking_issues 常驻可见', txt('[data-test="logic-verification-blocking"]').includes('尚未经教师确认'))
    record('校验失败项排在前面且带 file:line/detail', qa('[data-test="logic-check"]')[0].getAttribute('data-status') === 'fail', `${qa('[data-test="logic-check"]')[0].getAttribute('data-check-id')} · ${txt('[data-test="logic-check-location"]')} · ${txt('[data-test="logic-check-detail"]')}`)
    record('被拦截的断言 id 照原样列出', txt('[data-test="logic-verification-rejected"]').includes('claim_bad'))
    record('人工审核 stale 状态显眼', !!q('[data-test="logic-review-stale"]'), txt('[data-test="logic-review-stale"]'))
    record('讲解层状态如实（默认关闭）', q('[data-test="logic-narration-status"]').getAttribute('data-enabled') === 'false' && txt('[data-test="logic-narration-status"]').includes('平台默认关闭'))
    record('generated_by 显示为规则引擎', txt('[data-test="logic-generated-by"]') === '规则引擎', txt('[data-test="logic-generated-by"]'))

    // 重新校验
    click(q('[data-test="logic-reverify"]'))
    await waitFor('校验结论渲染', () => txt('[data-test="logic-verify-conclusion"]').includes('机械复核未通过'))
    record('「重新校验」调用 POST verify 并显示结论', calls.some((c) => c.startsWith('POST') && c.includes('/verify')), txt('[data-test="logic-verify-conclusion"]'))

    // 讲解层请求 → 503 原文
    click(q('[data-test="logic-narration-attempt"]'))
    await waitFor('讲解 503 提示', () => q('[data-test="logic-narration-notice"]'))
    record('503 的 detail 原样显示（未被隐藏）', txt('[data-test="logic-narration-notice"]').includes('平台默认关闭它'))

    record('没有出现"AI 智能分析/准确率"这类话术', !/AI 智能分析|分析准确率|自动发现核心业务/.test(window.document.body.textContent || ''))
  } catch (e) {
    record('流程走查异常', false, e?.message || String(e))
  }

  const failed = results.filter((r) => !r.ok)
  console.log(`\n=== ${results.length - failed.length}/${results.length} 通过 ===`)
  if (failed.length) {
    console.log('失败项：')
    for (const f of failed) console.log(` - ${f.name}: ${f.detail}`)
  }
  console.log(`\n[API 调用 ${calls.length} 次]`)
  process.exit(failed.length ? 1 : 0)
}

main()
