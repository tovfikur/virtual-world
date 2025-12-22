# Exchange & Trading Context (session snapshot - RISK & MARGIN ADDED)

## Backend scope completed

- Instruments CRUD (`/api/v1/instruments`) with asset class, tick/lot, leverage flags; DB tables auto-created on entrypoint.
- Orders/trades endpoints (`/api/v1/orders`, `/api/v1/trades`) with filters and pagination; orders ordered latest-first.
- Matching service: price-time priority books, market/limit, IOC/FOK, iceberg disclosure/replenish, trailing-stop/stop/stop-limit activation, OCO sibling cancel, maker attribution, liquidity pre-check for FOK, market liquidity guards, and market-state enforcement.
- Market status controls: `/api/v1/market/status` (admin to set open/halt/close). Matching rejects when not open.
- Pricing Engine (`pricing_service.py`): LP quote aggregation, spread/markup application (FX 1bp, CFD 3bp+markup), tick normalization, configurable spreads per asset class.
- Market Data Service (`market_data_service.py`): OHLCV aggregation at 1s-1M timeframes, corporate action adjustments (splits/dividends), candle storage.
- Market Data APIs (`/api/v1/marketdata`): top-of-book quotes, depth (L2), candles with timeframe filters, corporate action history.
- WebSocket Market Data (`/ws/marketdata`): Real-time subscription channels for quotes, depth, trades, candles; publish trade/depth updates on matches.
- **NEW: Account & Margin Models** (`account.py`): Account (balance, equity, used/free margin, leverage limits), Position (LONG/SHORT tracking with P&L), MarginCall (margin event logging), CircuitBreaker (volatility halts).
- **NEW: Margin Calculation Service** (`margin_service.py`): Calculates margin requirements, equity, margin levels; opens/closes positions; tracks exposure per instrument.
- **NEW: Liquidation Service** (`liquidation_service.py`): Monitors margin levels, triggers margin calls at 100%, auto-liquidates positions at 50%; background monitoring task.
- **NEW: Pre-Trade Risk Validation** (`risk_service.py`): Validates leverage limits, margin sufficiency, position size limits (20% of equity), exposure limits (50% per instrument).
- **NEW: Circuit Breaker Service** (`circuit_breaker_service.py`): Monitors price volatility, triggers instrument-level (5%/10%/20%) and market-wide (7%/13%/20%) trading halts.
- Tests passing: `tests/test_instruments.py`, `tests/test_order_book.py`, `tests/test_orders_match.py`, `tests/test_orders_advanced.py`, `tests/test_market_status.py`, `tests/test_pricing_and_market_data.py`, `tests/test_margin_and_risk.py`.
- Migrations: `a1b2c3d4e5f6_add_advanced_orders.py` (adds trailing_offset, oco_group_id, trailing_stop enum). MarketStatus, PriceHistory, Account, Position, MarginCall, CircuitBreaker tables created via create_all on entrypoint.

## Backend gaps / remaining

- Legacy suites still failing: auth/chunks/land allocation/trading_permissions (asyncpg/TestClient loop, payload shapes, fixtures as coroutines).
- No filled_quantity tracking; advanced orders beyond current set (trailing, OCO, iceberg) not persisted.
- Market data aggregation happens in-memory during matching; not persisted to history tables yet (awaiting integration).
- No Alembic migration for PriceHistory and Account tables yet (only create_all).
- Background tasks for margin monitoring and circuit breaker checks not yet added to main.py startup.

## Frontend scope completed

- New `/exchange` route (OrdersPage) with:
  - Order entry for market/limit/stop/stop-limit/trailing-stop/iceberg; IOC/FOK; OCO group id; filters (instrument/side/status).
  - Recent trades panel (per-user).
  - Market status badge and admin controls (Open/Halt/Close).
  - Admin instrument creation form.
- Trading lab page now links to Exchange (Phase 2).
- Services updated: instruments CRUD, orders list with params, trades list, market status API.
- Frontend rebuilt and container redeployed.
- **NEW: Market data WebSocket client** (can subscribe to quote/depth/trades/candles channels).

## Deployment/runtime notes

- `docker compose build frontend && docker compose up -d frontend` used after changes.
- Backend entrypoint imports market/order/trade/instrument/price_history models for create_all. DB credentials from .env.
- MarketStatus and PriceHistory tables auto-created on startup; no manual ALTER TYPE needed for pricing.
- Real-time market data published to WS subscribers on every trade/depth change.

## Quick commands

- Run exchange tests: `docker compose exec backend pytest -q tests/test_orders_match.py tests/test_orders_advanced.py tests/test_market_status.py tests/test_pricing_and_market_data.py`
- Subscribe to market data WS: Connect to `ws://localhost/api/v1/ws/marketdata`, send `{"action": "subscribe", "channel": "quote:instrument_uuid"}`.
- Restart services: `docker compose restart backend frontend`

## Next up (from TODO_PHASE2.md)

- Stabilize legacy test suite (auth/chunks/land/trading_permissions).
- Risk/Margin/Exposure: accounts/margin model, margin calls, liquidation flow, circuit breakers.
- Fees & PnL: configurable fee schedules, swap/overnight fees, PnL calculations.
- Portfolio endpoints, admin UI for risk/fees.
