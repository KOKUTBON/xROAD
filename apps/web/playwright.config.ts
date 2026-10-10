import { defineConfig, devices } from "@playwright/test";

const webPort = Number.parseInt(process.env.PLAYWRIGHT_WEB_PORT ?? "3100", 10);
const baseURL = `http://127.0.0.1:${webPort}`;
const browserChannel =
  process.env.PLAYWRIGHT_USE_SYSTEM_CHROME === "true" || process.env.CI ? "chrome" : undefined;

export default defineConfig({
  testDir: "./e2e",
  // The visual-baseline capture runner has its own config + npm script (#184).
  testIgnore: /(?:baseline-capture|static-demo)\.spec\.ts/,
  timeout: 45_000,
  expect: {
    timeout: 10_000,
  },
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI
    ? [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]]
    : [["list"]],
  use: {
    baseURL,
    channel: browserChannel,
    /*
     * Gates run with reduced motion (UX 3.0). The UI's enter animations fade
     * content in over a few hundred milliseconds; mid-transition opacity makes
     * axe's contrast sampling and visual baselines non-deterministic. Emulating
     * the reduced-motion preference exercises the accessible, settled state —
     * which is exactly the state these gates are asserting about.
     */
    contextOptions: { reducedMotion: "reduce" },
    screenshot: "only-on-failure",
    trace: "on-first-retry",
    video: process.env.CI ? "off" : "retain-on-failure",
  },
  webServer: {
    command: [
      "NEXT_TELEMETRY_DISABLED=1",
      "NEXT_PUBLIC_ENABLE_DEMO_AUTH=true",
      `NEXT_PUBLIC_API_BASE_URL=${baseURL}/api/backend`,
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
      name: "chromium-desktop",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { height: 900, width: 1440 },
      },
    },
    {
      name: "chromium-mobile",
      use: {
        ...devices["Pixel 5"],
        viewport: { height: 844, width: 390 },
      },
    },
  ],
});
