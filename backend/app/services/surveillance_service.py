"""
Surveillance service for market abuse detection and monitoring.
Detects spoofing, wash trading, front-running, and other suspicious patterns.
"""

from typing import List, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from datetime import datetime, timedelta
import logging
from uuid import UUID

from app.models.admin import (
    SurveillanceAlert, AnomalyType
)
from app.models.account import Account
from app.models.order import Order, OrderStatus
from app.models.trade import Trade
from app.models.instrument import Instrument

logger = logging.getLogger(__name__)


class SurveillanceService:
    """
    Market surveillance for abuse detection.
    Monitors for suspicious trading patterns and patterns indicative of market abuse.
    """
    
    async def detect_spoofing(
        self,
        account_id: int,
        instrument_id: UUID,
        time_window_minutes: int = 5,
        db: AsyncSession = None
    ) -> Optional[SurveillanceAlert]:
        """
        Detect spoofing pattern: Orders placed and cancelled without execution.
        
        Pattern: Many orders placed but quickly cancelled without being filled.
        """
        cutoff = datetime.utcnow() - timedelta(minutes=time_window_minutes)
        
        # Get cancelled orders for account/instrument
        stmt = select(Order).where(
            and_(
                Order.account_id == account_id,
                Order.instrument_id == instrument_id,
                Order.status == OrderStatus.CANCELLED,
                Order.created_at >= cutoff
            )
        )
        result = await db.execute(stmt)
        cancelled_orders = result.scalars().all()
        
        # Get filled orders
        stmt = select(Order).where(
            and_(
                Order.account_id == account_id,
                Order.instrument_id == instrument_id,
                Order.status == OrderStatus.FILLED,
                Order.created_at >= cutoff
            )
        )
        result = await db.execute(stmt)
        filled_orders = result.scalars().all()
        
        # Calculate ratio
        if len(cancelled_orders) == 0:
            return None
        
        cancel_ratio = len(cancelled_orders) / (len(cancelled_orders) + len(filled_orders) + 0.01)
        
        # Threshold: >80% cancellation is suspicious
        if cancel_ratio > 0.8:
            alert = SurveillanceAlert(
                anomaly_type=AnomalyType.SPOOFING,
                severity="high",
                account_id=account_id,
                instrument_id=instrument_id,
                description=f"Spoofing detected: {cancel_ratio:.1%} orders cancelled without fill",
                evidence={
                    "cancelled_count": len(cancelled_orders),
                    "filled_count": len(filled_orders),
                    "cancel_ratio": cancel_ratio,
                    "time_window_minutes": time_window_minutes
                },
                detected_at=datetime.utcnow()
            )
            
            db.add(alert)
            await db.flush()
            
            logger.warning(
                f"Spoofing detected for account {account_id}: "
                f"{cancel_ratio:.1%} cancellation rate"
            )
            
            return alert
        
        return None
    
    async def detect_wash_trading(
        self,
        account_id: int,
        instrument_id: UUID,
        time_window_minutes: int = 30,
        db: AsyncSession = None
    ) -> Optional[SurveillanceAlert]:
        """
        Detect wash trading: Same account buying and selling same instrument rapidly.
        
        Pattern: Account executes both buy and sell of same security within short time.
        """
        cutoff = datetime.utcnow() - timedelta(minutes=time_window_minutes)
        
        # Get all trades for account/instrument
        stmt = select(Trade).where(
            and_(
                Trade.created_at >= cutoff
            )
        )
        result = await db.execute(stmt)
        all_trades = result.scalars().all()
        
        # Find if same account appears on both sides
        for trade in all_trades:
            if (trade.buyer_account_id == account_id and 
                trade.instrument_id == instrument_id):
                # This account was buyer - look for sell
                seller_trades = [t for t in all_trades 
                                if t.seller_account_id == account_id 
                                and t.instrument_id == instrument_id
                                and abs((t.execution_timestamp - trade.execution_timestamp).total_seconds()) < 300]
                
                if seller_trades:
                    alert = SurveillanceAlert(
                        anomaly_type=AnomalyType.WASH_TRADE,
                        severity="critical",
                        account_id=account_id,
                        instrument_id=instrument_id,
                        description=f"Wash trading detected: Account bought and sold {len(seller_trades)} time(s)",
                        evidence={
                            "buy_trade_id": trade.id,
                            "sell_trade_ids": [t.id for t in seller_trades],
                            "time_window_seconds": 300
                        },
                        trade_ids=[trade.id] + [t.id for t in seller_trades],
                        detected_at=datetime.utcnow()
                    )
                    
                    db.add(alert)
                    await db.flush()
                    
                    logger.critical(
                        f"Wash trading detected for account {account_id}: "
                        f"Matched {len(seller_trades)} buy/sell pairs"
                    )
                    
                    return alert
        
        return None
    
    async def detect_front_running(
        self,
        account_id: int,
        time_window_seconds: int = 10,
        db: AsyncSession = None
    ) -> Optional[SurveillanceAlert]:
        """
        Detect front-running: Account trades before large order from different account.
        
        Pattern: Small account trades just before large order from client.
        """
        cutoff = datetime.utcnow() - timedelta(seconds=time_window_seconds)
        
        # Get large orders
        stmt = select(Order).where(
            and_(
                Order.created_at >= cutoff,
                Order.quantity > 1000.0  # Large size threshold
            )
        )
        result = await db.execute(stmt)
        large_orders = result.scalars().all()
        
        for large_order in large_orders:
            # Look for preceding trades by different account in same direction
            preceding_trades = await self._find_preceding_trades(
                account_id=account_id,
                instrument_id=large_order.instrument_id,
                side=large_order.side,
                before_time=large_order.created_at,
                window_seconds=time_window_seconds,
                db=db
            )
            
            if preceding_trades and len(preceding_trades) > 2:
                alert = SurveillanceAlert(
                    anomaly_type=AnomalyType.FRONT_RUNNING,
                    severity="high",
                    account_id=account_id,
                    instrument_id=large_order.instrument_id,
                    description=f"Front-running suspected: {len(preceding_trades)} trades before large order",
                    evidence={
                        "preceding_trades": len(preceding_trades),
                        "large_order_id": large_order.id,
                        "large_order_size": large_order.quantity,
                        "window_seconds": time_window_seconds
                    },
                    trade_ids=[t.id for t in preceding_trades],
                    order_ids=[large_order.id],
                    detected_at=datetime.utcnow()
                )
                
                db.add(alert)
                await db.flush()
                
                logger.warning(
                    f"Front-running suspected for account {account_id}: "
                    f"{len(preceding_trades)} trades before large order"
                )
                
                return alert
        
        return None
    
    async def detect_unusual_volume(
        self,
        instrument_id: UUID,
        std_devs: float = 3.0,
        db: AsyncSession = None
    ) -> Optional[SurveillanceAlert]:
        """
        Detect unusual volume surge.
        
        Pattern: Volume exceeds N standard deviations above average.
        """
        # Get last 30 days of volume data
        cutoff = datetime.utcnow() - timedelta(days=30)
        
        stmt = select(
            func.date(Trade.execution_timestamp),
            func.sum(Trade.quantity).label("daily_volume")
        ).where(
            and_(
                Trade.instrument_id == instrument_id,
                Trade.execution_timestamp >= cutoff
            )
        ).group_by(func.date(Trade.execution_timestamp))
        
        result = await db.execute(stmt)
        volumes = [row.daily_volume for row in result.all()]
        
        if len(volumes) < 5:
            return None  # Not enough data
        
        # Calculate mean and std dev
        import statistics
        mean_volume = statistics.mean(volumes)
        std_dev = statistics.stdev(volumes)
        
        # Get today's volume
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = select(func.sum(Trade.quantity)).where(
            and_(
                Trade.instrument_id == instrument_id,
                Trade.execution_timestamp >= today_start
            )
        )
        result = await db.execute(stmt)
        today_volume = result.scalar() or 0
        
        # Check if above threshold
        threshold = mean_volume + (std_devs * std_dev)
        if today_volume > threshold:
            alert = SurveillanceAlert(
                anomaly_type=AnomalyType.UNUSUAL_VOLUME,
                severity="medium",
                instrument_id=instrument_id,
                description=f"Unusual volume surge: {today_volume:.0f} vs avg {mean_volume:.0f}",
                evidence={
                    "today_volume": today_volume,
                    "average_volume": mean_volume,
                    "std_devs": std_devs,
                    "threshold": threshold
                },
                detected_at=datetime.utcnow()
            )
            
            db.add(alert)
            await db.flush()
            
            logger.info(
                f"Unusual volume detected for {instrument_id}: "
                f"{today_volume:.0f} vs avg {mean_volume:.0f}"
            )
            
            return alert
        
        return None
    
    async def resolve_alert(
        self,
        alert_id: int,
        resolution: str,
        resolved_by: str,
        db: AsyncSession = None
    ) -> SurveillanceAlert:
        """Mark alert as resolved."""
        stmt = select(SurveillanceAlert).where(SurveillanceAlert.id == alert_id)
        result = await db.execute(stmt)
        alert = result.scalars().first()
        
        if not alert:
            raise ValueError(f"Alert {alert_id} not found")
        
        alert.is_resolved = True
        alert.resolution = resolution
        alert.resolved_by = resolved_by
        alert.resolved_at = datetime.utcnow()
        
        await db.flush()
        
        logger.info(f"Resolved alert {alert_id}: {resolution}")
        return alert
    
    async def get_active_alerts(
        self,
        account_id: Optional[int] = None,
        severity: Optional[str] = None,
        db: AsyncSession = None
    ) -> List[SurveillanceAlert]:
        """Get active (unresolved) alerts."""
        stmt = select(SurveillanceAlert).where(
            SurveillanceAlert.is_resolved == False
        )
        
        if account_id:
            stmt = stmt.where(SurveillanceAlert.account_id == account_id)
        
        if severity:
            stmt = stmt.where(SurveillanceAlert.severity == severity)
        
        stmt = stmt.order_by(SurveillanceAlert.detected_at.desc())
        
        result = await db.execute(stmt)
        return result.scalars().all()
    
    async def _find_preceding_trades(
        self,
        account_id: int,
        instrument_id: UUID,
        side: str,
        before_time: datetime,
        window_seconds: int,
        db: AsyncSession
    ) -> List[Trade]:
        """Find trades preceding a given time."""
        cutoff = before_time - timedelta(seconds=window_seconds)
        
        stmt = select(Trade).where(
            and_(
                Trade.buyer_account_id == account_id if side == "BUY" else Trade.seller_account_id == account_id,
                Trade.instrument_id == instrument_id,
                Trade.execution_timestamp >= cutoff,
                Trade.execution_timestamp < before_time
            )
        )
        
        result = await db.execute(stmt)
        return result.scalars().all()


# Global surveillance service instance
_surveillance_service: Optional['SurveillanceService'] = None


def get_surveillance_service() -> SurveillanceService:
    """Get or create surveillance service."""
    global _surveillance_service
    if _surveillance_service is None:
        _surveillance_service = SurveillanceService()
    return _surveillance_service
