"""
Swap and funding rate service.
Handles overnight fees for FX/CFD positions and funding rates for perpetual futures.
"""

from typing import Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from uuid import UUID
from datetime import datetime, timedelta
import logging

from app.models.fee_schedule import SwapRate, FundingRate
from app.models.account import Position
from app.models.instrument import Instrument, AssetClass

logger = logging.getLogger(__name__)


class SwapFeeService:
    """
    Manages overnight swap fees and funding rates.
    
    Swap Fees (FX/CFD):
    - Applied daily at rollover time (typically 00:00 UTC)
    - Different rates for long vs short positions
    - Triple swap on Wednesdays (covers weekend)
    
    Funding Rates (Perpetual Futures):
    - Exchanged between longs and shorts every 8 hours
    - Calculated based on spot-perpetual price difference
    - Positive rate: longs pay shorts
    - Negative rate: shorts pay longs
    """
    
    def __init__(self, rollover_hour: int = 0):
        """
        Initialize swap fee service.
        
        Args:
            rollover_hour: Hour of day (UTC) when swaps are applied
        """
        self.rollover_hour = rollover_hour
    
    async def get_swap_rate(
        self,
        instrument_id: UUID,
        db: AsyncSession
    ) -> Optional[SwapRate]:
        """Get current swap rate for instrument."""
        stmt = select(SwapRate).where(
            and_(
                SwapRate.instrument_id == instrument_id,
                SwapRate.is_active == True
            )
        ).order_by(SwapRate.effective_date.desc()).limit(1)
        
        result = await db.execute(stmt)
        return result.scalars().first()
    
    async def calculate_swap_fee(
        self,
        position: Position,
        swap_rate: SwapRate,
        days: int = 1
    ) -> float:
        """
        Calculate swap fee for a position.
        
        Args:
            position: Position to calculate swap for
            swap_rate: Applicable swap rate
            days: Number of days to charge (1 or 3 for triple swap)
            
        Returns:
            Swap fee amount (positive = charge, negative = credit)
        """
        # Get rate based on position side
        if position.side == "LONG":
            rate_bps = swap_rate.long_swap_rate
        else:  # SHORT
            rate_bps = swap_rate.short_swap_rate
        
        # Convert basis points to decimal
        rate = rate_bps / 10000.0
        
        # Calculate fee on notional
        notional = position.quantity * (position.current_price or position.entry_price)
        swap_fee = notional * rate * days
        
        return swap_fee
    
    async def apply_daily_swap(
        self,
        db: AsyncSession
    ) -> Dict:
        """
        Apply daily swap fees to all open positions.
        
        Should be run once per day at rollover time.
        
        Returns:
            Statistics: {
                "positions_charged": int,
                "total_swap_fees": float,
                "triple_swap_applied": bool
            }
        """
        now = datetime.utcnow()
        is_triple_swap_day = (now.weekday() == 2)  # Wednesday
        days = 3 if is_triple_swap_day else 1
        
        # Get all open positions
        stmt = select(Position).where(Position.closed_at.is_(None))
        result = await db.execute(stmt)
        positions = result.scalars().all()
        
        stats = {
            "positions_charged": 0,
            "total_swap_fees": 0.0,
            "triple_swap_applied": is_triple_swap_day
        }
        
        for position in positions:
            # Get instrument
            stmt = select(Instrument).where(
                Instrument.instrument_id == position.instrument_id
            )
            result = await db.execute(stmt)
            instrument = result.scalars().first()
            
            if not instrument:
                continue
            
            # Only apply to FX and CFD instruments
            if instrument.asset_class not in [AssetClass.FX, AssetClass.CFD]:
                continue
            
            # Get swap rate
            swap_rate = await self.get_swap_rate(position.instrument_id, db)
            
            if not swap_rate:
                logger.warning(f"No swap rate for instrument {instrument.symbol}")
                continue
            
            # Calculate and apply swap
            swap_fee = await self.calculate_swap_fee(position, swap_rate, days)
            position.swap_accumulated += swap_fee
            stats["positions_charged"] += 1
            stats["total_swap_fees"] += swap_fee
            
            logger.info(
                f"Applied swap {swap_fee:.4f} to position {position.id} "
                f"({instrument.symbol}, {position.side})"
            )
        
        await db.flush()
        
        if stats["positions_charged"] > 0:
            logger.info(
                f"Daily swap complete: {stats['positions_charged']} positions, "
                f"{stats['total_swap_fees']:.2f} total fees"
            )
        
        return stats
    
    async def get_funding_rate(
        self,
        instrument_id: UUID,
        db: AsyncSession
    ) -> Optional[FundingRate]:
        """Get current funding rate for perpetual futures."""
        stmt = select(FundingRate).where(
            FundingRate.instrument_id == instrument_id
        ).order_by(FundingRate.timestamp.desc()).limit(1)
        
        result = await db.execute(stmt)
        return result.scalars().first()
    
    async def calculate_funding_payment(
        self,
        position: Position,
        funding_rate: FundingRate
    ) -> float:
        """
        Calculate funding payment for perpetual futures position.
        
        Positive rate + Long position = Pay funding
        Positive rate + Short position = Receive funding
        Negative rate = Opposite
        
        Returns:
            Payment amount (positive = pay, negative = receive)
        """
        notional = position.quantity * (position.current_price or position.entry_price)
        
        # Calculate payment
        payment = notional * funding_rate.rate
        
        # Long positions pay when rate is positive
        if position.side == "LONG":
            return payment
        else:  # Short positions receive when rate is positive
            return -payment
    
    async def apply_funding_rate(
        self,
        db: AsyncSession
    ) -> Dict:
        """
        Apply funding rate to perpetual futures positions.
        
        Typically runs every 8 hours.
        
        Returns:
            Statistics about funding application
        """
        # Get all open positions in perpetual futures
        stmt = select(Position).join(Instrument).where(
            and_(
                Position.closed_at.is_(None),
                Instrument.asset_class == AssetClass.DERIVATIVE
                # TODO: Add is_perpetual flag to Instrument model
            )
        )
        result = await db.execute(stmt)
        positions = result.scalars().all()
        
        stats = {
            "positions_charged": 0,
            "total_payments": 0.0,
            "longs_paid": 0.0,
            "shorts_received": 0.0
        }
        
        for position in positions:
            # Get funding rate
            funding_rate = await self.get_funding_rate(position.instrument_id, db)
            
            if not funding_rate:
                continue
            
            # Calculate payment
            payment = await self.calculate_funding_payment(position, funding_rate)
            
            # Apply to position (stored in swap_accumulated for now)
            # TODO: Create separate funding_accumulated field
            position.swap_accumulated += abs(payment)
            
            stats["positions_charged"] += 1
            stats["total_payments"] += abs(payment)
            
            if payment > 0:
                stats["longs_paid"] += payment
            else:
                stats["shorts_received"] += abs(payment)
        
        await db.flush()
        
        if stats["positions_charged"] > 0:
            logger.info(f"Funding rate applied: {stats}")
        
        return stats
    
    async def estimate_daily_swap(
        self,
        instrument_id: UUID,
        quantity: float,
        side: str,
        price: float,
        db: AsyncSession
    ) -> float:
        """
        Estimate daily swap cost for a position.
        
        Used to show traders the overnight cost before opening position.
        """
        swap_rate = await self.get_swap_rate(instrument_id, db)
        
        if not swap_rate:
            return 0.0
        
        # Get rate based on side
        if side == "LONG":
            rate_bps = swap_rate.long_swap_rate
        else:
            rate_bps = swap_rate.short_swap_rate
        
        rate = rate_bps / 10000.0
        notional = quantity * price
        daily_swap = notional * rate
        
        return daily_swap
    
    async def create_swap_rate(
        self,
        instrument_id: UUID,
        long_rate: float,
        short_rate: float,
        effective_date: str,
        db: AsyncSession
    ) -> SwapRate:
        """Create or update swap rate for instrument."""
        # Deactivate previous rates
        stmt = select(SwapRate).where(
            and_(
                SwapRate.instrument_id == instrument_id,
                SwapRate.is_active == True
            )
        )
        result = await db.execute(stmt)
        old_rates = result.scalars().all()
        
        for rate in old_rates:
            rate.is_active = False
        
        # Create new rate
        swap_rate = SwapRate(
            instrument_id=instrument_id,
            long_swap_rate=long_rate,
            short_swap_rate=short_rate,
            effective_date=effective_date,
            is_active=True
        )
        db.add(swap_rate)
        await db.flush()
        
        logger.info(
            f"Created swap rate for {instrument_id}: "
            f"long={long_rate} bps, short={short_rate} bps"
        )
        
        return swap_rate
    
    async def create_funding_rate(
        self,
        instrument_id: UUID,
        rate: float,
        interval_hours: int,
        timestamp: str,
        db: AsyncSession
    ) -> FundingRate:
        """Create funding rate for perpetual futures."""
        # Calculate next funding time
        ts = datetime.fromisoformat(timestamp)
        next_funding = ts + timedelta(hours=interval_hours)
        
        funding_rate = FundingRate(
            instrument_id=instrument_id,
            rate=rate,
            interval_hours=interval_hours,
            timestamp=timestamp,
            next_funding_time=next_funding.isoformat()
        )
        db.add(funding_rate)
        await db.flush()
        
        logger.info(
            f"Created funding rate for {instrument_id}: "
            f"rate={rate:.6f}, interval={interval_hours}h"
        )
        
        return funding_rate


# Global swap fee service instance
_swap_service: Optional[SwapFeeService] = None


def get_swap_service() -> SwapFeeService:
    """Get or create global swap fee service."""
    global _swap_service
    if _swap_service is None:
        _swap_service = SwapFeeService()
    return _swap_service
