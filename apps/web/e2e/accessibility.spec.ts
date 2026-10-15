import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { installApiFixtures } from "./fixtures";

/**
 * WCAG 2.x A/AA accessibility gate (#177).
 *
 * Runs axe-core across every route with the shared API fixtures so content is
 * deterministic, and fails on any A/AA violation. Complements the
 * dependency-free token-contrast gate in `lib/contrast.test.ts`: that one pins
 * the palette, this one catches structural/ARIA/contrast issues on the rendered
 * pages. Runs under both the desktop and mobile projects via `npm run e2e`.
 */

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

async function expectNoAxeViolations(page: Page, label: string) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  const summary = results.violations
    .map((violation) => `${violation.id} [${violation.impact}] x${violation.nodes.length}`)
    .join("; ");
  expect(results.violations, `${label}: ${summary || "none"}`).toEqual([]);
}

async function signInAs(page: Page, profileLabel: string) {
  await page.goto("/login");
  await page.getByRole("button", { name: new RegExp(profileLabel, "i") }).click();
  await page.waitForURL(/\/workspace/);
}

// Internal routes reachable by the regional-admin demo profile (broadest role).
const INTERNAL_ROUTES = [
  "/workspace",
  "/workspace/executive",
  "/workspace/analyst?city=bari",
  "/workspace/scenarios",
  "/workspace/climate",
  "/workspace/operations",
  "/workspace/reports",
  "/workspace/uploads",
  "/workspace/automation",
  "/workspace/system-health",
  // Design gallery: exercises the new UX 2.0 primitives (segmented control,
  // grouped list, async states, icon set) under the axe gate (#259).
  "/workspace/_design",
];

test.describe("WCAG AA axe gate (#177)", () => {
  test("public home is free of A/AA violations", async ({ page }) => {
    await installApiFixtures(page);
    await page.goto("/", { waitUntil: "networkidle" }).catch(() => {});
    await page.waitForTimeout(500);
    await expectNoAxeViolations(page, "public home");
  });

  test("login is free of A/AA violations", async ({ page }) => {
    await installApiFixtures(page);
    await page.goto("/login", { waitUntil: "networkidle" }).catch(() => {});
    await page.waitForTimeout(300);
    await expectNoAxeViolations(page, "/login");
  });

  test("internal routes are free of A/AA violations", async ({ page }) => {
    test.setTimeout(120_000); // Eleven routes each run a full axe audit.
    await installApiFixtures(page);
    await signInAs(page, "Regional admin");
    for (const route of INTERNAL_ROUTES) {
      await page.goto(route, { waitUntil: "networkidle" }).catch(() => {});
      // Let the route's enter cascade settle before sampling contrast: the
      // reveal safety net fires at 400ms and the transition runs after it.
      await page.waitForTimeout(1200);
      await expectNoAxeViolations(page, route);
    }
  });
});
