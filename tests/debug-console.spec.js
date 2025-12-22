import { test } from "@playwright/test";

test("Debug: Capture Console from Start", async ({ browser }) => {
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

  console.log(`📊 Console logs so far: ${allLogs.length}`);
  const liveLogs = allLogs.filter((l) => l.includes("[live]"));
  console.log(`📊 [live] logs so far: ${liveLogs.length}\n`);

  // Click Go Live button
  console.log("🖱️ Clicking Go Live (Audio) button...");
  const goLiveBtn = page.locator('button:has-text("Go Live (Audio)")').first();
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
