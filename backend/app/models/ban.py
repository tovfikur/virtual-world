"""
Ban model for user bans and suspensions
"""

from sqlalchemy import Column, String, Text, Boolean, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.db.base import Base


class Ban(Base):
    __tablename__ = "bans"

    ban_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True)
    banned_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    reason = Column(Text, nullable=False)
    ban_type = Column(String(20), nullable=False)  # 'full', 'marketplace', 'chat'
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="bans")
    admin = relationship("User", foreign_keys=[banned_by])