import { test } from "@playwright/test";

test("Debug: Check if SDP offers and answers are being exchanged", async ({
  browser,
}) => {
  const context = await browser.newContext({
    permissions: ["microphone", "camera"],
  });
  const page = await context.newPage();

  const logs = [];
  page.on("console", (msg) => {
    const text = msg.text();
    logs.push(text);
    if (
      text.includes("[OFFER]") ||
      text.includes("[ANSWER]") ||
      text.includes("[PEER]") ||
      text.includes("live_peers")
    ) {
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
    await page.waitForTimeout(5000); // Wait longer for offers/answers
  }

  console.log("\n=== SUMMARIZING ===");

  const offerLogs = logs.filter((log) => log.includes("[OFFER]"));
  const answerLogs = logs.filter((log) => log.includes("[ANSWER]"));
  const peerCreationLogs = logs.filter((log) => log.includes("[PEER]"));
  const peersMessages = logs.filter((log) =>
    log.includes("live_peers received")
  );

  console.log(`\nLive peers messages: ${peersMessages.length}`);
  peersMessages.forEach((log) => console.log(`  ${log}`));

  console.log(`\nPeer connections created: ${peerCreationLogs.length}`);
  peerCreationLogs.forEach((log) => console.log(`  ${log}`));

  console.log(`\nOffers received: ${offerLogs.length}`);
  offerLogs.forEach((log) => console.log(`  ${log}`));

  console.log(`\nAnswers created/sent: ${answerLogs.length}`);
  answerLogs.forEach((log) => console.log(`  ${log}`));

  console.log("\n=== CONCLUSION ===");
  if (
    peerCreationLogs.length === 0 &&
    peersMessages.some((p) => p.includes("peers: Array(0)"))
  ) {
    console.log("✅ Expected: No peers in room yet, so no connections created");
  }

  await context.close();
});
