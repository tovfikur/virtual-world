"""
Biome Trading Schemas
Pydantic models for biome market API requests/responses
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum


class BiomeType(str, Enum):
    """Biome type enum."""
    OCEAN = "ocean"
    BEACH = "beach"
    PLAINS = "plains"
    FOREST = "forest"
    DESERT = "desert"
    MOUNTAIN = "mountain"
    SNOW = "snow"


class TransactionType(str, Enum):
    """Transaction type enum."""
    BUY = "buy"
    SELL = "sell"


# =============================================================================
# Market State Schemas
# =============================================================================

class BiomeMarketResponse(BaseModel):
    """Schema for biome market state response."""
    biome: str
    market_cash_bdt: int
    attention_score: float
    share_price_bdt: float
    total_shares: int
    last_redistribution: str
    updated_at: str

    class Config:
        from_attributes = True


class AllBiomeMarketsResponse(BaseModel):
    """Schema for all biome markets response."""
    markets: List[BiomeMarketResponse]
    total_market_cash: int
    timestamp: str


# =============================================================================
# Trading Schemas
# =============================================================================

class BuySharesRequest(BaseModel):
    """Schema for buying biome shares."""
    biome: BiomeType = Field(..., description="Biome to buy shares in")
    amount_bdt: int = Field(..., ge=1, description="Amount in BDT to spend")

    class Config:
        json_schema_extra = {
            "example": {
                "biome": "forest",
                "amount_bdt": 1000
            }
        }


class SellSharesRequest(BaseModel):
    """Schema for selling biome shares."""
    biome: BiomeType = Field(..., description="Biome to sell shares from")
    shares: float = Field(..., gt=0, description="Number of shares to sell")

    class Config:
        json_schema_extra = {
            "example": {
                "biome": "forest",
                "shares": 10.5
            }
        }


class TradeResponse(BaseModel):
    """Schema for trade execution response."""
    transaction_id: str
    user_id: str
    biome: str
    type: str
    shares: float
    price_per_share_bdt: float
    total_amount_bdt: int
    realized_gain_bdt: Optional[float] = None
    executed_at: str
    message: str

    class Config:
        from_attributes = True


# =============================================================================
# Portfolio Schemas
# =============================================================================

class BiomeHoldingResponse(BaseModel):
    """Schema for biome holding response."""
    holding_id: str
    user_id: str
    biome: str
    shares: float
    average_buy_price_bdt: float
    total_invested_bdt: int
    current_value_bdt: Optional[float] = None
    unrealized_gain_bdt: Optional[float] = None
    unrealized_gain_percent: Optional[float] = None
    created_at: str

    class Config:
        from_attributes = True


class PortfolioResponse(BaseModel):
    """Schema for user portfolio response."""
    holdings: List[BiomeHoldingResponse]
    total_invested_bdt: int
    total_current_value_bdt: float
    total_unrealized_gain_bdt: float
    total_unrealized_gain_percent: float
    cash_balance_bdt: int


class BiomeTransactionResponse(BaseModel):
    """Schema for transaction history response."""
    transaction_id: str
    user_id: str
    biome: str
    type: str
    shares: float
    price_per_share_bdt: float
    total_amount_bdt: int
    realized_gain_bdt: Optional[float] = None
    executed_at: str

    class Config:
        from_attributes = True


class TransactionHistoryResponse(BaseModel):
    """Schema for paginated transaction history."""
    transactions: List[BiomeTransactionResponse]
    pagination: Dict


# =============================================================================
# Price History Schemas
# =============================================================================

class PriceHistoryPoint(BaseModel):
    """Schema for single price history point."""
    timestamp: str
    price_bdt: float
    market_cash_bdt: int
    attention_score: float


class BiomePriceHistoryResponse(BaseModel):
    """Schema for biome price history response."""
    biome: str
    history: List[PriceHistoryPoint]
    start_time: str
    end_time: str
    data_points: int


class AllBiomesPriceHistoryResponse(BaseModel):
    """Schema for all biomes price history."""
    biomes: Dict[str, List[PriceHistoryPoint]]
    start_time: str
    end_time: str


# =============================================================================
# Attention Tracking Schemas
# =============================================================================

class TrackAttentionRequest(BaseModel):
    """Schema for tracking attention."""
    biome: BiomeType = Field(..., description="Biome being viewed/interacted with")
    score: float = Field(..., ge=0, description="Attention score to add (e.g., seconds spent, clicks)")

    class Config:
        json_schema_extra = {
            "example": {
                "biome": "plains",
                "score": 5.0
            }
        }


class AttentionScoreResponse(BaseModel):
    """Schema for attention score response."""
    score_id: str
    user_id: str
    biome: str
    score: float
    last_activity: str

    class Config:
        from_attributes = True


# =============================================================================
# Statistics Schemas
# =============================================================================

class BiomeStatistics(BaseModel):
    """Schema for biome statistics."""
    biome: str
    current_price_bdt: float
    price_change_24h_percent: float
    volume_24h_bdt: int
    total_holders: int
    average_holding_size: float


class MarketStatisticsResponse(BaseModel):
    """Schema for overall market statistics."""
    total_market_cash: int
    total_market_cash_change_24h_percent: float
    total_volume_24h_bdt: int
    total_traders: int
    most_active_biome: str
    biome_statistics: List[BiomeStatistics]
