import { test } from "@playwright/test";

test("Manual Audio Test - Keep Browsers Open", async ({ browser }) => {
  const user1Context = await browser.newContext({
    permissions: ["microphone", "camera"],
  });
  const user2Context = await browser.newContext({
    permissions: ["microphone", "camera"],
  });

  const user1Page = await user1Context.newPage();
  const user2Page = await user2Context.newPage();

  const BASE_URL = "http://localhost";

  console.log("\n🚀 MANUAL TEST - BROWSERS OPEN AND READY\n");
  console.log("USER 1: topubiswas1234@gmail.com / topubiswas1234@gmail.com");
  console.log("USER 2: demo@example.com / DemoPassword123!\n");

  // ========== USER 1: LOGIN ==========
  console.log("👤 USER 1: Logging in...");
  await user1Context.grantPermissions(["microphone", "camera"]);
  await user1Page.goto(BASE_URL, { waitUntil: "networkidle" });
  await user1Page.waitForTimeout(2000);

  const user1Email = user1Page.locator('input[type="email"]').first();
  await user1Email.fill("topubiswas1234@gmail.com");

  const user1Pass = user1Page.locator('input[type="password"]').first();
  await user1Pass.fill("topubiswas1234@gmail.com");

  await user1Page.click('button:has-text("Sign in")');
  await user1Page.waitForURL("**/world", { timeout: 30000 });
  console.log("✅ USER 1: Logged in and ready\n");

  // ========== USER 2: LOGIN ==========
  console.log("👤 USER 2: Logging in...");
  await user2Context.grantPermissions(["microphone", "camera"]);
  await user2Page.goto(BASE_URL, { waitUntil: "networkidle" });
  await user2Page.waitForTimeout(2000);

  const user2Email = user2Page.locator('input[type="email"]').first();
  await user2Email.fill("demo@example.com");

  const user2Pass = user2Page.locator('input[type="password"]').first();
  await user2Pass.fill("DemoPassword123!");

  await user2Page.click('button:has-text("Sign in")');
  await user2Page.waitForURL("**/world", { timeout: 30000 });
  console.log("✅ USER 2: Logged in and ready\n");

  // ========== COLLECT LOGS ==========
  const user1Logs = [];
  const user2Logs = [];

  user1Page.on("console", (msg) => {
    const text = msg.text();
    user1Logs.push(text);
    if (text.includes("[live]")) {
      console.log(`📍 USER 1: ${text}`);
    }
  });

  user2Page.on("console", (msg) => {
    const text = msg.text();
    user2Logs.push(text);
    if (text.includes("[live]")) {
      console.log(`📍 USER 2: ${text}`);
    }
  });

  console.log("═══════════════════════════════════════════════════════════");
  console.log("🎤 INSTRUCTIONS:");
  console.log("═══════════════════════════════════════════════════════════");
  console.log("1. Both browsers are open and logged in");
  console.log("2. Navigate USER 2 to the SAME land as USER 1");
  console.log('3. In USER 1: Click "Go Live (Audio)" and allow microphone');
  console.log("4. Talk into USER 1 microphone");
  console.log("5. Check if USER 2 receives audio");
  console.log("═══════════════════════════════════════════════════════════\n");

  // Keep browsers open for 5 minutes
  await user1Page.waitForTimeout(300000);

  console.log("\n✅ TEST COMPLETE - Check console logs above\n");
});
