from uuid import UUID
from decimal import Decimal
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field


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


class TimeInForce(str, Enum):
    GTC = "gtc"
    DAY = "day"
    IOC = "ioc"
    FOK = "fok"


class OrderCreate(BaseModel):
    instrument_id: UUID
    side: OrderSide
    order_type: OrderType
    quantity: Decimal = Field(..., gt=0)
    price: Optional[Decimal] = Field(None, gt=0)
    stop_price: Optional[Decimal] = Field(None, gt=0)
    trailing_offset: Optional[Decimal] = Field(None, gt=0)
    iceberg_visible: Optional[Decimal] = Field(None, gt=0)
    oco_group_id: Optional[str] = Field(None, max_length=64)
    time_in_force: TimeInForce = TimeInForce.GTC
    client_order_id: Optional[str] = Field(None, max_length=64)


class OrderBookLevel(BaseModel):
    price: Decimal
    quantity: Decimal
    orders: int


class TopOfBook(BaseModel):
    best_bid: Optional[OrderBookLevel]
    best_ask: Optional[OrderBookLevel]


class DepthSnapshot(BaseModel):
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]


class OrderOut(BaseModel):
    order_id: UUID
    instrument_id: UUID
    user_id: UUID
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Optional[Decimal]
    stop_price: Optional[Decimal]
    trailing_offset: Optional[Decimal]
    iceberg_visible: Optional[Decimal]
    oco_group_id: Optional[str]
    time_in_force: TimeInForce
    status: str
    client_order_id: Optional[str]

    class Config:
        from_attributes = True


class TradeOut(BaseModel):
    trade_id: UUID
    buy_order_id: UUID
    sell_order_id: UUID
    instrument_id: UUID
    price: Decimal
    quantity: Decimal
    buyer_id: UUID
    seller_id: UUID

    class Config:
        from_attributes = True
