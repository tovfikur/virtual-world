import { test, expect } from "@playwright/test";

test.describe("Live Audio Streaming Test", () => {
  const BASE_URL = "http://localhost";

  const USER1_EMAIL = "topubiswas1234@gmail.com";
  const USER1_PASSWORD = "topubiswas1234@gmail.com";

  const USER2_EMAIL = "demo@example.com";
  const USER2_PASSWORD = "DemoPassword123!";

  test("Test live audio between two users", async ({ browser }, testInfo) => {
    testInfo.setTimeout(60000); // 60 second timeout
    console.log("\n🚀 Starting Live Audio Test\n");

    // Create two browser contexts WITH media permissions and fake media devices
    const user1Context = await browser.newContext({
      permissions: ["microphone", "camera"],
    });
    const user2Context = await browser.newContext({
      permissions: ["microphone", "camera"],
    });

    const user1Page = await user1Context.newPage();
    const user2Page = await user2Context.newPage();

    try {
      // ========== USER 1: LOGIN ==========
      console.log("👤 USER 1: Logging in...");
      await user1Page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
      await user1Page.waitForTimeout(2000);

      // Find and fill login form
      const user1Email = user1Page.locator('input[type="email"]').first();
      await user1Email.fill(USER1_EMAIL);

      const user1Pass = user1Page.locator('input[type="password"]').first();
      await user1Pass.fill(USER1_PASSWORD);

      await user1Page.click('button:has-text("Sign in")');

      // Wait for navigation to world page
      await user1Page.waitForURL("**/world", { timeout: 30000 });
      console.log("✅ USER 1: Logged in\n");

      await user1Page.waitForTimeout(3000); // Wait for page to settle

      // ========== USER 2: LOGIN ==========
      console.log("👤 USER 2: Logging in...");
      // Grant permissions BEFORE loading the page
      await user2Context.grantPermissions(["microphone", "camera"]);
      await user2Page.goto(BASE_URL, { waitUntil: "networkidle" });
      await user2Page.waitForTimeout(3000);

      const user2Email = user2Page.locator('input[type="email"]').first();
      await user2Email.fill(USER2_EMAIL);

      const user2Pass = user2Page.locator('input[type="password"]').first();
      await user2Pass.fill(USER2_PASSWORD);

      await user2Page.click('button:has-text("Sign in")');
      await user2Page.waitForURL("**/world", { timeout: 30000 });
      console.log("✅ USER 2: Logged in\n");

      await user2Page.waitForTimeout(3000);

      // ========== NAVIGATE BOTH USERS TO SAME LAND ==========
      console.log("🗺️ Navigating both users to the same land...");
      // Navigate to a specific land using the URL
      const landUrl = `${BASE_URL}/land/100/100`;

      await user1Page.goto(landUrl, { waitUntil: "networkidle" });
      await user1Page.waitForTimeout(3000);
      console.log("✅ USER 1 navigated to land 100,100");

      await user2Page.goto(landUrl, { waitUntil: "networkidle" });
      await user2Page.waitForTimeout(3000);
      console.log("✅ USER 2 navigated to same land 100,100\n");

      // ========== COLLECT CONSOLE LOGS ==========
      const user1Logs = [];
      const user2Logs = [];

      // Set up console listeners BEFORE going live
      user1Page.on("console", (msg) => {
        const text = msg.text();
        user1Logs.push(text);
        console.log(`  [USER 1 CONSOLE] ${text}`);
      });

      user2Page.on("console", (msg) => {
        const text = msg.text();
        user2Logs.push(text);
        console.log(`  [USER 2 CONSOLE] ${text}`);
      });

      // Wait a moment for listeners to be ready
      await user1Page.waitForTimeout(500);
      await user2Page.waitForTimeout(500);

      // ========== USER 1: GO LIVE ==========
      console.log("\n🎙️ USER 1: Going Live with Audio...\n");

      // First test if getUserMedia works
      const mediaTest = await user1Page.evaluate(async () => {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({
            audio: true,
          });
          stream.getTracks().forEach((t) => t.stop());
          return { success: true };
        } catch (e) {
          return { success: false, error: e.message, name: e.name };
        }
      });
      console.log(`📱 getUserMedia test on USER 1:`, mediaTest);

      const goLiveButton = user1Page
        .locator('button:has-text("Go Live (Audio)")')
        .first();

      // Wait for button to be visible
      await goLiveButton.waitFor({ state: "visible", timeout: 10000 });
      console.log("✅ Found Go Live button");

      // Check if button is enabled
      const isDisabled = await goLiveButton.evaluate((el) => el.disabled);
      console.log(`Button disabled state: ${isDisabled}`);

      // If button is disabled (isLive=true from previous session), click Stop first
      if (isDisabled) {
        console.log("⏹️ Button disabled, clicking Stop first...");
        const stopButton = user1Page.locator('button:has-text("Stop")').first();
        await stopButton.click();
        await user1Page.waitForTimeout(2000);
      }

      // Take screenshot before clicking
      await user1Page.screenshot({ path: "before-click.png" });
      console.log("📸 Screenshot before click saved");

      // Click it
      await goLiveButton.click();
      console.log("✅ Clicked Go Live button");

      // Give it time to process
      await user1Page.waitForTimeout(2000);

      // Check if anything happened
      const debugLog = await user1Page.evaluate(() => {
        return window.__LIVE_DEBUG || [];
      });
      console.log(`📋 Debug log length: ${debugLog.length} entries`);
      if (debugLog.length > 0) {
        console.log("✅ FULL debug log:");
        debugLog.forEach((entry, i) => {
          console.log(
            `  [${i}] ${entry.label}:`,
            JSON.stringify(entry.payload)
          );
        });
      }

      // Wait for UI to show live status
      await user1Page.waitForTimeout(5000);

      // Take screenshot after clicking
      await user1Page.screenshot({ path: "after-click.png" });
      console.log("📸 Screenshot after click saved");

      console.log("\n⏳ Waiting for WebRTC connection (10 seconds)...\n");
      await user2Page.waitForTimeout(10000);

      // ========== GET USER 2 DEBUG LOG ==========
      const user2DebugLog = await user2Page.evaluate(() => {
        return window.__LIVE_DEBUG || [];
      });
      console.log(
        `📋 USER 2 Debug log length: ${user2DebugLog.length} entries`
      );
      if (user2DebugLog.length > 0) {
        console.log("USER 2 recent debug entries:");
        user2DebugLog.slice(-10).forEach((entry, i) => {
          console.log(
            `  [${user2DebugLog.length - 10 + i}] ${entry.label}:`,
            JSON.stringify(entry.payload)
          );
        });
      }

      // ========== ANALYZE RESULTS ==========
      console.log("\n📊 TEST RESULTS:\n");

      const hasAudioTrack = user1Logs.some(
        (l) => l.includes("✅ added local track") && l.includes("audio")
      );
      const hasMediaGranted = user1Logs.some((l) =>
        l.includes("media granted")
      );
      const hasOfferCreated = user1Logs.some((l) =>
        l.includes("✅ offer created")
      );
      const hasAnswerCreated =
        user2Logs.some((l) => l.includes("✅ answer created")) ||
        user2DebugLog.some((l) => l.label.includes("answer created"));
      const hasOnTrack =
        user2Logs.some((l) => l.includes("🎵 ontrack event fired")) ||
        user2DebugLog.some((l) => l.label.includes("ontrack event"));
      const hasAudioTrackReceived =
        user2Logs.some((l) => l.includes("ontrack") && l.includes("audio")) ||
        user2DebugLog.some(
          (l) =>
            l.label.includes("ontrack") &&
            JSON.stringify(l.payload).includes("audio")
        );

      console.log("USER 1 (Broadcaster):");
      console.log(`  ✓ Media Granted: ${hasMediaGranted}`);
      console.log(`  ✓ Audio Track Added: ${hasAudioTrack}`);
      console.log(`  ✓ Offer Created: ${hasOfferCreated}`);

      console.log("\nUSER 2 (Listener):");
      console.log(`  ✓ Received ontrack Event: ${hasOnTrack}`);
      console.log(`  ✓ Audio Track Received: ${hasAudioTrackReceived}`);
      console.log(`  ✓ Answer Created: ${hasAnswerCreated}`);

      // Final verdict
      console.log("\n" + "=".repeat(60));
      if (hasAudioTrack && hasAnswerCreated && hasOnTrack) {
        console.log("✨ SUCCESS! Audio connection established!");
        console.log("🔊 User 2 should be able to hear User 1");
      } else {
        console.log("❌ FAILURE! WebRTC connection incomplete");
        console.log("\nDEBUGGING INFO:");
        if (!hasAudioTrack) {
          console.log(
            "  ❌ Audio track was not added (getUserMedia may have failed)"
          );
        }
        if (!hasAnswerCreated) {
          console.log(
            "  ❌ Answer was not created (offer may not have been received)"
          );
        }
        if (!hasOnTrack) {
          console.log("  ❌ No ontrack event (audio not flowing)");
        }
      }
      console.log("=".repeat(60) + "\n");

      // Print full logs for debugging
      console.log("📝 FULL LOG SEQUENCE:\n");
      console.log("USER 1 Logs:");
      user1Logs.forEach((log, i) => console.log(`  ${i + 1}. ${log}`));

      console.log("\nUSER 2 Logs:");
      user2Logs.forEach((log, i) => console.log(`  ${i + 1}. ${log}`));
    } finally {
      await user1Context.close();
      await user2Context.close();
    }
  });
});
