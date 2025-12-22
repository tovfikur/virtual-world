import { test } from "@playwright/test";

test("Debug: Check LivePanel rendering", async ({ browser }) => {
  const context = await browser.newContext({
    permissions: ["microphone", "camera"],
  });
  const page = await context.newPage();

  const BASE_URL = "http://localhost";

  // Capture all logs
  const allLogs = [];
  page.on("console", (msg) => {
    allLogs.push(msg.text());
    console.log(`[CONSOLE] ${msg.text()}`);
  });

  // Navigate and login
  await page.goto(BASE_URL, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);

  await page.fill('input[type="email"]', "topubiswas1234@gmail.com");
  await page.fill('input[type="password"]', "topubiswas1234@gmail.com");
  await page.click('button:has-text("Sign in")');
  await page.waitForURL("**/world", { timeout: 30000 });

  // Wait for world to load
  await page.waitForTimeout(5000);

  // Click on a land tile to select it
  const canvas = page.locator("canvas").first();
  const canvasBox = await canvas.boundingBox();
  if (canvasBox) {
    await page.click("canvas", {
      position: { x: canvasBox.width / 2, y: canvasBox.height / 2 },
    });
    await page.waitForTimeout(2000);
  }

  // Check DOM
  console.log("\n=== DOM STRUCTURE CHECK ===");

  const chatBox = await page.$(".absolute.bottom-4.left-2");
  console.log(`✅ ChatBox div exists: ${!!chatBox}`);

  const livePanel = await page.$(
    '[class*="LivePanel"], [role="live"], [data-testid*="live"]'
  );
  console.log(`📊 LivePanel element found: ${!!livePanel}`);

  const goLiveBtn = await page.$('button:has-text("Go Live (Audio)")');
  console.log(`✅ Go Live button element: ${!!goLiveBtn}`);

  // Check what logs contain
  console.log("\n=== LOG ANALYSIS ===");
  const mountLogs = allLogs.filter(
    (l) => l.includes("[live]") && l.includes("mounted")
  );
  console.log(`[live] mount logs: ${mountLogs.length}`);

  const anyLiveLogs = allLogs.filter((l) => l.includes("[live]"));
  console.log(`Total [live] logs: ${anyLiveLogs.length}`);

  if (anyLiveLogs.length > 0) {
    console.log("Found [live] logs:");
    anyLiveLogs.forEach((log) => console.log(`  - ${log}`));
  }

  // Check if we can evaluate startLive in page context
  console.log("\n=== REACT COMPONENT CHECK ===");
  const startLiveExists = await page.evaluate(() => {
    // Look for React component in window
    return typeof window.__LIVE_DEBUG !== "undefined";
  });
  console.log(`window.__LIVE_DEBUG exists: ${startLiveExists}`);

  console.log("\n=== FINAL SUMMARY ===");
  console.log(`Go Live button visible: ${!!goLiveBtn}`);
  console.log(`[live] mount log captured: ${mountLogs.length > 0}`);
  console.log(`Total [live] logs: ${anyLiveLogs.length}`);
});
