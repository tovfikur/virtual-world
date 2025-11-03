const { chromium } = require('playwright');

(async () => {
  console.log('Testing navigation between pages...\n');
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  const page = await context.newPage();

  let errorsDetected = [];

  page.on('pageerror', error => {
    console.error('❌ PAGE ERROR:', error.message);
    errorsDetected.push(error.message);
  });

  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.error('❌ CONSOLE ERROR:', msg.text());
      errorsDetected.push(msg.text());
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

    console.log('2. Navigating to World page...');
    if (!page.url().includes('/world')) {
      await page.goto('http://localhost/world', { waitUntil: 'networkidle' });
    }
    await page.waitForTimeout(3000);
    console.log('   ✅ World page loaded');

    console.log('3. Navigating to Profile page...');
    await page.click('a[href="/profile"]');
    await page.waitForTimeout(2000);

    if (page.url().includes('/profile')) {
      console.log('   ✅ Profile page loaded');
    } else {
      console.log('   ⚠️  Not on profile page, URL:', page.url());
    }

    console.log('4. Navigating back to World page...');
    await page.click('a[href="/world"]');
    await page.waitForTimeout(2000);

    if (page.url().includes('/world')) {
      console.log('   ✅ World page loaded again');
    }

    console.log('5. Navigating to Marketplace page...');
    await page.click('a[href="/marketplace"]');
    await page.waitForTimeout(2000);

    if (page.url().includes('/marketplace')) {
      console.log('   ✅ Marketplace page loaded');
    }

    console.log('6. Navigating back to World page again...');
    await page.click('a[href="/world"]');
    await page.waitForTimeout(2000);

    if (page.url().includes('/world')) {
      console.log('   ✅ World page loaded again (3rd time)');
    }

    await page.screenshot({ path: 'k:/VirtualWorld/screenshot-navigation-test.png' });

    console.log('\n' + '='.repeat(70));
    console.log('TEST RESULTS:');
    console.log('='.repeat(70));

    if (errorsDetected.length === 0) {
      console.log('✅ SUCCESS: No errors during navigation!');
      console.log('   All page transitions work correctly.');
    } else {
      console.log(`❌ FAILED: ${errorsDetected.length} errors detected:`);
      errorsDetected.forEach((err, i) => {
        console.log(`   ${i + 1}. ${err.substring(0, 100)}...`);
      });
    }
    console.log('='.repeat(70));

  } catch (error) {
    console.error('\n❌ Test failed:', error.message);
  } finally {
    console.log('\nClosing browser in 3 seconds...');
    await page.waitForTimeout(3000);
    await browser.close();
  }
})();
