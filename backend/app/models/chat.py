"""
Chat models
ChatSession and Message for land-based proximity chat
"""

from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Index, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from app.db.base import BaseModel


class ChatSession(BaseModel):
    """
    Chat session for land-based group conversations.

    Each land can have one active chat session where users
    automatically join when entering the land area.

    Attributes:
        session_id: Unique UUID identifier
        land_id: Reference to land (unique - one session per land)
        status: Session status (active/archived/deleted)
        participant_count: Number of users in session
    """

    __tablename__ = "chat_sessions"

    # Primary Key
    session_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )

    # Foreign Key
    land_id = Column(
        UUID(as_uuid=True),
        ForeignKey("lands.land_id"),
        unique=True,  # One session per land
        nullable=False,
        index=True
    )

    # Session Data
    status = Column(
        String(20),
        default="active",
        nullable=False
    )
    participant_count = Column(
        Integer,
        default=0,
        nullable=False
    )

    # Relationships
    land = relationship("Land", back_populates="chat_sessions")
    messages = relationship(
        "Message",
        back_populates="session",
        cascade="all, delete-orphan"
    )

    def add_participant(self) -> None:
        """Increment participant count."""
        self.participant_count += 1

    def remove_participant(self) -> None:
        """Decrement participant count."""
        if self.participant_count > 0:
            self.participant_count -= 1

    def archive(self) -> None:
        """Archive the chat session."""
        self.status = "archived"

    def __repr__(self) -> str:
        """String representation of ChatSession."""
        return f"<ChatSession {self.session_id} - Land {self.land_id}>"

    def to_dict(self) -> dict:
        """
        Convert session to dictionary for API responses.

        Returns:
            dict: Session data dictionary
        """
        return {
            "session_id": str(self.session_id),
            "land_id": str(self.land_id),
            "status": self.status,
            "participant_count": self.participant_count,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class MessageType(str, PyEnum):
    """Message type enumeration."""
    TEXT = "text"
    IMAGE = "image"
    ATTACHMENT = "attachment"


class Message(BaseModel):
    """
    Encrypted chat message.

    Messages are encrypted client-side using E2EE (AES-256-GCM).
    Server stores encrypted payload and initialization vector.

    Attributes:
        message_id: Unique UUID identifier
        session_id: Reference to chat session
        sender_id: Reference to user who sent message
        encrypted_payload: Encrypted message content (AES-256-GCM)
        encryption_version: Version of encryption scheme
        iv: Initialization vector for AES-GCM
        message_type: Type of message (text/image/attachment)
        deleted_at: Soft delete timestamp
    """

    __tablename__ = "messages"

    __table_args__ = (
        Index("idx_messages_session", "session_id", "created_at"),
        Index("idx_messages_sender", "sender_id"),
    )

    # Primary Key
    message_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )

    # Foreign Keys
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.session_id"),
        nullable=False,
        index=True
    )
    sender_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=False,
        index=True
    )

    # Message Content (encrypted)
    encrypted_payload = Column(
        String,
        nullable=False
    )
    encryption_version = Column(
        String(10),
        default="1.0",
        nullable=False
    )
    iv = Column(
        String(255),
        nullable=False
    )

    # Message Type
    message_type = Column(
        SQLEnum(MessageType),
        default=MessageType.TEXT,
        nullable=False
    )

    # Soft Delete
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relationships
    session = relationship("ChatSession", back_populates="messages")
    sender = relationship("User", back_populates="messages")

    def soft_delete(self) -> None:
        """Soft delete the message."""
        self.deleted_at = datetime.utcnow()

    @property
    def is_deleted(self) -> bool:
        """Check if message is deleted."""
        return self.deleted_at is not None

    def __repr__(self) -> str:
        """String representation of Message."""
        return f"<Message {self.message_id}>"

    def to_dict(self) -> dict:
        """
        Convert message to dictionary for API responses.

        Returns:
            dict: Message data dictionary
        """
        return {
            "message_id": str(self.message_id),
            "session_id": str(self.session_id),
            "sender_id": str(self.sender_id),
            "encrypted_payload": self.encrypted_payload,
            "encryption_version": self.encryption_version,
            "iv": self.iv,
            "message_type": self.message_type.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "deleted": self.is_deleted
        }
