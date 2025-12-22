import { test, expect } from "@playwright/test";

test("Audio transmission flow - track addition and ontrack", async ({
  browser,
}) => {
  // Create two browser contexts (simulating two users)
  const context1 = await browser.newContext({
    permissions: ["microphone", "camera"],
  });
  const context2 = await browser.newContext({
    permissions: ["microphone", "camera"],
  });

  const page1 = await context1.newPage();
  const page2 = await context2.newPage();

  const logs1 = [];
  const logs2 = [];

  page1.on("console", (msg) => logs1.push(`[${msg.type()}] ${msg.text()}`));
  page2.on("console", (msg) => logs2.push(`[${msg.type()}] ${msg.text()}`));

  console.log("=== USER 1 LOGGING IN ===");

  // Login user 1
  await page1.goto("http://localhost");
  await page1.fill('input[type="email"]', "topubiswas1234@gmail.com");
  await page1.fill('input[type="password"]', "topubiswas1234@gmail.com");
  await page1.click('button:has-text("Sign in")');
  await page1.waitForURL("**/world", { timeout: 30000 });
  await page1.waitForTimeout(2000);

  console.log("=== USER 2 LOGGING IN ===");

  // Login user 2
  await page2.goto("http://localhost");
  await page2.fill('input[type="email"]', "testuser@test.com");
  await page2.fill('input[type="password"]', "TestPassword123!");
  await page2.click('button:has-text("Sign in")');
  await page2.waitForURL("**/world", { timeout: 30000 });
  await page2.waitForTimeout(2000);

  console.log("=== USER 1 GOES LIVE ===");

  // User 1 goes live
  const liveButton1 = await page1.locator('button:has-text("Go Live")').first();
  if (await liveButton1.isVisible()) {
    await liveButton1.click();
    await page1.waitForTimeout(3000);
  }

  console.log("=== USER 2 GOES LIVE ===");

  // User 2 goes live
  const liveButton2 = await page2.locator('button:has-text("Go Live")').first();
  if (await liveButton2.isVisible()) {
    await liveButton2.click();
    await page2.waitForTimeout(3000);
  }

  await page1.waitForTimeout(2000);
  await page2.waitForTimeout(2000);

  console.log("\n=== TRACK ADDITION LOGS (User 1) ===");
  const addTrackLogs1 = logs1.filter(
    (log) =>
      log.includes("added local track") ||
      log.includes("about to add local tracks")
  );
  addTrackLogs1.forEach((log) => console.log(log));
  console.log(`Total track addition logs: ${addTrackLogs1.length}`);

  console.log("\n=== ONTRACK LOGS (User 2 - should receive User 1 tracks) ===");
  const ontrackLogs2 = logs2.filter((log) =>
    log.includes("ontrack event fired")
  );
  ontrackLogs2.forEach((log) => console.log(log));
  console.log(`Total ontrack events: ${ontrackLogs2.length}`);

  console.log("\n=== KEY INDICATORS ===");
  const hasTrackAdded1 = logs1.some((log) => log.includes("added local track"));
  const hasOntrack2 = logs2.some((log) => log.includes("ontrack event fired"));
  const hasRemoteStream2 = logs2.some((log) =>
    log.includes("setting remote stream")
  );

  console.log(`✅ User 1 added local tracks: ${hasTrackAdded1}`);
  console.log(`⚠️ User 2 received ontrack event: ${hasOntrack2}`);
  console.log(`⚠️ User 2 set remote stream: ${hasRemoteStream2}`);

  // Check if audio element is getting the stream
  console.log("\n=== CHECKING AUDIO ELEMENTS ===");
  const audioElements2 = await page2.locator("audio").count();
  console.log(`Audio elements on page 2: ${audioElements2}`);

  if (hasTrackAdded1 && !hasOntrack2) {
    console.log(
      "\n❌ PROBLEM: Tracks were added on user 1 side, but user 2 never received ontrack event!"
    );
    console.log(
      "This suggests the RTCPeerConnection is not properly set up between peers."
    );
  }

  if (!hasTrackAdded1) {
    console.log(
      "\n❌ PROBLEM: Local stream was never added to RTCPeerConnection!"
    );
  }

  expect(hasTrackAdded1).toBeTruthy();
  expect(hasOntrack2).toBeTruthy();

  await context1.close();
  await context2.close();
});
