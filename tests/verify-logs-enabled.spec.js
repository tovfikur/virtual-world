import { test, expect } from "@playwright/test";

test("Verify console.log is enabled in frontend", async ({ page, context }) => {
  // Capture console messages
  const consoleLogs = [];
  page.on("console", (msg) => {
    consoleLogs.push({
      type: msg.type(),
      text: msg.text(),
    });
  });

  // Navigate and login
  await page.goto("http://localhost");
  await page.fill('input[type="email"]', "topubiswas1234@gmail.com");
  await page.fill('input[type="password"]', "topubiswas1234@gmail.com");
  await page.click('button:has-text("Sign in")');
  await page.waitForURL("**/world", { timeout: 30000 });

  // Wait a moment for any initialization logs
  await page.waitForTimeout(2000);

  // Check if any [live] logs appeared in console (should be during init)
  const liveLogs = consoleLogs.filter((log) => log.text.includes("[live]"));
  console.log("Console logs captured:", consoleLogs.length);
  console.log("[live] logs captured:", liveLogs.length);
  console.log("Sample logs:", consoleLogs.slice(0, 5));

  // Now click Go Live button
  const liveButton = await page.locator('button:has-text("Go Live")').first();
  if (await liveButton.isVisible()) {
    await liveButton.click();
    await page.waitForTimeout(2000);
  }

  // Check logs after button click
  const liveLogsAfter = consoleLogs.filter((log) =>
    log.text.includes("[live]")
  );
  console.log("Total console logs after click:", consoleLogs.length);
  console.log("[live] logs after click:", liveLogsAfter.length);

  // Print all console logs for inspection
  console.log("\n=== ALL CONSOLE LOGS ===");
  consoleLogs.forEach((log, idx) => {
    console.log(`[${idx}] ${log.type.toUpperCase()}: ${log.text}`);
  });

  // Assertion: we should have console.log working now
  expect(consoleLogs.length).toBeGreaterThan(0);
});
