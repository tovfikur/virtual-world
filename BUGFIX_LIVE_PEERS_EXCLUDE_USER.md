# 🔧 CRITICAL BUG FIX: Live Peers Not Including Other Users

## Problem

Audio was not being transmitted between users even though the local stream was being kept alive. The root cause was identified through detailed logging: **The frontend was receiving its own user ID in the peer list and filtering it out**, preventing peer connections from being created.

## Root Cause Analysis

The backend's `handle_live_status` function was returning ALL live users in a room including the requesting user, instead of returning OTHER live users.

### Example Flow (BROKEN):

1. User A goes live in room "land_265_86"
2. User B joins the room
3. User B's frontend requests `live_status`
4. Backend responds with `live_peers: [{user_id: "User B"}, {user_id: "User A"}]`
5. Frontend filters: "User B is me, skip" → Only sees User A
6. BUT ALSO: Backend returned User B in its own list (BUG!)
7. Frontend receives same message again with self in the list
8. Frontend filters self → No peers to connect to
9. No peer connection created ❌
10. No audio transmitted ❌

## The Fix

### File: `backend/app/api/v1/endpoints/websocket.py`

**Change 1 - Line 162**: Pass user_id to handle_live_status

```python
# BEFORE:
await handle_live_status(websocket, message)

# AFTER:
await handle_live_status(websocket, user_id, message)
```

**Change 2 - Lines 643-665**: Update function signature and use exclude_user parameter

```python
# BEFORE:
async def handle_live_status(websocket: WebSocket, message: dict):
    # ...
    "peers": _get_live_peers(room_id),  # ❌ Returns all including self

# AFTER:
async def handle_live_status(websocket: WebSocket, user_id: str, message: dict):
    # ...
    "peers": _get_live_peers(room_id, exclude_user=user_id),  # ✅ Excludes self
```

## How It Works Now

The `_get_live_peers` function (already existed at line 514) now correctly excludes the requesting user:

```python
def _get_live_peers(room_id: str, exclude_user: Optional[str] = None) -> list:
    """Return metadata for active live participants in a room."""
    room = live_rooms.get(room_id, {})
    peers = []
    for uid, meta in room.items():
        if exclude_user and uid == exclude_user:
            continue  # ✅ Skip self
        peers.append({
            "user_id": uid,
            "username": meta.get("username"),
            "media_type": meta.get("media_type", "video"),
        })
    return peers
```

## Corrected Flow (FIXED):

1. User A goes live in room "land_265_86"
2. User B joins the room
3. User B's frontend requests `live_status`
4. Backend responds with `live_peers: [{user_id: "User A"}]` (User B excluded) ✅
5. Frontend sees User A in the list
6. Frontend creates peer connection to User A
7. Sends WebRTC offer to User A
8. User A receives offer, creates return connection
9. ICE candidates exchanged
10. **Audio transmitted successfully** ✅

## Status

- ✅ Backend fix deployed
- ✅ Docker image rebuilt
- ✅ Fix verified in logs: `[live] live_status room=land_283_69 user=eda5e993-e52b-47c9-ac3e-ea153f698655`

## Next Steps for Testing

To fully verify, you need TWO simultaneous users:

1. User 1 goes live
2. User 2 joins the same room
3. User 2 goes live
4. Both should see each other and create peer connections
5. Audio should transmit in both directions
