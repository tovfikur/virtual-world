"""
Trading endpoints (phase 1: standalone panel).
"""
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from app.db.session import get_db
from app.dependencies import get_current_user, require_role
from app.models.trading import TradingCompany, TradingTransaction
from app.models.user import User, UserRole
from app.schemas.trading_schema import (
    TradingCompanyCreate,
    TradingCompanyOut,
    TradingTransactionCreate,
    TradingTransactionOut,
    TradingBatchResult,
)
from app.services.trading_service import trading_service
from app.services.payment_service import payment_service, PaymentGateway

router = APIRouter(prefix="/trading", tags=["trading"])


def _round_int(val: Decimal) -> int:
    return int(val.to_integral_value(rounding=ROUND_HALF_UP))


@router.get("/companies", response_model=List[TradingCompanyOut])
async def list_companies(
    db: AsyncSession = Depends(get_db),
):
    companies = await trading_service.list_companies(db)
    return companies


@router.post("/companies", response_model=TradingCompanyOut, status_code=status.HTTP_201_CREATED)
async def create_company(
    payload: TradingCompanyCreate,
    _: dict = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    company = await trading_service.create_company(
        db=db,
        name=payload.name,
        total_shares=payload.total_shares,
        initial_price=Decimal(payload.initial_price),
    )
    return company


@router.post("/transactions", response_model=TradingTransactionOut, status_code=status.HTTP_201_CREATED)
async def queue_transaction(
    payload: TradingTransactionCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = UUID(current_user["sub"])

    # Basic validation
    if payload.shares == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Shares must be non-zero")
    if Decimal(payload.fee_percent) < 0 or Decimal(payload.fee_percent) > 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="fee_percent must be between 0 and 1")
    if Decimal(payload.fee_fixed_shares) < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="fee_fixed_shares must be >= 0")

    # Validate company exists
    result = await db.execute(
        select(TradingCompany).where(TradingCompany.company_id == payload.company_id)
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    # Lock user to adjust balance instantly
    user_result = await db.execute(
        select(User).where(User.user_id == user_id).with_for_update()
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Pending aggregates (to prevent over-buy/sell across concurrent requests)
    pending_stmt = (
        select(
            func.coalesce(func.sum(TradingTransaction.shares), 0),
            func.coalesce(func.sum(func.case((TradingTransaction.shares > 0, TradingTransaction.shares), else_=0)), 0),
        )
        .where(
            TradingTransaction.company_id == payload.company_id,
            TradingTransaction.processed.is_(False),
        )
    )
    pending_net, pending_buys = (await db.execute(pending_stmt)).one()
    pending_net = int(pending_net)
    pending_buys = int(pending_buys)

    # Company level availability (sold_shares includes processed only)
    available_buy = company.total_shares - company.sold_shares - pending_buys
    if payload.shares > 0 and payload.shares > available_buy:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not enough available shares to buy",
        )

    price = Decimal(company.share_price)
    shares_abs = Decimal(abs(payload.shares))
    fee_shares = shares_abs * Decimal(payload.fee_percent) + Decimal(payload.fee_fixed_shares)
    trade_value = shares_abs * price
    fee_value_bdt = fee_shares * price

    # Prevent oversell (consider processed + pending net)
    if payload.shares < 0:
        holdings_result = await db.execute(
            select(func.coalesce(func.sum(TradingTransaction.shares), 0))
            .where(
                TradingTransaction.company_id == payload.company_id,
                TradingTransaction.user_id == user_id,
            )
        )
        current_holdings = int(holdings_result.scalar() or 0)

        pending_user_stmt = (
            select(func.coalesce(func.sum(TradingTransaction.shares), 0))
            .where(
                TradingTransaction.company_id == payload.company_id,
                TradingTransaction.user_id == user_id,
                TradingTransaction.processed.is_(False),
            )
        )
        pending_user_net = int((await db.execute(pending_user_stmt)).scalar() or 0)

        available_to_sell = current_holdings + pending_user_net
        if available_to_sell < abs(payload.shares):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient shares to sell",
            )

    if payload.shares > 0:
        total_debit_int = _round_int(trade_value + fee_value_bdt)
        if user.balance_bdt < total_debit_int:
            reference_id = f"trade-{company.company_id}-{user_id}"
            payment = await payment_service.initiate_rocket_payment(
                user_id=str(user_id),
                amount=total_debit_int,
                reference_id=reference_id,
            )
            detail = {
                "message": "Insufficient balance for trade",
                "required_amount": total_debit_int,
                "payment_required": True,
                "gateway": PaymentGateway.ROCKET.value,
            }
            if payment.get("success"):
                detail["payment_url"] = payment.get("payment_url")
                detail["reference_id"] = payment.get("reference_id")
            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=detail)
        user.balance_bdt -= total_debit_int
    elif payload.shares < 0:
        credit_dec = trade_value - fee_value_bdt
        credit_int = max(_round_int(credit_dec), 0)
        user.balance_bdt += credit_int

    tx = await trading_service.queue_transaction(
        db=db,
        company_id=payload.company_id,
        user_id=user_id,
        shares=payload.shares,
        fee_percent=Decimal(payload.fee_percent),
        fee_fixed_shares=Decimal(payload.fee_fixed_shares),
    )
    return tx


@router.post("/run-batch", response_model=TradingBatchResult)
async def run_batch(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    processed_count, total_net_bs, updated = await trading_service.run_batch(db)
    return TradingBatchResult(
        processed=processed_count,
        total_net_bs=total_net_bs,
        companies_updated=updated,
    )


@router.delete("/companies/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    company_id: UUID,
    current_admin: dict = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    # Fetch company
    result = await db.execute(
        select(TradingCompany).where(TradingCompany.company_id == company_id)
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    # If no shares sold, allow deletion immediately
    if company.sold_shares == 0:
        allow_delete = True
    else:
        # Check if all sold shares are owned by the current admin
        holdings_result = await db.execute(
            select(
                TradingTransaction.user_id,
                func.coalesce(func.sum(TradingTransaction.shares), 0).label("qty"),
            )
            .where(
                TradingTransaction.company_id == company_id,
                TradingTransaction.processed.is_(True),
            )
            .group_by(TradingTransaction.user_id)
        )
        rows = holdings_result.all()
        total_qty = sum(int(r.qty) for r in rows)
        only_admin_holds_all = (
            len(rows) == 1
            and str(rows[0].user_id) == current_admin["sub"]
            and total_qty == company.sold_shares
        )
        allow_delete = only_admin_holds_all

    if not allow_delete:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete: shares sold to other users",
        )

    # Delete transactions for this company (processed and pending), then company
    await db.execute(
        delete(TradingTransaction).where(TradingTransaction.company_id == company_id)
    )
    await db.execute(delete(TradingCompany).where(TradingCompany.company_id == company_id))
    await db.commit()
