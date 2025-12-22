import { test } from "@playwright/test";

test("Debug: Select Land Then Go Live", async ({ browser }) => {
  const context = await browser.newContext({
    permissions: ["microphone", "camera"],
  });
  const page = await context.newPage();

  const BASE_URL = "http://localhost";

  // ATTACH CONSOLE LISTENER IMMEDIATELY
  const allLogs = [];
  page.on("console", (msg) => {
    allLogs.push(msg.text());
    console.log(`[CONSOLE] ${msg.text()}`);
  });

  console.log("\n🔍 DEBUG: Console listener attached\n");

  // Login
  console.log("👤 Logging in...");
  await page.goto(BASE_URL, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);

  await page.fill('input[type="email"]', "topubiswas1234@gmail.com");
  await page.fill('input[type="password"]', "topubiswas1234@gmail.com");
  await page.click('button:has-text("Sign in")');
  await page.waitForURL("**/world", { timeout: 30000 });
  console.log("✅ Logged in\n");

  // Wait for world to load
  await page.waitForTimeout(5000);

  // Click on a land tile to select it
  console.log("🌍 Clicking on canvas to select land...");
  const canvas = page.locator("canvas").first();
  const canvasBox = await canvas.boundingBox();
  if (canvasBox) {
    await page.click("canvas", {
      position: { x: canvasBox.width / 2, y: canvasBox.height / 2 },
    });
    console.log("✅ Clicked on map");
    await page.waitForTimeout(2000);
  }

  console.log(`\n📊 After land selection:`);
  console.log(`  Total logs: ${allLogs.length}`);
  console.log(
    `  [live] logs: ${allLogs.filter((l) => l.includes("[live]")).length}\n`
  );

  // Check if Go Live button is visible
  const goLiveBtn = page.locator('button:has-text("Go Live (Audio)")').first();
  const isVisible = await goLiveBtn.isVisible().catch(() => false);
  console.log(`🎬 Go Live button visible: ${isVisible}`);

  if (!isVisible) {
    console.log("❌ Button not visible - land may not be selected");
    console.log("\nAll logs:");
    allLogs.forEach((log, i) => console.log(`  [${i}] ${log}`));
    return;
  }

  // Click Go Live button
  console.log("🖱️ Clicking Go Live (Audio) button...");
  await goLiveBtn.click();
  console.log("✅ Click executed\n");

  // Wait for handler to execute
  await page.waitForTimeout(3000);

  console.log(`\n📊 FINAL RESULTS:`);
  console.log(`  Total console logs: ${allLogs.length}`);

  const liveLogsAfter = allLogs.filter((l) => l.includes("[live]"));
  console.log(`  [live] logs: ${liveLogsAfter.length}`);

  if (liveLogsAfter.length > 0) {
    console.log(`\n✅ [live] MESSAGES CAPTURED:`);
    liveLogsAfter.forEach((log) => console.log(`  - ${log}`));
  } else {
    console.log(`\n❌ NO [live] LOGS - startLive() not called or not logging`);
    console.log(`\nAll console messages:`);
    allLogs.forEach((log, i) => {
      console.log(`  [${i}] ${log}`);
    });
  }
});
