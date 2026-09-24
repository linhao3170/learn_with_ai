import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// https://vite.dev/config/
//
// P0-13：前端与后端第一次真正接上。
// - 开发环境：所有 `/api/*` 请求由 dev server 代理到本地 FastAPI（默认 http://127.0.0.1:8000），
//   前端代码里因此只写同源相对路径 `/api/...`，不需要处理 CORS，也不用在演示机上配环境变量。
// - 生产/独立部署：把 `VITE_API_BASE` 指向后端地址（例如 VITE_API_BASE=http://127.0.0.1:8000），
//   `src/api/client.js` 会读它作为请求前缀；不设置时走同源 `/api`（即仍然依赖下面的 proxy）。
// - 后端没启动时也不会白屏：`src/api/dataSource.js` 会回落到静态快照，进入"离线演示模式"。
const API_TARGET = process.env.VITE_API_TARGET || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: API_TARGET,
        changeOrigin: true,
      },
    },
  },
})
