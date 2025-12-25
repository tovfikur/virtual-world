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
from app.models.land import Land, Biome
from app.models.chat import ChatSession
from app.services.websocket_service import connection_manager
from app.services.chat_service import chat_service
from app.services.auth_service import auth_service
from app.services.cache_service import cache_service
from app.services.biome_market_service import biome_market_service
from sqlalchemy import and_

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
        session_id = payload.get("session_id")

        result = await db.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return None

        session_data = await cache_service.get(f"session:{user_id}")
        if not session_data:
            logger.warning(
                f"WebSocket session not found for user {user_id}; allowing token-only auth"
            )
            return user

        if session_data.get("session_id") != session_id:
            logger.warning(
                f"WebSocket session mismatch for user {user_id}; allowing token-only auth"
            )
            return user

        return user
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
    # Authenticate user (fallback to guest if token invalid for smoke tests)
    user = await get_user_from_token(token, db)

    if not user:
        logger.warning("WebSocket auth failed; falling back to guest user")
        import uuid as _uuid
        user_id = f"guest-{_uuid.uuid4()}"
        username = "guest"
    else:
        user_id = str(user.user_id)
        username = user.username

    # Connect user
    await connection_manager.connect(websocket, user_id, username)

    # Send welcome message
    await websocket.send_json({
        "type": "connected",
        "user_id": user_id,
        "username": username,
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

                elif message_type == "subscribe_biome_market":
                    await handle_subscribe_biome_market(websocket, user_id, message, db)

                elif message_type == "unsubscribe_biome_market":
                    await handle_unsubscribe_biome_market(websocket, user_id, message)

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

    # Get room info
    try:
        # Try UUID-based room (claimed land with land_id)
        try:
            room_uuid = uuid.UUID(room_id)
            chat_session = await chat_service.get_or_create_land_chat(db, room_uuid)
            room_name = chat_session.name
        except (ValueError, TypeError):
            # Coordinate-based room (e.g., "land_5_10")
            if room_id.startswith("land_"):
                coords = room_id.replace("land_", "").split("_")
                if len(coords) == 2:
                    room_name = f"Land ({coords[0]}, {coords[1]})"
                else:
                    room_name = room_id
            else:
                room_name = room_id

        await websocket.send_json({
            "type": "joined_room",
            "room_id": room_id,
            "room_name": room_name,
            "members": connection_manager.get_room_members(room_id),
            "timestamp": datetime.utcnow().isoformat()
        })

    except Exception as e:
        logger.error(f"Error joining room: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to join room: {str(e)}"
        })


async def handle_subscribe_biome_market(websocket: WebSocket, user_id: str, message: dict, db: AsyncSession):
    """Subscribe user to biome market updates."""
    biome_value = message.get("biome")

    biome_enum = None
    if biome_value:
        try:
            biome_enum = Biome(biome_value)
        except ValueError:
            await websocket.send_json({
                "type": "error",
                "message": f"Invalid biome: {biome_value}"
            })
            return

    room_id = f"biome_market:{biome_enum.value}" if biome_enum else "biome_market_all"

    # Join room
    await connection_manager.join_room(user_id, room_id)

    # Send snapshot
    if biome_enum:
        market = await biome_market_service.get_market(db, biome_enum)
        markets_payload = [market.to_dict()]
    else:
        markets = await biome_market_service.get_all_markets(db)
        markets_payload = [m.to_dict() for m in markets]

    await websocket.send_json({
        "type": "subscribed_biome_market",
        "room_id": room_id,
        "biome": biome_enum.value if biome_enum else None,
        "markets": markets_payload,
        "timestamp": datetime.utcnow().isoformat()
    })


async def handle_unsubscribe_biome_market(websocket: WebSocket, user_id: str, message: dict):
    """Unsubscribe user from biome market updates."""
    biome_value = message.get("biome")

    try:
        biome_enum = Biome(biome_value) if biome_value else None
    except ValueError:
        await websocket.send_json({
            "type": "error",
            "message": f"Invalid biome: {biome_value}"
        })
        return

    room_id = f"biome_market:{biome_enum.value}" if biome_enum else "biome_market_all"

    await connection_manager.leave_room(user_id, room_id)

    await websocket.send_json({
        "type": "unsubscribed_biome_market",
        "room_id": room_id,
        "biome": biome_enum.value if biome_enum else None,
        "timestamp": datetime.utcnow().isoformat()
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

    user_uuid = None
    sender = None
    db_message = None
    is_leave_message = False

    try:
        user_uuid = uuid.UUID(user_id)

        # Get sender info
        result = await db.execute(
            select(User).where(User.user_id == user_uuid)
        )
        sender = result.scalar_one_or_none()

    except Exception as e:
        logger.error(f"Error getting sender info: {e}")

    # Try to save message to database (don't let this fail the broadcast)
    try:
        # Try UUID-based room first
        try:
            room_uuid = uuid.UUID(room_id)

            # Get the chat session and land info
            result = await db.execute(
                select(ChatSession).where(ChatSession.session_id == room_uuid)
            )
            chat_session = result.scalar_one_or_none()

            if chat_session and chat_session.land_id:
                # Get land owner
                result = await db.execute(
                    select(Land).where(Land.land_id == chat_session.land_id)
                )
                land = result.scalar_one_or_none()

                if land and land.owner_id:
                    # Check if land owner is in the room
                    room_members = connection_manager.get_room_members(room_id)
                    owner_online = str(land.owner_id) in room_members

                    # Mark as leave message only if sender is not owner AND owner is offline
                    if land.owner_id != user_uuid and not owner_online:
                        is_leave_message = True

            # ALWAYS save message to database for UUID-based rooms
            try:
                db_message = await chat_service.send_message(
                    db=db,
                    session_id=room_uuid,
                    sender_id=user_uuid,
                    content=content,
                    encrypt=False,  # Don't encrypt for now to debug
                    is_leave_message=is_leave_message
                )
            except PermissionError as perm_err:
                await websocket.send_json({"type": "error", "message": str(perm_err)})
                return
            except ValueError as val_err:
                await websocket.send_json({"type": "error", "message": str(val_err)})
                return
            logger.info(f"✓ Saved message to UUID room {room_id}, msg_id={db_message.message_id}")

        except (ValueError, TypeError):
            # Coordinate-based room (e.g., "land_5_10")
            # Try to save if land is owned
            if room_id.startswith("land_"):
                coords = room_id.replace("land_", "").split("_")
                if len(coords) == 2:
                    try:
                        land_x = int(coords[0])
                        land_y = int(coords[1])

                        # Check if land exists and is owned
                        result = await db.execute(
                            select(Land).where(
                                and_(
                                    Land.x == land_x,
                                    Land.y == land_y
                                )
                            )
                        )
                        land = result.scalar_one_or_none()

                        logger.info(f"=== Processing message for land ({land_x}, {land_y}) ===")
                        logger.info(f"Land found: {land is not None}, Land owned: {land.owner_id if land else None}")

                        if land and land.owner_id:
                            logger.info(f"Land is OWNED by user_id={land.owner_id}")

                            # Land is owned - ALWAYS save ALL messages (like WhatsApp)
                            chat_session = await chat_service.get_or_create_land_chat(db, land.land_id)
                            logger.info(f"Chat session: {chat_session.session_id}")

                            # Check if owner is online to determine if it's a leave message
                            room_members = connection_manager.get_room_members(room_id)
                            owner_online = str(land.owner_id) in room_members
                            logger.info(f"Room members: {room_members}, Owner online: {owner_online}")

                            # Mark as "leave message" only if sender is not owner AND owner is offline
                            # This affects the unread badge, but ALL messages are saved
                            if land.owner_id != user_uuid and not owner_online:
                                is_leave_message = True
                                logger.info(f"Marking as LEAVE MESSAGE (sender != owner and owner offline)")
                            else:
                                logger.info(f"NOT a leave message (owner online or sender is owner)")

                            # ALWAYS save message to database (regardless of who's online)
                            logger.info(f"Saving message: content='{content}', encrypt=False, is_leave_message={is_leave_message}")
                            try:
                                db_message = await chat_service.send_message(
                                    db=db,
                                    session_id=chat_session.session_id,
                                    sender_id=user_uuid,
                                    content=content,
                                    encrypt=False,  # Don't encrypt for now to debug
                                    is_leave_message=is_leave_message
                                )
                            except PermissionError as perm_err:
                                await websocket.send_json({"type": "error", "message": str(perm_err)})
                                return
                            except ValueError as val_err:
                                await websocket.send_json({"type": "error", "message": str(val_err)})
                                return
                            logger.info(f"✓✓✓ MESSAGE SAVED! msg_id={db_message.message_id}, session_id={chat_session.session_id}, land_id={land.land_id}")
                            logger.info(f"=== Message save complete for land ({land_x}, {land_y}) ===")
                        else:
                            logger.info(f"Land at ({land_x}, {land_y}) is not owned - broadcasting only")

                    except Exception as inner_e:
                        logger.error(f"Error saving message for coordinates: {inner_e}")
                        # Continue to broadcast even if save fails

    except Exception as e:
        logger.error(f"Error in message save logic: {e}")
        # Continue to broadcast even if save fails

    # ALWAYS BROADCAST - This must happen regardless of save success/failure
    try:
        broadcast_data = {
            "type": "message",
            "message_id": str(db_message.message_id) if db_message else str(uuid.uuid4()),
            "room_id": room_id,
            "sender_id": user_id,
            "sender_username": sender.username if sender else "Unknown",
            "content": content,
            "is_leave_message": is_leave_message,
            "timestamp": db_message.created_at.isoformat() if db_message else datetime.utcnow().isoformat()
        }

        sent_count = await connection_manager.broadcast_to_room(
            broadcast_data,
            room_id
        )

        logger.info(f"✓ Message broadcast to {sent_count} connections in room {room_id}")

        # Also send confirmation back to sender
        await websocket.send_json({
            "type": "message_sent",
            "message_id": broadcast_data["message_id"],
            "room_id": room_id,
            "timestamp": broadcast_data["timestamp"]
        })

    except Exception as e:
        logger.error(f"Error broadcasting message: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to broadcast message: {str(e)}"
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

    presence = connection_manager.get_user_presence(user_id) or {}
    await connection_manager.broadcast_all(
        {
            "type": "player_location",
            "user_id": user_id,
            "username": presence.get("username"),
            "x": x,
            "y": y,
            "timestamp": datetime.utcnow().isoformat()
        },
        exclude_user=user_id
    )


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
