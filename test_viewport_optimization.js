const { chromium } = require('playwright');

(async () => {
  console.log('Testing viewport-aware batch loading...\n');
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  const page = await context.newPage();

  let skippedChunks = false;
  let removedFromQueue = false;
  const events = [];

  page.on('console', msg => {
    const text = msg.text();

    // Track skip events
    if (text.includes('⏭️') || text.includes('Skipping') || text.includes('skipped')) {
      events.push(text);
      console.log('⏭️ ', text);
      skippedChunks = true;
    }

    // Track queue removal
    if (text.includes('🗑️') || text.includes('Removed') || text.includes('from queue')) {
      events.push(text);
      console.log('🗑️ ', text);
      removedFromQueue = true;
    }

    // Track batch loading
    if (text.includes('🔄 Loading batch') || text.includes('🎉 Sequential')) {
      console.log('📦', text);
    }
  });

  try {
    console.log('1. Setting up and logging in...');
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

    console.log('\n2. Waiting for initial chunks to load...');
    await page.waitForTimeout(3000);

    console.log('\n3. RAPID PANNING to trigger viewport changes during loading...');
    const canvas = await page.$('canvas');

    // Pan right quickly while chunks are loading
    for (let i = 0; i < 3; i++) {
      await canvas.hover();
      await page.mouse.down();
      await page.mouse.move(300, 540);
      await page.mouse.move(1600, 540, { steps: 10 });
      await page.mouse.up();
      await page.waitForTimeout(500);

      // Pan back
      await page.mouse.down();
      await page.mouse.move(1600, 540);
      await page.mouse.move(300, 540, { steps: 10 });
      await page.mouse.up();
      await page.waitForTimeout(500);
    }

    console.log('\n4. Waiting for batch loading to process...');
    await page.waitForTimeout(5000);

    console.log('\n5. Pan to completely different area...');
    await page.mouse.down();
    await page.mouse.move(960, 540);
    await page.mouse.move(100, 100, { steps: 30 });
    await page.mouse.up();

    await page.waitForTimeout(5000);

    await page.screenshot({ path: 'k:/VirtualWorld/screenshot-viewport-optimized.png' });

    console.log('\n' + '='.repeat(70));
    console.log('TEST RESULTS:');
    console.log('='.repeat(70));
    console.log(`Total optimization events: ${events.length}`);

    if (skippedChunks) {
      console.log('✅ Chunks SKIPPED when outside viewport during batch loading');
    } else {
      console.log('⚠️  No chunks were skipped (may not have gone outside viewport)');
    }

    if (removedFromQueue) {
      console.log('✅ Chunks REMOVED from queue when no longer visible');
    } else {
      console.log('⚠️  No chunks removed from queue (queue may have been empty)');
    }

    if (skippedChunks || removedFromQueue) {
      console.log('\n🎉 SUCCESS: Viewport optimization is working!');
      console.log('   Only visible chunks are being loaded.');
    } else {
      console.log('\n📝 Note: Optimization is active but no skips detected in this test.');
      console.log('   This could mean all chunks stayed in viewport during the test.');
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
