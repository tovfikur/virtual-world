const { chromium } = require('playwright');

(async () => {
  console.log('Testing that ONLY visible chunks are loaded...\n');
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  const page = await context.newPage();

  let visibleChunksCount = 0;
  let loadingChunksCount = 0;

  page.on('console', msg => {
    const text = msg.text();

    // Track viewport and visible chunks calculation
    if (text.includes('📐 Viewport:')) {
      console.log('📐', text);
    }

    if (text.includes('📊 Visible area:')) {
      console.log('📊', text);
      const match = text.match(/= (\d+) chunks/);
      if (match) {
        visibleChunksCount = parseInt(match[1]);
      }
    }

    // Track how many chunks are being loaded
    if (text.includes('📦 Sequential loading:')) {
      console.log('📦', text);
      const match = text.match(/loading: (\d+) chunks/);
      if (match) {
        loadingChunksCount = parseInt(match[1]);
      }
    }

    // Track batch loading
    if (text.includes('🔄 Loading batch')) {
      console.log('   ', text);
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

    console.log('\n2. Initial load - checking chunk counts...');
    await page.waitForTimeout(5000);

    console.log('\n3. Taking screenshot...');
    await page.screenshot({ path: 'k:/VirtualWorld/screenshot-only-visible.png' });

    console.log('\n' + '='.repeat(70));
    console.log('TEST RESULTS:');
    console.log('='.repeat(70));
    console.log(`Visible chunks calculated: ${visibleChunksCount}`);
    console.log(`Chunks requested to load: ${loadingChunksCount}`);

    if (visibleChunksCount > 0 && loadingChunksCount > 0) {
      if (visibleChunksCount === loadingChunksCount) {
        console.log('\n✅ PERFECT: Loading EXACTLY the visible chunks!');
        console.log(`   ${visibleChunksCount} visible = ${loadingChunksCount} loaded`);
      } else if (loadingChunksCount <= visibleChunksCount * 1.5) {
        console.log('\n✅ GOOD: Loading approximately the visible chunks');
        console.log(`   Difference: ${Math.abs(loadingChunksCount - visibleChunksCount)} chunks`);
      } else {
        console.log('\n⚠️  WARNING: Loading more chunks than visible');
        console.log(`   Visible: ${visibleChunksCount}, Loading: ${loadingChunksCount}`);
        console.log(`   Excess: ${loadingChunksCount - visibleChunksCount} chunks`);
      }
    } else {
      console.log('\n📝 Could not determine chunk counts from logs');
    }

    // Expected chunks for 1920x1080 viewport at zoom 1.0:
    // (1920 / (1.0 * 32)) * (1080 / (1.0 * 32)) = 60 * 33.75 = ~2025 lands
    // 2025 / (32 * 32) = ~2 chunks width * 2 chunks height = ~4 chunks
    // BUT with 32x32 chunk size: 60/32 = ~2 chunks wide, 34/32 = ~2 chunks tall
    // So we expect roughly 2x2 = 4 chunks, or 3x3 = 9 chunks max
    const expectedChunks = 9; // Conservative estimate

    if (visibleChunksCount > 0 && visibleChunksCount <= expectedChunks) {
      console.log(`\n✅ Chunk count is reasonable (≤${expectedChunks} chunks for this viewport)`);
    } else if (visibleChunksCount > expectedChunks) {
      console.log(`\n⚠️  Chunk count seems high (${visibleChunksCount} > ${expectedChunks})`);
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
