"""
Bid model
Represents individual bids on auction listings
"""

from sqlalchemy import Column, Integer, ForeignKey, DateTime, Enum as SQLEnum, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from enum import Enum as PyEnum

from app.db.base import BaseModel


class BidStatus(str, PyEnum):
    """Bid status enumeration."""
    ACTIVE = "active"       # Current highest bid
    OUTBID = "outbid"      # No longer highest bid
    CANCELLED = "cancelled" # Bid cancelled by bidder
    WON = "won"            # Auction won


class Bid(BaseModel):
    """
    Bid model for auction listings.

    Tracks individual bids with chronological ordering.
    Only one bid can be ACTIVE per listing (the highest).

    Attributes:
        bid_id: Unique UUID identifier
        listing_id: Reference to auction listing
        bidder_id: Reference to user placing bid
        amount_bdt: Bid amount in BDT
        status: Current bid status
    """

    __tablename__ = "bids"

    __table_args__ = (
        Index("idx_bids_listing", "listing_id", "created_at"),
        Index("idx_bids_status", "status"),
    )

    # Primary Key
    bid_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )

    # Foreign Keys
    listing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("listings.listing_id"),
        nullable=False,
        index=True
    )
    bidder_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=False,
        index=True
    )

    # Bid Data
    amount_bdt = Column(
        Integer,
        nullable=False
    )
    status = Column(
        SQLEnum(BidStatus),
        default=BidStatus.ACTIVE,
        nullable=False,
        index=True
    )

    # Relationships
    listing = relationship("Listing", back_populates="bids")
    bidder = relationship("User", back_populates="bids")

    def mark_outbid(self) -> None:
        """Mark this bid as outbid (no longer highest)."""
        self.status = BidStatus.OUTBID

    def mark_won(self) -> None:
        """Mark this bid as winning (auction ended, highest bid)."""
        self.status = BidStatus.WON

    def cancel(self) -> None:
        """Cancel this bid (if allowed by business rules)."""
        self.status = BidStatus.CANCELLED

    def __repr__(self) -> str:
        """String representation of Bid."""
        return f"<Bid {self.bid_id} - {self.amount_bdt} BDT>"

    def to_dict(self) -> dict:
        """
        Convert bid to dictionary for API responses.

        Returns:
            dict: Bid data dictionary
        """
        return {
            "bid_id": str(self.bid_id),
            "listing_id": str(self.listing_id),
            "bidder_id": str(self.bidder_id),
            "amount_bdt": self.amount_bdt,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
