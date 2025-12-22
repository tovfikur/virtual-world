"""
Margin call detection and liquidation service.
Monitors margin levels and automatically liquidates positions when necessary.
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import logging

from app.models.account import Account, Position, MarginCall, AccountStatus
from app.services.margin_service import get_margin_service
from app.services.matching_service import get_matching_service
from app.models.order import Order, OrderSide, OrderType

logger = logging.getLogger(__name__)


class LiquidationService:
    """
    Monitors margin levels and executes forced liquidations.
    
    Margin Thresholds:
    - Margin Call: margin_level < margin_call_level (default 100%)
    - Liquidation: margin_level < liquidation_level (default 50%)
    """
    
    def __init__(self):
        self.margin_service = get_margin_service()
        self.matching_service = get_matching_service()
    
    async def check_margin_levels(
        self,
        account: Account,
        db: AsyncSession
    ) -> Optional[str]:
        """
        Check account margin level and take action if necessary.
        
        Returns:
            Action taken: "MARGIN_CALL", "LIQUIDATION", or None
        """
        # Skip if account is already in liquidation
        if account.status == AccountStatus.LIQUIDATING:
            return None
        
        # Recalculate equity and margin
        equity, used_margin, free_margin = await self.margin_service.calculate_account_equity(
            account, db
        )
        
        # No positions = no margin issues
        if used_margin == 0:
            return None
        
        margin_level = (equity / used_margin) * 100
        
        # Liquidation threshold
        if margin_level < account.liquidation_level:
            logger.warning(
                f"Account {account.id} margin level {margin_level:.2f}% "
                f"below liquidation threshold {account.liquidation_level:.2f}%"
            )
            await self._trigger_liquidation(account, margin_level, equity, used_margin, db)
            return "LIQUIDATION"
        
        # Margin call threshold
        if margin_level < account.margin_call_level:
            logger.warning(
                f"Account {account.id} margin level {margin_level:.2f}% "
                f"below margin call threshold {account.margin_call_level:.2f}%"
            )
            await self._trigger_margin_call(account, margin_level, equity, used_margin, db)
            return "MARGIN_CALL"
        
        return None
    
    async def _trigger_margin_call(
        self,
        account: Account,
        margin_level: float,
        equity: float,
        used_margin: float,
        db: AsyncSession
    ) -> None:
        """Record a margin call event."""
        # Create margin call record
        margin_call = MarginCall(
            account_id=account.id,
            margin_level=margin_level,
            equity=equity,
            used_margin=used_margin,
            action="MARGIN_CALL",
            resolved=False
        )
        db.add(margin_call)
        
        # Update account status
        if account.status != AccountStatus.MARGIN_CALL:
            account.status = AccountStatus.MARGIN_CALL
        
        await db.flush()
        
        # TODO: Send notification to user (email, push notification)
        logger.info(f"Margin call issued for account {account.id}")
    
    async def _trigger_liquidation(
        self,
        account: Account,
        margin_level: float,
        equity: float,
        used_margin: float,
        db: AsyncSession
    ) -> None:
        """
        Force liquidate account positions.
        
        Liquidation Process:
        1. Set account to LIQUIDATING status
        2. Cancel all pending orders
        3. Close positions one by one (starting with worst performing)
        4. Continue until margin level recovers or all positions closed
        """
        # Create liquidation record
        margin_call = MarginCall(
            account_id=account.id,
            margin_level=margin_level,
            equity=equity,
            used_margin=used_margin,
            action="LIQUIDATION",
            resolved=False
        )
        db.add(margin_call)
        
        # Set account to liquidating
        account.status = AccountStatus.LIQUIDATING
        await db.flush()
        
        logger.critical(f"Liquidation started for account {account.id}")
        
        # Cancel all pending orders
        await self._cancel_pending_orders(account.id, db)
        
        # Get all open positions
        positions = await self.margin_service.get_account_positions(account.id, db)
        
        if not positions:
            logger.warning(f"No positions to liquidate for account {account.id}")
            account.status = AccountStatus.ACTIVE
            margin_call.resolved = True
            await db.flush()
            return
        
        # Sort by P&L (worst first)
        positions.sort(key=lambda p: p.unrealized_pnl)
        
        # Liquidate positions
        for position in positions:
            try:
                await self._liquidate_position(position, account, db)
            except Exception as e:
                logger.error(f"Failed to liquidate position {position.id}: {e}")
        
        # Recalculate margin after liquidation
        equity, used_margin, free_margin = await self.margin_service.calculate_account_equity(
            account, db
        )
        
        # Check if liquidation resolved the issue
        if used_margin == 0 or (equity / used_margin * 100) > account.margin_call_level:
            account.status = AccountStatus.ACTIVE
            margin_call.resolved = True
            logger.info(f"Liquidation resolved for account {account.id}")
        else:
            # Still under margin - keep liquidating
            logger.warning(f"Liquidation incomplete for account {account.id}")
        
        await db.flush()
    
    async def _liquidate_position(
        self,
        position: Position,
        account: Account,
        db: AsyncSession
    ) -> None:
        """
        Force close a position at market price.
        
        Creates a market order to close the position immediately.
        """
        # Determine order side (opposite of position)
        order_side = OrderSide.SELL if position.side == "LONG" else OrderSide.BUY
        
        logger.info(
            f"Liquidating position {position.id}: {position.side} "
            f"{position.quantity} @ {position.entry_price}"
        )
        
        # Create liquidation order (market order to close)
        order = Order(
            user_id=account.user_id,
            instrument_id=position.instrument_id,
            side=order_side,
            order_type=OrderType.MARKET,
            quantity=position.quantity,
            price=None,  # Market order
            status="NEW"
        )
        db.add(order)
        await db.flush()
        
        # Execute through matching engine
        try:
            await self.matching_service.match_order(order, db)
            logger.info(f"Position {position.id} liquidated via order {order.id}")
        except Exception as e:
            logger.error(f"Failed to execute liquidation order {order.id}: {e}")
            raise
    
    async def _cancel_pending_orders(
        self,
        account_id: int,
        db: AsyncSession
    ) -> None:
        """Cancel all pending orders for an account."""
        # Get account's user_id
        stmt = select(Account.user_id).where(Account.id == account_id)
        result = await db.execute(stmt)
        user_id = result.scalar_one_or_none()
        
        if not user_id:
            return
        
        # Get all open orders
        stmt = select(Order).where(
            and_(
                Order.user_id == user_id,
                Order.status.in_(["NEW", "PARTIALLY_FILLED"])
            )
        )
        result = await db.execute(stmt)
        orders = result.scalars().all()
        
        # Cancel each order
        for order in orders:
            try:
                await self.matching_service.cancel_order(order.id, db)
                logger.info(f"Cancelled order {order.id} due to liquidation")
            except Exception as e:
                logger.error(f"Failed to cancel order {order.id}: {e}")
    
    async def monitor_all_accounts(self, db: AsyncSession) -> dict:
        """
        Monitor margin levels for all active accounts.
        
        This should be called periodically (e.g., every minute).
        
        Returns:
            Statistics: {
                "checked": int,
                "margin_calls": int,
                "liquidations": int
            }
        """
        stats = {
            "checked": 0,
            "margin_calls": 0,
            "liquidations": 0
        }
        
        # Get all accounts with open positions
        stmt = select(Account).where(
            Account.status.in_([AccountStatus.ACTIVE, AccountStatus.MARGIN_CALL])
        )
        result = await db.execute(stmt)
        accounts = result.scalars().all()
        
        for account in accounts:
            stats["checked"] += 1
            
            try:
                action = await self.check_margin_levels(account, db)
                
                if action == "MARGIN_CALL":
                    stats["margin_calls"] += 1
                elif action == "LIQUIDATION":
                    stats["liquidations"] += 1
            
            except Exception as e:
                logger.error(f"Error checking account {account.id}: {e}")
        
        await db.commit()
        
        if stats["margin_calls"] > 0 or stats["liquidations"] > 0:
            logger.info(f"Margin monitoring: {stats}")
        
        return stats


# Global liquidation service instance
_liquidation_service: Optional[LiquidationService] = None


def get_liquidation_service() -> LiquidationService:
    """Get or create global liquidation service."""
    global _liquidation_service
    if _liquidation_service is None:
        _liquidation_service = LiquidationService()
    return _liquidation_service
