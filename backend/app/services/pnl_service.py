"""
Profit and Loss (PnL) calculation service.
Computes realized and unrealized P&L, VWAP, and portfolio aggregations.
"""

from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from uuid import UUID
from datetime import datetime
import logging

from app.models.account import Account, Position
from app.models.trade import Trade
from app.models.instrument import Instrument
from app.models.fee_schedule import Commission

logger = logging.getLogger(__name__)


class PnLCalculationService:
    """
    Calculates profit and loss for positions and portfolios.
    
    P&L Types:
    - Realized P&L: Locked-in profit/loss from closed positions
    - Unrealized P&L: Mark-to-market profit/loss from open positions
    - Total P&L: Realized + Unrealized
    
    Position Modes:
    - Net: Single position per instrument (combines long/short)
    - Hedged: Separate long and short positions allowed
    """
    
    def __init__(self, position_mode: str = "net"):
        """
        Initialize PnL service.
        
        Args:
            position_mode: "net" or "hedged"
        """
        self.position_mode = position_mode
    
    async def calculate_position_pnl(
        self,
        position: Position,
        current_price: float
    ) -> Tuple[float, float]:
        """
        Calculate P&L for a position.
        
        Args:
            position: Position object
            current_price: Current market price
            
        Returns:
            (unrealized_pnl, percent_return)
        """
        # Update current price
        position.current_price = current_price
        
        # Calculate P&L based on side
        if position.side == "LONG":
            pnl = (current_price - position.entry_price) * position.quantity
        else:  # SHORT
            pnl = (position.entry_price - current_price) * position.quantity
        
        # Subtract accumulated swap fees
        pnl -= position.swap_accumulated
        
        # Calculate percent return
        notional = position.entry_price * position.quantity
        percent_return = (pnl / notional) * 100 if notional > 0 else 0.0
        
        return pnl, percent_return
    
    async def calculate_realized_pnl(
        self,
        entry_price: float,
        close_price: float,
        quantity: float,
        side: str,
        commissions: float = 0.0,
        swap_fees: float = 0.0
    ) -> float:
        """
        Calculate realized P&L for a closed position.
        
        Args:
            entry_price: Opening price
            close_price: Closing price
            quantity: Position size
            side: "LONG" or "SHORT"
            commissions: Total commissions paid
            swap_fees: Total swap fees paid
            
        Returns:
            Realized P&L
        """
        if side == "LONG":
            pnl = (close_price - entry_price) * quantity
        else:  # SHORT
            pnl = (entry_price - close_price) * quantity
        
        # Deduct costs
        pnl -= commissions
        pnl -= swap_fees
        
        return pnl
    
    async def calculate_vwap(
        self,
        account_id: int,
        instrument_id: UUID,
        side: str,
        db: AsyncSession
    ) -> Optional[float]:
        """
        Calculate Volume Weighted Average Price for positions.
        
        Used to determine average entry price when multiple fills
        build up a position.
        
        Returns:
            VWAP or None if no trades
        """
        # Get all trades for this account/instrument/side
        stmt = select(Trade).where(
            and_(
                Trade.instrument_id == instrument_id,
                # Match side (if buying, we're long)
                Trade.buyer_id == account_id if side == "LONG" else Trade.seller_id == account_id
            )
        )
        
        result = await db.execute(stmt)
        trades = result.scalars().all()
        
        if not trades:
            return None
        
        # Calculate VWAP
        total_value = sum(t.price * t.quantity for t in trades)
        total_volume = sum(t.quantity for t in trades)
        
        vwap = total_value / total_volume if total_volume > 0 else None
        
        return vwap
    
    async def calculate_portfolio_pnl(
        self,
        account_id: int,
        db: AsyncSession
    ) -> Dict:
        """
        Calculate total P&L for entire portfolio.
        
        Returns:
            {
                "total_pnl": float,
                "realized_pnl": float,
                "unrealized_pnl": float,
                "open_positions": int,
                "closed_positions": int,
                "by_instrument": {...}
            }
        """
        # Get all positions (open and closed)
        stmt = select(Position).where(Position.account_id == account_id)
        result = await db.execute(stmt)
        positions = result.scalars().all()
        
        total_realized = 0.0
        total_unrealized = 0.0
        open_count = 0
        closed_count = 0
        by_instrument = {}
        
        for position in positions:
            if position.closed_at is None:
                # Open position - unrealized P&L
                open_count += 1
                total_unrealized += position.unrealized_pnl
                
                # Track by instrument
                inst_id = str(position.instrument_id)
                if inst_id not in by_instrument:
                    by_instrument[inst_id] = {
                        "realized": 0.0,
                        "unrealized": 0.0,
                        "open_positions": 0
                    }
                by_instrument[inst_id]["unrealized"] += position.unrealized_pnl
                by_instrument[inst_id]["open_positions"] += 1
            else:
                # Closed position - realized P&L
                closed_count += 1
                total_realized += position.realized_pnl
                
                # Track by instrument
                inst_id = str(position.instrument_id)
                if inst_id not in by_instrument:
                    by_instrument[inst_id] = {
                        "realized": 0.0,
                        "unrealized": 0.0,
                        "open_positions": 0
                    }
                by_instrument[inst_id]["realized"] += position.realized_pnl
        
        return {
            "total_pnl": total_realized + total_unrealized,
            "realized_pnl": total_realized,
            "unrealized_pnl": total_unrealized,
            "open_positions": open_count,
            "closed_positions": closed_count,
            "by_instrument": by_instrument
        }
    
    async def calculate_portfolio_return(
        self,
        account: Account,
        db: AsyncSession
    ) -> Dict:
        """
        Calculate portfolio return metrics.
        
        Returns:
            {
                "total_return": float,        # % return on initial balance
                "total_return_pct": float,
                "realized_return": float,
                "unrealized_return": float,
                "roi": float                  # Return on investment
            }
        """
        # Get initial balance (would need to track separately in production)
        # For now, approximate from current balance and realized P&L
        stmt = select(func.sum(Position.realized_pnl)).where(
            Position.account_id == account.id
        )
        result = await db.execute(stmt)
        total_realized = result.scalar() or 0.0
        
        # Estimate initial balance
        initial_balance = account.balance - total_realized
        if initial_balance <= 0:
            initial_balance = account.balance  # Fallback
        
        # Calculate returns
        total_return = account.equity - initial_balance
        total_return_pct = (total_return / initial_balance * 100) if initial_balance > 0 else 0.0
        
        # Get portfolio P&L
        portfolio_pnl = await self.calculate_portfolio_pnl(account.id, db)
        
        return {
            "total_return": total_return,
            "total_return_pct": total_return_pct,
            "realized_return": portfolio_pnl["realized_pnl"],
            "unrealized_return": portfolio_pnl["unrealized_pnl"],
            "roi": total_return_pct,
            "initial_balance": initial_balance,
            "current_equity": account.equity
        }
    
    async def calculate_daily_pnl(
        self,
        account_id: int,
        date: str,
        db: AsyncSession
    ) -> float:
        """
        Calculate P&L for a specific day.
        
        Sum of:
        - Realized P&L from closed positions
        - Change in unrealized P&L for open positions
        """
        # Get positions closed on this date
        stmt = select(Position).where(
            and_(
                Position.account_id == account_id,
                func.date(Position.closed_at) == date
            )
        )
        result = await db.execute(stmt)
        closed_positions = result.scalars().all()
        
        daily_realized = sum(p.realized_pnl for p in closed_positions)
        
        # TODO: Track daily snapshots of unrealized P&L for accurate calculation
        # For now, just return realized P&L
        
        return daily_realized
    
    async def calculate_win_rate(
        self,
        account_id: int,
        db: AsyncSession,
        instrument_id: Optional[UUID] = None
    ) -> Dict:
        """
        Calculate win rate statistics.
        
        Returns:
            {
                "win_rate": float,           # % of profitable trades
                "total_trades": int,
                "winning_trades": int,
                "losing_trades": int,
                "average_win": float,
                "average_loss": float,
                "profit_factor": float       # Avg win / Avg loss
            }
        """
        stmt = select(Position).where(
            and_(
                Position.account_id == account_id,
                Position.closed_at.isnot(None)  # Only closed positions
            )
        )
        
        if instrument_id:
            stmt = stmt.where(Position.instrument_id == instrument_id)
        
        result = await db.execute(stmt)
        positions = result.scalars().all()
        
        if not positions:
            return {
                "win_rate": 0.0,
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "average_win": 0.0,
                "average_loss": 0.0,
                "profit_factor": 0.0
            }
        
        winning = [p for p in positions if p.realized_pnl > 0]
        losing = [p for p in positions if p.realized_pnl < 0]
        
        win_count = len(winning)
        loss_count = len(losing)
        total_count = len(positions)
        
        avg_win = sum(p.realized_pnl for p in winning) / win_count if win_count > 0 else 0.0
        avg_loss = sum(p.realized_pnl for p in losing) / loss_count if loss_count > 0 else 0.0
        
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0.0
        
        return {
            "win_rate": (win_count / total_count * 100) if total_count > 0 else 0.0,
            "total_trades": total_count,
            "winning_trades": win_count,
            "losing_trades": loss_count,
            "average_win": avg_win,
            "average_loss": avg_loss,
            "profit_factor": profit_factor
        }
    
    async def get_pnl_statement(
        self,
        account_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        db: AsyncSession = None
    ) -> Dict:
        """
        Generate comprehensive P&L statement.
        
        Returns complete breakdown of profits, losses, fees, and returns.
        """
        # Get positions in date range
        stmt = select(Position).where(Position.account_id == account_id)
        
        if start_date:
            stmt = stmt.where(Position.opened_at >= start_date)
        if end_date:
            stmt = stmt.where(Position.opened_at <= end_date)
        
        result = await db.execute(stmt)
        positions = result.scalars().all()
        
        # Calculate totals
        total_realized = sum(p.realized_pnl for p in positions if p.closed_at)
        total_unrealized = sum(p.unrealized_pnl for p in positions if not p.closed_at)
        
        # Get commissions
        from app.services.fee_service import get_fee_service
        fee_service = get_fee_service()
        fee_breakdown = await fee_service.get_fee_breakdown(
            account_id, start_date, end_date, db
        )
        
        # Get win rate
        win_rate_stats = await self.calculate_win_rate(account_id, db)
        
        return {
            "period": {
                "start_date": start_date,
                "end_date": end_date
            },
            "pnl": {
                "realized": total_realized,
                "unrealized": total_unrealized,
                "total": total_realized + total_unrealized
            },
            "fees": fee_breakdown,
            "statistics": win_rate_stats,
            "position_count": len(positions),
            "open_positions": len([p for p in positions if not p.closed_at]),
            "closed_positions": len([p for p in positions if p.closed_at])
        }


# Global PnL calculation service instance
_pnl_service: Optional[PnLCalculationService] = None


def get_pnl_service() -> PnLCalculationService:
    """Get or create global PnL calculation service."""
    global _pnl_service
    if _pnl_service is None:
        _pnl_service = PnLCalculationService()
    return _pnl_service
