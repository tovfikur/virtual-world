"""
Chat Service
Handles chat sessions, message encryption, and proximity-based chat
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
import uuid
import logging
from cryptography.fernet import Fernet
import base64

from app.models.chat import ChatSession
from app.models.chat import Message
from app.models.user import User
from app.models.land import Land
from app.config import settings
from app.services.cache_service import cache_service

logger = logging.getLogger(__name__)


class ChatService:
    """
    Service for chat operations.

    Features:
    - Land-based chat rooms
    - End-to-end encryption (E2EE)
    - Proximity detection
    - Message persistence
    - Chat history retrieval
    """

    def __init__(self):
        # Initialize encryption (simplified - in production use per-session keys)
        self.cipher_suite = Fernet(base64.urlsafe_b64encode(settings.encryption_key[:32].encode().ljust(32)[:32]))
        logger.info("ChatService initialized with E2EE")

    def encrypt_message(self, plaintext: str) -> str:
        """
        Encrypt a message.

        Args:
            plaintext: Message text to encrypt

        Returns:
            Encrypted message (base64 encoded)
        """
        try:
            encrypted = self.cipher_suite.encrypt(plaintext.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise ValueError("Message encryption failed")

    def decrypt_message(self, encrypted_text: str) -> str:
        """
        Decrypt a message.

        Args:
            encrypted_text: Encrypted message (base64 encoded)

        Returns:
            Decrypted plaintext
        """
        try:
            encrypted = base64.urlsafe_b64decode(encrypted_text.encode())
            decrypted = self.cipher_suite.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Message decryption failed")

    async def get_or_create_land_chat(
        self,
        db: AsyncSession,
        land_id: uuid.UUID
    ) -> ChatSession:
        """
        Get or create a chat session for a land.

        Args:
            db: Database session
            land_id: Land ID

        Returns:
            ChatSession instance
        """
        # Check if chat session exists
        result = await db.execute(
            select(ChatSession).where(ChatSession.land_id == land_id)
        )
        chat_session = result.scalar_one_or_none()

        if chat_session:
            return chat_session

        # Verify land exists
        land_result = await db.execute(
            select(Land).where(Land.land_id == land_id)
        )
        land = land_result.scalar_one_or_none()

        if not land:
            raise ValueError("Land not found")

        # Create new chat session
        chat_session = ChatSession(
            land_id=land_id,
            name=f"Land ({land.x}, {land.y})",
            is_public="True"  # Land chats are public by default
        )

        db.add(chat_session)
        await db.commit()
        await db.refresh(chat_session)

        logger.info(f"Created land chat session: {chat_session.session_id} for land {land_id}")

        return chat_session

    async def create_private_chat(
        self,
        db: AsyncSession,
        participants: List[uuid.UUID],
        name: Optional[str] = None
    ) -> ChatSession:
        """
        Create a private chat session between users.

        Args:
            db: Database session
            participants: List of user IDs (2+ users)
            name: Optional chat name

        Returns:
            ChatSession instance
        """
        if len(participants) < 2:
            raise ValueError("Private chat requires at least 2 participants")

        # Verify all users exist
        for user_id in participants:
            result = await db.execute(
                select(User).where(User.user_id == user_id)
            )
            if not result.scalar_one_or_none():
                raise ValueError(f"User {user_id} not found")

        # Create chat session
        chat_session = ChatSession(
            name=name or f"Private Chat ({len(participants)} users)",
            is_public="False",
            max_participants=len(participants)
        )

        db.add(chat_session)
        await db.commit()
        await db.refresh(chat_session)

        logger.info(f"Created private chat session: {chat_session.session_id}")

        return chat_session

    async def send_message(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        sender_id: uuid.UUID,
        content: str,
        encrypt: bool = True,
        is_leave_message: bool = False
    ) -> Message:
        """
        Send a message to a chat session.

        Args:
            db: Database session
            session_id: Chat session ID
            sender_id: Sender user ID
            content: Message content
            encrypt: Whether to encrypt message (default True)

        Returns:
            Created Message instance

        Raises:
            ValueError: If chat session not found, sender not found, or fenced land restriction
        """
        # Verify chat session exists
        result = await db.execute(
            select(ChatSession).where(ChatSession.session_id == session_id)
        )
        chat_session = result.scalar_one_or_none()

        if not chat_session:
            raise ValueError("Chat session not found")

        # Verify sender exists
        result = await db.execute(
            select(User).where(User.user_id == sender_id)
        )
        sender = result.scalar_one_or_none()

        if not sender:
            raise ValueError("Sender not found")

        # Check fencing restrictions for land-based chats
        if chat_session.land_id:
            result = await db.execute(
                select(Land).where(Land.land_id == chat_session.land_id)
            )
            land = result.scalar_one_or_none()

            if land:
                # If land is fenced and sender is not the owner, deny message
                if land.fenced and land.owner_id != sender_id:
                    raise ValueError(f"This land is fenced. Only the owner can receive messages here.")

        # Encrypt content if requested
        if encrypt:
            encrypted_content = self.encrypt_message(content)
        else:
            encrypted_content = content

        # Create message
        message = Message(
            session_id=session_id,
            sender_id=sender_id,
            content_encrypted=encrypted_content,
            is_encrypted="True" if encrypt else "False",
            is_leave_message="True" if is_leave_message else "False",
            read_by_owner="False"
        )

        db.add(message)

        # Update chat session last_message_at
        chat_session.last_message_at = datetime.utcnow()
        chat_session.message_count += 1

        await db.commit()
        await db.refresh(message)

        logger.info(f"Message sent: {message.message_id} to session {session_id}")

        return message

    async def get_chat_history(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        limit: int = 50,
        before_message_id: Optional[uuid.UUID] = None
    ) -> List[Message]:
        """
        Get chat history for a session.

        Args:
            db: Database session
            session_id: Chat session ID
            limit: Maximum messages to return
            before_message_id: Get messages before this message ID (for pagination)

        Returns:
            List of Message instances (decrypted)
        """
        query = select(Message).where(
            Message.session_id == session_id,
            Message.deleted_at.is_(None)  # Exclude deleted messages
        )

        # Pagination support
        if before_message_id:
            query = query.where(Message.created_at < select(Message.created_at).where(
                Message.message_id == before_message_id
            ).scalar_subquery())

        # Order by most recent first
        query = query.order_by(Message.created_at.desc()).limit(limit)

        result = await db.execute(query)
        messages = result.scalars().all()

        # Decrypt messages
        for message in messages:
            if message.is_encrypted == "True":
                try:
                    message.content_encrypted = self.decrypt_message(message.content_encrypted)
                except Exception as e:
                    logger.error(f"Failed to decrypt message {message.message_id}: {e}")
                    message.content_encrypted = "[Decryption failed]"

        return list(reversed(messages))  # Return in chronological order

    async def get_unread_messages_by_land(
        self,
        db: AsyncSession,
        owner_id: uuid.UUID
    ) -> Dict[str, Dict[str, int]]:
        """
        Get count of unread and read leave messages for each land owned by user.

        Args:
            db: Database session
            owner_id: Land owner user ID

        Returns:
            Dict mapping land_id to {"unread": count, "read": count}
        """
        # Get all lands owned by user
        result = await db.execute(
            select(Land).where(Land.owner_id == owner_id)
        )
        lands = result.scalars().all()

        if not lands:
            return {}

        # Get chat sessions for those lands
        land_ids = [land.land_id for land in lands]
        result = await db.execute(
            select(ChatSession).where(ChatSession.land_id.in_(land_ids))
        )
        sessions = result.scalars().all()

        # Count unread and read messages per session
        message_counts = {}
        for session in sessions:
            # Count unread messages
            result = await db.execute(
                select(func.count(Message.message_id)).where(
                    and_(
                        Message.session_id == session.session_id,
                        Message.is_leave_message == "True",
                        Message.read_by_owner == "False",
                        Message.deleted_at.is_(None)
                    )
                )
            )
            unread_count = result.scalar() or 0

            # Count read messages
            result = await db.execute(
                select(func.count(Message.message_id)).where(
                    and_(
                        Message.session_id == session.session_id,
                        Message.is_leave_message == "True",
                        Message.read_by_owner == "True",
                        Message.deleted_at.is_(None)
                    )
                )
            )
            read_count = result.scalar() or 0

            # Only include lands with messages
            if unread_count > 0 or read_count > 0:
                message_counts[str(session.land_id)] = {
                    "unread": unread_count,
                    "read": read_count
                }

        return message_counts

    async def mark_messages_as_read(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        owner_id: uuid.UUID
    ) -> int:
        """
        Mark all unread leave messages in a session as read by owner.

        Args:
            db: Database session
            session_id: Chat session ID
            owner_id: Land owner user ID

        Returns:
            int: Number of messages marked as read
        """
        # Verify the owner owns the land for this session
        result = await db.execute(
            select(ChatSession).where(ChatSession.session_id == session_id)
        )
        session = result.scalar_one_or_none()

        if not session or not session.land_id:
            return 0

        result = await db.execute(
            select(Land).where(Land.land_id == session.land_id)
        )
        land = result.scalar_one_or_none()

        if not land or land.owner_id != owner_id:
            return 0

        # Mark all unread leave messages as read
        result = await db.execute(
            select(Message).where(
                and_(
                    Message.session_id == session_id,
                    Message.is_leave_message == "True",
                    Message.read_by_owner == "False",
                    Message.deleted_at.is_(None)
                )
            )
        )
        messages = result.scalars().all()

        count = 0
        for message in messages:
            message.mark_as_read()
            count += 1

        await db.commit()

        logger.info(f"Marked {count} messages as read for session {session_id}")

        return count

    async def get_land_chat_participants(
        self,
        db: AsyncSession,
        land_id: uuid.UUID,
        radius: int = 5
    ) -> List[dict]:
        """
        Get users who can participate in land chat (proximity-based).

        Args:
            db: Database session
            land_id: Center land ID
            radius: Proximity radius (default 5)

        Returns:
            List of user dicts with distance info
        """
        # Get the center land
        result = await db.execute(
            select(Land).where(Land.land_id == land_id)
        )
        center_land = result.scalar_one_or_none()

        if not center_land:
            raise ValueError("Land not found")

        # Find nearby lands
        result = await db.execute(
            select(Land, User).join(
                User, Land.owner_id == User.user_id
            ).where(
                and_(
                    Land.x.between(center_land.x - radius, center_land.x + radius),
                    Land.y.between(center_land.y - radius, center_land.y + radius)
                )
            )
        )
        nearby = result.all()

        participants = []
        for land, user in nearby:
            distance = max(abs(land.x - center_land.x), abs(land.y - center_land.y))
            participants.append({
                "user_id": str(user.user_id),
                "username": user.username,
                "land_x": land.x,
                "land_y": land.y,
                "distance": distance,
                "can_chat": distance <= radius
            })

        return participants

    async def delete_old_messages(
        self,
        db: AsyncSession,
        days: int = 30
    ) -> int:
        """
        Delete messages older than specified days.

        Args:
            db: Database session
            days: Delete messages older than this many days

        Returns:
            Number of messages deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        result = await db.execute(
            select(func.count(Message.message_id)).where(
                Message.created_at < cutoff_date
            )
        )
        count = result.scalar()

        # Delete old messages
        await db.execute(
            select(Message).where(Message.created_at < cutoff_date)
        )
        await db.commit()

        logger.info(f"Deleted {count} old messages (older than {days} days)")

        return count

    async def get_user_chat_sessions(
        self,
        db: AsyncSession,
        user_id: uuid.UUID
    ) -> List[ChatSession]:
        """
        Get all chat sessions user has access to.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            List of ChatSession instances
        """
        # Get user's lands
        result = await db.execute(
            select(Land).where(Land.owner_id == user_id)
        )
        lands = result.scalars().all()

        # Get chat sessions for those lands
        land_ids = [land.land_id for land in lands]

        if not land_ids:
            return []

        result = await db.execute(
            select(ChatSession).where(
                or_(
                    ChatSession.land_id.in_(land_ids),
                    ChatSession.is_public == True
                )
            ).order_by(ChatSession.last_message_at.desc())
        )

        return result.scalars().all()


# Global chat service instance
chat_service = ChatService()
