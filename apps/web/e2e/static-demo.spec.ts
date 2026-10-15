import { expect, test } from "@playwright/test";

test("static export loads data, filters maps, and persists fake auth without a backend", async ({ page }) => {
  const errors: string[] = [];
  const backendRequests: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    if (/\/api\/|:8000/.test(request.url())) backendRequests.push(request.url());
  });
  await page.goto("/xROAD/");
  await expect(page.getByRole("note")).toContainText("synthetic sample data");
  await expect(page.getByRole("heading", { name: /See the risk.*before the crash/ })).toBeVisible();
  await expect(page.getByLabel("Score band")).toBeVisible();
  await page.getByLabel("Score band").selectOption("very_high");
  await expect(page.getByText("tile-tirana-001").first()).toBeVisible();
  await page.getByLabel("Score band").selectOption("high");
  await expect(page.getByText("tile-tirana-002").first()).toBeVisible();
  await page.goto("/xROAD/workspace/analyst/");
  await expect(page).toHaveURL(/\/xROAD\/login/);
  await expect(page.getByRole("link", { name: /Institutional identity provider/ })).toHaveCount(0);
  await page.getByRole("button", { name: /Analyst for Tirana/ }).click();
  await expect(page).toHaveURL(/\/xROAD\/workspace\/analyst/);
  await expect(page.getByText("Central Tirana demo corridor", { exact: true }).first()).toBeVisible();
  await page.reload();
  await expect(page.getByText("Central Tirana demo corridor", { exact: true }).first()).toBeVisible();
  await page.goto("/xROAD/workspace/admin/");
  await expect(page.getByText("This workspace is outside your current role")).toBeVisible();
  await page.goto("/xROAD/login/");
  await page.getByRole("button", { name: /Demo admin/ }).click();
  for (const route of ["reports", "uploads", "automation", "climate", "scenarios"]) {
    const response = await page.goto(`/xROAD/workspace/${route}/`);
    expect(response?.status()).toBe(200);
    await expect(page.locator("main h1, main h2").first()).toBeVisible();
  }
  await page.goto("/xROAD/workspace/automation/");
  const trigger = page.getByRole("button", { name: /manual refresh|trigger refresh/i });
  await expect(trigger).toBeVisible();
  await trigger.click();
  await expect(page.getByText(/This action requires the institutional backend/)).toBeVisible();
  const images = await page.locator("img").evaluateAll((elements) => elements.every((image) => (image as HTMLImageElement).complete && (image as HTMLImageElement).naturalWidth > 0));
  expect(images).toBe(true);
  expect(backendRequests).toEqual([]);
  expect(errors).toEqual([]);
});
