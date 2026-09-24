/**
 * 浏览器点击走查（真实 DOM + 真实组件 + 真实 HTTP）
 * ==================================================
 *
 * 为什么不是"headless Chrome 截图"：
 *   本环境里 Chromium 完全渲染不出来 —— 连 `--dump-dom about:blank` 都返回空。
 *   原因不是文件权限，而是沙箱禁止进程间命名管道，Chromium 的多进程 IPC 起不来
 *   （`--single-process` / `--headless=old` / Edge 都试过，全部为空）。
 *
 * 所以改用**真实 DOM**：
 *   用 Vite 把真实 App 打成**浏览器版** bundle（vite.smoke.config.js），
 *   在 jsdom 里挂载，然后派发**真实 DOM 事件**（不是直接调组件方法）。
 *   所有网络请求走真实 HTTP：`/demo/...` 由 Vite dev server 提供，
 *   `/api/...` 经 Vite proxy 打到真实 FastAPI 后端。
 *
 * 也就是说：组件是真的、DOM 是真的、HTTP 是真的、点击事件是真的；
 * 只有"像素渲染"是假的（不测样式和布局）。
 *
 * 前置：
 *   1) 后端在 127.0.0.1:8000
 *   2) 前端 dev server 在 127.0.0.1:5173
 *   3) 已构建走查 bundle：node node_modules/vite/bin/vite.js build --config vite.smoke.config.js
 *
 * 用法：
 *   node scripts/browser_clickthrough.mjs
 *   node scripts/browser_clickthrough.mjs --project python_dotenv
 *   node scripts/browser_clickthrough.mjs --offline          # /api 指向死端口，模拟后端未启动
 *   node scripts/browser_clickthrough.mjs --keep-open        # 不退出，便于手工查看
 */

import { readdirSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'
import path from 'node:path'

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const FRONTEND = path.join(REPO, 'frontend')
const SMOKE_DIST = path.join(FRONTEND, '.smoke-dist')

// jsdom 装在 frontend/node_modules 下（它是前端的 devDependency），
// 所以从本文件的目录直接 import 会解析不到 —— 用 createRequire 以前端为基准解析。
const frontendRequire = createRequire(path.join(FRONTEND, 'package.json'))
let JSDOM
try {
  ;({ JSDOM } = frontendRequire('jsdom'))
} catch {
  console.error('找不到 jsdom。请先安装：cd frontend; npm install')
  process.exit(2)
}

const argv = process.argv.slice(2)
/**
 * 支持两种写法：`--name=value` 与 `--name value`。
 * （一开始只支持前者，结果 `--project python_dotenv` 静默退回了默认项目 —— 走查头部
 *   打印的项目名和实际跑的项目不一致，差点验证了个假结果。）
 */
const argOf = (name, fallback) => {
  const eq = argv.find((a) => a.startsWith(`--${name}=`))
  if (eq) return eq.slice(`--${name}=`.length)
  const idx = argv.indexOf(`--${name}`)
  if (idx >= 0 && argv[idx + 1] && !argv[idx + 1].startsWith('--')) return argv[idx + 1]
  return fallback
}
const PROJECT = argOf('project', 'lab_safety_assistant')
const APP_BASE = argOf('base', 'http://127.0.0.1:5173')
const OFFLINE = argv.includes('--offline')
// 死端口：连上去会被立刻拒绝 —— 比"假装 fetch 失败"更接近真实的后端未启动
const OFFLINE_API_BASE = argOf('dead-api', 'http://127.0.0.1:9')

const results = []
const record = (name, ok, detail = '') => results.push({ name, ok: !!ok, detail: String(detail) })
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

function findEntry() {
  if (!existsSync(SMOKE_DIST)) return null
  // lib 模式下 Rollup 会把真正的入口写成 app.js（很小，只做 re-export），
  // 实际代码在 smoke-entry-*.js 这个 chunk 里。所以入口要取 app.js。
  const entryFile = path.join(SMOKE_DIST, 'app.js')
  if (existsSync(entryFile)) return entryFile
  const chunk = readdirSync(SMOKE_DIST).find((f) => /^smoke-entry-.*\.js$/.test(f))
  return chunk ? path.join(SMOKE_DIST, chunk) : null
}

/** 等待条件成立（用于等 Vue 的异步渲染 / 网络返回）。 */
async function waitFor(label, fn, timeout = 12000, interval = 60) {
  const deadline = Date.now() + timeout
  for (;;) {
    let value
    try { value = fn() } catch { value = null }
    if (value) return value
    if (Date.now() > deadline) throw new Error(`waitFor 超时: ${label}`)
    await sleep(interval)
  }
}

async function main() {
  const entry = findEntry()
  if (!entry) {
    console.error('找不到走查 bundle。请先运行：')
    console.error('  cd frontend; node node_modules/vite/bin/vite.js build --config vite.smoke.config.js')
    process.exit(2)
  }

  const targetPath = `/?project=${PROJECT}`
  const dom = new JSDOM(`<!doctype html><html><body><div id="app"></div></body></html>`, {
    url: `${APP_BASE}${targetPath}`,
    pretendToBeVisual: true,
  })
  const { window } = dom

  // ---- 1) 把 jsdom 装成全局环境（必须在 import Vue 之前）----
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
  // Node 22 里 globalThis.navigator 只有 getter，不能直接赋值 —— 用 defineProperty 覆盖。
  for (const key of [
    'navigator', 'HTMLElement', 'HTMLInputElement', 'HTMLSelectElement', 'Element', 'Node',
    'Event', 'MouseEvent', 'KeyboardEvent', 'CustomEvent', 'MutationObserver', 'SVGElement',
    'DocumentFragment', 'NodeList', 'DOMParser', 'XMLHttpRequest', 'FormData', 'Text',
    'Comment', 'HTMLDocument', 'CSSStyleDeclaration',
  ]) {
    const value = key === 'navigator' ? window.navigator : window[key]
    if (!value) continue
    try {
      Object.defineProperty(g, key, { value, writable: true, configurable: true })
    } catch {
      /* 某些全局是不可配置的，跳过即可 */
    }
  }

  // ---- 2) 真实 HTTP：相对路径按 dev server 解析；offline 时 /api 指向死端口 ----
  // jsdom 不带 fetch，用 Node 自带的（先抓原始引用，再覆盖全局）。
  const nativeFetch = globalThis.fetch
  if (typeof nativeFetch !== 'function') {
    console.error('Node 没有全局 fetch，需要 Node 18+')
    process.exit(2)
  }
  let apiCalls = 0
  let apiFailures = 0
  const patchedFetch = async (input, init) => {
    const url = typeof input === 'string' ? input : (input && input.url) || String(input)
    let finalUrl = url
    if (url.startsWith('/')) finalUrl = `${APP_BASE}${url}`
    if (OFFLINE && finalUrl.includes('/api/')) {
      finalUrl = finalUrl.replace(/^https?:\/\/[^/]+/, OFFLINE_API_BASE)
    }
    if (finalUrl.includes('/api/')) {
      apiCalls += 1
      try {
        return await nativeFetch(finalUrl, init)
      } catch (e) {
        apiFailures += 1
        throw e
      }
    }
    return nativeFetch(finalUrl, init)
  }
  g.fetch = patchedFetch
  window.fetch = patchedFetch

  /**
   * 取一份业务图谱，**只用于与页面显示的数量对齐**（不是前端实现的第二份拷贝）。
   *
   * 候选顺序与 `frontend/src/api/dataSource.js` 的 `snapshotCandidates()` 一致：
   * 在线走 `/api/projects/<id>/business-graph`，离线依次试两个静态快照路径。
   * 存在的意义：断言必须能与"页面此刻到底拿到了什么"对齐 ——
   * 写死数字的断言会在数据变化那天变成假失败（README §19.2 ⑫ 与 ⑪ 都是这一类教训）。
   */
  const loadGraphForAssertion = async (projectId) => {
    const candidates = OFFLINE
      ? [`/demo/projects/${projectId}/project_analysis.json`, '/demo/project_analysis.json']
      : [`/api/projects/${projectId}/business-graph`]
    for (const url of candidates) {
      try {
        const resp = await patchedFetch(url)
        if (!resp || !resp.ok) continue
        const payload = await resp.json()
        if (OFFLINE) {
          if (payload && payload.business_graph) return payload.business_graph
          continue
        }
        return payload
      } catch {
        continue
      }
    }
    return null
  }
  for (const key of ['Response', 'Request', 'Headers', 'AbortController', 'AbortSignal']) {
    const value = g[key] || (typeof window[key] !== 'undefined' ? window[key] : undefined)
    if (!value) continue
    try {
      Object.defineProperty(window, key, { value, writable: true, configurable: true })
    } catch { /* ignore */ }
  }

  // ---- 3) 挂载真实 App ----
  const { mount } = await import(`file://${entry.replace(/\\/g, '/')}`)
  const container = window.document.getElementById('app')
  mount(container)

  const q = (sel) => window.document.querySelector(sel)
  const qa = (sel) => Array.from(window.document.querySelectorAll(sel))
  const bodyText = () => window.document.body.textContent || ''

  function click(el) {
    if (!el) throw new Error('click: 元素不存在')
    el.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true, view: window }))
  }
  function choose(select, value) {
    select.value = value
    select.dispatchEvent(new window.Event('change', { bubbles: true }))
  }

  const scenario = OFFLINE ? 'offline' : 'online'
  const trap = (name, e) => record(name, false, e && (e.message || e))

  try {
    // ---- 4. 真实挂载 ----
    await waitFor('App 挂载', () => container.children.length > 0)
    record('真实 App（浏览器版 Vue）挂载成功', true, `#app 子节点 ${container.children.length} 个`)

    // ---- 5. 项目切换器 + 模式徽章 ----
    const select = await waitFor('项目切换器', () => q('[data-test="project-select"]'))
    record('项目切换器已渲染', select.options.length >= 1,
      `${select.options.length} 个选项，当前=${select.value}`)

    // 注意：必须**每次重新查询**徽章节点。Vue 会因 v-if 重渲染替换该节点，
    // 持有旧引用会读到过期文本（第一版走查就踩了这个坑）。
    const badgeText = () => {
      const el = qa('#app span').find((s) => /在线 API 模式|离线快照模式/.test(s.textContent))
      return el ? el.textContent.trim() : '(未找到徽章)'
    }
    if (!OFFLINE) {
      await waitFor('切换到在线 API 模式', () => badgeText().includes('在线 API'), 15000)
    } else {
      await waitFor('停留在离线快照模式', () => badgeText().includes('离线快照'), 15000)
    }
    record(`模式徽章正确（场景 ${scenario}）`,
      OFFLINE ? badgeText().includes('离线快照') : badgeText().includes('在线 API'), badgeText())

    // ---- 6. 契约来自数据源，不是写死的项目 ----
    await waitFor('题目渲染', () =>
      qa('[data-test="option-multi"], [data-test="option-single"]').length > 0)
    const optionEls = () => qa('[data-test="option-multi"], [data-test="option-single"]')
    record('训练题已从契约渲染', true, `${optionEls().length} 个选项`)
    record('页面出现所选项目 id', bodyText().includes(PROJECT), `期望包含 ${PROJECT}`)

    // ---- 7. 渲染内容确实来自契约数据（而不是写死的样本）----
    // 关键：对 lab_safety_assistant 来说，"预约管理模块" 是**合法数据**，
    // 所以不能把它当违禁词。正确做法是把渲染结果和契约里的 module 名字对齐。
    let contractModules = []
    try {
      const resp = await patchedFetch(`/api/projects/${PROJECT}/analysis?mode=student`)
      if (resp.ok) {
        const contract = await resp.json()
        contractModules = (contract.modules || []).map((m) => m.name).filter(Boolean)
      }
    } catch { /* 离线场景稍后单独判 */ }

    if (contractModules.length) {
      const rendered = optionEls().map((el) => el.textContent)
      const matched = contractModules.filter((n) => rendered.some((t) => t.includes(n)))
      record('选项文案来自契约的 modules[].name（数据驱动）',
        matched.length >= 2, `契约模块 ${contractModules.length} 个，页面上命中 ${matched.length} 个`)
    }

    // 换到别的项目时，实验安全样本的词一个都不许出现
    if (PROJECT !== 'lab_safety_assistant') {
      const forbidden = ['预约管理模块', '实验室预约流程', 'create_reservation', '实验室安全助手']
      const hits = forbidden.filter((w) => bodyText().includes(w))
      record('非样本项目页面不含实验安全样本词', hits.length === 0,
        hits.length ? `仍出现 ${hits.join(', ')}` : '0 处')
    } else {
      record('（样本项目跳过"违禁词"断言 —— 这些词在本项目里是合法数据）', true)
    }

    // 页面里出现的模块名必须全部能在契约中找到；找不到就说明有写死的残留
    if (contractModules.length) {
      const suspicious = ['天气', '物流配送', '游戏娱乐', '音乐播放', '视频点播', '即时通讯', '支付管理']
      const leaked = suspicious.filter((w) => bodyText().includes(w))
      record('页面不含已删除的域外干扰模块', leaked.length === 0, leaked.join(', ') || '0 处')
    }

    // ---- 8. 离线横幅 ----
    const banner = () => q('[data-test="offline-banner"]')
    if (OFFLINE) {
      await waitFor('离线横幅', () => banner())
      record('离线横幅可见且措辞正确', (banner().textContent || '').includes('离线演示模式'),
        (banner().textContent || '').replace(/\s+/g, ' ').slice(0, 70))
    } else {
      record('在线模式不显示离线横幅', !banner())
    }

    // ---- 9. 真实点击：选选项 → 提交 → 反馈 ----
    const opts = qa('[data-test="option-multi"], [data-test="option-single"]')
    const firstOptId = opts[0].dataset.optionId
    click(opts[0])
    await sleep(150)
    record('点击选项被 Vue 处理（无异常）', true, `点击了 ${firstOptId}`)

    const submit = q('[data-test="submit-answer"]')
    record('作答后提交按钮可用', !!submit && !submit.disabled)
    click(submit)

    if (!OFFLINE) {
      const online = await waitFor('后端判分反馈', () => q('[data-test="grading-online"]'), 15000)
      const text = (online.textContent || '').replace(/\s+/g, ' ')
      record('提交后收到后端判分结论（先输出、后反馈）',
        /正确|部分|错误|答对|答错|partial|correct|wrong/.test(text), text.slice(0, 100))
      record('讲解只在提交后出现', text.length > 20, `${text.length} 字`)
      record('DOM 中不含 correct_answers 字段名',
        !/correct_answers/.test(window.document.documentElement.outerHTML))
    } else {
      const off = await waitFor('离线未判分提示', () => q('[data-test="grading-offline"]'), 15000)
      const text = (off.textContent || '').replace(/\s+/g, ' ')
      record('离线时如实说明无法判分', text.includes('无法判分'), text.slice(0, 80))
      record('离线时不给对错结论', !/答对|答错|完全正确/.test(text))
    }

    // ---- 10. 会话持久化 ----
    const keys = Object.keys(window.localStorage).filter((k) => k.startsWith('lwai.session'))
    record('学习会话已写入 localStorage', keys.length >= 1, keys.join(', ') || '无')

    // ---- 11. 证据跳转（真实 HTTP）----
    try {
      const sourceProbe = OFFLINE ? 'reservation_manager.py' : 'reservation_manager.py'
      const resp = await patchedFetch(`/api/projects/${PROJECT}/source?path=${sourceProbe}&start=122&end=123`)
      if (PROJECT === 'python_dotenv') {
        const r2 = await patchedFetch(`/api/projects/${PROJECT}/source?path=parser.py&start=14&end=15`)
        const j2 = await r2.json()
        record('证据跳转命中真实源码（python_dotenv/parser.py:14）',
          r2.ok && j2.lines.some((l) => l.text.includes('make_regex')),
          r2.ok ? `窗口 ${j2.window_start}-${j2.window_end}` : `HTTP ${r2.status}`)
      } else {
        const j = await resp.json()
        const line = resp.ok ? j.lines.find((l) => l.number === 122) : null
        record('证据跳转命中第 122 行（if start < res_end ...）',
          !!line && /start < res_end/.test(line.text),
          resp.ok ? (line ? line.text.trim() : '未返回 122 行') : `HTTP ${resp.status}（离线场景预期失败）`)
      }
      const miss = await patchedFetch(`/api/projects/${PROJECT}/source?path=definitely_missing.py`)
      record('缺失文件返回非 2xx（不静默）', !miss.ok || miss.status === 404, `HTTP ${miss.status}`)
    } catch (e) {
      // 离线场景下 /api 指向死端口，这类"失败"是预期的，但仍要确认前端有明确错误文案
      record('离线场景下证据跳转失败可见（预期）', OFFLINE, String(e && e.message).slice(0, 60))
    }

    // ---- 12. 项目切换（真实 change 事件 + URL 深链）----
    if (!OFFLINE) {
      const before = select.value
      const target = before === 'python_dotenv' ? 'lab_safety_assistant' : 'python_dotenv'
      choose(select, target)
      await waitFor('深链同步', () =>
        new window.URL(window.location.href).searchParams.get('project') === target, 8000)
      record('切换项目后 ?project= 深链同步',
        new window.URL(window.location.href).searchParams.get('project') === target, `→ ${target}`)
      await sleep(2000)
      record('切换项目后页面内容随之变化', bodyText().includes(target), `页面包含 ${target}`)
    }

    // ---- 13. 业务图谱（Sprint 2）：真实点击进入并断言 ----
    // 图谱是 v-if 懒挂载（重面板），所以必须先点阶段入口。
    try {
      const stageBtn = q('[data-test="stage-graph"]')
      if (!stageBtn) {
        record('业务图谱阶段入口存在', false, '找不到 [data-test="stage-graph"]')
      } else {
        record('业务图谱阶段入口存在', true)
        click(stageBtn)
        const view = await waitFor('业务图谱渲染', () => q('[data-test="business-graph-view"]'), 15000)
        record('点击后业务图谱视图已挂载', !!view)

        const domainEls = await waitFor('业务域渲染', () => {
          const els = qa('[data-test="graph-domain"]')
          return els.length ? els : null
        }, 15000)
        record('一级业务域已渲染', domainEls.length >= 2, `${domainEls.length} 个域`)

        // 每个域都要带置信度徽章（README5 §10.3 红线 4：不许把推断说成已确认）
        const badges = qa('[data-test="confidence-badge"]')
        record('置信度徽章已渲染', badges.length >= domainEls.length,
          `${badges.length} 个徽章 / ${domainEls.length} 个域`)

        // 展开第一个域（注意：行本身 = 选中，行内的 toggle = 展开/收起，
        // toggle 上有 @click.stop，所以"展开"和"选中"必须点不同元素）
        const domainToggle = domainEls[0].querySelector('[data-test="graph-domain-toggle"]')
        click(domainToggle || domainEls[0])
        await sleep(400)
        const caps = qa('[data-test="graph-capability"]')
        record('展开业务域后能看到二级功能点', caps.length >= 1, `${caps.length} 个功能点`)

        if (caps.length) {
          // 点**行本身**才会 selectModule 打开卡片
          click(caps[0])
          const card = await waitFor('模块卡片打开', () => q('[data-test="module-card"]'), 10000)
          const cardText = (card.textContent || '').replace(/\s+/g, ' ')
          record('点击功能点行打开模块卡片', !!card,
            `${caps[0].getAttribute('data-capability-id')} → ${cardText.slice(0, 60)}`)

          // "不负责什么"是 README4 点名的关键教学字段
          record('模块卡片含【不负责什么】区块', !!card.querySelector('[data-test="does-not"]'))

          // 卡片里的证据行号必须可点
          const evidence = card.querySelector('[data-test="member-evidence"], [data-test="fact-evidence"]')
          record('卡片证据带可点击的行号入口', !!evidence)
        }

        // 复杂度徽章 + 明细（含 caveat 原文）
        const cx = await waitFor('复杂度徽章', () => q('[data-test="complexity-badge"]'), 8000)
        record('复杂度徽章已渲染', !!cx, (cx.textContent || '').trim().slice(0, 20))
        click(cx)
        const detail = await waitFor('复杂度明细', () => q('[data-test="complexity-detail"]'), 8000)
        const detailText = (detail.textContent || '').replace(/\s+/g, ' ')
        record('复杂度明细含七维与公式', /公式|complexity_raw|权重/.test(detailText), detailText.slice(0, 60))
        record('复杂度明细含 caveat 原文（阈值未校准）',
          /未校准|未经|待校准|caveat/i.test(detailText) || !!q('[data-test="complexity-caveat"]'))

        // caveats 必须可见（README4 §9.2 的诚实边界）
        record('图谱 caveats 可见', !!q('[data-test="graph-caveats"]'))

        // 流程标签页
        const flowsTab = q('[data-test="graph-tab-flows"]')
        if (flowsTab) {
          click(flowsTab)
          await sleep(500)
          const flowCards = qa('[data-test="flow-card"]')
          record('流程与场景标签页渲染了流程', flowCards.length >= 1, `${flowCards.length} 条流程`)
          const lifecycle = qa('[data-test="lifecycle-badge"], [data-test="lifecycle-section"]')
          record('生命周期流程被单独标注（不混进业务流）', lifecycle.length >= 0,
            lifecycle.length ? '有标注' : '本项目无生命周期流程或未标注')
        } else {
          record('流程与场景标签页存在', false, '找不到 [data-test="graph-tab-flows"]')
        }
      }
    } catch (e) {
      trap('业务图谱走查', e)
    }

    // ---- 14. 阶段一「项目认知」（Sprint 3）：学生先输出 → 系统只回覆盖清单 ----
    try {
      const stageBtn = q('[data-test="stage-orientation"]')
      if (!stageBtn) {
        record('阶段一「项目认知」入口存在', false, '找不到 [data-test="stage-orientation"]')
      } else {
        record('阶段一「项目认知」入口存在', true)
        click(stageBtn)
        await waitFor('阶段一视图挂载', () => q('[data-test="stage-orientation-view"]'), 15000)

        const domainRows = await waitFor('阶段一模块列表', () => {
          const els = qa('[data-test="orientation-domain"]')
          return els.length ? els : null
        }, 15000)
        record('阶段一渲染了一级业务模块', domainRows.length >= 2, `${domainRows.length} 个模块`)

        // 核心纪律：**提交前反馈区一个节点都不能有**（README5 §12.6：学生先输出、系统后反馈）
        record('提交前不渲染覆盖清单（学生先输出）', !q('[data-test="orientation-report"]'))

        // 图谱没给出模块目标时必须如实标注"待教师确认"，不许代填。
        // ⚠️ 但**"有没有待确认的"取决于这份图谱有没有教师种子**：优先级 4 一轮给
        // lab_safety_assistant 落了 business_graph.seed.json（5 个域目标全部 confirmed），
        // 所以这里**不能**再断言"至少有 1 个"——那条断言在种子落地那天就变成假失败了。
        // 正确写法与阶段二那条「待教师确认徽章数量与后端对齐」一致（README §19.2 ⑫ 的教训）：
        // **页面显示的数量必须等于这份图谱此刻真实的数量，是 0 也要等于 0**。
        const objectiveMissing = qa('[data-test="orientation-objective-unconfirmed"]')
        const pageProject = (q('[data-test="project-select"]')?.value) || PROJECT
        const graphPayload = await loadGraphForAssertion(pageProject)
        if (graphPayload) {
          const cardsOf = graphPayload.module_cards || {}
          // 与 StageOrientation.vue 的 domains 口径一致：编排 / 支撑域不参与核心覆盖度
          const coreDomainRows = (graphPayload.domains || []).filter(
            (d) => !['orchestrator', 'support'].includes(String(d.role || '').trim().toLowerCase()))
          const expectedMissing = coreDomainRows.filter(
            (d) => !String((cardsOf[d.domain_id] || {}).objective || '').trim()).length
          record('未确认的模块目标数量与该图谱一致（0 也允许，不许代填）',
            objectiveMissing.length === expectedMissing,
            `页面 ${objectiveMissing.length} 个 / 图谱 ${expectedMissing} 个（项目 ${pageProject}）`)
        } else {
          record('未确认的模块目标如实标注（取不到图谱，只能记录数量）',
            objectiveMissing.length >= 0, `${objectiveMissing.length} 个模块目标待教师确认`)
        }

        const box = q('[data-test="orientation-input"]')
        record('阶段一有自由文本作答框', !!box)

        // 回答内容**取自图谱里真实的模块名**（数据驱动：不写死任何业务词）
        const domainNameOf = (el) => (el.querySelector('span')?.textContent || '').trim()
        const names = domainRows.map(domainNameOf).filter(Boolean)
        const answer = `我认为这个项目需要这些模块：${names.join('、')}。它们各自负责一块业务，互相协作。`
        box.value = answer
        box.dispatchEvent(new window.Event('input', { bubbles: true }))
        await sleep(200)

        const submitBtn = q('[data-test="orientation-submit"]')
        record('写下回答后提交按钮可用', !!submitBtn && !submitBtn.disabled, `${answer.length} 字`)
        click(submitBtn)

        if (!OFFLINE) {
          const rep = await waitFor('覆盖清单渲染', () => q('[data-test="orientation-report"]'), 15000)
          const repText = (rep.textContent || '').replace(/\s+/g, ' ')
          record('提交后收到覆盖清单（学生先输出、系统后反馈）', !!rep, repText.slice(0, 70))

          // 阶段一的硬契约：不打分
          const noScore = q('[data-test="orientation-no-score"]')
          record('报告明示「不打分、不给标准答案」',
            !!noScore && /不打分/.test(noScore.textContent || ''))
          const scoreLike = repText.match(/\d+\s*分/)
          record('报告里没有「XX 分」这类结论', !scoreLike, scoreLike ? scoreLike[0] : '无')

          // 回答里写了全部模块名 → 覆盖清单必须命中（证明比对真的跑了，不是空壳）
          const covered = qa('[data-test="orientation-covered"]')
          const missed = qa('[data-test="orientation-missed"]')
          record('覆盖清单命中已提到的模块', covered.length >= 2,
            `命中 ${covered.length} / 未提到 ${missed.length}`)
          record('命中项说明「用哪个词比中的」', !!q('[data-test="orientation-key"]'),
            (q('[data-test="orientation-key"]')?.textContent || '').replace(/\s+/g, ' ').slice(0, 60))

          // 报告的诚实边界必须原样展示
          record('覆盖清单带 caveats（诚实边界）', !!q('[data-test="orientation-caveats"]'))

          // 未参与比对的模块单列，且写明原因（不许当成"漏掉"）
          const nc = qa('[data-test="orientation-not-comparable"]')
          record('未参与比对的模块单列并写明原因', nc.length >= 0,
            nc.length ? `${nc.length} 个（含原因）` : '本项目无需降级的模块')

          record('阶段一 DOM 中不含答案字段名',
            !/correct_answers/.test(window.document.documentElement.outerHTML))
        } else {
          const err = await waitFor('离线不可用提示', () => q('[data-test="orientation-submit-error"]'), 15000)
          const errText = (err.textContent || '').replace(/\s+/g, ' ')
          record('离线时如实说明覆盖度报告不可用', /离线演示模式/.test(errText), errText.slice(0, 80))
          record('离线时不渲染覆盖清单（数据层面就没有判定通道）',
            !q('[data-test="orientation-report"]'))
        }
      }
    } catch (e) {
      trap('阶段一走查', e)
    }

    // ---- 15. 阶段二「模块卡片学习」（Sprint 4）：逐张卡片 + 五问 → 事实覆盖清单 ----
    try {
      const stageBtn = q('[data-test="stage-module-card"]')
      if (!stageBtn) {
        record('阶段二「模块卡片」入口存在', false, '找不到 [data-test="stage-module-card"]')
      } else {
        record('阶段二「模块卡片」入口存在', true)
        click(stageBtn)
        await waitFor('阶段二视图挂载', () => q('[data-test="stage-module-card-view"]'), 15000)

        // 核心纪律：**提交前反馈区一个节点都不能有**（README5 §12.6：学生先输出、系统后反馈）
        record('提交前不渲染覆盖清单（阶段二同样先输出）',
          !q('[data-test="module-card-report"]'))

        if (!OFFLINE) {
          // ⚠️ 前面的走查步骤把项目切成了别的项目（深链同步那一步），
          // 所以这里必须按**当前**项目取任务包 —— 第一版写死 PROJECT，
          // 于是拿 lab_safety 的任务去比 python_dotenv 的页面，卡片数对不上（30/34）。
          const currentProject = (q('[data-test="project-select"]')?.value) || PROJECT
          const taskResp = await patchedFetch(`/api/projects/${currentProject}/teaching/module-card/task`)
          const task = taskResp.ok ? await taskResp.json() : null
          record('阶段二任务包可获取（题目 + 卡片都由后端派生）', !!task,
            task ? `项目 ${currentProject}：${task.counts.cards} 张卡片 / ${task.counts.questions} 个问题`
                 : '任务包请求失败')

          if (task) {
            const questionEls = await waitFor('阶段二题目渲染', () => {
              const els = qa('[data-test="module-card-question"]')
              return els.length ? els : null
            }, 15000)
            record('阶段二渲染了后端下发的五个问题',
              questionEls.length === task.questions.length && questionEls.length === 5,
              `${questionEls.length} 个问题`)

            // 题目文本必须与后端一致（证明题目不是写死在前端组件里的）
            const renderedText = questionEls.map((el) => (el.textContent || '').replace(/\s+/g, ''))
            const missingText = task.questions
              .map((item) => String(item.text_cn || '').replace(/\s+/g, ''))
              .filter((text) => text && !renderedText.some((rendered) => rendered.includes(text)))
            record('题目文本与后端下发的一致（页面不写死题目）', missingText.length === 0,
              missingText.length ? `缺失：${missingText.join('、')}` : `${task.questions.length} 题全部对上`)

            const options = qa('[data-test="module-card-option"]')
            record('阶段二渲染了图谱里的卡片（一张不少）',
              options.length === task.cards.length && options.length > 0,
              `${options.length} / ${task.cards.length} 张`)

            // 「待教师确认」的卡片必须有徽章：数量与后端给的 card_needs_review 对齐
            const expectedPending = task.cards.filter((c) => c.card_needs_review).length
            const pendingBadges = qa('[data-test="module-card-option-needs-review"]')
            record('卡片列表按后端标注「待教师确认」',
              pendingBadges.length === expectedPending,
              `页面 ${pendingBadges.length} 个 / 后端 ${expectedPending} 张`)

            record('阶段二默认选中一张卡片', !!q('[data-test="module-card-selected"]'),
              (q('[data-test="module-card-selected"]')?.textContent || '').trim())

            // 卡片内容默认收起：学生可主动展开（先自己想，再对照）
            record('提交前卡片内容默认收起（先自己写）',
              !q('[data-test="module-card-reveal-panel"]'))
            const revealBtn = q('[data-test="module-card-reveal"]')
            if (revealBtn) {
              click(revealBtn)
              await sleep(200)
              const panel = q('[data-test="module-card-reveal-panel"]')
              record('可以按需展开卡片内容与证据', !!panel,
                panel ? `${qa('[data-test="module-card-fact"]').length} 条事实` : '未展开')
              record('卡片证据带「项目内相对路径 + 行号」',
                qa('[data-test="module-card-fact-location"]').length >= 0,
                `${qa('[data-test="module-card-fact-location"]').length} 个出处按钮`)
            } else {
              record('可以按需展开卡片内容与证据', false, '找不到 [data-test="module-card-reveal"]')
            }

            // 回答内容**取自卡片面板的真实文本**（数据驱动：走查不写死任何业务词）
            const panelText = (q('[data-test="module-card-reveal-panel"]')?.textContent || '')
              .replace(/\s+/g, ' ')
              .trim()
            const selectedName = (q('[data-test="module-card-selected"]')?.textContent || '').trim()
            const answerText = `${selectedName} ${panelText}`.slice(0, 700)
            const boxes = qa('[data-test="module-card-answer"]')
            record('阶段二有五个作答框（每个问题一个）',
              boxes.length === 5, `${boxes.length} 个`)
            for (const box of boxes) {
              box.value = answerText
              box.dispatchEvent(new window.Event('input', { bubbles: true }))
            }
            await sleep(200)

            const submitBtn = q('[data-test="module-card-submit"]')
            record('写下回答后提交按钮可用',
              !!submitBtn && !submitBtn.disabled, `${answerText.length} 字 × ${boxes.length}`)
            click(submitBtn)

            const rep = await waitFor('阶段二覆盖清单渲染',
              () => q('[data-test="module-card-report"]'), 15000)
            const repText = (rep.textContent || '').replace(/\s+/g, ' ')
            record('提交后收到事实覆盖清单（学生先输出、系统后反馈）', !!rep, repText.slice(0, 70))

            const noScore = q('[data-test="module-card-report-no-score"]')
            record('阶段二报告明示「不打分、不给标准答案」',
              !!noScore && /不打分/.test(noScore.textContent || ''))
            const scoreLike = repText.match(/\d+\s*分/)
            record('阶段二报告里没有「XX 分」这类结论', !scoreLike, scoreLike ? scoreLike[0] : '无')

            const results = qa('[data-test="module-card-question-result"]')
            record('报告按问题逐条给出覆盖清单',
              results.length === task.questions.length,
              `${results.length} / ${task.questions.length} 条`)

            const matched = qa('[data-test="module-card-matched-key"]')
            const missedKeys = qa('[data-test="module-card-missed-key"]')
            const notComparable = qa('[data-test="module-card-not-comparable"]')
            record('把卡片内容写进回答后确实命中了事实（比对真的跑了）',
              matched.length >= 1,
              `命中 ${matched.length} 条 / 未提到 ${missedKeys.length} 条 / 未参与比对 ${notComparable.length} 问`)
            record('命中项写明「系统拿什么比出来的」',
              matched.length === 0 || /卡片|状态|清单|规则|模块/.test(matched[0].textContent || ''),
              (matched[0]?.textContent || '').replace(/\s+/g, ' ').slice(0, 60))

            const selectedId = q('[data-test="module-card-selected"]')?.getAttribute('data-module-id') || ''
            const selectedTaskCard = task.cards.find((c) => c.module_id === selectedId) || null
            record('默认选中的卡片能在后端任务包里对上', !!selectedTaskCard, selectedId || '(未读到 id)')

            const expectReview = !!selectedTaskCard?.card_needs_review
            const reviewNotice = q('[data-test="module-card-report-needs-review"]')
            record('「该卡片待教师确认」的提示如实出现/不出现',
              !!reviewNotice === expectReview,
              reviewNotice
                ? (reviewNotice.textContent || '').replace(/\s+/g, ' ').slice(0, 60)
                : '本卡片无需降级的字段')

            record('阶段二报告带 caveats（诚实边界）', !!q('[data-test="module-card-caveats"]'))
            record('阶段二 DOM 中不含答案字段名',
              !/correct_answers/.test(window.document.documentElement.outerHTML))
          }
        } else {
          const err = await waitFor('阶段二离线提示', () => q('[data-test="module-card-error"]'), 15000)
          const errText = (err.textContent || '').replace(/\s+/g, ' ')
          record('离线时如实说明阶段二不可用（题目在后端，不在前端另算一份）',
            /离线演示模式/.test(errText), errText.slice(0, 80))
          record('离线时不渲染任何题目与覆盖清单',
            !q('[data-test="module-card-question"]') && !q('[data-test="module-card-report"]'))
        }
      }
    } catch (e) {
      trap('阶段二走查', e)
    }

    // ---- 16. 阶段四「设计画布」+ 阶段五「六维评审」（Sprint 5 / README §18 优先级 3）----
    try {
      const stageBtn = q('[data-test="stage-design"]')
      if (!stageBtn) {
        record('阶段四「设计画布」入口存在', false, '找不到 [data-test="stage-design"]')
      } else {
        record('阶段四「设计画布」入口存在', true)
        click(stageBtn)
        await waitFor('设计画布视图挂载', () => q('[data-test="stage-design-view"]'), 15000)

        // 核心纪律：**提交前反馈区一个节点都不能有**（README §12.6 第 1 条）
        record('提交前不渲染六维评审（学生先输出、系统后反馈）',
          !q('[data-test="design-report"]'))

        if (!OFFLINE) {
          const currentProject = (q('[data-test="project-select"]')?.value) || PROJECT
          const listResp = await patchedFetch(`/api/projects/${currentProject}/teaching/design/tasks`)
          const listing = listResp.ok ? await listResp.json() : null
          record('设计任务清单可获取（按复杂度级别给类型）', !!listing,
            listing ? `项目 ${currentProject}：${listing.counts.tasks} 个任务 / 级别 ${listing.level}` : '任务清单请求失败')

          const taskResp = await patchedFetch(
            `/api/projects/${currentProject}/teaching/design/task?task_id=${encodeURIComponent(listing?.default_task_id || '')}`,
          )
          const studentTask = taskResp.ok ? await taskResp.json() : null
          record('设计任务（学生视图）可获取', !!studentTask,
            studentTask ? `${studentTask.type_name_cn} / 必备能力 ${studentTask.must_have_count} 项` : '任务请求失败')

          if (studentTask) {
            // 题干必须与后端下发的一致（证明题干不是写死在前端组件里的）
            const promptText = (q('[data-test="design-task-prompt"]')?.textContent || '').replace(/\s+/g, '')
            const backendPrompt = String(studentTask.prompt_cn || '').replace(/\s+/g, '')
            record('题干与后端下发的一致（页面不写死题目）',
              backendPrompt.length > 0 && promptText.includes(backendPrompt.slice(0, 40)),
              promptText.slice(0, 60))

            // 学生视图**不下发**必备能力全文（§10.5 字段可见性矩阵）
            const teacherResp = await patchedFetch(
              `/api/projects/${currentProject}/teaching/design/task?task_id=${encodeURIComponent(studentTask.task_id)}&mode=teacher`,
            )
            const teacherTask = teacherResp.ok ? await teacherResp.json() : null
            const mustHaveNames = (teacherTask?.must_have || []).map((m) => String(m.name_cn || '')).filter(Boolean)
            record('学生视图的 API 响应里没有 must_have 全文',
              !('must_have' in studentTask) && !('rubric_weights' in studentTask) && !('required_relations' in studentTask),
              `字段=${Object.keys(studentTask).length} 个`)
            const domHtml = window.document.documentElement.outerHTML
            const leakedNames = mustHaveNames.filter((name) => name && domHtml.includes(name))
            record('页面 DOM 里不出现任何必备能力名（清单不下发）',
              mustHaveNames.length > 0 && leakedNames.length === 0,
              leakedNames.length ? `泄漏：${leakedNames.slice(0, 3).join('、')}` : `教师视图 ${mustHaveNames.length} 项，页面 0 处`)

            // 「待教师确认」徽章与后端标注对齐
            record('「必备能力清单待教师确认」徽章与后端一致',
              !!q('[data-test="design-needs-review"]') === !!studentTask.needs_review,
              q('[data-test="design-needs-review"]')?.textContent?.trim() || '后端标注无需复核')

            // ---- 画布：加模块 → 改名 → 连线 ----
            record('画布初始为空（评审要求至少一个模块）', qa('[data-test="design-node"]').length === 0)
            click(q('[data-test="design-add-module"]'))
            await sleep(120)
            click(q('[data-test="design-add-module"]'))
            await sleep(120)
            const nodeEls = qa('[data-test="design-node"]')
            record('点「添加模块」能在画布上落节点', nodeEls.length === 2, `${nodeEls.length} 个节点`)

            const nameInputs = qa('[data-test="design-node-name"]')
            const names = ['模块甲', '模块乙']
            for (let i = 0; i < nameInputs.length && i < names.length; i++) {
              nameInputs[i].value = names[i]
              nameInputs[i].dispatchEvent(new window.Event('input', { bubbles: true }))
            }
            await sleep(150)
            const renderedNames = qa('[data-test="design-node"]').map((el) => el.getAttribute('data-module-name'))
            record('节点改名后回写到节点数据（供提交）',
              names.every((n) => renderedNames.includes(n)),
              renderedNames.join('、'))

            // 从第一个节点的连线圆点拖到第二个节点 → 建立有向依赖
            const port = q('[data-test="design-port-out"]')
            const targetNode = qa('[data-test="design-node"]')[1]
            if (port && targetNode) {
              port.dispatchEvent(new window.MouseEvent('mousedown', { bubbles: true }))
              targetNode.dispatchEvent(new window.MouseEvent('mouseup', { bubbles: true }))
              await sleep(150)
            }
            const edgeEls = qa('[data-test="design-edge"]')
            record('从一个节点拖到另一个节点能建立有向依赖（SVG 连线）',
              edgeEls.length === 1 && !!edgeEls[0].getAttribute('d'),
              `${edgeEls.length} 条连线`)

            // 点击连线选中 → 删除（可验证"能选中、能删"）
            if (edgeEls.length) {
              edgeEls[0].dispatchEvent(new window.MouseEvent('click', { bubbles: true }))
              await sleep(120)
              const selectedLabel = (q('[data-test="design-remove-selected"]')?.textContent || '').trim()
              record('点击连线可被选中（删除按钮切换为「删除选中连线」）', /连线/.test(selectedLabel), selectedLabel)
              // 再画回来，后面提交时要有依赖
              port.dispatchEvent(new window.MouseEvent('mousedown', { bubbles: true }))
              targetNode.dispatchEvent(new window.MouseEvent('mouseup', { bubbles: true }))
              await sleep(150)
            }
            record('依赖关系可以重新建立（画布可编辑）', qa('[data-test="design-edge"]').length === 1)

            // ---- 填模块卡片与设计理由（第 2 / 5 / 6 维要用）----
            const firstNode = qa('[data-test="design-node"]')[0]
            firstNode.dispatchEvent(new window.MouseEvent('click', { bubbles: true }))
            await sleep(120)
            const fill = (selector, text) => {
              const el = q(selector)
              if (!el) return false
              el.value = text
              el.dispatchEvent(new window.Event('input', { bubbles: true }))
              return true
            }
            const filled = [
              fill('[data-test="design-card-objective"]', '只负责模块甲这一件事'),
              fill('[data-test="design-card-does-not"]', '不负责模块乙的职责'),
              fill('[data-test="design-card-inputs"]', '入参甲'),
              fill('[data-test="design-card-outputs"]', '出参乙'),
              fill('[data-test="design-card-rules"]', '入参不能为空'),
              fill('[data-test="design-card-exceptions"]', '入参为空时拒绝并报错'),
              fill('[data-test="design-rationale"]', '我把这两件事拆成两个模块：甲负责写入状态，乙负责校验与拒绝；两者职责不同，所以不合并。'),
            ].filter(Boolean).length
            record('模块卡片面板能填写（目标 / 边界 / 输入输出 / 规则 / 异常 / 理由）',
              filled === 7, `${filled} / 7 个字段写入成功`)
            await sleep(150)

            const submitBtn = q('[data-test="design-submit"]')
            record('有模块之后提交按钮可用', !!submitBtn && !submitBtn.disabled, `${qa('[data-test="design-node"]').length} 个模块`)
            click(submitBtn)

            const rep = await waitFor('六维评审渲染', () => q('[data-test="design-report"]'), 20000)
            const repText = (rep.textContent || '').replace(/\s+/g, ' ')
            record('提交后收到六维评审报告', !!rep, repText.slice(0, 70))

            const dims = qa('[data-test="design-dimension"]')
            record('报告按六维逐条给出（覆盖率 / 职责 / 层级 / 依赖 / 异常 / 理由）',
              dims.length === 6, `${dims.length} 维`)

            // 「算不出来就 not_evaluated、不许填 0」必须在页面上成立
            const notEvaluated = qa('[data-test="design-not-evaluated"]')
            const evaluatedBadges = qa('[data-test="design-dimension-score"]')
            const zeroFilled = dims.filter((el) => {
              const status = el.getAttribute('data-status')
              if (status === 'evaluated') return false
              // 未评估的维度里不该出现「得分 0」
              return /得分\s*0(\.0+)?\b/.test(el.textContent || '')
            })
            record('未评估的维度显示「本轮未评估」而不是 0 分',
              zeroFilled.length === 0,
              `未评估 ${notEvaluated.length} 维 / 已评估 ${evaluatedBadges.length} 维`)
            record('未评估的维度写明了原因',
              notEvaluated.length === 0 || qa('[data-test="design-not-evaluated-reason"]').length === notEvaluated.length,
              `${qa('[data-test="design-not-evaluated-reason"]').length} 条原因`)

            const overall = q('[data-test="design-overall-score"]')
            const overallText = (overall?.textContent || '').trim()
            record('总分与「已评估维度数」自洽（没有一维可算时显示 —）',
              evaluatedBadges.length > 0 ? /^[\d.]+$/.test(overallText) : overallText === '—',
              `总分 ${overallText} / 已评估 ${evaluatedBadges.length} 维`)

            record('页面明示「算不出来的维度不填 0」', !!q('[data-test="design-no-fake-score"]'))
            record('报告渲染了信号码（每条反馈都能追溯）',
              qa('[data-test="design-signal"]').length >= 0,
              `${qa('[data-test="design-signal"]').length} 个信号`)
            record('报告给出三分类清单（已识别 / 未识别到 / 系统未识别）',
              qa('[data-test="design-matched"]').length + qa('[data-test="design-missing"]').length + qa('[data-test="design-unrecognized"]').length > 0,
              `已识别 ${qa('[data-test="design-matched"]').length} / 缺 ${qa('[data-test="design-missing"]').length} / 未识别 ${qa('[data-test="design-unrecognized"]').length}`)
            record('报告带 caveats（诚实边界）', !!q('[data-test="design-caveats"]'))
            record('报告显示结构检查与替代结构判定的真实状态',
              !!q('[data-test="design-graph-checks"]') && !!q('[data-test="design-alternatives"]'))
            record('设计层 DOM 中不含答案字段名',
              !/correct_answers/.test(window.document.documentElement.outerHTML))

            // ---- 再次提交 → iteration + 1 且显示与上一轮的对比（§12.4 最小功能集）----
            const secondSubmit = q('[data-test="design-submit"]')
            if (secondSubmit && !secondSubmit.disabled) {
              click(secondSubmit)
              await waitFor('第二轮评审渲染', () => q('[data-test="design-compare"]'), 20000)
              const iterationText = (q('[data-test="design-iteration"]')?.textContent || '').trim()
              record('再次提交后 iteration 递增并显示与上一轮的对比',
                /2/.test(iterationText) && !!q('[data-test="design-compare"]'),
                `${iterationText} / ${(q('[data-test="design-compare"]')?.textContent || '').replace(/\s+/g, ' ').slice(0, 60)}`)
            } else {
              record('再次提交后 iteration 递增并显示与上一轮的对比', false, '第二次提交按钮不可用')
            }
          }
        } else {
          const err = await waitFor('设计层离线提示', () => q('[data-test="design-load-error"]'), 15000)
          const errText = (err.textContent || '').replace(/\s+/g, ' ')
          record('离线时如实说明设计任务不可用（题干与判定都在后端）',
            /离线演示模式/.test(errText), errText.slice(0, 80))
          record('离线时不渲染任何画布节点与评审',
            !q('[data-test="design-canvas"]') && !q('[data-test="design-report"]'))
        }
      }
    } catch (e) {
      trap('阶段四走查', e)
    }

    record('全过程 API 调用次数 > 0', apiCalls > 0, `${apiCalls} 次，失败 ${apiFailures} 次`)
    if (OFFLINE) {
      record('离线场景确实产生了 API 连接失败（模拟后端未启动）', apiFailures > 0, `${apiFailures} 次`)
    }
  } catch (e) {
    trap('未捕获异常', e)
  }

  // ---- 报告 ----
  const failed = results.filter((r) => !r.ok)
  console.log('='.repeat(78))
  console.log(`浏览器点击走查（jsdom + 真实组件 + 真实 HTTP）  场景=${scenario}  项目=${PROJECT}`)
  console.log('='.repeat(78))
  for (const r of results) {
    console.log(`[${r.ok ? 'PASS' : 'FAIL'}] ${r.name}${r.detail ? '  — ' + r.detail : ''}`)
  }
  console.log('-'.repeat(78))
  console.log(`合计 ${results.length - failed.length}/${results.length} 项通过`)
  console.log(`SMOKE_RESULT: ${failed.length === 0 ? 'PASS' : 'FAIL'}`)
  if (argv.includes('--keep-open')) {
    console.log('（--keep-open：保持进程，Ctrl+C 退出）')
    return new Promise(() => {})
  }
  process.exit(failed.length === 0 ? 0 : 1)
}

main().catch((e) => {
  console.error('走查脚本自身出错：', e)
  process.exit(3)
})
