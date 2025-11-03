/**
 * Log File Monitor
 * Watches browser-console.log and outputs new lines in real-time
 */

const fs = require('fs');
const path = require('path');

const LOG_FILE = path.join(__dirname, 'browser-console.log');
let lastSize = 0;

console.log('👁️  Monitoring browser-console.log for changes...\n');

function checkLog() {
  if (!fs.existsSync(LOG_FILE)) {
    return;
  }

  const stats = fs.statSync(LOG_FILE);
  const currentSize = stats.size;

  if (currentSize > lastSize) {
    const stream = fs.createReadStream(LOG_FILE, {
      start: lastSize,
      end: currentSize,
      encoding: 'utf8'
    });

    stream.on('data', (chunk) => {
      process.stdout.write(chunk);
    });

    lastSize = currentSize;
  }
}

// Check every 100ms
setInterval(checkLog, 100);

// Initial check
checkLog();
