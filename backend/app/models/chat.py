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
        name: Display name for the chat session
        is_public: Whether the chat is public or private
        max_participants: Maximum number of participants
        message_count: Total number of messages
        last_message_at: Timestamp of last message
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
        nullable=True,
        index=True
    )

    # Session Data
    name = Column(
        String(255),
        nullable=True
    )
    is_public = Column(
        String,  # Using String for compatibility, True/False stored as text
        default="True",
        nullable=False
    )
    max_participants = Column(
        Integer,
        nullable=True
    )
    message_count = Column(
        Integer,
        default=0,
        nullable=False
    )
    last_message_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relationships
    land = relationship("Land", back_populates="chat_sessions")
    messages = relationship(
        "Message",
        back_populates="session",
        cascade="all, delete-orphan"
    )

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
            "land_id": str(self.land_id) if self.land_id else None,
            "name": self.name,
            "is_public": self.is_public,
            "message_count": self.message_count,
            "last_message_at": self.last_message_at.isoformat() if self.last_message_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class MessageType(str, PyEnum):
    """Message type enumeration."""
    TEXT = "text"
    IMAGE = "image"
    ATTACHMENT = "attachment"


class Message(BaseModel):
    """
    Chat message with encryption support.

    Messages can be encrypted using E2EE or stored as plaintext.
    Supports read tracking for leave messages.

    Attributes:
        message_id: Unique UUID identifier
        session_id: Reference to chat session
        sender_id: Reference to user who sent message
        content_encrypted: Message content (encrypted or plaintext)
        is_encrypted: Whether content is encrypted
        is_leave_message: Whether this is a message left for offline owner
        read_by_owner: Whether land owner has read this message
        read_at: Timestamp when message was read by owner
        deleted_at: Soft delete timestamp
    """

    __tablename__ = "messages"

    __table_args__ = (
        Index("idx_messages_session", "session_id", "created_at"),
        Index("idx_messages_sender", "sender_id"),
        Index("idx_messages_unread", "session_id", "read_by_owner"),
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

    # Message Content
    content_encrypted = Column(
        String,
        nullable=False
    )
    is_encrypted = Column(
        String,  # Using String for compatibility, stored as "True"/"False"
        default="True",
        nullable=False
    )

    # Leave Message tracking
    is_leave_message = Column(
        String,  # Using String for compatibility
        default="False",
        nullable=False
    )
    read_by_owner = Column(
        String,  # Using String for compatibility
        default="False",
        nullable=False
    )
    read_at = Column(
        DateTime(timezone=True),
        nullable=True
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

    def mark_as_read(self) -> None:
        """Mark message as read by owner."""
        self.read_by_owner = "True"
        self.read_at = datetime.utcnow()

    @property
    def is_deleted(self) -> bool:
        """Check if message is deleted."""
        return self.deleted_at is not None

    @property
    def is_read(self) -> bool:
        """Check if message has been read by owner."""
        return self.read_by_owner == "True"

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
            "content": self.content_encrypted,
            "is_encrypted": self.is_encrypted == "True",
            "is_leave_message": self.is_leave_message == "True",
            "read_by_owner": self.read_by_owner == "True",
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "deleted": self.is_deleted
        }
