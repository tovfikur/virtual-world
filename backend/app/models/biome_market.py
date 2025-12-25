"""
BiomeMarket model
Represents the current market state for each biome
"""

from sqlalchemy import Column, Integer, Float, DateTime, Enum as SQLEnum, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum as PyEnum

from app.db.base import BaseModel
from app.models.land import Biome


class BiomeMarket(BaseModel):
    """
    Market state for each biome type.
    
    Tracks current market cash, attention scores, and share prices.
    Updated periodically via attention-based redistribution system.
    
    Attributes:
        biome: Biome type (ocean/beach/plains/forest/desert/mountain/snow)
        market_cash_bdt: Current market cash allocated to this biome
        attention_score: Current attention score (clicks, views, time spent)
        share_price_bdt: Current price per share (calculated from market_cash / total_shares)
        total_shares: Total shares issued for this biome
        last_redistribution: Timestamp of last attention-based redistribution
    """

    __tablename__ = "biome_markets"

    __table_args__ = (
        Index("idx_biome_markets_biome", "biome", unique=True),
        Index("idx_biome_markets_updated", "updated_at"),
    )

    # Biome identifier (primary key via biome enum)
    biome = Column(
        SQLEnum(Biome),
        primary_key=True,
        nullable=False
    )

    # Market State
    market_cash_bdt = Column(
        Integer,
        default=1000000,  # Starting market cash per biome
        nullable=False
    )
    
    attention_score = Column(
        Float,
        default=0.0,
        nullable=False
    )
    
    share_price_bdt = Column(
        Float,
        default=100.0,  # Starting price per share
        nullable=False
    )
    
    total_shares = Column(
        Integer,
        default=10000,  # Starting total shares per biome
        nullable=False
    )
    
    # Redistribution tracking
    last_redistribution = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )

    # Relationships
    holdings = relationship("BiomeHolding", back_populates="biome_market")
    transactions = relationship("BiomeTransaction", back_populates="biome_market")
    price_history = relationship("BiomePriceHistory", back_populates="biome_market", cascade="all, delete-orphan")

    def calculate_share_price(self) -> float:
        """
        Calculate current share price from market cash and total shares.
        
        Returns:
            float: Price per share in BDT
        """
        if self.total_shares <= 0:
            return 0.0
        return self.market_cash_bdt / self.total_shares

    def reset_attention(self) -> None:
        """Reset attention score after redistribution cycle."""
        self.attention_score = 0.0

    def add_attention(self, score: float) -> None:
        """
        Add to attention score.
        
        Args:
            score: Attention value to add
        """
        self.attention_score += score

    def __repr__(self) -> str:
        """String representation of BiomeMarket."""
        return f"<BiomeMarket {self.biome.value} - {self.market_cash_bdt} BDT>"

    def to_dict(self) -> dict:
        """
        Convert biome market to dictionary for API responses.
        
        Returns:
            dict: Biome market data dictionary
        """
        return {
            "biome": self.biome.value,
            "market_cash_bdt": self.market_cash_bdt,
            "attention_score": self.attention_score,
            "share_price_bdt": self.share_price_bdt,
            "total_shares": self.total_shares,
            "last_redistribution": self.last_redistribution.isoformat() if self.last_redistribution else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
