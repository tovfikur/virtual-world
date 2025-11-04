"""
Announcement model for admin announcements
"""

from sqlalchemy import Column, String, Text, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.db.base_class import Base


class Announcement(Base):
    __tablename__ = "announcements"

    announcement_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(20), nullable=False)  # 'info', 'warning', 'urgent'
    target_audience = Column(String(50), nullable=True)  # 'all', 'admins', 'users'
    display_location = Column(String(20), nullable=True)  # 'banner', 'popup', 'both'
    start_date = Column(TIMESTAMP(timezone=True), nullable=True)
    end_date = Column(TIMESTAMP(timezone=True), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    creator = relationship("User", backref="announcements")
