# Virtual Land World - Chat & WebRTC Communication

## WebSocket Chat Implementation

```python
# app/api/v1/websocket/connection_manager.py

from fastapi import WebSocket
import json
from typing import List, Set
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.user_connections: dict = {}  # user_id -> WebSocket
        self.room_members: dict = {}  # room_id -> Set[user_id]

    async def connect(self, websocket: WebSocket, user_id: str):
        """Register new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.user_connections[user_id] = websocket
        logger.info(f"User {user_id} connected")

    async def disconnect(self, user_id: str):
        """Unregister WebSocket connection."""
        if user_id in self.user_connections:
            ws = self.user_connections[user_id]
            self.active_connections.remove(ws)
            del self.user_connections[user_id]
            logger.info(f"User {user_id} disconnected")

    async def broadcast_to_room(self, room_id: str, message: dict):
        """Send message to all users in room."""
        if room_id not in self.room_members:
            return

        for user_id in self.room_members[room_id]:
            if user_id in self.user_connections:
                ws = self.user_connections[user_id]
                try:
                    await ws.send_json(message)
                except Exception as e:
                    logger.error(f"Send error to {user_id}: {e}")

    async def send_personal_message(self, user_id: str, message: dict):
        """Send message to specific user."""
        if user_id in self.user_connections:
            ws = self.user_connections[user_id]
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.error(f"Send error: {e}")

    async def join_room(self, user_id: str, room_id: str):
        """Add user to room."""
        if room_id not in self.room_members:
            self.room_members[room_id] = set()
        self.room_members[room_id].add(user_id)

        # Notify others
        await self.broadcast_to_room(room_id, {
            "type": "presence.update",
            "data": {
                "action": "user_joined",
                "user_id": user_id,
                "count": len(self.room_members[room_id])
            }
        })

    async def leave_room(self, user_id: str, room_id: str):
        """Remove user from room."""
        if room_id in self.room_members:
            self.room_members[room_id].discard(user_id)

            await self.broadcast_to_room(room_id, {
                "type": "presence.update",
                "data": {
                    "action": "user_left",
                    "user_id": user_id,
                    "count": len(self.room_members[room_id])
                }
            })

manager = ConnectionManager()
```

## WebSocket Endpoint

```python
# app/api/v1/websocket/connection.py

from fastapi import APIRouter, WebSocket, Depends, Query
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    token: str = Query(...)
):
    """WebSocket connection for real-time messaging."""

    # Authenticate
    try:
        payload = auth_service.verify_token(token)
        if payload["sub"] != user_id:
            await websocket.close(code=401)
            return
    except:
        await websocket.close(code=401)
        return

    # Connect
    await manager.connect(websocket, user_id)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "chat.send":
                # Handle chat message
                room_id = data.get("room_id")
                message_text = data.get("message")

                # Encrypt message
                encrypted = await encryption_service.encrypt_message(
                    message_text,
                    room_id
                )

                # Store in database
                msg = Message(
                    session_id=room_id,
                    sender_id=user_id,
                    encrypted_payload=encrypted["ciphertext"],
                    iv=encrypted["iv"]
                )
                db.add(msg)
                await db.commit()

                # Broadcast
                await manager.broadcast_to_room(room_id, {
                    "type": "chat.receive",
                    "data": {
                        "message_id": str(msg.message_id),
                        "sender_id": user_id,
                        "message": encrypted["ciphertext"],
                        "iv": encrypted["iv"]
                    }
                })

            elif msg_type == "presence.update":
                room_id = data.get("room_id")
                action = data.get("action")

                if action == "join":
                    await manager.join_room(user_id, room_id)
                elif action == "leave":
                    await manager.leave_room(user_id, room_id)

            elif msg_type == "call.initiate":
                # WebRTC call signaling
                room_id = data.get("room_id")
                call_id = data.get("call_id")

                # Notify room of incoming call
                await manager.broadcast_to_room(room_id, {
                    "type": "call.initiate",
                    "data": {
                        "initiator": user_id,
                        "call_id": call_id,
                        "call_type": data.get("call_type")
                    }
                })

            elif msg_type == "call.signal":
                # WebRTC offer/answer/candidate
                to_user = data.get("to_id")
                signal_data = data.get("signal_data")

                await manager.send_personal_message(to_user, {
                    "type": "call.signal",
                    "data": {
                        "from_id": user_id,
                        "signal_type": data.get("signal_type"),
                        "signal_data": signal_data
                    }
                })

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await manager.disconnect(user_id)
```

## Encryption Service

```typescript
// src/services/encryption.ts

export class EncryptionService {
    private sharedKey: CryptoKey | null = null

    async generateKeyPair() {
        return await crypto.subtle.generateKey(
            { name: "ECDH", namedCurve: "P-256" },
            false,
            ["deriveKey", "deriveBits"]
        )
    }

    async deriveSharedKey(otherPublicKey: CryptoKey, ownPrivateKey: CryptoKey) {
        this.sharedKey = await crypto.subtle.deriveKey(
            { name: "ECDH", public: otherPublicKey },
            ownPrivateKey,
            { name: "AES-GCM", length: 256 },
            false,
            ["encrypt", "decrypt"]
        )
    }

    async encryptMessage(message: string): Promise<{ ciphertext: string; iv: string }> {
        if (!this.sharedKey) throw new Error("Shared key not established")

        const iv = crypto.getRandomValues(new Uint8Array(12))
        const encoded = new TextEncoder().encode(message)

        const ciphertext = await crypto.subtle.encrypt(
            { name: "AES-GCM", iv },
            this.sharedKey,
            encoded
        )

        return {
            ciphertext: this.arrayBufferToBase64(ciphertext),
            iv: this.arrayBufferToBase64(iv)
        }
    }

    async decryptMessage(ciphertext: string, iv: string): Promise<string> {
        if (!this.sharedKey) throw new Error("Shared key not established")

        const decrypted = await crypto.subtle.decrypt(
            { name: "AES-GCM", iv: this.base64ToArrayBuffer(iv) },
            this.sharedKey,
            this.base64ToArrayBuffer(ciphertext)
        )

        return new TextDecoder().decode(decrypted)
    }

    private arrayBufferToBase64(buffer: ArrayBuffer): string {
        return btoa(String.fromCharCode(...new Uint8Array(buffer)))
    }

    private base64ToArrayBuffer(base64: string): ArrayBuffer {
        const binaryString = atob(base64)
        const bytes = new Uint8Array(binaryString.length)
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i)
        }
        return bytes.buffer
    }
}
```

**Resume Token:** `✓ PHASE_6_COMPLETE`
