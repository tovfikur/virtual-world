"""
User Session model
Tracks active sessions for users to enforce single-session-per-user policy
"""

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from app.db.base import BaseModel


class UserSession(BaseModel):
    """
    UserSession model for tracking active user sessions.

    Enforces single session per authenticated user:
    - Logged-in users: Only 1 active session allowed
    - Anonymous users: Unlimited sessions allowed (tracked separately)

    Attributes:
        session_id: Unique UUID for this session
        user_id: User UUID (null for anonymous users)
        session_token: JWT token identifier (session_id claim)
        device_fingerprint: Hash of user-agent + IP for device identification
        user_agent: Browser/app identifier string
        ip_address: Client IP address
        started_at: Session creation timestamp
        last_activity: Last activity timestamp for timeout detection
        expires_at: Session expiration timestamp
        is_active: Whether session is currently active
    """

    __tablename__ = "user_sessions"

    # Primary Key
    session_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )

    # Foreign Key
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=True,  # NULL for anonymous sessions
        index=True
    )

    # Session Binding
    session_token = Column(
        String(512),
        unique=True,
        nullable=False,
        index=True
    )

    # Device Information
    device_fingerprint = Column(
        String(255),
        nullable=False,
        index=True
    )
    user_agent = Column(
        String(512),
        nullable=True
    )
    ip_address = Column(
        String(45),  # IPv6 max length
        nullable=False,
        index=True
    )

    # Timestamps
    started_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        index=True
    )
    last_activity = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )

    # Status
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True
    )

    # Indexes for efficient queries
    __table_args__ = (
        Index("idx_user_sessions_user_id_active", "user_id", "is_active"),
        Index("idx_user_sessions_device_fingerprint", "device_fingerprint"),
        Index("idx_user_sessions_expires_at", "expires_at"),
    )

    # Relationships
    user = relationship(
        "User",
        foreign_keys=[user_id]
    )

    def __repr__(self) -> str:
        """String representation of UserSession."""
        user_info = f"user_id={self.user_id}" if self.user_id else "anonymous"
        return f"<UserSession {self.session_id} ({user_info})>"

    def to_dict(self) -> dict:
        """Convert session to dictionary."""
        return {
            "session_id": str(self.session_id),
            "user_id": str(self.user_id) if self.user_id else None,
            "device_fingerprint": self.device_fingerprint,
            "user_agent": self.user_agent,
            "ip_address": self.ip_address,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active,
        }
