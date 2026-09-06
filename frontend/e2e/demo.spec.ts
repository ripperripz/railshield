import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("import → monthly → detailed plan → stress → recovery → export", async ({
  page,
  request,
}) => {
  const raw = await request.post("/api/v1/datasets/generate", {
    data: { tasks: 6, sections: 2, days: 7, trains: 4, seed: 26027 },
  });
  expect(raw.ok()).toBeTruthy();
  const { dataset } = await raw.json();
  dataset.name = "Browser demo fixture";
  await page.goto("/");
  await page.getByRole("button", { name: "Data sources", exact: true }).click();
  await page.locator("input[type=file]").setInputFiles({
    name: "demo.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(dataset)),
  });
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Dataset validated and imported" }),
  ).toContainText("Dataset validated and imported");
  await page
    .getByRole("button", { name: "Command center", exact: true })
    .click();
  await page.getByRole("button", { name: "Build monthly plan" }).click();
  await expect(page.getByText(/6 tasks allocated/)).toBeVisible({
    timeout: 30000,
  });
  await expect(
    page.getByRole("button", { name: "Generate plan", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Generate plan", exact: true })
    .click();
  await expect(
    page.getByText("CONSTRAINTS VERIFIED", { exact: true }),
  ).toBeVisible({ timeout: 60000 });
  await expect(
    page.getByRole("heading", { name: "Possession timeline" }),
  ).toBeVisible();
  const accessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  await test
    .info()
    .attach("accessibility.json", {
      body: JSON.stringify(accessibility.violations, null, 2),
      contentType: "application/json",
    });
  expect(
    accessibility.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => ({
        target: n.target,
        summary: n.failureSummary,
      })),
    })),
  ).toEqual([]);
  await page.screenshot({
    path: "test-results/command-center.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Disruption lab", exact: true })
    .click();
  await page.getByRole("button", { name: "Run stress test" }).click();
  await expect(page.getByText(/20 scenarios remain feasible/)).toBeVisible({
    timeout: 30000,
  });
  await page.getByRole("button", { name: "Recover plan" }).click();
  await expect(page.getByText(/Recovered and verified/)).toBeVisible({
    timeout: 60000,
  });
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export plan" }).click();
  expect((await download).suggestedFilename()).toMatch(/railshield-plan/);
  await page.getByRole("button", { name: "Plan history", exact: true }).click();
  await expect(
    page.getByRole("cell", { name: "recovery", exact: false }).first(),
  ).toBeVisible();
});

test("mobile navigation and no page overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Command center" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Data sources", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Generate synthetic data" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({ path: "test-results/mobile.png", fullPage: true });
});
