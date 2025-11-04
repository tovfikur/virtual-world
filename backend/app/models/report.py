"""
Report model for user reports
"""

from sqlalchemy import Column, String, Text, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.db.base_class import Base


class Report(Base):
    __tablename__ = "reports"

    report_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reporter_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    reported_user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)
    resource_type = Column(String(50), nullable=True)  # 'user', 'land', 'chat_message'
    resource_id = Column(UUID(as_uuid=True), nullable=True)
    reason = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default='pending', index=True)  # 'pending', 'resolved', 'dismissed'
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), index=True)
    resolved_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Relationships
    reporter = relationship("User", foreign_keys=[reporter_id], backref="reports_made")
    reported_user = relationship("User", foreign_keys=[reported_user_id], backref="reports_received")
    assignee = relationship("User", foreign_keys=[assigned_to], backref="assigned_reports")
