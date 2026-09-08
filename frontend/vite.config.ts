/// <reference types="vitest" />
import react from '@vitejs/plugin-react'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { defineConfig } from 'vite'

// 루트 .env(모든 서비스 공용)의 VITE_* 값을 읽어 둔다. frontend/.env 가 같은 키를 갖고 있으면 그쪽이 우선한다.
function loadRootEnv(): void {
  const env = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env
  if (!env) return
  const fromShell = new Set(Object.keys(env))   // 셸·compose 가 준 값이 파일보다 우선
  for (const file of [resolve(__dirname, '..', '.env'), resolve(__dirname, '.env')]) {
    if (!existsSync(file)) continue
    for (const raw of readFileSync(file, 'utf8').split(/\r?\n/)) {
      const line = raw.trim()
      if (!line || line.startsWith('#')) continue
      const eq = line.indexOf('=')
      if (eq < 0) continue
      const key = line.slice(0, eq).trim()
      if (!key.startsWith('VITE_')) continue
      const value = line.slice(eq + 1).trim().replace(/^(["'])(.*)\1$/, '$2')
      if (fromShell.has(key)) continue
      if (file === resolve(__dirname, '.env') || env[key] === undefined) env[key] = value
    }
  }
}
loadRootEnv()

// 개발 서버에서 /api 는 백엔드(8000)로 프록시한다. 운영(nginx)도 같은 경로 규칙을 쓴다.
// Docker Compose 에서는 PROXY_TARGET=http://backend:8000 으로 바꾼다.
const proxyTarget = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env?.PROXY_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  define: { __BUILD_ID__: JSON.stringify(Date.now().toString(36)) },
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
