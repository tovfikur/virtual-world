"""
Tests for position management service.
"""

import pytest
from datetime import datetime
from uuid import uuid4

from app.models.account import Account, Position
from app.models.instrument import Instrument
from app.services.position_service import PositionService, PositionMode


@pytest.fixture
async def test_instrument(db_session):
    """Create test instrument."""
    instrument = Instrument(
        id=uuid4(),
        symbol="EUR/USD",
        name="Euro vs US Dollar",
        asset_class="FX",
        quote_currency="USD",
        pip_size=0.0001,
        min_quantity=0.01,
        max_quantity=100.0,
        margin_requirement=0.01,  # 1%
        is_active=True
    )
    db_session.add(instrument)
    await db_session.commit()
    await db_session.refresh(instrument)
    return instrument


@pytest.fixture
async def test_account(db_session):
    """Create test account with $10,000 balance."""
    account = Account(
        user_id=1,
        balance=10000.0,
        equity=10000.0,
        used_margin=0.0,
        free_margin=10000.0,
        max_leverage=100.0,
        margin_call_level=100.0,
        liquidation_level=50.0
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)
    return account


@pytest.mark.asyncio
async def test_open_position_net_mode(db_session, test_account, test_instrument):
    """Test opening a position in net mode."""
    service = PositionService(mode=PositionMode.NET)
    
    # Open long position
    position = await service.add_to_position(
        account=test_account,
        instrument_id=test_instrument.id,
        side="LONG",
        quantity=1.0,
        price=1.1000,
        leverage=10.0,
        db=db_session
    )
    
    assert position is not None
    assert position.side == "LONG"
    assert position.quantity == 1.0
    assert position.entry_price == 1.1000
    assert position.leverage_used == 10.0
    assert position.closed_at is None


@pytest.mark.asyncio
async def test_add_to_existing_position(db_session, test_account, test_instrument):
    """Test adding to an existing position (VWAP calculation)."""
    service = PositionService(mode=PositionMode.NET)
    
    # Open initial position: 1.0 lot @ 1.1000
    pos1 = await service.add_to_position(
        test_account, test_instrument.id, "LONG", 1.0, 1.1000, 10.0, db_session
    )
    
    # Add to position: 1.0 lot @ 1.1100
    pos2 = await service.add_to_position(
        test_account, test_instrument.id, "LONG", 1.0, 1.1100, 10.0, db_session
    )
    
    # Should be same position with updated quantity and VWAP
    assert pos2.id == pos1.id
    assert pos2.quantity == 2.0
    
    # VWAP: (1.0 * 1.1000 + 1.0 * 1.1100) / 2.0 = 1.1050
    expected_vwap = 1.1050
    assert abs(pos2.entry_price - expected_vwap) < 0.0001


@pytest.mark.asyncio
async def test_net_opposite_positions(db_session, test_account, test_instrument):
    """Test netting: opening opposite side reduces position."""
    service = PositionService(mode=PositionMode.NET)
    
    # Open long position: 2.0 lots
    pos1 = await service.add_to_position(
        test_account, test_instrument.id, "LONG", 2.0, 1.1000, 10.0, db_session
    )
    
    # Open short 1.0 lot (should reduce long position)
    pos2 = await service.add_to_position(
        test_account, test_instrument.id, "SHORT", 1.0, 1.1050, 10.0, db_session
    )
    
    # Position should be reduced
    await db_session.refresh(pos1)
    assert pos1.quantity == 1.0
    assert pos1.side == "LONG"


@pytest.mark.asyncio
async def test_net_exact_opposite(db_session, test_account, test_instrument):
    """Test netting: exact opposite closes position."""
    service = PositionService(mode=PositionMode.NET)
    
    # Open long 1.0 lot
    pos1 = await service.add_to_position(
        test_account, test_instrument.id, "LONG", 1.0, 1.1000, 10.0, db_session
    )
    
    # Open short 1.0 lot (exact opposite)
    await service.add_to_position(
        test_account, test_instrument.id, "SHORT", 1.0, 1.1050, 10.0, db_session
    )
    
    # Position should be closed
    await db_session.refresh(pos1)
    assert pos1.closed_at is not None


@pytest.mark.asyncio
async def test_net_reverse_position(db_session, test_account, test_instrument):
    """Test netting: larger opposite creates new position."""
    service = PositionService(mode=PositionMode.NET)
    
    # Open long 1.0 lot
    pos1 = await service.add_to_position(
        test_account, test_instrument.id, "LONG", 1.0, 1.1000, 10.0, db_session
    )
    
    # Open short 2.0 lots (closes long, opens short 1.0)
    pos2 = await service.add_to_position(
        test_account, test_instrument.id, "SHORT", 2.0, 1.1050, 10.0, db_session
    )
    
    # Should be new short position
    assert pos2.id != pos1.id
    assert pos2.side == "SHORT"
    assert pos2.quantity == 1.0
    
    # Original should be closed
    await db_session.refresh(pos1)
    assert pos1.closed_at is not None


@pytest.mark.asyncio
async def test_hedged_mode_separate_positions(db_session, test_account, test_instrument):
    """Test hedged mode: can have separate long and short positions."""
    service = PositionService(mode=PositionMode.HEDGED)
    
    # Open long position
    long_pos = await service.add_to_position(
        test_account, test_instrument.id, "LONG", 1.0, 1.1000, 10.0, db_session
    )
    
    # Open short position (does not net)
    short_pos = await service.add_to_position(
        test_account, test_instrument.id, "SHORT", 1.0, 1.1050, 10.0, db_session
    )
    
    # Should be two separate positions
    assert long_pos.id != short_pos.id
    assert long_pos.side == "LONG"
    assert short_pos.side == "SHORT"
    assert long_pos.quantity == 1.0
    assert short_pos.quantity == 1.0


@pytest.mark.asyncio
async def test_hedge_position(db_session, test_account, test_instrument):
    """Test opening hedge position."""
    service = PositionService(mode=PositionMode.HEDGED)
    
    # Open long position
    await service.add_to_position(
        test_account, test_instrument.id, "LONG", 1.0, 1.1000, 10.0, db_session
    )
    
    # Hedge with short
    hedge_pos = await service.hedge_position(
        test_account, test_instrument.id, 0.5, 1.1050, 10.0, db_session
    )
    
    assert hedge_pos.side == "SHORT"
    assert hedge_pos.quantity == 0.5


@pytest.mark.asyncio
async def test_close_position(db_session, test_account, test_instrument):
    """Test closing entire position."""
    service = PositionService(mode=PositionMode.NET)
    
    # Open position
    position = await service.add_to_position(
        test_account, test_instrument.id, "LONG", 1.0, 1.1000, 10.0, db_session
    )
    
    # Close position at profit
    pnl = await service.close_position(position, 1.1100, db_session)
    
    # P&L should be positive (bought at 1.1000, sold at 1.1100)
    assert pnl > 0
    
    # Position should be closed
    await db_session.refresh(position)
    assert position.closed_at is not None


@pytest.mark.asyncio
async def test_partial_close(db_session, test_account, test_instrument):
    """Test partial position close."""
    service = PositionService(mode=PositionMode.NET)
    
    # Open position: 2.0 lots
    position = await service.add_to_position(
        test_account, test_instrument.id, "LONG", 2.0, 1.1000, 10.0, db_session
    )
    
    original_quantity = position.quantity
    
    # Close half
    pnl = await service.partial_close(position, 1.0, 1.1100, db_session)
    
    # P&L should be from 1.0 lot
    assert pnl > 0
    
    # Position should still be open with reduced quantity
    await db_session.refresh(position)
    assert position.closed_at is None
    assert position.quantity == 1.0
    assert position.quantity == original_quantity - 1.0


@pytest.mark.asyncio
async def test_reverse_position(db_session, test_account, test_instrument):
    """Test reversing position direction."""
    service = PositionService(mode=PositionMode.NET)
    
    # Open long position
    long_pos = await service.add_to_position(
        test_account, test_instrument.id, "LONG", 1.0, 1.1000, 10.0, db_session
    )
    
    # Reverse to short 1.5 lots
    short_pos = await service.reverse_position(
        long_pos, 1.5, 1.1050, db_session
    )
    
    # Original long should be closed
    await db_session.refresh(long_pos)
    assert long_pos.closed_at is not None
    
    # New short position
    assert short_pos.side == "SHORT"
    assert short_pos.quantity == 1.5
    assert short_pos.entry_price == 1.1050


@pytest.mark.asyncio
async def test_get_position_summary(db_session, test_account, test_instrument):
    """Test portfolio position summary."""
    service = PositionService(mode=PositionMode.NET)
    
    # Open multiple positions
    await service.add_to_position(
        test_account, test_instrument.id, "LONG", 1.0, 1.1000, 10.0, db_session
    )
    await service.add_to_position(
        test_account, test_instrument.id, "SHORT", 0.5, 1.1050, 10.0, db_session
    )
    
    # Get summary
    summary = await service.get_position_summary(test_account.id, db_session)
    
    assert summary["open_positions"] >= 1
    assert summary["total_exposure"] > 0
    assert "by_instrument" in summary
    assert "by_side" in summary


@pytest.mark.asyncio
async def test_insufficient_margin(db_session, test_account, test_instrument):
    """Test position opening fails with insufficient margin."""
    service = PositionService(mode=PositionMode.NET)
    
    # Try to open position larger than account can handle
    with pytest.raises(ValueError, match="Insufficient margin"):
        await service.add_to_position(
            test_account,
            test_instrument.id,
            "LONG",
            1000.0,  # Very large position
            1.1000,
            100.0,
            db_session
        )


@pytest.mark.asyncio
async def test_position_pnl_calculation(db_session, test_account, test_instrument):
    """Test position P&L updates correctly."""
    service = PositionService(mode=PositionMode.NET)
    
    # Open long position
    position = await service.add_to_position(
        test_account, test_instrument.id, "LONG", 1.0, 1.1000, 10.0, db_session
    )
    
    # Manually set current price
    position.current_price = 1.1100
    
    # Calculate P&L
    from app.services.pnl_service import get_pnl_service
    pnl_service = get_pnl_service()
    
    pnl, pct_return = await pnl_service.calculate_position_pnl(position, 1.1100)
    
    # Long position: profit = (1.1100 - 1.1000) * 1.0 = 0.01 per unit
    assert pnl > 0
    assert pct_return > 0


@pytest.mark.asyncio
async def test_update_position_prices(db_session, test_account, test_instrument):
    """Test bulk position price updates."""
    service = PositionService(mode=PositionMode.NET)
    
    # Open position
    position = await service.add_to_position(
        test_account, test_instrument.id, "LONG", 1.0, 1.1000, 10.0, db_session
    )
    
    # TODO: Mock pricing engine to return quote
    # await service.update_position_prices(test_account.id, db_session)
    # await db_session.refresh(position)
    # assert position.current_price is not None


@pytest.mark.asyncio
async def test_hedging_not_allowed_in_net_mode(db_session, test_account, test_instrument):
    """Test hedging fails in net mode."""
    service = PositionService(mode=PositionMode.NET)
    
    # Open long position
    await service.add_to_position(
        test_account, test_instrument.id, "LONG", 1.0, 1.1000, 10.0, db_session
    )
    
    # Try to hedge (should fail in net mode)
    with pytest.raises(ValueError, match="Hedging only available"):
        await service.hedge_position(
            test_account, test_instrument.id, 0.5, 1.1050, 10.0, db_session
        )
