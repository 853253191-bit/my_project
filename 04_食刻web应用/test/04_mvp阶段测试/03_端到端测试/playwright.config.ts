import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, devices } from '@playwright/test'

/**
 * 食刻 MVP · 端到端测试配置
 *
 * 默认：启动 frontend preview（含 data-testid）+ /api 反代线上后端。
 * 打已部署站点：
 *   $env:E2E_BASE_URL="http://118.178.131.84"; $env:E2E_NO_SERVER="1"; npm run test:e2e
 */
const __dirname = path.dirname(fileURLToPath(import.meta.url))
/** 相对本目录：../../../frontend */
const frontendDir = path.resolve(__dirname, '../../../frontend')

const baseURL = process.env.E2E_BASE_URL || 'http://127.0.0.1:4173'
const startLocalServer = !process.env.E2E_NO_SERVER && !process.env.E2E_BASE_URL

export default defineConfig({
  testDir: './specs',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  // 线上 LLM / 网络偶发抖动：本地与 CI 均允许重试 1 次
  retries: 1,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  timeout: 180_000,
  expect: {
    timeout: 30_000,
  },
  use: {
    baseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    locale: 'zh-CN',
  },
  webServer: startLocalServer
    ? {
        command: 'npm run preview -- --host 127.0.0.1 --port 4173',
        cwd: frontendDir,
        url: 'http://127.0.0.1:4173',
        reuseExistingServer: !process.env.CI,
        timeout: 180_000,
      }
    : undefined,
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
