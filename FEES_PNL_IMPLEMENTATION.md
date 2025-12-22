# Fees & PnL Implementation

## Overview

Complete implementation of trading fees, commissions, swap/funding rates, and profit/loss tracking for the VirtualWorld Exchange. This system handles maker/taker fees, volume-based discounts, overnight charges, and comprehensive P&L analytics.

## Components

### 1. Fee Schedule Models (`backend/app/models/fee_schedule.py`)

**FeeSchedule Model**
- Base fee schedule defining maker/taker fees
- Fields:
  - `name`: Schedule name (e.g., "Standard", "VIP")
  - `maker_fee_type`: PERCENTAGE, FLAT, or PER_LOT
  - `maker_fee_value`: Fee value (0.001 = 0.1% for percentage)
  - `taker_fee_type`: Fee calculation method
  - `taker_fee_value`: Taker fee value
  - `min_fee`: Minimum fee cap
  - `max_fee`: Maximum fee cap
  - `is_default`: Default schedule for new accounts
  - `is_active`: Active status

**FeeVolumeTier Model**
- Volume-based discount tiers
- Fields:
  - `min_volume`: Minimum 30-day volume to qualify
  - `maker/taker_fee_type`: Discounted fee type
  - `maker/taker_fee_value`: Reduced fees for high-volume traders
  - `tier_name`: Bronze, Silver, Gold, VIP, etc.

**InstrumentFeeOverride Model**
- Per-instrument fee customization
- Allows higher fees for volatile assets (crypto, commodities)
- Overrides base schedule for specific instruments

**AccountFeeSchedule Model**
- Links accounts to fee schedules
- Tracks 30-day rolling volume for tier calculation
- Supports institutional pricing arrangements

**SwapRate Model**
- Overnight swap/rollover rates for FX and CFDs
- Fields:
  - `long_swap_rate`: Swap in basis points for long positions
  - `short_swap_rate`: Swap for short positions
  - `triple_swap_day`: Day of week for triple swap (0=Monday)
  - `effective_date`: When rate takes effect

**FundingRate Model**
- Funding rates for perpetual futures
- Fields:
  - `rate`: Funding rate (e.g., 0.0001 = 0.01%)
  - `interval_hours`: Funding interval (typically 8 hours)
  - `timestamp`: Current funding period
  - `next_funding_time`: Next funding calculation

**Commission Model**
- Records fee breakdown per trade
- Fields:
  - `maker_fee`: Maker portion
  - `taker_fee`: Taker portion
  - `exchange_fee`: Exchange-level fee
  - `regulatory_fee`: Government/regulatory charges
  - `total_commission`: Total fees charged
  - `fee_type`: "MAKER" or "TAKER"
  - `notional_value`: Trade size for audit

### 2. Fee Calculation Service (`backend/app/services/fee_service.py`)

**Fee Hierarchy:**
1. Instrument-specific override (highest priority)
2. Volume tier discount
3. Base schedule fee (fallback)

**Fee Types:**
- **PERCENTAGE**: `fee_value * notional`
  - Example: 0.001 * $100,000 = $100 (0.1%)
- **FLAT**: Fixed amount per trade
  - Example: $5 per trade regardless of size
- **PER_LOT**: `fee_value * quantity`
  - Example: $0.50 per lot * 100 lots = $50

**Key Methods:**
- `calculate_trade_fee()`: Computes fee based on account, instrument, volume
- `record_commission()`: Creates Commission record for audit
- `deduct_fee_from_account()`: Subtracts fee from balance, updates equity
- `update_rolling_volume()`: Updates 30-day volume for tier calculation
- `get_fee_breakdown()`: Returns fee statistics for period

**Example Calculation:**
```python
# Standard account: 0.1% maker, 0.2% taker
# VIP tier (>$1M volume): 0.05% maker, 0.1% taker
# Crypto override: 0.5% maker, 0.8% taker

notional = $50,000
is_maker = True

if instrument == "BTCUSD" and has_override:
    fee = 0.005 * 50,000 = $250 (override)
elif rolling_volume > $1,000,000:
    fee = 0.0005 * 50,000 = $25 (VIP tier)
else:
    fee = 0.001 * 50,000 = $50 (base rate)
```

### 3. PnL Calculation Service (`backend/app/services/pnl_service.py`)

**P&L Types:**
- **Realized P&L**: Locked-in profit/loss from closed positions
- **Unrealized P&L**: Mark-to-market profit/loss from open positions
- **Total P&L**: Realized + Unrealized

**Position Modes:**
- **Net Mode**: Single position per instrument (default)
- **Hedged Mode**: Separate long/short positions allowed

**Key Calculations:**

**Position P&L:**
```python
# Long position
pnl = (current_price - entry_price) * quantity - swap_fees

# Short position
pnl = (entry_price - current_price) * quantity - swap_fees

# Percent return
return_pct = (pnl / (entry_price * quantity)) * 100
```

**VWAP (Volume Weighted Average Price):**
```python
vwap = sum(trade.price * trade.quantity) / sum(trade.quantity)
```

**Win Rate:**
```python
win_rate = (winning_trades / total_trades) * 100
profit_factor = average_win / average_loss
```

**Key Methods:**
- `calculate_position_pnl()`: Unrealized P&L and percent return
- `calculate_realized_pnl()`: P&L for closed position
- `calculate_vwap()`: Average entry price across multiple fills
- `calculate_portfolio_pnl()`: Aggregate P&L across all positions
- `calculate_portfolio_return()`: ROI and return metrics
- `calculate_win_rate()`: Win/loss statistics
- `get_pnl_statement()`: Comprehensive P&L report

### 4. Swap Fee Service (`backend/app/services/swap_service.py`)

**Swap Fees (FX/CFD):**
- Applied daily at rollover time (00:00 UTC)
- Triple swap on Wednesdays (covers weekend)
- Different rates for long vs short positions
- Calculated in basis points per day

**Funding Rates (Perpetual Futures):**
- Exchanged every 8 hours between longs and shorts
- Positive rate: longs pay shorts
- Negative rate: shorts pay longs
- Based on spot-perpetual price difference

**Swap Calculation:**
```python
# Single day swap
rate_decimal = swap_rate_bps / 10000
notional = quantity * current_price
swap_fee = notional * rate_decimal * days

# Example: 100,000 EUR @ 1.2500 with 2 bps long swap
swap = (100,000 * 1.25) * (2 / 10000) * 1 = $25 per day

# Triple swap (Wednesday)
triple_swap = $25 * 3 = $75
```

**Funding Calculation:**
```python
notional = quantity * current_price
payment = notional * funding_rate

# Long position with positive rate = pay
# Short position with positive rate = receive
```

**Key Methods:**
- `apply_daily_swap()`: Apply overnight fees to all open positions
- `apply_funding_rate()`: Apply perpetual funding (8-hour intervals)
- `calculate_swap_fee()`: Compute swap for a position
- `estimate_daily_swap()`: Show cost before opening position
- `create_swap_rate()`: Admin function to set rates
- `create_funding_rate()`: Admin function to set funding

## Database Schema

```sql
-- Fee Schedules
CREATE TABLE fee_schedules (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(500),
    maker_fee_type VARCHAR(20) NOT NULL,  -- PERCENTAGE, FLAT, PER_LOT
    maker_fee_value FLOAT NOT NULL,
    taker_fee_type VARCHAR(20) NOT NULL,
    taker_fee_value FLOAT NOT NULL,
    min_fee FLOAT DEFAULT 0.0,
    max_fee FLOAT,
    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Volume Tiers
CREATE TABLE fee_volume_tiers (
    id SERIAL PRIMARY KEY,
    schedule_id INTEGER REFERENCES fee_schedules(id),
    min_volume FLOAT NOT NULL,  -- 30-day volume threshold
    maker_fee_type VARCHAR(20) NOT NULL,
    maker_fee_value FLOAT NOT NULL,
    taker_fee_type VARCHAR(20) NOT NULL,
    taker_fee_value FLOAT NOT NULL,
    tier_name VARCHAR(50)  -- Bronze, Silver, Gold, VIP
);

-- Instrument Overrides
CREATE TABLE instrument_fee_overrides (
    id SERIAL PRIMARY KEY,
    schedule_id INTEGER REFERENCES fee_schedules(id),
    instrument_id UUID REFERENCES instruments(instrument_id),
    maker_fee_type VARCHAR(20) NOT NULL,
    maker_fee_value FLOAT NOT NULL,
    taker_fee_type VARCHAR(20) NOT NULL,
    taker_fee_value FLOAT NOT NULL,
    min_fee FLOAT,
    max_fee FLOAT
);

-- Account-Schedule Links
CREATE TABLE account_fee_schedules (
    id SERIAL PRIMARY KEY,
    account_id INTEGER REFERENCES accounts(id),
    schedule_id INTEGER REFERENCES fee_schedules(id),
    rolling_volume_30d FLOAT DEFAULT 0.0,
    last_volume_update TIMESTAMP DEFAULT NOW(),
    assigned_at TIMESTAMP DEFAULT NOW()
);

-- Swap Rates
CREATE TABLE swap_rates (
    id SERIAL PRIMARY KEY,
    instrument_id UUID REFERENCES instruments(instrument_id),
    long_swap_rate FLOAT NOT NULL,   -- Basis points per day
    short_swap_rate FLOAT NOT NULL,
    triple_swap_day INTEGER DEFAULT 3,  -- 0=Monday, 3=Wednesday
    effective_date TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

-- Funding Rates
CREATE TABLE funding_rates (
    id SERIAL PRIMARY KEY,
    instrument_id UUID REFERENCES instruments(instrument_id),
    rate FLOAT NOT NULL,
    interval_hours INTEGER DEFAULT 8,
    timestamp TIMESTAMP NOT NULL,
    next_funding_time TIMESTAMP NOT NULL
);

-- Commissions
CREATE TABLE commissions (
    id SERIAL PRIMARY KEY,
    trade_id INTEGER REFERENCES trades(id),
    account_id INTEGER REFERENCES accounts(id),
    maker_fee FLOAT DEFAULT 0.0,
    taker_fee FLOAT DEFAULT 0.0,
    exchange_fee FLOAT DEFAULT 0.0,
    regulatory_fee FLOAT DEFAULT 0.0,
    total_commission FLOAT NOT NULL,
    fee_type VARCHAR(20),  -- MAKER, TAKER
    fee_rate FLOAT,
    notional_value FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Usage Examples

### Example 1: Fee Calculation with Volume Tiers

```python
from app.services.fee_service import get_fee_service

fee_service = get_fee_service()

# Calculate fee for $100k trade
fee, details = await fee_service.calculate_trade_fee(
    account_id=account.id,
    instrument_id=instrument_id,
    notional_value=100000.0,
    quantity=100.0,
    is_maker=True,  # Provided liquidity
    db=db
)

# Record commission
commission = await fee_service.record_commission(
    trade_id=trade.id,
    account_id=account.id,
    fee_amount=fee,
    fee_details=details,
    db=db
)

# Deduct from account
await fee_service.deduct_fee_from_account(account, fee, db)
```

### Example 2: Portfolio P&L Analysis

```python
from app.services.pnl_service import get_pnl_service

pnl_service = get_pnl_service()

# Get portfolio summary
portfolio = await pnl_service.calculate_portfolio_pnl(
    account_id=account.id,
    db=db
)
# Returns:
# {
#     "total_pnl": 5000.0,
#     "realized_pnl": 3000.0,
#     "unrealized_pnl": 2000.0,
#     "open_positions": 5,
#     "by_instrument": {...}
# }

# Calculate returns
returns = await pnl_service.calculate_portfolio_return(account, db)
# Returns:
# {
#     "total_return": 5000.0,
#     "total_return_pct": 50.0,  # 50% ROI
#     "realized_return": 3000.0,
#     "unrealized_return": 2000.0
# }

# Win rate statistics
stats = await pnl_service.calculate_win_rate(account.id, db)
# Returns:
# {
#     "win_rate": 65.0,  # 65% winning trades
#     "total_trades": 100,
#     "winning_trades": 65,
#     "losing_trades": 35,
#     "average_win": 150.0,
#     "average_loss": -80.0,
#     "profit_factor": 1.875  # avg_win / avg_loss
# }
```

### Example 3: Daily Swap Application

```python
from app.services.swap_service import get_swap_service

swap_service = get_swap_service()

# Run daily (typically at 00:00 UTC)
stats = await swap_service.apply_daily_swap(db)
# Returns:
# {
#     "positions_charged": 150,
#     "total_swap_fees": 2500.0,
#     "triple_swap_applied": True  # if Wednesday
# }

# Estimate swap before opening position
daily_cost = await swap_service.estimate_daily_swap(
    instrument_id=eurusd.instrument_id,
    quantity=100000.0,
    side="LONG",
    price=1.1000,
    db=db
)
print(f"Daily swap cost: ${daily_cost:.2f}")
```

### Example 4: P&L Statement Generation

```python
# Get comprehensive P&L statement
statement = await pnl_service.get_pnl_statement(
    account_id=account.id,
    start_date="2025-01-01",
    end_date="2025-12-31",
    db=db
)

# Returns:
# {
#     "period": {"start_date": "...", "end_date": "..."},
#     "pnl": {
#         "realized": 15000.0,
#         "unrealized": 2000.0,
#         "total": 17000.0
#     },
#     "fees": {
#         "total_fees": 500.0,
#         "maker_fees": 200.0,
#         "taker_fees": 300.0,
#         "trade_count": 250,
#         "average_fee_per_trade": 2.0
#     },
#     "statistics": {
#         "win_rate": 62.5,
#         "profit_factor": 2.1
#     }
# }
```

## Integration with Matching Engine

### Trade Execution Flow with Fees

```python
# In matching_service.py after trade execution

async def _execute_trade(self, buy_order, sell_order, price, quantity, db):
    # Create trade
    trade = Trade(...)
    db.add(trade)
    await db.flush()
    
    # Calculate fees
    fee_service = get_fee_service()
    
    # Buyer fee (determine if maker/taker)
    is_buyer_maker = buy_order.created_at < sell_order.created_at
    buyer_fee, buyer_details = await fee_service.calculate_trade_fee(
        account_id=buyer_account.id,
        instrument_id=instrument_id,
        notional_value=price * quantity,
        quantity=quantity,
        is_maker=is_buyer_maker,
        db=db
    )
    
    # Seller fee
    seller_fee, seller_details = await fee_service.calculate_trade_fee(
        account_id=seller_account.id,
        instrument_id=instrument_id,
        notional_value=price * quantity,
        quantity=quantity,
        is_maker=not is_buyer_maker,
        db=db
    )
    
    # Record commissions
    await fee_service.record_commission(
        trade.id, buyer_account.id, buyer_fee, buyer_details, db
    )
    await fee_service.record_commission(
        trade.id, seller_account.id, seller_fee, seller_details, db
    )
    
    # Deduct fees
    await fee_service.deduct_fee_from_account(buyer_account, buyer_fee, db)
    await fee_service.deduct_fee_from_account(seller_account, seller_fee, db)
    
    # Update or create positions
    margin_service = get_margin_service()
    await margin_service.open_position(...)  # Updates P&L
```

## Background Tasks

### Daily Swap Application

Add to `backend/app/main.py`:

```python
from app.services.swap_service import get_swap_service
import asyncio
from datetime import datetime

@app.on_event("startup")
async def startup_tasks():
    async def apply_daily_swaps():
        while True:
            now = datetime.utcnow()
            # Run at 00:00 UTC
            if now.hour == 0 and now.minute == 0:
                async with AsyncSessionLocal() as db:
                    swap_service = get_swap_service()
                    stats = await swap_service.apply_daily_swap(db)
                    await db.commit()
                    logger.info(f"Daily swap applied: {stats}")
                # Wait 60 seconds to avoid double execution
                await asyncio.sleep(60)
            else:
                # Check every minute
                await asyncio.sleep(60)
    
    asyncio.create_task(apply_daily_swaps())
```

### Volume Update Task

```python
async def update_rolling_volumes():
    while True:
        async with AsyncSessionLocal() as db:
            fee_service = get_fee_service()
            # Get all accounts
            accounts = await db.execute(select(Account))
            for account in accounts.scalars():
                await fee_service.update_rolling_volume(account.id, db)
            await db.commit()
        # Run every hour
        await asyncio.sleep(3600)

asyncio.create_task(update_rolling_volumes())
```

## Configuration

**Default Fee Rates:**
```python
# Standard schedule
MAKER_FEE = 0.001  # 0.1%
TAKER_FEE = 0.002  # 0.2%

# VIP tier (>$1M volume)
VIP_MAKER_FEE = 0.0005  # 0.05%
VIP_TAKER_FEE = 0.001   # 0.1%

# Crypto overrides
CRYPTO_MAKER_FEE = 0.005  # 0.5%
CRYPTO_TAKER_FEE = 0.008  # 0.8%
```

**Swap Rates (example):**
```python
# FX pairs (basis points per day)
EURUSD_LONG_SWAP = 2.0   # +2 bps
EURUSD_SHORT_SWAP = -1.0  # -1 bps

GBPUSD_LONG_SWAP = 3.0
GBPUSD_SHORT_SWAP = -1.5

# Funding rates (perpetual futures)
BTCUSD_FUNDING = 0.0001  # 0.01% every 8 hours
```

## Testing

Comprehensive test suite in `backend/tests/test_fees_and_pnl.py`:

**Test Cases:**
1. `test_percentage_fee_calculation`: Validates % -based fees
2. `test_volume_tier_discount`: Tests tier-based discounts
3. `test_instrument_fee_override`: Verifies per-instrument overrides
4. `test_pnl_calculation_long_position`: Long P&L calculation
5. `test_pnl_calculation_short_position`: Short P&L calculation
6. `test_swap_fee_calculation`: Overnight swap fees
7. `test_portfolio_pnl_aggregation`: Portfolio-level P&L
8. `test_win_rate_calculation`: Win/loss statistics

**Run tests:**
```bash
cd backend
pytest tests/test_fees_and_pnl.py -v
```

## Files Created

1. `backend/app/models/fee_schedule.py` - Fee schedule models (210 lines)
2. `backend/app/services/fee_service.py` - Fee calculation service (370 lines)
3. `backend/app/services/pnl_service.py` - P&L calculation service (420 lines)
4. `backend/app/services/swap_service.py` - Swap/funding service (330 lines)
5. `backend/tests/test_fees_and_pnl.py` - Test suite (460 lines)

## Files Modified

1. `backend/app/models/__init__.py` - Added fee model exports
2. `TODO_PHASE2.md` - Marked Fees & PnL section complete

---

## Summary

The Fees & PnL system provides:
- ✅ Configurable fee schedules (maker/taker, percentage/flat/per-lot)
- ✅ Volume-based discount tiers
- ✅ Per-instrument fee overrides
- ✅ Overnight swap fees for FX/CFDs
- ✅ Funding rates for perpetual futures
- ✅ Comprehensive P&L tracking (realized/unrealized)
- ✅ Portfolio aggregation and analytics
- ✅ VWAP calculations
- ✅ Win rate statistics
- ✅ Audit trail for all fees

**Total Lines**: ~1,790 lines of production code + tests + documentation

This implementation enables accurate fee collection, transparent cost disclosure, and detailed performance analytics for traders.
