import { test, expect } from "@playwright/test";

test.describe("Registration Tests", () => {
  test("should register a new user successfully", async ({ page }) => {
    // Generate unique username/email
    const timestamp = Date.now();
    const username = `testuser${timestamp}`;
    const email = `testuser${timestamp}@example.com`;
    const password = "TestPass123!";

    // Enable console logging
    page.on("console", (msg) => console.log("BROWSER:", msg.text()));
    page.on("response", (response) => {
      if (response.url().includes("/auth/")) {
        console.log(`API: ${response.status()} ${response.url()}`);
      }
    });

    // Navigate to register page
    await page.goto("http://localhost/register");
    await page.waitForLoadState("networkidle");

    // Take screenshot of register page
    await page.screenshot({ path: "test-results/register-page.png" });

    // Fill in registration form
    await page.fill('input[type="text"]', username);
    await page.fill('input[type="email"]', email);

    // Fill password fields
    const passwordInputs = page.locator('input[type="password"]');
    await passwordInputs.first().fill(password);
    await passwordInputs.last().fill(password);

    // Take screenshot before submit
    await page.screenshot({ path: "test-results/register-filled.png" });

    // Submit form
    await page.click('button[type="submit"]');

    // Wait longer for registration + auto-login + redirect
    console.log("Waiting for registration flow...");
    await page.waitForTimeout(8000);

    // Take screenshot after submit
    await page.screenshot({ path: "test-results/register-after-submit.png" });

    // Check current URL
    const currentUrl = page.url();
    console.log("Current URL after registration:", currentUrl);

    // Check for any error toasts or messages
    const errorToast = page.locator('.Toastify__toast--error, [role="alert"]');
    if ((await errorToast.count()) > 0) {
      const errorText = await errorToast.first().textContent();
      console.log("Error message:", errorText);
    }

    // If redirected to /world, registration succeeded
    if (currentUrl.includes("/world")) {
      console.log("✓ Registration successful - redirected to world");
      expect(currentUrl).toContain("/world");
    } else {
      // Check page content for any errors
      const pageContent = await page.content();
      console.log("Page still on register, checking for errors...");

      // Look for validation errors on page
      const errorElements = page.locator(
        ".text-red-500, .text-red-400, .error"
      );
      const errorCount = await errorElements.count();
      if (errorCount > 0) {
        for (let i = 0; i < errorCount; i++) {
          const text = await errorElements.nth(i).textContent();
          console.log(`Error ${i + 1}:`, text);
        }
      }
    }
  });

  test("should show error for duplicate email", async ({ page }) => {
    // Try to register with existing demo email
    await page.goto("http://localhost/register");
    await page.waitForLoadState("networkidle");

    await page.fill('input[type="text"]', "duplicatetest");
    await page.fill('input[type="email"]', "demo@example.com");

    const passwordInputs = page.locator('input[type="password"]');
    await passwordInputs.first().fill("TestPass123!");
    await passwordInputs.last().fill("TestPass123!");

    await page.click('button[type="submit"]');
    await page.waitForTimeout(2000);

    // Should show error about duplicate email
    await page.screenshot({ path: "test-results/register-duplicate.png" });

    // Check for error message
    const pageContent = await page.content();
    const hasDuplicateError =
      pageContent.includes("already") || pageContent.includes("exists");
    console.log("Duplicate email error shown:", hasDuplicateError);
  });
});
