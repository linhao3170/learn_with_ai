/**
 * 证据折叠自查（真实 DOM + 真实后端载荷）
 * ==========================================
 * 它盯的是"证据折叠一轮"这一层**行为**，不是像素：
 *   1. **口径说明**：摘要常驻可见；完整说明默认收起**但内容仍在 DOM 里**；点得开。
 *   2. **逐条证据**：默认收起时证据按钮**一条不少地存在于 DOM 里**；点开后仍能跳源码；
 *      教师标注按钮仍在（折叠不许把流程吃掉）；**被拦截的断言默认展开**（失败不许藏）。
 *   3. **反幻觉面板**：0 失败时逐项明细默认收起；**有失败时默认展开**；
 *      计数徽章 / 发布闸门 / 拦截提示常驻；被拦截 id 清单收起但 id 仍在 DOM 里。
 *
 * 为什么断言"收起 ≠ 删掉"：这是本仓库的硬纪律（静默删除等于把幻觉藏起来）。
 * 折叠如果写成 `v-if`，证据就从 DOM 里消失了 —— 所以本脚本自带一个
 * **负向对照组件**（`NegativeControlFold`，就是用 `v-if` 收起的错误写法），
 * 同一条断言在它身上**必须 FAIL**，否则这条断言等于永远绿。
 *
 * 前置（与总验收里的其它前端检查一致）：
 *   1) 后端在 `--api-base`（默认 http://127.0.0.1:8000）；
 *   2) 已构建走查 bundle：
 *      `cd frontend && node node_modules/vite/bin/vite.js build --config vite.smoke.config.js`
 *   —— 本脚本**自带**前端 dev server 不需要：讲稿载荷直接从后端取，
 *      页面渲染在 jsdom 里完成，不加载样式（只断言 DOM 行为）。
 *
 * 用法：
 *   node scripts/check_evidence_fold.mjs
 *   node scripts/check_evidence_fold.mjs --api-base http://127.0.0.1:8000
 *   node scripts/check_evidence_fold.mjs --lesson <讲稿 JSON 路径>   # 跳过后端，用现成载荷
 *
 * 退出码：0 = 全部 PASS；1 = 有 FAIL 或前置缺失。
 */

import { readdirSync, existsSync, readFileSync, writeFileSync, mkdtempSync } from 'node:fs'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { createRequire } from 'node:module'
import { tmpdir } from 'node:os'
import path from 'node:path'

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const FRONTEND = path.join(REPO, 'frontend')
const SMOKE_DIST = path.join(FRONTEND, '.smoke-dist')
const DEMO_FILE = path.join(REPO, 'demo', 'student_manager.py')

const argv = process.argv.slice(2)
const argOf = (name, fallback) => {
  const eq = argv.find((a) => a.startsWith(`--${name}=`))
  if (eq) return eq.slice(`--${name}=`.length)
  const idx = argv.indexOf(`--${name}`)
  if (idx >= 0 && argv[idx + 1] && !argv[idx + 1].startsWith('--')) return argv[idx + 1]
  return fallback
}
const API_BASE = argOf('api-base', 'http://127.0.0.1:8000')
const LESSON_FILE = argOf('lesson', '')

// jsdom 装在前端的 devDependencies 下，从本文件所在目录 import 解析不到 —— 以前端为基准解析。
const frontendRequire = createRequire(path.join(FRONTEND, 'package.json'))
let JSDOM
try {
  ;({ JSDOM } = frontendRequire('jsdom'))
} catch {
  console.error('找不到 jsdom。请先安装：cd frontend; npm install')
  process.exit(2)
}

const results = []
const record = (name, ok, detail = '') => results.push({ name, ok: !!ok, detail: String(detail).slice(0, 200) })
const tick = (ms = 30) => new Promise((r) => setTimeout(r, ms))

function findEntry() {
  if (!existsSync(SMOKE_DIST)) return null
  const entryFile = path.join(SMOKE_DIST, 'app.js')
  if (existsSync(entryFile)) return entryFile
  const chunk = readdirSync(SMOKE_DIST).find((f) => /^smoke-entry-.*\.js$/.test(f))
  return chunk ? path.join(SMOKE_DIST, chunk) : null
}

/**
 * 取一份**真实讲稿载荷**：投入 demo 项目 → 取第一个能力点的讲稿。
 * 载荷是真的（后端规则引擎 + 校验器产出），所以断言里的期望值（证据条数 / 检查项条数）
 * 全部**从载荷里数出来**，一个都不写死 —— 写死的数字会在数据变化那天变成假失败。
 */
async function fetchRealLesson() {
  if (LESSON_FILE) {
    console.log(`载荷：使用现成文件 ${LESSON_FILE}`)
    return JSON.parse(readFileSync(LESSON_FILE, 'utf8'))
  }
  if (!existsSync(DEMO_FILE)) {
    console.error(`找不到演示源码：${DEMO_FILE}`)
    process.exit(2)
  }
  const form = new FormData()
  form.append('file', new Blob([readFileSync(DEMO_FILE)]), path.basename(DEMO_FILE))
  const analyzeResp = await fetch(`${API_BASE}/api/logic-platform/analyze`, { method: 'POST', body: form })
  if (!analyzeResp.ok) {
    console.error(`后端 analyze 失败：HTTP ${analyzeResp.status}（后端没起来？）`)
    process.exit(2)
  }
  const analysis = await analyzeResp.json()
  const projectId = analysis.project_id
  const capabilityId = analysis.sections?.sections?.[0]?.capabilities?.[0]?.capability_id
  if (!projectId || !capabilityId) {
    console.error('后端没有返回可用的 project_id / capability_id')
    process.exit(2)
  }
  const lessonResp = await fetch(`${API_BASE}/api/logic-platform/${projectId}/lessons/${capabilityId}`)
  if (!lessonResp.ok) {
    console.error(`后端取讲稿失败：HTTP ${lessonResp.status}`)
    process.exit(2)
  }
  const lesson = await lessonResp.json()
  console.log(`载荷：真实后端 ${API_BASE} · ${projectId} · ${capabilityId}`)

  // 留一份载荷到临时目录，便于复核这次断言到底跑在什么数据上（不进仓库）。
  const dir = mkdtempSync(path.join(tmpdir(), 'lwai_evidence_'))
  const file = path.join(dir, 'lesson.json')
  writeFileSync(file, JSON.stringify(lesson, null, 2), 'utf8')
  console.log(`      本次载荷副本：${file}`)
  return lesson
}

/** 装一个最小的 DOM 环境（只用真实 DOM 行为，不加载样式）。 */
async function bootDom() {
  const dom = new JSDOM('<!doctype html><html><body></body></html>', {
    url: 'http://127.0.0.1:5173/',
    pretendToBeVisual: true,
  })
  const { window } = dom
  const g = globalThis
  g.window = window
  g.document = window.document
  g.location = window.location
  try {
    Object.defineProperty(g, 'navigator', { value: window.navigator, writable: true, configurable: true })
  } catch { /* Node 22 的 navigator 是不可配置的 getter；Vue 在 jsdom 里不依赖它 */ }
  g.requestAnimationFrame = window.requestAnimationFrame.bind(window)
  g.cancelAnimationFrame = window.cancelAnimationFrame.bind(window)
  for (const key of [
    'HTMLElement', 'HTMLInputElement', 'Element', 'Node', 'Event', 'MouseEvent', 'CustomEvent',
    'MutationObserver', 'SVGElement', 'DocumentFragment', 'NodeList', 'Text', 'Comment',
  ]) {
    const value = window[key]
    if (!value) continue
    try { Object.defineProperty(g, key, { value, writable: true, configurable: true }) } catch { /* ignore */ }
  }
  return { window, document: window.document }
}

async function main() {
  const entry = findEntry()
  if (!entry) {
    console.error('找不到走查 bundle。请先运行：')
    console.error('  cd frontend; node node_modules/vite/bin/vite.js build --config vite.smoke.config.js')
    process.exit(2)
  }

  const { window, document } = await bootDom()
  const mod = await import(pathToFileURL(entry).href)
  const { mountInto, ImmersiveLesson, VerificationPanel } = mod
  if (!mountInto || !ImmersiveLesson || !VerificationPanel) {
    console.error('走查 bundle 里没有证据折叠自查所需的导出（frontend/smoke-entry.js 是不是被改回去了？）')
    process.exit(2)
  }

  const lesson = await fetchRealLesson()

  const host = () => {
    const el = document.createElement('div')
    document.body.appendChild(el)
    return el
  }
  const q = (root, sel) => root.querySelector(sel)
  const qa = (root, sel) => Array.from(root.querySelectorAll(sel))
  const click = (el) => el.dispatchEvent(new window.MouseEvent('click', { bubbles: true }))
  /** 折叠区根节点选择器：排掉它自己的 `-toggle` / `-body` 子元素。 */
  const FOLD_ROOT = '[data-test^="claim-fold-"]:not([data-test$="-toggle"]):not([data-test$="-body"])'

  const claimCount = (l) => (l.segments || []).reduce((acc, s) => acc + (s.must_remember || []).length, 0)
  const claimEvidenceCount = (l) =>
    (l.segments || []).reduce(
      (acc, s) => acc + (s.must_remember || []).reduce((n, c) => n + (c.evidence || []).length, 0),
      0,
    )

  // =========================================================================
  // A / B：沉浸式讲稿（口径说明 + 逐条断言证据）
  // =========================================================================
  {
    const el = host()
    const { events } = mountInto(ImmersiveLesson, { lesson }, el)
    await tick()

    const note = q(el, '[data-test="lesson-evidence-note"]')
    const summaryEl = q(el, '[data-test="lesson-evidence-note-summary"]')
    const noteBody = q(el, '[data-test="lesson-evidence-note-body"]')
    record('A1 讲稿上有证据口径说明', !!note)
    record('A2 摘要在抽屉体之外（常驻可见）',
      !!summaryEl && !summaryEl.closest('[data-test="lesson-evidence-note-body"]')
        && summaryEl.textContent.trim().length > 20,
      summaryEl ? summaryEl.textContent.trim().slice(0, 50) : 'missing')
    record('A3 完整说明默认收起', note?.getAttribute('data-open') === 'false',
      `data-open=${note?.getAttribute('data-open')}`)
    record('A4 收起时说明内容仍在 DOM 里（不是 v-if）',
      (noteBody?.textContent.replace(/\s+/g, '').length || 0) > 300,
      `body 文本 ${noteBody?.textContent.replace(/\s+/g, '').length || 0} 字`)
    click(q(el, '[data-test="lesson-evidence-note-toggle"]'))
    await tick()
    record('A5 说明点得开', note?.getAttribute('data-open') === 'true',
      `data-open=${note?.getAttribute('data-open')}`)

    const folds = qa(el, FOLD_ROOT)
    const claims = claimCount(lesson)
    record('B1 每条断言都有一个折叠区', folds.length === claims, `folds=${folds.length} claims=${claims}`)
    record('B2 折叠区默认收起', folds.length > 0 && folds.every((f) => f.getAttribute('data-open') === 'false'),
      folds.map((f) => f.getAttribute('data-open')).join(','))
    record('B3 收起时证据按钮仍在 DOM 里且条数不变',
      qa(el, '[data-test="claim-evidence"]').length === claimEvidenceCount(lesson),
      `dom=${qa(el, '[data-test="claim-evidence"]').length} 期望=${claimEvidenceCount(lesson)}`)
    record('B4 教师标注按钮仍在 DOM 里（折叠不吃流程）',
      qa(el, '[data-test="claim-review-actions"]').length === claims,
      `actions=${qa(el, '[data-test="claim-review-actions"]').length} claims=${claims}`)

    const firstFold = folds[0]
    click(q(firstFold, '[data-test$="-toggle"]'))
    await tick()
    record('B5 折叠区点得开', firstFold?.getAttribute('data-open') === 'true',
      `data-open=${firstFold?.getAttribute('data-open')}`)

    const evBtn = q(firstFold, '[data-test="claim-evidence"]')
    if (evBtn) click(evBtn)
    await tick()
    const openEv = events.find((e) => e.name === 'open-source')
    record('B6 证据按钮仍能跳源码（open-source 带 file/start_line）',
      !!openEv && String(openEv.args[0] || '').length > 0 && Number(openEv.args[1]) > 0,
      openEv ? JSON.stringify(openEv.args) : 'no event')

    // 徽章是折叠区的**兄弟节点**（刻意常驻），所以要在断言那一行里找。
    const claimRow = firstFold?.closest('[data-test="segment-bullet"]')
    const confirmBtn = qa(firstFold, '[data-test="claim-review-actions"] button')[0]
    if (confirmBtn) click(confirmBtn)
    await tick()
    const decisionBadge = claimRow && q(claimRow, '[data-test="claim-review-decision"]')
    record('B7 教师"确认"仍生效（徽章常驻回显）', !!decisionBadge,
      decisionBadge?.textContent.trim() || 'missing')

    // 被拦截的断言：折叠区必须默认展开（失败不许藏在一次点击之后）
    const broken = JSON.parse(JSON.stringify(lesson))
    if (broken.segments?.[0]?.must_remember?.[0]) {
      broken.segments[0].must_remember[0].verified = false
      broken.segments[0].must_remember[0].reject_reason = '未通过确定性校验：引用的代码或行号与磁盘源码不符'
    }
    const el2 = host()
    mountInto(ImmersiveLesson, { lesson: broken }, el2)
    await tick()
    const brokenFolds = qa(el2, FOLD_ROOT)
    record('B8 被拦截的断言折叠区默认展开',
      brokenFolds[0]?.getAttribute('data-open') === 'true',
      `data-open=${brokenFolds[0]?.getAttribute('data-open')}`)
    record('B9 被拦截徽章仍常驻（没有随证据一起折叠）',
      !!q(el2, '[data-test="bullet-intercepted"]') && !!q(el2, '[data-test="logic-claim-intercepted"]'))
  }

  // =========================================================================
  // C：反幻觉面板（逐项校验明细 + 被拦截清单）
  // =========================================================================
  {
    const el = host()
    mountInto(VerificationPanel, { lesson }, el)
    await tick()

    const totalChecks = lesson.verification?.checks?.length || 0
    const fold = q(el, '[data-test="logic-checks-fold"]')
    record('C1 逐项检查明细收进折叠区', !!fold && !!q(el, '[data-test="logic-checks-fold-body"]'))
    record('C2 0 失败时默认收起',
      fold?.getAttribute('data-open') === 'false' && Number(lesson.verification?.counts?.failed || 0) === 0,
      `data-open=${fold?.getAttribute('data-open')} failed=${lesson.verification?.counts?.failed}`)
    record('C3 收起时检查项仍在 DOM 里且条数不变',
      qa(el, '[data-test="logic-check"]').length === totalChecks,
      `dom=${qa(el, '[data-test="logic-check"]').length} 期望=${totalChecks}`)
    record('C4 计数徽章常驻（收起也知道几项通过 / 失败）',
      qa(el, '[data-test="logic-verification-counts"] [data-count-key]').length > 0)
    record('C5 发布闸门常驻', !!q(el, '[data-test="logic-publish-gate"]'))
    record('C6 面板口径：摘要常驻 + 说明收起但内容在 DOM 里', (() => {
      const n = q(el, '[data-test="logic-verification-note"]')
      const s = q(el, '[data-test="logic-verification-note-summary"]')
      const b = q(el, '[data-test="logic-verification-note-body"]')
      return !!n && n.getAttribute('data-open') === 'false'
        && !!s && !s.closest('[data-test="logic-verification-note-body"]')
        && (b?.textContent.replace(/\s+/g, '').length || 0) > 300
    })())
    click(q(el, '[data-test="logic-checks-fold-toggle"]'))
    await tick()
    record('C7 明细点得开', fold?.getAttribute('data-open') === 'true',
      `data-open=${fold?.getAttribute('data-open')}`)

    // 合成一份"有失败"的载荷：证明失败时明细**默认展开**
    const failing = JSON.parse(JSON.stringify(lesson))
    failing.verification.checks[0].status = 'fail'
    failing.verification.checks[0].detail = '证据摘录与磁盘源码不一致（合成负向载荷，只用于验证默认展开）'
    failing.verification.counts.failed = 1
    failing.verification.counts.passed = Math.max(0, Number(failing.verification.counts.passed || 1) - 1)
    failing.verification.rejected_claim_ids = ['synthetic_claim_1']
    failing.verification.rejected_segment_ids = ['synthetic_segment_1']
    failing.review.blocking_issues = ['1 条断言未通过校验：synthetic_claim_1']
    const el3 = host()
    mountInto(VerificationPanel, { lesson: failing }, el3)
    await tick()
    const fold3 = q(el3, '[data-test="logic-checks-fold"]')
    record('C8 有失败时明细默认展开（失败不许藏在点击之后）',
      fold3?.getAttribute('data-open') === 'true', `data-open=${fold3?.getAttribute('data-open')}`)
    record('C9 失败项自己也在 DOM 里且标 fail',
      !!q(el3, '[data-test="logic-check"][data-status="fail"]'))
    record('C10 拦截提示常驻（不随 id 清单一起收起）',
      !!q(el3, '[data-test="logic-verification-blocking"]') && !!q(el3, '[data-test="logic-verification-rejected"]'))
    const rejFold = q(el3, '[data-test="logic-rejected-ids-fold"]')
    const rejBody = q(el3, '[data-test="logic-rejected-ids-fold-body"]')
    record('C11 被拦截 id 清单收起但 id 仍在 DOM 里',
      !!rejFold && rejFold.getAttribute('data-open') === 'false'
        && (rejBody?.textContent || '').includes('synthetic_claim_1')
        && (rejBody?.textContent || '').includes('synthetic_segment_1'))
    click(q(el3, '[data-test="logic-rejected-ids-fold-toggle"]'))
    await tick()
    record('C12 拦截清单点得开', rejFold?.getAttribute('data-open') === 'true')
  }

  // =========================================================================
  // 负向对照：用 `v-if` 收起的对照组件，同一条断言必须 FAIL
  // =========================================================================
  {
    const el = host()
    mod.mountNegativeControl(el)
    await tick()
    const body = q(el, '[data-test="evidence-fold-body"]')
    const stillInDom = !!body && body.textContent.includes('对照内容')
    record('N1 负向对照：v-if 收起会把内容从 DOM 里摘掉（同一条断言应 FAIL）', stillInDom === false,
      stillInDom ? '意外通过 —— 断言抓不到删除，需重写断言' : '如预期 FAIL：收起后 body 不存在')
  }

  const passed = results.filter((r) => r.ok).length
  for (const r of results) {
    console.log(`${r.ok ? 'PASS' : 'FAIL'}  ${r.name}${r.detail ? '  |  ' + r.detail : ''}`)
  }
  console.log(`\nEVIDENCE_FOLD_RESULT: ${passed}/${results.length}`)
  process.exit(passed === results.length ? 0 : 1)
}

main().catch((err) => {
  console.error('证据折叠自查异常终止：', err)
  process.exit(1)
})
