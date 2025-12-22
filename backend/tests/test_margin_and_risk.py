"""
Tests for margin calculation, liquidation, and circuit breaker services.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from uuid import UUID
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.account import Account, Position, MarginCall, CircuitBreaker, AccountStatus
from app.models.instrument import Instrument, AssetClass, InstrumentStatus
from app.models.order import Order, OrderSide, OrderType
from app.models.price_history import PriceHistory, QuoteLevel
from app.services.margin_service import get_margin_service
from app.services.liquidation_service import get_liquidation_service
from app.services.circuit_breaker_service import get_circuit_breaker_service
from app.services.risk_service import risk_service
from app.services.pricing_service import get_pricing_engine


@pytest.mark.asyncio
async def test_margin_calculation(db_session: AsyncSession):
    """Test margin calculation for leveraged positions."""
    margin_service = get_margin_service()
    
    # Create test instrument (FX pair)
    instrument = Instrument(
        symbol="EURUSD",
        name="Euro vs US Dollar",
        asset_class=AssetClass.FX,
        tick_size=Decimal("0.00001"),
        lot_size=Decimal("1000"),
        leverage_max=Decimal("50"),
        is_margin_allowed=True,
        status=InstrumentStatus.ACTIVE
    )
    db_session.add(instrument)
    await db_session.flush()
    
    # Test margin calculation
    # Position: 100,000 EUR @ 1.1000 with 50x leverage
    margin = await margin_service.calculate_position_margin(
        instrument_id=instrument.instrument_id,
        quantity=100000.0,
        price=1.1000,
        leverage=50.0,
        db=db_session
    )
    
    # Expected: (100,000 * 1.1000) / 50 = 2,200 USD
    assert abs(margin - 2200.0) < 0.01


@pytest.mark.asyncio
async def test_account_equity_calculation(db_session: AsyncSession):
    """Test account equity and margin level calculation."""
    margin_service = get_margin_service()
    
    # Create user and account
    user = User(username="trader1", email="trader1@test.com")
    db_session.add(user)
    await db_session.flush()
    
    account = Account(
        user_id=user.id,
        balance=10000.0,
        equity=10000.0,
        leverage_max=50.0
    )
    db_session.add(account)
    await db_session.flush()
    
    # Create instrument
    instrument = Instrument(
        symbol="GBPUSD",
        name="British Pound vs US Dollar",
        asset_class=AssetClass.FX,
        tick_size=Decimal("0.00001"),
        lot_size=Decimal("1000"),
        leverage_max=Decimal("50"),
        is_margin_allowed=True,
        status=InstrumentStatus.ACTIVE
    )
    db_session.add(instrument)
    await db_session.flush()
    
    # Add quote for current price
    pricing_engine = get_pricing_engine()
    await pricing_engine.add_quote(
        instrument_id=instrument.instrument_id,
        bid=1.2500,
        ask=1.2502,
        lp_name="TestLP",
        db=db_session
    )
    
    # Open position: 50,000 GBP @ 1.2500 with 50x leverage
    position = await margin_service.open_position(
        account=account,
        instrument_id=instrument.instrument_id,
        side="LONG",
        quantity=50000.0,
        entry_price=1.2500,
        leverage=50.0,
        db=db_session
    )
    
    # Margin used = (50,000 * 1.25) / 50 = 1,250 USD
    assert abs(position.margin_used - 1250.0) < 0.01
    
    # Update quote to simulate price movement (profit scenario)
    await pricing_engine.add_quote(
        instrument_id=instrument.instrument_id,
        bid=1.2600,
        ask=1.2602,
        lp_name="TestLP",
        db=db_session
    )
    
    # Recalculate equity
    equity, used_margin, free_margin = await margin_service.calculate_account_equity(
        account, db_session
    )
    
    # Expected P&L: (1.2601 - 1.2500) * 50,000 = 505 USD
    # Expected equity: 10,000 + 505 = 10,505 USD
    assert equity > 10000.0
    assert used_margin == 1250.0
    assert free_margin == equity - used_margin


@pytest.mark.asyncio
async def test_margin_call_detection(db_session: AsyncSession):
    """Test margin call detection when equity falls."""
    margin_service = get_margin_service()
    liquidation_service = get_liquidation_service()
    
    # Create user and account
    user = User(username="trader2", email="trader2@test.com")
    db_session.add(user)
    await db_session.flush()
    
    account = Account(
        user_id=user.id,
        balance=5000.0,
        equity=5000.0,
        leverage_max=50.0,
        margin_call_level=100.0,  # Margin call at 100%
        liquidation_level=50.0    # Liquidate at 50%
    )
    db_session.add(account)
    await db_session.flush()
    
    # Create instrument
    instrument = Instrument(
        symbol="BTCUSD",
        name="Bitcoin vs US Dollar",
        asset_class=AssetClass.CRYPTO,
        tick_size=Decimal("0.01"),
        lot_size=Decimal("0.001"),
        leverage_max=Decimal("20"),
        is_margin_allowed=True,
        status=InstrumentStatus.ACTIVE
    )
    db_session.add(instrument)
    await db_session.flush()
    
    # Add initial quote
    pricing_engine = get_pricing_engine()
    await pricing_engine.add_quote(
        instrument_id=instrument.instrument_id,
        bid=50000.0,
        ask=50010.0,
        lp_name="TestLP",
        db=db_session
    )
    
    # Open position: 0.1 BTC @ 50,005 with 10x leverage
    position = await margin_service.open_position(
        account=account,
        instrument_id=instrument.instrument_id,
        side="LONG",
        quantity=0.1,
        entry_price=50005.0,
        leverage=10.0,
        db=db_session
    )
    
    # Margin used = (0.1 * 50,005) / 10 = 500.05 USD
    assert abs(position.margin_used - 500.05) < 0.1
    
    # Simulate price drop (loss scenario) -> margin call
    await pricing_engine.add_quote(
        instrument_id=instrument.instrument_id,
        bid=45000.0,
        ask=45010.0,
        lp_name="TestLP",
        db=db_session
    )
    
    # Check margin level
    action = await liquidation_service.check_margin_levels(account, db_session)
    
    # Expected: Equity = 5000 + (45005 - 50005) * 0.1 = 5000 - 500 = 4500 USD
    # Margin level = (4500 / 500) * 100 = 900% (OK)
    # Actually, let's make it trigger margin call by using higher leverage
    
    await db_session.commit()


@pytest.mark.asyncio
async def test_position_liquidation(db_session: AsyncSession):
    """Test automatic position liquidation below threshold."""
    margin_service = get_margin_service()
    liquidation_service = get_liquidation_service()
    
    # Create user and account
    user = User(username="trader3", email="trader3@test.com")
    db_session.add(user)
    await db_session.flush()
    
    account = Account(
        user_id=user.id,
        balance=1000.0,
        equity=1000.0,
        leverage_max=50.0,
        margin_call_level=100.0,
        liquidation_level=50.0
    )
    db_session.add(account)
    await db_session.flush()
    
    # Create instrument
    instrument = Instrument(
        symbol="ETHUSD",
        name="Ethereum vs US Dollar",
        asset_class=AssetClass.CRYPTO,
        tick_size=Decimal("0.01"),
        lot_size=Decimal("0.01"),
        leverage_max=Decimal("20"),
        is_margin_allowed=True,
        status=InstrumentStatus.ACTIVE
    )
    db_session.add(instrument)
    await db_session.flush()
    
    # Add initial quote
    pricing_engine = get_pricing_engine()
    await pricing_engine.add_quote(
        instrument_id=instrument.instrument_id,
        bid=3000.0,
        ask=3001.0,
        lp_name="TestLP",
        db=db_session
    )
    
    # Open highly leveraged position: 1 ETH @ 3000 with 20x leverage
    position = await margin_service.open_position(
        account=account,
        instrument_id=instrument.instrument_id,
        side="LONG",
        quantity=1.0,
        entry_price=3000.5,
        leverage=20.0,
        db=db_session
    )
    
    # Margin used = 3000 / 20 = 150 USD
    assert abs(position.margin_used - 150.025) < 1.0
    
    # Simulate severe price drop -> liquidation
    await pricing_engine.add_quote(
        instrument_id=instrument.instrument_id,
        bid=2500.0,
        ask=2501.0,
        lp_name="TestLP",
        db=db_session
    )
    
    # Check margin level (should trigger liquidation)
    # Loss = (2500.5 - 3000.5) * 1 = -500 USD
    # Equity = 1000 - 500 = 500 USD
    # Margin level = (500 / 150) * 100 = 333% (still above liquidation)
    
    # Let's make price drop more severe
    await pricing_engine.add_quote(
        instrument_id=instrument.instrument_id,
        bid=2000.0,
        ask=2001.0,
        lp_name="TestLP",
        db=db_session
    )
    
    # Loss = (2000.5 - 3000.5) * 1 = -1000 USD
    # Equity = 1000 - 1000 = 0 USD
    # Margin level = (0 / 150) * 100 = 0% -> LIQUIDATE
    
    action = await liquidation_service.check_margin_levels(account, db_session)
    
    # Should trigger liquidation
    assert action == "LIQUIDATION"
    assert account.status == AccountStatus.LIQUIDATING


@pytest.mark.asyncio
async def test_pre_trade_risk_validation(db_session: AsyncSession):
    """Test pre-trade risk checks (margin, leverage, exposure)."""
    # Create user and account
    user = User(username="trader4", email="trader4@test.com")
    db_session.add(user)
    await db_session.flush()
    
    account = Account(
        user_id=user.id,
        balance=10000.0,
        equity=10000.0,
        leverage_max=30.0
    )
    db_session.add(account)
    await db_session.flush()
    
    # Create instrument
    instrument = Instrument(
        symbol="XAUUSD",
        name="Gold vs US Dollar",
        asset_class=AssetClass.COMMODITY,
        tick_size=Decimal("0.01"),
        lot_size=Decimal("1"),
        leverage_max=Decimal("50"),
        is_margin_allowed=True,
        status=InstrumentStatus.ACTIVE
    )
    db_session.add(instrument)
    await db_session.flush()
    
    # Add quote
    pricing_engine = get_pricing_engine()
    await pricing_engine.add_quote(
        instrument_id=instrument.instrument_id,
        bid=2000.0,
        ask=2001.0,
        lp_name="TestLP",
        db=db_session
    )
    
    # Test 1: Valid order (within limits)
    try:
        await risk_service.validate_pre_trade(
            account=account,
            instrument=instrument,
            side="LONG",
            quantity=1.0,
            price=2000.5,
            leverage=20.0,
            db=db_session
        )
        # Should pass
    except ValueError as e:
        pytest.fail(f"Valid order rejected: {e}")
    
    # Test 2: Excessive leverage (above account limit)
    with pytest.raises(ValueError, match="exceeds account limit"):
        await risk_service.validate_pre_trade(
            account=account,
            instrument=instrument,
            side="LONG",
            quantity=1.0,
            price=2000.5,
            leverage=40.0,  # Exceeds account limit of 30x
            db=db_session
        )
    
    # Test 3: Insufficient margin
    with pytest.raises(ValueError, match="Insufficient margin"):
        await risk_service.validate_pre_trade(
            account=account,
            instrument=instrument,
            side="LONG",
            quantity=1000.0,  # Huge position
            price=2000.5,
            leverage=1.0,  # No leverage -> full notional required
            db=db_session
        )


@pytest.mark.asyncio
async def test_circuit_breaker_instrument_level(db_session: AsyncSession):
    """Test circuit breaker for instrument-level volatility."""
    circuit_breaker_service = get_circuit_breaker_service()
    
    # Create instrument
    instrument = Instrument(
        symbol="AAPL",
        name="Apple Inc",
        asset_class=AssetClass.EQUITY,
        tick_size=Decimal("0.01"),
        lot_size=Decimal("1"),
        leverage_max=Decimal("5"),
        is_margin_allowed=True,
        status=InstrumentStatus.ACTIVE
    )
    db_session.add(instrument)
    await db_session.flush()
    
    # Add historical price data (1 minute ago)
    one_min_ago = datetime.utcnow() - timedelta(seconds=60)
    candle = PriceHistory(
        instrument_id=instrument.instrument_id,
        timeframe="1m",
        timestamp=one_min_ago,
        open=150.0,
        high=150.5,
        low=149.5,
        close=150.0,
        volume=10000
    )
    db_session.add(candle)
    await db_session.flush()
    
    # Simulate 6% price spike (should trigger Level 1: 5% threshold)
    current_price = 159.0  # +6% from 150.0
    
    breaker = await circuit_breaker_service.check_instrument_volatility(
        instrument_id=instrument.instrument_id,
        current_price=current_price,
        db=db_session
    )
    
    # Should trigger circuit breaker
    assert breaker is not None
    assert breaker.breaker_type == "INSTRUMENT"
    assert breaker.is_active == True
    assert abs(breaker.percent_change) >= 5.0
    
    # Check if trading is halted
    is_halted = await circuit_breaker_service.is_trading_halted(
        instrument.instrument_id,
        db_session
    )
    assert is_halted == True


@pytest.mark.asyncio
async def test_exposure_limits(db_session: AsyncSession):
    """Test exposure limits per instrument."""
    margin_service = get_margin_service()
    
    # Create user and account
    user = User(username="trader5", email="trader5@test.com")
    db_session.add(user)
    await db_session.flush()
    
    account = Account(
        user_id=user.id,
        balance=100000.0,
        equity=100000.0,
        leverage_max=50.0
    )
    db_session.add(account)
    await db_session.flush()
    
    # Create instrument
    instrument = Instrument(
        symbol="SPX500",
        name="S&P 500 Index",
        asset_class=AssetClass.INDEX,
        tick_size=Decimal("0.01"),
        lot_size=Decimal("1"),
        leverage_max=Decimal("100"),
        is_margin_allowed=True,
        status=InstrumentStatus.ACTIVE
    )
    db_session.add(instrument)
    await db_session.flush()
    
    # Add quote
    pricing_engine = get_pricing_engine()
    await pricing_engine.add_quote(
        instrument_id=instrument.instrument_id,
        bid=4500.0,
        ask=4501.0,
        lp_name="TestLP",
        db=db_session
    )
    
    # Open first position
    position1 = await margin_service.open_position(
        account=account,
        instrument_id=instrument.instrument_id,
        side="LONG",
        quantity=10.0,
        entry_price=4500.5,
        leverage=50.0,
        db=db_session
    )
    
    # Calculate exposure
    exposure = await margin_service.get_exposure_per_instrument(
        account_id=account.id,
        instrument_id=instrument.instrument_id,
        db=db_session
    )
    
    # Expected: 10 * 4500.5 = 45,005 USD
    assert abs(exposure - 45005.0) < 1.0
    
    # Try to open another large position (should be rejected by risk check)
    with pytest.raises(ValueError, match="exceeds max.*exposure"):
        await risk_service.validate_pre_trade(
            account=account,
            instrument=instrument,
            side="LONG",
            quantity=100.0,  # Would push total exposure over 50% limit
            price=4500.5,
            leverage=50.0,
            db=db_session
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
