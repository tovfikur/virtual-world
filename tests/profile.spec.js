// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('Profile Page Tests', () => {
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
      }
    });

    page.on('pageerror', error => {
      consoleErrors.push(error.message);
      console.log(`[PAGE ERROR] ${error.message}`);
    });

    page.on('requestfailed', request => {
      console.log(`[REQUEST FAILED] ${request.url()}: ${request.failure().errorText}`);
    });

    // Login first
    await page.goto('http://localhost/login');
    await page.fill('input[type="email"]', 'demo@example.com');
    await page.fill('input[type="password"]', 'DemoPassword123!');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/world', { timeout: 15000 });
  });

  test('Profile page loads and displays user info', async ({ page }) => {
    console.log('\n🧪 Testing profile page...\n');

    // Navigate to profile
    await page.goto('http://localhost/profile');
    await page.waitForTimeout(2000);

    // Take screenshot
    await page.screenshot({
      path: 'profile-page.png',
      fullPage: true
    });

    console.log('✅ Profile page screenshot saved\n');
    console.log(`📊 Errors: ${consoleErrors.length}, Warnings: ${consoleWarnings.length}\n`);

    if (consoleErrors.length > 0) {
      console.log('❌ Console Errors on Profile Page:');
      consoleErrors.forEach(err => console.log(`   - ${err}`));
    }

    // Check for user info display
    const pageContent = await page.content();
    const hasUsername = pageContent.includes('demo') || await page.locator('text=demo').count() > 0;

    console.log(`Username displayed: ${hasUsername ? '✅' : '❌'}`);

    // Check current URL
    console.log(`Current URL: ${page.url()}\n`);
  });
});
