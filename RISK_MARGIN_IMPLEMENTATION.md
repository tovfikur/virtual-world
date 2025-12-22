# Risk, Margin & Exposure Implementation

## Overview

Complete implementation of risk management, margin tracking, liquidation handling, and circuit breakers for the VirtualWorld Exchange. This system ensures safe trading operations by monitoring margin levels, preventing over-leveraged positions, and halting trading during extreme volatility.

## Components

### 1. Account & Margin Models (`backend/app/models/account.py`)

**Account Model**
- Tracks user's trading account balance and margin metrics
- Fields:
  - `balance`: Cash balance in account currency
  - `equity`: Balance + unrealized P&L
  - `used_margin`: Margin locked by open positions
  - `free_margin`: Equity - used margin (available for new positions)
  - `margin_level`: (Equity / Used Margin) * 100
  - `leverage_max`: Maximum leverage allowed for this account
  - `margin_call_level`: Margin level threshold for margin call (default 100%)
  - `liquidation_level`: Margin level threshold for forced liquidation (default 50%)
  - `status`: ACTIVE, MARGIN_CALL, LIQUIDATING, SUSPENDED

**Position Model**
- Tracks individual open positions
- Fields:
  - `side`: LONG or SHORT
  - `quantity`: Position size
  - `entry_price`: Opening price
  - `current_price`: Latest market price
  - `unrealized_pnl`: Mark-to-market P&L
  - `realized_pnl`: Locked-in P&L on close
  - `margin_used`: Margin allocated for this position
  - `leverage_used`: Leverage factor applied
  - `swap_accumulated`: Overnight swap fees
  - `closed_at`: Timestamp when position closed (NULL for open positions)

**MarginCall Model**
- Records margin call and liquidation events
- Fields:
  - `margin_level`: Margin level at time of event
  - `equity`: Account equity at time of event
  - `used_margin`: Used margin at time of event
  - `action`: "MARGIN_CALL" or "LIQUIDATION"
  - `resolved`: Whether issue has been resolved

**CircuitBreaker Model**
- Records volatility halts
- Fields:
  - `breaker_type`: "INSTRUMENT" or "MARKET_WIDE"
  - `trigger_reason`: Human-readable explanation
  - `reference_price`: Price before spike
  - `trigger_price`: Price that triggered halt
  - `percent_change`: Percentage move
  - `is_active`: Whether halt is currently in effect
  - `duration_seconds`: How long halt lasts

### 2. Margin Calculation Service (`backend/app/services/margin_service.py`)

**Margin Calculation**
```python
margin_required = (quantity * price) / leverage
```

For a 100,000 EUR position at 1.1000 with 50x leverage:
```
margin = (100,000 * 1.1000) / 50 = 2,200 USD
```

**Equity Calculation**
```python
equity = balance + sum(unrealized_pnl for all positions)
```

**Free Margin**
```python
free_margin = equity - used_margin
```

**Margin Level**
```python
margin_level = (equity / used_margin) * 100
```

**Key Methods:**
- `calculate_account_equity()`: Recalculates equity, used margin, free margin for account
- `calculate_position_margin()`: Computes margin required for new position
- `check_margin_sufficiency()`: Validates if account has enough free margin
- `open_position()`: Opens new position and updates account margin
- `close_position()`: Closes position, realizes P&L, releases margin
- `get_exposure_per_instrument()`: Calculates total notional exposure for instrument

### 3. Liquidation Service (`backend/app/services/liquidation_service.py`)

**Margin Thresholds:**
- **Margin Call (100% default)**: Warning notification, no forced action
- **Liquidation (50% default)**: Automatic position closure

**Liquidation Process:**
1. Set account status to `LIQUIDATING`
2. Cancel all pending orders
3. Get all open positions, sort by P&L (worst first)
4. Force close positions one by one via market orders
5. Continue until margin level recovers or all positions closed
6. Create `MarginCall` record with action="LIQUIDATION"

**Key Methods:**
- `check_margin_levels()`: Monitors margin level, triggers margin call or liquidation
- `monitor_all_accounts()`: Periodic check of all accounts (called by background task)

**Monitoring:**
```python
# Call periodically (e.g., every minute)
stats = await liquidation_service.monitor_all_accounts(db)
# Returns: {"checked": 150, "margin_calls": 2, "liquidations": 1}
```

### 4. Pre-Trade Risk Validation (`backend/app/services/risk_service.py`)

**Risk Checks:**

1. **Leverage Limits**
   - Validate against instrument max leverage
   - Validate against account max leverage
   
2. **Margin Sufficiency**
   - Calculate margin required for new position
   - Verify account has sufficient free margin

3. **Position Size Limits**
   - Max 20% of account equity per position
   - Prevents over-concentration

4. **Exposure Limits**
   - Max 50% of account equity per instrument
   - Sums notional value of all positions for same instrument

**Integration:**
```python
# Before placing order
await risk_service.validate_order_with_account(
    account=account,
    instrument=instrument,
    payload=order_payload,
    db=db
)
# Raises ValueError if any check fails
```

### 5. Circuit Breaker Service (`backend/app/services/circuit_breaker_service.py`)

**Instrument-Level Thresholds:**
| Level | Percent Move | Time Window | Halt Duration |
|-------|-------------|-------------|---------------|
| 1     | 5%          | 1 minute    | 5 minutes     |
| 2     | 10%         | 5 minutes   | 15 minutes    |
| 3     | 20%         | 15 minutes  | 30 minutes    |

**Market-Wide Thresholds:**
| Level | Avg Move | Time Window | Halt Duration |
|-------|----------|-------------|---------------|
| 1     | 7%       | 5 minutes   | 15 minutes    |
| 2     | 13%      | 10 minutes  | 30 minutes    |
| 3     | 20%      | 15 minutes  | 60 minutes    |

**Detection:**
- Uses `PriceHistory` 1-minute candles as reference
- Compares current price to price N minutes ago
- Calculates percent change
- Triggers halt if threshold exceeded

**Integration:**
```python
# Check before executing trade
is_halted = await circuit_breaker_service.is_trading_halted(
    instrument_id, db
)
if is_halted:
    raise ValueError("Trading halted due to circuit breaker")
```

**Automatic Expiry:**
- Circuit breakers automatically deactivate after duration expires
- Checked on each query via `elapsed time > duration_seconds`

## Database Schema

```sql
-- Accounts
CREATE TABLE accounts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    balance FLOAT NOT NULL DEFAULT 0.0,
    equity FLOAT NOT NULL DEFAULT 0.0,
    used_margin FLOAT NOT NULL DEFAULT 0.0,
    free_margin FLOAT NOT NULL DEFAULT 0.0,
    margin_level FLOAT,
    leverage_max FLOAT NOT NULL DEFAULT 50.0,
    margin_call_level FLOAT NOT NULL DEFAULT 100.0,
    liquidation_level FLOAT NOT NULL DEFAULT 50.0,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Positions
CREATE TABLE positions (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    instrument_id UUID NOT NULL REFERENCES instruments(instrument_id),
    side VARCHAR(10) NOT NULL, -- LONG, SHORT
    quantity FLOAT NOT NULL,
    entry_price FLOAT NOT NULL,
    current_price FLOAT,
    unrealized_pnl FLOAT DEFAULT 0.0,
    realized_pnl FLOAT DEFAULT 0.0,
    margin_used FLOAT NOT NULL,
    leverage_used FLOAT NOT NULL,
    swap_accumulated FLOAT DEFAULT 0.0,
    opened_at TIMESTAMP DEFAULT NOW(),
    closed_at TIMESTAMP
);

-- Margin Calls
CREATE TABLE margin_calls (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    margin_level FLOAT NOT NULL,
    equity FLOAT NOT NULL,
    used_margin FLOAT NOT NULL,
    action VARCHAR(20) NOT NULL, -- MARGIN_CALL, LIQUIDATION
    resolved BOOLEAN DEFAULT FALSE,
    triggered_at TIMESTAMP DEFAULT NOW()
);

-- Circuit Breakers
CREATE TABLE circuit_breakers (
    id SERIAL PRIMARY KEY,
    instrument_id UUID REFERENCES instruments(instrument_id),
    breaker_type VARCHAR(20) NOT NULL, -- INSTRUMENT, MARKET_WIDE
    trigger_reason TEXT NOT NULL,
    reference_price FLOAT,
    trigger_price FLOAT,
    percent_change FLOAT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    duration_seconds INTEGER NOT NULL,
    triggered_at TIMESTAMP DEFAULT NOW()
);
```

## Usage Examples

### Example 1: Opening a Position

```python
from app.services.margin_service import get_margin_service

margin_service = get_margin_service()

# Open 100,000 EUR/USD with 50x leverage
position = await margin_service.open_position(
    account=account,
    instrument_id=eurusd_instrument.instrument_id,
    side="LONG",
    quantity=100000.0,
    entry_price=1.1000,
    leverage=50.0,
    db=db
)

# Margin used: (100,000 * 1.10) / 50 = 2,200 USD
# Account free margin reduced by 2,200
```

### Example 2: Monitoring Margin Levels

```python
from app.services.liquidation_service import get_liquidation_service

liquidation_service = get_liquidation_service()

# Check single account
action = await liquidation_service.check_margin_levels(account, db)
if action == "MARGIN_CALL":
    # Send notification to user
    pass
elif action == "LIQUIDATION":
    # Positions are being force-closed
    pass

# Or monitor all accounts (background task)
stats = await liquidation_service.monitor_all_accounts(db)
logger.info(f"Checked {stats['checked']} accounts, "
            f"{stats['liquidations']} liquidations")
```

### Example 3: Pre-Trade Risk Check

```python
from app.services.risk_service import risk_service

# Validate order before placement
try:
    await risk_service.validate_order_with_account(
        account=account,
        instrument=instrument,
        payload=order_create_payload,
        db=db
    )
    # Order is safe to place
    await place_order(order_create_payload, db)
except ValueError as e:
    # Risk check failed
    return {"error": str(e)}, 400
```

### Example 4: Circuit Breaker Check

```python
from app.services.circuit_breaker_service import get_circuit_breaker_service

circuit_breaker_service = get_circuit_breaker_service()

# Before executing trade
is_halted = await circuit_breaker_service.is_trading_halted(
    instrument_id, db
)
if is_halted:
    raise ValueError("Trading halted for this instrument")

# Monitor instrument volatility (called after price updates)
breaker = await circuit_breaker_service.check_instrument_volatility(
    instrument_id=instrument.instrument_id,
    current_price=new_price,
    db=db
)
if breaker:
    # Trading halted, broadcast notification
    await websocket_service.broadcast({
        "type": "circuit_breaker",
        "instrument_id": str(instrument_id),
        "reason": breaker.trigger_reason,
        "duration": breaker.duration_seconds
    })
```

## Testing

Comprehensive test suite in `backend/tests/test_margin_and_risk.py`:

**Test Cases:**
1. `test_margin_calculation`: Validates margin computation for leveraged positions
2. `test_account_equity_calculation`: Tests equity and P&L calculations
3. `test_margin_call_detection`: Verifies margin call triggers at threshold
4. `test_position_liquidation`: Tests automatic liquidation flow
5. `test_pre_trade_risk_validation`: Validates all risk checks
6. `test_circuit_breaker_instrument_level`: Tests volatility halt triggers
7. `test_exposure_limits`: Validates per-instrument exposure caps

**Run tests:**
```bash
cd backend
pytest tests/test_margin_and_risk.py -v
```

## Integration Points

### Order Placement Flow
1. User submits order
2. **Risk validation** (`risk_service.validate_order_with_account()`)
3. **Circuit breaker check** (`circuit_breaker_service.is_trading_halted()`)
4. If validations pass, place order in matching engine
5. On fill, **open/update position** (`margin_service.open_position()`)
6. **Update account equity** (`margin_service.calculate_account_equity()`)

### Background Tasks
Add to `backend/app/main.py`:

```python
from app.services.liquidation_service import get_liquidation_service
from app.services.circuit_breaker_service import get_circuit_breaker_service

@app.on_event("startup")
async def startup_tasks():
    # Margin monitoring (every minute)
    async def monitor_margins():
        while True:
            async with AsyncSessionLocal() as db:
                liquidation_service = get_liquidation_service()
                await liquidation_service.monitor_all_accounts(db)
            await asyncio.sleep(60)
    
    # Circuit breaker monitoring (every 30 seconds)
    async def monitor_circuit_breakers():
        while True:
            async with AsyncSessionLocal() as db:
                circuit_breaker_service = get_circuit_breaker_service()
                # Check market-wide volatility
                await circuit_breaker_service.check_market_wide_volatility(db)
            await asyncio.sleep(30)
    
    asyncio.create_task(monitor_margins())
    asyncio.create_task(monitor_circuit_breakers())
```

### WebSocket Price Updates
When price updates via WebSocket:

```python
# After updating pricing engine
breaker = await circuit_breaker_service.check_instrument_volatility(
    instrument_id=instrument_id,
    current_price=new_price,
    db=db
)

if breaker:
    # Broadcast halt notification to all clients
    await market_data_manager.broadcast({
        "type": "circuit_breaker",
        "instrument_id": str(instrument_id),
        "trigger_reason": breaker.trigger_reason
    })
```

## Configuration

**Risk Parameters** (in `risk_service.py`):
```python
max_order_notional = 100_000_000  # $100M per order
max_position_size_pct = 0.20      # 20% of equity per position
max_instrument_exposure_pct = 0.50  # 50% of equity per instrument
```

**Margin Defaults** (in `Account` model):
```python
margin_call_level = 100.0   # Margin call at 100%
liquidation_level = 50.0    # Liquidate at 50%
leverage_max = 50.0         # Default max leverage
```

**Circuit Breaker Thresholds** (in `circuit_breaker_service.py`):
Modify `instrument_thresholds` and `market_wide_thresholds` arrays.

## Security Considerations

1. **Margin Monitoring**: Run as background task, not user-triggered
2. **Liquidation**: Execute as system orders, bypass normal order validation
3. **Circuit Breakers**: Store in database for audit trail
4. **Pre-Trade Checks**: Always validate before order placement
5. **Exposure Limits**: Aggregate by account and instrument to prevent concentration risk

## Performance

- **Margin Calculation**: O(n) where n = number of open positions
- **Liquidation Check**: O(1) per account (cached margin level)
- **Circuit Breaker**: O(1) per instrument (query recent candles)
- **Pre-Trade Validation**: O(1) (few database queries)

**Optimization Tips:**
- Cache margin levels in Redis for high-frequency updates
- Use database indexes on `account_id`, `instrument_id`, `is_active`
- Batch margin monitoring for multiple accounts
- Use WebSocket for real-time margin level updates to UI

## Future Enhancements

1. **Dynamic Leverage**: Adjust leverage based on volatility
2. **Partial Liquidation**: Close only portion of position to restore margin
3. **Margin Call Notifications**: Email, SMS, push notifications
4. **Risk Scoring**: Assign risk scores to accounts based on trading patterns
5. **Portfolio VaR**: Value at Risk calculations for entire portfolio
6. **Stress Testing**: Simulate market crashes and margin requirements
7. **Collateral Management**: Support multiple collateral types (stocks, bonds, crypto)

## Files Created

1. `backend/app/models/account.py` - Account, Position, MarginCall, CircuitBreaker models
2. `backend/app/services/margin_service.py` - Margin calculations and position management
3. `backend/app/services/liquidation_service.py` - Margin call detection and liquidation
4. `backend/app/services/circuit_breaker_service.py` - Volatility halt management
5. `backend/app/services/risk_service.py` - Extended with pre-trade risk checks
6. `backend/tests/test_margin_and_risk.py` - Comprehensive test suite

## Files Modified

1. `backend/app/models/__init__.py` - Added Account, Position, MarginCall, CircuitBreaker exports
2. `TODO_PHASE2.md` - Marked Risk, Margin & Exposure section complete

---

## Summary

The Risk, Margin & Exposure system provides:
- ✅ Real-time margin tracking with used/free margin and equity calculations
- ✅ Automatic margin call detection and forced liquidation
- ✅ Pre-trade risk validation (leverage, margin, position size, exposure)
- ✅ Circuit breakers for instrument and market-wide volatility halts
- ✅ Comprehensive testing and documentation
- ✅ Integration hooks for background monitoring and WebSocket notifications

This implementation ensures safe trading operations and protects both users and the exchange from excessive risk exposure.
