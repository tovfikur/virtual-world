"""
Order model for matching engine scaffold.
"""

from enum import Enum
from uuid import uuid4
from sqlalchemy import Column, String, Enum as SQLEnum, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import BaseModel


class OrderStatus(str, Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"
    IOC = "ioc"
    FOK = "fok"
    ICEBERG = "iceberg"
    OCO = "oco"


class Order(BaseModel):
    """
    Lightweight order record; executions not yet persisted in this phase.
    """

    __tablename__ = "orders"

    order_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4, nullable=False)
    instrument_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    side = Column(SQLEnum(OrderSide), nullable=False)
    order_type = Column(SQLEnum(OrderType), nullable=False)
    quantity = Column(Numeric(24, 8), nullable=False)
    price = Column(Numeric(24, 8), nullable=True)
    stop_price = Column(Numeric(24, 8), nullable=True)
    trailing_offset = Column(Numeric(24, 8), nullable=True)
    oco_group_id = Column(String(64), nullable=True, index=True)
    iceberg_visible = Column(Numeric(24, 8), nullable=True)
    time_in_force = Column(String(8), nullable=False, default="gtc")

    status = Column(SQLEnum(OrderStatus), nullable=False, default=OrderStatus.PENDING, index=True)
    client_order_id = Column(String(64), nullable=True, index=True)

    def __repr__(self) -> str:
        return f"<Order {self.order_id} {self.side} {self.order_type}>"
