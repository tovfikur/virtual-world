"""
Instrument model for multi-asset trading (equities/forex/commodities/indices/crypto/derivatives).
"""

from enum import Enum
from uuid import uuid4

from sqlalchemy import Column, String, Enum as SQLEnum, Numeric, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import BaseModel


class AssetClass(str, Enum):
    EQUITY = "equity"
    FOREX = "forex"
    COMMODITY = "commodity"
    INDEX = "index"
    CRYPTO = "crypto"
    DERIVATIVE = "derivative"


class InstrumentStatus(str, Enum):
    ACTIVE = "active"
    HALTED = "halted"
    CLOSED = "closed"


class Instrument(BaseModel):
    """
    Tradeable instrument definition with tick/lot sizing and risk flags.
    """

    __tablename__ = "instruments"

    instrument_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )
    symbol = Column(String(32), nullable=False, unique=True, index=True)
    name = Column(String(128), nullable=False)
    asset_class = Column(SQLEnum(AssetClass), nullable=False, index=True)

    tick_size = Column(Numeric(20, 8), nullable=False, default=0.0001)
    lot_size = Column(Numeric(20, 8), nullable=False, default=1)
    leverage_max = Column(Numeric(10, 4), nullable=False, default=1)

    is_margin_allowed = Column(Boolean, nullable=False, default=False)
    is_short_selling_allowed = Column(Boolean, nullable=False, default=False)

    status = Column(SQLEnum(InstrumentStatus), nullable=False, default=InstrumentStatus.ACTIVE, index=True)

    session_open_utc = Column(String(8), nullable=True)  # HH:MM:SS optional
    session_close_utc = Column(String(8), nullable=True)  # HH:MM:SS optional
    
    # Relationships for market data
    price_histories = relationship("PriceHistory", back_populates="instrument", cascade="all, delete-orphan")
    corporate_actions = relationship("CorporateAction", back_populates="instrument", cascade="all, delete-orphan")
    quote_levels = relationship("QuoteLevel", back_populates="instrument", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Instrument {self.symbol} ({self.asset_class})>"
