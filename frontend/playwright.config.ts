import { defineConfig, devices } from '@playwright/test'

// E2E: 엔진(8001)·백엔드(8000)는 밖에서 띄우고(scripts/e2e_up.sh 또는 CI 잡), vite 는 여기서 띄운다.
const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:5173'

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]] : 'list',
  use: {
    baseURL,
    locale: 'ko-KR',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    ...(process.env.CHROMIUM_PATH ? { launchOptions: { executablePath: process.env.CHROMIUM_PATH, args: ['--use-gl=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist'] } } : {}),
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 860 } } },
    { name: 'mobile', use: { ...devices['Pixel 7'] }, testMatch: /search\.spec\.ts/ },
  ],
  webServer: {
    command: 'npx vite --port 5173 --strictPort',
    url: baseURL,
    reuseExistingServer: true,
    timeout: 60_000,
  },
})
