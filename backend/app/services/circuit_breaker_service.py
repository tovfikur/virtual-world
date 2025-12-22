"""
Circuit breaker service for volatility halts.
Monitors price movements and triggers trading halts when thresholds exceeded.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from uuid import UUID
import logging

from app.models.account import CircuitBreaker
from app.models.instrument import Instrument
from app.models.price_history import PriceHistory

logger = logging.getLogger(__name__)


class CircuitBreakerService:
    """
    Monitors price volatility and triggers trading halts.
    
    Types of Circuit Breakers:
    1. Instrument-level: Halt trading for specific instrument on excessive move
    2. Market-wide: Halt all trading on systemic volatility
    
    Thresholds:
    - Level 1: 5% move in 1 minute -> 5 minute halt
    - Level 2: 10% move in 5 minutes -> 15 minute halt
    - Level 3: 20% move in 15 minutes -> 30 minute halt
    """
    
    def __init__(self):
        self.instrument_thresholds = [
            {"percent": 5.0, "window_seconds": 60, "halt_seconds": 300},      # 5% in 1m -> 5m halt
            {"percent": 10.0, "window_seconds": 300, "halt_seconds": 900},    # 10% in 5m -> 15m halt
            {"percent": 20.0, "window_seconds": 900, "halt_seconds": 1800},   # 20% in 15m -> 30m halt
        ]
        
        self.market_wide_thresholds = [
            {"percent": 7.0, "window_seconds": 300, "halt_seconds": 900},     # 7% in 5m -> 15m halt
            {"percent": 13.0, "window_seconds": 600, "halt_seconds": 1800},   # 13% in 10m -> 30m halt
            {"percent": 20.0, "window_seconds": 900, "halt_seconds": 3600},   # 20% in 15m -> 60m halt
        ]
    
    async def check_instrument_volatility(
        self,
        instrument_id: UUID,
        current_price: float,
        db: AsyncSession
    ) -> Optional[CircuitBreaker]:
        """
        Check if instrument price movement triggers circuit breaker.
        
        Returns:
            CircuitBreaker if halt triggered, None otherwise
        """
        # Check if already halted
        existing_halt = await self._get_active_breaker(instrument_id, db)
        if existing_halt:
            return existing_halt
        
        # Check each threshold level
        for threshold in self.instrument_thresholds:
            percent_change = await self._calculate_price_change(
                instrument_id,
                window_seconds=threshold["window_seconds"],
                current_price=current_price,
                db=db
            )
            
            if percent_change is None:
                continue
            
            # Trigger on absolute percent change
            if abs(percent_change) >= threshold["percent"]:
                logger.warning(
                    f"Circuit breaker triggered for instrument {instrument_id}: "
                    f"{percent_change:.2f}% in {threshold['window_seconds']}s"
                )
                
                breaker = await self._trigger_breaker(
                    instrument_id=instrument_id,
                    breaker_type="INSTRUMENT",
                    trigger_reason=f"{abs(percent_change):.2f}% move in {threshold['window_seconds']}s",
                    percent_change=percent_change,
                    current_price=current_price,
                    duration_seconds=threshold["halt_seconds"],
                    db=db
                )
                return breaker
        
        return None
    
    async def check_market_wide_volatility(
        self,
        db: AsyncSession
    ) -> Optional[CircuitBreaker]:
        """
        Check if market-wide volatility triggers circuit breaker.
        
        Uses an index or basket of instruments to determine market stress.
        For simplicity, we check average volatility across all active instruments.
        
        Returns:
            CircuitBreaker if market-wide halt triggered, None otherwise
        """
        # Check if already halted
        existing_halt = await self._get_active_market_breaker(db)
        if existing_halt:
            return existing_halt
        
        # Get all active instruments
        stmt = select(Instrument).where(Instrument.status == "ACTIVE")
        result = await db.execute(stmt)
        instruments = result.scalars().all()
        
        if not instruments:
            return None
        
        # Calculate average volatility across instruments
        for threshold in self.market_wide_thresholds:
            total_volatility = 0.0
            count = 0
            
            for instrument in instruments:
                # Get current price
                from app.services.pricing_service import get_pricing_engine
                pricing_engine = get_pricing_engine()
                quote = await pricing_engine.get_aggregated_quote(instrument.instrument_id, db)
                
                if not quote:
                    continue
                
                current_price = quote['mid']
                
                # Calculate percent change
                percent_change = await self._calculate_price_change(
                    instrument.instrument_id,
                    window_seconds=threshold["window_seconds"],
                    current_price=current_price,
                    db=db
                )
                
                if percent_change is not None:
                    total_volatility += abs(percent_change)
                    count += 1
            
            if count == 0:
                continue
            
            avg_volatility = total_volatility / count
            
            # Trigger market-wide halt if average volatility exceeds threshold
            if avg_volatility >= threshold["percent"]:
                logger.critical(
                    f"Market-wide circuit breaker triggered: "
                    f"avg {avg_volatility:.2f}% move in {threshold['window_seconds']}s"
                )
                
                breaker = await self._trigger_breaker(
                    instrument_id=None,
                    breaker_type="MARKET_WIDE",
                    trigger_reason=f"Market avg {avg_volatility:.2f}% move in {threshold['window_seconds']}s",
                    percent_change=avg_volatility,
                    current_price=None,
                    duration_seconds=threshold["halt_seconds"],
                    db=db
                )
                return breaker
        
        return None
    
    async def _calculate_price_change(
        self,
        instrument_id: UUID,
        window_seconds: int,
        current_price: float,
        db: AsyncSession
    ) -> Optional[float]:
        """
        Calculate percent price change over time window.
        
        Returns:
            Percent change (e.g., 5.5 for +5.5%), or None if insufficient data
        """
        # Get reference price from time window ago
        lookback_time = datetime.utcnow() - timedelta(seconds=window_seconds)
        
        stmt = select(PriceHistory).where(
            and_(
                PriceHistory.instrument_id == instrument_id,
                PriceHistory.timestamp >= lookback_time,
                PriceHistory.timeframe == "1m"  # Use 1-minute candles for reference
            )
        ).order_by(PriceHistory.timestamp.asc()).limit(1)
        
        result = await db.execute(stmt)
        reference_candle = result.scalars().first()
        
        if not reference_candle:
            return None
        
        reference_price = reference_candle.open
        
        # Calculate percent change
        percent_change = ((current_price - reference_price) / reference_price) * 100
        
        return percent_change
    
    async def _trigger_breaker(
        self,
        instrument_id: Optional[UUID],
        breaker_type: str,
        trigger_reason: str,
        percent_change: float,
        current_price: Optional[float],
        duration_seconds: int,
        db: AsyncSession
    ) -> CircuitBreaker:
        """Create and activate a circuit breaker."""
        # Get reference price (for instrument-level breakers)
        reference_price = None
        if instrument_id and current_price:
            # Calculate reference price from percent change
            reference_price = current_price / (1 + percent_change / 100)
        
        # Create breaker
        breaker = CircuitBreaker(
            instrument_id=instrument_id,
            breaker_type=breaker_type,
            trigger_reason=trigger_reason,
            reference_price=reference_price,
            trigger_price=current_price,
            percent_change=percent_change,
            is_active=True,
            duration_seconds=duration_seconds
        )
        db.add(breaker)
        await db.flush()
        
        logger.critical(f"Circuit breaker activated: {breaker.id} - {trigger_reason}")
        
        # TODO: Broadcast halt notification via WebSocket
        # TODO: Cancel all pending orders for affected instruments
        
        return breaker
    
    async def _get_active_breaker(
        self,
        instrument_id: UUID,
        db: AsyncSession
    ) -> Optional[CircuitBreaker]:
        """Check if instrument has active circuit breaker."""
        stmt = select(CircuitBreaker).where(
            and_(
                CircuitBreaker.instrument_id == instrument_id,
                CircuitBreaker.is_active == True
            )
        ).order_by(CircuitBreaker.triggered_at.desc()).limit(1)
        
        result = await db.execute(stmt)
        breaker = result.scalars().first()
        
        if breaker:
            # Check if halt duration has expired
            elapsed = (datetime.utcnow() - breaker.triggered_at).total_seconds()
            if elapsed > breaker.duration_seconds:
                # Halt expired, deactivate
                breaker.is_active = False
                logger.info(f"Circuit breaker {breaker.id} expired and deactivated")
                await db.flush()
                return None
        
        return breaker
    
    async def _get_active_market_breaker(
        self,
        db: AsyncSession
    ) -> Optional[CircuitBreaker]:
        """Check if market-wide circuit breaker is active."""
        stmt = select(CircuitBreaker).where(
            and_(
                CircuitBreaker.breaker_type == "MARKET_WIDE",
                CircuitBreaker.is_active == True
            )
        ).order_by(CircuitBreaker.triggered_at.desc()).limit(1)
        
        result = await db.execute(stmt)
        breaker = result.scalars().first()
        
        if breaker:
            # Check if halt duration has expired
            elapsed = (datetime.utcnow() - breaker.triggered_at).total_seconds()
            if elapsed > breaker.duration_seconds:
                # Halt expired, deactivate
                breaker.is_active = False
                logger.info(f"Market-wide circuit breaker {breaker.id} expired and deactivated")
                await db.flush()
                return None
        
        return breaker
    
    async def is_trading_halted(
        self,
        instrument_id: UUID,
        db: AsyncSession
    ) -> bool:
        """Check if trading is halted for an instrument."""
        # Check instrument-specific halt
        instrument_halt = await self._get_active_breaker(instrument_id, db)
        if instrument_halt:
            return True
        
        # Check market-wide halt
        market_halt = await self._get_active_market_breaker(db)
        if market_halt:
            return True
        
        return False
    
    async def get_active_breakers(
        self,
        db: AsyncSession
    ) -> List[CircuitBreaker]:
        """Get all currently active circuit breakers."""
        stmt = select(CircuitBreaker).where(
            CircuitBreaker.is_active == True
        ).order_by(CircuitBreaker.triggered_at.desc())
        
        result = await db.execute(stmt)
        breakers = result.scalars().all()
        
        # Filter out expired breakers
        active_breakers = []
        for breaker in breakers:
            elapsed = (datetime.utcnow() - breaker.triggered_at).total_seconds()
            if elapsed <= breaker.duration_seconds:
                active_breakers.append(breaker)
            else:
                # Deactivate expired breaker
                breaker.is_active = False
        
        await db.flush()
        
        return active_breakers


# Global circuit breaker service instance
_circuit_breaker_service: Optional[CircuitBreakerService] = None


def get_circuit_breaker_service() -> CircuitBreakerService:
    """Get or create global circuit breaker service."""
    global _circuit_breaker_service
    if _circuit_breaker_service is None:
        _circuit_breaker_service = CircuitBreakerService()
    return _circuit_breaker_service
