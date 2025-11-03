const { chromium } = require('playwright');

(async () => {
  console.log('Testing aggressive chunk culling...\n');
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  const page = await context.newPage();

  let hiddenChunksDetected = false;

  page.on('console', msg => {
    const text = msg.text();
    if (text.includes('Chunks -')) {
      console.log('📊', text);
      if (text.includes('Hidden:') && !text.includes('Hidden: 0')) {
        hiddenChunksDetected = true;
      }
    }
  });

  try {
    console.log('1. Setting up...');
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

    console.log('\n2. Initial load...');
    await page.waitForTimeout(4000);
    await page.screenshot({ path: 'k:/VirtualWorld/screenshot-cull-1-initial.png' });

    const canvas = await page.$('canvas');

    console.log('\n3. AGGRESSIVE PAN RIGHT (should hide left chunks)...');
    for (let i = 0; i < 5; i++) {
      await canvas.hover();
      await page.mouse.down();
      await page.mouse.move(200, 540);
      await page.mouse.move(1720, 540, { steps: 30 });
      await page.mouse.up();
      await page.waitForTimeout(500);
    }
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'k:/VirtualWorld/screenshot-cull-2-panned-right.png' });

    console.log('\n4. AGGRESSIVE PAN LEFT (should hide right chunks)...');
    for (let i = 0; i < 5; i++) {
      await page.mouse.down();
      await page.mouse.move(1720, 540);
      await page.mouse.move(200, 540, { steps: 30 });
      await page.mouse.up();
      await page.waitForTimeout(500);
    }
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'k:/VirtualWorld/screenshot-cull-3-panned-left.png' });

    console.log('\n5. ZOOM OUT and PAN...');
    // Zoom out
    await canvas.hover();
    for (let i = 0; i < 5; i++) {
      await page.mouse.wheel(0, -100);
      await page.waitForTimeout(200);
    }

    await page.waitForTimeout(2000);

    // Now pan while zoomed out
    await page.mouse.down();
    await page.mouse.move(960, 540);
    await page.mouse.move(200, 200, { steps: 40 });
    await page.mouse.up();

    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'k:/VirtualWorld/screenshot-cull-4-zoomed-panned.png' });

    console.log('\n' + '='.repeat(60));
    if (hiddenChunksDetected) {
      console.log('✅ SUCCESS: Hidden chunks detected!');
      console.log('   Chunk visibility culling is working correctly.');
    } else {
      console.log('⚠️  WARNING: No hidden chunks detected');
      console.log('   Chunks may all still be in view, or culling needs adjustment.');
    }
    console.log('='.repeat(60));

  } catch (error) {
    console.error('\n❌ Test failed:', error.message);
  } finally {
    console.log('\nClosing browser in 3 seconds...');
    await page.waitForTimeout(3000);
    await browser.close();
  }
})();
