import { test, expect } from "@playwright/test";

test("debug registration flow", async ({ page }) => {
  const timestamp = Date.now();
  const username = `debuguser${timestamp}`;
  const email = `debuguser${timestamp}@example.com`;
  const password = "TestPass123!";

  // Listen to all network requests
  const requests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/")) {
      requests.push(`${request.method()} ${request.url()}`);
    }
  });

  const responses: string[] = [];
  page.on("response", (response) => {
    if (response.url().includes("/api/")) {
      responses.push(`${response.status()} ${response.url()}`);
    }
  });

  // Listen to console
  const consoleLogs: string[] = [];
  page.on("console", (msg) => {
    consoleLogs.push(`[${msg.type()}] ${msg.text()}`);
  });

  // Navigate to register page
  await page.goto("http://localhost/register");
  await page.waitForLoadState("networkidle");

  // Fill form
  await page.fill('input[type="text"]', username);
  await page.fill('input[type="email"]', email);

  const passwordInputs = page.locator('input[type="password"]');
  await passwordInputs.first().fill(password);
  await passwordInputs.last().fill(password);

  console.log("Form filled, submitting...");

  // Submit
  await page.click('button[type="submit"]');

  // Wait for up to 30 seconds for navigation or response
  try {
    await page.waitForURL("**/world", { timeout: 30000 });
    console.log("✓ Redirected to /world successfully");
  } catch (e) {
    console.log("✗ Did not redirect to /world");
    console.log("Current URL:", page.url());
  }

  // Wait a bit more for any pending requests
  await page.waitForTimeout(2000);

  // Print all captured info
  console.log("\n=== REQUESTS ===");
  requests.forEach((r) => console.log(r));

  console.log("\n=== RESPONSES ===");
  responses.forEach((r) => console.log(r));

  console.log("\n=== CONSOLE LOGS ===");
  consoleLogs.forEach((l) => console.log(l));

  // Take final screenshot
  await page.screenshot({
    path: "test-results/debug-register-final.png",
    fullPage: true,
  });

  // Check for visible errors on page
  const errorText = await page
    .locator('.text-red-500, .text-red-400, [class*="error"]')
    .allTextContents();
  if (errorText.length > 0) {
    console.log("\n=== VISIBLE ERRORS ===");
    errorText.forEach((e) => console.log(e));
  }

  // Check toast notifications
  const toasts = await page
    .locator('.Toastify__toast, [role="alert"]')
    .allTextContents();
  if (toasts.length > 0) {
    console.log("\n=== TOAST MESSAGES ===");
    toasts.forEach((t) => console.log(t));
  }
});
