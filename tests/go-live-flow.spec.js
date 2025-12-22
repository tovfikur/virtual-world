import { test, expect } from '@playwright/test';

test('Capture full Go Live audio flow with console logs', async ({ page, context }) => {
  // Capture ALL console messages
  const consoleLogs = [];
  page.on('console', msg => {
    consoleLogs.push(`[${msg.type()}] ${msg.text()}`);
  });

  // Navigate and login
  await page.goto('http://localhost');
  await page.fill('input[type="email"]', 'topubiswas1234@gmail.com');
  await page.fill('input[type="password"]', 'topubiswas1234@gmail.com');
  await page.click('button:has-text("Sign in")');
  await page.waitForURL('**/world', { timeout: 30000 });
  
  // Wait for world to stabilize
  await page.waitForTimeout(3000);
  
  console.log('========== BEFORE BUTTON CLICK ==========');
  console.log(`Total logs before: ${consoleLogs.length}`);
  const liveLogsBefore = consoleLogs.filter(log => log.includes('[live]')).length;
  console.log(`[live] logs before: ${liveLogsBefore}`);

  // Click the Go Live button
  const liveButton = await page.locator('button:has-text("Go Live")').first();
  if (await liveButton.isVisible()) {
    console.log('✅ Go Live button visible, clicking...');
    await liveButton.click();
    
    // Wait for audio setup
    await page.waitForTimeout(4000);
  } else {
    console.log('❌ Go Live button NOT visible');
  }

  console.log('\n========== AFTER BUTTON CLICK ==========');
  console.log(`Total logs after: ${consoleLogs.length}`);
  const liveLogsAfter = consoleLogs.filter(log => log.includes('[live]')).length;
  console.log(`[live] logs after: ${liveLogsAfter}`);
  console.log(`New [live] logs: ${liveLogsAfter - liveLogsBefore}`);

  console.log('\n========== ALL [live] LOGS AFTER CLICK ==========');
  const liveOnlyLogs = consoleLogs.filter(log => log.includes('[live]'));
  liveOnlyLogs.forEach((log, idx) => {
    console.log(`[${idx}] ${log}`);
  });

  console.log('\n========== KEY FLOW INDICATORS ==========');
  const hasStartLive = consoleLogs.some(log => log.includes('[START] Go Live'));
  const hasGetUserMedia = consoleLogs.some(log => log.includes('getUserMedia'));
  const hasMediaSuccess = consoleLogs.some(log => log.includes('[MEDIA]'));
  const hasBackendLive = consoleLogs.some(log => log.includes('live_start'));
  const hasOntrack = consoleLogs.some(log => log.includes('ontrack'));
  const hasICE = consoleLogs.some(log => log.includes('ICE'));
  
  console.log(`✅ Start Live logged: ${hasStartLive}`);
  console.log(`✅ getUserMedia called: ${hasGetUserMedia}`);
  console.log(`✅ Media success: ${hasMediaSuccess}`);
  console.log(`✅ Backend message sent: ${hasBackendLive}`);
  console.log(`⚠️ ontrack handler fired: ${hasOntrack}`);
  console.log(`⚠️ ICE candidates exchanged: ${hasICE}`);

  // Print all console logs for detailed inspection
  console.log('\n========== ALL CONSOLE LOGS ==========');
  consoleLogs.forEach((log, idx) => {
    console.log(`[${idx}] ${log}`);
  });
});
