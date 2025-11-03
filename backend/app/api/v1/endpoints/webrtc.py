"""
WebRTC Signaling Endpoints
Handles peer-to-peer voice/video call setup
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Optional
import json
import logging
import uuid
from datetime import datetime

from app.db.session import get_db
from app.services.websocket_service import connection_manager
from app.api.v1.endpoints.websocket import get_user_from_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webrtc", tags=["webrtc"])


# Store active calls: {call_id: {participants, state}}
active_calls: Dict[str, dict] = {}


@router.websocket("/signal")
async def webrtc_signaling(
    websocket: WebSocket,
    token: str = Query(..., description="JWT authentication token"),
    db: AsyncSession = Depends(get_db)
):
    """
    WebRTC signaling server.

    Handles:
    - Offer/Answer exchange (SDP)
    - ICE candidate exchange
    - Call initiation and acceptance
    - Hang up

    Message Types (Client -> Server):
    - call_initiate: Start a call
    - call_accept: Accept incoming call
    - call_reject: Reject incoming call
    - call_hangup: End call
    - offer: WebRTC offer (SDP)
    - answer: WebRTC answer (SDP)
    - ice_candidate: ICE candidate

    Message Types (Server -> Client):
    - incoming_call: Incoming call notification
    - call_started: Call successfully started
    - call_ended: Call ended
    - offer: WebRTC offer forwarded
    - answer: WebRTC answer forwarded
    - ice_candidate: ICE candidate forwarded
    - error: Error message
    """
    # Authenticate user
    user = await get_user_from_token(token, db)

    if not user:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    user_id = str(user.user_id)
    await websocket.accept()

    logger.info(f"WebRTC signaling connected: {user_id}")

    try:
        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                message_type = message.get("type")

                if message_type == "call_initiate":
                    await handle_call_initiate(websocket, user_id, message)

                elif message_type == "call_accept":
                    await handle_call_accept(websocket, user_id, message)

                elif message_type == "call_reject":
                    await handle_call_reject(websocket, user_id, message)

                elif message_type == "call_hangup":
                    await handle_call_hangup(websocket, user_id, message)

                elif message_type == "offer":
                    await handle_offer(websocket, user_id, message)

                elif message_type == "answer":
                    await handle_answer(websocket, user_id, message)

                elif message_type == "ice_candidate":
                    await handle_ice_candidate(websocket, user_id, message)

                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown message type: {message_type}"
                    })

            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON"
                })
            except Exception as e:
                logger.error(f"Error handling WebRTC message: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })

    except WebSocketDisconnect:
        logger.info(f"WebRTC signaling disconnected: {user_id}")
        # Clean up any active calls
        await cleanup_user_calls(user_id)


async def handle_call_initiate(websocket: WebSocket, caller_id: str, message: dict):
    """Handle call initiation."""
    callee_id = message.get("callee_id")
    call_type = message.get("call_type", "audio")  # audio or video

    if not callee_id:
        await websocket.send_json({
            "type": "error",
            "message": "callee_id required"
        })
        return

    # Check if callee is online
    if callee_id not in connection_manager.active_connections:
        await websocket.send_json({
            "type": "error",
            "message": "User is offline"
        })
        return

    # Create call
    call_id = str(uuid.uuid4())
    active_calls[call_id] = {
        "caller_id": caller_id,
        "callee_id": callee_id,
        "call_type": call_type,
        "state": "ringing",
        "started_at": datetime.utcnow().isoformat()
    }

    # Notify callee
    await connection_manager.send_personal_message(
        {
            "type": "incoming_call",
            "call_id": call_id,
            "caller_id": caller_id,
            "call_type": call_type,
            "timestamp": datetime.utcnow().isoformat()
        },
        callee_id
    )

    # Confirm to caller
    await websocket.send_json({
        "type": "call_initiated",
        "call_id": call_id,
        "callee_id": callee_id,
        "state": "ringing"
    })

    logger.info(f"Call initiated: {call_id} ({caller_id} -> {callee_id})")


async def handle_call_accept(websocket: WebSocket, user_id: str, message: dict):
    """Handle call acceptance."""
    call_id = message.get("call_id")

    if not call_id or call_id not in active_calls:
        await websocket.send_json({
            "type": "error",
            "message": "Invalid call_id"
        })
        return

    call = active_calls[call_id]

    # Verify user is the callee
    if call["callee_id"] != user_id:
        await websocket.send_json({
            "type": "error",
            "message": "Not authorized for this call"
        })
        return

    # Update call state
    call["state"] = "active"
    call["accepted_at"] = datetime.utcnow().isoformat()

    # Notify caller
    await connection_manager.send_personal_message(
        {
            "type": "call_accepted",
            "call_id": call_id,
            "callee_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        },
        call["caller_id"]
    )

    # Confirm to callee
    await websocket.send_json({
        "type": "call_started",
        "call_id": call_id,
        "state": "active"
    })

    logger.info(f"Call accepted: {call_id}")


async def handle_call_reject(websocket: WebSocket, user_id: str, message: dict):
    """Handle call rejection."""
    call_id = message.get("call_id")

    if not call_id or call_id not in active_calls:
        return

    call = active_calls[call_id]

    # Verify user is the callee
    if call["callee_id"] != user_id:
        return

    # Notify caller
    await connection_manager.send_personal_message(
        {
            "type": "call_rejected",
            "call_id": call_id,
            "timestamp": datetime.utcnow().isoformat()
        },
        call["caller_id"]
    )

    # Remove call
    del active_calls[call_id]

    logger.info(f"Call rejected: {call_id}")


async def handle_call_hangup(websocket: WebSocket, user_id: str, message: dict):
    """Handle call hangup."""
    call_id = message.get("call_id")

    if not call_id or call_id not in active_calls:
        return

    call = active_calls[call_id]

    # Determine other participant
    other_user = call["callee_id"] if user_id == call["caller_id"] else call["caller_id"]

    # Notify other participant
    await connection_manager.send_personal_message(
        {
            "type": "call_ended",
            "call_id": call_id,
            "reason": "hangup",
            "timestamp": datetime.utcnow().isoformat()
        },
        other_user
    )

    # Remove call
    del active_calls[call_id]

    logger.info(f"Call ended: {call_id}")


async def handle_offer(websocket: WebSocket, user_id: str, message: dict):
    """Forward WebRTC offer to peer."""
    call_id = message.get("call_id")
    sdp = message.get("sdp")

    if not call_id or call_id not in active_calls or not sdp:
        await websocket.send_json({
            "type": "error",
            "message": "Invalid offer"
        })
        return

    call = active_calls[call_id]

    # Forward to callee
    await connection_manager.send_personal_message(
        {
            "type": "offer",
            "call_id": call_id,
            "sdp": sdp,
            "from_user": user_id
        },
        call["callee_id"]
    )


async def handle_answer(websocket: WebSocket, user_id: str, message: dict):
    """Forward WebRTC answer to peer."""
    call_id = message.get("call_id")
    sdp = message.get("sdp")

    if not call_id or call_id not in active_calls or not sdp:
        await websocket.send_json({
            "type": "error",
            "message": "Invalid answer"
        })
        return

    call = active_calls[call_id]

    # Forward to caller
    await connection_manager.send_personal_message(
        {
            "type": "answer",
            "call_id": call_id,
            "sdp": sdp,
            "from_user": user_id
        },
        call["caller_id"]
    )


async def handle_ice_candidate(websocket: WebSocket, user_id: str, message: dict):
    """Forward ICE candidate to peer."""
    call_id = message.get("call_id")
    candidate = message.get("candidate")

    if not call_id or call_id not in active_calls or not candidate:
        return

    call = active_calls[call_id]

    # Determine target user
    target_user = call["callee_id"] if user_id == call["caller_id"] else call["caller_id"]

    # Forward ICE candidate
    await connection_manager.send_personal_message(
        {
            "type": "ice_candidate",
            "call_id": call_id,
            "candidate": candidate,
            "from_user": user_id
        },
        target_user
    )


async def cleanup_user_calls(user_id: str):
    """Clean up calls when user disconnects."""
    calls_to_remove = []

    for call_id, call in active_calls.items():
        if call["caller_id"] == user_id or call["callee_id"] == user_id:
            # Notify other participant
            other_user = call["callee_id"] if user_id == call["caller_id"] else call["caller_id"]

            await connection_manager.send_personal_message(
                {
                    "type": "call_ended",
                    "call_id": call_id,
                    "reason": "disconnect",
                    "timestamp": datetime.utcnow().isoformat()
                },
                other_user
            )

            calls_to_remove.append(call_id)

    # Remove calls
    for call_id in calls_to_remove:
        del active_calls[call_id]

    if calls_to_remove:
        logger.info(f"Cleaned up {len(calls_to_remove)} calls for user {user_id}")


@router.get("/active-calls")
async def get_active_calls():
    """
    Get list of currently active calls.

    Returns call statistics and active call count.
    """
    return {
        "active_calls": len(active_calls),
        "calls": [
            {
                "call_id": call_id,
                "call_type": call["call_type"],
                "state": call["state"],
                "started_at": call["started_at"]
            }
            for call_id, call in active_calls.items()
        ],
        "timestamp": datetime.utcnow().isoformat()
    }
