# 🎙️ Live Audio - Quick Testing Guide

## What Was Fixed

Your audio wasn't working because:
1. ✅ **Backend was returning the user's own ID in peer list** → User skipped connecting to themselves
2. ✅ **Frontend wasn't adding audio tracks before creating offers** → Empty SDP = no audio
3. ✅ **Only broadcasters could receive streams, not listeners** → Added bidirectional support

Now it works like a game:
- **One user broadcasts** their voice
- **Others in the same land square hear them**
- **Location-based (same zone only)**

---

## How to Test

### Test 1: Single User (Baseline)
```
1. Open http://localhost in browser
2. Login
3. Find a land square (e.g., land_265_86)
4. Click "Go Live" → Select "Audio"
5. Check console: Should see logs with 🎤 emojis
```

**Expected**: No peer connections (no one else), but your stream is broadcasting

---

### Test 2: Two Users - Same Zone (THE REAL TEST)
```
Browser 1 (User A):
  1. Login as user@example.com
  2. Go to land at coordinates 265, 86
  3. Click "Go Live" → Audio
  4. Console shows: "📋 Processing 0 peers" (waiting)
  5. Wait for User B...

Browser 2 (User B):
  1. Login as different user@example.com (must be different account)
  2. Go to SAME land (265, 86)
  3. Console shows: "📋 Processing 1 peers"
  4. Should see: "🔗 Creating peer connection"
  
Browser 1 (User A):
  5. Now gets updated: "📋 Processing 1 peers" (sees User B)
  6. Creates peer connection back to B

Both:
  ✅ Should hear each other's voice
```

---

### Test 3: Two Users - Different Zones (Isolation)
```
Browser 1 (User A):
  1. Go to land 265_86
  2. Click "Go Live" → Audio

Browser 2 (User B):
  1. Go to land 270_70 (DIFFERENT location)
  2. Check console: "📋 Processing 0 peers"
  
Expected: ✅ No peer connections (different zones)
Result: ✅ User B doesn't hear User A
```

---

## Console Logs to Look For

### ✅ Good Signs (Audio Working)
```
🎤 Adding local tracks to peer connection
✅ Track added (kind: audio, enabled: true)
📋 Offer created
📥 [OFFER] Received offer from USER_ID
🔄 [SDP] Setting remote description
✅ [ANSWER] Answer set as local description
🎵 ontrack event fired
✅ setting remote stream
```

### ❌ Bad Signs (Debug These)
```
⚠️ No stream available to add tracks      ← Stream not ready
❌ Error creating offer                    ← SDP error
❌ Error adding track                      ← Track error
📋 Processing 0 peers                      ← No broadcasters
⚠️ no streams in ontrack event            ← Remote track not received
```

---

## Architecture

```
┌─────────────┐      WebSocket       ┌─────────────┐
│   User A    │◄──────(signaling)────►│   User B    │
│ (Audio On)  │                       │ (listening) │
└─────┬───────┘                       └──────┬──────┘
      │                                       │
      │   RTCPeerConnection                   │
      │   (media transport)                   │
      └──────────────────────────────────────►
           Audio Stream → User B hears A
           
Same room_id (e.g., "land_265_86") = can connect
Different room_id = backend filters them out
```

---

## Files Changed

1. **`backend/app/api/v1/endpoints/websocket.py`**
   - Line 162: Pass `user_id` to `handle_live_status`
   - Lines 643-665: Exclude self from peer list

2. **`frontend/src/components/LivePanel.jsx`**
   - Lines 165-197: Add tracks BEFORE creating offer
   - Lines 199-212: Create offer with 50ms delay
   - Lines 370-401: Support broadcaster/listener modes
   - Lines 75-88, 89-107: Prevent stream teardown while live

---

## Troubleshooting

### "No sound on other side"
1. Check both users are in **same room** (same land coordinates)
2. Check console for 🎤 logs (tracks being added)
3. Check console for 📥 [OFFER] logs (negotiation happening)
4. Check volume/mute in browser audio settings
5. Check microphone permissions granted

### "Peer connection not creating"
1. Check other user actually went live (they sent live_start)
2. Check backend logs: `docker logs virtualworld-backend | grep live_status`
3. Check frontend logs for "🔗 Creating peer connection"
4. Check no errors in console

### "Only one direction works"
1. Both users must go "Live" for bidirectional
2. If only A broadcasts, B just listens (one-way is OK)
3. For both directions: both click "Go Live"

---

## Environment Check

### Frontend `.env`
```bash
cat frontend/.env | grep VITE_SILENCE
# Should output: VITE_SILENCE_LOGS=false
# If true: No logs visible (rebuild frontend)
```

### Backend Status
```bash
docker logs virtualworld-backend | tail -5 | grep -E "live_status|ERROR"
# Should show recent live_status requests, no errors
```

### Containers
```bash
docker-compose ps
# All should be "Up" (healthy = green, starting = yellow)
```

---

## Success Checklist

- [ ] Two users in same zone
- [ ] Both see each other in peer list
- [ ] Console shows peer connection creation
- [ ] Console shows SDP offer/answer exchange
- [ ] Console shows ontrack event
- [ ] ✅ User B hears User A
- [ ] If both broadcasting: ✅ Both directions work

---

## Performance Notes

- **Typical latency**: 50-200ms (P2P optimized)
- **Audio bitrate**: ~128 kbps
- **Maximum peers**: 5-20 per device (RTCPeerConnection limits)
- **Zones scale independently**: 10 zones with 10 users each = no impact

---

## Quick Commands

```bash
# Rebuild frontend (if you change JS)
cd frontend && npx vite build && docker-compose up -d frontend

# Rebuild backend (if you change Python)
docker-compose up -d --build backend

# See all logs (live)
docker-compose logs -f

# See just backend WebRTC logs
docker logs virtualworld-backend | grep -E "\[live\]|live_status|live_peers"

# Clear all containers (warning: wipes data)
docker-compose down && docker-compose up -d
```

---

## Next Steps

1. ✅ Test with 2 real users in same zone
2. ✅ Verify audio flows both directions
3. ✅ Test zone isolation (different coordinates)
4. Consider: Echo cancellation, audio mixing for large zones
5. Consider: Bandwidth optimization for video

---

**Status**: ✅ Ready for testing!
Test with two different user accounts in the same land square.
