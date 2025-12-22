# Admin System Quick Start Guide

## Overview

This guide shows how to use the admin, broker, and surveillance systems to manage your exchange platform.

## Prerequisites

- Admin role in the system (VIEWER, OPERATOR, ADMIN, or SUPER_ADMIN)
- Valid API token from authentication endpoint
- Postman, curl, or similar HTTP client

## Authentication

All admin endpoints require authentication. First, get a token:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d {
    "email": "admin@example.com",
    "password": "secure_password"
  }
```

Response:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

Use this token in all subsequent requests:

```bash
Authorization: Bearer <your_token>
```

## Common Tasks

### 1. Check Market Status

```bash
curl http://localhost:8000/api/v1/admin/trading/market/status \
  -H "Authorization: Bearer $TOKEN"
```

Response:

```json
{
  "market_open": true,
  "market_halted": false,
  "halt_reason": null,
  "order_rate_limit": 1000,
  "circuit_breaker_enabled": true,
  "updated_at": "2024-01-15T10:00:00Z"
}
```

### 2. Halt Market (Emergency)

```bash
curl -X POST "http://localhost:8000/api/v1/admin/trading/market/halt?duration_minutes=30&reason=Emergency%20market%20halt%20due%20to%20extreme%20volatility" \
  -H "Authorization: Bearer $TOKEN"
```

Response:

```json
{
  "status": "halted",
  "market_halted": true,
  "reason": "Emergency market halt due to extreme volatility"
}
```

### 3. Resume Market

```bash
curl -X POST http://localhost:8000/api/v1/admin/trading/market/resume \
  -H "Authorization: Bearer $TOKEN"
```

### 4. Halt a Specific Instrument

```bash
curl -X POST "http://localhost:8000/api/v1/admin/trading/instruments/btc-usd/halt?duration_minutes=60&reason=Circuit%20breaker%20triggered" \
  -H "Authorization: Bearer $TOKEN"
```

### 5. Update Instrument Limits

```bash
curl -X PUT "http://localhost:8000/api/v1/admin/trading/instruments/eth-usd/limits?max_order_size=500&max_daily_volume=10000&max_leverage=20" \
  -H "Authorization: Bearer $TOKEN"
```

Response:

```json
{
  "instrument_id": "eth-usd",
  "max_order_size": 500,
  "max_daily_volume": 10000,
  "max_leverage": 20
}
```

### 6. Get Risk Configuration

```bash
curl http://localhost:8000/api/v1/admin/trading/risk/config \
  -H "Authorization: Bearer $TOKEN"
```

Response:

```json
{
  "maintenance_margin": 0.15,
  "initial_margin": 0.2,
  "liquidation_threshold": 0.95,
  "max_position_size": 100000,
  "max_account_leverage": 50
}
```

### 7. Update Risk Configuration

```bash
curl -X PUT "http://localhost:8000/api/v1/admin/trading/risk/config?maintenance_margin=0.12&initial_margin=0.18&liquidation_threshold=0.90" \
  -H "Authorization: Bearer $TOKEN"
```

### 8. Get Fee Configuration

```bash
curl http://localhost:8000/api/v1/admin/trading/fees/config \
  -H "Authorization: Bearer $TOKEN"
```

Response:

```json
{
  "maker_fee": 0.0001,
  "taker_fee": 0.0005,
  "funding_fee": 0.00015,
  "swap_fee": 0.0002,
  "effective_from": "2024-01-15T00:00:00Z"
}
```

### 9. Update Fees

```bash
curl -X PUT "http://localhost:8000/api/v1/admin/trading/fees/config?maker_fee=0.00008&taker_fee=0.0004" \
  -H "Authorization: Bearer $TOKEN"
```

### 10. Create Broker Account

```bash
curl -X POST "http://localhost:8000/api/v1/admin/brokers?name=Prime%20Broker%20LLC&broker_type=A_BOOK&credit_limit=5000000" \
  -H "Authorization: Bearer $TOKEN"
```

Response:

```json
{
  "broker_id": "PB-001",
  "name": "Prime Broker LLC",
  "broker_type": "A_BOOK",
  "api_key": "pb_live_abc123...",
  "credit_limit": 5000000,
  "created_at": "2024-01-15T10:15:00Z"
}
```

**Important**: Save the `api_key` - it won't be shown again!

### 11. Get Broker Details

```bash
curl http://localhost:8000/api/v1/admin/brokers/PB-001 \
  -H "Authorization: Bearer $TOKEN"
```

Response:

```json
{
  "broker_id": "PB-001",
  "name": "Prime Broker LLC",
  "broker_type": "A_BOOK",
  "credit_limit": 5000000,
  "credit_utilized": 1250000,
  "commission_accrued": 75000,
  "commission_paid": 300000
}
```

### 12. Check Surveillance Alerts

```bash
curl "http://localhost:8000/api/v1/admin/trading/surveillance/alerts?severity=critical" \
  -H "Authorization: Bearer $TOKEN"
```

Response:

```json
{
  "count": 2,
  "alerts": [
    {
      "alert_id": 1,
      "anomaly_type": "wash_trade",
      "severity": "critical",
      "account_id": 42,
      "instrument_id": "btc-usd",
      "description": "Wash trading detected: Account bought and sold 3 time(s)",
      "detected_at": "2024-01-15T10:45:00Z"
    },
    {
      "alert_id": 2,
      "anomaly_type": "spoofing",
      "severity": "high",
      "account_id": 89,
      "instrument_id": "eth-usd",
      "description": "Spoofing detected: 85% orders cancelled without fill",
      "detected_at": "2024-01-15T10:50:00Z"
    }
  ]
}
```

### 13. Check for Spoofing (Manual)

```bash
curl -X POST "http://localhost:8000/api/v1/admin/trading/surveillance/check-spoofing?account_id=42&instrument_id=btc-usd" \
  -H "Authorization: Bearer $TOKEN"
```

### 14. Resolve an Alert

```bash
curl -X POST "http://localhost:8000/api/v1/admin/trading/surveillance/alerts/1/resolve?resolution=Account%20suspended%20for%20suspicious%20trading%20activity" \
  -H "Authorization: Bearer $TOKEN"
```

## Role Permissions

### VIEWER (Read-only)

- View market status
- View instrument controls
- View risk/fee configuration
- View surveillance alerts
- View broker details

### OPERATOR (Execute operations)

- All VIEWER permissions
- Halt/resume individual instruments
- Create/update broker accounts
- Create broker sub-accounts
- Resolve surveillance alerts

### ADMIN (System configuration)

- All OPERATOR permissions
- Halt/resume entire market
- Update risk configuration
- Update fee configuration
- Create admin users

### SUPER_ADMIN (Full control)

- All ADMIN permissions
- Create other SUPER_ADMIN users
- Modify role hierarchy
- System-level configuration

## Testing with Python

```python
import requests
import json

BASE_URL = "http://localhost:8000/api/v1/admin"
TOKEN = "your_token_here"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# Get market status
response = requests.get(f"{BASE_URL}/trading/market/status", headers=headers)
market = response.json()
print(f"Market open: {market['market_open']}")

# Get surveillance alerts
response = requests.get(f"{BASE_URL}/trading/surveillance/alerts", headers=headers)
alerts = response.json()
print(f"Active alerts: {alerts['count']}")

# Create broker
broker_data = {
    "name": "Test Broker",
    "broker_type": "B_BOOK",
    "credit_limit": 2000000
}
response = requests.post(f"{BASE_URL}/brokers", headers=headers, json=broker_data)
broker = response.json()
print(f"Created broker: {broker['broker_id']}")
```

## Monitoring

### Key Metrics to Monitor

1. **Market Metrics**:

   - Market open/halted status
   - Order rate limit utilization
   - Circuit breaker triggers

2. **Instrument Metrics**:

   - Per-instrument halt status
   - Order size violations
   - Daily volume compliance

3. **Risk Metrics**:

   - Margin utilization by account
   - Liquidation events
   - Leverage distribution

4. **Broker Metrics**:

   - Credit utilization
   - Commission accrual
   - Sub-account performance

5. **Surveillance Metrics**:
   - Alert frequency by type
   - Resolution times
   - False positive rate

## Troubleshooting

### "Admin access required" error

- Your user doesn't have admin role
- Contact your system administrator

### "Instrument control not found" error

- The instrument doesn't have control settings yet
- The instrument may not exist
- Check instrument ID format

### "Credit limit exceeded" error

- Broker has exceeded credit line
- Reduce broker credit utilization or increase limit

### Rate limiting

- You've exceeded API rate limits
- Wait and retry
- Check `X-RateLimit-*` headers in response

## Best Practices

1. **Emergency Procedures**:

   - Have market halt procedures documented
   - Test halt/resume in staging environment
   - Keep emergency contact info updated

2. **Configuration Changes**:

   - Always make changes during low-volume periods
   - Monitor system closely after changes
   - Keep audit logs for compliance

3. **Broker Management**:

   - Regularly review credit utilization
   - Monitor commission accrual
   - Set conservative limits initially

4. **Surveillance**:

   - Review alerts at least daily
   - Investigate high-severity alerts immediately
   - Document resolution actions

5. **Access Control**:
   - Minimize number of SUPER_ADMIN users
   - Rotate admin credentials regularly
   - Log all admin activities
   - Require MFA for sensitive operations

## Support

For issues or questions:

1. Check the documentation: `ADMIN_BROKER_COMPLIANCE_IMPLEMENTATION.md`
2. Review test cases: `backend/tests/test_admin_trading.py`
3. Check API logs for detailed errors
4. Contact your system administrator
