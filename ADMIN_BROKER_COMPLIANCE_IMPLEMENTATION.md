# Admin, Broker & Compliance Implementation

## Overview

This document describes the implementation of administrative controls, broker partner management, and market surveillance systems for the virtual exchange platform. These components provide:

- **Admin Controls**: Role-based access, instrument/market halting, circuit breakers
- **Risk Management**: Configurable margin, liquidation, exposure limits
- **Fee Configuration**: Dynamic fees with volume tiers and maker rebates
- **Broker Management**: A/B-book routing, sub-accounts, credit limits, commission sharing
- **Surveillance**: Anomaly detection for spoofing, wash trading, front-running
- **Audit Logging**: Comprehensive tracking of all administrative actions

## Architecture

### Role Hierarchy

The system implements a four-tier admin role hierarchy:

```
SUPER_ADMIN (4) - Complete system control, user creation
    ↓
ADMIN (3) - Market halts, fee changes, risk config
    ↓
OPERATOR (2) - Instrument halts, broker management, surveillance
    ↓
VIEWER (1) - Read-only access to controls and metrics
```

Each higher tier can perform all lower-tier operations.

### Models

#### AdminUser

- **Purpose**: Admin account with role-based access
- **Fields**:
  - `account_id`: Linked trading account
  - `role`: VIEWER/OPERATOR/ADMIN/SUPER_ADMIN
  - `is_active`: Enable/disable admin access
  - `last_login`: Track admin activity
- **Operations**: Create, list, update role, enable/disable

#### InstrumentControl

- **Purpose**: Per-instrument trading controls and limits
- **Fields**:
  - `instrument_id`: Target instrument
  - `is_trading_enabled`: Global trading flag
  - `is_halted`: Halt status
  - `halt_reason`: Reason for halt
  - `halted_until`: Automatic resume time
  - `max_order_size`: Maximum order size
  - `max_daily_volume`: Daily volume limit
  - `max_leverage`: Maximum allowed leverage
  - `circuit_breaker_enabled`: Auto-halt on volatility
  - `circuit_breaker_threshold`: Volatility threshold %
  - `circuit_breaker_duration_minutes`: Auto-halt duration
- **Operations**: Get, halt, resume, update limits

#### MarketControl

- **Purpose**: Global market state and controls
- **Fields**:
  - `market_open`: Market trading flag
  - `market_halted`: Global halt status
  - `halt_reason`: Reason for halt
  - `order_rate_limit`: Orders per minute
  - `circuit_breaker_enabled`: Market-wide circuit breaker
  - `circuit_breaker_threshold`: Market-wide volatility threshold
- **Operations**: Get status, halt market, resume market

#### RiskConfigurable

- **Purpose**: System-wide risk parameters
- **Fields**:
  - `maintenance_margin`: Min margin (default 15%)
  - `initial_margin`: Margin requirement (default 20%)
  - `liquidation_threshold`: Liquidation trigger (default 95%)
  - `max_position_size`: Position size limit per account
  - `max_account_leverage`: Account-wide leverage cap
  - `max_vega_exposure`: Options vega limit
  - `max_gamma_exposure`: Options gamma limit
  - `stress_test_scenarios`: Stress test parameters
  - `var_confidence`: VaR confidence level
  - `var_horizon_days`: VaR lookback period
- **Operations**: Get, update parameters with audit trail

#### FeeConfig

- **Purpose**: Dynamic fee configuration
- **Fields**:
  - `maker_fee`: Maker fee (default 0.02%)
  - `taker_fee`: Taker fee (default 0.05%)
  - `funding_fee`: Funding rate (default 0.015%)
  - `swap_fee`: Swap fee (default 0.02%)
  - `volume_tiers`: Tiered fee brackets
  - `maker_rebate`: Optional maker rebate
  - `is_active`: Fee configuration status
  - `effective_from`: Activation timestamp
- **Operations**: Get, update with effective date

#### BrokerAccount

- **Purpose**: Broker partner management
- **Fields**:
  - `broker_id`: Unique broker identifier
  - `name`: Broker name
  - `broker_type`: A_BOOK (passthrough) or B_BOOK (counterparty)
  - `api_key`: Broker API key for authentication
  - `api_secret`: API secret (hashed)
  - `credit_limit`: Total credit line
  - `credit_utilized`: Current credit usage
  - `commission_accrued`: Pending commission
  - `commission_paid`: Historical commission
  - `sub_accounts`: Linked trading accounts
- **Operations**: Create, list, update credit limit, sub-account management

#### SurveillanceAlert

- **Purpose**: Market abuse detection alerts
- **Fields**:
  - `anomaly_type`: SPOOFING/WASH_TRADE/FRONT_RUNNING/LAYERING/UNUSUAL_VOLUME
  - `severity`: critical/high/medium/low
  - `account_id`: Subject account
  - `instrument_id`: Subject instrument
  - `description`: Alert description
  - `evidence`: Detection metrics and thresholds
  - `trade_ids`: Related trades
  - `order_ids`: Related orders
  - `is_resolved`: Alert status
  - `resolution`: Admin action taken
  - `resolved_by`: Admin who resolved
- **Operations**: Create, resolve, query active alerts

#### AuditAction

- **Purpose**: Admin action logging
- **Fields**:
  - `admin_id`: Performing admin
  - `action_type`: Operation type
  - `resource_type`: Target resource
  - `resource_id`: Target identifier
  - `old_values`: Pre-change state
  - `new_values`: Post-change state
  - `approval_status`: PENDING/APPROVED/REJECTED
  - `approved_by`: Approving admin (if applicable)
  - `timestamp`: Action timestamp
- **Operations**: Create, approve, query audit trail

## Services

### AdminService

Manages administrative controls and configuration.

**Key Methods**:

```python
# Permission checks
await verify_admin_permission(required_role, user_role, db)

# Instrument controls
control = await get_instrument_control(instrument_id, db)
control = await halt_instrument(instrument_id, duration_min, reason, admin_id, db)
control = await resume_instrument(instrument_id, admin_id, db)
control = await update_instrument_limits(instrument_id, max_size, max_vol, max_lev, admin_id, db)

# Market controls
control = await get_market_control(db)
control = await halt_market(duration_min, reason, admin_id, db)
control = await resume_market(admin_id, db)
is_open = await check_market_open(db)

# Risk configuration
config = await get_risk_config(db)
config = await update_risk_config(maint_margin, init_margin, liq_thresh, max_pos, admin_id, db)

# Fee configuration
config = await get_fee_config(db)
config = await update_fee_config(maker, taker, funding, swap, admin_id, db)

# Audit logging
await _audit_action(admin_id, action, resource_type, resource_id, old_vals, new_vals, db)
```

### BrokerService

Manages broker partner accounts and trading arrangements.

**Key Methods**:

```python
# Broker account management
broker = await create_broker_account(name, broker_type, credit_limit, db)
broker = await get_broker_account(broker_id=None, api_key=None, db)
sub = await create_sub_account(broker_id, account_id, commission_share, db)

# Order routing
side = await route_order(broker_id, instrument_id, order_size, db)  # Returns A_BOOK or B_BOOK

# Exposure management
await hedge_broker_exposure(broker_id, instrument_id, hedge_qty, db)

# Commission management
await accrue_commission(broker_id, amount, db)
await payout_commission(broker_id, amount, db)

# Credit management
available = await check_credit_limit(broker_id, db)
await utilize_credit(broker_id, amount, db)
await release_credit(broker_id, amount, db)
```

### SurveillanceService

Detects market abuse patterns and generates alerts.

**Key Methods**:

```python
# Pattern detection (all return Optional[SurveillanceAlert])
alert = await detect_spoofing(account_id, instrument_id, time_window_min, db)
  # Detects: >80% order cancellation rate

alert = await detect_wash_trading(account_id, instrument_id, time_window_min, db)
  # Detects: Same account buy/sell of same security within 5 minutes

alert = await detect_front_running(account_id, time_window_sec, db)
  # Detects: Trades before large orders in same direction

alert = await detect_unusual_volume(instrument_id, std_devs=3.0, db)
  # Detects: Volume >3 std devs above average

# Alert management
alert = await resolve_alert(alert_id, resolution, resolved_by, db)
alerts = await get_active_alerts(account_id=None, severity=None, db)
```

## API Endpoints

### Instrument Controls

```
GET  /api/v1/admin/trading/instruments/{instrument_id}/control
POST /api/v1/admin/trading/instruments/{instrument_id}/halt
POST /api/v1/admin/trading/instruments/{instrument_id}/resume
PUT  /api/v1/admin/trading/instruments/{instrument_id}/limits
```

### Market Controls

```
GET  /api/v1/admin/trading/market/status
POST /api/v1/admin/trading/market/halt
POST /api/v1/admin/trading/market/resume
```

### Risk Configuration

```
GET /api/v1/admin/trading/risk/config
PUT /api/v1/admin/trading/risk/config
```

### Fee Configuration

```
GET /api/v1/admin/trading/fees/config
PUT /api/v1/admin/trading/fees/config
```

### Broker Management

```
POST /api/v1/admin/brokers
GET  /api/v1/admin/brokers/{broker_id}
POST /api/v1/admin/brokers/{broker_id}/sub-accounts
```

### Surveillance Alerts

```
POST /api/v1/admin/trading/surveillance/check-spoofing
POST /api/v1/admin/trading/surveillance/check-wash-trading
POST /api/v1/admin/trading/surveillance/check-front-running
GET  /api/v1/admin/trading/surveillance/alerts
POST /api/v1/admin/trading/surveillance/alerts/{alert_id}/resolve
```

## Usage Examples

### Halting an Instrument

```python
# API Request
POST /api/v1/admin/trading/instruments/btc-usd/halt?duration_minutes=30&reason=Circuit breaker triggered

# Response
{
    "status": "halted",
    "instrument_id": "btc-usd",
    "halted_until": "2024-01-15T14:30:00Z",
    "reason": "Circuit breaker triggered"
}
```

### Creating a Broker Account

```python
# API Request
POST /api/v1/admin/brokers?name=Prime Broker&broker_type=A_BOOK&credit_limit=1000000

# Response
{
    "broker_id": "PB-001",
    "name": "Prime Broker",
    "broker_type": "A_BOOK",
    "api_key": "pb_live_...",
    "credit_limit": 1000000,
    "created_at": "2024-01-15T10:00:00Z"
}
```

### Detecting Spoofing

```python
# API Request
POST /api/v1/admin/trading/surveillance/check-spoofing?account_id=123&instrument_id=btc-usd

# Response
{
    "alert_found": true,
    "alert_id": 456,
    "severity": "high",
    "description": "Spoofing detected: 85% orders cancelled without fill"
}
```

### Updating Risk Configuration

```python
# API Request
PUT /api/v1/admin/trading/risk/config?maintenance_margin=0.15&initial_margin=0.20&liquidation_threshold=0.95

# Response
{
    "status": "updated",
    "maintenance_margin": 0.15,
    "initial_margin": 0.20,
    "liquidation_threshold": 0.95,
    "max_position_size": 100000
}
```

## Security Considerations

1. **Role-Based Access Control**: All operations require appropriate admin role
2. **Audit Logging**: Every administrative action is logged with admin ID and timestamp
3. **API Key Management**: Broker API keys are hashed before storage
4. **Credit Limits**: Enforced at order time to prevent broker overdraft
5. **Circuit Breakers**: Automatic market/instrument halts on extreme volatility
6. **Anomaly Detection**: Real-time pattern matching for market abuse

## Testing

Comprehensive test suite in `test_admin_trading.py`:

- **AdminService Tests** (10 tests):

  - Instrument control CRUD
  - Halt/resume functionality
  - Limit updates
  - Market controls
  - Risk configuration
  - Fee configuration

- **BrokerService Tests** (8 tests):

  - Broker account creation
  - Sub-account management
  - Credit limit enforcement
  - Commission accrual/payout

- **SurveillanceService Tests** (4 tests):

  - Spoofing detection
  - Alert management
  - Active alert retrieval

- **Permission Tests** (2 tests):
  - Role hierarchy
  - Permission verification

## Deployment Checklist

- [ ] Database migrations applied (admin tables created)
- [ ] Admin models imported in `models/__init__.py`
- [ ] Admin service registered in DI container
- [ ] Broker service registered in DI container
- [ ] Surveillance service registered in DI container
- [ ] API endpoints mounted in main router
- [ ] Admin users created with appropriate roles
- [ ] Initial market controls configured
- [ ] Default fees and risk parameters set
- [ ] API documentation updated
- [ ] Monitoring alerts configured for anomalies
- [ ] Audit log queries optimized with indexes

## Future Enhancements

1. **Approval Workflows**: Multi-approval for critical changes
2. **Scheduled Controls**: Time-based market halts (e.g., pre-earnings)
3. **Position Limits**: Per-account and per-broker position tracking
4. **Stress Testing**: Real-time portfolio stress scenarios
5. **Regulatory Reports**: Automated compliance reporting
6. **Machine Learning**: Pattern-based anomaly detection
7. **Webhook Alerts**: Push notifications to monitoring systems
8. **API Rate Limiting**: Per-broker rate limit enforcement
