# Chat System Test Plan

## Step-by-Step Testing Instructions

### Step 1: Send a Leave Message

1. **Open browser as User "qwe"** (not the owner)
2. **Navigate to land (19, 1)** - owned by "admin"
3. **Open DevTools** (Press F12) → Go to **Console** tab
4. **Open chat** by clicking on the land
5. **Send message**: Type "Test message from qwe" and send
6. **Check console** - should see:
   ```
   Loading message history for land (19, 1)
   Land data: {...}
   ```
7. **Check backend logs** - should see:
   ```
   === Processing message for land (19, 1) ===
   Land found: True, Land owned: <uuid>
   Land is OWNED by user_id=<uuid>
   Chat session: <session_id>
   Room members: ['<qwe_user_id>'], Owner online: False
   Marking as LEAVE MESSAGE (sender != owner and owner offline)
   ✓✓✓ MESSAGE SAVED! msg_id=<msg_id>, session_id=<session_id>, land_id=<land_id>
   ```

### Step 2: Owner Returns and Checks Messages

1. **Logout "qwe"**
2. **Login as "admin"** (the owner)
3. **Navigate to land (19, 1)**
4. **Check map** - should see 🔴 **RED BADGE** on land (19, 1)
5. **Click on land (19, 1)** to open chat
6. **Check console** - should see:
   ```
   Loading message history for land (19, 1)
   Land data: {land_id: "...", ...}
   Land has ID: <land_id>, fetching messages...
   ✓ Received 1 messages from API: [...]
   ✓ Set 1 messages in state
   ```
7. **Check backend logs** - should see:
   ```
   === GET /land/<land_id>/messages called ===
   Valid land UUID: <uuid>
   Getting/creating chat session for land <uuid>
   Chat session ID: <session_id>
   Fetching message history (limit=50)
   Found 1 messages in database
   ✓ Returning 1 messages
   Messages: ['Test message from q...']
   ```
8. **Check chat UI** - should see message "Test message from qwe"
9. **Check map** - badge should turn 🔵 **BLUE** (read)

### Step 3: Verify Read Receipts

1. **Logout "admin"**
2. **Login back as "qwe"**
3. **Navigate to land (19, 1)**
4. **Open chat**
5. **Check your sent message** - should show ✓✓ **blue** checkmark (read)

## Expected Backend Logs

### When sending message (from qwe):
```
=== Processing message for land (19, 1) ===
Land found: True, Land owned: 7b83c1ee-...
Land is OWNED by user_id=7b83c1ee-...
Chat session: a1b2c3d4-...
Room members: ['5f4e3d2c-...'], Owner online: False
Marking as LEAVE MESSAGE (sender != owner and owner offline)
Saving message: content='Test message from qwe', encrypt=False, is_leave_message=True
✓✓✓ MESSAGE SAVED! msg_id=e5f6a7b8-..., session_id=a1b2c3d4-..., land_id=7b83c1ee-...
✓ Message broadcast to 1 connections in room land_19_1
```

### When loading messages (admin opens chat):
```
=== GET /land/7b83c1ee-.../messages called ===
Valid land UUID: 7b83c1ee-...
Getting/creating chat session for land 7b83c1ee-...
Chat session ID: a1b2c3d4-...
Fetching message history (limit=50)
Found 1 messages in database
✓ Returning 1 messages
Messages: ['Test message from q...']
```

## If Messages Don't Appear:

### Check 1: Is the land owned?
- In console, look for `Land data:` log
- Should have `land_id` field (not null)
- If `land_id` is null → Land is NOT owned, messages won't save

### Check 2: Are messages being saved?
- Check backend logs for: `✓✓✓ MESSAGE SAVED!`
- If missing → Message save is failing
- Look for errors above that line

### Check 3: Are messages being loaded?
- Check backend logs for: `Found X messages in database`
- If 0 messages → Check database directly
- If > 0 messages → Check frontend console

### Check 4: Frontend receiving messages?
- Check frontend console for: `✓ Received X messages from API`
- If 0 messages → API not returning messages
- If > 0 messages → Check if they're rendered

## Quick Database Check

Run in backend container:
```bash
docker exec -it virtualworld-backend-1 bash
python -c "
from app.db.session import AsyncSessionLocal
from app.models.chat import Message
from sqlalchemy import select
import asyncio

async def check():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Message).limit(10))
        messages = result.scalars().all()
        print(f'Total messages: {len(messages)}')
        for msg in messages:
            print(f'  - {msg.content_encrypted[:30]}...')

asyncio.run(check())
"
```

## Success Criteria

✅ Message sent by "qwe" appears in backend logs with `✓✓✓ MESSAGE SAVED!`
✅ Red badge appears on land (19, 1) when "admin" logs in
✅ Message appears in chat when "admin" opens land (19, 1)
✅ Badge turns blue after opening chat
✅ Blue checkmark appears on "qwe"'s message when they check back
