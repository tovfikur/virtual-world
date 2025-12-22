import { test } from "@playwright/test";

test("Audio Test with Full Debugging", async ({ browser }) => {
  const user1Context = await browser.newContext({
    permissions: ["microphone", "camera"],
  });
  const user2Context = await browser.newContext({
    permissions: ["microphone", "camera"],
  });

  const user1Page = await user1Context.newPage();
  const user2Page = await user2Context.newPage();

  const BASE_URL = "http://localhost";

  console.log("\n🚀 AUDIO TEST WITH FULL DEBUGGING\n");

  // ========== USER 1: LOGIN ==========
  console.log("👤 USER 1: Logging in...");
  await user1Context.grantPermissions(["microphone", "camera"]);
  await user1Page.goto(BASE_URL, { waitUntil: "networkidle" });
  await user1Page.waitForTimeout(2000);

  await user1Page.fill('input[type="email"]', "topubiswas1234@gmail.com");
  await user1Page.fill('input[type="password"]', "topubiswas1234@gmail.com");
  await user1Page.click('button:has-text("Sign in")');
  await user1Page.waitForURL("**/world", { timeout: 30000 });
  console.log("✅ USER 1: Logged in\n");

  // ========== USER 2: LOGIN ==========
  console.log("👤 USER 2: Logging in...");
  await user2Context.grantPermissions(["microphone", "camera"]);
  await user2Page.goto(BASE_URL, { waitUntil: "networkidle" });
  await user2Page.waitForTimeout(2000);

  await user2Page.fill('input[type="email"]', "demo@example.com");
  await user2Page.fill('input[type="password"]', "DemoPassword123!");
  await user2Page.click('button:has-text("Sign in")');
  await user2Page.waitForURL("**/world", { timeout: 30000 });
  console.log("✅ USER 2: Logged in\n");

  // ========== COLLECT ALL LOGS ==========
  const user1AllLogs = [];
  const user2AllLogs = [];

  user1Page.on("console", (msg) => {
    const text = msg.text();
    user1AllLogs.push(text);
    if (
      text.includes("[live]") ||
      text.includes("error") ||
      text.includes("Error")
    ) {
      console.log(`📍 USER 1: ${text}`);
    }
  });

  user2Page.on("console", (msg) => {
    const text = msg.text();
    user2AllLogs.push(text);
    if (
      text.includes("[live]") ||
      text.includes("error") ||
      text.includes("Error")
    ) {
      console.log(`📍 USER 2: ${text}`);
    }
  });

  console.log("═══════════════════════════════════════════════════════════");
  console.log("📋 LOG LISTENERS ACTIVE - Ready to capture console messages");
  console.log("═══════════════════════════════════════════════════════════\n");

  // Wait 90 seconds
  console.log("⏳ Waiting 90 seconds for your manual test...\n");

  // Check results every 10 seconds and print them
  for (let i = 0; i < 9; i++) {
    await user1Page.waitForTimeout(10000);
    const user1LiveLogs = user1AllLogs.filter((l) => l.includes("[live]"));
    const user2LiveLogs = user2AllLogs.filter((l) => l.includes("[live]"));
    console.log(
      `[${(i + 1) * 10}s] USER 1: ${
        user1LiveLogs.length
      } [live] logs | USER 2: ${user2LiveLogs.length} [live] logs`
    );
  }

  console.log("\n═══════════════════════════════════════════════════════════");
  console.log("📊 FINAL RESULTS");
  console.log("═══════════════════════════════════════════════════════════");

  const user1LiveLogs = user1AllLogs.filter((l) => l.includes("[live]"));
  const user2LiveLogs = user2AllLogs.filter((l) => l.includes("[live]"));

  console.log(`\nUSER 1 [live] logs: ${user1LiveLogs.length}`);
  if (user1LiveLogs.length > 0) {
    user1LiveLogs.forEach((log) => console.log(`  - ${log}`));
  } else {
    console.log(
      "  ⚠️ NO [live] LOGS FOUND - startLive may not have been called"
    );
  }

  console.log(`\nUSER 2 [live] logs: ${user2LiveLogs.length}`);
  if (user2LiveLogs.length > 0) {
    user2LiveLogs.forEach((log) => console.log(`  - ${log}`));
  } else {
    console.log("  ⚠️ NO [live] LOGS FOUND - may not be receiving stream");
  }

  console.log(
    "\n═══════════════════════════════════════════════════════════\n"
  );
});
