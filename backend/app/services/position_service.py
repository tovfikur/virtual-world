"""
Position management service.
Handles position lifecycle: open, add, hedge, close, partial close, reverse.
Supports both net and hedged position modes.
"""

from typing import List, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from uuid import UUID
from datetime import datetime
import logging

from app.models.account import Account, Position
from app.models.instrument import Instrument
from app.services.margin_service import get_margin_service
from app.services.pnl_service import get_pnl_service
from app.services.pricing_service import get_pricing_engine

logger = logging.getLogger(__name__)


class PositionMode:
    """Position tracking modes."""
    NET = "net"       # Single position per instrument (combine long/short)
    HEDGED = "hedged"  # Separate long and short positions


class PositionService:
    """
    Manages position lifecycle and operations.
    
    Position Modes:
    - Net Mode: Only one position per instrument, automatically nets out
    - Hedged Mode: Can have separate long and short positions
    
    Operations:
    - Add: Increase existing position size
    - Hedge: Open opposite position (hedged mode only)
    - Close: Close entire position
    - Partial Close: Close portion of position
    - Reverse: Close current and open opposite position
    """
    
    def __init__(self, mode: str = PositionMode.NET):
        """
        Initialize position service.
        
        Args:
            mode: "net" or "hedged"
        """
        self.mode = mode
        self.margin_service = get_margin_service()
        self.pnl_service = get_pnl_service()
    
    async def get_position(
        self,
        account_id: int,
        instrument_id: UUID,
        side: Optional[str] = None,
        db: AsyncSession = None
    ) -> Optional[Position]:
        """
        Get existing position.
        
        In net mode, returns the net position regardless of side.
        In hedged mode, returns position for specific side.
        """
        stmt = select(Position).where(
            and_(
                Position.account_id == account_id,
                Position.instrument_id == instrument_id,
                Position.closed_at.is_(None)
            )
        )
        
        if self.mode == PositionMode.HEDGED and side:
            stmt = stmt.where(Position.side == side)
        
        result = await db.execute(stmt)
        return result.scalars().first()
    
    async def add_to_position(
        self,
        account: Account,
        instrument_id: UUID,
        side: str,
        quantity: float,
        price: float,
        leverage: float,
        db: AsyncSession
    ) -> Position:
        """
        Add to existing position or create new one.
        
        Net Mode: Adds to existing if same side, reduces if opposite
        Hedged Mode: Always adds to specific side
        """
        existing = await self.get_position(
            account.id, instrument_id, side, db
        )
        
        if self.mode == PositionMode.NET:
            # Check for opposite side position
            opposite_side = "SHORT" if side == "LONG" else "LONG"
            opposite_pos = await self.get_position(
                account.id, instrument_id, opposite_side, db
            )
            
            if opposite_pos:
                # Reduce opposite position (netting)
                return await self._net_positions(
                    account, opposite_pos, quantity, price, db
                )
        
        if existing:
            # Add to existing position
            return await self._increase_position(
                existing, quantity, price, leverage, db
            )
        else:
            # Open new position
            return await self.margin_service.open_position(
                account, instrument_id, side, quantity, price, leverage, db
            )
    
    async def _increase_position(
        self,
        position: Position,
        additional_quantity: float,
        price: float,
        leverage: float,
        db: AsyncSession
    ) -> Position:
        """Increase existing position size."""
        # Calculate new VWAP entry price
        old_notional = position.quantity * position.entry_price
        new_notional = additional_quantity * price
        total_quantity = position.quantity + additional_quantity
        
        new_entry_price = (old_notional + new_notional) / total_quantity
        
        # Calculate additional margin required
        additional_margin = await self.margin_service.calculate_position_margin(
            position.instrument_id,
            additional_quantity,
            price,
            leverage,
            db
        )
        
        # Get account
        stmt = select(Account).where(Account.id == position.account_id)
        result = await db.execute(stmt)
        account = result.scalars().first()
        
        # Check margin sufficiency
        is_sufficient, msg = await self.margin_service.check_margin_sufficiency(
            account, additional_margin, db
        )
        if not is_sufficient:
            raise ValueError(msg)
        
        # Update position
        position.quantity = total_quantity
        position.entry_price = new_entry_price
        position.margin_used += additional_margin
        
        # Update account margin
        account.used_margin += additional_margin
        account.free_margin -= additional_margin
        
        await db.flush()
        
        logger.info(
            f"Increased position {position.id}: +{additional_quantity} @ {price}, "
            f"new entry VWAP: {new_entry_price:.5f}"
        )
        
        return position
    
    async def _net_positions(
        self,
        account: Account,
        opposite_pos: Position,
        quantity: float,
        price: float,
        db: AsyncSession
    ) -> Position:
        """
        Net out opposite positions (net mode only).
        
        If new quantity > opposite quantity: Close opposite, open remainder
        If new quantity < opposite quantity: Reduce opposite
        If equal: Close opposite
        """
        if quantity > opposite_pos.quantity:
            # Close opposite, open new position with remainder
            await self.close_position(opposite_pos, price, db)
            
            remainder = quantity - opposite_pos.quantity
            new_side = "SHORT" if opposite_pos.side == "LONG" else "LONG"
            
            return await self.margin_service.open_position(
                account,
                opposite_pos.instrument_id,
                new_side,
                remainder,
                price,
                opposite_pos.leverage_used,
                db
            )
        
        elif quantity < opposite_pos.quantity:
            # Partial close of opposite position
            return await self.partial_close(
                opposite_pos, quantity, price, db
            )
        
        else:
            # Exact net: close opposite position
            await self.close_position(opposite_pos, price, db)
            return opposite_pos
    
    async def hedge_position(
        self,
        account: Account,
        instrument_id: UUID,
        quantity: float,
        price: float,
        leverage: float,
        db: AsyncSession
    ) -> Position:
        """
        Open hedge position (hedged mode only).
        
        Opens opposite side of existing position to hedge risk.
        """
        if self.mode != PositionMode.HEDGED:
            raise ValueError("Hedging only available in hedged position mode")
        
        # Get existing position
        existing_long = await self.get_position(
            account.id, instrument_id, "LONG", db
        )
        existing_short = await self.get_position(
            account.id, instrument_id, "SHORT", db
        )
        
        if existing_long and not existing_short:
            # Open short hedge
            return await self.margin_service.open_position(
                account, instrument_id, "SHORT", quantity, price, leverage, db
            )
        elif existing_short and not existing_long:
            # Open long hedge
            return await self.margin_service.open_position(
                account, instrument_id, "LONG", quantity, price, leverage, db
            )
        else:
            raise ValueError("Cannot hedge: position state unclear")
    
    async def close_position(
        self,
        position: Position,
        close_price: float,
        db: AsyncSession
    ) -> float:
        """
        Close entire position.
        
        Returns:
            Realized P&L
        """
        realized_pnl = await self.margin_service.close_position(
            position, close_price, db
        )
        
        logger.info(
            f"Closed position {position.id}: {position.side} {position.quantity} "
            f"@ {close_price}, P&L: {realized_pnl:.2f}"
        )
        
        return realized_pnl
    
    async def partial_close(
        self,
        position: Position,
        close_quantity: float,
        close_price: float,
        db: AsyncSession
    ) -> float:
        """
        Close portion of position.
        
        Args:
            position: Position to partially close
            close_quantity: Amount to close
            close_price: Closing price
            
        Returns:
            Realized P&L from closed portion
        """
        if close_quantity >= position.quantity:
            # Full close
            return await self.close_position(position, close_price, db)
        
        # Calculate P&L for closed portion
        if position.side == "LONG":
            pnl_per_unit = close_price - position.entry_price
        else:  # SHORT
            pnl_per_unit = position.entry_price - close_price
        
        partial_pnl = pnl_per_unit * close_quantity
        
        # Proportional swap fees
        partial_swap = position.swap_accumulated * (close_quantity / position.quantity)
        partial_pnl -= partial_swap
        
        # Release proportional margin
        released_margin = position.margin_used * (close_quantity / position.quantity)
        
        # Update position
        position.quantity -= close_quantity
        position.margin_used -= released_margin
        position.realized_pnl += partial_pnl
        position.swap_accumulated -= partial_swap
        
        # Get account
        stmt = select(Account).where(Account.id == position.account_id)
        result = await db.execute(stmt)
        account = result.scalars().first()
        
        if account:
            # Release margin
            account.used_margin -= released_margin
            
            # Add realized P&L to balance
            account.balance += partial_pnl
            
            # Recalculate equity
            await self.margin_service.calculate_account_equity(account, db)
        
        await db.flush()
        
        logger.info(
            f"Partial close position {position.id}: -{close_quantity} @ {close_price}, "
            f"P&L: {partial_pnl:.2f}, remaining: {position.quantity}"
        )
        
        return partial_pnl
    
    async def reverse_position(
        self,
        position: Position,
        new_quantity: float,
        reverse_price: float,
        db: AsyncSession
    ) -> Position:
        """
        Reverse position: close current and open opposite.
        
        Example: Close LONG 100, open SHORT 100
        """
        # Close existing position
        await self.close_position(position, reverse_price, db)
        
        # Get account
        stmt = select(Account).where(Account.id == position.account_id)
        result = await db.execute(stmt)
        account = result.scalars().first()
        
        # Open opposite position
        opposite_side = "SHORT" if position.side == "LONG" else "LONG"
        
        new_position = await self.margin_service.open_position(
            account,
            position.instrument_id,
            opposite_side,
            new_quantity,
            reverse_price,
            position.leverage_used,
            db
        )
        
        logger.info(
            f"Reversed position: closed {position.side} {position.quantity}, "
            f"opened {opposite_side} {new_quantity}"
        )
        
        return new_position
    
    async def get_all_positions(
        self,
        account_id: int,
        db: AsyncSession,
        include_closed: bool = False
    ) -> List[Position]:
        """Get all positions for account."""
        stmt = select(Position).where(Position.account_id == account_id)
        
        if not include_closed:
            stmt = stmt.where(Position.closed_at.is_(None))
        
        stmt = stmt.order_by(Position.opened_at.desc())
        
        result = await db.execute(stmt)
        return result.scalars().all()
    
    async def update_position_prices(
        self,
        account_id: int,
        db: AsyncSession
    ) -> None:
        """Update all open positions with current market prices."""
        positions = await self.get_all_positions(account_id, db)
        pricing_engine = get_pricing_engine()
        
        for position in positions:
            quote = await pricing_engine.get_aggregated_quote(
                position.instrument_id, db
            )
            
            if quote:
                # Update position with current price
                old_price = position.current_price
                position.current_price = quote['mid']
                
                # Recalculate unrealized P&L
                pnl, pct_return = await self.pnl_service.calculate_position_pnl(
                    position, quote['mid']
                )
                position.unrealized_pnl = pnl
                
                if old_price and abs(position.current_price - old_price) > 0.0001:
                    logger.debug(
                        f"Updated position {position.id}: {old_price:.5f} → "
                        f"{position.current_price:.5f}, P&L: {pnl:.2f}"
                    )
        
        await db.flush()
    
    async def get_position_summary(
        self,
        account_id: int,
        db: AsyncSession
    ) -> Dict:
        """
        Get summary of all positions.
        
        Returns:
            {
                "open_positions": int,
                "total_exposure": float,
                "total_unrealized_pnl": float,
                "by_instrument": {...},
                "by_side": {"long": int, "short": int}
            }
        """
        positions = await self.get_all_positions(account_id, db)
        
        total_exposure = 0.0
        total_unrealized = 0.0
        by_instrument = {}
        long_count = 0
        short_count = 0
        
        for pos in positions:
            # Exposure
            notional = pos.quantity * (pos.current_price or pos.entry_price)
            total_exposure += notional
            
            # Unrealized P&L
            total_unrealized += pos.unrealized_pnl
            
            # By instrument
            inst_id = str(pos.instrument_id)
            if inst_id not in by_instrument:
                by_instrument[inst_id] = {
                    "positions": 0,
                    "total_quantity": 0.0,
                    "exposure": 0.0,
                    "unrealized_pnl": 0.0
                }
            
            by_instrument[inst_id]["positions"] += 1
            by_instrument[inst_id]["total_quantity"] += pos.quantity
            by_instrument[inst_id]["exposure"] += notional
            by_instrument[inst_id]["unrealized_pnl"] += pos.unrealized_pnl
            
            # By side
            if pos.side == "LONG":
                long_count += 1
            else:
                short_count += 1
        
        return {
            "open_positions": len(positions),
            "total_exposure": total_exposure,
            "total_unrealized_pnl": total_unrealized,
            "by_instrument": by_instrument,
            "by_side": {
                "long": long_count,
                "short": short_count
            }
        }


# Global position service instances
_position_service_net: Optional[PositionService] = None
_position_service_hedged: Optional[PositionService] = None


def get_position_service(mode: str = PositionMode.NET) -> PositionService:
    """Get or create position service for specified mode."""
    global _position_service_net, _position_service_hedged
    
    if mode == PositionMode.NET:
        if _position_service_net is None:
            _position_service_net = PositionService(mode=PositionMode.NET)
        return _position_service_net
    else:
        if _position_service_hedged is None:
            _position_service_hedged = PositionService(mode=PositionMode.HEDGED)
        return _position_service_hedged
