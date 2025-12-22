"""
Settlement and clearing API endpoints.
Provides trade confirmation, settlement status, custody balance tracking, and reconciliation.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from uuid import UUID

from app.database import get_db
from app.models.settlement import (
    TradeConfirmation, SettlementRecord, CustodyBalance,
    SettlementStatus, SettlementType
)
from app.models.auth import User
from app.services.settlement_service import get_settlement_service
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/settlement", tags=["settlement"])


# Response models
class TradeConfirmationResponse(BaseModel):
    """Trade confirmation response."""
    id: str
    trade_id: int
    buyer_account_id: int
    seller_account_id: int
    instrument_id: str
    quantity: float
    price: float
    gross_amount: float
    buyer_fee: float
    seller_fee: float
    net_amount: float
    settlement_type: str
    settlement_date: datetime
    settlement_status: str
    buyer_confirmed: bool
    seller_confirmed: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class SettlementRecordResponse(BaseModel):
    """Settlement record response."""
    id: int
    settlement_id: str
    trade_confirmation_id: str
    buyer_account_id: int
    seller_account_id: int
    instrument_id: str
    quantity: float
    settlement_price: float
    settlement_amount: float
    buyer_pays: float
    seller_receives: float
    platform_fee_collected: float
    settlement_type: str
    status: str
    settlement_date: datetime
    actual_settlement_date: Optional[datetime]
    buyer_custody_updated: bool
    seller_custody_updated: bool
    broker_paid: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class CustodyBalanceResponse(BaseModel):
    """Custody balance response."""
    id: int
    account_id: int
    instrument_id: str
    custody_type: str
    balance: float
    pending_debit: float
    pending_credit: float
    quantity_settled: float
    quantity_pending: float
    custodian: Optional[str]
    is_reconciled: bool
    last_reconciled_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class ConfirmTradeRequest(BaseModel):
    """Request to confirm trade."""
    confirmation_id: str
    is_buyer: bool


class SettlementSummaryResponse(BaseModel):
    """Settlement summary for account."""
    account_id: int
    total_pending_settlements: int
    pending_settlement_amount: float
    total_settled_today: int
    total_settled_amount: float
    pending_custody_updates: int
    failed_settlements: int


@router.get("/confirmations/{confirmation_id}", response_model=TradeConfirmationResponse)
async def get_trade_confirmation(
    confirmation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get trade confirmation details."""
    from sqlalchemy import select
    
    stmt = select(TradeConfirmation).where(
        TradeConfirmation.id == UUID(confirmation_id)
    )
    result = await db.execute(stmt)
    confirmation = result.scalars().first()
    
    if not confirmation:
        raise HTTPException(status_code=404, detail="Confirmation not found")
    
    # Check authorization
    if (current_user.account_id != confirmation.buyer_account_id and
        current_user.account_id != confirmation.seller_account_id):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return confirmation


@router.post("/confirmations/{confirmation_id}/confirm")
async def confirm_trade(
    confirmation_id: str,
    request: ConfirmTradeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Confirm trade from buyer or seller side."""
    settlement_service = get_settlement_service()
    
    try:
        confirmation = await settlement_service.confirm_trade(
            UUID(confirmation_id),
            current_user.account_id,
            request.is_buyer,
            db
        )
        
        await db.commit()
        await db.refresh(confirmation)
        
        return {
            "status": "success",
            "confirmation_id": str(confirmation.id),
            "settlement_status": confirmation.settlement_status,
            "buyer_confirmed": confirmation.buyer_confirmed,
            "seller_confirmed": confirmation.seller_confirmed
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/summary", response_model=SettlementSummaryResponse)
async def get_settlement_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get settlement summary for user account."""
    from sqlalchemy import select, func
    
    account_id = current_user.account_id
    
    # Pending settlements
    pending_stmt = select(func.count(TradeConfirmation.id), func.sum(TradeConfirmation.net_amount)).where(
        TradeConfirmation.settlement_status == SettlementStatus.PENDING
    )
    pending_result = await db.execute(pending_stmt)
    pending_count, pending_amount = pending_result.one()
    
    # Settled today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    settled_stmt = select(func.count(SettlementRecord.id), func.sum(SettlementRecord.settlement_amount)).where(
        SettlementRecord.actual_settlement_date >= today_start
    )
    settled_result = await db.execute(settled_stmt)
    settled_count, settled_amount = settled_result.one()
    
    # Pending custody updates
    custody_stmt = select(func.count(CustodyBalance.id)).where(
        CustodyBalance.is_reconciled == False
    )
    custody_result = await db.execute(custody_stmt)
    custody_pending = custody_result.scalar()
    
    # Failed settlements
    failed_stmt = select(func.count(TradeConfirmation.id)).where(
        TradeConfirmation.settlement_status == SettlementStatus.FAILED
    )
    failed_result = await db.execute(failed_stmt)
    failed_count = failed_result.scalar()
    
    return SettlementSummaryResponse(
        account_id=account_id,
        total_pending_settlements=pending_count or 0,
        pending_settlement_amount=float(pending_amount or 0.0),
        total_settled_today=settled_count or 0,
        total_settled_amount=float(settled_amount or 0.0),
        pending_custody_updates=custody_pending or 0,
        failed_settlements=failed_count or 0
    )


@router.get("/settlements", response_model=List[SettlementRecordResponse])
async def get_settlement_records(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0)
):
    """Get settlement records for account."""
    from sqlalchemy import select, or_
    
    stmt = select(SettlementRecord).where(
        or_(
            SettlementRecord.buyer_account_id == current_user.account_id,
            SettlementRecord.seller_account_id == current_user.account_id
        )
    )
    
    if status:
        stmt = stmt.where(SettlementRecord.status == status)
    
    stmt = stmt.order_by(SettlementRecord.created_at.desc()).limit(limit).offset(offset)
    
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/custody", response_model=List[CustodyBalanceResponse])
async def get_custody_balances(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    include_zero: bool = Query(False)
):
    """Get custody balances for account."""
    from sqlalchemy import select
    
    stmt = select(CustodyBalance).where(
        CustodyBalance.account_id == current_user.account_id
    )
    
    if not include_zero:
        stmt = stmt.where(CustodyBalance.balance > 0)
    
    stmt = stmt.order_by(CustodyBalance.updated_at.desc())
    
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/custody/{instrument_id}", response_model=CustodyBalanceResponse)
async def get_custody_balance(
    instrument_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get custody balance for specific instrument."""
    from sqlalchemy import select
    
    stmt = select(CustodyBalance).where(
        CustodyBalance.account_id == current_user.account_id,
        CustodyBalance.instrument_id == UUID(instrument_id)
    )
    
    result = await db.execute(stmt)
    custody = result.scalars().first()
    
    if not custody:
        raise HTTPException(status_code=404, detail="Custody balance not found")
    
    return custody


@router.post("/reconcile")
async def request_reconciliation(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Request reconciliation of custody balances."""
    settlement_service = get_settlement_service()
    
    try:
        report = await settlement_service.reconcile_custody(
            account_id=current_user.account_id,
            db=db
        )
        
        await db.commit()
        
        return {
            "status": "success",
            "report_id": report.id,
            "expected_balance": report.expected_balance,
            "actual_balance": report.actual_balance,
            "difference": report.difference,
            "is_balanced": report.is_balanced,
            "matched_trades": report.matched_trades,
            "unmatched_trades": report.unmatched_trades
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/pending")
async def get_pending_settlements(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all pending settlements."""
    from sqlalchemy import select
    
    stmt = select(TradeConfirmation).where(
        TradeConfirmation.settlement_status.in_([
            SettlementStatus.PENDING,
            SettlementStatus.CONFIRMED
        ])
    )
    
    result = await db.execute(stmt)
    confirmations = result.scalars().all()
    
    return {
        "count": len(confirmations),
        "settlements": [
            {
                "id": str(c.id),
                "trade_id": c.trade_id,
                "status": c.settlement_status,
                "settlement_date": c.settlement_date,
                "amount": c.net_amount,
                "buyer_confirmed": c.buyer_confirmed,
                "seller_confirmed": c.seller_confirmed
            }
            for c in confirmations
        ]
    }


@router.get("/statistics")
async def get_settlement_statistics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365)
):
    """Get settlement statistics for period."""
    from sqlalchemy import select, func
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    stmt = select(
        func.count(SettlementRecord.id).label("total_settlements"),
        func.sum(SettlementRecord.settlement_amount).label("total_amount"),
        func.avg(SettlementRecord.settlement_amount).label("avg_amount"),
        func.count(SettlementRecord.id).filter(
            SettlementRecord.status == SettlementStatus.FAILED
        ).label("failed_count")
    ).where(
        SettlementRecord.actual_settlement_date >= start_date
    )
    
    result = await db.execute(stmt)
    row = result.one()
    
    return {
        "period_days": days,
        "total_settlements": row.total_settlements or 0,
        "total_amount": float(row.total_amount or 0.0),
        "average_amount": float(row.avg_amount or 0.0),
        "failed_count": row.failed_count or 0,
        "success_rate": (
            ((row.total_settlements - row.failed_count) / row.total_settlements * 100)
            if row.total_settlements else 0
        )
    }


from datetime import timedelta
