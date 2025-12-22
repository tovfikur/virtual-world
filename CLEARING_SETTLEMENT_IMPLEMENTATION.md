# Clearing & Settlement System

## Overview

Complete trade clearing and settlement system with:

- **Trade Confirmation**: Bilateral confirmation after order match
- **Netting Pipeline**: Multi-trade consolidation for net settlement
- **T+N Settlement**: Configurable settlement dates (T+0, T+1, T+2, T+N)
- **Custody Management**: Asset and cash balance tracking
- **Reconciliation**: Periodic account validation
- **Exception Handling**: Failed settlement recovery
- **Broker Payout**: Payment distribution to broker partners

## Architecture

### Settlement Pipeline

```
Order Match
    ↓
Create Trade Confirmation (T+0)
    ↓
Bilateral Confirmation (T+0 to T+1)
    ↓
Netting Pipeline (T+1)
    ↓
Settlement Processing (T+N)
    ↓
Custody Updates
    ↓
Reconciliation
    ↓
Broker Payout
```

## Components

### 1. Settlement Models (`models/settlement.py`)

#### TradeConfirmation

Created immediately after order match. Tracks both parties' confirmation status.

```python
TradeConfirmation(
    trade_id=123,
    buyer_account_id=1,
    seller_account_id=2,
    instrument_id=uuid(...),
    quantity=100.0,
    price=150.0,
    gross_amount=15000.0,
    buyer_fee=45.0,
    seller_fee=45.0,
    net_amount=14910.0,
    settlement_type="DVP",  # Delivery vs Payment
    settlement_date=datetime(2024, 1, 17),  # T+2
    settlement_status="pending"
)
```

**Status Flow**:

```
PENDING → CONFIRMED → NETTED → SETTLED
                                   ↓
                              (or FAILED/REVERSED)
```

#### SettlementQueue

Queues trades for settlement processing.

```python
SettlementQueue(
    trade_confirmation_id=uuid(...),
    netting_batch_id=uuid(...),  # When part of batch
    status="pending",
    settlement_date=datetime(...),
    retry_count=0,
    queued_at=datetime(...)
)
```

#### CustodyBalance

Tracks settled and pending asset balances.

```python
CustodyBalance(
    account_id=1,
    instrument_id=uuid(...),
    custody_type="securities",
    balance=100.0,              # Settled quantity
    pending_debit=10.0,         # Awaiting outbound
    pending_credit=20.0,        # Awaiting inbound
    quantity_settled=100.0,
    quantity_pending=10.0,
    custodian="JPMorgan Chase",
    is_reconciled=True
)
```

#### SettlementRecord

Permanent settlement transaction record.

```python
SettlementRecord(
    settlement_id=uuid(...),
    trade_confirmation_id=uuid(...),
    buyer_account_id=1,
    seller_account_id=2,
    instrument_id=uuid(...),
    quantity=100.0,
    settlement_price=150.0,
    settlement_amount=15000.0,
    buyer_pays=15045.0,         # Including fees
    seller_receives=14955.0,    # After fees
    platform_fee_collected=90.0,
    settlement_type="DVP",
    status="settled",
    actual_settlement_date=datetime(...),
    buyer_custody_updated=True,
    seller_custody_updated=True,
    broker_paid=True
)
```

#### NetSettlementBatch

Groups multiple trades for efficient net settlement.

```python
NetSettlementBatch(
    batch_number="NET-20240115-ABC12345",
    batch_date=datetime(...),
    settlement_date=datetime(...),
    trade_count=5,
    gross_amount=75000.0,
    fees_collected=225.0,
    net_amount=74775.0,
    buy_quantity=250.0,
    sell_quantity=200.0,
    net_quantity=50.0,
    status="settled"
)
```

#### SettlementException

Failed settlement tracking for manual intervention.

```python
SettlementException(
    exception_id=uuid(...),
    settlement_record_id=1,
    exception_type="insufficient_funds",
    severity="high",
    description="Buyer insufficient balance",
    affected_account_id=1,
    is_resolved=False
)
```

### 2. Settlement Service (`services/settlement_service.py`)

#### create_trade_confirmation

Creates confirmation record after order match.

```python
confirmation = await service.create_trade_confirmation(
    trade=trade,
    settlement_days=2,  # T+2
    db=db
)
```

**Result**: TradeConfirmation with status PENDING

#### confirm_trade

One party confirms settlement.

```python
confirmation = await service.confirm_trade(
    confirmation_id=uuid(...),
    account_id=1,
    is_buyer=True,
    db=db
)
```

**Logic**:

- Validate account matches buyer or seller
- Mark as confirmed
- If both confirmed, status → CONFIRMED

#### net_trades

Groups trades for net settlement.

```python
batch = await service.net_trades(
    account_id=None,          # Optional: specific account
    instrument_id=None,       # Optional: specific instrument
    settlement_date=None,     # Optional: specific date
    db=db
)
```

**Netting Algorithm**:

- Find all CONFIRMED trades for settlement date
- Aggregate quantities and amounts
- Calculate net position
- Create NetSettlementBatch

#### settle_trade

Settle individual trade and update balances.

```python
settlement = await service.settle_trade(
    confirmation_id=uuid(...),
    db=db
)
```

**Operations**:

1. Validate both parties confirmed
2. Deduct buyer balance
3. Credit seller balance
4. Update custody balances
5. Create SettlementRecord
6. Mark as SETTLED

#### settle_batch

Settle all trades in batch.

```python
result = await service.settle_batch(
    batch_id=uuid(...),
    db=db
)

# Returns:
{
    "batch_id": uuid(...),
    "settled_count": 5,
    "failed_count": 0,
    "total_amount": 14910.0,
    "settlement_records": [...]
}
```

#### reconcile_custody

Validate custody balances.

```python
report = await service.reconcile_custody(
    account_id=None,
    custodian=None,
    db=db
)
```

**Checks**:

- Expected vs actual balances
- Trade count matching
- Custody account validation

#### process_broker_payout

Process payment to broker.

```python
success = await service.process_broker_payout(
    settlement_record_id=1,
    db=db
)
```

### 3. Settlement API (`api/settlement.py`)

#### GET `/api/v1/settlement/confirmations/{confirmation_id}`

Get trade confirmation details.

**Response**:

```json
{
  "id": "uuid",
  "trade_id": 123,
  "buyer_account_id": 1,
  "seller_account_id": 2,
  "instrument_id": "uuid",
  "quantity": 100.0,
  "price": 150.0,
  "gross_amount": 15000.0,
  "buyer_fee": 45.0,
  "seller_fee": 45.0,
  "net_amount": 14910.0,
  "settlement_type": "DVP",
  "settlement_date": "2024-01-17T00:00:00Z",
  "settlement_status": "confirmed",
  "buyer_confirmed": true,
  "seller_confirmed": true,
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### POST `/api/v1/settlement/confirmations/{confirmation_id}/confirm`

Confirm trade from one party.

**Request**:

```json
{
  "confirmation_id": "uuid",
  "is_buyer": true
}
```

**Response**:

```json
{
  "status": "success",
  "confirmation_id": "uuid",
  "settlement_status": "confirmed",
  "buyer_confirmed": true,
  "seller_confirmed": true
}
```

#### GET `/api/v1/settlement/summary`

Portfolio settlement summary.

**Response**:

```json
{
  "account_id": 1,
  "total_pending_settlements": 5,
  "pending_settlement_amount": 75000.0,
  "total_settled_today": 3,
  "total_settled_amount": 45000.0,
  "pending_custody_updates": 2,
  "failed_settlements": 0
}
```

#### GET `/api/v1/settlement/settlements`

Get settlement records.

**Query Parameters**:

- `status`: Filter by status (settled, failed)
- `limit`: Max results (default 50, max 500)
- `offset`: Pagination offset

**Response**:

```json
[
  {
    "id": 1,
    "settlement_id": "uuid",
    "trade_confirmation_id": "uuid",
    "buyer_account_id": 1,
    "seller_account_id": 2,
    "quantity": 100.0,
    "settlement_price": 150.0,
    "settlement_amount": 15000.0,
    "buyer_pays": 15045.0,
    "seller_receives": 14955.0,
    "platform_fee_collected": 90.0,
    "status": "settled",
    "actual_settlement_date": "2024-01-17T10:00:00Z"
  }
]
```

#### GET `/api/v1/settlement/custody`

Get custody balances.

**Query Parameters**:

- `include_zero`: Include zero balances (default false)

**Response**:

```json
[
  {
    "id": 1,
    "account_id": 1,
    "instrument_id": "uuid",
    "custody_type": "securities",
    "balance": 100.0,
    "pending_debit": 10.0,
    "pending_credit": 20.0,
    "quantity_settled": 100.0,
    "quantity_pending": 10.0,
    "custodian": "JPMorgan Chase",
    "is_reconciled": true,
    "last_reconciled_at": "2024-01-15T14:00:00Z"
  }
]
```

#### GET `/api/v1/settlement/custody/{instrument_id}`

Get specific custody balance.

#### POST `/api/v1/settlement/reconcile`

Request reconciliation.

**Response**:

```json
{
  "status": "success",
  "report_id": 1,
  "expected_balance": 100.0,
  "actual_balance": 100.0,
  "difference": 0.0,
  "is_balanced": true,
  "matched_trades": 50,
  "unmatched_trades": 0
}
```

#### GET `/api/v1/settlement/status/pending`

Get all pending settlements.

**Response**:

```json
{
  "count": 5,
  "settlements": [
    {
      "id": "uuid",
      "trade_id": 123,
      "status": "pending",
      "settlement_date": "2024-01-17T00:00:00Z",
      "amount": 14910.0,
      "buyer_confirmed": true,
      "seller_confirmed": false
    }
  ]
}
```

#### GET `/api/v1/settlement/statistics`

Settlement statistics.

**Query Parameters**:

- `days`: Period (default 30, max 365)

**Response**:

```json
{
  "period_days": 30,
  "total_settlements": 100,
  "total_amount": 1500000.0,
  "average_amount": 15000.0,
  "failed_count": 2,
  "success_rate": 98.0
}
```

## Usage Examples

### Trade Confirmation Flow

```python
from app.services.settlement_service import get_settlement_service

service = get_settlement_service()

# 1. Create confirmation after order match
confirmation = await service.create_trade_confirmation(
    trade=trade,
    settlement_days=2,
    db=db
)

print(f"Confirmation {confirmation.id} created")
print(f"Settlement date: {confirmation.settlement_date.date()}")

# 2. Buyer confirms
await service.confirm_trade(
    confirmation.id,
    buyer_account_id,
    is_buyer=True,
    db=db
)

# 3. Seller confirms
await service.confirm_trade(
    confirmation.id,
    seller_account_id,
    is_buyer=False,
    db=db
)

# 4. Settlement proceeds on T+2
```

### Netting Multiple Trades

```python
# Group trades for net settlement
batch = await service.net_trades(
    account_id=None,
    instrument_id=None,
    settlement_date=settlement_date,
    db=db
)

print(f"Batch {batch.batch_number}")
print(f"Trades: {batch.trade_count}")
print(f"Net quantity: {batch.net_quantity}")
print(f"Net amount: ${batch.net_amount:.2f}")

# Settle batch
result = await service.settle_batch(batch.id, db=db)
print(f"Settled: {result['settled_count']}, Failed: {result['failed_count']}")
```

### Custody Balance Tracking

```python
# Get custody balances
custodies = await db.execute(
    select(CustodyBalance).where(
        CustodyBalance.account_id == account_id
    )
)

for custody in custodies.scalars().all():
    print(f"{custody.instrument_id}")
    print(f"  Settled: {custody.balance}")
    print(f"  Pending: {custody.quantity_pending}")
    print(f"  Custodian: {custody.custodian}")

# Reconcile
report = await service.reconcile_custody(
    account_id=account_id,
    db=db
)

if report.is_balanced:
    print("✅ Custody balances reconciled")
else:
    print(f"⚠️ Discrepancy: ${report.difference:.2f}")
```

### Broker Payout Processing

```python
# Process payout to broker
settlement_record = await db.get(SettlementRecord, 1)

success = await service.process_broker_payout(
    settlement_record.id,
    db=db
)

if success:
    print(f"Payout processed: {settlement_record.broker_payment_reference}")
    print(f"Amount: ${settlement_record.seller_receives:.2f}")
```

## Settlement Types

### Cash Settlement

For FX and CFDs. Cash transferred on settlement date.

### Delivery vs Payment (DVP)

For equities and bonds. Securities delivered when payment received.

### Netting

Multiple trades combined for net settlement. Reduces settlement risk.

## T+N Settlement

Configurable settlement dates:

- **T+0**: Immediate settlement (rare, high risk)
- **T+1**: Next business day (crypto, some options)
- **T+2**: Two business days (default for equities)
- **T+3+**: Custom periods for specific instruments

**Calculation**:

```
Settlement Date = Trade Date + N Business Days (excluding weekends/holidays)
```

## Error Handling

### Insufficient Funds

When buyer balance too low for settlement:

1. Create SettlementException
2. Mark settlement FAILED
3. Notify parties
4. Allow retry or settlement reversal

### Custody Mismatch

When actual custody differs from internal records:

1. Create ReconciliationReport
2. Flag for manual review
3. Generate discrepancy report
4. Remediation workflow

## Database Schema

### settlement_confirmations

```sql
CREATE TABLE trade_confirmations (
    id UUID PRIMARY KEY,
    trade_id INTEGER UNIQUE,
    buyer_account_id INTEGER REFERENCES accounts(id),
    seller_account_id INTEGER REFERENCES accounts(id),
    instrument_id UUID REFERENCES instruments(id),
    quantity FLOAT,
    price FLOAT,
    gross_amount FLOAT,
    buyer_fee FLOAT,
    seller_fee FLOAT,
    net_amount FLOAT,
    settlement_type VARCHAR(50),
    settlement_date TIMESTAMP,
    settlement_status VARCHAR(50),
    buyer_confirmed BOOLEAN DEFAULT FALSE,
    seller_confirmed BOOLEAN DEFAULT FALSE,
    buyer_confirmed_at TIMESTAMP,
    seller_confirmed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    settled_at TIMESTAMP
);
```

### settlement_records

```sql
CREATE TABLE settlement_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    settlement_id UUID UNIQUE,
    trade_confirmation_id UUID UNIQUE,
    buyer_account_id INTEGER,
    seller_account_id INTEGER,
    quantity FLOAT,
    settlement_price FLOAT,
    buyer_pays FLOAT,
    seller_receives FLOAT,
    platform_fee_collected FLOAT,
    settlement_type VARCHAR(50),
    status VARCHAR(50),
    settlement_date TIMESTAMP,
    actual_settlement_date TIMESTAMP,
    buyer_custody_updated BOOLEAN,
    seller_custody_updated BOOLEAN,
    broker_paid BOOLEAN,
    broker_paid_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### custody_balances

```sql
CREATE TABLE custody_balances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER REFERENCES accounts(id),
    instrument_id UUID REFERENCES instruments(id),
    custody_type VARCHAR(50),
    balance FLOAT DEFAULT 0,
    pending_debit FLOAT DEFAULT 0,
    pending_credit FLOAT DEFAULT 0,
    quantity_settled FLOAT DEFAULT 0,
    quantity_pending FLOAT DEFAULT 0,
    custodian VARCHAR(255),
    is_reconciled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(account_id, instrument_id)
);
```

## Testing

Comprehensive test suite in `tests/test_settlement_service.py`:

```bash
pytest tests/test_settlement_service.py -v
```

Test coverage:

- ✅ Create trade confirmation
- ✅ Buyer confirmation
- ✅ Seller confirmation
- ✅ Both parties confirm (CONFIRMED status)
- ✅ Wrong party rejection
- ✅ Settlement amount calculations
- ✅ Net multiple trades
- ✅ Settle individual trade
- ✅ Custody balance updates
- ✅ Settlement failure handling
- ✅ Reconciliation
- ✅ Settlement date calculation (T+N)
- ✅ Settlement type determination
- ✅ Batch settlement
- ✅ Broker payout processing

## Performance Considerations

### Batch Processing

Settle in batches rather than individually:

```python
# Efficient: One batch transaction
batch = await service.net_trades(settlement_date=date, db=db)
result = await service.settle_batch(batch.id, db=db)

# Less efficient: Individual settlements
for confirmation in confirmations:
    await service.settle_trade(confirmation.id, db=db)
```

### Database Indexes

Critical indexes:

- `settlement_queue(status, settlement_date)`
- `trade_confirmations(settlement_status, settlement_date)`
- `custody_balances(account_id, instrument_id)`
- `settlement_records(actual_settlement_date)`

### Caching

Cache custody balances (TTL: 5-10 minutes)

## Future Enhancements

### Real-time Settlement

Straight-through processing (STP) for immediate settlement

### DVP Automation

Atomic securities + cash settlement

### FX Netting

Multi-currency netting across trading pairs

### Regulatory Reporting

EMIR, SFTR, MiFID II reporting

### Settlement Holds

Automatic settlement on hold for compliance checks

### Auto-reconciliation

Daily automated reconciliation with custodians

## Monitoring

Monitor key metrics:

- Settlement lag (time from T to actual settlement)
- Exception rate (failed settlements %)
- Netting efficiency (net vs gross volume ratio)
- Custody discrepancies
- Broker payout status

## Conclusion

Complete clearing and settlement system with:

- ✅ Bilateral trade confirmation
- ✅ Flexible T+N settlement
- ✅ Multi-trade netting
- ✅ Custody management
- ✅ Exception handling
- ✅ Reconciliation
- ✅ Broker integration
- ✅ Comprehensive testing

Ready for integration with matching engine and portfolio management.
