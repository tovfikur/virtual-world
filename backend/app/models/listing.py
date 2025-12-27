"""
Listing model
Represents marketplace listings for land sales and auctions
"""

from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, DateTime, Enum as SQLEnum, Index
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
import uuid
from enum import Enum as PyEnum
from datetime import datetime, timedelta, timezone

from app.db.base import BaseModel


class ListingType(str, PyEnum):
    """Listing type enumeration."""
    AUCTION = "auction"
    FIXED_PRICE = "fixed_price"
    AUCTION_WITH_BUYNOW = "auction_with_buynow"


class ListingStatus(str, PyEnum):
    """Listing status enumeration."""
    ACTIVE = "active"
    SOLD = "sold"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class Listing(BaseModel):
    """
    Marketplace listing for land sales (parcel system).

    Supports multiple listing types:
    - Auction: Time-limited bidding with highest bidder winning
    - Fixed Price: Set price with immediate purchase option
    - Buy Now: Instant purchase at fixed price

    A listing can contain multiple connected lands (parcel).

    Attributes:
        listing_id: Unique UUID identifier
        seller_id: Reference to user selling the parcel
        listing_lands: List of lands in this parcel (via junction table)
        type: Listing type (auction/fixed_price/buy_now)
        description: Seller's description of the parcel
        images: Array of image URLs
        price_bdt: Starting/fixed price in BDT (for entire parcel)
        reserve_price_bdt: Minimum acceptable price for auctions
        auction_start_time: When auction begins
        auction_end_time: When auction ends
        auto_extend: Whether to extend auction if bids near end
        auto_extend_minutes: Minutes to extend by
        buy_now_enabled: Whether instant purchase is available
        buy_now_price_bdt: Fixed price for instant purchase (for entire parcel)
        status: Current listing status
        sold_at: When listing was sold
    """

    __tablename__ = "listings"

    __table_args__ = (
        Index("idx_listings_status", "status"),
        Index("idx_listings_auction_end", "auction_end_time"),
    )

    # Primary Key
    listing_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )

    # Foreign Keys
    seller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=False,
        index=True
    )

    # Listing Details
    type = Column(
        SQLEnum(ListingType),
        nullable=False
    )
    description = Column(String, nullable=True)
    images = Column(ARRAY(String), nullable=True)

    # Pricing
    price_bdt = Column(Integer, nullable=False)
    reserve_price_bdt = Column(Integer, nullable=True)

    # Auction Fields
    auction_start_time = Column(DateTime(timezone=True), nullable=True)
    auction_end_time = Column(DateTime(timezone=True), nullable=True)
    auto_extend = Column(Boolean, default=False, nullable=False)
    auto_extend_minutes = Column(Integer, default=5, nullable=False)

    # Buy Now Option
    buy_now_enabled = Column(Boolean, default=False, nullable=False)
    buy_now_price_bdt = Column(Integer, nullable=True)

    # Status
    status = Column(
        SQLEnum(ListingStatus),
        default=ListingStatus.ACTIVE,
        nullable=False,
        index=True
    )
    sold_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    listing_lands = relationship("ListingLand", back_populates="listing", cascade="all, delete-orphan")
    seller = relationship("User", back_populates="listings")
    bids = relationship("Bid", back_populates="listing", cascade="all, delete-orphan")

    def is_auction_active(self) -> bool:
        """
        Check if auction is still active (within time window and status is active).

        Returns:
            bool: True if auction is active, False otherwise
        """
        if self.type != ListingType.AUCTION:
            return False
        if self.status != ListingStatus.ACTIVE:
            return False
        if not self.auction_end_time:
            return False
        return datetime.now(timezone.utc) < self.auction_end_time

    def extend_auction(self) -> None:
        """
        Extend auction end time by auto_extend_minutes.
        Only works if auto_extend is enabled.
        """
        if not self.auto_extend or not self.auction_end_time:
            return

        self.auction_end_time += timedelta(minutes=self.auto_extend_minutes)

    def can_accept_bids(self) -> bool:
        """
        Check if listing can accept new bids.

        Returns:
            bool: True if bids are accepted, False otherwise
        """
        return (
            self.type == ListingType.AUCTION and
            self.status == ListingStatus.ACTIVE and
            self.is_auction_active()
        )

    def mark_sold(self, buyer_id: uuid.UUID, final_price: int) -> None:
        """
        Mark listing as sold.

        Args:
            buyer_id: UUID of buyer
            final_price: Final sale price
        """
        self.status = ListingStatus.SOLD
        self.sold_at = datetime.now(timezone.utc)

    def mark_expired(self) -> None:
        """Mark listing as expired (for auctions that didn't sell)."""
        self.status = ListingStatus.EXPIRED

    def cancel(self) -> None:
        """Cancel the listing (seller initiated)."""
        self.status = ListingStatus.CANCELLED

    def __repr__(self) -> str:
        """String representation of Listing."""
        return f"<Listing {self.listing_id} - {self.type.value}>"

    @property
    def land_count(self) -> int:
        """Get number of lands in this parcel."""
        return len(self.listing_lands) if self.listing_lands else 0

    def to_dict(self) -> dict:
        """
        Convert listing to dictionary for API responses.

        Note: land_count should be added manually in API endpoints to avoid lazy loading.

        Returns:
            dict: Listing data dictionary
        """
        return {
            "listing_id": str(self.listing_id),
            "seller_id": str(self.seller_id),
            "listing_type": self.type.value,
            "status": self.status.value,
            "starting_price_bdt": self.price_bdt if self.type in [ListingType.AUCTION, ListingType.AUCTION_WITH_BUYNOW] else None,
            "current_price_bdt": self.price_bdt,
            "reserve_price_bdt": self.reserve_price_bdt,
            "buy_now_price_bdt": self.buy_now_price_bdt,
            "bid_count": 0,  # TODO: Calculate from bids relationship
            "highest_bidder_id": None,  # TODO: Get from bids
            "ends_at": self.auction_end_time.isoformat() if self.auction_end_time else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
