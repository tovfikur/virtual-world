"""
Tests for settlement and clearing service.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from app.models.account import Account
from app.models.instrument import Instrument
from app.models.trade import Trade
from app.models.settlement import (
    TradeConfirmation, SettlementRecord, CustodyBalance,
    SettlementStatus, SettlementType
)
from app.services.settlement_service import get_settlement_service


@pytest.fixture
async def test_instrument(db_session):
    """Create test instrument."""
    instrument = Instrument(
        id=uuid4(),
        symbol="AAPL",
        name="Apple Inc.",
        asset_class="EQUITY",
        quote_currency="USD",
        pip_size=0.01,
        min_quantity=1.0,
        max_quantity=10000.0,
        margin_requirement=0.25,
        is_active=True
    )
    db_session.add(instrument)
    await db_session.commit()
    await db_session.refresh(instrument)
    return instrument


@pytest.fixture
async def buyer_account(db_session):
    """Create buyer account with $100,000."""
    account = Account(
        user_id=1,
        balance=100000.0,
        equity=100000.0,
        used_margin=0.0,
        free_margin=100000.0,
        max_leverage=10.0
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)
    return account


@pytest.fixture
async def seller_account(db_session):
    """Create seller account with $100,000."""
    account = Account(
        user_id=2,
        balance=100000.0,
        equity=100000.0,
        used_margin=0.0,
        free_margin=100000.0,
        max_leverage=10.0
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)
    return account


@pytest.fixture
async def test_trade(db_session, buyer_account, seller_account, test_instrument):
    """Create test trade."""
    trade = Trade(
        buyer_account_id=buyer_account.id,
        seller_account_id=seller_account.id,
        instrument_id=test_instrument.id,
        quantity=100.0,
        execution_price=150.0,
        execution_timestamp=datetime.utcnow(),
        is_maker=True,
        status="MATCHED"
    )
    db_session.add(trade)
    await db_session.commit()
    await db_session.refresh(trade)
    return trade


@pytest.mark.asyncio
async def test_create_trade_confirmation(db_session, test_trade, test_instrument):
    """Test creating trade confirmation."""
    service = get_settlement_service()
    
    confirmation = await service.create_trade_confirmation(
        test_trade, settlement_days=2, db=db_session
    )
    
    assert confirmation is not None
    assert confirmation.trade_id == test_trade.id
    assert confirmation.quantity == 100.0
    assert confirmation.price == 150.0
    assert confirmation.gross_amount == 15000.0
    assert confirmation.settlement_status == SettlementStatus.PENDING


@pytest.mark.asyncio
async def test_confirm_trade_buyer(db_session, test_trade):
    """Test buyer confirmation."""
    service = get_settlement_service()
    
    # Create confirmation
    confirmation = await service.create_trade_confirmation(
        test_trade, settlement_days=2, db=db_session
    )
    
    # Buyer confirms
    confirmed = await service.confirm_trade(
        confirmation.id, test_trade.buyer_account_id, is_buyer=True, db=db_session
    )
    
    assert confirmed.buyer_confirmed == True
    assert confirmed.buyer_confirmed_at is not None
    assert confirmed.settlement_status == SettlementStatus.PENDING  # Waiting for seller


@pytest.mark.asyncio
async def test_confirm_trade_both_parties(db_session, test_trade):
    """Test both parties confirming settlement."""
    service = get_settlement_service()
    
    # Create confirmation
    confirmation = await service.create_trade_confirmation(
        test_trade, settlement_days=2, db=db_session
    )
    
    # Buyer confirms
    await service.confirm_trade(
        confirmation.id, test_trade.buyer_account_id, is_buyer=True, db=db_session
    )
    
    # Seller confirms
    confirmed = await service.confirm_trade(
        confirmation.id, test_trade.seller_account_id, is_buyer=False, db=db_session
    )
    
    assert confirmed.buyer_confirmed == True
    assert confirmed.seller_confirmed == True
    assert confirmed.settlement_status == SettlementStatus.CONFIRMED


@pytest.mark.asyncio
async def test_confirm_wrong_party(db_session, test_trade):
    """Test that wrong party cannot confirm."""
    service = get_settlement_service()
    
    confirmation = await service.create_trade_confirmation(
        test_trade, settlement_days=2, db=db_session
    )
    
    # Wrong account tries to confirm
    with pytest.raises(ValueError, match="Not the buyer"):
        await service.confirm_trade(
            confirmation.id, 999, is_buyer=True, db=db_session
        )


@pytest.mark.asyncio
async def test_settlement_amount_calculation(db_session, test_trade):
    """Test settlement amount calculations with fees."""
    service = get_settlement_service()
    
    # Create confirmation
    confirmation = await service.create_trade_confirmation(
        test_trade, settlement_days=2, db=db_session
    )
    
    # Verify amounts
    gross = 100.0 * 150.0  # 15,000
    assert confirmation.gross_amount == gross
    assert confirmation.net_amount > 0
    assert confirmation.buyer_fee > 0
    assert confirmation.seller_fee > 0


@pytest.mark.asyncio
async def test_net_trades(db_session, buyer_account, seller_account, test_instrument):
    """Test netting multiple trades."""
    from app.models.trade import Trade
    
    service = get_settlement_service()
    
    # Create multiple trades for netting
    trades = []
    for i in range(3):
        trade = Trade(
            buyer_account_id=buyer_account.id,
            seller_account_id=seller_account.id,
            instrument_id=test_instrument.id,
            quantity=50.0,
            execution_price=150.0,
            execution_timestamp=datetime.utcnow(),
            status="MATCHED"
        )
        db_session.add(trade)
        trades.append(trade)
    
    await db_session.flush()
    
    # Create confirmations
    confirmations = []
    for trade in trades:
        conf = await service.create_trade_confirmation(
            trade, settlement_days=2, db=db_session
        )
        confirmations.append(conf)
    
    # Confirm all trades
    for conf in confirmations:
        await service.confirm_trade(conf.id, buyer_account.id, is_buyer=True, db=db_session)
        await service.confirm_trade(conf.id, seller_account.id, is_buyer=False, db=db_session)
    
    # Net trades
    batch = await service.net_trades(db=db_session)
    
    assert batch is not None
    assert batch.trade_count == 3
    assert batch.buy_quantity > 0
    assert batch.net_amount > 0


@pytest.mark.asyncio
async def test_settle_trade(db_session, test_trade, buyer_account, seller_account):
    """Test settling a trade."""
    service = get_settlement_service()
    
    initial_buyer_balance = buyer_account.balance
    initial_seller_balance = seller_account.balance
    
    # Create and confirm trade
    confirmation = await service.create_trade_confirmation(
        test_trade, settlement_days=2, db=db_session
    )
    
    await service.confirm_trade(
        confirmation.id, buyer_account.id, is_buyer=True, db=db_session
    )
    await service.confirm_trade(
        confirmation.id, seller_account.id, is_buyer=False, db=db_session
    )
    
    # Settle
    settlement = await service.settle_trade(confirmation.id, db=db_session)
    
    assert settlement is not None
    assert settlement.status == SettlementStatus.SETTLED
    assert settlement.actual_settlement_date is not None
    
    # Verify balances updated
    await db_session.refresh(buyer_account)
    await db_session.refresh(seller_account)
    
    assert buyer_account.balance < initial_buyer_balance  # Paid for shares
    assert seller_account.balance > initial_seller_balance  # Received payment


@pytest.mark.asyncio
async def test_custody_balance_update(db_session, buyer_account, test_instrument):
    """Test custody balance updates."""
    service = get_settlement_service()
    
    # Update custody
    custody = await service._update_custody_balance(
        buyer_account.id, test_instrument.id, 100.0, "credit", db=db_session
    )
    
    assert custody.quantity_settled == 100.0
    assert custody.balance == 100.0


@pytest.mark.asyncio
async def test_settlement_failure_handling(db_session, test_trade, buyer_account, seller_account):
    """Test settlement failure and exception recording."""
    service = get_settlement_service()
    
    # Create and confirm trade
    confirmation = await service.create_trade_confirmation(
        test_trade, settlement_days=2, db=db_session
    )
    
    await service.confirm_trade(
        confirmation.id, buyer_account.id, is_buyer=True, db=db_session
    )
    await service.confirm_trade(
        confirmation.id, seller_account.id, is_buyer=False, db=db_session
    )
    
    # Make buyer balance insufficient
    buyer_account.balance = 100.0  # Not enough
    
    # Try to settle (should fail)
    with pytest.raises(Exception):
        await service.settle_trade(confirmation.id, db=db_session)
    
    # Verify failure recorded
    await db_session.refresh(confirmation)
    assert confirmation.settlement_status == SettlementStatus.FAILED


@pytest.mark.asyncio
async def test_reconciliation(db_session, buyer_account, test_instrument):
    """Test custody reconciliation."""
    service = get_settlement_service()
    
    # Create custody balance
    custody = CustodyBalance(
        account_id=buyer_account.id,
        instrument_id=test_instrument.id,
        balance=100.0,
        quantity_settled=100.0
    )
    db_session.add(custody)
    await db_session.flush()
    
    # Reconcile
    report = await service.reconcile_custody(
        account_id=buyer_account.id, db=db_session
    )
    
    assert report is not None
    assert report.status == "complete"
    assert report.is_balanced == True


@pytest.mark.asyncio
async def test_settlement_date_calculation(db_session, test_trade):
    """Test T+N settlement date calculation."""
    service = get_settlement_service()
    
    now = datetime.utcnow()
    expected_settlement = now + timedelta(days=2)
    
    confirmation = await service.create_trade_confirmation(
        test_trade, settlement_days=2, db=db_session
    )
    
    # Settlement date should be 2 business days later
    assert confirmation.settlement_date.date() >= expected_settlement.date()


@pytest.mark.asyncio
async def test_settlement_type_determination(db_session, test_instrument):
    """Test settlement type based on asset class."""
    service = get_settlement_service()
    
    settlement_type = service._determine_settlement_type(test_instrument)
    assert settlement_type == SettlementType.DVP  # Equity = DVP


@pytest.mark.asyncio
async def test_batch_settlement(db_session, buyer_account, seller_account, test_instrument):
    """Test settling entire batch."""
    from app.models.trade import Trade
    
    service = get_settlement_service()
    
    # Create trades
    trades = []
    for i in range(2):
        trade = Trade(
            buyer_account_id=buyer_account.id,
            seller_account_id=seller_account.id,
            instrument_id=test_instrument.id,
            quantity=50.0,
            execution_price=150.0,
            execution_timestamp=datetime.utcnow(),
            status="MATCHED"
        )
        db_session.add(trade)
        trades.append(trade)
    
    await db_session.flush()
    
    # Create and confirm trades
    confirmations = []
    for trade in trades:
        conf = await service.create_trade_confirmation(
            trade, settlement_days=2, db=db_session
        )
        await service.confirm_trade(conf.id, buyer_account.id, is_buyer=True, db=db_session)
        await service.confirm_trade(conf.id, seller_account.id, is_buyer=False, db=db_session)
        confirmations.append(conf)
    
    # Net into batch
    batch = await service.net_trades(db=db_session)
    
    # Settle batch
    result = await service.settle_batch(batch.id, db=db_session)
    
    assert result["settled_count"] == 2
    assert result["failed_count"] == 0


@pytest.mark.asyncio
async def test_broker_payout(db_session, test_trade):
    """Test broker payout processing."""
    service = get_settlement_service()
    
    # Create, confirm, and settle
    confirmation = await service.create_trade_confirmation(
        test_trade, settlement_days=2, db=db_session
    )
    
    await service.confirm_trade(
        confirmation.id, test_trade.buyer_account_id, is_buyer=True, db=db_session
    )
    await service.confirm_trade(
        confirmation.id, test_trade.seller_account_id, is_buyer=False, db=db_session
    )
    
    settlement = await service.settle_trade(confirmation.id, db=db_session)
    
    # Process payout
    success = await service.process_broker_payout(settlement.id, db=db_session)
    
    assert success == True
    
    # Verify payout recorded
    await db_session.refresh(settlement)
    assert settlement.broker_paid == True
    assert settlement.broker_payment_reference is not None
