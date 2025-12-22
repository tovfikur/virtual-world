# Manual Audio Test Instructions

## Setup

1. Open **2 browser windows/tabs** with the application at `http://localhost`
2. **Window 1**: Log in as `topubiswas1234@gmail.com` / `topubiswas1234@gmail.com`
3. **Window 2**: Log in as `demo@example.com` / `DemoPassword123!`

## Step 1: Navigate to Same Land

Both users need to be on the **same land tile**.

1. In **Window 1** (USER 1):

   - Click on the world map to navigate to a land tile (e.g., around coordinate 0,0)
   - Wait for the land to load

2. In **Window 2** (USER 2):
   - Navigate to the **exact same land tile** by clicking the same area
   - Confirm both users are on the same land (should see each other as player models)

## Step 2: USER 1 Goes Live with Audio

1. In **Window 1**, look for the **Live Panel** (should be visible on the page)
2. Click the **"Go Live (Audio)"** button
3. Your browser will ask for microphone permission - **ALLOW IT**
4. Wait 2-3 seconds for the stream to start
5. You should see:
   - Your own audio tile appear in the Live Panel (showing "You")
   - The "Go Live (Audio)" button becomes disabled
   - A "Stop" button appears

## Step 3: USER 2 Joins the Audio Stream

1. In **Window 2**, you should immediately see:

   - The live peers list update to show `topubiswas1234` is broadcasting audio
   - USER 1's audio tile appears in the Live Panel

2. Click on USER 1's audio tile (or it might auto-play)

## Step 4: Test Audio

1. **USER 1 (topubiswas1234)**: Speak into your microphone
2. **USER 2 (demo@example.com)**: Listen for audio from USER 1

**SUCCESS CRITERIA**:

- ✅ USER 2 can hear USER 1's voice clearly
- ✅ No delays or stuttering
- ✅ Audio starts immediately when USER 1 speaks

## Debugging

If audio doesn't flow:

### Check USER 1 (Broadcaster):

- Open **DevTools** (F12)
- Go to **Console** tab
- Look for logs starting with `[live]`
- Should see:
  - `[live] startLive click`
  - `[live] media granted` with audio track
  - `[live] live_start sent`
  - `[live] ✅ added local track`

### Check USER 2 (Listener):

- Open **DevTools** (F12)
- Go to **Console** tab
- Look for `[live]` logs
- Should see:
  - `[live] live_peers received` with USER 1 in the list
  - `[live] createPeerConnection` with USER 1's ID
  - `[live] 🎵 ontrack event fired` with audio track
  - `[live] ✅ added remote stream`

## Known Issues Fixed

1. ✅ **Fixed**: useEffect was calling teardown() immediately after startLive

   - Cause: Logic error - was unconditionally tearing down before checking if in room
   - Status: FIXED - only teardown if NOT in a room
   - Deployment: Frontend rebuilt and deployed

2. ✅ **Fixed**: SimplePeer library had bugs with stream handling
   - Cause: SimplePeer doesn't properly expose addTrack() method
   - Solution: Replaced with RTCPeerConnection API directly
   - Status: COMPLETE - all track addition now works

## Expected Timeline

1. USER 1 clicks "Go Live (Audio)" → ~2 seconds for stream setup
2. USER 2 receives `live_peers` update → ~1 second after USER 1 goes live
3. USER 2 receives `live_offer` and connects → ~2-3 seconds
4. Audio starts flowing → immediate once connection established

**Total time from click to hearing audio: ~5-7 seconds**
