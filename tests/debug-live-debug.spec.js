import { test } from "@playwright/test";

test("Debug: Print __LIVE_DEBUG contents", async ({ browser }) => {
  const context = await browser.newContext({
    permissions: ["microphone", "camera"],
  });
  const page = await context.newPage();

  const BASE_URL = "http://localhost";

  // Navigate and login
  await page.goto(BASE_URL, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);

  await page.fill('input[type="email"]', "topubiswas1234@gmail.com");
  await page.fill('input[type="password"]', "topubiswas1234@gmail.com");
  await page.click('button:has-text("Sign in")');
  await page.waitForURL("**/world", { timeout: 30000 });

  await page.waitForTimeout(5000);

  // Click on a land tile
  const canvas = page.locator("canvas").first();
  const canvasBox = await canvas.boundingBox();
  if (canvasBox) {
    await page.click("canvas", {
      position: { x: canvasBox.width / 2, y: canvasBox.height / 2 },
    });
    await page.waitForTimeout(2000);
  }

  // Click the button
  const goLiveBtn = page
    .locator("button")
    .filter({ has: page.locator("text=Go Live (Audio)") });
  await goLiveBtn.first().click();
  await page.waitForTimeout(2000);

  // Get __LIVE_DEBUG contents
  const debugLogs = await page.evaluate(() => {
    if (!window.__LIVE_DEBUG) return [];
    return window.__LIVE_DEBUG.map((entry, idx) => ({
      idx,
      label: entry.label,
      keys: entry.payload ? Object.keys(entry.payload) : [],
    }));
  });

  console.log("\n=== __LIVE_DEBUG CONTENTS ===");
  console.log(`Total entries: ${debugLogs.length}`);
  debugLogs.forEach((log) => {
    console.log(`[${log.idx}] ${log.label}`);
  });
});
