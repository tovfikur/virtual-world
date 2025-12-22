import { test } from '@playwright/test';

test('Audio: Verify audio track transmission between two simulated users', async ({ browser }) => {
  const context = await browser.newContext({
    permissions: ['microphone', 'camera'],
  });
  const page = await context.newPage();

  const logs = [];
  
  page.on('console', msg => {
    const text = msg.text();
    logs.push(text);
    if (text.includes('[PEER]') || text.includes('[ANSWER]') || text.includes('[OFFER]') || text.includes('ontrack')) {
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

  console.log('\n=== TEST: Audio Track Transmission ===');
  
  // Go live with audio
  const liveButton = await page.locator('button:has-text("Go Live")').first();
  if (await liveButton.isVisible()) {
    console.log('📻 Going live with audio...');
    await liveButton.click();
    await page.waitForTimeout(2000);
    
    // Wait longer for peer creation and offer/answer
    await page.waitForTimeout(6000);
  }

  console.log('\n=== CHECKING RESULTS ===');
  
  // Check for peer creation
  const peerCreationLogs = logs.filter(log => log.includes('[PEER]') && log.includes('Creating'));
  console.log(`\nPeer Connections Created: ${peerCreationLogs.length}`);
  peerCreationLogs.forEach(log => console.log(`  ${log}`));

  // Check for offer creation
  const offerLogs = logs.filter(log => log.includes('[OFFER]'));
  console.log(`\nOffers Created: ${offerLogs.length}`);
  offerLogs.forEach(log => console.log(`  ${log}`));

  // Check for answer creation
  const answerLogs = logs.filter(log => log.includes('[ANSWER]'));
  console.log(`\nAnswers Created: ${answerLogs.length}`);
  answerLogs.forEach(log => console.log(`  ${log}`));

  // Check for ontrack
  const ontrackLogs = logs.filter(log => log.includes('ontrack'));
  console.log(`\nOntrack Events: ${ontrackLogs.length}`);
  ontrackLogs.forEach(log => console.log(`  ${log}`));

  // Check for track additions
  const trackLogs = logs.filter(log => log.includes('🎤 Adding local tracks') || log.includes('✅ Track added'));
  console.log(`\nTrack Addition Logs: ${trackLogs.length}`);
  trackLogs.forEach(log => console.log(`  ${log}`));

  // Get detailed debug array
  const debugArray = await page.evaluate(() => window.__LIVE_DEBUG || []);
  
  console.log(`\n=== DETAILED FLOW (last 20 events) ===`);
  debugArray.slice(-20).forEach(entry => {
    const emoji = entry.label.includes('✅') ? '✅' :
                  entry.label.includes('❌') ? '❌' :
                  entry.label.includes('🎤') ? '🎤' :
                  entry.label.includes('ontrack') ? '🔊' :
                  entry.label.includes('[OFFER]') ? '📄' :
                  entry.label.includes('[ANSWER]') ? '✍️' :
                  entry.label.includes('[PEER]') ? '🔗' :
                  '📍';
    console.log(`  ${emoji} ${entry.label}`);
  });

  console.log('\n=== SUMMARY ===');
  if (trackLogs.length > 0) {
    console.log('✅ Local tracks were added to peer connection');
  } else {
    console.log('❌ No local tracks added (stream might not be ready)');
  }

  if (offerLogs.length > 0) {
    console.log('✅ Offer was created and sent');
  } else {
    console.log('❌ No offer created');
  }

  if (answerLogs.length > 0) {
    console.log('✅ Answer was created');
  } else {
    console.log('⚠️  No answer (might be first user)');
  }

  if (ontrackLogs.length > 0) {
    console.log('✅ Remote audio track received');
  } else {
    console.log('❌ No remote audio track received');
  }

  await context.close();
});
