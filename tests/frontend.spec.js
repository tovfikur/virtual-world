// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('VirtualWorld Frontend Tests', () => {
  let consoleErrors = [];
  let consoleWarnings = [];

  test.beforeEach(async ({ page }) => {
    // Capture console messages
    consoleErrors = [];
    consoleWarnings = [];

    page.on('console', msg => {
      const type = msg.type();
      const text = msg.text();

      if (type === 'error') {
        consoleErrors.push(text);
        console.log(`[BROWSER ERROR] ${text}`);
      } else if (type === 'warning') {
        consoleWarnings.push(text);
        console.log(`[BROWSER WARNING] ${text}`);
      }
    });

    page.on('pageerror', error => {
      consoleErrors.push(error.message);
      console.log(`[PAGE ERROR] ${error.message}`);
    });

    page.on('requestfailed', request => {
      console.log(`[REQUEST FAILED] ${request.url()}: ${request.failure().errorText}`);
    });
  });

  test('Login page loads without errors', async ({ page }) => {
    console.log('\n🧪 Testing login page load...\n');

    await page.goto('http://localhost/login', {
      waitUntil: 'networkidle',
      timeout: 30000
    });

    // Check page title
    await expect(page).toHaveTitle(/Virtual Land World/i);

    // Check form elements exist
    const emailInput = page.locator('input[type="email"]');
    const passwordInput = page.locator('input[type="password"]');
    const submitButton = page.locator('button[type="submit"]');

    await expect(emailInput).toBeVisible();
    await expect(passwordInput).toBeVisible();
    await expect(submitButton).toBeVisible();

    console.log(`\n✅ Login page loaded successfully`);
    console.log(`📊 Errors: ${consoleErrors.length}, Warnings: ${consoleWarnings.length}\n`);

    if (consoleErrors.length > 0) {
      console.log('❌ Console Errors Found:');
      consoleErrors.forEach(err => console.log(`   - ${err}`));
    }

    // Fail test if there are errors
    expect(consoleErrors.length, 'Should have no console errors').toBe(0);
  });

  test('Login with demo credentials', async ({ page }) => {
    console.log('\n🧪 Testing login functionality...\n');

    await page.goto('http://localhost/login', {
      waitUntil: 'networkidle',
      timeout: 30000
    });

    // Fill in login form
    await page.fill('input[type="email"]', 'demo@example.com');
    await page.fill('input[type="password"]', 'DemoPassword123!');

    // Click submit and wait for navigation
    await Promise.all([
      page.waitForURL('**/world', { timeout: 15000 }),
      page.click('button[type="submit"]')
    ]);

    // Should redirect to /world
    expect(page.url()).toContain('/world');
    console.log('✅ Login successful - redirected to /world\n');

    // Wait a bit for any errors
    await page.waitForTimeout(2000);

    console.log(`📊 Errors: ${consoleErrors.length}, Warnings: ${consoleWarnings.length}\n`);

    if (consoleErrors.length > 0) {
      console.log('❌ Console Errors After Login:');
      consoleErrors.slice(0, 10).forEach(err => console.log(`   - ${err}`));
    }
  });

  test('World page loads and renders canvas', async ({ page }) => {
    console.log('\n🧪 Testing world page...\n');

    // Login first
    await page.goto('http://localhost/login');
    await page.fill('input[type="email"]', 'demo@example.com');
    await page.fill('input[type="password"]', 'DemoPassword123!');
    await Promise.all([
      page.waitForURL('**/world', { timeout: 15000 }),
      page.click('button[type="submit"]')
    ]);

    // Wait for canvas to load
    await page.waitForTimeout(3000);

    // Check if canvas exists (PixiJS renders to canvas)
    const canvas = page.locator('canvas');
    await expect(canvas).toBeVisible({ timeout: 10000 });

    console.log('✅ World canvas rendered\n');
    console.log(`📊 Total Errors: ${consoleErrors.length}, Warnings: ${consoleWarnings.length}\n`);

    if (consoleErrors.length > 0) {
      console.log('❌ Console Errors on World Page:');
      consoleErrors.slice(0, 15).forEach(err => console.log(`   - ${err}`));
      if (consoleErrors.length > 15) {
        console.log(`   ... and ${consoleErrors.length - 15} more errors`);
      }
    }

    // Log summary
    console.log('\n📋 Test Summary:');
    console.log(`   Total console errors: ${consoleErrors.length}`);
    console.log(`   Total warnings: ${consoleWarnings.length}`);
  });
});
