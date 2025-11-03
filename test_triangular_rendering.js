const { chromium } = require('playwright');

(async () => {
  console.log('Testing triangular land rendering...\n');
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  const page = await context.newPage();

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

    if (!page.url().includes('/world')) {
      await page.goto('http://localhost/world', { waitUntil: 'networkidle' });
    }

    console.log('2. Waiting for triangular world to render...');
    await page.waitForTimeout(5000);

    console.log('3. Taking screenshots...');
    await page.screenshot({ path: 'k:/VirtualWorld/screenshot-triangular-1.png' });

    // Zoom in to see triangle details
    const canvas = await page.$('canvas');
    await canvas.hover();
    for (let i = 0; i < 3; i++) {
      await page.mouse.wheel(0, -100);
      await page.waitForTimeout(300);
    }

    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'k:/VirtualWorld/screenshot-triangular-zoomed.png' });

    console.log('4. Panning to see more of the triangular world...');
    await page.mouse.down();
    await page.mouse.move(960, 540);
    await page.mouse.move(600, 300, { steps: 20 });
    await page.mouse.up();

    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'k:/VirtualWorld/screenshot-triangular-panned.png' });

    console.log('\n✅ Screenshots saved:');
    console.log('   - screenshot-triangular-1.png (initial view)');
    console.log('   - screenshot-triangular-zoomed.png (zoomed in)');
    console.log('   - screenshot-triangular-panned.png (panned view)');
    console.log('\nCheck the screenshots to see the triangular rendering!');

  } catch (error) {
    console.error('\n❌ Test failed:', error.message);
  } finally {
    console.log('\nClosing browser in 5 seconds...');
    await page.waitForTimeout(5000);
    await browser.close();
  }
})();
