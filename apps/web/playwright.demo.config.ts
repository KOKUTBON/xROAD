import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e", testMatch: "static-demo.spec.ts", timeout: 45_000,
  fullyParallel: false, workers: 1, reporter: "list",
  use: { baseURL: "http://127.0.0.1:4173", contextOptions: { reducedMotion: "reduce" }, screenshot: "only-on-failure" },
  webServer: { command: "npm run preview:demo", url: "http://127.0.0.1:4173/xROAD/", reuseExistingServer: !process.env.CI },
  projects: [
    { name: "demo-desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "demo-mobile", use: { ...devices["Pixel 5"] } },
  ],
});
