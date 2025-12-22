"""
Risk checks: validates order sizing, margin, leverage, and exposure limits.
"""
from decimal import Decimal
from uuid import UUID
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.instrument import Instrument, InstrumentStatus
from app.models.account import Account
from app.schemas.order_schema import OrderCreate
from app.services.margin_service import get_margin_service


class RiskService:
    """
    Pre-trade risk validation service.
    
    Validates:
    - Instrument status and trading parameters
    - Margin sufficiency
    - Leverage limits
    - Position size limits
    - Exposure limits per instrument
    """
    
    def __init__(self) -> None:
        self.max_order_notional = Decimal("100000000")  # $100M max per order
        self.max_position_size_pct = 0.20  # Max 20% of account equity per position
        self.max_instrument_exposure_pct = 0.50  # Max 50% of account equity per instrument
        self.margin_service = get_margin_service()

    def validate_order(self, instrument: Instrument, payload: OrderCreate) -> None:
        """Basic order validation (tick size, lot size, notional)."""
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
    
    async def validate_pre_trade(
        self,
        account: Account,
        instrument: Instrument,
        side: str,
        quantity: float,
        price: Optional[float],
        leverage: float,
        db: AsyncSession
    ) -> None:
        """
        Comprehensive pre-trade risk checks.
        
        Raises ValueError if any risk check fails.
        """
        # 1. Check leverage limits
        if leverage > float(instrument.leverage_max):
            raise ValueError(
                f"Leverage {leverage}x exceeds instrument limit {instrument.leverage_max}x"
            )
        
        if leverage > account.leverage_max:
            raise ValueError(
                f"Leverage {leverage}x exceeds account limit {account.leverage_max}x"
            )
        
        # 2. Estimate order price if not provided
        if price is None:
            # For market orders, use current market price estimate
            from app.services.pricing_service import get_pricing_engine
            pricing_engine = get_pricing_engine()
            quote = await pricing_engine.get_aggregated_quote(instrument.instrument_id, db)
            if quote:
                price = quote['mid']
            else:
                raise ValueError("Unable to determine market price for validation")
        
        # 3. Calculate margin required
        margin_required = await self.margin_service.calculate_position_margin(
            instrument.instrument_id,
            quantity,
            price,
            leverage,
            db
        )
        
        # 4. Check margin sufficiency
        is_sufficient, msg = await self.margin_service.check_margin_sufficiency(
            account,
            margin_required,
            db
        )
        if not is_sufficient:
            raise ValueError(f"Insufficient margin: {msg}")
        
        # 5. Check position size limit (% of equity)
        notional = quantity * price
        max_position_notional = account.equity * self.max_position_size_pct
        if notional > max_position_notional:
            raise ValueError(
                f"Position size {notional:.2f} exceeds max "
                f"{self.max_position_size_pct*100}% of equity ({max_position_notional:.2f})"
            )
        
        # 6. Check total exposure per instrument
        current_exposure = await self.margin_service.get_exposure_per_instrument(
            account.id,
            instrument.instrument_id,
            db
        )
        
        # Add new position exposure (positive for long, negative for short)
        new_exposure = notional if side == "LONG" else -notional
        total_exposure = abs(current_exposure + new_exposure)
        
        max_instrument_exposure = account.equity * self.max_instrument_exposure_pct
        if total_exposure > max_instrument_exposure:
            raise ValueError(
                f"Total exposure {total_exposure:.2f} exceeds max "
                f"{self.max_instrument_exposure_pct*100}% of equity ({max_instrument_exposure:.2f}) "
                f"for this instrument"
            )
    
    async def validate_order_with_account(
        self,
        account: Account,
        instrument: Instrument,
        payload: OrderCreate,
        db: AsyncSession
    ) -> None:
        """
        Combined validation: basic order validation + pre-trade risk checks.
        
        This is the main entry point for order validation.
        """
        # Basic validation
        self.validate_order(instrument, payload)
        
        # Pre-trade risk checks
        await self.validate_pre_trade(
            account=account,
            instrument=instrument,
            side=payload.side.value,
            quantity=float(payload.quantity),
            price=float(payload.price) if payload.price else None,
            leverage=float(payload.leverage) if hasattr(payload, 'leverage') else 1.0,
            db=db
        )


risk_service = RiskService()
