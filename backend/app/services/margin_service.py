"""
Margin calculation service.
Computes margin requirements, equity, margin levels, and handles position tracking.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from uuid import UUID
import logging

from app.models.account import Account, Position, AccountStatus
from app.models.instrument import Instrument
from app.models.order import Order, OrderSide
from app.services.pricing_service import get_pricing_engine

logger = logging.getLogger(__name__)


class MarginCalculationService:
    """
    Calculates margin requirements and tracks account equity.
    
    Margin Calculation:
    - Used Margin = sum of margin required by all open positions
    - Free Margin = Equity - Used Margin
    - Margin Level = (Equity / Used Margin) * 100
    
    Position Margin:
    - For leveraged positions: notional / leverage
    - For unleveraged: full notional value
    """
    
    async def calculate_account_equity(
        self,
        account: Account,
        db: AsyncSession
    ) -> Tuple[float, float, float]:
        """
        Calculate account equity and margin metrics.
        
        Returns:
            (equity, used_margin, free_margin)
        """
        # Get all open positions
        stmt = select(Position).where(
            and_(
                Position.account_id == account.id,
                Position.closed_at.is_(None)
            )
        )
        result = await db.execute(stmt)
        positions = result.scalars().all()
        
        # Calculate total unrealized P&L
        total_unrealized_pnl = 0.0
        total_used_margin = 0.0
        
        for position in positions:
            # Update position with current market price
            await self._update_position_price(position, db)
            
            # Calculate unrealized P&L
            pnl = self._calculate_position_pnl(position)
            position.unrealized_pnl = pnl
            total_unrealized_pnl += pnl
            
            # Add margin used by this position
            total_used_margin += position.margin_used
        
        # Equity = Balance + Unrealized P&L
        equity = account.balance + total_unrealized_pnl
        
        # Free Margin = Equity - Used Margin
        free_margin = equity - total_used_margin
        
        # Update account
        account.equity = equity
        account.used_margin = total_used_margin
        account.free_margin = free_margin
        
        # Margin Level = (Equity / Used Margin) * 100
        if total_used_margin > 0:
            account.margin_level = (equity / total_used_margin) * 100
        else:
            account.margin_level = None  # No margin used
        
        return equity, total_used_margin, free_margin
    
    async def _update_position_price(
        self,
        position: Position,
        db: AsyncSession
    ) -> None:
        """Update position with current market price."""
        pricing_engine = get_pricing_engine()
        quote = await pricing_engine.get_aggregated_quote(position.instrument_id, db)
        
        if quote:
            # Use mid price for position valuation
            position.current_price = quote['mid']
        else:
            # Keep last known price if no quote available
            if position.current_price is None:
                position.current_price = position.entry_price
    
    def _calculate_position_pnl(self, position: Position) -> float:
        """
        Calculate unrealized P&L for a position.
        
        Long: (current_price - entry_price) * quantity
        Short: (entry_price - current_price) * quantity
        """
        if position.current_price is None:
            return 0.0
        
        if position.side == "LONG":
            pnl = (position.current_price - position.entry_price) * position.quantity
        else:  # SHORT
            pnl = (position.entry_price - position.current_price) * position.quantity
        
        # Subtract accumulated swap fees
        pnl -= position.swap_accumulated
        
        return pnl
    
    async def calculate_position_margin(
        self,
        instrument_id: UUID,
        quantity: float,
        price: float,
        leverage: float,
        db: AsyncSession
    ) -> float:
        """
        Calculate margin required for a position.
        
        Args:
            instrument_id: Instrument UUID
            quantity: Position size
            price: Entry price
            leverage: Leverage to use (e.g., 50.0 for 50:1)
            db: Database session
            
        Returns:
            Margin required in account currency
        """
        # Get instrument
        stmt = select(Instrument).where(Instrument.instrument_id == instrument_id)
        result = await db.execute(stmt)
        instrument = result.scalars().first()
        
        if not instrument:
            raise ValueError("Instrument not found")
        
        # Notional value = quantity * price
        notional = quantity * price
        
        # Margin = notional / leverage (if leverage allowed)
        if instrument.is_margin_allowed and leverage > 1.0:
            # Enforce max leverage limit
            effective_leverage = min(leverage, float(instrument.leverage_max))
            margin = notional / effective_leverage
        else:
            # No leverage: full notional
            margin = notional
        
        return margin
    
    async def check_margin_sufficiency(
        self,
        account: Account,
        additional_margin: float,
        db: AsyncSession
    ) -> Tuple[bool, str]:
        """
        Check if account has sufficient free margin for a new position.
        
        Args:
            account: Account to check
            additional_margin: Margin required for new position
            db: Database session
            
        Returns:
            (is_sufficient, message)
        """
        # Recalculate equity and margins
        equity, used_margin, free_margin = await self.calculate_account_equity(account, db)
        
        # Check if free margin covers additional requirement
        if free_margin >= additional_margin:
            return True, "Sufficient margin"
        
        deficit = additional_margin - free_margin
        return False, f"Insufficient margin: need {additional_margin:.2f}, have {free_margin:.2f} free (deficit: {deficit:.2f})"
    
    async def open_position(
        self,
        account: Account,
        instrument_id: UUID,
        side: str,
        quantity: float,
        entry_price: float,
        leverage: float,
        db: AsyncSession
    ) -> Position:
        """
        Open a new position and update account margin.
        
        Args:
            account: Account to open position in
            instrument_id: Instrument UUID
            side: "LONG" or "SHORT"
            quantity: Position size
            entry_price: Entry price
            leverage: Leverage used
            db: Database session
            
        Returns:
            Created Position
        """
        # Calculate margin required
        margin_required = await self.calculate_position_margin(
            instrument_id,
            quantity,
            entry_price,
            leverage,
            db
        )
        
        # Check margin sufficiency
        is_sufficient, msg = await self.check_margin_sufficiency(account, margin_required, db)
        if not is_sufficient:
            raise ValueError(msg)
        
        # Create position
        position = Position(
            account_id=account.id,
            instrument_id=instrument_id,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            current_price=entry_price,
            margin_used=margin_required,
            leverage_used=leverage,
        )
        db.add(position)
        
        # Update account margin
        account.used_margin += margin_required
        account.free_margin -= margin_required
        
        await db.flush()
        logger.info(f"Opened {side} position: {quantity}@{entry_price} for account {account.id}")
        
        return position
    
    async def close_position(
        self,
        position: Position,
        close_price: float,
        db: AsyncSession
    ) -> float:
        """
        Close a position and realize P&L.
        
        Args:
            position: Position to close
            close_price: Closing price
            db: Database session
            
        Returns:
            Realized P&L
        """
        # Calculate realized P&L
        position.current_price = close_price
        realized_pnl = self._calculate_position_pnl(position)
        position.realized_pnl = realized_pnl
        position.closed_at = datetime.utcnow()
        
        # Get account
        stmt = select(Account).where(Account.id == position.account_id)
        result = await db.execute(stmt)
        account = result.scalars().first()
        
        if account:
            # Release margin
            account.used_margin -= position.margin_used
            
            # Add realized P&L to balance
            account.balance += realized_pnl
            
            # Recalculate equity
            await self.calculate_account_equity(account, db)
        
        await db.flush()
        logger.info(f"Closed position {position.id}: realized P&L = {realized_pnl:.2f}")
        
        return realized_pnl
    
    async def get_account_positions(
        self,
        account_id: int,
        db: AsyncSession,
        include_closed: bool = False
    ) -> List[Position]:
        """Get all positions for an account."""
        stmt = select(Position).where(Position.account_id == account_id)
        
        if not include_closed:
            stmt = stmt.where(Position.closed_at.is_(None))
        
        result = await db.execute(stmt)
        return result.scalars().all()
    
    async def get_exposure_per_instrument(
        self,
        account_id: int,
        instrument_id: UUID,
        db: AsyncSession
    ) -> float:
        """
        Get total exposure (notional value) for an instrument.
        
        Returns:
            Total notional exposure (positive for long, negative for short)
        """
        stmt = select(Position).where(
            and_(
                Position.account_id == account_id,
                Position.instrument_id == instrument_id,
                Position.closed_at.is_(None)
            )
        )
        result = await db.execute(stmt)
        positions = result.scalars().all()
        
        total_exposure = 0.0
        for pos in positions:
            notional = pos.quantity * (pos.current_price or pos.entry_price)
            if pos.side == "LONG":
                total_exposure += notional
            else:
                total_exposure -= notional
        
        return total_exposure


# Global margin calculation service instance
_margin_service: Optional[MarginCalculationService] = None


def get_margin_service() -> MarginCalculationService:
    """Get or create global margin calculation service."""
    global _margin_service
    if _margin_service is None:
        _margin_service = MarginCalculationService()
    return _margin_service
