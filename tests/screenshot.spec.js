// @ts-check
const { test } = require('@playwright/test');

test('Capture working world page screenshot', async ({ page }) => {
  console.log('\n📸 Capturing world page screenshot...\n');

  // Login
  await page.goto('http://localhost/login');
  await page.fill('input[type="email"]', 'demo@example.com');
  await page.fill('input[type="password"]', 'DemoPassword123!');
  await page.click('button[type="submit"]');

  // Wait for world page
  await page.waitForURL('**/world', { timeout: 15000 });
  await page.waitForTimeout(5000); // Wait for chunks to load

  // Take screenshot
  await page.screenshot({
    path: 'world-page-working.png',
    fullPage: false
  });

  console.log('✅ Screenshot saved to: world-page-working.png\n');
});
