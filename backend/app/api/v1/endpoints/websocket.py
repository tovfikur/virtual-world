"""
WebSocket Endpoints
Real-time communication, chat, and presence
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
import json
import logging
import uuid
from datetime import datetime

from app.db.session import get_db
from app.models.user import User
from app.models.land import Land
from app.services.websocket_service import connection_manager
from app.services.chat_service import chat_service
from app.services.auth_service import auth_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ws", tags=["websocket"])


async def get_user_from_token(token: str, db: AsyncSession) -> Optional[User]:
    """
    Verify JWT token and get user.

    Args:
        token: JWT token
        db: Database session

    Returns:
        User instance or None
    """
    try:
        payload = auth_service.verify_token(token)
        user_id = uuid.UUID(payload.get("sub"))

        result = await db.execute(
            select(User).where(User.user_id == user_id)
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        return None


@router.websocket("/connect")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT authentication token"),
    db: AsyncSession = Depends(get_db)
):
    """
    Main WebSocket connection endpoint.

    Handles:
    - User authentication via JWT
    - Connection lifecycle
    - Message routing
    - Room management
    - Presence updates

    Message Types (Client -> Server):
    - join_room: Join a chat room
    - leave_room: Leave a chat room
    - send_message: Send chat message
    - update_location: Update user location
    - typing: Typing indicator

    Message Types (Server -> Client):
    - message: Chat message
    - user_joined: User joined room
    - user_left: User left room
    - presence_update: User online/offline
    - typing: Someone is typing
    - error: Error message
    """
    # Authenticate user
    user = await get_user_from_token(token, db)

    if not user:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    user_id = str(user.user_id)

    # Connect user
    await connection_manager.connect(websocket, user_id)

    # Send welcome message
    await websocket.send_json({
        "type": "connected",
        "user_id": user_id,
        "username": user.username,
        "timestamp": datetime.utcnow().isoformat(),
        "message": "Connected to Virtual Land World"
    })

    try:
        while True:
            # Receive message
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                message_type = message.get("type")

                # Handle different message types
                if message_type == "join_room":
                    await handle_join_room(websocket, user_id, message, db)

                elif message_type == "leave_room":
                    await handle_leave_room(websocket, user_id, message, db)

                elif message_type == "send_message":
                    await handle_send_message(websocket, user_id, message, db)

                elif message_type == "update_location":
                    await handle_update_location(websocket, user_id, message, db)

                elif message_type == "typing":
                    await handle_typing(websocket, user_id, message, db)

                elif message_type == "ping":
                    # Heartbeat
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    })

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
                logger.error(f"Error handling message: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })

    except WebSocketDisconnect:
        logger.info(f"User {user_id} disconnected")
    finally:
        await connection_manager.disconnect(websocket)


async def handle_join_room(websocket: WebSocket, user_id: str, message: dict, db: AsyncSession):
    """Handle join_room message."""
    room_id = message.get("room_id")

    if not room_id:
        await websocket.send_json({
            "type": "error",
            "message": "room_id required"
        })
        return

    # Join the room
    await connection_manager.join_room(user_id, room_id)

    # Get room info (if it's a land chat)
    try:
        room_uuid = uuid.UUID(room_id)
        chat_session = await chat_service.get_or_create_land_chat(db, room_uuid)

        await websocket.send_json({
            "type": "joined_room",
            "room_id": room_id,
            "room_name": chat_session.name,
            "members": connection_manager.get_room_members(room_id),
            "timestamp": datetime.utcnow().isoformat()
        })

    except Exception as e:
        logger.error(f"Error joining room: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to join room: {str(e)}"
        })


async def handle_leave_room(websocket: WebSocket, user_id: str, message: dict, db: AsyncSession):
    """Handle leave_room message."""
    room_id = message.get("room_id")

    if not room_id:
        await websocket.send_json({
            "type": "error",
            "message": "room_id required"
        })
        return

    await connection_manager.leave_room(user_id, room_id)

    await websocket.send_json({
        "type": "left_room",
        "room_id": room_id,
        "timestamp": datetime.utcnow().isoformat()
    })


async def handle_send_message(websocket: WebSocket, user_id: str, message: dict, db: AsyncSession):
    """Handle send_message."""
    room_id = message.get("room_id")
    content = message.get("content")

    if not room_id or not content:
        await websocket.send_json({
            "type": "error",
            "message": "room_id and content required"
        })
        return

    try:
        # Save message to database
        room_uuid = uuid.UUID(room_id)
        user_uuid = uuid.UUID(user_id)

        db_message = await chat_service.send_message(
            db=db,
            session_id=room_uuid,
            sender_id=user_uuid,
            content=content,
            encrypt=True
        )

        # Get sender info
        result = await db.execute(
            select(User).where(User.user_id == user_uuid)
        )
        sender = result.scalar_one_or_none()

        # Broadcast to room
        broadcast_data = {
            "type": "message",
            "message_id": str(db_message.message_id),
            "room_id": room_id,
            "sender_id": user_id,
            "sender_username": sender.username if sender else "Unknown",
            "content": content,  # Send plaintext to clients (they handle E2EE)
            "timestamp": db_message.created_at.isoformat()
        }

        sent_count = await connection_manager.broadcast_to_room(
            broadcast_data,
            room_id
        )

        logger.info(f"Message broadcast to {sent_count} connections in room {room_id}")

    except Exception as e:
        logger.error(f"Error sending message: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to send message: {str(e)}"
        })


async def handle_update_location(websocket: WebSocket, user_id: str, message: dict, db: AsyncSession):
    """Handle update_location for proximity detection."""
    x = message.get("x")
    y = message.get("y")

    if x is None or y is None:
        await websocket.send_json({
            "type": "error",
            "message": "x and y coordinates required"
        })
        return

    # Update location in connection manager
    await connection_manager.update_user_location(user_id, x, y)

    # Get nearby users
    nearby_users = connection_manager.get_nearby_users(x, y, radius=5)

    await websocket.send_json({
        "type": "location_updated",
        "x": x,
        "y": y,
        "nearby_users": nearby_users,
        "timestamp": datetime.utcnow().isoformat()
    })


async def handle_typing(websocket: WebSocket, user_id: str, message: dict, db: AsyncSession):
    """Handle typing indicator."""
    room_id = message.get("room_id")
    is_typing = message.get("is_typing", True)

    if not room_id:
        return

    # Broadcast typing status to room
    await connection_manager.broadcast_to_room(
        {
            "type": "typing",
            "room_id": room_id,
            "user_id": user_id,
            "is_typing": is_typing,
            "timestamp": datetime.utcnow().isoformat()
        },
        room_id,
        exclude_user=user_id
    )


@router.get("/stats")
async def get_websocket_stats():
    """
    Get WebSocket connection statistics.

    Returns real-time stats about connections, rooms, and online users.
    """
    stats = connection_manager.get_stats()

    return {
        **stats,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/online-users")
async def get_online_users(
    db: AsyncSession = Depends(get_db)
):
    """
    Get list of currently online users.

    Returns user IDs and basic info for all online users.
    """
    online_user_ids = connection_manager.get_all_online_users()

    if not online_user_ids:
        return {"users": [], "count": 0}

    # Get user details
    user_uuids = [uuid.UUID(uid) for uid in online_user_ids]

    result = await db.execute(
        select(User).where(User.user_id.in_(user_uuids))
    )
    users = result.scalars().all()

    return {
        "users": [
            {
                "user_id": str(user.user_id),
                "username": user.username,
                "presence": connection_manager.get_user_presence(str(user.user_id))
            }
            for user in users
        ],
        "count": len(users)
    }
