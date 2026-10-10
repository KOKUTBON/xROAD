import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

import {
  allScenarios,
  buildManifest,
  type BaselineManifest,
  type BaselineScenario,
} from "../scripts/baseline-scenarios.mjs";
import { installApiFixtures } from "./fixtures";

/**
 * Visual-baseline capture runner (#184).
 *
 * Fulfils the `screenshotPath` of every scenario in
 * `docs/ui-baseline/capture-manifest.json` — the 104-scenario matrix
 * (13 routes × 4 demo personas × 2 viewports) enumerated by the #167 audit.
 * Each persona is signed in through demo auth, the API is stubbed with the
 * shared e2e fixtures for deterministic content, and the route is screenshotted
 * at the scenario's viewport. `no-access` scenarios capture the guard/redirect
 * rather than failing.
 *
 * This is QA tooling, not app code: it lives behind `npm run baseline:capture`
 * and its own Playwright config, and is excluded from the default `e2e` run.
 */

// e2e/ -> apps/web -> apps -> repo root; the baseline lives at repo-root docs/.
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, "..", "..", "..");
const BASELINE_DIR = path.join(REPO_ROOT, "docs", "ui-baseline");
const MANIFEST_PATH = path.join(BASELINE_DIR, "capture-manifest.json");

// Manifest persona id -> the demo-profile button label on /login.
const PROFILE_LABEL: Record<string, string> = {
  analyst_bari: "Analyst for Bari",
  admin_regional: "Regional admin",
  traffic_engineer_bari: "Traffic engineer",
};

/** Read the committed manifest, or build (and persist) it if absent. */
function loadScenarios(): BaselineScenario[] {
  try {
    const manifest = JSON.parse(readFileSync(MANIFEST_PATH, "utf8")) as BaselineManifest;
    if (Array.isArray(manifest.scenarios) && manifest.scenarios.length > 0) {
      return manifest.scenarios;
    }
  } catch {
    // Fall through and synthesize the manifest from the shared model.
  }
  const manifest = buildManifest([]);
  mkdirSync(BASELINE_DIR, { recursive: true });
  writeFileSync(MANIFEST_PATH, `${JSON.stringify(manifest, null, 2)}\n`);
  return manifest.scenarios.length > 0 ? manifest.scenarios : allScenarios();
}

async function signInAs(page: Page, profileLabel: string) {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: /your road safety workspace/i })).toBeVisible();
  await page.getByRole("button", { name: new RegExp(profileLabel, "i") }).click();
  await page.waitForURL(/\/workspace/);
}

const scenarios = loadScenarios();

test.describe("UI baseline capture (#184)", () => {
  // Demo auth state lives in localStorage; capture serially for stable sessions.
  test.describe.configure({ mode: "serial" });

  for (const scenario of scenarios) {
    test(scenario.id, async ({ page }, testInfo) => {
      await installApiFixtures(page);
      await page.setViewportSize({
        width: scenario.viewport.width,
        height: scenario.viewport.height,
      });
      // Pin the theme before any document loads so the no-flash init script in
      // <head> reads it and applies data-theme — captures light + dark (#260).
      await page.addInitScript((theme) => {
        try {
          localStorage.setItem("road-risk-web-theme-v1", theme);
        } catch {
          // Ignore storage failures; capture proceeds with the default theme.
        }
      }, scenario.theme);

      const profileLabel = PROFILE_LABEL[scenario.persona.id];
      if (profileLabel) {
        await signInAs(page, profileLabel);
      }

      await page.goto(scenario.route, { waitUntil: "networkidle" }).catch(() => {
        // networkidle can be denied by long-poll/map sources; fall back below.
      });
      // Settle fonts, the no-flash theme attribute, and map/canvas paints.
      await page.waitForTimeout(500);

      const outputPath = path.join(REPO_ROOT, scenario.screenshotPath);
      mkdirSync(path.dirname(outputPath), { recursive: true });
      await page.screenshot({ path: outputPath, fullPage: true });

      testInfo.annotations.push(
        { type: "route", description: scenario.route },
        { type: "persona", description: scenario.persona.id },
        { type: "viewport", description: scenario.viewport.viewport },
        { type: "expectedAccess", description: scenario.expectedAccess },
      );
    });
  }
});
