"""
Market data and pricing API endpoints.
Provides top-of-book, depth, trades, candles, and quotes.
"""

from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db.session import get_db
from app.schemas.market_schema import (
    QuoteResponse,
    DepthResponse,
    CandleResponse,
    TradesResponse,
)
from app.services.pricing_service import get_pricing_engine
from app.services.market_data_service import get_market_data_aggregator
from app.models.price_history import TimeframeEnum
from app.models.instrument import Instrument
from sqlalchemy import select

router = APIRouter(prefix="/api/v1/marketdata", tags=["market_data"])


@router.get("/quotes/{instrument_id}", response_model=QuoteResponse)
async def get_quote(
    instrument_id: str,
    db: AsyncSession = Depends(get_db)
) -> QuoteResponse:
    """
    Get current market quote (top-of-book) for an instrument.
    Includes bid/ask with spreads and available liquidity.
    """
    try:
        instr_uuid = UUID(instrument_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid instrument_id format")
    
    pricing_engine = get_pricing_engine()
    quote = await pricing_engine.get_aggregated_quote(instr_uuid, db)
    
    if not quote:
        raise HTTPException(status_code=404, detail="No quotes available for instrument")
    
    return QuoteResponse(
        instrument_id=str(instr_uuid),
        bid=quote['bid'],
        ask=quote['ask'],
        mid=quote['mid'],
        spread=quote['spread'],
        spread_bp=quote['spread_bp'],
        bid_size=quote['bid_size'],
        ask_size=quote['ask_size'],
        timestamp=quote['timestamp'].isoformat(),
    )


@router.get("/depth/{instrument_id}", response_model=DepthResponse)
async def get_depth(
    instrument_id: str,
    levels: int = Query(5, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
) -> DepthResponse:
    """
    Get order book depth (Level 2 market data).
    
    Args:
        instrument_id: Instrument ID (UUID)
        levels: Number of price levels on each side (default 5, max 50)
    """
    try:
        instr_uuid = UUID(instrument_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid instrument_id format")
    
    pricing_engine = get_pricing_engine()
    depth = await pricing_engine.get_depth(instr_uuid, levels=levels, db=db)
    
    if not depth:
        raise HTTPException(status_code=404, detail="No depth available for instrument")
    
    return DepthResponse(
        instrument_id=str(instr_uuid),
        bids=depth.get('bids', []),
        asks=depth.get('asks', []),
        timestamp=datetime.utcnow().isoformat(),
    )


@router.get("/candles/{instrument_id}", response_model=List[CandleResponse])
async def get_candles(
    instrument_id: str,
    timeframe: TimeframeEnum = Query(TimeframeEnum.M1),
    limit: int = Query(100, ge=1, le=1000),
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> List[CandleResponse]:
    """
    Get OHLCV candles for an instrument at a specific timeframe.
    
    Args:
        instrument_id: Instrument ID (UUID)
        timeframe: Candle timeframe (1s, 5s, 15s, 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 1M)
        limit: Max candles to return (1-1000, default 100)
        start_time: ISO format start time (e.g., "2025-01-01T00:00:00")
        end_time: ISO format end time (e.g., "2025-01-02T00:00:00")
    """
    try:
        instr_uuid = UUID(instrument_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid instrument_id format")
    
    # Verify instrument exists
    stmt = select(Instrument).where(Instrument.instrument_id == instr_uuid)
    result = await db.execute(stmt)
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Instrument not found")
    
    # Parse time filters
    start_dt = None
    end_dt = None
    
    if start_time:
        try:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_time format")
    
    if end_time:
        try:
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_time format")
    
    # Fetch candles
    aggregator = get_market_data_aggregator()
    candles = await aggregator.get_candles(
        instr_uuid,
        timeframe,
        limit=limit,
        start_time=start_dt,
        end_time=end_dt,
        db=db
    )
    
    return [
        CandleResponse(
            instrument_id=str(instr_uuid),
            timeframe=timeframe.value,
            timestamp=c['timestamp'],
            open=c['open'],
            high=c['high'],
            low=c['low'],
            close=c['close'],
            volume=c['volume'],
            trade_count=c['trade_count'],
            vwap=c['vwap'],
        )
        for c in candles
    ]


@router.get("/top-of-book", response_model=List[QuoteResponse])
async def get_top_of_book_all(
    db: AsyncSession = Depends(get_db)
) -> List[QuoteResponse]:
    """Get current market quotes for all active instruments."""
    pricing_engine = get_pricing_engine()
    
    # Get all instruments
    stmt = select(Instrument).where(Instrument.status == "active")
    result = await db.execute(stmt)
    instruments = result.scalars().all()
    
    quotes = []
    for instrument in instruments:
        quote = await pricing_engine.get_aggregated_quote(instrument.instrument_id, db)
        if quote:
            quotes.append(
                QuoteResponse(
                    instrument_id=str(instrument.instrument_id),
                    bid=quote['bid'],
                    ask=quote['ask'],
                    mid=quote['mid'],
                    spread=quote['spread'],
                    spread_bp=quote['spread_bp'],
                    bid_size=quote['bid_size'],
                    ask_size=quote['ask_size'],
                    timestamp=quote['timestamp'].isoformat(),
                )
            )
    
    return quotes


@router.get("/tob/{instrument_id}")
async def get_tob(
    instrument_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Shorthand for top-of-book quote."""
    return await get_quote(instrument_id, db)


@router.post("/quotes/{instrument_id}/add")
async def add_quote(
    instrument_id: str,
    provider: str = Query(...),
    bid: float = Query(..., gt=0),
    ask: float = Query(..., gt=0),
    bid_size: float = Query(..., gt=0),
    ask_size: float = Query(..., gt=0),
    db: AsyncSession = Depends(get_db)
):
    """
    Add or update a liquidity provider quote.
    (Typically called by market data consumer or LP integration)
    
    Args:
        instrument_id: Instrument ID (UUID)
        provider: LP identifier (e.g., "lp1", "lp2")
        bid: Bid price
        ask: Ask price
        bid_size: Bid volume
        ask_size: Ask volume
    """
    try:
        instr_uuid = UUID(instrument_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid instrument_id format")
    
    if bid >= ask:
        raise HTTPException(status_code=400, detail="Bid must be less than ask")
    
    pricing_engine = get_pricing_engine()
    quote = await pricing_engine.add_quote(
        instr_uuid,
        provider,
        bid,
        ask,
        bid_size,
        ask_size,
        db
    )
    
    await db.commit()
    return quote
