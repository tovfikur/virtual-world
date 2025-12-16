const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();

  // Listen to console logs
  page.on('console', msg => {
    const type = msg.type();
    const text = msg.text();
    console.log(`[Browser ${type.toUpperCase()}]`, text);
  });

  // Listen to network requests
  page.on('request', request => {
    if (request.url().includes('/api/')) {
      console.log(`[REQUEST] ${request.method()} ${request.url()}`);
      if (request.postData()) {
        console.log(`[REQUEST BODY]`, request.postData());
      }
    }
  });

  page.on('response', async response => {
    if (response.url().includes('/api/')) {
      console.log(`[RESPONSE] ${response.status()} ${response.url()}`);
      try {
        const body = await response.text();
        console.log(`[RESPONSE BODY]`, body.substring(0, 500));
      } catch (e) {}
    }
  });

  try {
    console.log('\n=== Step 1: Navigate to login page ===');
    await page.goto('http://localhost:3000/login');
    await page.waitForTimeout(2000);

    console.log('\n=== Step 2: Login as topu@gmail.com ===');
    await page.fill('input[type="email"], input[name="email"]', 'topu@gmail.com');
    await page.fill('input[type="password"], input[name="password"]', 'DemoPassword123!');
    await page.click('button[type="submit"]');
    await page.waitForTimeout(3000);

    console.log('\n=== Step 3: Navigate to world page ===');
    await page.goto('http://localhost:3000/world');
    await page.waitForTimeout(5000);

    console.log('\n=== Step 4: Click on a land (Ctrl+Click for multi-select) ===');
    // Wait for canvas to be ready
    await page.waitForSelector('canvas', { timeout: 10000 });

    // Click on canvas to select land (center of screen)
    const canvas = await page.$('canvas');
    const box = await canvas.boundingBox();

    // Click first land
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
    await page.waitForTimeout(2000);

    // Ctrl+Click second land for multi-select
    await page.keyboard.down('Control');
    await page.mouse.click(box.x + box.width / 2 + 50, box.y + box.height / 2);
    await page.keyboard.up('Control');
    await page.waitForTimeout(2000);

    // Ctrl+Click third land
    await page.keyboard.down('Control');
    await page.mouse.click(box.x + box.width / 2 + 100, box.y + box.height / 2);
    await page.keyboard.up('Control');
    await page.waitForTimeout(2000);

    console.log('\n=== Step 5: Try to create listing from multi-select panel ===');

    // Look for "List All on Marketplace" button
    const listAllButton = await page.$('button:has-text("List All on Marketplace")');
    if (listAllButton) {
      console.log('Found "List All on Marketplace" button, clicking...');
      await listAllButton.click();
      await page.waitForTimeout(2000);

      // Fill in listing form
      const priceInput = await page.$('input[placeholder*="Price"]');
      if (priceInput) {
        await priceInput.fill('500');
        await page.waitForTimeout(500);

        // Submit
        const createButton = await page.$('button[type="submit"]:has-text("Create")');
        if (createButton) {
          console.log('Submitting listing form...');
          await createButton.click();
          await page.waitForTimeout(5000);
        }
      }
    } else {
      console.log('Multi-select panel not found. Trying single land listing...');

      // Try single land listing
      const listButton = await page.$('button:has-text("List on Marketplace")');
      if (listButton) {
        console.log('Found single land "List on Marketplace" button');
        await listButton.click();
        await page.waitForTimeout(2000);

        // Fill form
        const priceInput = await page.$('input[placeholder*="Price"]');
        if (priceInput) {
          await priceInput.fill('500');
          await page.waitForTimeout(500);

          const createButton = await page.$('button:has-text("Create")');
          if (createButton) {
            console.log('Creating single listing...');
            await createButton.click();
            await page.waitForTimeout(5000);
          }
        }
      }
    }

    console.log('\n=== Test Complete - Check console output above ===');
    await page.waitForTimeout(5000);

  } catch (error) {
    console.error('\n[ERROR]', error);
  }

  // Don't close browser so you can inspect
  console.log('\n=== Browser will stay open for inspection. Press Ctrl+C to close ===');
  await page.waitForTimeout(300000); // Wait 5 minutes
  await browser.close();
})();
