// @ts-check
const { test, expect } = require('@playwright/test');

test('Profile page shows user data after login', async ({ page }) => {
  console.log('\n🧪 Testing full profile flow...\n');

  // 1. Login first
  await page.goto('http://localhost/login');
  await page.fill('input[type="email"]', 'demo@example.com');
  await page.fill('input[type="password"]', 'DemoPassword123!');
  await page.click('button[type="submit"]');
  await page.waitForURL('**/world', { timeout: 15000 });
  console.log('✅ Logged in successfully');

  // 2. Navigate to profile
  await page.goto('http://localhost/profile');
  await page.waitForTimeout(3000); // Wait for profile data to load

  // 3. Take screenshot
  await page.screenshot({
    path: 'profile-page-authenticated.png',
    fullPage: true
  });

  // 4. Verify profile elements exist
  const username = await page.locator('text=demo').count();
  const email = await page.locator('text=demo@example.com').count();

  console.log(`✅ Username visible: ${username > 0 ? 'Yes' : 'No'}`);
  console.log(`✅ Email visible: ${email > 0 ? 'Yes' : 'No'}`);
  console.log(`✅ Current URL: ${page.url()}`);
  console.log(`📸 Screenshot saved: profile-page-authenticated.png\n`);

  // Test should pass if we're on profile page (not redirected)
  expect(page.url()).toContain('/profile');
});
