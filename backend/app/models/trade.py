"""
Trade execution record.
"""

from uuid import uuid4
from sqlalchemy import Column, Numeric
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import BaseModel


class Trade(BaseModel):
    __tablename__ = "trades"

    trade_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4, nullable=False)
    buy_order_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    sell_order_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    instrument_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    price = Column(Numeric(24, 8), nullable=False)
    quantity = Column(Numeric(24, 8), nullable=False)
    buyer_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    seller_id = Column(UUID(as_uuid=True), nullable=False, index=True)
