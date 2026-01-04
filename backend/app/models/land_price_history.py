"""
LandPriceHistory model
Tracks owner and price changes for each land unit on every transfer.
"""

from sqlalchemy import Column, Integer, ForeignKey, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from app.db.base import BaseModel


class LandPriceHistory(BaseModel):
    """Immutable history of land ownership transfers and sale prices."""

    __tablename__ = "land_price_history"

    __table_args__ = (
        Index("idx_land_price_history_land", "land_id"),
        Index("idx_land_price_history_created", "created_at"),
    )

    history_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )

    land_id = Column(
        UUID(as_uuid=True),
        ForeignKey("lands.land_id"),
        nullable=False
    )

    listing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("listings.listing_id"),
        nullable=True
    )

    transaction_id = Column(
        UUID(as_uuid=True),
        ForeignKey("transactions.transaction_id"),
        nullable=True
    )

    previous_owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True
    )

    new_owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=False
    )

    price_bdt = Column(Integer, nullable=False)
    transferred_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    land = relationship("Land", back_populates="price_history")
    transaction = relationship("Transaction")

    def to_dict(self) -> dict:
        """Serialize history record."""
        return {
            "history_id": str(self.history_id),
            "land_id": str(self.land_id),
            "listing_id": str(self.listing_id) if self.listing_id else None,
            "transaction_id": str(self.transaction_id) if self.transaction_id else None,
            "previous_owner_id": str(self.previous_owner_id) if self.previous_owner_id else None,
            "new_owner_id": str(self.new_owner_id),
            "price_bdt": self.price_bdt,
            "transferred_at": self.transferred_at.isoformat() if self.transferred_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
