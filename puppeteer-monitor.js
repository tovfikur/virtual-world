/**
 * Puppeteer Interactive Browser Monitor
 * Opens a browser and logs all console messages to console and file
 */

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const LOG_FILE = path.join(__dirname, 'browser-console.log');

// Clear log file
fs.writeFileSync(LOG_FILE, `=== Browser Console Monitor Started at ${new Date().toISOString()} ===\n\n`);

function log(message) {
  const timestamp = new Date().toISOString();
  const logMessage = `[${timestamp}] ${message}\n`;

  // Write to console
  console.log(logMessage.trim());

  // Append to file
  fs.appendFileSync(LOG_FILE, logMessage);
}

async function startMonitor() {
  log('🚀 Starting Puppeteer browser...');

  const browser = await puppeteer.launch({
    headless: false, // Visible browser
    defaultViewport: null,
    args: [
      '--start-maximized',
      '--disable-blink-features=AutomationControlled'
    ]
  });

  const pages = await browser.pages();
  const page = pages[0];

  // Disable cache
  await page.setCacheEnabled(false);

  log('✅ Browser opened');
  log(`📄 Navigate to: http://localhost/login`);

  // Monitor console messages
  page.on('console', msg => {
    const type = msg.type();
    const text = msg.text();

    if (type === 'error') {
      log(`❌ [CONSOLE ERROR] ${text}`);
    } else if (type === 'warning') {
      log(`⚠️  [CONSOLE WARNING] ${text}`);
    } else if (type === 'log' || type === 'info') {
      log(`ℹ️  [CONSOLE LOG] ${text}`);
    }
  });

  // Monitor page errors
  page.on('pageerror', error => {
    log(`💥 [PAGE ERROR] ${error.message}`);
    log(`   Stack: ${error.stack}`);
  });

  // Monitor failed requests
  page.on('requestfailed', request => {
    log(`🚫 [REQUEST FAILED] ${request.url()}`);
    log(`   Error: ${request.failure().errorText}`);
  });

  // Monitor response errors (4xx, 5xx)
  page.on('response', response => {
    const status = response.status();
    const url = response.url();

    if (status >= 400) {
      log(`🔴 [HTTP ${status}] ${url}`);
    }
  });

  // Navigate to login page
  await page.goto('http://localhost/login', {
    waitUntil: 'networkidle2',
    timeout: 30000
  });

  log('');
  log('=' .repeat(80));
  log('🎮 BROWSER IS READY FOR INTERACTION');
  log('=' .repeat(80));
  log('');
  log('Instructions:');
  log('  1. Interact with the browser manually');
  log('  2. I will monitor all console messages in real-time');
  log('  3. Check browser-console.log for full logs');
  log('  4. Press Ctrl+C in terminal to stop monitoring');
  log('');

  // Keep the process running
  process.on('SIGINT', async () => {
    log('');
    log('🛑 Stopping monitor...');
    await browser.close();
    log('✅ Browser closed');
    process.exit(0);
  });

  // Keep alive
  await new Promise(() => {});
}

startMonitor().catch(error => {
  log(`❌ Fatal error: ${error.message}`);
  log(error.stack);
  process.exit(1);
});
