"""
Tests for fee calculation, PnL tracking, and swap/funding rate services.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.account import Account
from app.models.instrument import Instrument, AssetClass, InstrumentStatus
from app.models.order import Order, OrderSide, OrderType
from app.models.trade import Trade
from app.models.fee_schedule import (
    FeeSchedule, FeeVolumeTier, InstrumentFeeOverride,
    AccountFeeSchedule, SwapRate, FundingRate, Commission, FeeType
)
from app.services.fee_service import get_fee_service
from app.services.pnl_service import get_pnl_service
from app.services.swap_service import get_swap_service
from app.services.margin_service import get_margin_service


@pytest.mark.asyncio
async def test_percentage_fee_calculation(db_session: AsyncSession):
    """Test percentage-based fee calculation."""
    fee_service = get_fee_service()
    
    # Create fee schedule with 0.1% maker, 0.2% taker
    schedule = FeeSchedule(
        name="Standard",
        maker_fee_type=FeeType.PERCENTAGE,
        maker_fee_value=0.001,  # 0.1%
        taker_fee_type=FeeType.PERCENTAGE,
        taker_fee_value=0.002,  # 0.2%
        is_default=True,
        is_active=True
    )
    db_session.add(schedule)
    await db_session.flush()
    
    # Create user and account
    user = User(username="trader1", email="trader1@test.com")
    db_session.add(user)
    await db_session.flush()
    
    account = Account(user_id=user.id, balance=10000.0, equity=10000.0)
    db_session.add(account)
    await db_session.flush()
    
    # Link account to schedule
    account_schedule = AccountFeeSchedule(
        account_id=account.id,
        schedule_id=schedule.id
    )
    db_session.add(account_schedule)
    await db_session.flush()
    
    # Create instrument
    instrument = Instrument(
        symbol="EURUSD",
        name="Euro vs US Dollar",
        asset_class=AssetClass.FX,
        tick_size=Decimal("0.00001"),
        lot_size=Decimal("1000"),
        status=InstrumentStatus.ACTIVE
    )
    db_session.add(instrument)
    await db_session.flush()
    
    # Calculate maker fee (0.1% of notional)
    notional = 100000.0  # $100k trade
    maker_fee, details = await fee_service.calculate_trade_fee(
        account_id=account.id,
        instrument_id=instrument.instrument_id,
        notional_value=notional,
        quantity=100000.0,
        is_maker=True,
        db=db_session
    )
    
    # Expected: 0.001 * 100,000 = 100 USD
    assert abs(maker_fee - 100.0) < 0.01
    assert details["fee_type"] == "MAKER"
    
    # Calculate taker fee (0.2% of notional)
    taker_fee, details = await fee_service.calculate_trade_fee(
        account_id=account.id,
        instrument_id=instrument.instrument_id,
        notional_value=notional,
        quantity=100000.0,
        is_maker=False,
        db=db_session
    )
    
    # Expected: 0.002 * 100,000 = 200 USD
    assert abs(taker_fee - 200.0) < 0.01
    assert details["fee_type"] == "TAKER"


@pytest.mark.asyncio
async def test_volume_tier_discount(db_session: AsyncSession):
    """Test volume-based fee tiers."""
    fee_service = get_fee_service()
    
    # Create fee schedule
    schedule = FeeSchedule(
        name="Tiered",
        maker_fee_type=FeeType.PERCENTAGE,
        maker_fee_value=0.002,  # 0.2% base
        taker_fee_type=FeeType.PERCENTAGE,
        taker_fee_value=0.003,  # 0.3% base
        is_default=True,
        is_active=True
    )
    db_session.add(schedule)
    await db_session.flush()
    
    # Add VIP tier for >$1M volume
    vip_tier = FeeVolumeTier(
        schedule_id=schedule.id,
        min_volume=1000000.0,
        maker_fee_type=FeeType.PERCENTAGE,
        maker_fee_value=0.0005,  # 0.05% (75% discount)
        taker_fee_type=FeeType.PERCENTAGE,
        taker_fee_value=0.001,   # 0.1% (67% discount)
        tier_name="VIP"
    )
    db_session.add(vip_tier)
    await db_session.flush()
    
    # Create account with high volume
    user = User(username="vip_trader", email="vip@test.com")
    db_session.add(user)
    await db_session.flush()
    
    account = Account(user_id=user.id, balance=100000.0, equity=100000.0)
    db_session.add(account)
    await db_session.flush()
    
    account_schedule = AccountFeeSchedule(
        account_id=account.id,
        schedule_id=schedule.id,
        rolling_volume_30d=2000000.0  # $2M volume
    )
    db_session.add(account_schedule)
    await db_session.flush()
    
    # Create instrument
    instrument = Instrument(
        symbol="BTCUSD",
        name="Bitcoin",
        asset_class=AssetClass.CRYPTO,
        tick_size=Decimal("0.01"),
        lot_size=Decimal("0.001"),
        status=InstrumentStatus.ACTIVE
    )
    db_session.add(instrument)
    await db_session.flush()
    
    # Calculate fee with VIP tier
    notional = 50000.0
    maker_fee, details = await fee_service.calculate_trade_fee(
        account_id=account.id,
        instrument_id=instrument.instrument_id,
        notional_value=notional,
        quantity=1.0,
        is_maker=True,
        db=db_session
    )
    
    # Expected: 0.0005 * 50,000 = 25 USD (VIP rate, not base rate)
    assert abs(maker_fee - 25.0) < 0.01
    assert details["volume_tier"] == "VIP"


@pytest.mark.asyncio
async def test_instrument_fee_override(db_session: AsyncSession):
    """Test per-instrument fee overrides."""
    fee_service = get_fee_service()
    
    # Create base schedule
    schedule = FeeSchedule(
        name="Standard",
        maker_fee_type=FeeType.PERCENTAGE,
        maker_fee_value=0.001,
        taker_fee_type=FeeType.PERCENTAGE,
        taker_fee_value=0.002,
        is_default=True,
        is_active=True
    )
    db_session.add(schedule)
    await db_session.flush()
    
    # Create crypto instrument with higher fees
    instrument = Instrument(
        symbol="ETHUSD",
        name="Ethereum",
        asset_class=AssetClass.CRYPTO,
        tick_size=Decimal("0.01"),
        lot_size=Decimal("0.01"),
        status=InstrumentStatus.ACTIVE
    )
    db_session.add(instrument)
    await db_session.flush()
    
    # Add instrument override (higher fees for crypto)
    override = InstrumentFeeOverride(
        schedule_id=schedule.id,
        instrument_id=instrument.instrument_id,
        maker_fee_type=FeeType.PERCENTAGE,
        maker_fee_value=0.005,  # 0.5%
        taker_fee_type=FeeType.PERCENTAGE,
        taker_fee_value=0.008   # 0.8%
    )
    db_session.add(override)
    await db_session.flush()
    
    # Create account
    user = User(username="crypto_trader", email="crypto@test.com")
    db_session.add(user)
    await db_session.flush()
    
    account = Account(user_id=user.id, balance=10000.0, equity=10000.0)
    db_session.add(account)
    await db_session.flush()
    
    account_schedule = AccountFeeSchedule(
        account_id=account.id,
        schedule_id=schedule.id
    )
    db_session.add(account_schedule)
    await db_session.flush()
    
    # Calculate fee (should use override, not base rate)
    notional = 5000.0
    maker_fee, details = await fee_service.calculate_trade_fee(
        account_id=account.id,
        instrument_id=instrument.instrument_id,
        notional_value=notional,
        quantity=1.0,
        is_maker=True,
        db=db_session
    )
    
    # Expected: 0.005 * 5,000 = 25 USD (override rate)
    assert abs(maker_fee - 25.0) < 0.01
    assert details["calculation_type"] == FeeType.PERCENTAGE


@pytest.mark.asyncio
async def test_pnl_calculation_long_position(db_session: AsyncSession):
    """Test P&L calculation for long position."""
    pnl_service = get_pnl_service()
    margin_service = get_margin_service()
    
    # Create account
    user = User(username="pnl_test", email="pnl@test.com")
    db_session.add(user)
    await db_session.flush()
    
    account = Account(user_id=user.id, balance=10000.0, equity=10000.0)
    db_session.add(account)
    await db_session.flush()
    
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
    
    # Open long position: 100 shares @ $150
    position = await margin_service.open_position(
        account=account,
        instrument_id=instrument.instrument_id,
        side="LONG",
        quantity=100.0,
        entry_price=150.0,
        leverage=1.0,
        db=db_session
    )
    
    # Calculate P&L at $160 (profit scenario)
    pnl, pct_return = await pnl_service.calculate_position_pnl(
        position, current_price=160.0
    )
    
    # Expected: (160 - 150) * 100 = +$1,000
    assert abs(pnl - 1000.0) < 0.01
    # Return: 1000 / 15000 = 6.67%
    assert abs(pct_return - 6.67) < 0.1


@pytest.mark.asyncio
async def test_pnl_calculation_short_position(db_session: AsyncSession):
    """Test P&L calculation for short position."""
    pnl_service = get_pnl_service()
    margin_service = get_margin_service()
    
    # Create account
    user = User(username="short_test", email="short@test.com")
    db_session.add(user)
    await db_session.flush()
    
    account = Account(user_id=user.id, balance=10000.0, equity=10000.0)
    db_session.add(account)
    await db_session.flush()
    
    # Create instrument
    instrument = Instrument(
        symbol="SPX500",
        name="S&P 500",
        asset_class=AssetClass.INDEX,
        tick_size=Decimal("0.01"),
        lot_size=Decimal("1"),
        leverage_max=Decimal("20"),
        is_margin_allowed=True,
        status=InstrumentStatus.ACTIVE
    )
    db_session.add(instrument)
    await db_session.flush()
    
    # Open short position: 10 contracts @ $4500
    position = await margin_service.open_position(
        account=account,
        instrument_id=instrument.instrument_id,
        side="SHORT",
        quantity=10.0,
        entry_price=4500.0,
        leverage=5.0,
        db=db_session
    )
    
    # Calculate P&L at $4400 (profit for short)
    pnl, pct_return = await pnl_service.calculate_position_pnl(
        position, current_price=4400.0
    )
    
    # Expected: (4500 - 4400) * 10 = +$1,000
    assert abs(pnl - 1000.0) < 0.01


@pytest.mark.asyncio
async def test_swap_fee_calculation(db_session: AsyncSession):
    """Test overnight swap fee calculation."""
    swap_service = get_swap_service()
    margin_service = get_margin_service()
    
    # Create account
    user = User(username="swap_test", email="swap@test.com")
    db_session.add(user)
    await db_session.flush()
    
    account = Account(user_id=user.id, balance=10000.0, equity=10000.0)
    db_session.add(account)
    await db_session.flush()
    
    # Create FX instrument
    instrument = Instrument(
        symbol="GBPUSD",
        name="British Pound",
        asset_class=AssetClass.FX,
        tick_size=Decimal("0.00001"),
        lot_size=Decimal("1000"),
        leverage_max=Decimal("50"),
        is_margin_allowed=True,
        status=InstrumentStatus.ACTIVE
    )
    db_session.add(instrument)
    await db_session.flush()
    
    # Create swap rate: +2 bps for long, -1 bps for short
    swap_rate = SwapRate(
        instrument_id=instrument.instrument_id,
        long_swap_rate=2.0,   # 2 basis points per day
        short_swap_rate=-1.0,  # -1 basis points per day
        effective_date=datetime.utcnow().isoformat(),
        is_active=True
    )
    db_session.add(swap_rate)
    await db_session.flush()
    
    # Open long position
    position = await margin_service.open_position(
        account=account,
        instrument_id=instrument.instrument_id,
        side="LONG",
        quantity=100000.0,
        entry_price=1.2500,
        leverage=50.0,
        db=db_session
    )
    
    # Calculate single day swap
    swap_fee = await swap_service.calculate_swap_fee(position, swap_rate, days=1)
    
    # Expected: (100,000 * 1.25) * (2 / 10000) = 25 USD
    assert abs(swap_fee - 25.0) < 0.01
    
    # Calculate triple swap (Wednesday)
    triple_swap = await swap_service.calculate_swap_fee(position, swap_rate, days=3)
    
    # Expected: 25 * 3 = 75 USD
    assert abs(triple_swap - 75.0) < 0.01


@pytest.mark.asyncio
async def test_portfolio_pnl_aggregation(db_session: AsyncSession):
    """Test portfolio-level P&L aggregation."""
    pnl_service = get_pnl_service()
    margin_service = get_margin_service()
    
    # Create account
    user = User(username="portfolio_test", email="portfolio@test.com")
    db_session.add(user)
    await db_session.flush()
    
    account = Account(user_id=user.id, balance=100000.0, equity=100000.0, leverage_max=50.0)
    db_session.add(account)
    await db_session.flush()
    
    # Create two instruments
    eurusd = Instrument(
        symbol="EURUSD",
        name="Euro",
        asset_class=AssetClass.FX,
        tick_size=Decimal("0.00001"),
        lot_size=Decimal("1000"),
        leverage_max=Decimal("50"),
        is_margin_allowed=True,
        status=InstrumentStatus.ACTIVE
    )
    db_session.add(eurusd)
    
    gbpusd = Instrument(
        symbol="GBPUSD",
        name="Pound",
        asset_class=AssetClass.FX,
        tick_size=Decimal("0.00001"),
        lot_size=Decimal("1000"),
        leverage_max=Decimal("50"),
        is_margin_allowed=True,
        status=InstrumentStatus.ACTIVE
    )
    db_session.add(gbpusd)
    await db_session.flush()
    
    # Open two positions
    pos1 = await margin_service.open_position(
        account, eurusd.instrument_id, "LONG", 100000.0, 1.1000, 50.0, db_session
    )
    pos1.unrealized_pnl = 500.0  # Simulate profit
    
    pos2 = await margin_service.open_position(
        account, gbpusd.instrument_id, "SHORT", 50000.0, 1.2500, 50.0, db_session
    )
    pos2.unrealized_pnl = -200.0  # Simulate loss
    
    # Calculate portfolio P&L
    portfolio = await pnl_service.calculate_portfolio_pnl(account.id, db_session)
    
    # Expected: 500 - 200 = 300 unrealized
    assert abs(portfolio["unrealized_pnl"] - 300.0) < 0.01
    assert portfolio["open_positions"] == 2


@pytest.mark.asyncio
async def test_win_rate_calculation(db_session: AsyncSession):
    """Test win rate statistics."""
    pnl_service = get_pnl_service()
    
    # Create account
    user = User(username="stats_test", email="stats@test.com")
    db_session.add(user)
    await db_session.flush()
    
    account = Account(user_id=user.id, balance=10000.0, equity=10000.0)
    db_session.add(account)
    await db_session.flush()
    
    # Create instrument
    instrument = Instrument(
        symbol="TEST",
        name="Test",
        asset_class=AssetClass.FX,
        tick_size=Decimal("0.00001"),
        lot_size=Decimal("1000"),
        status=InstrumentStatus.ACTIVE
    )
    db_session.add(instrument)
    await db_session.flush()
    
    # Create closed positions (3 wins, 2 losses)
    from app.models.account import Position
    
    # Winners
    for pnl in [100.0, 150.0, 200.0]:
        pos = Position(
            account_id=account.id,
            instrument_id=instrument.instrument_id,
            side="LONG",
            quantity=1000.0,
            entry_price=1.0,
            realized_pnl=pnl,
            margin_used=100.0,
            leverage_used=1.0,
            closed_at=datetime.utcnow().isoformat()
        )
        db_session.add(pos)
    
    # Losers
    for pnl in [-50.0, -75.0]:
        pos = Position(
            account_id=account.id,
            instrument_id=instrument.instrument_id,
            side="LONG",
            quantity=1000.0,
            entry_price=1.0,
            realized_pnl=pnl,
            margin_used=100.0,
            leverage_used=1.0,
            closed_at=datetime.utcnow().isoformat()
        )
        db_session.add(pos)
    
    await db_session.flush()
    
    # Calculate win rate
    stats = await pnl_service.calculate_win_rate(account.id, db_session)
    
    # Expected: 3 wins out of 5 = 60%
    assert abs(stats["win_rate"] - 60.0) < 0.1
    assert stats["winning_trades"] == 3
    assert stats["losing_trades"] == 2
    assert abs(stats["average_win"] - 150.0) < 0.1  # (100+150+200)/3
    assert abs(stats["average_loss"] - (-62.5)) < 0.1  # (-50-75)/2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
