import { test } from '@playwright/test';

test('Debug: Check if local tracks are being added to RTCPeerConnection', async ({ browser }) => {
  const context = await browser.newContext({
    permissions: ['microphone', 'camera'],
  });
  const page = await context.newPage();

  const logs = [];
  page.on('console', msg => {
    const text = msg.text();
    logs.push(`[${msg.type()}] ${text}`);
    if (text.includes('added local track') || text.includes('about to add') || text.includes('ontrack') || text.includes('error adding track')) {
      console.log(`>>> ${text}`);
    }
  });

  // Login
  await page.goto('http://localhost');
  await page.fill('input[type="email"]', 'topubiswas1234@gmail.com');
  await page.fill('input[type="password"]', 'topubiswas1234@gmail.com');
  await page.click('button:has-text("Sign in")');
  await page.waitForURL('**/world', { timeout: 30000 });
  await page.waitForTimeout(2000);

  console.log('\n=== USER GOES LIVE ===');
  
  const liveButton = await page.locator('button:has-text("Go Live")').first();
  if (await liveButton.isVisible()) {
    await liveButton.click();
    await page.waitForTimeout(4000);
  }

  console.log('\n=== ANALYSIS ===');
  
  // Check specific logs
  const aboutToAddLogs = logs.filter(log => log.includes('about to add local tracks'));
  const addedTrackLogs = logs.filter(log => log.includes('added local track'));
  const errorAddingLogs = logs.filter(log => log.includes('error adding track'));
  const noStreamLogs = logs.filter(log => log.includes('no stream to add tracks from'));
  const ontrackLogs = logs.filter(log => log.includes('ontrack event fired'));

  console.log(`About to add local tracks: ${aboutToAddLogs.length}`);
  aboutToAddLogs.slice(-3).forEach(log => console.log(`  ${log}`));

  console.log(`\nLocal tracks actually added: ${addedTrackLogs.length}`);
  addedTrackLogs.slice(-3).forEach(log => console.log(`  ${log}`));

  console.log(`\nErrors adding tracks: ${errorAddingLogs.length}`);
  errorAddingLogs.forEach(log => console.log(`  ${log}`));

  console.log(`\nNo stream available to add: ${noStreamLogs.length}`);
  noStreamLogs.forEach(log => console.log(`  ${log}`));

  console.log(`\nOntrack events received: ${ontrackLogs.length}`);
  ontrackLogs.forEach(log => console.log(`  ${log}`));

  // Detailed troubleshooting
  console.log('\n=== KEY FINDINGS ===');
  if (aboutToAddLogs.length === 0) {
    console.log('❌ createPeerConnection was never called (no peers to add tracks to)');
  } else if (addedTrackLogs.length === 0 && noStreamLogs.length > 0) {
    console.log('❌ Stream was null when trying to add tracks');
  } else if (addedTrackLogs.length === 0 && errorAddingLogs.length > 0) {
    console.log('❌ Error occurred while adding tracks');
  } else if (addedTrackLogs.length > 0 && ontrackLogs.length === 0) {
    console.log('⚠️ Tracks were added but no ontrack events fired (peers may not be connected yet)');
  }

  await context.close();
});
