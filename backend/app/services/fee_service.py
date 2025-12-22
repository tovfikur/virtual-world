"""
Fee calculation service.
Computes trading fees based on maker/taker status, volume tiers, and instrument overrides.
"""

from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from uuid import UUID
from datetime import datetime, timedelta
import logging

from app.models.fee_schedule import (
    FeeSchedule, FeeVolumeTier, InstrumentFeeOverride, 
    AccountFeeSchedule, Commission, FeeType
)
from app.models.account import Account
from app.models.instrument import Instrument
from app.models.trade import Trade

logger = logging.getLogger(__name__)


class FeeCalculationService:
    """
    Calculates trading fees and commissions.
    
    Fee Hierarchy:
    1. Instrument-specific override
    2. Volume tier discount
    3. Base schedule fee
    
    Fee Types:
    - PERCENTAGE: fee_value * notional
    - FLAT: fee_value (fixed per trade)
    - PER_LOT: fee_value * quantity
    """
    
    async def calculate_trade_fee(
        self,
        account_id: int,
        instrument_id: UUID,
        notional_value: float,
        quantity: float,
        is_maker: bool,
        db: AsyncSession
    ) -> Tuple[float, dict]:
        """
        Calculate fee for a trade.
        
        Args:
            account_id: Account ID
            instrument_id: Instrument UUID
            notional_value: Trade notional (quantity * price)
            quantity: Trade quantity
            is_maker: True if maker (provided liquidity), False if taker
            db: Database session
            
        Returns:
            (fee_amount, fee_details)
        """
        # Get account's fee schedule
        fee_schedule = await self._get_account_fee_schedule(account_id, db)
        
        if not fee_schedule:
            # Use default schedule
            fee_schedule = await self._get_default_fee_schedule(db)
        
        if not fee_schedule:
            logger.warning("No fee schedule found, using zero fees")
            return 0.0, {"error": "No fee schedule configured"}
        
        # Get 30-day volume for tier calculation
        volume_30d = await self._get_rolling_volume(account_id, db)
        
        # Determine applicable fee tier
        fee_config = await self._get_applicable_fee_config(
            fee_schedule.id,
            instrument_id,
            volume_30d,
            is_maker,
            db
        )
        
        # Calculate fee based on type
        fee_amount = self._calculate_fee(
            fee_type=fee_config["fee_type"],
            fee_value=fee_config["fee_value"],
            notional_value=notional_value,
            quantity=quantity
        )
        
        # Apply min/max caps
        if fee_config.get("min_fee") and fee_amount < fee_config["min_fee"]:
            fee_amount = fee_config["min_fee"]
        
        if fee_config.get("max_fee") and fee_amount > fee_config["max_fee"]:
            fee_amount = fee_config["max_fee"]
        
        fee_details = {
            "fee_type": "MAKER" if is_maker else "TAKER",
            "fee_rate": fee_config["fee_value"],
            "notional_value": notional_value,
            "fee_amount": fee_amount,
            "volume_tier": fee_config.get("tier_name"),
            "calculation_type": fee_config["fee_type"]
        }
        
        return fee_amount, fee_details
    
    async def record_commission(
        self,
        trade_id: int,
        account_id: int,
        fee_amount: float,
        fee_details: dict,
        db: AsyncSession
    ) -> Commission:
        """Record commission for a trade."""
        commission = Commission(
            trade_id=trade_id,
            account_id=account_id,
            total_commission=fee_amount,
            fee_type=fee_details["fee_type"],
            fee_rate=fee_details.get("fee_rate"),
            notional_value=fee_details.get("notional_value"),
        )
        
        # Distribute fee across categories
        if fee_details["fee_type"] == "MAKER":
            commission.maker_fee = fee_amount
        else:
            commission.taker_fee = fee_amount
        
        db.add(commission)
        await db.flush()
        
        logger.info(f"Recorded commission {fee_amount:.4f} for trade {trade_id}")
        
        return commission
    
    async def deduct_fee_from_account(
        self,
        account: Account,
        fee_amount: float,
        db: AsyncSession
    ) -> None:
        """Deduct fee from account balance."""
        account.balance -= fee_amount
        
        # Recalculate equity
        from app.services.margin_service import get_margin_service
        margin_service = get_margin_service()
        await margin_service.calculate_account_equity(account, db)
        
        await db.flush()
        
        logger.info(f"Deducted fee {fee_amount:.4f} from account {account.id}")
    
    async def _get_account_fee_schedule(
        self,
        account_id: int,
        db: AsyncSession
    ) -> Optional[FeeSchedule]:
        """Get fee schedule assigned to account."""
        stmt = select(FeeSchedule).join(AccountFeeSchedule).where(
            AccountFeeSchedule.account_id == account_id
        )
        result = await db.execute(stmt)
        return result.scalars().first()
    
    async def _get_default_fee_schedule(
        self,
        db: AsyncSession
    ) -> Optional[FeeSchedule]:
        """Get default fee schedule."""
        stmt = select(FeeSchedule).where(
            and_(
                FeeSchedule.is_default == True,
                FeeSchedule.is_active == True
            )
        )
        result = await db.execute(stmt)
        return result.scalars().first()
    
    async def _get_rolling_volume(
        self,
        account_id: int,
        db: AsyncSession,
        days: int = 30
    ) -> float:
        """
        Calculate rolling volume for account.
        
        Sum of all trade notional values in the last N days.
        """
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
        
        stmt = select(func.sum(Trade.quantity * Trade.price)).join(
            Account
        ).where(
            and_(
                Trade.buyer_id == account_id or Trade.seller_id == account_id,
                Trade.timestamp >= cutoff_date
            )
        )
        
        result = await db.execute(stmt)
        volume = result.scalar()
        
        return volume or 0.0
    
    async def _get_applicable_fee_config(
        self,
        schedule_id: int,
        instrument_id: UUID,
        volume_30d: float,
        is_maker: bool,
        db: AsyncSession
    ) -> dict:
        """
        Determine which fee configuration applies.
        
        Priority:
        1. Instrument-specific override
        2. Volume tier discount
        3. Base schedule
        """
        # Check for instrument override
        stmt = select(InstrumentFeeOverride).where(
            and_(
                InstrumentFeeOverride.schedule_id == schedule_id,
                InstrumentFeeOverride.instrument_id == instrument_id
            )
        )
        result = await db.execute(stmt)
        override = result.scalars().first()
        
        if override:
            return {
                "fee_type": override.maker_fee_type if is_maker else override.taker_fee_type,
                "fee_value": override.maker_fee_value if is_maker else override.taker_fee_value,
                "min_fee": override.min_fee,
                "max_fee": override.max_fee,
                "source": "instrument_override"
            }
        
        # Check for volume tier
        stmt = select(FeeVolumeTier).where(
            and_(
                FeeVolumeTier.schedule_id == schedule_id,
                FeeVolumeTier.min_volume <= volume_30d
            )
        ).order_by(FeeVolumeTier.min_volume.desc()).limit(1)
        
        result = await db.execute(stmt)
        tier = result.scalars().first()
        
        if tier:
            return {
                "fee_type": tier.maker_fee_type if is_maker else tier.taker_fee_type,
                "fee_value": tier.maker_fee_value if is_maker else tier.taker_fee_value,
                "tier_name": tier.tier_name,
                "source": "volume_tier"
            }
        
        # Use base schedule
        stmt = select(FeeSchedule).where(FeeSchedule.id == schedule_id)
        result = await db.execute(stmt)
        schedule = result.scalars().first()
        
        if schedule:
            return {
                "fee_type": schedule.maker_fee_type if is_maker else schedule.taker_fee_type,
                "fee_value": schedule.maker_fee_value if is_maker else schedule.taker_fee_value,
                "min_fee": schedule.min_fee,
                "max_fee": schedule.max_fee,
                "source": "base_schedule"
            }
        
        # Fallback: zero fees
        return {
            "fee_type": FeeType.PERCENTAGE,
            "fee_value": 0.0,
            "source": "fallback"
        }
    
    def _calculate_fee(
        self,
        fee_type: str,
        fee_value: float,
        notional_value: float,
        quantity: float
    ) -> float:
        """
        Calculate fee based on type.
        
        PERCENTAGE: fee_value * notional (e.g., 0.001 = 0.1%)
        FLAT: fee_value (fixed amount per trade)
        PER_LOT: fee_value * quantity
        """
        if fee_type == FeeType.PERCENTAGE:
            return fee_value * notional_value
        elif fee_type == FeeType.FLAT:
            return fee_value
        elif fee_type == FeeType.PER_LOT:
            return fee_value * quantity
        else:
            logger.error(f"Unknown fee type: {fee_type}")
            return 0.0
    
    async def update_rolling_volume(
        self,
        account_id: int,
        db: AsyncSession
    ) -> None:
        """Update 30-day rolling volume for account."""
        volume = await self._get_rolling_volume(account_id, db)
        
        stmt = select(AccountFeeSchedule).where(
            AccountFeeSchedule.account_id == account_id
        )
        result = await db.execute(stmt)
        account_schedule = result.scalars().first()
        
        if account_schedule:
            account_schedule.rolling_volume_30d = volume
            account_schedule.last_volume_update = datetime.utcnow().isoformat()
            await db.flush()
    
    async def get_fee_breakdown(
        self,
        account_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        db: AsyncSession = None
    ) -> dict:
        """
        Get fee breakdown for an account over a period.
        
        Returns:
            {
                "total_fees": float,
                "maker_fees": float,
                "taker_fees": float,
                "trade_count": int,
                "average_fee_per_trade": float
            }
        """
        stmt = select(Commission).where(Commission.account_id == account_id)
        
        if start_date:
            stmt = stmt.where(Commission.created_at >= start_date)
        if end_date:
            stmt = stmt.where(Commission.created_at <= end_date)
        
        result = await db.execute(stmt)
        commissions = result.scalars().all()
        
        total_fees = sum(c.total_commission for c in commissions)
        maker_fees = sum(c.maker_fee for c in commissions)
        taker_fees = sum(c.taker_fee for c in commissions)
        trade_count = len(commissions)
        
        return {
            "total_fees": total_fees,
            "maker_fees": maker_fees,
            "taker_fees": taker_fees,
            "trade_count": trade_count,
            "average_fee_per_trade": total_fees / trade_count if trade_count > 0 else 0.0
        }


# Global fee calculation service instance
_fee_service: Optional[FeeCalculationService] = None


def get_fee_service() -> FeeCalculationService:
    """Get or create global fee calculation service."""
    global _fee_service
    if _fee_service is None:
        _fee_service = FeeCalculationService()
    return _fee_service
