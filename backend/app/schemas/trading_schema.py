"""
Pydantic schemas for trading system.
"""
from decimal import Decimal
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field, condecimal, confloat, validator


Decimal18_8 = condecimal(max_digits=18, decimal_places=8)
Decimal6_4 = condecimal(max_digits=6, decimal_places=4)


class TradingCompanyCreate(BaseModel):
    name: str = Field(..., max_length=128)
    total_shares: int = Field(1000, gt=0)
    initial_price: Decimal18_8 = Field(Decimal("1"), gt=0)


class TradingCompanyOut(BaseModel):
    company_id: UUID
    name: str
    total_shares: int
    sold_shares: int
    share_price: Decimal18_8

    class Config:
        orm_mode = True


class TradingTransactionCreate(BaseModel):
    company_id: UUID
    shares: int  # +buy, -sell
    fee_percent: Decimal6_4 = Decimal("0")
    fee_fixed_shares: Decimal18_8 = Decimal("0")

    @validator("shares")
    def non_zero(cls, v):
        if v == 0:
            raise ValueError("shares must be non-zero")
        return v


class TradingTransactionOut(BaseModel):
    tx_id: UUID
    company_id: UUID
    user_id: UUID
    shares: int
    fee_percent: Decimal6_4
    fee_fixed_shares: Decimal18_8
    processed: bool
    created_at: datetime

    class Config:
        orm_mode = True


class TradingBatchResult(BaseModel):
    processed: int
    total_net_bs: Decimal18_8
    companies_updated: List[TradingCompanyOut]

