"""
Order entry endpoints (scaffolded).
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.db.session import get_db
from app.dependencies import get_current_user
from app.services.matching_service import matching_service
from app.schemas.order_schema import OrderCreate, OrderOut
from app.models.order import Order

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def place_order(
    payload: OrderCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        order = await matching_service.place_order(
            db=db,
            user_id=UUID(current_user["sub"]),
            payload=payload,
        )
        return order
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=list[OrderOut])
async def list_orders(
    instrument_id: UUID | None = None,
    side: str | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Order).where(Order.user_id == UUID(current_user["sub"]))
    if instrument_id:
        query = query.where(Order.instrument_id == instrument_id)
    if side:
        query = query.where(Order.side == side)
    if status_filter:
        query = query.where(Order.status == status_filter)
    query = query.order_by(Order.created_at.desc()).offset(offset).limit(min(limit, 200))

    result = await db.execute(query)
    return result.scalars().all()


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_order(
    order_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Order).where(Order.order_id == order_id, Order.user_id == UUID(current_user["sub"]))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    # Remove from in-memory book if present
    book = matching_service.books.get(order.instrument_id)
    if book:
        book.cancel(order.order_id)

    await db.execute(delete(Order).where(Order.order_id == order.order_id))
    await db.commit()
