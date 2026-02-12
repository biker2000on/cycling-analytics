import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,  // 2 min per test (uploads + processing take time)
  use: {
    baseURL: 'http://localhost:5173',
    headless: true,
  },
  retries: 0,
  // Do NOT start dev servers — assumes they are already running
});
