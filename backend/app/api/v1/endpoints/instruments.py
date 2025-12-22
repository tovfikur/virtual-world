"""
Instrument management endpoints (phase 2 scaffold).
"""
from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.db.session import get_db
from app.dependencies import require_role
from app.models.instrument import Instrument
from app.models.user import UserRole
from app.schemas.instrument_schema import (
    InstrumentCreate,
    InstrumentUpdate,
    InstrumentOut,
)

router = APIRouter(prefix="/instruments", tags=["instruments"])


@router.get("", response_model=List[InstrumentOut])
async def list_instruments(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Instrument))
    return result.scalars().all()


@router.post("", response_model=InstrumentOut, status_code=status.HTTP_201_CREATED)
async def create_instrument(
    payload: InstrumentCreate,
    _: dict = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    # Ensure symbol unique
    existing = await db.execute(select(Instrument).where(Instrument.symbol == payload.symbol))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Symbol already exists")

    instrument = Instrument(
        symbol=payload.symbol.upper(),
        name=payload.name,
        asset_class=payload.asset_class,
        tick_size=payload.tick_size,
        lot_size=payload.lot_size,
        leverage_max=payload.leverage_max,
        is_margin_allowed=payload.is_margin_allowed,
        is_short_selling_allowed=payload.is_short_selling_allowed,
        status=payload.status,
        session_open_utc=payload.session_open_utc,
        session_close_utc=payload.session_close_utc,
    )
    db.add(instrument)
    await db.commit()
    await db.refresh(instrument)
    return instrument


@router.patch("/{instrument_id}", response_model=InstrumentOut)
async def update_instrument(
    instrument_id: UUID,
    payload: InstrumentUpdate,
    _: dict = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Instrument).where(Instrument.instrument_id == instrument_id))
    instrument = result.scalar_one_or_none()
    if not instrument:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instrument not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(instrument, field, value)

    await db.commit()
    await db.refresh(instrument)
    return instrument


@router.delete("/{instrument_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_instrument(
    instrument_id: UUID,
    _: dict = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Instrument).where(Instrument.instrument_id == instrument_id))
    instrument = result.scalar_one_or_none()
    if not instrument:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instrument not found")

    await db.delete(instrument)
    await db.commit()
