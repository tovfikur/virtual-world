"""
Fee schedule models for trading commissions and charges.
Supports maker/taker fees, volume tiers, and per-instrument overrides.
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.models.base import Base


class FeeType(str, enum.Enum):
    """Type of fee calculation."""
    PERCENTAGE = "PERCENTAGE"  # Fee as % of notional
    FLAT = "FLAT"              # Fixed fee per trade
    PER_LOT = "PER_LOT"        # Fee per lot/contract


class FeeSchedule(Base):
    """
    Base fee schedule for the exchange.
    Defines default maker/taker fees and volume-based tiers.
    """
    __tablename__ = "fee_schedules"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    
    # Default maker/taker fees
    maker_fee_type = Column(SQLEnum(FeeType), nullable=False, default=FeeType.PERCENTAGE)
    maker_fee_value = Column(Float, nullable=False, default=0.001)  # 0.1% default
    
    taker_fee_type = Column(SQLEnum(FeeType), nullable=False, default=FeeType.PERCENTAGE)
    taker_fee_value = Column(Float, nullable=False, default=0.002)  # 0.2% default
    
    # Minimum/maximum fee caps
    min_fee = Column(Float, default=0.0)
    max_fee = Column(Float, default=None)  # NULL = no cap
    
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)  # Default schedule for new users
    
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    
    # Relationships
    tiers = relationship("FeeVolumeTier", back_populates="schedule", cascade="all, delete-orphan")
    instrument_overrides = relationship("InstrumentFeeOverride", back_populates="schedule", cascade="all, delete-orphan")
    account_assignments = relationship("AccountFeeSchedule", back_populates="schedule")


class FeeVolumeTier(Base):
    """
    Volume-based fee discount tiers.
    Higher trading volumes qualify for lower fees.
    """
    __tablename__ = "fee_volume_tiers"
    
    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(Integer, ForeignKey("fee_schedules.id"), nullable=False)
    
    # Volume threshold (30-day rolling volume)
    min_volume = Column(Float, nullable=False)  # Minimum notional volume
    
    # Discounted fees for this tier
    maker_fee_type = Column(SQLEnum(FeeType), nullable=False)
    maker_fee_value = Column(Float, nullable=False)
    
    taker_fee_type = Column(SQLEnum(FeeType), nullable=False)
    taker_fee_value = Column(Float, nullable=False)
    
    tier_name = Column(String(50))  # e.g., "Bronze", "Silver", "Gold"
    
    # Relationships
    schedule = relationship("FeeSchedule", back_populates="tiers")


class InstrumentFeeOverride(Base):
    """
    Per-instrument fee overrides.
    Allows different fees for specific instruments (e.g., higher fees for crypto).
    """
    __tablename__ = "instrument_fee_overrides"
    
    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(Integer, ForeignKey("fee_schedules.id"), nullable=False)
    instrument_id = Column(UUID(as_uuid=True), ForeignKey("instruments.instrument_id"), nullable=False)
    
    # Override fees for this instrument
    maker_fee_type = Column(SQLEnum(FeeType), nullable=False)
    maker_fee_value = Column(Float, nullable=False)
    
    taker_fee_type = Column(SQLEnum(FeeType), nullable=False)
    taker_fee_value = Column(Float, nullable=False)
    
    min_fee = Column(Float, default=None)
    max_fee = Column(Float, default=None)
    
    # Relationships
    schedule = relationship("FeeSchedule", back_populates="instrument_overrides")
    instrument = relationship("Instrument")


class AccountFeeSchedule(Base):
    """
    Links accounts to fee schedules.
    Allows per-account fee arrangements (e.g., institutional clients).
    """
    __tablename__ = "account_fee_schedules"
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    schedule_id = Column(Integer, ForeignKey("fee_schedules.id"), nullable=False)
    
    # 30-day rolling volume for tier calculation
    rolling_volume_30d = Column(Float, default=0.0)
    last_volume_update = Column(String, default=lambda: datetime.utcnow().isoformat())
    
    assigned_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    
    # Relationships
    account = relationship("Account")
    schedule = relationship("FeeSchedule", back_populates="account_assignments")


class SwapRate(Base):
    """
    Overnight swap/rollover rates for FX and CFD positions.
    Applied daily to open positions held overnight.
    """
    __tablename__ = "swap_rates"
    
    id = Column(Integer, primary_key=True, index=True)
    instrument_id = Column(UUID(as_uuid=True), ForeignKey("instruments.instrument_id"), nullable=False)
    
    # Swap rates (in basis points per day)
    long_swap_rate = Column(Float, nullable=False)   # Swap for long positions
    short_swap_rate = Column(Float, nullable=False)  # Swap for short positions
    
    # Triple swap day (usually Wednesday for FX)
    triple_swap_day = Column(Integer, default=3)  # 0=Monday, 6=Sunday
    
    effective_date = Column(String, nullable=False)  # Date this rate takes effect
    is_active = Column(Boolean, default=True)
    
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    
    # Relationships
    instrument = relationship("Instrument")


class FundingRate(Base):
    """
    Funding rates for perpetual futures/swaps.
    Paid between long and short position holders.
    """
    __tablename__ = "funding_rates"
    
    id = Column(Integer, primary_key=True, index=True)
    instrument_id = Column(UUID(as_uuid=True), ForeignKey("instruments.instrument_id"), nullable=False)
    
    rate = Column(Float, nullable=False)  # Funding rate (e.g., 0.0001 = 0.01%)
    
    # Funding interval (in hours, typically 8h)
    interval_hours = Column(Integer, default=8)
    
    # Timestamp for this funding period
    timestamp = Column(String, nullable=False)
    
    # Next funding time
    next_funding_time = Column(String, nullable=False)
    
    # Relationships
    instrument = relationship("Instrument")


class Commission(Base):
    """
    Commission charges per trade.
    Records breakdown of fees charged on each trade.
    """
    __tablename__ = "commissions"
    
    id = Column(Integer, primary_key=True, index=True)
    trade_id = Column(Integer, ForeignKey("trades.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    
    # Fee breakdown
    maker_fee = Column(Float, default=0.0)
    taker_fee = Column(Float, default=0.0)
    exchange_fee = Column(Float, default=0.0)    # Exchange-level fee
    regulatory_fee = Column(Float, default=0.0)  # Government/regulatory fee
    
    # Total commission
    total_commission = Column(Float, nullable=False)
    
    # Fee calculation metadata
    fee_type = Column(String(20))  # "MAKER" or "TAKER"
    fee_rate = Column(Float)       # Rate applied
    notional_value = Column(Float) # Trade notional for % calculation
    
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    
    # Relationships
    trade = relationship("Trade")
    account = relationship("Account")
