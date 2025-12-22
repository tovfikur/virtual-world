from uuid import UUID
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, Field

from app.models.instrument import AssetClass, InstrumentStatus


class InstrumentBase(BaseModel):
    symbol: str = Field(..., max_length=32)
    name: str = Field(..., max_length=128)
    asset_class: AssetClass
    tick_size: Decimal = Field(..., gt=0)
    lot_size: Decimal = Field(..., gt=0)
    leverage_max: Decimal = Field(..., gt=0)
    is_margin_allowed: bool = False
    is_short_selling_allowed: bool = False
    status: InstrumentStatus = InstrumentStatus.ACTIVE
    session_open_utc: Optional[str] = Field(None, max_length=8)
    session_close_utc: Optional[str] = Field(None, max_length=8)


class InstrumentCreate(InstrumentBase):
    pass


class InstrumentUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=128)
    tick_size: Optional[Decimal] = Field(None, gt=0)
    lot_size: Optional[Decimal] = Field(None, gt=0)
    leverage_max: Optional[Decimal] = Field(None, gt=0)
    is_margin_allowed: Optional[bool] = None
    is_short_selling_allowed: Optional[bool] = None
    status: Optional[InstrumentStatus] = None
    session_open_utc: Optional[str] = Field(None, max_length=8)
    session_close_utc: Optional[str] = Field(None, max_length=8)


class InstrumentOut(InstrumentBase):
    instrument_id: UUID

    class Config:
        from_attributes = True
