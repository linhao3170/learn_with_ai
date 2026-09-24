/**
 * 沉浸式学习视图 · 渲染自测（SSR）
 * ================================
 * 为什么需要它：`engine` 侧的测试只能证明**讲稿数据**对；
 * 界面是不是把参考文档（`shuliyewu.txt`）的形态**真的渲染出来了**，
 * 只有渲染一遍才知道。而这个界面恰恰是整个功能最容易被「看起来差不多」糊弄过去的地方。
 *
 * 做法：用 Vite 的 SSR 加载器把 `ImmersiveLesson.vue` 编译出来，
 * 拿**真实讲稿 JSON** 渲染成 HTML，然后断言：
 *   1. 参考文档的四个字面模板都在（段头 / 重点记什么：/ 一句话概括： + 尾随空格）；
 *   2. 代码摘录按真实行号渲染（`data-line`）；
 *   3. 证据跳转、断言徽章、复核状态、阻断项、课后要点、口径边界、教师审核入口都在；
 *   4. **被拦截的断言仍然渲染出来**并带原因（本项目禁止「静默删除」）。
 *
 * 刻意不开浏览器：这个仓库跑不了 headless Chromium（见 README §17），
 * SSR 足够证明「给定契约能渲染出正确结构」，而且快、可进 CI。
 *
 * 为什么放在 `frontend/scripts/` 而不是仓库根的 `scripts/`：
 * 本脚本要 `import 'vite'` / `'vue'` / `'@vue/server-renderer'`，
 * Node 的裸模块解析是从脚本所在目录往上找 `node_modules` 的 ——
 * 放在仓库根就找不到 `frontend/node_modules`（实测报 ERR_MODULE_NOT_FOUND）。
 *
 * 用法
 * ----
 *   # 先让接口自测生成一课（会落盘到 backend/data/logic_platform/<project>/lessons/）
 *   python scripts/test_logic_platform_api.py --base-url http://127.0.0.1:8000
 *   node frontend/scripts/test_immersive_render.mjs
 *   node frontend/scripts/test_immersive_render.mjs --project python_dotenv
 *   node frontend/scripts/test_immersive_render.mjs --lesson path/to/lesson.json
 *
 * 退出码：0 = 全部通过；1 = 有失败项。
 */
import { readFileSync, readdirSync, existsSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
import { createSSRApp } from 'vue'
import { renderToString } from '@vue/server-renderer'

const HERE = dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = resolve(HERE, '..', '..')
const FRONTEND_DIR = join(REPO_ROOT, 'frontend')

const args = process.argv.slice(2)
const argValue = (name, fallback = '') => {
  const index = args.indexOf(name)
  return index >= 0 && args[index + 1] ? args[index + 1] : fallback
}
const project = argValue('--project', 'python_dotenv')
const explicitLesson = argValue('--lesson', '')

const lessonDir = join(REPO_ROOT, 'backend', 'data', 'logic_platform', project, 'lessons')

function pickLessonFile() {
  if (explicitLesson) return explicitLesson
  if (!existsSync(lessonDir)) {
    console.error(`找不到讲稿目录：${lessonDir}`)
    console.error('请先跑：python scripts/test_logic_platform_api.py（它会在校验后生成一课并落盘）')
    process.exit(1)
  }
  const files = readdirSync(lessonDir).filter((f) => f.endsWith('.json') && !f.startsWith('_'))
  if (!files.length) {
    console.error(`讲稿目录是空的：${lessonDir}`)
    console.error('请先跑：python scripts/test_logic_platform_api.py')
    process.exit(1)
  }
  return join(lessonDir, files[0])
}

const lessonPath = pickLessonFile()
const lesson = JSON.parse(readFileSync(lessonPath, 'utf-8'))
console.log('\n=== 沉浸式学习视图 · 渲染自测 ===')
console.log(`讲稿：${lesson.lesson_id}（${(lesson.segments || []).length} 段）`)
console.log(`来源：${lessonPath}`)

async function renderWith(payload) {
  const server = await createServer({
    root: FRONTEND_DIR,
    server: { middlewareMode: true },
    appType: 'custom',
    logLevel: 'error',
  })
  try {
    const mod = await server.ssrLoadModule('/src/components/logic-platform/ImmersiveLesson.vue')
    const app = createSSRApp(mod.default, {
      lesson: payload,
      verification: payload.verification || null,
      analysisId: project,
      loading: false,
      error: '',
    })
    return await renderToString(app)
  } finally {
    await server.close()
  }
}

let failed = 0
const check = (name, ok, hint = '') => {
  if (!ok) failed++
  console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name}${ok || !hint ? '' : `  ${hint}`}`)
}

const html = await renderWith(lesson)
const render = lesson.render || {}
const firstSegment = (lesson.segments || [])[0] || {}
const firstCodeLine = String(firstSegment.code_excerpt || '').split('\n')[0] || ''

check('容器挂载点存在（data-test）', html.includes('data-test="immersive-lesson"'))
// 参考文档的四个字面模板 —— 任何一个被改写，「像那份文档」就不成立了
check('课前负荷免责句（参考文档 L1）', html.includes('你不用记住每一行'))
check('课前定调句（参考文档 L2）', html.includes(render.lesson_frame_prefix || '一句话先定调：'))
check('段头字面模板「第 N 段：…」', html.includes('第 1 段：'))
check('段头行号括号「（… 行）」', html.includes(' 行）'))
check('要点标题字面量', Boolean(render.bullets_heading) && html.includes(render.bullets_heading))
check(
  '一句话标题字面量（含尾随空格）',
  Boolean(render.summary_heading) && html.includes(render.summary_heading),
  `render.summary_heading=${JSON.stringify(render.summary_heading)}`,
)
check(
  '「一句话概括：」后确实接了内容（模板未被改写）',
  /一句话概括：(\s|&nbsp;|<!--[^>]*-->)*\S/.test(html),
)
check('代码按真实行号渲染（data-line）', html.includes('data-line="'))
check(
  '代码摘录内容真实出现在页面上',
  Boolean(firstCodeLine.trim()) && html.includes(firstCodeLine.trim().slice(0, 12)),
)
check('证据跳转按钮', html.includes('data-test="claim-evidence"'))
check('断言徽章（置信度 + 生成主体）', html.includes('data-test="claim-badge"'))
check('机械复核状态可见', html.includes('data-test="lesson-verification-badge"'))
check('阻断项（blocking_issues）可见', html.includes('data-test="lesson-blocking-issues"'))
check('课后「记住 N 件事」', html.includes('data-test="lesson-recap"'))
check('口径与边界可展开（caveats 不丢）', html.includes('data-test="lesson-caveats"'))
check('教师审核入口', html.includes('data-test="lesson-confirm"'))

// ---- 诚实路径：被拦截的断言必须照原样显示，带原因 ----
const tampered = JSON.parse(JSON.stringify(lesson))
const targetSegment = (tampered.segments || []).find((s) => (s.must_remember || []).length)
check('构造拦截样本（讲稿里有可拦截的要点）', Boolean(targetSegment))
if (targetSegment) {
  targetSegment.must_remember[0].verified = false
  targetSegment.must_remember[0].reject_reason = '未通过确定性校验：引用的代码或行号与磁盘源码不符'
  targetSegment.must_remember[0].confidence = 'needs_review'
  const tamperedHtml = await renderWith(tampered)
  check('被拦截的断言仍然渲染出来（不许静默删除）', tamperedHtml.includes('data-test="bullet-intercepted"'))
  check('拦截原因照原样显示', tamperedHtml.includes('已拦截：未通过确定性校验'))
  check('被拦截行标记 data-verified="false"', tamperedHtml.includes('data-verified="false"'))
}

console.log(`\n渲染 HTML 长度：${html.length} 字符`)
if (failed) {
  console.log(`结果：存在未通过项 ✗（${failed} 项）`)
  process.exit(1)
}
console.log('结果：全部通过 ✓')
