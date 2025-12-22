"""
Risk checks scaffold: validates order sizing against instrument tick/lot and basic max size.
"""
from decimal import Decimal
from uuid import UUID

from app.models.instrument import Instrument, InstrumentStatus
from app.schemas.order_schema import OrderCreate


class RiskService:
    def __init__(self) -> None:
        self.max_order_notional = Decimal("100000000")  # placeholder

    def validate_order(self, instrument: Instrument, payload: OrderCreate) -> None:
        if instrument.status != InstrumentStatus.ACTIVE:
            raise ValueError("Instrument not active")

        # Lot size multiple
        if (Decimal(payload.quantity) % instrument.lot_size) != 0:
            raise ValueError("Quantity must be a multiple of lot_size")

        # Tick size for limit/stop prices
        if payload.price is not None and (Decimal(payload.price) % instrument.tick_size) != 0:
            raise ValueError("Price must align to tick_size")
        if payload.stop_price is not None and (Decimal(payload.stop_price) % instrument.tick_size) != 0:
            raise ValueError("Stop price must align to tick_size")

        # Notional cap placeholder
        if payload.price:
            notional = Decimal(payload.price) * Decimal(payload.quantity)
            if notional > self.max_order_notional:
                raise ValueError("Order notional exceeds limit")


risk_service = RiskService()
