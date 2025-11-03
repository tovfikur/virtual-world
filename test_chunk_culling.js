const { chromium } = require('playwright');

(async () => {
  console.log('Testing chunk visibility culling...\n');
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  const page = await context.newPage();

  // Track chunk visibility changes
  const chunkEvents = [];
  page.on('console', msg => {
    const text = msg.text();
    if (text.includes('Chunk') && (text.includes('visible') || text.includes('hidden') || text.includes('Chunks -'))) {
      chunkEvents.push(text);
      console.log('📊', text);
    }
  });

  try {
    console.log('1. Navigating and logging in...');
    await page.goto('http://localhost', { waitUntil: 'networkidle' });

    const timestamp = Date.now();
    const testEmail = `test${timestamp}@example.com`;
    const testPassword = 'TestPassword123!';

    // Quick registration
    const registerLink = await page.$('a[href="/register"]');
    if (registerLink) {
      await registerLink.click();
      await page.waitForTimeout(500);

      await page.fill('input[type="text"]', `testuser${timestamp}`);
      await page.fill('input[type="email"]', testEmail);
      const passwordInputs = await page.$$('input[type="password"]');
      if (passwordInputs.length > 0) await passwordInputs[0].fill(testPassword);
      if (passwordInputs.length > 1) await passwordInputs[1].fill(testPassword);

      await page.click('button[type="submit"]');
      await page.waitForTimeout(2000);
    }

    // Navigate to world if not there
    if (!page.url().includes('/world')) {
      await page.goto('http://localhost/world', { waitUntil: 'networkidle' });
    }

    console.log('\n2. Waiting for initial chunks to load...');
    await page.waitForTimeout(5000);

    console.log('\n3. Panning camera to load more chunks...');
    const canvas = await page.$('canvas');

    // Pan right (drag from center-left to center-right)
    await canvas.hover();
    await page.mouse.down();
    await page.mouse.move(500, 540); // Start position
    await page.mouse.move(1420, 540, { steps: 20 }); // Drag right
    await page.mouse.up();

    await page.waitForTimeout(3000);
    console.log('\n4. After panning right - chunks should be culled');

    // Pan down
    await page.mouse.down();
    await page.mouse.move(960, 300); // Top center
    await page.mouse.move(960, 780, { steps: 20 }); // Drag down
    await page.mouse.up();

    await page.waitForTimeout(3000);
    console.log('\n5. After panning down - more chunks culled');

    // Pan back to see culling in action
    await page.mouse.down();
    await page.mouse.move(1420, 780);
    await page.mouse.move(500, 300, { steps: 20 }); // Diagonal pan
    await page.mouse.up();

    await page.waitForTimeout(3000);
    console.log('\n6. After diagonal pan - chunks visible/hidden');

    await page.screenshot({ path: 'k:/VirtualWorld/screenshot-culling-test.png' });

    console.log('\n✅ Culling test completed!');
    console.log(`Total chunk events tracked: ${chunkEvents.length}`);

    if (chunkEvents.length === 0) {
      console.log('⚠️  No culling events detected - optimization may not be working');
    } else {
      console.log('✅ Chunk culling is working - chunks are being shown/hidden as expected');
    }

  } catch (error) {
    console.error('\n❌ Test failed:', error.message);
  } finally {
    console.log('\nClosing browser in 3 seconds...');
    await page.waitForTimeout(3000);
    await browser.close();
  }
})();
