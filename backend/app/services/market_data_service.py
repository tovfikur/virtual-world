"""
Market data aggregation service.
Computes and stores OHLCV candles at multiple timeframes.
Manages price history and corporate action adjustments.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import logging

from app.models.instrument import Instrument
from app.models.price_history import (
    PriceHistory, TimeframeEnum, CorporateAction, CorporateActionType
)
from app.models.trade import Trade

logger = logging.getLogger(__name__)


class MarketDataAggregator:
    """Aggregates trade data into OHLCV candles at multiple timeframes."""
    
    # Mapping timeframe strings to timedelta
    TIMEFRAME_MAP = {
        TimeframeEnum.S1: timedelta(seconds=1),
        TimeframeEnum.S5: timedelta(seconds=5),
        TimeframeEnum.S15: timedelta(seconds=15),
        TimeframeEnum.M1: timedelta(minutes=1),
        TimeframeEnum.M5: timedelta(minutes=5),
        TimeframeEnum.M15: timedelta(minutes=15),
        TimeframeEnum.M30: timedelta(minutes=30),
        TimeframeEnum.H1: timedelta(hours=1),
        TimeframeEnum.H4: timedelta(hours=4),
        TimeframeEnum.D1: timedelta(days=1),
        TimeframeEnum.W1: timedelta(weeks=1),
        TimeframeEnum.MN1: timedelta(days=30),  # Approximate month
    }
    
    async def record_trade(self,
                          instrument_id: int,
                          price: float,
                          quantity: float,
                          db: AsyncSession) -> None:
        """
        Record a trade execution and trigger candle aggregation.
        In production, this is called from matching_service after a fill.
        """
        # Trigger aggregation for all timeframes
        for timeframe in TimeframeEnum:
            if timeframe == TimeframeEnum.TICK:
                continue
            await self._update_candle(instrument_id, price, quantity, timeframe, db)
    
    async def _update_candle(self,
                            instrument_id: int,
                            price: float,
                            quantity: float,
                            timeframe: TimeframeEnum,
                            db: AsyncSession) -> None:
        """Update or create OHLCV candle for a timeframe."""
        
        now = datetime.utcnow()
        candle_start = self._get_candle_start(now, timeframe)
        
        # Check if candle exists
        stmt = select(PriceHistory).where(
            and_(
                PriceHistory.instrument_id == instrument_id,
                PriceHistory.timeframe == timeframe,
                PriceHistory.timestamp == candle_start
            )
        )
        result = await db.execute(stmt)
        candle = result.scalars().first()
        
        notional = price * quantity
        
        if candle:
            # Update existing candle
            candle.high = max(candle.high, price)
            candle.low = min(candle.low, price)
            candle.close = price
            candle.volume += quantity
            candle.trade_count += 1
            candle.notional += notional
            
            if candle.volume > 0:
                candle.vwap = candle.notional / candle.volume
                candle.typical_price = (candle.high + candle.low + candle.close) / 3.0
        else:
            # Create new candle
            candle = PriceHistory(
                instrument_id=instrument_id,
                timeframe=timeframe,
                timestamp=candle_start,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=quantity,
                trade_count=1,
                notional=notional,
                vwap=price,
                typical_price=price,
            )
            db.add(candle)
        
        candle.updated_at = datetime.utcnow()
        await db.flush()
    
    def _get_candle_start(self, timestamp: datetime, timeframe: TimeframeEnum) -> datetime:
        """Get the start timestamp of a candle for a given timeframe."""
        
        if timeframe == TimeframeEnum.S1:
            return timestamp.replace(microsecond=0)
        elif timeframe == TimeframeEnum.S5:
            seconds = (timestamp.second // 5) * 5
            return timestamp.replace(second=seconds, microsecond=0)
        elif timeframe == TimeframeEnum.S15:
            seconds = (timestamp.second // 15) * 15
            return timestamp.replace(second=seconds, microsecond=0)
        elif timeframe == TimeframeEnum.M1:
            return timestamp.replace(second=0, microsecond=0)
        elif timeframe == TimeframeEnum.M5:
            minute = (timestamp.minute // 5) * 5
            return timestamp.replace(minute=minute, second=0, microsecond=0)
        elif timeframe == TimeframeEnum.M15:
            minute = (timestamp.minute // 15) * 15
            return timestamp.replace(minute=minute, second=0, microsecond=0)
        elif timeframe == TimeframeEnum.M30:
            minute = (timestamp.minute // 30) * 30
            return timestamp.replace(minute=minute, second=0, microsecond=0)
        elif timeframe == TimeframeEnum.H1:
            return timestamp.replace(minute=0, second=0, microsecond=0)
        elif timeframe == TimeframeEnum.H4:
            hour = (timestamp.hour // 4) * 4
            return timestamp.replace(hour=hour, minute=0, second=0, microsecond=0)
        elif timeframe == TimeframeEnum.D1:
            return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        elif timeframe == TimeframeEnum.W1:
            # Week starts Monday
            days_since_monday = timestamp.weekday()
            week_start = timestamp - timedelta(days=days_since_monday)
            return week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        elif timeframe == TimeframeEnum.MN1:
            return timestamp.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            return timestamp
    
    async def get_candles(self,
                         instrument_id: int,
                         timeframe: TimeframeEnum,
                         limit: int = 100,
                         start_time: Optional[datetime] = None,
                         end_time: Optional[datetime] = None,
                         db: AsyncSession = None) -> List[Dict]:
        """
        Fetch OHLCV candles for an instrument at a specific timeframe.
        
        Args:
            instrument_id: Instrument ID
            timeframe: TimeframeEnum value
            limit: Max number of candles to return
            start_time: Filter from this time
            end_time: Filter until this time
            db: Database session
            
        Returns:
            List of candle dicts ordered by timestamp DESC (newest first)
        """
        stmt = select(PriceHistory).where(
            PriceHistory.instrument_id == instrument_id,
            PriceHistory.timeframe == timeframe
        )
        
        if start_time:
            stmt = stmt.where(PriceHistory.timestamp >= start_time)
        if end_time:
            stmt = stmt.where(PriceHistory.timestamp <= end_time)
        
        stmt = stmt.order_by(PriceHistory.timestamp.desc()).limit(limit)
        
        result = await db.execute(stmt)
        candles = result.scalars().all()
        
        return [
            {
                'timestamp': c.timestamp.isoformat(),
                'open': c.open,
                'high': c.high,
                'low': c.low,
                'close': c.close,
                'volume': c.volume,
                'trade_count': c.trade_count,
                'vwap': c.vwap,
                'typical_price': c.typical_price,
                'adjustment_factor': c.adjustment_factor,
            }
            for c in reversed(candles)  # Reverse to return oldest first
        ]
    
    async def record_corporate_action(self,
                                     instrument_id: int,
                                     action_type: CorporateActionType,
                                     effective_date: datetime,
                                     ratio: Optional[float] = None,
                                     dividend_per_share: Optional[float] = None,
                                     currency: str = "USD",
                                     description: Optional[str] = None,
                                     db: AsyncSession = None) -> CorporateAction:
        """
        Record a corporate action and apply adjustments to price history.
        """
        action = CorporateAction(
            instrument_id=instrument_id,
            action_type=action_type,
            effective_date=effective_date,
            ratio=ratio,
            dividend_per_share=dividend_per_share,
            currency=currency,
            description=description,
        )
        db.add(action)
        await db.flush()
        
        # Apply adjustments to historical prices
        if action_type == CorporateActionType.SPLIT and ratio:
            # Update adjustment factors on historical prices
            stmt = select(PriceHistory).where(
                and_(
                    PriceHistory.instrument_id == instrument_id,
                    PriceHistory.timestamp < effective_date
                )
            )
            result = await db.execute(stmt)
            for price_record in result.scalars():
                price_record.adjustment_factor *= ratio
            logger.info(f"Applied {ratio}:1 split to {instrument_id} before {effective_date}")
        
        elif action_type == CorporateActionType.REVERSE_SPLIT and ratio:
            stmt = select(PriceHistory).where(
                and_(
                    PriceHistory.instrument_id == instrument_id,
                    PriceHistory.timestamp < effective_date
                )
            )
            result = await db.execute(stmt)
            for price_record in result.scalars():
                price_record.adjustment_factor *= (1.0 / ratio)
            logger.info(f"Applied 1:{ratio} reverse split to {instrument_id} before {effective_date}")
        
        await db.commit()
        return action
    
    async def get_adjusted_candles(self,
                                  instrument_id: int,
                                  timeframe: TimeframeEnum,
                                  limit: int = 100,
                                  db: AsyncSession = None) -> List[Dict]:
        """
        Get candles adjusted for corporate actions (splits/dividends).
        """
        candles = await self.get_candles(instrument_id, timeframe, limit, db=db)
        
        # Apply adjustment factors
        for candle in candles:
            factor = candle['adjustment_factor']
            candle['open'] /= factor
            candle['high'] /= factor
            candle['low'] /= factor
            candle['close'] /= factor
            candle['vwap'] /= factor
            candle['typical_price'] /= factor
        
        return candles


# Global market data aggregator instance
_market_data_aggregator: Optional[MarketDataAggregator] = None


def get_market_data_aggregator() -> MarketDataAggregator:
    """Get or create global market data aggregator."""
    global _market_data_aggregator
    if _market_data_aggregator is None:
        _market_data_aggregator = MarketDataAggregator()
    return _market_data_aggregator
