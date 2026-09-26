/**
 * 浏览器点击走查的入口（仅用于测试打包，不参与演示产物）
 * ============================================================
 * 为什么需要单独一个入口：
 *   本环境里无头浏览器渲染不出来（Chromium 需要的进程间通道被沙箱挡住），
 *   所以改用 **jsdom + 真实浏览器版 Vue 打包产物** 来跑真实的 DOM 点击。
 *
 *   `main.js` 会直接 mount 到 #app，不适合被测；这里导出 mount(el)，
 *   让 scripts/browser_clickthrough.mjs 自己决定容器和时机。
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './src/App.vue'

export function mount(el) {
  const app = createApp(App)
  app.use(createPinia())
  app.mount(el)
  return app
}

export { App }

// 证据折叠一轮：两个逻辑平台组件 + 它们的挂载助手也从这里导出，
// 好让 `scripts/check_evidence_fold.mjs` 能复用同一个走查 bundle（不另建打包配置）。
export {
  ImmersiveLesson,
  VerificationPanel,
  mountInto,
  NegativeControlFold,
  mountNegativeControl,
} from './evidence-check-entry.js'
