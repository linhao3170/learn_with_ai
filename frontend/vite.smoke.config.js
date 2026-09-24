/**
 * 仅用于「浏览器点击走查」的 Vite 配置（不参与正式构建）
 * ======================================================
 * 产物：frontend/.smoke-dist/app.js（浏览器版 ESM，未压缩，便于断言）
 * 用法：npx vite build --config vite.smoke.config.js
 *
 * 说明：
 * - `ssr: false` 很关键 —— 要测的是**浏览器版** Vue（能挂载、能响应点击），
 *   不是 server-renderer。
 * - `emptyOutDir: true` 只清 .smoke-dist，不会碰 dist。
 * - 不引 tailwind/postcss：点击走查只关心 DOM 结构与事件，样式无意义，
 *   去掉后构建快很多。
 */
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('.', import.meta.url))

export default defineConfig({
  root,
  plugins: [vue()],
  css: { postcss: { plugins: [] } },
  build: {
    ssr: false,
    outDir: '.smoke-dist',
    emptyOutDir: true,
    minify: false,
    target: 'esnext',
    lib: {
      entry: fileURLToPath(new URL('./smoke-entry.js', import.meta.url)),
      formats: ['es'],
      fileName: () => 'app.js',
    },
    rollupOptions: {
      // 依赖全部打进来，方便 jsdom 里一次性 import
      external: [],
    },
  },
})
