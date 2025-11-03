const { chromium } = require('playwright');

(async () => {
  console.log('Testing sequential batch loading...\n');
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  const page = await context.newPage();

  const batchEvents = [];
  const loadingPattern = [];

  page.on('console', msg => {
    const text = msg.text();

    // Track batch loading events
    if (text.includes('📦 Sequential loading') ||
        text.includes('🔄 Loading batch') ||
        text.includes('✅ Batch') ||
        text.includes('🎉 Sequential loading complete')) {
      batchEvents.push(text);
      console.log('📋', text);
    }

    // Track loading pattern
    if (text.includes('🔄 Loading batch')) {
      const match = text.match(/batch (\d+)\/(\d+)/);
      if (match) {
        loadingPattern.push({ batch: parseInt(match[1]), total: parseInt(match[2]) });
      }
    }
  });

  try {
    console.log('1. Navigating to application...');
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

    console.log('\n2. Initial chunk loading (should be sequential)...');
    await page.waitForTimeout(10000); // Wait for chunks to load sequentially

    console.log('\n3. Panning to trigger more chunk loading...');
    const canvas = await page.$('canvas');
    await canvas.hover();
    await page.mouse.down();
    await page.mouse.move(500, 540);
    await page.mouse.move(1420, 540, { steps: 20 });
    await page.mouse.up();

    await page.waitForTimeout(8000); // Wait for sequential loading

    console.log('\n' + '='.repeat(70));
    console.log('TEST RESULTS:');
    console.log('='.repeat(70));
    console.log(`Total batch events: ${batchEvents.length}`);

    if (loadingPattern.length > 0) {
      console.log('\n✅ Sequential Loading Pattern Detected:');

      // Check if batches loaded sequentially (batch 1, then 2, then 3, etc.)
      const isSequential = loadingPattern.every((event, index) => {
        if (index === 0) return event.batch === 1;
        return event.batch === loadingPattern[index - 1].batch ||
               event.batch === loadingPattern[index - 1].batch + 1;
      });

      if (isSequential) {
        console.log('   ✅ Batches loaded in correct sequential order');
      } else {
        console.log('   ⚠️  Batches may not be loading sequentially');
      }

      console.log(`   📊 Number of batches: ${Math.max(...loadingPattern.map(p => p.batch))}`);
      console.log(`   📦 Loading events: ${loadingPattern.length}`);
    } else {
      console.log('⚠️  No sequential loading pattern detected');
      console.log('   This might mean chunks are loading differently');
    }

    console.log('\n📸 Taking screenshot...');
    await page.screenshot({ path: 'k:/VirtualWorld/screenshot-sequential.png' });

    console.log('='.repeat(70));

  } catch (error) {
    console.error('\n❌ Test failed:', error.message);
  } finally {
    console.log('\nClosing browser in 3 seconds...');
    await page.waitForTimeout(3000);
    await browser.close();
  }
})();
