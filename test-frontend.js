/**
 * Frontend Browser Test
 * Tests the frontend and captures console errors
 */

const puppeteer = require('puppeteer');

async function testFrontend() {
  console.log('🚀 Starting browser test...\n');

  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();

  // Capture console messages
  const consoleMessages = [];
  page.on('console', msg => {
    const type = msg.type();
    const text = msg.text();
    consoleMessages.push({ type, text });

    if (type === 'error' || type === 'warning') {
      console.log(`[${type.toUpperCase()}] ${text}`);
    }
  });

  // Capture page errors
  page.on('pageerror', error => {
    console.log(`[PAGE ERROR] ${error.message}`);
    consoleMessages.push({ type: 'pageerror', text: error.message });
  });

  // Capture failed requests
  page.on('requestfailed', request => {
    console.log(`[REQUEST FAILED] ${request.url()}: ${request.failure().errorText}`);
  });

  try {
    console.log('📄 Loading http://localhost/login\n');
    await page.goto('http://localhost/login', {
      waitUntil: 'networkidle2',
      timeout: 30000
    });

    console.log('✅ Page loaded successfully\n');

    // Check if login form exists
    const hasEmailInput = await page.$('input[type="email"]');
    const hasPasswordInput = await page.$('input[type="password"]');
    const hasSubmitButton = await page.$('button[type="submit"]');

    console.log('🔍 Form elements check:');
    console.log(`   Email input: ${hasEmailInput ? '✅' : '❌'}`);
    console.log(`   Password input: ${hasPasswordInput ? '✅' : '❌'}`);
    console.log(`   Submit button: ${hasSubmitButton ? '✅' : '❌'}\n`);

    // Test login with demo credentials
    if (hasEmailInput && hasPasswordInput && hasSubmitButton) {
      console.log('🔐 Testing login with demo credentials...');
      await page.type('input[type="email"]', 'demo@example.com');
      await page.type('input[type="password"]', 'DemoPassword123!');

      // Wait for navigation after clicking submit
      await Promise.all([
        page.waitForNavigation({ timeout: 10000 }).catch(e => {
          console.log('Navigation timeout (might be expected if error occurs)');
        }),
        page.click('button[type="submit"]')
      ]);

      const currentUrl = page.url();
      console.log(`   Current URL after login: ${currentUrl}`);

      if (currentUrl.includes('/world')) {
        console.log('   ✅ Login successful - redirected to /world\n');
      } else if (currentUrl.includes('/login')) {
        console.log('   ⚠️  Still on login page - checking for errors...\n');
      }
    }

    // Wait a bit for any async errors
    await page.waitForTimeout(3000);

    // Summary
    console.log('📊 Console Summary:');
    const errors = consoleMessages.filter(m => m.type === 'error' || m.type === 'pageerror');
    const warnings = consoleMessages.filter(m => m.type === 'warning');

    console.log(`   Errors: ${errors.length}`);
    console.log(`   Warnings: ${warnings.length}`);
    console.log(`   Total messages: ${consoleMessages.length}\n`);

    if (errors.length > 0) {
      console.log('❌ Errors detected:');
      errors.slice(0, 10).forEach(e => console.log(`   - ${e.text}`));
      if (errors.length > 10) {
        console.log(`   ... and ${errors.length - 10} more\n`);
      }
    } else {
      console.log('✅ No errors detected!\n');
    }

  } catch (error) {
    console.error('❌ Test failed:', error.message);
  } finally {
    await browser.close();
    console.log('🏁 Browser closed');
  }
}

testFrontend().catch(console.error);
