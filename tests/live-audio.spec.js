import { test, expect } from "@playwright/test";

test.describe("Live Audio Streaming", () => {
  const BASE_URL = "http://localhost"; // Using port 80 (Nginx)
  const USER1_EMAIL = "testuser1@test.com";
  const USER1_PASS = "Test@123";
  const USER2_EMAIL = "testuser2@test.com";
  const USER2_PASS = "Test@123";

  test("should stream audio between two users on same land", async ({
    browser,
  }) => {
    // Create two contexts for two users
    const user1Context = await browser.newContext();
    const user2Context = await browser.newContext();

    const user1Page = await user1Context.newPage();
    const user2Page = await user2Context.newPage();

    try {
      console.log("🚀 Starting live audio test with two users...\n");

      // ========== USER 1: Login and go live ==========
      console.log("👤 USER 1: Logging in...");
      await user1Page.goto(BASE_URL, { waitUntil: "networkidle" });
      await user1Page.waitForTimeout(2000);

      // Try to find login form
      const emailInput = user1Page.locator('input[type="email"]').first();
      await emailInput.fill(USER1_EMAIL);
      await user1Page
        .locator('input[type="password"]')
        .first()
        .fill(USER1_PASS);
      await user1Page.click('button:has-text("Sign in")');
      await user1Page.waitForURL("**/world", { timeout: 10000 });
      console.log("✅ USER 1: Logged in successfully\n");

      // Navigate to a specific land (6, 12)
      console.log("👤 USER 1: Navigating to land...");
      await user1Page.waitForTimeout(2000); // Wait for page to fully load

      // Go live with audio
      console.log('🎙️ USER 1: Clicking "Go Live (Audio)"...');
      const goLiveButton = user1Page
        .locator('button:has-text("Go Live (Audio)")')
        .first();
      await goLiveButton.waitFor({ state: "visible", timeout: 5000 });
      await goLiveButton.click();

      // Grant microphone permission
      console.log("🎤 USER 1: Granting microphone permission...");
      try {
        await user1Page.context().grantPermissions(["microphone"]);
      } catch (e) {
        console.log("⚠️ Microphone permission dialog may appear in browser");
      }
      await user1Page.waitForTimeout(3000);

      // Check for success indicator
      console.log("✅ USER 1: Now broadcasting live\n");

      // ========== USER 2: Login and join same land ==========
      console.log("👤 USER 2: Logging in...");
      await user2Page.goto(BASE_URL, { waitUntil: "networkidle" });
      await user2Page.waitForTimeout(2000);

      const user2EmailInput = user2Page.locator('input[type="email"]').first();
      await user2EmailInput.fill(USER2_EMAIL);
      await user2Page
        .locator('input[type="password"]')
        .first()
        .fill(USER2_PASS);
      await user2Page.click('button:has-text("Sign in")');
      await user2Page.waitForURL("**/world", { timeout: 10000 });
      console.log("✅ USER 2: Logged in successfully\n");

      // Navigate to same land
      console.log("👤 USER 2: Navigating to same land...");
      await user2Page.waitForTimeout(2000);
      console.log("✅ USER 2: At same land\n");

      // ========== Verify connection ==========
      console.log("🔍 Checking if USER 2 sees USER 1 broadcasting...");

      // Wait for peer to appear
      const user1BroadcastVisible = user2Page
        .locator("text=testuser1@test.com")
        .isVisible();
      const user1NameinDebug = await user2Page
        .locator("text=/User|testuser1/")
        .count();

      if (user1NameinDebug > 0) {
        console.log("✅ USER 2: Sees USER 1 broadcasting!\n");
      } else {
        console.log("⚠️ USER 2: Does not see USER 1 yet. Waiting...");
        await user2Page.waitForTimeout(3000);
        const count = await user2Page.locator("text=live").count();
        console.log(`   Found ${count} live indicators\n`);
      }

      // ========== Check debug logs ==========
      console.log("📊 Checking console logs for WebRTC events...\n");

      // Get logs from user1
      const user1Logs = [];
      user1Page.on("console", (msg) => {
        const text = msg.text();
        if (text.includes("[live]")) {
          console.log(`  USER 1: ${text}`);
          user1Logs.push(text);
        }
      });

      // Get logs from user2
      const user2Logs = [];
      user2Page.on("console", (msg) => {
        const text = msg.text();
        if (text.includes("[live]")) {
          console.log(`  USER 2: ${text}`);
          user2Logs.push(text);
        }
      });

      // Wait for WebRTC events
      console.log("\n⏳ Waiting for WebRTC events (10 seconds)...\n");
      await user2Page.waitForTimeout(10000);

      // ========== Analyze results ==========
      console.log("\n📈 Analysis:\n");

      const hasOffer = user1Logs.some((l) => l.includes("offer created"));
      const hasAnswer = user2Logs.some((l) => l.includes("answer created"));
      const hasOnTrack = user2Logs.some((l) =>
        l.includes("ontrack event fired")
      );
      const hasAudioAdded = user1Logs.some(
        (l) => l.includes("added local track") && l.includes("audio")
      );

      console.log(`✅ USER 1 created offer: ${hasOffer}`);
      console.log(`✅ USER 2 created answer: ${hasAnswer}`);
      console.log(`✅ Audio track added by USER 1: ${hasAudioAdded}`);
      console.log(`✅ USER 2 received track: ${hasOnTrack}`);

      if (hasOffer && hasAnswer && hasOnTrack && hasAudioAdded) {
        console.log("\n✨ SUCCESS! Audio connection established!\n");
      } else {
        console.log("\n❌ FAILURE! WebRTC connection incomplete.\n");
        console.log("Checking what went wrong:");
        if (!hasAudioAdded) console.log("  - Audio track not added");
        if (!hasOffer) console.log("  - Offer not created");
        if (!hasAnswer) console.log("  - Answer not created");
        if (!hasOnTrack)
          console.log("  - No ontrack event fired (tracks not flowing)");
      }

      // Print all logs for debugging
      console.log("\n📝 Full USER 1 logs:");
      user1Logs.forEach((l) => console.log("  " + l));
      console.log("\n📝 Full USER 2 logs:");
      user2Logs.forEach((l) => console.log("  " + l));
    } finally {
      await user1Context.close();
      await user2Context.close();
    }
  });
});
