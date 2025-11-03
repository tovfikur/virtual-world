const { chromium } = require('playwright');

(async () => {
  console.log('Starting browser test...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  const page = await context.newPage();

  // Listen for console messages
  page.on('console', msg => console.log('BROWSER LOG:', msg.text()));

  // Listen for errors
  page.on('pageerror', error => console.log('PAGE ERROR:', error.message));

  try {
    console.log('Navigating to http://localhost...');
    await page.goto('http://localhost', { waitUntil: 'networkidle', timeout: 30000 });

    console.log('Taking screenshot of login page...');
    await page.screenshot({ path: 'k:/VirtualWorld/screenshot-login.png', fullPage: true });

    // Check if we're on login page
    const currentUrl = page.url();
    console.log('Current URL:', currentUrl);

    // Register a new user with random credentials
    const timestamp = Date.now();
    const testEmail = `test${timestamp}@example.com`;
    const testPassword = 'TestPassword123!';

    console.log('Attempting to register user:', testEmail);

    // Click register link if on login page
    if (currentUrl.includes('/login')) {
      await page.click('a[href="/register"]');
      await page.waitForURL('**/register', { timeout: 5000 });
    }

    // Fill registration form
    await page.fill('input[name="username"], input[type="text"]', `testuser${timestamp}`);
    await page.fill('input[name="email"], input[type="email"]', testEmail);
    await page.fill('input[name="password"], input[type="password"]', testPassword);

    console.log('Submitting registration form...');
    await page.click('button[type="submit"]');

    // Wait for redirect to world page
    console.log('Waiting for world page to load...');
    await page.waitForURL('**/world', { timeout: 10000 });

    // Wait a bit for world to render
    await page.waitForTimeout(5000);

    console.log('Taking screenshot of world page...');
    await page.screenshot({ path: 'k:/VirtualWorld/screenshot-world.png', fullPage: true });

    // Check for canvas element
    const canvasExists = await page.$('canvas');
    console.log('Canvas element exists:', !!canvasExists);

    // Check if chunks are being loaded
    const apiRequests = [];
    page.on('request', request => {
      if (request.url().includes('/chunks/')) {
        apiRequests.push(request.url());
      }
    });

    await page.waitForTimeout(3000);
    console.log('Chunk requests made:', apiRequests.length);

    // Get any error messages from the page
    const errors = await page.evaluate(() => {
      const errorElements = document.querySelectorAll('.error, [class*="error"]');
      return Array.from(errorElements).map(el => el.textContent);
    });

    if (errors.length > 0) {
      console.log('Errors found on page:', errors);
    }

    // Check the canvas rendering
    const canvasInfo = await page.evaluate(() => {
      const canvas = document.querySelector('canvas');
      if (!canvas) return { exists: false };

      const ctx = canvas.getContext('2d');
      if (!ctx) {
        // Try WebGL
        const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
        if (!gl) return { exists: true, context: 'none', width: canvas.width, height: canvas.height };
        return { exists: true, context: 'webgl', width: canvas.width, height: canvas.height };
      }

      return { exists: true, context: '2d', width: canvas.width, height: canvas.height };
    });

    console.log('Canvas info:', JSON.stringify(canvasInfo, null, 2));

    // Final screenshot
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'k:/VirtualWorld/screenshot-final.png', fullPage: true });

    console.log('\n✅ Test completed successfully!');
    console.log('Screenshots saved:');
    console.log('  - screenshot-login.png');
    console.log('  - screenshot-world.png');
    console.log('  - screenshot-final.png');

  } catch (error) {
    console.error('❌ Test failed:', error.message);
    await page.screenshot({ path: 'k:/VirtualWorld/screenshot-error.png', fullPage: true });
    console.log('Error screenshot saved: screenshot-error.png');
  } finally {
    await browser.close();
  }
})();
