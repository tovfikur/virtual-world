"""
Market status controls (open/halt/close) - admin only for mutations.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.dependencies import require_role
from app.models.user import UserRole
from app.models.market_status import MarketStatus, MarketState
from app.schemas.market_schema import MarketStatusOut, MarketStatusUpdate

router = APIRouter(prefix="/market", tags=["market"])


async def _get_or_create_status(db: AsyncSession) -> MarketStatus:
    result = await db.execute(select(MarketStatus))
    row = result.scalar_one_or_none()
    if row:
        return row
    row = MarketStatus(state=MarketState.OPEN.value)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.get("/status", response_model=MarketStatusOut)
async def get_market_status(db: AsyncSession = Depends(get_db)):
    row = await _get_or_create_status(db)
    return MarketStatusOut(state=row.state, reason=row.reason)


@router.post("/status", response_model=MarketStatusOut)
async def set_market_status(
    payload: MarketStatusUpdate,
    _: dict = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    row = await _get_or_create_status(db)
    row.state = payload.state
    row.reason = payload.reason
    await db.commit()
    await db.refresh(row)
    return MarketStatusOut(state=row.state, reason=row.reason)
