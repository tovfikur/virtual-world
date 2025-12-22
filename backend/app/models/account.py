"""
Account and margin management models.
Tracks user account balances, margin, equity, and leverage limits.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from .base import Base


class AccountStatus(str, enum.Enum):
    """Account status."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    LIQUIDATING = "liquidating"
    CLOSED = "closed"


class Account(Base):
    """
    Trading account with margin and balance tracking.
    One account per user (1:1 relationship).
    """
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # Balance and equity
    balance = Column(Float, nullable=False, default=0.0)  # Deposited funds
    equity = Column(Float, nullable=False, default=0.0)   # Balance + unrealized P&L
    
    # Margin tracking
    used_margin = Column(Float, nullable=False, default=0.0)
    free_margin = Column(Float, nullable=False, default=0.0)  # equity - used_margin
    margin_level = Column(Float, nullable=True)  # (equity / used_margin) * 100
    
    # Leverage and risk limits
    leverage_max = Column(Float, nullable=False, default=1.0)  # Max leverage allowed (e.g., 50.0 = 50:1)
    max_position_size = Column(Float, nullable=True)  # Max position size in base currency
    max_exposure_per_instrument = Column(Float, nullable=True)  # Max notional per instrument
    
    # Status
    status = Column(Enum(AccountStatus), nullable=False, default=AccountStatus.ACTIVE)
    
    # Margin call thresholds
    margin_call_level = Column(Float, nullable=False, default=100.0)  # Trigger margin call at 100%
    liquidation_level = Column(Float, nullable=False, default=50.0)   # Force liquidate at 50%
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="account")
    positions = relationship("Position", back_populates="account", cascade="all, delete-orphan")
    margin_calls = relationship("MarginCall", back_populates="account", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Account user_id={self.user_id} balance={self.balance} equity={self.equity}>"


class Position(Base):
    """
    Open trading position for an instrument.
    Tracks entry price, quantity, and unrealized P&L.
    """
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    instrument_id = Column(UUID(as_uuid=True), ForeignKey("instruments.instrument_id", ondelete="CASCADE"), nullable=False)
    
    # Position details
    side = Column(String(10), nullable=False)  # LONG or SHORT
    quantity = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=True)  # Last known market price
    
    # P&L tracking
    unrealized_pnl = Column(Float, nullable=False, default=0.0)
    realized_pnl = Column(Float, nullable=False, default=0.0)
    
    # Margin used by this position
    margin_used = Column(Float, nullable=False, default=0.0)
    leverage_used = Column(Float, nullable=False, default=1.0)
    
    # Swap/overnight fees
    swap_accumulated = Column(Float, nullable=False, default=0.0)
    
    # Timestamps
    opened_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    
    # Relationships
    account = relationship("Account", back_populates="positions")
    instrument = relationship("Instrument")
    
    def __repr__(self) -> str:
        return f"<Position {self.side} {self.quantity}@{self.entry_price} instrument={self.instrument_id}>"


class MarginCall(Base):
    """
    Margin call record when account falls below margin call level.
    Tracks margin call events and actions taken.
    """
    __tablename__ = "margin_calls"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    
    # Margin call details
    margin_level = Column(Float, nullable=False)  # Margin level at time of call
    equity = Column(Float, nullable=False)
    used_margin = Column(Float, nullable=False)
    
    # Action taken
    action = Column(String(50), nullable=True)  # e.g., "notification_sent", "liquidation_triggered"
    resolved = Column(Boolean, default=False)
    
    # Timestamps
    triggered_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    
    # Relationships
    account = relationship("Account", back_populates="margin_calls")
    
    def __repr__(self) -> str:
        return f"<MarginCall account_id={self.account_id} level={self.margin_level}% action={self.action}>"


class CircuitBreaker(Base):
    """
    Circuit breaker events for volatility halts.
    Tracks when trading is paused due to excessive price movements.
    """
    __tablename__ = "circuit_breakers"

    id = Column(Integer, primary_key=True, index=True)
    instrument_id = Column(UUID(as_uuid=True), ForeignKey("instruments.instrument_id", ondelete="CASCADE"), nullable=True)
    
    # Breaker details
    breaker_type = Column(String(50), nullable=False)  # "instrument" or "market_wide"
    trigger_reason = Column(String(200), nullable=False)  # e.g., "price moved 10% in 1 minute"
    
    # Price movement data
    reference_price = Column(Float, nullable=True)
    trigger_price = Column(Float, nullable=True)
    percent_change = Column(Float, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    duration_seconds = Column(Integer, nullable=True)  # How long to halt (e.g., 300 = 5 min)
    
    # Timestamps
    triggered_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    cleared_at = Column(DateTime, nullable=True)
    
    # Relationships
    instrument = relationship("Instrument")
    
    def __repr__(self) -> str:
        return f"<CircuitBreaker type={self.breaker_type} instrument={self.instrument_id} active={self.is_active}>"
