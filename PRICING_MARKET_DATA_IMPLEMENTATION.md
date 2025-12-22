# Pricing & Market Data System Implementation Summary

## Overview

Completed implementation of comprehensive pricing engine and market data infrastructure for the exchange. Includes LP quote aggregation, OHLCV candle generation, corporate action handling, and real-time WebSocket feeds.

## Components Implemented

### 1. Pricing Service (`backend/app/services/pricing_service.py`)

- **LP Quote Aggregation**: Combines quotes from multiple liquidity providers
- **Spread Management**:
  - Default: 2bp
  - FX: 1bp (configurable)
  - CFD: 3bp + 1bp broker markup (configurable)
- **Tick Normalization**: Rounds prices to instrument tick size
- **Features**:
  - Quote caching with stale quote detection (30s timeout)
  - Best bid/ask aggregation from all fresh providers
  - Liquidity aggregation across providers
  - Configurable via `PricingConfig` class

### 2. Market Data Models (`backend/app/models/price_history.py`)

- **PriceHistory**: OHLCV candles at multiple timeframes

  - Supports: 1s, 5s, 15s, 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 1M
  - Fields: open, high, low, close, volume, trade_count, VWAP, typical price
  - Indexed by: (instrument_id, timeframe, timestamp)
  - Adjustment factor for corporate actions

- **CorporateAction**: Records splits, dividends, reverse splits

  - Automatically adjusts historical prices
  - Supports ratio-based (splits) and dividend records

- **QuoteLevel**: Real-time LP quotes
  - Bid/ask with sizes
  - Spread and spread_bp calculations
  - Stale quote tracking

### 3. Market Data Aggregation Service (`backend/app/services/market_data_service.py`)

- **Candle Generation**:

  - Automatically aggregates trades into candles at all timeframes
  - VWAP and typical price calculations
  - Trade count and notional volume tracking

- **Corporate Action Handling**:

  - Apply splits to historical prices (adjustment factor \*= ratio)
  - Support for dividend records
  - Automatic price adjustment on retrieval

- **Candle Retrieval**:
  - Filter by time range
  - Limit result count
  - Return adjusted prices (accounting for corporate actions)

### 4. Market Data REST APIs (`backend/app/api/v1/endpoints/marketdata.py`)

Endpoints under `/api/v1/marketdata/`:

- **GET `/quotes/{instrument_id}`** - Top-of-book quote with spreads
- **GET `/depth/{instrument_id}`** - Order book depth (L2, configurable levels)
- **GET `/candles/{instrument_id}`** - OHLCV candles with timeframe/time filters
- **GET `/top-of-book`** - All active instruments' quotes
- **POST `/quotes/{instrument_id}/add`** - Add/update LP quote (admin/integration)

All endpoints support UUID instrument IDs and return ISO timestamps.

### 5. WebSocket Market Data Service (`backend/app/services/websocket_service.py`)

- **MarketDataSubscriptionManager**: New class managing subscriptions
  - Subscribe/unsubscribe from channels
  - Publish to all subscribers
  - Automatic cleanup on disconnect
  - Channels: `quote:{id}`, `depth:{id}`, `trades:{id}`, `candles:{id}:{tf}`, `status:{id}`

### 6. WebSocket Endpoint (`backend/app/api/v1/endpoints/marketdata_ws.py`)

- **URL**: `/ws/marketdata`
- **Protocol**:
  - Subscribe: `{"action": "subscribe", "channel": "quote:uuid"}`
  - Unsubscribe: `{"action": "unsubscribe", "channel": "quote:uuid"}`
  - Ping: `{"action": "ping"}` → `{"type": "pong"}`
- **Messages**:
  - Subscribed: `{"type": "subscribed", "channel": "..."}`
  - Data: `{"type": "market_data", "channel": "...", "data": {...}, "timestamp": "..."}`
  - Errors: `{"type": "error", "message": "..."}`

### 7. Matching Engine Integration (`backend/app/services/matching_service.py`)

- **Trade Publishing**: After each fill, publishes trade to `trades:{instrument_id}` channel
- **Depth Publishing**: After each fill, publishes updated L10 depth to `depth:{instrument_id}`
- **Data Format**:
  ```python
  {
      "instrument_id": "uuid",
      "side": "BUY|SELL",
      "price": 100.50,
      "quantity": 1000,
      "buyer_id": "uuid",
      "seller_id": "uuid",
      "timestamp": "2025-01-01T12:00:00"
  }
  ```

## Database Schema

### PriceHistory

- id (PK)
- instrument_id (FK → Instrument)
- timeframe (Enum)
- timestamp (DateTime)
- open, high, low, close, volume
- trade_count, notional, vwap, typical_price
- adjustment_factor
- Index: (instrument_id, timeframe, timestamp)

### CorporateAction

- id (PK)
- instrument_id (FK → Instrument)
- action_type (Enum)
- effective_date
- ratio, dividend_per_share, currency
- description

### QuoteLevel

- id (PK)
- instrument_id (FK → Instrument)
- provider (String)
- bid_price, ask_price, bid_size, ask_size
- spread, spread_bp, mid
- timestamp, is_stale
- Index: (instrument_id, provider, timestamp)

## Testing

- **Test File**: `backend/tests/test_pricing_and_market_data.py`
- **Coverage**:
  - LP quote aggregation and multi-provider handling
  - Tick normalization with configurable precision
  - CFD markup application
  - OHLCV candle generation at multiple timeframes
  - Corporate action adjustments (splits)
  - Order book depth calculation
  - Stale quote detection

## Usage Examples

### Subscribe to Market Data

```javascript
const ws = new WebSocket("ws://localhost/api/v1/ws/marketdata");

ws.onopen = () => {
  // Subscribe to quotes
  ws.send(
    JSON.stringify({
      action: "subscribe",
      channel: "quote:550e8400-e29b-41d4-a716-446655440000",
    })
  );

  // Subscribe to trades
  ws.send(
    JSON.stringify({
      action: "subscribe",
      channel: "trades:550e8400-e29b-41d4-a716-446655440000",
    })
  );
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  console.log("Market Data:", msg.data);
};
```

### Get Candles via REST

```bash
curl "http://localhost/api/v1/marketdata/candles/550e8400-e29b-41d4-a716-446655440000?timeframe=1m&limit=100&start_time=2025-01-01T00:00:00&end_time=2025-01-02T00:00:00"
```

### Get Quote

```bash
curl "http://localhost/api/v1/marketdata/quotes/550e8400-e29b-41d4-a716-446655440000"
```

## Performance Considerations

- **In-memory quote cache**: O(1) lookups, instant updates
- **Depth calculation**: O(L) where L = levels (typically 10-20)
- **Candle aggregation**: O(1) per trade (running aggregation)
- **Corporate action adjustments**: Applied at retrieval time (no pre-computation)

## Integration with Matching Engine

- Every trade automatically recorded to PriceHistory candles
- Trade execution triggers WebSocket publish to all subscribers
- Depth updates published after every fill
- Last trade price tracked for stop order activation

## Configuration

Edit `PricingConfig` in `pricing_service.py`:

```python
config = PricingConfig(
    base_spread_bp=2.0,        # Default spread
    fx_spread_bp=1.0,          # FX specific
    cfd_spread_bp=3.0,         # CFD specific
    cfd_markup_bp=1.0,         # CFD markup
    stale_quote_timeout_sec=30,
    tick_normalization=True
)
```

## Next Steps

1. Persist aggregated candles to database automatically
2. Add Alembic migration for PriceHistory tables (currently via create_all)
3. Implement Margin & Exposure system
4. Add PnL calculation service
5. Create portfolio aggregation endpoints
