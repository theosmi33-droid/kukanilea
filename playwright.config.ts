import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: 'http://127.0.0.1:5051',
    locale: 'de-DE',
    timezoneId: 'UTC',
    colorScheme: 'light',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    launchOptions: {
      args: ['--font-render-hinting=none']
    }
  },
  reporter: [['list']],
  snapshotPathTemplate: '{testDir}/{testFilePath}-snapshots/{arg}{ext}',
  workers: 1
});
