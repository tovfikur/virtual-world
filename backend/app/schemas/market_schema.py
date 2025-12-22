from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional


class MarketState(str, Enum):
    OPEN = "open"
    HALTED = "halted"
    CLOSED = "closed"


class MarketStatusOut(BaseModel):
    state: MarketState
    reason: Optional[str] = None


class MarketStatusUpdate(BaseModel):
    state: MarketState = Field(..., description="open/halted/closed")
    reason: Optional[str] = Field(None, max_length=256)


class QuoteResponse(BaseModel):
    """Market quote (top-of-book) response."""
    instrument_id: int
    bid: float = Field(..., description="Best bid price")
    ask: float = Field(..., description="Best ask price")
    mid: float = Field(..., description="Mid-price (bid + ask) / 2")
    spread: float = Field(..., description="Spread amount (ask - bid)")
    spread_bp: float = Field(..., description="Spread in basis points")
    bid_size: float = Field(..., description="Available bid volume")
    ask_size: float = Field(..., description="Available ask volume")
    timestamp: str = Field(..., description="Quote timestamp (ISO format)")


class DepthLevel(BaseModel):
    """Single level in order book depth."""
    price: float
    size: float
    provider: Optional[str] = None


class DepthResponse(BaseModel):
    """Order book depth (Level 2) response."""
    instrument_id: int
    bids: List[DepthLevel] = Field(..., description="Bid levels (highest first)")
    asks: List[DepthLevel] = Field(..., description="Ask levels (lowest first)")
    timestamp: str = Field(..., description="Depth timestamp (ISO format)")


class CandleResponse(BaseModel):
    """OHLCV candle response."""
    instrument_id: int
    timeframe: str = Field(..., description="Timeframe (1s, 5s, 15s, 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 1M)")
    timestamp: str = Field(..., description="Candle open time (ISO format)")
    open: float = Field(..., description="Opening price")
    high: float = Field(..., description="Highest price")
    low: float = Field(..., description="Lowest price")
    close: float = Field(..., description="Closing price")
    volume: float = Field(..., description="Total volume traded")
    trade_count: int = Field(..., description="Number of trades in candle")
    vwap: Optional[float] = Field(None, description="Volume-weighted average price")


class TradeResponse(BaseModel):
    """Trade execution response."""
    instrument_id: int
    side: str = Field(..., description="BUY or SELL")
    price: float
    quantity: float
    timestamp: str = Field(..., description="Trade execution time (ISO format)")
    buyer_id: Optional[int] = None
    seller_id: Optional[int] = None
    order_id: Optional[int] = None


class TradesResponse(BaseModel):
    """Recent trades list response."""
    instrument_id: int
    trades: List[TradeResponse]
    timestamp: str


class PricingConfigSchema(BaseModel):
    """Pricing engine configuration."""
    base_spread_bp: float = Field(2.0, description="Base spread in basis points")
    fx_spread_bp: float = Field(1.0, description="FX spread in basis points")
    cfd_spread_bp: float = Field(3.0, description="CFD spread in basis points")
    cfd_markup_bp: float = Field(1.0, description="CFD broker markup in basis points")
    stale_quote_timeout_sec: int = Field(30, description="Stale quote timeout in seconds")
    tick_normalization: bool = Field(True, description="Enable tick normalization")
