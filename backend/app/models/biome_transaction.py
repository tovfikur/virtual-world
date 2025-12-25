"""
BiomeTransaction model
Represents buy/sell transactions for biome shares
"""

from sqlalchemy import Column, Integer, Float, ForeignKey, DateTime, Enum as SQLEnum, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from enum import Enum as PyEnum
from datetime import datetime

from app.db.base import BaseModel
from app.models.land import Biome


class BiomeTransactionType(str, PyEnum):
    """Biome transaction type enumeration."""
    BUY = "buy"
    SELL = "sell"


class BiomeTransaction(BaseModel):
    """
    Transaction record for biome share trading.
    
    Immutable record of all buy/sell operations.
    
    Attributes:
        transaction_id: Unique UUID identifier
        user_id: Reference to user making the transaction
        biome: Biome type traded
        type: Transaction type (buy/sell)
        shares: Number of shares traded
        price_per_share_bdt: Price per share at transaction time
        total_amount_bdt: Total transaction amount
        realized_gain_bdt: Realized gain/loss (for sell transactions)
        executed_at: When transaction was executed
    """

    __tablename__ = "biome_transactions"

    __table_args__ = (
        Index("idx_biome_transactions_user", "user_id", "executed_at"),
        Index("idx_biome_transactions_biome", "biome", "executed_at"),
        Index("idx_biome_transactions_type", "type"),
    )

    # Primary Key
    transaction_id = Column(
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

    # Transaction Details
    type = Column(
        SQLEnum(BiomeTransactionType),
        nullable=False,
        index=True
    )

    shares = Column(
        Float,
        nullable=False
    )

    price_per_share_bdt = Column(
        Float,
        nullable=False
    )

    total_amount_bdt = Column(
        Integer,
        nullable=False
    )

    # Gain/Loss (for sell transactions)
    realized_gain_bdt = Column(
        Float,
        nullable=True  # Only for sell transactions
    )

    executed_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        index=True
    )

    # Relationships
    user = relationship("User", back_populates="biome_transactions")
    biome_market = relationship("BiomeMarket", back_populates="transactions")

    def __repr__(self) -> str:
        """String representation of BiomeTransaction."""
        return f"<BiomeTransaction {self.type.value} {self.shares} {self.biome.value} @ {self.price_per_share_bdt}>"

    def to_dict(self) -> dict:
        """
        Convert transaction to dictionary for API responses.
        
        Returns:
            dict: Transaction data dictionary
        """
        return {
            "transaction_id": str(self.transaction_id),
            "user_id": str(self.user_id),
            "biome": self.biome.value,
            "type": self.type.value,
            "shares": self.shares,
            "price_per_share_bdt": self.price_per_share_bdt,
            "total_amount_bdt": self.total_amount_bdt,
            "realized_gain_bdt": self.realized_gain_bdt,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None
        }
