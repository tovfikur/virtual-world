const { chromium } = require('playwright');

(async () => {
  console.log('Testing for WorldRenderer cleanup error...\n');
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  const page = await context.newPage();

  let cleanupErrorDetected = false;
  let stageNullError = false;

  page.on('pageerror', error => {
    const msg = error.message;
    console.log('Page Error:', msg.substring(0, 100));

    if (msg.includes("can't access property \"off\"") && msg.includes('stage')) {
      cleanupErrorDetected = true;
      stageNullError = true;
      console.error('❌ CLEANUP ERROR DETECTED:', msg);
    }
  });

  page.on('console', msg => {
    if (msg.type() === 'error') {
      const text = msg.text();
      if (text.includes("can't access property \"off\"") && text.includes('stage')) {
        cleanupErrorDetected = true;
        stageNullError = true;
        console.error('❌ CLEANUP ERROR DETECTED:', text);
      }
    }
  });

  try {
    console.log('1. Logging in...');
    await page.goto('http://localhost', { waitUntil: 'networkidle' });

    const timestamp = Date.now();
    const registerLink = await page.$('a[href="/register"]');
    if (registerLink) {
      await registerLink.click();
      await page.waitForTimeout(500);

      await page.fill('input[type="text"]', `testuser${timestamp}`);
      await page.fill('input[type="email"]', `test${timestamp}@example.com`);
      const passwordInputs = await page.$$('input[type="password"]');
      if (passwordInputs.length > 0) await passwordInputs[0].fill('TestPass123!');
      if (passwordInputs.length > 1) await passwordInputs[1].fill('TestPass123!');

      await page.click('button[type="submit"]');
      await page.waitForTimeout(2000);
    }

    console.log('2. Going to World page...');
    if (!page.url().includes('/world')) {
      await page.goto('http://localhost/world', { waitUntil: 'networkidle' });
    }
    await page.waitForTimeout(3000);
    console.log('   ✅ World page loaded');

    console.log('3. Navigating AWAY from World page to Profile...');
    console.log('   (This should trigger WorldRenderer cleanup)');
    await page.click('a[href="/profile"]');
    await page.waitForTimeout(3000);

    console.log('   ✅ Profile page loaded');

    await page.screenshot({ path: 'k:/VirtualWorld/screenshot-cleanup-test.png' });

    console.log('\n' + '='.repeat(70));
    console.log('TEST RESULTS:');
    console.log('='.repeat(70));

    if (stageNullError) {
      console.log('❌ FAILED: WorldRenderer cleanup error still exists!');
      console.log('   Error: "can\'t access property \'off\', stage is null"');
    } else if (cleanupErrorDetected) {
      console.log('⚠️  WARNING: Cleanup error detected (but not stage null)');
    } else {
      console.log('✅ SUCCESS: No cleanup errors detected!');
      console.log('   WorldRenderer cleanup is working correctly.');
    }

    console.log('='.repeat(70));

  } catch (error) {
    console.error('\n❌ Test execution failed:', error.message);
  } finally {
    console.log('\nClosing browser in 3 seconds...');
    await page.waitForTimeout(3000);
    await browser.close();
  }
})();
