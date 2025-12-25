"""
Transaction model
Immutable record of all land purchases and transfers
"""

from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime, Enum as SQLEnum, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, column_property
from sqlalchemy.ext.hybrid import hybrid_property
import uuid
from enum import Enum as PyEnum
from datetime import datetime

from app.db.base import BaseModel


class TransactionStatus(str, PyEnum):
    """Transaction status enumeration."""
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class TransactionType(str, PyEnum):
    """Transaction type enumeration."""
    AUCTION = "AUCTION"
    BUY_NOW = "BUY_NOW"
    FIXED_PRICE = "FIXED_PRICE"
    TRANSFER = "TRANSFER"
    TOPUP = "TOPUP"
    BIOME_BUY = "BIOME_BUY"
    BIOME_SELL = "BIOME_SELL"


class Transaction(BaseModel):
    """
    Transaction model for land purchases and biome share trading.

    IMMUTABLE: Records cannot be updated after creation (audit trail).
    All monetary transactions are logged for compliance.

    Attributes:
        transaction_id: Unique UUID identifier
        land_id: Reference to land involved (nullable for biome trades)
        seller_id: Reference to seller (nullable for biome trades)
        buyer_id: Reference to buyer
        listing_id: Reference to marketplace listing (nullable for direct transfers)
        amount_bdt: Transaction amount in BDT
        currency: Currency code (always "BDT")
        status: Transaction status
        gateway_name: Payment gateway used (bkash/nagad/rocket/sslcommerz)
        gateway_transaction_id: External transaction ID from gateway
        platform_fee_bdt: Platform commission
        gateway_fee_bdt: Payment processor fee
        completed_at: When transaction was completed
        biome: Biome type for biome trading (nullable for land trades)
        shares: Number of shares traded (nullable for land trades)
        price_per_share_bdt: Price per share at trade time (nullable for land trades)
    """

    __tablename__ = "transactions"

    __table_args__ = (
        Index("idx_transactions_seller", "seller_id", "created_at"),
        Index("idx_transactions_buyer", "buyer_id", "created_at"),
        Index("idx_transactions_status", "status"),
        Index("idx_transactions_created_at", "created_at"),
        CheckConstraint("amount_bdt > 0", name="check_positive_amount"),
    )

    # Primary Key
    transaction_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )

    # Foreign Keys
    land_id = Column(
        UUID(as_uuid=True),
        ForeignKey("lands.land_id"),
        nullable=True,  # Nullable for biome trades
        index=True
    )
    seller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True  # Nullable for biome trades
    )
    buyer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=False
    )
    listing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("listings.listing_id"),
        nullable=True  # Nullable for direct transfers
    )

    # Transaction Details
    transaction_type = Column(
        SQLEnum(TransactionType),
        nullable=False,
        index=True
    )
    amount_bdt = Column(
        Integer,
        nullable=False
    )
    currency = Column(
        String(3),
        default="BDT",
        nullable=False
    )
    status = Column(
        SQLEnum(TransactionStatus),
        default=TransactionStatus.PENDING,
        nullable=False,
        index=True
    )

    # Payment Gateway Info
    gateway_name = Column(
        String(50),
        nullable=True  # Nullable for internal transfers
    )
    gateway_transaction_id = Column(
        String(255),
        nullable=True,
        unique=True  # External transaction ID must be unique
    )

    # Fees
    platform_fee_bdt = Column(
        Integer,
        default=0,
        nullable=False
    )
    gateway_fee_bdt = Column(
        Integer,
        default=0,
        nullable=False
    )

    # Biome Trading Fields (nullable for marketplace transactions)
    biome = Column(
        String(50),
        nullable=True,  # Only set for BIOME_BUY/BIOME_SELL transactions
        index=True
    )
    shares = Column(
        Float,
        nullable=True  # Number of shares traded
    )
    price_per_share_bdt = Column(
        Integer,
        nullable=True  # Price per share at trade time
    )

    # Timestamps (immutable after creation)
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relationships
    land = relationship("Land", back_populates="transactions")
    seller = relationship(
        "User",
        back_populates="transactions_as_seller",
        foreign_keys=[seller_id]
    )
    buyer = relationship(
        "User",
        back_populates="transactions_as_buyer",
        foreign_keys=[buyer_id]
    )

    @hybrid_property
    def seller_receives_bdt(self) -> int:
        """
        Calculate net amount seller receives after fees.

        Returns:
            int: Amount seller receives in BDT
        """
        return self.amount_bdt - self.platform_fee_bdt - self.gateway_fee_bdt

    def mark_completed(self) -> None:
        """
        Mark transaction as completed.
        Sets status and completion timestamp.
        """
        self.status = TransactionStatus.COMPLETED
        self.completed_at = datetime.utcnow()

    def mark_failed(self) -> None:
        """Mark transaction as failed."""
        self.status = TransactionStatus.FAILED

    def mark_refunded(self) -> None:
        """Mark transaction as refunded."""
        self.status = TransactionStatus.REFUNDED

    def calculate_platform_fee(self, fee_percent: float = 5.0) -> int:
        """
        Calculate platform fee based on amount and percentage.

        Args:
            fee_percent: Platform fee percentage (default 5%)

        Returns:
            int: Platform fee amount in BDT
        """
        return int(self.amount_bdt * (fee_percent / 100))

    def __repr__(self) -> str:
        """String representation of Transaction."""
        return f"<Transaction {self.transaction_id} - {self.amount_bdt} BDT>"

    def to_dict(self) -> dict:
        """
        Convert transaction to dictionary for API responses.

        Returns:
            dict: Transaction data dictionary
        """
        return {
            "transaction_id": str(self.transaction_id),
            "land_id": str(self.land_id) if self.land_id else None,
            "seller_id": str(self.seller_id) if self.seller_id else None,
            "buyer_id": str(self.buyer_id),
            "listing_id": str(self.listing_id) if self.listing_id else None,
            "transaction_type": self.transaction_type.value,
            "amount_bdt": self.amount_bdt,
            "currency": self.currency,
            "status": self.status.value,
            "gateway_name": self.gateway_name,
            "gateway_transaction_id": self.gateway_transaction_id,
            "platform_fee_bdt": self.platform_fee_bdt,
            "gateway_fee_bdt": self.gateway_fee_bdt,
            "seller_receives_bdt": self.seller_receives_bdt if self.seller_id else None,
            "biome": self.biome,
            "shares": self.shares,
            "price_per_share_bdt": self.price_per_share_bdt,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }
