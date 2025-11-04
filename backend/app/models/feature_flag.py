"""
Feature Flag model for feature toggles
"""

from sqlalchemy import Column, String, Text, Boolean, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.db.base import Base


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    flag_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flag_name = Column(String(100), nullable=False, unique=True)
    enabled = Column(Boolean, nullable=False, default=False)
    description = Column(Text, nullable=True)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    updater = relationship("User", backref="feature_flags_updated")
