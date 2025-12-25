"""
IP access control lists for blacklist and whitelist.
"""

from datetime import datetime
import uuid

from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import BaseModel


class IPBlacklist(BaseModel):
    __tablename__ = "ip_blacklist"

    entry_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ip = Column(String(45), nullable=False, unique=True, index=True)
    reason = Column(Text, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)

    created_by = relationship("User", foreign_keys=[created_by_id])

    def is_expired(self) -> bool:
        return bool(self.expires_at and datetime.utcnow() > self.expires_at)


class IPWhitelist(BaseModel):
    __tablename__ = "ip_whitelist"

    entry_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ip = Column(String(45), nullable=False, unique=True, index=True)
    reason = Column(Text, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)

    created_by = relationship("User", foreign_keys=[created_by_id])

    def is_expired(self) -> bool:
        return bool(self.expires_at and datetime.utcnow() > self.expires_at)
