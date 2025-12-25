"""
Land chat access model
Grants explicit read/write permissions for land-specific chats.
"""

import uuid
from sqlalchemy import (
    Column,
    Boolean,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import BaseModel


class LandChatAccess(BaseModel):
    """
    Per-land chat access entry.

    When a land has at least one access record, only the owner and
    the listed users can read or write messages on that land.
    """

    __tablename__ = "land_chat_access"
    __table_args__ = (
        UniqueConstraint("land_id", "user_id", name="uq_land_chat_access"),
    )

    access_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    land_id = Column(
        UUID(as_uuid=True),
        ForeignKey("lands.land_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    can_read = Column(Boolean, nullable=False, default=True)
    can_write = Column(Boolean, nullable=False, default=True)

    land = relationship("Land", back_populates="chat_access")
    user = relationship("User")

