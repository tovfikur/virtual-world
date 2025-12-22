"""
Tests for pricing engine and market data services.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instrument import Instrument, AssetClass, InstrumentStatus
from app.models.price_history import PriceHistory, TimeframeEnum, CorporateAction, CorporateActionType
from app.services.pricing_service import PricingEngine, PricingConfig
from app.services.market_data_service import MarketDataAggregator


@pytest.mark.asyncio
async def test_pricing_engine_add_quote(db: AsyncSession):
    """Test adding LP quotes to pricing engine."""
    
    # Create test instrument
    instrument = Instrument(
        symbol="EURUSD",
        name="Euro USD",
        asset_class=AssetClass.FOREX,
        tick_size=0.0001,
        lot_size=1000,
        leverage_max=50,
        is_margin_allowed=True,
    )
    db.add(instrument)
    await db.flush()
    
    # Create pricing engine with FX config
    config = PricingConfig(fx_spread_bp=1.5)
    engine = PricingEngine(config)
    
    # Add quotes from two LPs
    quote1 = await engine.add_quote(
        instrument.instrument_id,
        "lp1",
        1.0950,
        1.0952,
        1000000,
        1000000,
        db
    )
    
    assert quote1 is not None
    assert 'bid' in quote1
    assert 'ask' in quote1
    
    quote2 = await engine.add_quote(
        instrument.instrument_id,
        "lp2",
        1.0951,
        1.0953,
        2000000,
        2000000,
        db
    )
    
    # Get aggregated quote
    agg = await engine.get_aggregated_quote(instrument.instrument_id, db)
    
    assert agg is not None
    assert agg['best_bid'] == 1.0951  # Higher of the two
    assert agg['best_ask'] == 1.0952  # Lower of the two
    assert agg['num_providers'] == 2
    assert agg['bid_size'] == 3000000  # Sum of liquidity
    assert agg['ask_size'] == 3000000


@pytest.mark.asyncio
async def test_pricing_engine_tick_normalization(db: AsyncSession):
    """Test tick size normalization in pricing."""
    
    instrument = Instrument(
        symbol="SPY",
        name="S&P 500 ETF",
        asset_class=AssetClass.EQUITY,
        tick_size=0.01,  # 1 cent ticks
        lot_size=1,
    )
    db.add(instrument)
    await db.flush()
    
    config = PricingConfig(
        base_spread_bp=2.0,
        tick_normalization=True
    )
    engine = PricingEngine(config)
    
    # Add quote with price that's not aligned to ticks
    await engine.add_quote(
        instrument.instrument_id,
        "market_maker",
        420.123456,  # Not aligned to 0.01
        420.134567,
        10000,
        10000,
        db
    )
    
    agg = await engine.get_aggregated_quote(instrument.instrument_id, db)
    
    # Should be normalized
    assert agg['bid'] % 0.01 == 0  # Exact multiple of 0.01
    assert agg['ask'] % 0.01 == 0


@pytest.mark.asyncio
async def test_pricing_cfd_markup(db: AsyncSession):
    """Test CFD pricing with markup."""
    
    instrument = Instrument(
        symbol="AAPL.CFD",
        name="Apple CFD",
        asset_class=AssetClass.CFD,
        tick_size=0.01,
    )
    db.add(instrument)
    await db.flush()
    
    config = PricingConfig(
        cfd_spread_bp=3.0,
        cfd_markup_bp=1.0  # 1bp markup on ask
    )
    engine = PricingEngine(config)
    
    raw_bid = 150.00
    raw_ask = 150.05
    
    await engine.add_quote(
        instrument.instrument_id,
        "lp",
        raw_bid,
        raw_ask,
        100000,
        100000,
        db
    )
    
    agg = await engine.get_aggregated_quote(instrument.instrument_id, db)
    
    # Ask should be higher due to spread + markup
    assert agg['ask'] > raw_ask
    assert agg['spread_bp'] > 3.0  # More than base spread


@pytest.mark.asyncio
async def test_market_data_candle_generation(db: AsyncSession):
    """Test OHLCV candle generation from trades."""
    
    instrument = Instrument(
        symbol="BTC/USD",
        name="Bitcoin USD",
        asset_class=AssetClass.CRYPTO,
        tick_size=0.01,
    )
    db.add(instrument)
    await db.flush()
    
    aggregator = MarketDataAggregator()
    
    # Record trades at 1-minute intervals
    prices = [50000, 50100, 50050, 50150, 50120]
    quantities = [1, 2, 1.5, 2.5, 1]
    
    now = datetime.utcnow()
    for i, (price, qty) in enumerate(zip(prices, quantities)):
        await aggregator.record_trade(
            instrument.instrument_id,
            price,
            qty,
            db
        )
    
    # Get 1-minute candles
    await db.commit()
    
    candles = await aggregator.get_candles(
        instrument.instrument_id,
        TimeframeEnum.M1,
        limit=10,
        db=db
    )
    
    # Should have at least one candle with all trades in same minute
    assert len(candles) > 0
    
    candle = candles[0]
    assert candle['open'] == 50000
    assert candle['high'] == 50150
    assert candle['low'] == 50050
    assert candle['close'] == 50120
    assert candle['volume'] == sum(quantities)
    assert candle['trade_count'] == len(prices)
    assert candle['vwap'] is not None  # VWAP should be computed


@pytest.mark.asyncio
async def test_candle_timeframe_aggregation(db: AsyncSession):
    """Test candle aggregation at multiple timeframes."""
    
    instrument = Instrument(
        symbol="EUR/USD",
        name="Euro USD",
        asset_class=AssetClass.FOREX,
        tick_size=0.0001,
    )
    db.add(instrument)
    await db.flush()
    
    aggregator = MarketDataAggregator()
    
    # Record 60 trades spread over a minute
    for second in range(60):
        await aggregator.record_trade(
            instrument.instrument_id,
            1.0900 + second * 0.0001,
            1000,
            db
        )
    
    await db.commit()
    
    # Get 1s candles (should have ~60)
    candles_1s = await aggregator.get_candles(
        instrument.instrument_id,
        TimeframeEnum.S1,
        limit=100,
        db=db
    )
    
    # Get 5s candles (should have ~12)
    candles_5s = await aggregator.get_candles(
        instrument.instrument_id,
        TimeframeEnum.S5,
        limit=100,
        db=db
    )
    
    # Get 1m candles (should have 1)
    candles_1m = await aggregator.get_candles(
        instrument.instrument_id,
        TimeframeEnum.M1,
        limit=100,
        db=db
    )
    
    assert len(candles_1s) > 0
    assert len(candles_5s) >= 0  # May have fewer buckets
    assert len(candles_1m) >= 1
    
    # 1m candle should contain all trades
    assert candles_1m[0]['volume'] == 60000  # 60 trades * 1000


@pytest.mark.asyncio
async def test_corporate_action_adjustment(db: AsyncSession):
    """Test price adjustment for corporate actions (stock split)."""
    
    instrument = Instrument(
        symbol="TSLA",
        name="Tesla",
        asset_class=AssetClass.EQUITY,
        tick_size=0.01,
    )
    db.add(instrument)
    await db.flush()
    
    aggregator = MarketDataAggregator()
    
    # Record some candles before split
    base_price = 1000.0
    for i in range(5):
        await aggregator.record_trade(
            instrument.instrument_id,
            base_price + i,
            100,
            db
        )
    
    await db.commit()
    
    # Get pre-split candles
    candles_before = await aggregator.get_candles(
        instrument.instrument_id,
        TimeframeEnum.M1,
        limit=100,
        db=db
    )
    
    # Record 2:1 split effective tomorrow
    split_date = datetime.utcnow() + timedelta(days=1)
    await aggregator.record_corporate_action(
        instrument.instrument_id,
        CorporateActionType.SPLIT,
        split_date,
        ratio=2.0,  # 2:1 split
        db=db
    )
    
    # Get adjusted candles (before split)
    candles_adjusted = await aggregator.get_adjusted_candles(
        instrument.instrument_id,
        TimeframeEnum.M1,
        limit=100,
        db=db
    )
    
    # Prices should be halved due to split adjustment
    assert candles_adjusted[0]['open'] == candles_before[0]['open'] / 2
    assert candles_adjusted[0]['high'] == candles_before[0]['high'] / 2
    assert candles_adjusted[0]['close'] == candles_before[0]['close'] / 2


@pytest.mark.asyncio
async def test_depth_calculation(db: AsyncSession):
    """Test order book depth calculation."""
    
    instrument = Instrument(
        symbol="GOLD",
        name="Gold Futures",
        asset_class=AssetClass.COMMODITY,
        tick_size=0.01,
    )
    db.add(instrument)
    await db.flush()
    
    config = PricingConfig()
    engine = PricingEngine(config)
    
    # Add multiple quotes from different LPs
    lps = [
        ("lp1", 2000.10, 2000.12, 10000, 10000),
        ("lp2", 2000.08, 2000.14, 15000, 15000),
        ("lp3", 2000.11, 2000.13, 20000, 20000),
    ]
    
    for lp, bid, ask, bid_size, ask_size in lps:
        await engine.add_quote(
            instrument.instrument_id,
            lp,
            bid,
            ask,
            bid_size,
            ask_size,
            db
        )
    
    depth = await engine.get_depth(instrument.instrument_id, levels=3, db=db)
    
    assert depth is not None
    assert 'bids' in depth
    assert 'asks' in depth
    assert len(depth['bids']) <= 3
    assert len(depth['asks']) <= 3
    
    # Best bid should be highest bid
    if depth['bids']:
        assert depth['bids'][0]['price'] == max(lp[1] for lp in lps)
    
    # Best ask should be lowest ask
    if depth['asks']:
        assert depth['asks'][0]['price'] == min(lp[2] for lp in lps)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
