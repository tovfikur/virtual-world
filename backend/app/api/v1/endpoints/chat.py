"""
Chat REST Endpoints
HTTP endpoints for chat history and management
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
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
from app.dependencies import get_current_user
from app.services.chat_service import chat_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


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
    db: AsyncSession = Depends(get_db)
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
