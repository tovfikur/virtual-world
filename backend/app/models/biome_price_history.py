"""
BiomePriceHistory model
Stores historical price data for charting
"""

from sqlalchemy import Column, Float, DateTime, ForeignKey, Index, Integer, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from app.db.base import BaseModel
from app.models.land import Biome


class BiomePriceHistory(BaseModel):
    """
    Historical price record for biome shares.
    
    Stores price snapshots for charting and analysis.
    
    Attributes:
        record_id: Unique UUID identifier
        biome: Biome type
        price_bdt: Share price at this timestamp
        market_cash_bdt: Market cash at this timestamp
        attention_score: Attention score at this timestamp
        timestamp: When this price was recorded
    """

    __tablename__ = "biome_price_history"

    __table_args__ = (
        Index("idx_biome_price_history_biome_time", "biome", "timestamp"),
        Index("idx_biome_price_history_timestamp", "timestamp"),
    )

    # Primary Key
    record_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )

    # Foreign Key
    biome = Column(
        SQLEnum(Biome),
        ForeignKey("biome_markets.biome"),
        nullable=False,
        index=True
    )

    # Price Data
    price_bdt = Column(
        Float,
        nullable=False
    )

    market_cash_bdt = Column(
        Integer,
        nullable=False
    )

    attention_score = Column(
        Float,
        nullable=False
    )

    timestamp = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        index=True
    )

    # Relationships
    biome_market = relationship("BiomeMarket", back_populates="price_history")

    def __repr__(self) -> str:
        """String representation of BiomePriceHistory."""
        return f"<BiomePriceHistory {self.biome.value} @ {self.timestamp}: {self.price_bdt} BDT>"

    def to_dict(self) -> dict:
        """
        Convert price history record to dictionary for API responses.
        
        Returns:
            dict: Price history data dictionary
        """
        return {
            "record_id": str(self.record_id),
            "biome": self.biome.value,
            "price_bdt": self.price_bdt,
            "market_cash_bdt": self.market_cash_bdt,
            "attention_score": self.attention_score,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }
