const { test, expect } = require("@playwright/test");
const path = require("path");

test("world page renders with canvas", async ({ page }) => {
  const consoleLogs = [];
  page.on("console", (msg) => consoleLogs.push(`${msg.type()}: ${msg.text()}`));

  // Login to reach /world
  await page.goto("http://localhost/login", { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', "demo@example.com");
  await page.fill('input[type="password"]', "DemoPassword123!");
  await Promise.all([
    page.waitForURL("**/world", { timeout: 15000 }),
    page.click('button[type="submit"]'),
  ]);

  // Wait for Pixi to initialize and chunks to appear
  await page.waitForTimeout(4000);

  const canvas = page.locator("canvas");
  await expect(canvas).toBeVisible({ timeout: 10000 });

  const box = await canvas.boundingBox();
  expect(box?.width || 0).toBeGreaterThan(100);
  expect(box?.height || 0).toBeGreaterThan(100);

  const screenshotPath = path.join("test-results", "world.png");
  await page.screenshot({ path: screenshotPath, fullPage: true });

  console.log("Captured screenshot at:", screenshotPath);
  console.log("Console logs:");
  consoleLogs.forEach((line) => console.log(line));
});
