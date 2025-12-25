"""
Chat REST Endpoints
HTTP endpoints for chat history and management
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
import logging
import uuid
from datetime import datetime

from app.db.session import get_db
from app.models.chat import ChatSession
from app.models.chat import Message
from app.models.user import User
from app.models.land import Land
from app.dependencies import get_current_user
from app.services.chat_service import chat_service
from app.services.websocket_service import connection_manager
from app.models.admin_config import AdminConfig
from app.services.rate_limit_service import rate_limit_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


def _rate_limit_identifier(request: Request, current_user: Optional[dict]) -> str:
    if current_user and current_user.get("sub"):
        return str(current_user["sub"])
    if request.client:
        return request.client.host
    return "anonymous"


async def _enforce_chat_rate_limit(
    db: AsyncSession,
    request: Request,
    current_user: Optional[dict]
):
    cfg_res = await db.execute(select(AdminConfig).limit(1))
    config = cfg_res.scalar_one_or_none()
    limit = config.chat_messages_per_minute if config else None
    if not limit:
        return

    identifier = _rate_limit_identifier(request, current_user)
    result = await rate_limit_service.check(
        bucket="chat",
        identifier=identifier,
        limit=limit,
        window_seconds=60
    )
    if result and not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Chat rate limit exceeded",
            headers={
                "X-RateLimit-Limit": str(result.limit),
                "X-RateLimit-Remaining": str(result.remaining),
                "X-RateLimit-Reset": str(result.reset_epoch),
            },
        )


@router.get("/sessions")
async def get_user_chat_sessions(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all chat sessions for current user.

    Returns land-based and private chats user has access to.
    """
    try:
        user_uuid = uuid.UUID(current_user["sub"])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID"
        )

    sessions = await chat_service.get_user_chat_sessions(db, user_uuid)

    return {
        "sessions": [
            {
                "session_id": str(session.session_id),
                "name": session.name,
                "is_public": session.is_public,
                "land_id": str(session.land_id) if session.land_id else None,
                "message_count": session.message_count,
                "last_message_at": session.last_message_at.isoformat() if session.last_message_at else None,
                "created_at": session.created_at.isoformat()
            }
            for session in sessions
        ],
        "count": len(sessions)
    }


@router.get("/sessions/{session_id}/messages")
async def get_chat_history(
    session_id: str,
    limit: int = Query(50, ge=1, le=200),
    before_message_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get chat history for a session.

    Supports pagination via before_message_id parameter.
    Messages are decrypted before being returned.
    """
    try:
        session_uuid = uuid.UUID(session_id)
        before_uuid = uuid.UUID(before_message_id) if before_message_id else None
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID format"
        )

    # Verify session exists
    result = await db.execute(
        select(ChatSession).where(ChatSession.session_id == session_uuid)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )

    # Get messages
    messages = await chat_service.get_chat_history(
        db=db,
        session_id=session_uuid,
        limit=limit,
        before_message_id=before_uuid
    )

    # Get sender usernames
    sender_ids = list(set(str(msg.sender_id) for msg in messages))
    sender_uuids = [uuid.UUID(sid) for sid in sender_ids]

    result = await db.execute(
        select(User).where(User.user_id.in_(sender_uuids))
    )
    users = {str(u.user_id): u.username for u in result.scalars().all()}

    return {
        "session_id": session_id,
        "messages": [
            {
                "message_id": str(msg.message_id),
                "sender_id": str(msg.sender_id),
                "sender_username": users.get(str(msg.sender_id), "Unknown"),
                "content": msg.content_encrypted,  # Already decrypted by service
                "created_at": msg.created_at.isoformat(),
                "is_edited": msg.edited_at is not None
            }
            for msg in messages
        ],
        "count": len(messages),
        "has_more": len(messages) == limit
    }


@router.post("/sessions/{session_id}/messages")
async def send_chat_message(
    session_id: str,
    content: str = Query(..., min_length=1, max_length=2000),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None
):
    """
    Send a message to a chat session (REST endpoint).

    Note: For real-time chat, use WebSocket endpoint instead.
    This is useful for bots or scheduled messages.
    """
    try:
        session_uuid = uuid.UUID(session_id)
        user_uuid = uuid.UUID(current_user["sub"])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID format"
        )

    try:
        await _enforce_chat_rate_limit(db, request, current_user)

        message = await chat_service.send_message(
            db=db,
            session_id=session_uuid,
            sender_id=user_uuid,
            content=content,
            encrypt=True
        )

        return {
            "message_id": str(message.message_id),
            "session_id": str(message.session_id),
            "sender_id": str(message.sender_id),
            "content": content,
            "created_at": message.created_at.isoformat(),
            "message": "Message sent successfully"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


@router.get("/land/{land_id}/messages")
async def get_land_messages(
    land_id: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get message history for a land (by land_id).

    Returns all messages (both real-time and leave messages) for the land's chat session.
    """
    logger.info(f"=== GET /land/{land_id}/messages called ===")

    try:
        land_uuid = uuid.UUID(land_id)
        logger.info(f"Valid land UUID: {land_uuid}")
    except ValueError:
        logger.error(f"Invalid land ID format: {land_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid land ID"
        )

    try:
        user_uuid = uuid.UUID(current_user["sub"])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID"
        )

    try:
        land_result = await db.execute(select(Land).where(Land.land_id == land_uuid))
        land = land_result.scalar_one_or_none()
        if not land:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Land not found"
            )

        try:
            await chat_service.enforce_land_chat_access(
                db=db,
                land=land,
                user_id=user_uuid,
                require_write=False,
            )
        except PermissionError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            ) from exc

        # Get or create chat session for this land
        logger.info(f"Getting/creating chat session for land {land_uuid}")
        chat_session = await chat_service.get_or_create_land_chat(db, land_uuid)
        logger.info(f"Chat session ID: {chat_session.session_id}")

        # Get message history
        logger.info(f"Fetching message history (limit={limit})")
        messages = await chat_service.get_chat_history(
            db=db,
            session_id=chat_session.session_id,
            limit=limit
        )
        logger.info(f"Found {len(messages)} messages in database")

        # Get sender usernames
        sender_ids = list(set(str(msg.sender_id) for msg in messages))
        sender_uuids = [uuid.UUID(sid) for sid in sender_ids]

        result = await db.execute(
            select(User).where(User.user_id.in_(sender_uuids))
        )
        users = {str(u.user_id): u.username for u in result.scalars().all()}

        response_messages = [
            {
                "message_id": str(msg.message_id),
                "sender_id": str(msg.sender_id),
                "sender_username": users.get(str(msg.sender_id), "Unknown"),
                "content": msg.content_encrypted,  # Already decrypted by service
                "created_at": msg.created_at.isoformat(),
                "is_leave_message": msg.is_leave_message == "True",
                "read_by_owner": msg.read_by_owner == "True"
            }
            for msg in messages
        ]

        logger.info(f"✓ Returning {len(response_messages)} messages")
        logger.info(f"Messages: {[m['content'][:20] + '...' for m in response_messages]}")

        return {
            "land_id": land_id,
            "session_id": str(chat_session.session_id),
            "messages": response_messages,
            "count": len(response_messages)
        }

    except ValueError as e:
        logger.error(f"Error getting messages: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/land/{land_id}/participants")
async def get_land_chat_participants(
    land_id: str,
    radius: int = Query(5, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """
    Get users who can participate in land chat (proximity-based).

    Returns users within specified radius of the land.
    """
    try:
        land_uuid = uuid.UUID(land_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid land ID"
        )

    try:
        participants = await chat_service.get_land_chat_participants(
            db=db,
            land_id=land_uuid,
            radius=radius
        )

        return {
            "land_id": land_id,
            "radius": radius,
            "participants": participants,
            "count": len(participants)
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/land/{land_id}/session")
async def create_land_chat_session(
    land_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get or create a chat session for a land.

    Land owners can create chat sessions for their land.
    """
    try:
        land_uuid = uuid.UUID(land_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid land ID"
        )

    try:
        session = await chat_service.get_or_create_land_chat(
            db=db,
            land_id=land_uuid
        )

        return {
            "session_id": str(session.session_id),
            "land_id": str(session.land_id),
            "name": session.name,
            "is_public": session.is_public,
            "created_at": session.created_at.isoformat(),
            "message": "Chat session ready"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.delete("/sessions/{session_id}/messages/{message_id}")
async def delete_message(
    session_id: str,
    message_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a message (soft delete - mark as deleted).

    Only message sender or session owner can delete.
    """
    try:
        message_uuid = uuid.UUID(message_id)
        user_uuid = uuid.UUID(current_user["sub"])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID format"
        )

    # Get message
    result = await db.execute(
        select(Message).where(Message.message_id == message_uuid)
    )
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )

    # Check permission (only sender can delete)
    if message.sender_id != user_uuid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own messages"
        )

    # Soft delete (mark as deleted)
    message.deleted_at = datetime.utcnow()
    message.content_encrypted = "[deleted]"

    await db.commit()

    return {
        "message_id": message_id,
        "status": "deleted",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/stats")
async def get_chat_stats(
    db: AsyncSession = Depends(get_db)
):
    """
    Get chat statistics.

    Returns total sessions, messages, and activity stats.
    """
    from sqlalchemy import func

    # Count sessions
    sessions_result = await db.execute(
        select(func.count(ChatSession.session_id))
    )
    total_sessions = sessions_result.scalar()

    # Count messages
    messages_result = await db.execute(
        select(func.count(Message.message_id))
    )
    total_messages = messages_result.scalar()

    # Count public sessions
    public_result = await db.execute(
        select(func.count(ChatSession.session_id)).where(
            ChatSession.is_public == True
        )
    )
    public_sessions = public_result.scalar()

    return {
        "total_sessions": total_sessions,
        "public_sessions": public_sessions,
        "private_sessions": total_sessions - public_sessions,
        "total_messages": total_messages,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/unread-messages")
async def get_unread_messages(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get leave-message indicator data scoped to the current user.

    Each record now includes unread/read counts for owned lands plus
    participation metadata (received/mine/others) for squares where the user
    has left messages.
    """
    try:
        user_uuid = uuid.UUID(current_user["sub"])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID"
        )

    message_counts = await chat_service.get_unread_messages_by_land(db, user_uuid)

    # Calculate total unread
    total_unread = sum(counts.get("unread", 0) for counts in message_counts.values())

    return {
        "messages_by_land": message_counts,
        "total_unread": total_unread,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/sessions/{session_id}/mark-read")
async def mark_session_messages_read(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Mark all unread leave messages in a session as read.

    Only land owner can mark messages as read.
    """
    try:
        session_uuid = uuid.UUID(session_id)
        user_uuid = uuid.UUID(current_user["sub"])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID format"
        )

    try:
        count = await chat_service.mark_messages_as_read(db, session_uuid, user_uuid)

        return {
            "session_id": session_id,
            "messages_marked_read": count,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error marking messages as read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark messages as read"
        )


@router.delete("/land/{land_id}/messages")
async def clean_land_messages(
    land_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete all messages for a land (clean the square).

    Permission rules:
    - If land is owned: only owner can clean
    - If land is unclaimed: anyone can clean
    """
    try:
        land_uuid = uuid.UUID(land_id)
        user_uuid = uuid.UUID(current_user["sub"])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID format"
        )

    try:
        # Get land info
        from app.models.land import Land
        result = await db.execute(
            select(Land).where(Land.land_id == land_uuid)
        )
        land = result.scalar_one_or_none()

        if not land:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Land not found"
            )

        # Check permission
        if land.owner_id:
            # Land is owned - only owner can clean
            if land.owner_id != user_uuid:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the land owner can clean messages on owned land"
                )
        # If land is unclaimed (owner_id is None), anyone can clean

        # Get chat session for this land
        result = await db.execute(
            select(ChatSession).where(ChatSession.land_id == land_uuid)
        )
        chat_session = result.scalar_one_or_none()

        if not chat_session:
            return {
                "land_id": land_id,
                "messages_deleted": 0,
                "message": "No chat session found for this land"
            }

        # Delete all messages in this session (soft delete)
        result = await db.execute(
            select(Message).where(
                Message.session_id == chat_session.session_id
            )
        )
        messages = result.scalars().all()

        deleted_count = 0
        for msg in messages:
            msg.deleted_at = datetime.utcnow()
            deleted_count += 1

        # Update chat session message count
        chat_session.message_count = 0
        chat_session.last_message_at = None

        await db.commit()

        logger.info(f"Cleaned {deleted_count} messages from land {land_id} by user {user_uuid}")

        # Broadcast messages_cleaned event to all users in this land's room
        room_id = f"land_{land.x}_{land.y}"
        await connection_manager.broadcast_to_room(
            {
                "type": "messages_cleaned",
                "land_id": str(land_id),
                "room_id": room_id,
                "deleted_count": deleted_count,
                "timestamp": datetime.utcnow().isoformat()
            },
            room_id
        )
        logger.info(f"Broadcasted messages_cleaned event to room {room_id}")

        return {
            "land_id": land_id,
            "messages_deleted": deleted_count,
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"Successfully cleaned {deleted_count} messages"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cleaning land messages: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clean messages"
        )
