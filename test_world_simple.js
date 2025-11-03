const { chromium } = require('playwright');

(async () => {
  console.log('Starting browser test...');
  const browser = await chromium.launch({ headless: false }); // Set to false to see what's happening
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  const page = await context.newPage();

  // Listen for console messages
  page.on('console', msg => console.log('BROWSER:', msg.type(), msg.text()));

  // Listen for errors
  page.on('pageerror', error => console.log('PAGE ERROR:', error.message));

  // Track API requests
  let chunkRequests = 0;
  page.on('response', response => {
    if (response.url().includes('/chunks/')) {
      chunkRequests++;
      console.log(`Chunk loaded: ${response.url().split('/chunks/')[1].split('?')[0]} - Status: ${response.status()}`);
    }
  });

  try {
    console.log('\n1. Navigating to http://localhost...');
    await page.goto('http://localhost', { waitUntil: 'networkidle', timeout: 30000 });

    console.log('2. Taking screenshot of initial page...');
    await page.screenshot({ path: 'k:/VirtualWorld/screenshot-01-initial.png' });

    const timestamp = Date.now();
    const testEmail = `test${timestamp}@example.com`;
    const testPassword = 'TestPassword123!';
    const testUsername = `testuser${timestamp}`;

    // Try to find register link
    const registerLink = await page.$('a[href="/register"]');
    if (registerLink) {
      console.log('3. Clicking register link...');
      await registerLink.click();
      await page.waitForTimeout(1000);
      await page.screenshot({ path: 'k:/VirtualWorld/screenshot-02-register-page.png' });

      console.log('4. Filling registration form...');
      // Find and fill username
      const usernameInput = await page.$('input[type="text"]');
      if (usernameInput) await usernameInput.fill(testUsername);

      // Find and fill email
      const emailInput = await page.$('input[type="email"]');
      if (emailInput) await emailInput.fill(testEmail);

      // Find and fill password
      const passwordInputs = await page.$$('input[type="password"]');
      if (passwordInputs.length > 0) await passwordInputs[0].fill(testPassword);
      if (passwordInputs.length > 1) await passwordInputs[1].fill(testPassword);

      await page.screenshot({ path: 'k:/VirtualWorld/screenshot-03-form-filled.png' });

      console.log('5. Submitting form...');
      const submitButton = await page.$('button[type="submit"]');
      if (submitButton) {
        await submitButton.click();
        console.log('   Waiting for response...');
        await page.waitForTimeout(3000);
        await page.screenshot({ path: 'k:/VirtualWorld/screenshot-04-after-submit.png' });
      }
    }

    // Check current URL
    const currentUrl = page.url();
    console.log('6. Current URL:', currentUrl);

    // If not on world page, navigate directly
    if (!currentUrl.includes('/world')) {
      console.log('7. Not on world page, navigating directly...');
      await page.goto('http://localhost/world', { waitUntil: 'networkidle', timeout: 10000 });
    }

    console.log('8. On world page! Waiting for rendering...');
    await page.waitForTimeout(5000);

    // Check for canvas
    const canvas = await page.$('canvas');
    console.log('9. Canvas exists:', !!canvas);

    if (canvas) {
      const canvasInfo = await page.evaluate(() => {
        const canvas = document.querySelector('canvas');
        return {
          width: canvas.width,
          height: canvas.height,
          offsetWidth: canvas.offsetWidth,
          offsetHeight: canvas.offsetHeight,
        };
      });
      console.log('   Canvas dimensions:', canvasInfo);
    }

    console.log('10. Total chunk requests:', chunkRequests);

    await page.screenshot({ path: 'k:/VirtualWorld/screenshot-05-world-page.png', fullPage: true });

    // Wait a bit more for chunks to load
    console.log('11. Waiting for more chunks to load...');
    await page.waitForTimeout(5000);

    console.log('12. Final chunk count:', chunkRequests);
    await page.screenshot({ path: 'k:/VirtualWorld/screenshot-06-final.png', fullPage: true });

    console.log('\n✅ Test completed!');
    console.log(`   Total chunks loaded: ${chunkRequests}`);
    console.log('   Screenshots saved in k:/VirtualWorld/');

  } catch (error) {
    console.error('\n❌ Test failed:', error.message);
    await page.screenshot({ path: 'k:/VirtualWorld/screenshot-error.png', fullPage: true });
  } finally {
    console.log('\nClosing browser in 3 seconds...');
    await page.waitForTimeout(3000);
    await browser.close();
  }
})();
