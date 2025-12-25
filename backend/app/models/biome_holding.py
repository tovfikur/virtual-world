"""
BiomeHolding model
Represents user's biome share holdings
"""

from sqlalchemy import Column, Integer, Float, ForeignKey, Index, CheckConstraint, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.db.base import BaseModel
from app.models.land import Biome


class BiomeHolding(BaseModel):
    """
    User's holdings in a specific biome.
    
    Tracks number of shares owned and average buy price for gain/loss calculation.
    
    Attributes:
        holding_id: Unique UUID identifier
        user_id: Reference to user owning the shares
        biome: Biome type
        shares: Number of shares owned
        average_buy_price_bdt: Average price paid per share (for P&L calculation)
        total_invested_bdt: Total amount invested
    """

    __tablename__ = "biome_holdings"

    __table_args__ = (
        Index("idx_biome_holdings_user", "user_id"),
        Index("idx_biome_holdings_user_biome", "user_id", "biome", unique=True),
        CheckConstraint("shares >= 0", name="check_positive_shares"),
    )

    # Primary Key
    holding_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )

    # Foreign Keys
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=False,
        index=True
    )

    biome = Column(
        SQLEnum(Biome),
        ForeignKey("biome_markets.biome"),
        nullable=False,
        index=True
    )

    # Holdings Data
    shares = Column(
        Float,
        default=0.0,
        nullable=False
    )

    average_buy_price_bdt = Column(
        Float,
        default=0.0,
        nullable=False
    )

    total_invested_bdt = Column(
        Integer,
        default=0,
        nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="biome_holdings")
    biome_market = relationship("BiomeMarket", back_populates="holdings")

    def add_shares(self, shares: float, price_per_share: float) -> None:
        """
        Add shares to holding and update average buy price.
        
        Args:
            shares: Number of shares to add
            price_per_share: Price paid per share
        """
        new_investment = shares * price_per_share
        new_total_shares = self.shares + shares
        
        if new_total_shares > 0:
            self.average_buy_price_bdt = (
                (self.total_invested_bdt + new_investment) / new_total_shares
            )
        
        self.shares = new_total_shares
        self.total_invested_bdt += int(new_investment)

    def remove_shares(self, shares: float) -> float:
        """
        Remove shares from holding.
        
        Args:
            shares: Number of shares to remove
            
        Returns:
            float: Average buy price for removed shares
            
        Raises:
            ValueError: If insufficient shares
        """
        if shares > self.shares:
            raise ValueError("Insufficient shares")
        
        removed_value = shares * self.average_buy_price_bdt
        self.shares -= shares
        self.total_invested_bdt -= int(removed_value)
        
        if self.shares <= 0:
            self.shares = 0
            self.total_invested_bdt = 0
            self.average_buy_price_bdt = 0
        
        return self.average_buy_price_bdt

    def calculate_unrealized_gain(self, current_price: float) -> float:
        """
        Calculate unrealized gain/loss.
        
        Args:
            current_price: Current market price per share
            
        Returns:
            float: Unrealized gain/loss in BDT
        """
        current_value = self.shares * current_price
        return current_value - self.total_invested_bdt

    def __repr__(self) -> str:
        """String representation of BiomeHolding."""
        return f"<BiomeHolding {self.user_id} - {self.biome.value}: {self.shares} shares>"

    def to_dict(self, current_price: float = None) -> dict:
        """
        Convert holding to dictionary for API responses.
        
        Args:
            current_price: Current market price per share (optional)
        
        Returns:
            dict: Holding data dictionary
        """
        data = {
            "holding_id": str(self.holding_id),
            "user_id": str(self.user_id),
            "biome": self.biome.value,
            "shares": self.shares,
            "average_buy_price_bdt": self.average_buy_price_bdt,
            "total_invested_bdt": self.total_invested_bdt,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
        
        if current_price is not None:
            data["current_value_bdt"] = self.shares * current_price
            data["unrealized_gain_bdt"] = self.calculate_unrealized_gain(current_price)
            data["unrealized_gain_percent"] = (
                (data["unrealized_gain_bdt"] / self.total_invested_bdt * 100)
                if self.total_invested_bdt > 0 else 0.0
            )
        
        return data
