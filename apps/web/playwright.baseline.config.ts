import { defineConfig, devices } from "@playwright/test";

/**
 * Dedicated config for the visual-baseline capture runner (#184).
 *
 * Separate from `playwright.config.ts` so the 104-scenario capture only runs on
 * demand (`npm run baseline:capture`) and never as part of the default `e2e`
 * gate. Single worker + no retries keeps the captured set deterministic;
 * viewports are driven per scenario inside the spec, so one project suffices.
 */
const webPort = Number.parseInt(process.env.PLAYWRIGHT_WEB_PORT ?? "3101", 10);
const baseURL = `http://127.0.0.1:${webPort}`;
const browserChannel =
  process.env.PLAYWRIGHT_USE_SYSTEM_CHROME === "true" || process.env.CI ? "chrome" : undefined;

export default defineConfig({
  testDir: "./e2e",
  testMatch: /baseline-capture\.spec\.ts/,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL,
    channel: browserChannel,
    contextOptions: { reducedMotion: "reduce" },
    screenshot: "off",
    trace: "off",
    video: "off",
  },
  webServer: {
    command: [
      "NEXT_TELEMETRY_DISABLED=1",
      "NEXT_PUBLIC_ENABLE_DEMO_AUTH=true",
      "npm",
      "run",
      "dev",
      "--",
      "--hostname",
      "127.0.0.1",
      "--port",
      String(webPort),
    ].join(" "),
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    url: baseURL,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
