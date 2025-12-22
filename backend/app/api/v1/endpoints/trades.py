"""
Trade history endpoints (scaffold).
"""
from uuid import UUID
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.trade import Trade
from app.schemas.order_schema import TradeOut

router = APIRouter(prefix="/trades", tags=["trades"])


@router.get("", response_model=List[TradeOut])
async def list_trades(
    instrument_id: Optional[UUID] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = UUID(current_user["sub"])
    query = select(Trade).where(
        or_(Trade.buyer_id == user_id, Trade.seller_id == user_id)
    )
    if instrument_id:
        query = query.where(Trade.instrument_id == instrument_id)
    query = query.offset(offset).limit(min(limit, 200))
    result = await db.execute(query)
    return result.scalars().all()
