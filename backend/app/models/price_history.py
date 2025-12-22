"""
Price history and market data models.
Stores OHLCV data at various timeframes with corporate action adjustments.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from .base import Base


class TimeframeEnum(str, enum.Enum):
    """Supported timeframes for OHLCV aggregation."""
    TICK = "tick"
    S1 = "1s"
    S5 = "5s"
    S15 = "15s"
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"
    MN1 = "1M"


class CorporateActionType(str, enum.Enum):
    """Types of corporate actions affecting price history."""
    SPLIT = "split"
    DIVIDEND = "dividend"
    REVERSE_SPLIT = "reverse_split"
    BONUS = "bonus"
    RIGHTS = "rights"


class PriceHistory(Base):
    """OHLCV price history at various timeframes."""
    __tablename__ = "price_histories"

    id = Column(Integer, primary_key=True, index=True)
    instrument_id = Column(UUID(as_uuid=True), ForeignKey("instruments.instrument_id", ondelete="CASCADE"), nullable=False)
    
    # Timeframe: 1s, 5s, 15s, 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 1M
    timeframe = Column(Enum(TimeframeEnum), nullable=False)
    
    # OHLCV data
    timestamp = Column(DateTime, nullable=False, index=True)  # Open time for this candle
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False, default=0.0)
    
    # Trade count and notional value
    trade_count = Column(Integer, default=0)
    notional = Column(Float, default=0.0)  # VWAP * volume
    
    # VWAP and typical price
    vwap = Column(Float, nullable=True)  # Volume-weighted average price
    typical_price = Column(Float, nullable=True)  # (H + L + C) / 3
    
    # Adjustment factor for corporate actions (e.g., 2.0 for 2:1 split)
    adjustment_factor = Column(Float, default=1.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    instrument = relationship("Instrument", back_populates="price_histories")
    
    __table_args__ = (
        Index("ix_price_histories_instrument_timeframe_timestamp", 
              "instrument_id", "timeframe", "timestamp"),
    )


class CorporateAction(Base):
    """Corporate actions (splits, dividends) affecting price history."""
    __tablename__ = "corporate_actions"

    id = Column(Integer, primary_key=True, index=True)
    instrument_id = Column(UUID(as_uuid=True), ForeignKey("instruments.instrument_id", ondelete="CASCADE"), nullable=False)
    
    action_type = Column(Enum(CorporateActionType), nullable=False)
    effective_date = Column(DateTime, nullable=False)
    
    # Action-specific data
    ratio = Column(Float, nullable=True)  # For splits: 2.0 = 2:1 split; 0.5 = 1:2 reverse split
    dividend_per_share = Column(Float, nullable=True)
    currency = Column(String(3), default="USD")
    
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    instrument = relationship("Instrument", back_populates="corporate_actions")
    
    __table_args__ = (
        Index("ix_corporate_actions_instrument_effective_date", 
              "instrument_id", "effective_date"),
    )


class QuoteLevel(Base):
    """Liquidity provider quotes for pricing."""
    __tablename__ = "quote_levels"

    id = Column(Integer, primary_key=True, index=True)
    instrument_id = Column(UUID(as_uuid=True), ForeignKey("instruments.instrument_id", ondelete="CASCADE"), nullable=False)
    
    # Quote source/LP identifier
    provider = Column(String(50), nullable=False)  # e.g., "lp1", "lp2", "aggregator"
    
    # Bid/Ask quotes
    bid_price = Column(Float, nullable=False)
    ask_price = Column(Float, nullable=False)
    bid_size = Column(Float, nullable=False)
    ask_size = Column(Float, nullable=False)
    
    # Quote quality
    spread = Column(Float, nullable=True)  # ask - bid
    spread_bp = Column(Float, nullable=True)  # spread in basis points
    
    # Mid-price and derived metrics
    mid = Column(Float, nullable=True)  # (bid + ask) / 2
    
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    is_stale = Column(Integer, default=0)  # Boolean: 1 = stale, 0 = fresh
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    instrument = relationship("Instrument", back_populates="quote_levels")
    
    __table_args__ = (
        Index("ix_quote_levels_instrument_provider_timestamp", 
              "instrument_id", "provider", "timestamp"),
    )
