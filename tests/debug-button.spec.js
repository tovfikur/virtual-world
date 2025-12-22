import { test } from "@playwright/test";

test("Debug: Check if Go Live Button is Clickable", async ({ browser }) => {
  const context = await browser.newContext({
    permissions: ["microphone", "camera"],
  });
  const page = await context.newPage();

  const BASE_URL = "http://localhost";

  console.log("\n🔍 DEBUG: Checking Go Live Button\n");

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

  // Check if ChatBox is visible
  const chatBox = page.locator('div:has(button:has-text("Go Live (Audio)"))');
  const isVisible = await chatBox.isVisible().catch(() => false);
  console.log(`📍 ChatBox visible: ${isVisible}`);

  // Look for the button
  const goLiveBtn = page.locator('button:has-text("Go Live (Audio)")').first();

  try {
    await goLiveBtn.waitFor({ state: "visible", timeout: 5000 });
    console.log("✅ Go Live button found and visible");

    // Check button attributes
    const isDisabled = await goLiveBtn.evaluate((el) => el.disabled);
    const isDisplayed = await goLiveBtn.isVisible();
    const text = await goLiveBtn.textContent();

    console.log(`  - Text: "${text}"`);
    console.log(`  - Visible: ${isDisplayed}`);
    console.log(`  - Disabled: ${isDisabled}`);
    console.log(`  - Position: ${await goLiveBtn.boundingBox()}`);

    // Try clicking it
    console.log(`\n🖱️ Attempting to click Go Live button...`);
    await goLiveBtn.click();
    console.log("✅ Click executed");

    // Wait for anything to happen
    await page.waitForTimeout(3000);

    // Check if permission prompt appeared
    const permissionPrompt = page.locator("text=microphone").first();
    const hasPrompt = await permissionPrompt.isVisible().catch(() => false);
    console.log(`\n📍 Permission prompt visible: ${hasPrompt}`);

    // Get all console messages
    const allLogs = [];
    page.on("console", (msg) => {
      allLogs.push(msg.text());
    });

    // Wait a bit more
    await page.waitForTimeout(2000);

    const liveLogs = allLogs.filter((l) => l.includes("[live]"));
    console.log(`\n📋 Console logs:`);
    console.log(`  - Total: ${allLogs.length}`);
    console.log(`  - [live] logs: ${liveLogs.length}`);

    if (liveLogs.length > 0) {
      console.log(`\n[live] Messages found:`);
      liveLogs.forEach((log) => console.log(`  - ${log}`));
    } else {
      console.log(
        `\n❌ NO [live] LOGS - button click did not trigger startLive`
      );
      console.log(`\nFirst 20 console messages:`);
      allLogs.slice(0, 20).forEach((log, i) => {
        console.log(`  [${i}] ${log}`);
      });
    }
  } catch (error) {
    console.log(`❌ Go Live button not found or error: ${error.message}`);
  }

  await page.waitForTimeout(3000);
});
