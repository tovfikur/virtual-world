#!/usr/bin/env node
/**
 * Manual Live Audio Test
 * Run this, then:
 * 1. Open http://localhost in browser 1 and 2
 * 2. Follow the printed instructions
 * 3. Check the console output
 */

console.log(`
╔════════════════════════════════════════════════════════════════╗
║           VIRTUALWORLD LIVE AUDIO TEST SCRIPT                  ║
╚════════════════════════════════════════════════════════════════╝

This script will help you test live audio streaming between two users.

PREREQUISITES:
✓ Docker containers running (postgres, redis, backend, frontend)
✓ Two browser windows or tabs ready
✓ Test user accounts created or default users available

SETUP STEPS:

1️⃣  BROWSER 1 (User A - Broadcaster):
   └─ Open: http://localhost
   └─ Login with test account (e.g., testuser1@test.com)
   └─ Navigate to a land (click on map)
   └─ Open DevTools: F12 → Console
   └─ Watch for [live] prefixed console logs

2️⃣  BROWSER 2 (User B - Listener):
   └─ Open: http://localhost (separate window/tab)
   └─ Login with DIFFERENT test account (e.g., testuser2@test.com)
   └─ Navigate to the SAME land
   └─ Open DevTools: F12 → Console
   └─ Watch for [live] prefixed console logs

3️⃣  BROWSER 1 - GO LIVE:
   └─ Click "Go Live (Audio)" button
   └─ Grant microphone permission if prompted
   └─ Wait for "You (live)" to appear
   └─ Check console for:
      ✓ "✅ added local track" with kind: "audio"
      ✓ "media granted" with track kinds

4️⃣  BROWSER 2 - RECEIVE:
   └─ Wait for User A to appear as a live broadcaster
   └─ Check console for:
      ✓ "📨 offer received from [User A ID]"
      ✓ "✅ answer created"
      ✓ "🎵 ontrack event fired" with kind: "audio"
   └─ Try to hear audio from User A

5️⃣  BROWSER 1 - SPEAK:
   └─ Speak into your microphone
   └─ User B should hear you

╔════════════════════════════════════════════════════════════════╗
║                   DEBUG LOG INDICATORS                         ║
╚════════════════════════════════════════════════════════════════╝

SUCCESS SIGNS (in console):
✅ about to add local tracks → [count] > 0
✅ added local track → should show audio track
✅ offer created
✅ answer created  
✅ ontrack event fired → Audio is flowing!
✅ connectionstatechange → connected

FAILURE SIGNS:
❌ about to add local tracks → trackCount: 0 (no audio)
❌ no stream to add tracks from (stream not captured)
❌ peer not found for signal (connection not established)
❌ No "ontrack event fired" (tracks not reaching receiver)
❌ connectionstatechange → failed

╔════════════════════════════════════════════════════════════════╗
║                      EXPECTED FLOW                             ║
╚════════════════════════════════════════════════════════════════╝

USER A Timeline:
1. Click "Go Live (Audio)"
2. [live] media granted with audio track
3. [live] ✅ added local track kind: audio
4. [live] live_start sent
5. [live] live_peers received (empty or other users)
6. [live] createPeerConnection for User B
7. [live] offer created
8. [live] ✅ answer set as remote description
9. [live] 🧊 adding ICE candidate (multiple times)

USER B Timeline:
1. Already on same land
2. [live] live_peer_joined (User A)
3. [live] createPeerConnection for User A
4. [live] 📨 offer received from [User A]
5. [live] 🔄 setting remote description (offer)
6. [live] ✅ answer created
7. [live] 🎵 ontrack event fired ← AUDIO RECEIVED!
8. [live] 🧊 adding ICE candidate (multiple times)

╔════════════════════════════════════════════════════════════════╗
║                       START TEST                               ║
╚════════════════════════════════════════════════════════════════╝

Ready? Press Enter and follow the steps above...
`);

// Simple progress tracker
const steps = [
  "Browser 1: User A logged in",
  "Browser 2: User B logged in",
  "Both on same land",
  'User A clicks "Go Live (Audio)"',
  "User A: media granted ✓",
  "User A: tracks added ✓",
  "User B: sees User A broadcasting",
  "User B: receives offer",
  "User B: creates answer",
  "User B: ontrack event (audio received!)",
  "User A speaks",
  "User B hears audio ✓✓✓",
];

console.log("\n📋 PROGRESS CHECKLIST:\n");
steps.forEach((step, i) => {
  console.log(`  ${i + 1}. [ ] ${step}`);
});

console.log(`
\n🚀 Open http://localhost in two browser windows and start testing!

💡 TIP: Keep DevTools console visible to watch the [live] logs in real-time.
   Look for emoji indicators (✅, ❌, 📨, 🎵, etc) to track progress.
`);
