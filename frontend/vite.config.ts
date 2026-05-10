import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5174,
    proxy: {
      // 开发期把 /api 和 /ws 转发到后端 5173
      '/api': {
        target: 'http://localhost:5173',
        changeOrigin: true,
        // FastAPI WebSocket 路由也挂在 /api 下，所以这里也要走 ws 升级
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 1024,
  },
})
