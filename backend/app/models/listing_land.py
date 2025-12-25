"""
ListingLand model
Junction table linking listings to multiple lands (parcel system)
"""

from sqlalchemy import Column, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.db.base import BaseModel


class ListingLand(BaseModel):
    """
    Junction table for many-to-many relationship between listings and lands.

    Enables parcel system where one listing can contain multiple connected lands.

    Attributes:
        id: Unique UUID identifier
        listing_id: Reference to marketplace listing
        land_id: Reference to land parcel
    """

    __tablename__ = "listing_lands"

    __table_args__ = (
        UniqueConstraint('listing_id', 'land_id', name='uq_listing_land'),
        Index('idx_listing_lands_listing', 'listing_id'),
        Index('idx_listing_lands_land', 'land_id'),
    )

    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )

    # Foreign Keys
    listing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("listings.listing_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    land_id = Column(
        UUID(as_uuid=True),
        ForeignKey("lands.land_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Relationships
    listing = relationship("Listing", back_populates="listing_lands")
    land = relationship("Land", back_populates="listing_lands")

    def __repr__(self) -> str:
        """String representation of ListingLand."""
        return f"<ListingLand listing={self.listing_id} land={self.land_id}>"
