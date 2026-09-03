/// <reference types="vitest" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// 개발 서버에서 /api 는 백엔드(8000)로 프록시한다. 운영(nginx)도 같은 경로 규칙을 쓴다.
// Docker Compose 에서는 PROXY_TARGET=http://backend:8000 으로 바꾼다.
const proxyTarget = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env?.PROXY_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: proxyTarget,
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],   // e2e/*.spec.ts 는 Playwright 가 돌린다
    css: false,
  },
})
