import { test } from "@playwright/test";

test("Trace: Detailed flow of peer creation when peers available", async ({
  browser,
}) => {
  const context = await browser.newContext({
    permissions: ["microphone", "camera"],
  });
  const page = await context.newPage();

  const logs = [];
  let liveDebugArray = null;

  page.on("console", (msg) => {
    const text = msg.text();
    logs.push(text);
    // Print ALL logs containing [live] to see detailed flow
    if (text.includes("[live]")) {
      console.log(`>>> ${text}`);
    }
  });

  // Login
  await page.goto("http://localhost");
  await page.fill('input[type="email"]', "topubiswas1234@gmail.com");
  await page.fill('input[type="password"]', "topubiswas1234@gmail.com");
  await page.click('button:has-text("Sign in")');
  await page.waitForURL("**/world", { timeout: 30000 });
  await page.waitForTimeout(2000);

  console.log("\n=== GOING LIVE ===");

  const liveButton = await page.locator('button:has-text("Go Live")').first();
  if (await liveButton.isVisible()) {
    await liveButton.click();
    await page.waitForTimeout(6000);
  }

  console.log("\n=== CHECKING window.__LIVE_DEBUG ===");
  liveDebugArray = await page.evaluate(() => window.__LIVE_DEBUG || []);

  // Look for handlePeerList execution
  const peerListLogs = liveDebugArray.filter(
    (entry) =>
      entry.label.includes("Processing") ||
      entry.label.includes("Checking peer") ||
      entry.label.includes("Creating peer") ||
      entry.label.includes("live_peers received")
  );

  console.log(
    `\nLogs related to peer processing (${peerListLogs.length} total):`
  );
  peerListLogs.forEach((entry) => {
    console.log(`  [${entry.ts}] ${entry.label}`);
  });

  // Also show all [PEER] logs
  const peerLogs = liveDebugArray.filter((entry) =>
    entry.label.includes("[PEER]")
  );
  console.log(`\nAll [PEER] logs (${peerLogs.length} total):`);
  peerLogs.forEach((entry) => {
    console.log(`  [${entry.ts}] ${entry.label}`);
  });

  // Show the last 15 logs
  console.log(`\nLast 15 logs from window.__LIVE_DEBUG:`);
  liveDebugArray.slice(-15).forEach((entry) => {
    console.log(`  [${entry.ts}] ${entry.label}`);
  });

  await context.close();
});
