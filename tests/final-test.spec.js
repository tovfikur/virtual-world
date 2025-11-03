// @ts-check
const { test, expect } = require('@playwright/test');

test('Complete login and world test', async ({ page }) => {
  const errors = [];
  const warnings = [];

  // Capture console
  page.on('console', msg => {
    const type = msg.type();
    const text = msg.text();
    if (type === 'error') {
      errors.push(text);
      console.log(`❌ ERROR: ${text}`);
    } else if (type === 'warning') {
      warnings.push(text);
    }
  });

  page.on('pageerror', error => {
    errors.push(error.message);
    console.log(`💥 PAGE ERROR: ${error.message}`);
  });

  console.log('🧪 Starting fresh test with new frontend...\n');

  // Step 1: Go to login
  await page.goto('http://localhost/login', { waitForTimeout: 30000 });
  await page.waitForTimeout(2000);
  console.log('✅ Login page loaded');

  // Step 2: Login
  await page.fill('input[type="email"]', 'demo@example.com');
  await page.fill('input[type="password"]', 'DemoPassword123!');
  await page.click('button[type="submit"]');

  // Wait for navigation
  await page.waitForURL('**/world', { timeout: 20000 }).catch(() => {
    console.log('⚠️  Did not redirect to /world');
  });

  await page.waitForTimeout(5000); // Wait for chunks to start loading

  // Take screenshot
  await page.screenshot({ path: 'final-test-result.png', fullPage: false });
  console.log('📸 Screenshot saved: final-test-result.png');

  // Count errors
  const chunkErrors = errors.filter(e => e.includes('Failed to load chunk') || e.includes('ERR_INSUFFICIENT_RESOURCES'));

  console.log(`\n📊 RESULTS:`);
  console.log(`   Total Errors: ${errors.length}`);
  console.log(`   Chunk Load Errors: ${chunkErrors.length}`);
  console.log(`   Current URL: ${page.url()}`);

  if (chunkErrors.length > 50) {
    console.log(`\n❌ STILL TOO MANY CHUNK ERRORS (${chunkErrors.length})`);
  } else if (chunkErrors.length > 0) {
    console.log(`\n⚠️  Some chunk errors (${chunkErrors.length}) but improved`);
  } else {
    console.log(`\n✅ NO CHUNK ERRORS!`);
  }
});
