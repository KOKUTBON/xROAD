import { expect, test, type Page, type TestInfo } from "@playwright/test";

import { installApiFixtures } from "./fixtures";

async function signInAs(page: Page, profileLabel: string) {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: /your road safety workspace/i })).toBeVisible();
  await page.getByRole("button", { name: new RegExp(profileLabel, "i") }).click();
  await page.waitForURL(/\/workspace/);
}

async function assertKeyboardReachable(page: Page) {
  await page.keyboard.press("Tab");
  const focusedElement = await page.evaluate(() => {
    const focused = document.activeElement;
    if (!focused || focused === document.body) {
      return null;
    }
    return {
      tagName: focused.tagName,
      text: focused.textContent?.trim() ?? "",
      label: focused.getAttribute("aria-label") ?? "",
    };
  });
  expect(focusedElement).not.toBeNull();
}

async function assertResponsivePage(page: Page) {
  const overflow = await page.evaluate(() => {
    const documentWidth = Math.max(
      document.documentElement.scrollWidth,
      document.body.scrollWidth,
    );
    return documentWidth - window.innerWidth;
  });
  expect(overflow).toBeLessThanOrEqual(24);
}

async function assertAccessibleBaseline(page: Page) {
  await expect(page.locator("h1, h2, h3").first()).toBeVisible();

  const unlabeledControls = await page
    .locator("button, a[href], input, select, textarea")
    .evaluateAll((elements) =>
      elements
        .filter((element) => {
          const style = window.getComputedStyle(element);
          const rect = element.getBoundingClientRect();
          return (
            style.display !== "none" &&
            style.visibility !== "hidden" &&
            rect.width > 0 &&
            rect.height > 0 &&
            !element.hasAttribute("disabled")
          );
        })
        .map((element) => {
          const control = element as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;
          const labelText = control.labels
            ? Array.from(control.labels)
                .map((label) => label.textContent?.trim())
                .filter(Boolean)
                .join(" ")
            : "";
          const accessibleName = [
            element.getAttribute("aria-label"),
            element.getAttribute("title"),
            element.textContent,
            "placeholder" in control ? control.placeholder : "",
            labelText,
          ]
            .map((value) => value?.trim())
            .find(Boolean);
          return accessibleName
            ? null
            : `${element.tagName.toLowerCase()}${element.id ? `#${element.id}` : ""}`;
        })
        .filter((value): value is string => Boolean(value)),
    );
  expect(unlabeledControls).toEqual([]);

  const imagesMissingAlt = await page.locator("img").evaluateAll((images) =>
    images
      .filter((image) => !image.hasAttribute("alt"))
      .map((image) => image.getAttribute("src") ?? "img"),
  );
  expect(imagesMissingAlt).toEqual([]);
}

async function attachVisualSmoke(page: Page, testInfo: TestInfo, name: string) {
  const screenshot = await page.screenshot({
    animations: "disabled",
    fullPage: true,
  });
  await testInfo.attach(`${testInfo.project.name}-${name}`, {
    body: screenshot,
    contentType: "image/png",
  });
}

async function assertPageReleaseGate(page: Page, testInfo: TestInfo, name: string) {
  await assertKeyboardReachable(page);
  await assertAccessibleBaseline(page);
  await assertResponsivePage(page);
  await attachVisualSmoke(page, testInfo, name);
}

test.beforeEach(async ({ page }) => {
  await installApiFixtures(page);
});

test("public map and login gates work for citizens", async ({ page }, testInfo) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: /See the risk.*before the crash/ })).toBeVisible();
  await expect(page.getByText("Public risk map")).toBeVisible();
  await expect(page.getByText("Public detail panel")).toBeVisible();
  await page.getByLabel("Score band").selectOption("very_high");
  await expect(page.getByText("tile-bari-001")).toBeVisible();

  await assertPageReleaseGate(page, testInfo, "public-map");

  await page.goto("/login");
  await expect(page.getByRole("link", { name: /institutional identity provider/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /analyst for bari/i })).toBeVisible();
  await assertPageReleaseGate(page, testInfo, "login");
});

test("analyst workspace includes map workflow and role-denied admin state", async ({ page }, testInfo) => {
  await signInAs(page, "Analyst for Bari");

  await page.goto("/workspace");
  await expect(page.getByText("Municipal safety control room")).toBeVisible();
  await assertPageReleaseGate(page, testInfo, "workspace-overview");

  await page.goto("/workspace/analyst");
  await expect(page.getByText("Analyst risk explorer")).toBeVisible();
  await expect(page.getByText("Internal risk map")).toBeVisible();
  await expect(page.getByText("Selected feature")).toBeVisible();
  await page.getByRole("button", { name: "Junctions" }).click();
  await expect(page.getByRole("button", { name: "Junctions" })).toBeVisible();
  await assertPageReleaseGate(page, testInfo, "analyst-map");

  await page.goto("/workspace/uploads");
  await expect(page.getByText("This workspace is outside your current role")).toBeVisible();
  await assertPageReleaseGate(page, testInfo, "no-access");
});

test("admin can use upload, reports, governance, and automation workflows", async ({ page }, testInfo) => {
  await signInAs(page, "Regional admin");

  await page.goto("/workspace/uploads");
  await expect(page.locator(".eyebrow", { hasText: /^Upload center$/ })).toBeVisible();
  await page
    .locator('input[type="file"]')
    .setInputFiles({
      name: "bari-crashes.csv",
      mimeType: "text/csv",
      buffer: Buffer.from("crash_id,latitude,longitude\nA-1,41.12,16.86\nA-2,41.13,16.87\n"),
    });
  await expect(page.getByText("CSV detection")).toBeVisible();
  await page.getByRole("button", { name: "Register, upload, and validate" }).click();
  await expect(page.getByText("validated_ready").first()).toBeVisible();
  await expect(page.getByText("Accepted rows")).toBeVisible();
  await assertPageReleaseGate(page, testInfo, "upload-center");

  await page.goto("/workspace/reports");
  await expect(page.getByText("Generate, review, download, and publish")).toBeVisible();
  await page.getByRole("button", { name: "Generate" }).first().click();
  await expect(page.getByText(/generated monthly safety overview/i)).toBeVisible();
  await assertPageReleaseGate(page, testInfo, "reports");

  await page.goto("/workspace/admin");
  await expect(page.getByText("Governed source actions")).toBeVisible();
  await expect(page.getByText("User and access management")).toBeVisible();
  await assertPageReleaseGate(page, testInfo, "admin-control");

  await page.goto("/workspace/automation");
  await expect(page.getByText("Keep data refreshes")).toBeVisible();
  await page.getByRole("button", { name: "Trigger manual refresh" }).click();
  await expect(page.getByText("Manual refresh queued.")).toBeVisible();
  await assertPageReleaseGate(page, testInfo, "automation");
});

test("traffic engineer sees VRU and signal-phase operations gates", async ({ page }, testInfo) => {
  await signInAs(page, "Traffic engineer");

  await page.goto("/workspace/operations");
  await expect(page.getByText("Production scope and capability gates")).toBeVisible();
  await expect(page.getByText("signal write actions disabled")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Signal-phase operator board" })).toBeVisible();
  await assertPageReleaseGate(page, testInfo, "traffic-operations");
});
