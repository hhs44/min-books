import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000",
    trace: "on-first-retry",
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
  },
  webServer: {
    command: "npm run dev",
    port: 3000,
    timeout: 60_000,
    reuseExistingServer: true,
    stdout: "ignore",
    stderr: "pipe",
  },
});