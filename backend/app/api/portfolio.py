"""
Portfolio dashboard API endpoints.
Provides comprehensive portfolio overview, positions list, and performance metrics.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.database import get_db
from app.models.account import Account, Position
from app.models.auth import User
from app.services.position_service import get_position_service, PositionMode
from app.services.pnl_service import get_pnl_service
from app.services.margin_service import get_margin_service
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


# Response models
class PortfolioSummary(BaseModel):
    """Portfolio overview."""
    account_id: int
    balance: float
    equity: float
    used_margin: float
    free_margin: float
    margin_level: float
    unrealized_pnl: float
    realized_pnl_today: float
    open_positions: int
    total_exposure: float
    available_leverage: float
    
    class Config:
        from_attributes = True


class PositionInfo(BaseModel):
    """Detailed position information."""
    id: str
    instrument_id: str
    instrument_symbol: str
    side: str
    quantity: float
    entry_price: float
    current_price: Optional[float]
    unrealized_pnl: float
    pnl_percent: float
    margin_used: float
    leverage_used: float
    swap_accumulated: float
    opened_at: datetime
    
    class Config:
        from_attributes = True


class PerformanceMetrics(BaseModel):
    """Portfolio performance metrics."""
    period: str  # "24h", "7d", "30d", "all"
    total_pnl: float
    total_trades: int
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    sharpe_ratio: Optional[float]
    max_drawdown: float
    
    class Config:
        from_attributes = True


class PortfolioTimeSeries(BaseModel):
    """Portfolio value over time."""
    timestamp: datetime
    equity: float
    balance: float
    unrealized_pnl: float
    
    class Config:
        from_attributes = True


@router.get("/summary", response_model=PortfolioSummary)
async def get_portfolio_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get portfolio summary with balance, equity, margin, and P&L.
    """
    # Get user's account
    account = current_user.account
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Update position prices
    position_service = get_position_service(PositionMode.NET)
    await position_service.update_position_prices(account.id, db)
    
    # Recalculate equity
    margin_service = get_margin_service()
    await margin_service.calculate_account_equity(account, db)
    
    # Get position summary
    pos_summary = await position_service.get_position_summary(account.id, db)
    
    # Calculate realized P&L for today
    pnl_service = get_pnl_service()
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    pnl_statement = await pnl_service.get_pnl_statement(
        account.id, today_start, datetime.utcnow(), db
    )
    realized_pnl_today = pnl_statement.get("realized_pnl", 0.0)
    
    return PortfolioSummary(
        account_id=account.id,
        balance=account.balance,
        equity=account.equity,
        used_margin=account.used_margin,
        free_margin=account.free_margin,
        margin_level=account.margin_level,
        unrealized_pnl=pos_summary["total_unrealized_pnl"],
        realized_pnl_today=realized_pnl_today,
        open_positions=pos_summary["open_positions"],
        total_exposure=pos_summary["total_exposure"],
        available_leverage=account.max_leverage
    )


@router.get("/positions", response_model=List[PositionInfo])
async def get_portfolio_positions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    include_closed: bool = Query(False, description="Include closed positions")
):
    """
    Get list of all positions with details.
    """
    account = current_user.account
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Get positions
    position_service = get_position_service(PositionMode.NET)
    positions = await position_service.get_all_positions(
        account.id, db, include_closed
    )
    
    # Convert to response model
    result = []
    for pos in positions:
        # Calculate P&L percentage
        pnl_pct = 0.0
        if pos.current_price and pos.entry_price:
            if pos.side == "LONG":
                pnl_pct = ((pos.current_price - pos.entry_price) / pos.entry_price) * 100
            else:
                pnl_pct = ((pos.entry_price - pos.current_price) / pos.entry_price) * 100
        
        result.append(PositionInfo(
            id=str(pos.id),
            instrument_id=str(pos.instrument_id),
            instrument_symbol=pos.instrument.symbol if pos.instrument else "UNKNOWN",
            side=pos.side,
            quantity=pos.quantity,
            entry_price=pos.entry_price,
            current_price=pos.current_price,
            unrealized_pnl=pos.unrealized_pnl,
            pnl_percent=pnl_pct,
            margin_used=pos.margin_used,
            leverage_used=pos.leverage_used,
            swap_accumulated=pos.swap_accumulated,
            opened_at=pos.opened_at
        ))
    
    return result


@router.get("/performance", response_model=PerformanceMetrics)
async def get_portfolio_performance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    period: str = Query("30d", regex="^(24h|7d|30d|all)$")
):
    """
    Get portfolio performance metrics for specified period.
    
    Periods:
    - 24h: Last 24 hours
    - 7d: Last 7 days
    - 30d: Last 30 days
    - all: All time
    """
    account = current_user.account
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Calculate period start
    if period == "24h":
        start_date = datetime.utcnow() - timedelta(hours=24)
    elif period == "7d":
        start_date = datetime.utcnow() - timedelta(days=7)
    elif period == "30d":
        start_date = datetime.utcnow() - timedelta(days=30)
    else:  # all
        start_date = None
    
    # Get P&L statement
    pnl_service = get_pnl_service()
    pnl_statement = await pnl_service.get_pnl_statement(
        account.id, start_date, datetime.utcnow(), db
    )
    
    # Calculate win rate stats
    win_rate_stats = await pnl_service.calculate_win_rate(
        account.id, start_date, datetime.utcnow(), db
    )
    
    # Calculate Sharpe ratio (simplified - would need daily returns for accurate calculation)
    sharpe_ratio = None
    if pnl_statement.get("total_trades", 0) > 0:
        avg_pnl = pnl_statement["realized_pnl"] / pnl_statement["total_trades"]
        # Simplified - real Sharpe needs standard deviation of returns
        sharpe_ratio = avg_pnl / max(abs(pnl_statement.get("largest_loss", 1)), 1)
    
    return PerformanceMetrics(
        period=period,
        total_pnl=pnl_statement.get("realized_pnl", 0.0),
        total_trades=pnl_statement.get("total_trades", 0),
        win_rate=win_rate_stats.get("win_rate", 0.0),
        profit_factor=win_rate_stats.get("profit_factor", 0.0),
        avg_win=win_rate_stats.get("avg_win", 0.0),
        avg_loss=win_rate_stats.get("avg_loss", 0.0),
        largest_win=pnl_statement.get("largest_win", 0.0),
        largest_loss=pnl_statement.get("largest_loss", 0.0),
        sharpe_ratio=sharpe_ratio,
        max_drawdown=0.0  # TODO: Calculate from equity curve
    )


@router.get("/history", response_model=List[PortfolioTimeSeries])
async def get_portfolio_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    period: str = Query("7d", regex="^(24h|7d|30d)$"),
    resolution: str = Query("1h", regex="^(5m|15m|1h|4h|1d)$")
):
    """
    Get portfolio value history over time.
    
    Periods: 24h, 7d, 30d
    Resolutions: 5m, 15m, 1h, 4h, 1d
    """
    account = current_user.account
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # TODO: Implement portfolio snapshot history
    # For now, return current state
    return [
        PortfolioTimeSeries(
            timestamp=datetime.utcnow(),
            equity=account.equity,
            balance=account.balance,
            unrealized_pnl=account.equity - account.balance
        )
    ]


@router.get("/exposure")
async def get_portfolio_exposure(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get portfolio exposure breakdown by instrument and asset class.
    """
    account = current_user.account
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    position_service = get_position_service(PositionMode.NET)
    summary = await position_service.get_position_summary(account.id, db)
    
    # Enhance with instrument details
    exposure_by_class = {}
    
    for inst_id, inst_data in summary["by_instrument"].items():
        # TODO: Get instrument details and group by asset class
        # For now, return raw instrument data
        pass
    
    return {
        "total_exposure": summary["total_exposure"],
        "by_instrument": summary["by_instrument"],
        "by_side": summary["by_side"],
        "leverage_utilization": (
            summary["total_exposure"] / account.equity 
            if account.equity > 0 else 0
        )
    }


@router.get("/alerts")
async def get_portfolio_alerts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get active portfolio alerts (margin calls, risk warnings).
    """
    account = current_user.account
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    alerts = []
    
    # Check margin level
    if account.margin_level < 120:
        alerts.append({
            "type": "margin_warning",
            "severity": "high" if account.margin_level < 100 else "medium",
            "message": f"Margin level at {account.margin_level:.1f}%",
            "timestamp": datetime.utcnow()
        })
    
    # Check equity vs balance (large unrealized loss)
    unrealized_loss = account.balance - account.equity
    if unrealized_loss > account.balance * 0.1:  # >10% loss
        alerts.append({
            "type": "large_drawdown",
            "severity": "medium",
            "message": f"Unrealized loss: ${unrealized_loss:.2f}",
            "timestamp": datetime.utcnow()
        })
    
    # TODO: Add more alert types
    # - Position size warnings
    # - Concentration risk
    # - Unusual P&L movements
    
    return {"alerts": alerts}


@router.post("/snapshot")
async def create_portfolio_snapshot(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a portfolio snapshot for historical tracking.
    Used for portfolio value charts and performance analysis.
    """
    account = current_user.account
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # TODO: Implement PortfolioSnapshot model and save snapshot
    # For now, return current state
    
    return {
        "timestamp": datetime.utcnow(),
        "equity": account.equity,
        "balance": account.balance,
        "used_margin": account.used_margin,
        "open_positions": 0  # TODO: Count
    }
