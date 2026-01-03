"""
Biome Land Market model
Tracks sold land prices and statistics for each biome to enable dynamic market pricing
"""

from sqlalchemy import Column, Integer, Float, DateTime, Enum as SQLEnum, Index, CheckConstraint
from datetime import datetime
from enum import Enum as PyEnum

from app.db.base import BaseModel
from app.models.land import Biome


class BiomeLandMarket(BaseModel):
    """
    Land market state for each biome type.
    
    Tracks current land prices and sold land count per biome.
    Updated whenever land is bought or sold on the marketplace.
    
    Attributes:
        biome: Biome type (ocean/beach/plains/forest/desert/mountain/snow)
        sold_lands_count: Number of lands sold (owned) in this biome
        average_price_bdt: Average price of sold lands in this biome
        total_market_value_bdt: Total value of all sold lands in this biome
        last_transaction_at: Timestamp of last buy/sell event
    """

    __tablename__ = "biome_land_markets"

    __table_args__ = (
        Index("idx_biome_land_markets_biome", "biome", unique=True),
        Index("idx_biome_land_markets_updated", "updated_at"),
        CheckConstraint("sold_lands_count >= 0", name="check_nonnegative_sold_lands"),
        CheckConstraint("average_price_bdt >= 0", name="check_nonnegative_avg_price"),
    )

    # Biome identifier (primary key via biome enum)
    biome = Column(
        SQLEnum(Biome),
        primary_key=True,
        nullable=False
    )

    # Market State for Land Trading
    sold_lands_count = Column(
        Integer,
        default=0,  # Initially no sold lands
        nullable=False
    )
    
    average_price_bdt = Column(
        Float,
        default=0.0,  # Will be calculated from biome base prices
        nullable=False
    )
    
    total_market_value_bdt = Column(
        Integer,
        default=0,  # Sum of all sold land prices in biome
        nullable=False
    )
    
    # Transaction tracking
    last_transaction_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )

    def calculate_average_price(self) -> float:
        """
        Calculate current average price from total market value and sold lands count.
        
        Returns:
            float: Average price per sold land in BDT
        """
        if self.sold_lands_count <= 0:
            return 0.0
        return self.total_market_value_bdt / self.sold_lands_count

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "biome": self.biome.value if self.biome else None,
            "sold_lands_count": self.sold_lands_count,
            "average_price_bdt": self.average_price_bdt,
            "total_market_value_bdt": self.total_market_value_bdt,
            "last_transaction_at": self.last_transaction_at.isoformat() if self.last_transaction_at else None,
        }
