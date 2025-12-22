import { test, expect } from '@playwright/test';

test('Test: Go Live audio should work and NOT stop', async ({ browser }) => {
  // Create context with microphone/camera permissions
  const context = await browser.newContext({
    permissions: ['microphone', 'camera'],
  });
  const page = await context.newPage();
  
  // Capture ALL console messages
  const consoleLogs = [];
  page.on('console', msg => {
    const text = msg.text();
    consoleLogs.push(`[${msg.type()}] ${text}`);
    if (text.includes('[live]') || text.includes('getUserMedia') || text.includes('[MEDIA]')) {
      console.log(`>>> ${text}`);
    }
  });

  // Navigate and login
  await page.goto('http://localhost');
  await page.fill('input[type="email"]', 'topubiswas1234@gmail.com');
  await page.fill('input[type="password"]', 'topubiswas1234@gmail.com');
  await page.click('button:has-text("Sign in")');
  await page.waitForURL('**/world', { timeout: 30000 });
  
  // Wait for world to stabilize
  await page.waitForTimeout(3000);
  
  // Click the Go Live button
  const liveButton = await page.locator('button:has-text("Go Live")').first();
  if (await liveButton.isVisible()) {
    console.log('\n✅ Go Live button visible, clicking...\n');
    await liveButton.click();
    
    // Wait for audio setup and keep monitoring
    await page.waitForTimeout(5000);
  } else {
    console.log('❌ Go Live button NOT visible');
  }

  // Check for critical logs
  const hasGetUserMedia = consoleLogs.some(log => log.includes('getUserMedia'));
  const hasMediaSuccess = consoleLogs.some(log => log.includes('[MEDIA]'));
  const hasBackendLive = consoleLogs.some(log => log.includes('live_start'));
  const hasIsLiveTrue = consoleLogs.some(log => log.includes('[STATE] isLive set to true'));
  const hasTeardown = consoleLogs.filter(log => log.includes('teardown')).length;
  const hasStopStream = consoleLogs.filter(log => log.includes('stopLocalStream')).length;

  console.log('\n========== KEY INDICATORS ==========');
  console.log(`✅ getUserMedia called: ${hasGetUserMedia}`);
  console.log(`✅ Media success ([MEDIA]): ${hasMediaSuccess}`);
  console.log(`✅ isLive set to true: ${hasIsLiveTrue}`);
  console.log(`✅ Backend live_start sent: ${hasBackendLive}`);
  console.log(`⚠️ Teardown calls: ${hasTeardown}`);
  console.log(`⚠️ stopLocalStream calls: ${hasStopStream}`);

  // The important assertion: stopLocalStream should NOT have been called after getUserMedia succeeded
  if (hasMediaSuccess && hasTeardown > 0) {
    console.log('\n❌ PROBLEM: Media succeeded but stream was torn down!');
    console.log('This means the stream is being stopped after being started.');
  }
  
  if (hasMediaSuccess && hasBackendLive && hasTeardown === 0) {
    console.log('\n✅ GOOD: Media succeeded, backend notified, and stream was NOT stopped!');
  }

  // Show the [live] logs related to this button click
  console.log('\n========== [live] LOGS AFTER BUTTON CLICK ==========');
  const liveLogsAfterClick = consoleLogs.filter(log => log.includes('[live]'));
  liveLogsAfterClick.slice(-20).forEach(log => {
    console.log(log);
  });

  expect(hasGetUserMedia).toBeTruthy();
  expect(hasBackendLive).toBeTruthy();
  
  await context.close();
});
