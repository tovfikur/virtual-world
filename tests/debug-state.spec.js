import { test } from "@playwright/test";

test("Debug: Check room and land state when button visible", async ({
  browser,
}) => {
  const context = await browser.newContext({
    permissions: ["microphone", "camera"],
  });
  const page = await context.newPage();

  const BASE_URL = "http://localhost";

  // Capture logs
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

  // Evaluate what's happening in the page
  const pageState = await page.evaluate(() => {
    // Check if there's a "Go Live" button
    const buttons = Array.from(document.querySelectorAll("button"));
    const goLiveBtn = buttons.find((b) =>
      b.textContent.includes("Go Live (Audio)")
    );

    return {
      buttonExists: !!goLiveBtn,
      buttonVisible: goLiveBtn
        ? window.getComputedStyle(goLiveBtn).display !== "none"
        : false,
      buttonDisabled: goLiveBtn ? goLiveBtn.disabled : false,
      buttonParentClasses: goLiveBtn ? goLiveBtn.parentElement?.className : "",
    };
  });

  console.log("\n=== PAGE STATE ===");
  console.log(`Button Exists: ${pageState.buttonExists}`);
  console.log(`Button Visible: ${pageState.buttonVisible}`);
  console.log(`Button Disabled: ${pageState.buttonDisabled}`);
  console.log(`Button Parent Classes: ${pageState.buttonParentClasses}`);

  // Try to check what room is set
  const windowState = await page.evaluate(() => {
    return {
      hasWindow: typeof window !== "undefined",
      hasLiveDebug: typeof window.__LIVE_DEBUG !== "undefined",
      liveDebugLength: window.__LIVE_DEBUG ? window.__LIVE_DEBUG.length : 0,
    };
  });

  console.log("\n=== WINDOW STATE ===");
  console.log(`Has __LIVE_DEBUG: ${windowState.hasLiveDebug}`);
  console.log(`__LIVE_DEBUG entries: ${windowState.liveDebugLength}`);

  // Now click the button
  const goLiveBtn = page
    .locator("button")
    .filter({ has: page.locator("text=Go Live (Audio)") });
  await goLiveBtn.first().click();
  await page.waitForTimeout(2000);

  console.log("\n=== AFTER CLICK ===");
  const liveDebugAfter = await page.evaluate(() => {
    return window.__LIVE_DEBUG ? window.__LIVE_DEBUG.length : 0;
  });
  console.log(`__LIVE_DEBUG entries after click: ${liveDebugAfter}`);

  // Check all logs
  console.log("\n=== ALL LOGS ===");
  allLogs.forEach((log, i) => {
    if (log.includes("[live]") || log.includes("[START]")) {
      console.log(`  [${i}] ⭐ ${log}`);
    }
  });
});
