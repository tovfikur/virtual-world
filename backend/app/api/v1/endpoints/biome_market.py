"""
Biome Market Endpoints
API routes for biome trading, portfolio, and market data
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import logging
import uuid

from app.db.session import get_db
from app.models.land import Biome
from app.models.admin_config import AdminConfig
from app.schemas.biome_trading_schema import (
    BiomeMarketResponse,
    AllBiomeMarketsResponse,
    BuySharesRequest,
    SellSharesRequest,
    TradeResponse,
    PortfolioResponse,
    TransactionHistoryResponse,
    BiomePriceHistoryResponse,
    TrackAttentionRequest,
    MarketStatisticsResponse,
    BiomeStatistics
)
from app.dependencies import get_current_user
from app.services.biome_market_service import biome_market_service
from app.services.biome_trading_service import biome_trading_service
from app.services.attention_tracking_service import attention_tracking_service
from app.services.websocket_service import connection_manager
from app.services.rate_limit_service import rate_limit_service
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/biome-market", tags=["biome-market"])


def _rate_limit_identifier(request: Optional[Request], current_user: Optional[dict]) -> str:
    if current_user and current_user.get("sub"):
        return str(current_user["sub"])
    if request and request.client:
        return request.client.host
    return "anonymous"


async def _enforce_biome_trade_rate_limit(db: AsyncSession, request: Request, current_user: Optional[dict]):
    cfg_res = await db.execute(select(AdminConfig).limit(1))
    config = cfg_res.scalar_one_or_none()
    limit = config.biome_trades_per_minute if config else None
    if not limit:
        return

    identifier = _rate_limit_identifier(request, current_user)
    result = await rate_limit_service.check(
        bucket="biome_trades",
        identifier=identifier,
        limit=limit,
        window_seconds=60,
    )

    if result and not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Biome trade rate limit exceeded",
            headers={
                "X-RateLimit-Limit": str(result.limit),
                "X-RateLimit-Remaining": str(result.remaining),
                "X-RateLimit-Reset": str(result.reset_epoch),
            },
        )


# =============================================================================
# Market Data Endpoints
# =============================================================================

@router.get("/markets", response_model=AllBiomeMarketsResponse)
async def get_all_markets(db: AsyncSession = Depends(get_db)):
    """
    Get current state of all biome markets.
    
    Returns current prices, market cash, and attention scores for all biomes.
    """
    try:
        markets = await biome_market_service.get_all_markets(db)
        
        total_cash = sum(market.market_cash_bdt for market in markets)
        
        return AllBiomeMarketsResponse(
            markets=[BiomeMarketResponse(**market.to_dict()) for market in markets],
            total_market_cash=total_cash,
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Failed to get markets: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve market data"
        )


@router.get("/markets/{biome}", response_model=BiomeMarketResponse)
async def get_market(
    biome: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get current state of specific biome market.
    
    Returns current price, market cash, and attention score.
    """
    try:
        biome_enum = Biome(biome)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid biome. Must be one of: {[b.value for b in Biome]}"
        )

    try:
        market = await biome_market_service.get_market(db, biome_enum)
        return BiomeMarketResponse(**market.to_dict())
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get market for {biome}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve market data"
        )


@router.get("/price-history/{biome}", response_model=BiomePriceHistoryResponse)
async def get_price_history(
    biome: str,
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db)
):
    """
    Get historical price data for a biome.
    
    Args:
        biome: Biome type
        hours: Number of hours to look back (default 24, max 168 = 7 days)
    
    Returns price history for charting.
    """
    try:
        biome_enum = Biome(biome)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid biome. Must be one of: {[b.value for b in Biome]}"
        )

    try:
        history = await biome_market_service.get_price_history(db, biome_enum, hours)
        
        history_points = [
            {
                "timestamp": record.timestamp.isoformat(),
                "price_bdt": record.price_bdt,
                "market_cash_bdt": record.market_cash_bdt,
                "attention_score": record.attention_score
            }
            for record in history
        ]
        
        start_time = history[0].timestamp.isoformat() if history else datetime.utcnow().isoformat()
        end_time = history[-1].timestamp.isoformat() if history else datetime.utcnow().isoformat()
        
        return BiomePriceHistoryResponse(
            biome=biome,
            history=history_points,
            start_time=start_time,
            end_time=end_time,
            data_points=len(history_points)
        )
    except Exception as e:
        logger.error(f"Failed to get price history for {biome}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve price history"
        )


# =============================================================================
# Trading Endpoints
# =============================================================================

@router.post("/buy", response_model=TradeResponse, status_code=status.HTTP_201_CREATED)
async def buy_shares(
    buy_request: BuySharesRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None
):
    """
    Buy biome shares with BDT balance.
    
    Executes immediate purchase at current market price.
    Deducts amount from user balance and adds shares to portfolio.
    """
    try:
        user_uuid = uuid.UUID(current_user["sub"])
        biome_enum = Biome(buy_request.biome.value)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID or biome format"
        )

    try:
        await _enforce_biome_trade_rate_limit(db, request, current_user)

        transaction = await biome_trading_service.buy_shares(
            db=db,
            user_id=user_uuid,
            biome=biome_enum,
            amount_bdt=buy_request.amount_bdt
        )

        return TradeResponse(
            **transaction.to_dict(),
            message=f"Successfully bought {transaction.shares:.4f} shares of {biome_enum.value}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to buy shares: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute buy order"
        )


@router.post("/sell", response_model=TradeResponse, status_code=status.HTTP_201_CREATED)
async def sell_shares(
    sell_request: SellSharesRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None
):
    """
    Sell biome shares for BDT.
    
    Executes immediate sale at current market price.
    Adds proceeds to user balance and removes shares from portfolio.
    Calculates realized gain/loss.
    """
    try:
        user_uuid = uuid.UUID(current_user["sub"])
        biome_enum = Biome(sell_request.biome.value)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID or biome format"
        )

    try:
        await _enforce_biome_trade_rate_limit(db, request, current_user)

        transaction = await biome_trading_service.sell_shares(
            db=db,
            user_id=user_uuid,
            biome=biome_enum,
            shares=sell_request.shares
        )

        # Calculate realized gain from difference between current and purchase price
        realized_gain = 0
        if transaction.price_per_share_bdt and transaction.shares:
            # This is simplified - in reality you'd track the cost basis
            realized_gain = 0  # TODO: Track realized gain properly

        return TradeResponse(
            **transaction.to_dict(),
            message=f"Successfully sold {transaction.shares:.4f} shares of {biome_enum.value}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to sell shares: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute sell order"
        )


# =============================================================================
# Portfolio Endpoints
# =============================================================================

@router.get("/portfolio", response_model=PortfolioResponse)
async def get_portfolio(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's biome portfolio.
    
    Returns all holdings with current values, unrealized gains, and cash balance.
    """
    try:
        user_uuid = uuid.UUID(current_user["sub"])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )

    try:
        portfolio = await biome_trading_service.get_user_portfolio(db, user_uuid)
        return PortfolioResponse(**portfolio)
    except Exception as e:
        logger.error(f"Failed to get portfolio: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve portfolio"
        )


@router.get("/transactions", response_model=TransactionHistoryResponse)
async def get_transaction_history(
    biome: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's transaction history.
    
    Returns paginated list of buy/sell transactions.
    Optionally filter by biome.
    """
    try:
        user_uuid = uuid.UUID(current_user["sub"])
        biome_enum = Biome(biome) if biome else None
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID or biome format"
        )

    try:
        history = await biome_trading_service.get_transaction_history(
            db=db,
            user_id=user_uuid,
            biome=biome_enum,
            page=page,
            limit=limit
        )
        return TransactionHistoryResponse(**history)
    except Exception as e:
        logger.error(f"Failed to get transaction history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve transaction history"
        )


# =============================================================================
# Attention Tracking Endpoints
# =============================================================================

@router.post("/track-attention", status_code=status.HTTP_200_OK)
async def track_attention(
    attention_request: TrackAttentionRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Track user attention for a biome.
    
    Called when user interacts with or views a biome.
    Accumulates attention score for redistribution calculation.
    """
    try:
        user_uuid = uuid.UUID(current_user["sub"])
        biome_enum = Biome(attention_request.biome.value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID or biome format"
        )

    try:
        await attention_tracking_service.track_attention(
            db=db,
            user_id=user_uuid,
            biome=biome_enum,
            score=attention_request.score
        )

        # Broadcast updated attention totals to subscribers
        total_attention = await attention_tracking_service.get_biome_total_attention(
            db, biome_enum
        )

        message = {
            "type": "biome_attention_update",
            "biome": biome_enum.value,
            "total_attention": total_attention,
            "timestamp": datetime.utcnow().isoformat()
        }

        await connection_manager.broadcast_to_room(message, "biome_market_all")
        await connection_manager.broadcast_to_room(message, f"biome_market:{biome_enum.value}")

        return {
            "success": True,
            "message": f"Attention tracked for {biome_enum.value}",
            "score": attention_request.score
        }
    except Exception as e:
        logger.error(f"Failed to track attention: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to track attention"
        )
