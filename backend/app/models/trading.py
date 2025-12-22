"""
Trading models for batch-based in-game stock system.
"""

from sqlalchemy import Column, Integer, Numeric, String, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.db.base import BaseModel


class TradingCompany(BaseModel):
    """
    Represents a tradable company in the in-game exchange.
    """

    __tablename__ = "trading_companies"

    company_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    name = Column(String(128), nullable=False, unique=True)
    total_shares = Column(Integer, nullable=False, default=1000)
    sold_shares = Column(Integer, nullable=False, default=0)
    share_price = Column(Numeric(18, 8), nullable=False, default=1)

    transactions = relationship("TradingTransaction", back_populates="company")


class TradingTransaction(BaseModel):
    """
    Queued buy/sell transaction. Processed in 0.5s batches.
    """

    __tablename__ = "trading_transactions"

    tx_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("trading_companies.company_id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    shares = Column(Integer, nullable=False)  # positive buy, negative sell (requested)
    fee_percent = Column(Numeric(6, 4), nullable=False, default=0)
    fee_fixed_shares = Column(Numeric(18, 8), nullable=False, default=0)
    processed = Column(Boolean, nullable=False, default=False)

    company = relationship("TradingCompany", back_populates="transactions")
