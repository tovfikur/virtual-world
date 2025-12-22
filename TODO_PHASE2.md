# Phase 2 To-Do (Exchange Scope)

- [x] Draft high-level roadmap for phase 2 (this file)
- [ ] Stabilize legacy test suite (auth/chunks/land/trading permissions) for async TestClient + asyncpg (currently failing).

## Core Trading & Matching

- [x] Define instrument model (equities/forex/commodities/indices/crypto/derivatives) with tick size, lot size, leverage flags, and trading session controls.
- [x] Implement order types schema (market/limit/stop/stop-limit/IOC/FOK/iceberg/OCO) with validation.
- [x] Build in-memory order book per instrument (price-time priority) with Level I/II snapshots.
- [x] Implement matching engine loop (price-time, partial fills) and persistence of orders/trades (limit/market, maker attribution, IOC/FOK paths done; status updates for resting/IOC/FOK/market).
- [x] Add advanced orders handling: trailing stop, OCO linking, IOC/FOK execution paths beyond scaffold, iceberg disclosure logic.
- [x] Add market status controls (open/close/halt per instrument and market-wide).

## Pricing & Market Data

- [x] Add pricing engine to aggregate LP quotes (for FX/CFDs), apply spread/markup, normalize ticks, publish feed (WS).
- [x] Publish market data channels: top-of-book, depth, trades, candles; support 1s through monthly aggregation.
- [x] Price history storage with corporate-action-aware adjustments (splits/dividends).

## Risk, Margin & Exposure

- [x] Introduce accounts/margin model (used/free margin, equity, leverage limits).
- [x] Real-time pre-trade risk checks: max order size, exposure per instrument/user, leverage validation, margin sufficiency.
- [x] Margin call & liquidation flow (partial/full) with configurable thresholds.
- [x] Circuit breakers/volatility halts (instrument + market-wide).

## Fees & PnL

- [ ] Configurable fee schedules (maker/taker, per instrument/tier) and commissions per lot.
- [ ] Swap/overnight fees for FX/CFDs; funding rates for derivatives.
- [ ] PnL calculations (realized/unrealized), portfolio aggregation, VWAP/average price tracking.

## Portfolio, Positions, History

- [ ] Positions service (net/hedged modes), add/hedge/close/partial close, reverse position.
- [x] Orders/trades/fees/taxes history endpoints; filters and pagination (orders/trades now include instrument filter + limit/offset; orders ordered latest-first).
- [ ] Portfolio & dashboard endpoints: balance, equity, margin level, alerts.
  - [x] Trades history: basic per-user listing (no filters/pagination yet).

## Clearing & Settlement

- [ ] Trade confirmation and netting pipeline; T+N settlement support for equities.
- [ ] Custody balance updates, reconciliation hooks; broker/LP payout flows.

## Admin, Broker, Compliance

- [ ] Admin controls: add/remove instruments, change tick/lot, leverage, fees; halt/resume instruments/market.
- [ ] Broker features: client sub-accounts, A-book/B-book routing, exposure hedging, commission sharing.
- [ ] Surveillance hooks: spoofing/wash/front-running pattern stubs; audit log expansion.
- [ ] Regulator/auditor read-only views; export for best-execution/tax reports.

## API & UI

- [ ] REST + WebSocket (and FIX stub) for trading, market data, admin.
- [x] Trading terminal UI: basic order entry/cancel wired to scaffold (OrdersPage); live feed/depth/charts pending.
- [~] Portfolio/positions UI: P/L, margin, risk alerts; order/trade history UI (orders list basic; trades list basic API) — partial.
- [ ] Admin UI: market status, instruments, risk/fee config, surveillance alerts.
- [x] REST endpoints for instruments/orders/trades; DB tables auto-created via entrypoint.

## Reliability & Tests

- [ ] Load/perf tests for matching path (<1ms target per match) and market data latency.
- [ ] Unit/integration tests: order validation, matching, risk checks, margin, PnL, fee calc.
- [ ] Persistence durability and recovery tests; background runners health checks.
- [ ] Fix failing legacy tests (auth, chunks, land allocation, trading permissions) due to async TestClient/event-loop mismatch and pending dependency cleanup.
  - Note: current failures stem from asyncpg/TestClient loop mismatch, chunk batch payload shape, land allocation fixtures returning coroutines, and trading permission path returning 500 instead of 402 when balance is low.
