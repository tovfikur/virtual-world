# Exchange & Trading Context (session snapshot)

## Backend scope completed
- Instruments CRUD (`/api/v1/instruments`) with asset class, tick/lot, leverage flags; DB tables auto-created on entrypoint.
- Orders/trades endpoints (`/api/v1/orders`, `/api/v1/trades`) with filters and pagination; orders ordered latest-first.
- Matching service: price-time priority books, market/limit, IOC/FOK, iceberg disclosure/replenish, trailing-stop/stop/stop-limit activation, OCO sibling cancel, maker attribution, liquidity pre-check for FOK, market liquidity guards, and market-state enforcement.
- Market status controls: `/api/v1/market/status` (admin to set open/halt/close). Matching rejects when not open.
- Tests passing: `tests/test_instruments.py`, `tests/test_order_book.py`, `tests/test_orders_match.py`, `tests/test_orders_advanced.py`, `tests/test_market_status.py`.
- Migrations: `a1b2c3d4e5f6_add_advanced_orders.py` (adds trailing_offset, oco_group_id, trailing_stop enum). MarketStatus table created via create_all on entrypoint.

## Backend gaps / remaining
- Legacy suites still failing: auth/chunks/land allocation/trading_permissions (asyncpg/TestClient loop, payload shapes, fixtures as coroutines).
- No filled_quantity tracking; advanced orders beyond current set (trailing, OCO, iceberg) not persisted.
- No market data feeds/WS, no margin/PNL engine, no portfolio endpoints.

## Frontend scope completed
- New `/exchange` route (OrdersPage) with:
  - Order entry for market/limit/stop/stop-limit/trailing-stop/iceberg; IOC/FOK; OCO group id; filters (instrument/side/status).
  - Recent trades panel (per-user).
  - Market status badge and admin controls (Open/Halt/Close).
  - Admin instrument creation form.
- Trading lab page now links to Exchange (Phase 2).
- Services updated: instruments CRUD, orders list with params, trades list, market status API.
- Frontend rebuilt and container redeployed.

## Deployment/runtime notes
- `docker compose build frontend && docker compose up -d frontend` used after changes.
- Backend entrypoint imports market/order/trade/instrument models for create_all. DB credentials from .env (`DB_PASSWORD=CHANGEME_STRONG_PASSWORD_HERE` for psql inside backend container).
- MarketStatus table created if absent; advanced orders enum value applied manually if needed (`ALTER TYPE ordertype ADD VALUE IF NOT EXISTS 'trailing_stop'`).

## Quick commands
- Run exchange tests: `docker compose exec backend pytest -q tests/test_orders_match.py tests/test_orders_advanced.py tests/test_market_status.py`
- Restart services: `docker compose restart backend frontend`

## Open tasks (from TODO_PHASE2.md)
- Stabilize legacy test suite (auth/chunks/land/trading_permissions).
- Pricing engine/WS feeds, margin/PNL/portfolio endpoints, admin UI for risk/fees, etc. still pending.
