# Biome Trading System - File Reference Guide

## Complete File Inventory

### Backend - Database Models (5 files)

```
backend/app/models/
├── biome_market.py          [NEW] BiomeMarket model, enums, constants
├── biome_holding.py         [NEW] BiomeHolding model for user portfolios
├── biome_transaction.py     [NEW] BiomeTransaction model, TransactionType enum
├── biome_price_history.py   [NEW] BiomePriceHistory model
├── attention_score.py       [NEW] AttentionScore model
└── __init__.py              [MODIFIED] Added biome model exports
```

### Backend - Services (4 files)

```
backend/app/services/
├── biome_market_service.py          [NEW] 250+ lines
│   └── BiomeMarketService class with:
│       - initialize_markets()
│       - get_all_markets()
│       - get_market(biome)
│       - execute_redistribution() [CORE ALGORITHM]
│       - get_price_history()
│
├── biome_trading_service.py         [NEW] 200+ lines
│   └── BiomeTradingService class with:
│       - buy_shares(user_id, biome, amount_bdt)
│       - sell_shares(user_id, biome, shares)
│       - get_user_portfolio(user_id)
│       - get_transaction_history(user_id, offset, limit)
│
├── attention_tracking_service.py    [NEW] 150+ lines
│   └── AttentionTrackingService class with:
│       - track_attention(user_id, biome, score)
│       - get_user_attention(user_id)
│       - get_biome_total_attention(biome)
│       - reset_all_attention()
│
└── biome_market_worker.py           [NEW] 100+ lines
    └── Background worker task:
        - Runs every 0.5 seconds
        - Executes redistribution
        - Broadcasts via WebSocket
```

### Backend - API Endpoints (2 files)

```
backend/app/api/v1/endpoints/
├── biome_market.py          [NEW] 391 lines
│   ├── @router.get("/markets")
│   ├── @router.get("/markets/{biome}")
│   ├── @router.get("/price-history/{biome}")
│   ├── @router.post("/buy")
│   ├── @router.post("/sell")
│   ├── @router.get("/portfolio")
│   ├── @router.get("/transactions")
│   └── @router.post("/track-attention")
│
└── websocket.py             [MODIFIED] Added WebSocket handlers:
    ├── subscribe_biome_market handler
    └── unsubscribe_biome_market handler
```

### Backend - Schemas (1 file)

```
backend/app/schemas/
└── biome_trading_schema.py  [NEW] 236 lines
    ├── Enums:
    │   ├── BiomeType (7 biomes)
    │   └── TransactionType (buy, sell)
    ├── Request Models:
    │   ├── BuySharesRequest
    │   ├── SellSharesRequest
    │   ├── TrackAttentionRequest
    │   └── GetTransactionsRequest
    └── Response Models:
        ├── BiomeMarketResponse
        ├── AllBiomeMarketsResponse
        ├── BiomeHoldingResponse
        ├── BiomePortfolioResponse
        ├── TradeResponse
        ├── TransactionResponse
        ├── AttentionResponse
        └── BiomeAttentionResponse
```

### Backend - Core Application (1 file)

```
backend/app/
└── main.py                  [MODIFIED]
    └── Integrated biome_market_worker into lifespan
```

### Backend - Database Migration (1 file)

```
backend/alembic/versions/
└── 1de27dadc797_add_biome_trading_tables.py [NEW]
    Creates 5 tables:
    ├── biome_markets
    ├── biome_holdings
    ├── biome_transactions
    ├── biome_price_history
    └── attention_scores
```

### Frontend - Pages (1 file)

```
frontend/src/pages/
└── BiomeMarketPage.jsx      [NEW] 400+ lines
    ├── Portfolio Summary Panel
    │   ├── Balance display
    │   ├── Invested amount
    │   ├── Current value
    │   └── Unrealized P&L
    ├── Market Grid
    │   ├── 7 biome cards
    │   ├── Current prices
    │   └── Selection handler
    ├── Trading Panel
    │   ├── Buy form
    │   ├── Sell form
    │   └── Form validation
    ├── Price Chart
    │   ├── 24-hour sparkline
    │   └── Real-time updates
    └── Holdings Sidebar
        ├── Position details
        ├── P&L per holding
        └── Percentage allocation
```

### Frontend - Components (1 file)

```
frontend/src/components/
├── BiomeSparkline.jsx       [NEW] 100+ lines
│   └── SVG sparkline chart for price visualization
│
└── HUD.jsx                  [MODIFIED]
    ├── Added desktop nav link to Biome Market
    └── Added mobile menu link to Biome Market
```

### Frontend - Services (1 file)

```
frontend/src/services/
└── api.js                   [MODIFIED]
    Added biomeMarketAPI object with:
    ├── getMarkets()
    ├── getMarket(biome)
    ├── getPriceHistory(biome, hours)
    ├── buy(biome, amount)
    ├── sell(biome, shares)
    ├── getPortfolio()
    ├── getTransactions(offset, limit)
    └── trackAttention(biome, score)
```

### Frontend - Routing (1 file)

```
frontend/src/
└── App.jsx                  [MODIFIED]
    ├── Added BiomeMarketPage import
    └── Added route: /biome-market
```

### Testing - Unit & Integration Tests (2 files)

```
backend/tests/
├── test_biome_market.py     [NEW] 300+ lines
│   ├── TestBiomeMarketInitialization
│   ├── TestBiomeTrading
│   ├── TestAttentionTracking
│   └── TestBiomeMarketAPI
│
└── test_biome_market_ws.py  [NEW] 200+ lines
    └── TestBiomeMarketWebSocket
```

### Testing - Smoke Test (1 file)

```
project_root/
└── smoke_test_biome_trading.py [NEW] 220+ lines
    ├── test_health()
    ├── test_register_user()
    ├── test_login()
    ├── test_get_markets()
    ├── test_get_portfolio()
    ├── test_buy_shares()
    ├── test_track_attention()
    ├── test_websocket_market_subscription()
    └── run_smoke_tests()
```

### Documentation (3 files)

```
project_root/
├── BIOME_TRADING_SYSTEM_COMPLETE.md          [NEW]
│   └── Complete architecture & design documentation
│
├── BIOME_TRADING_QUICKSTART.md               [NEW]
│   └── User guide, API reference, troubleshooting
│
└── BIOME_TRADING_IMPLEMENTATION_CHECKLIST.md [NEW]
    └── Detailed implementation status & verification
```

## File Statistics

### Code Files Created: 17

- Backend Models: 5
- Backend Services: 4
- Backend Endpoints: 1
- Backend Schemas: 1
- Frontend Pages: 1
- Frontend Components: 1
- Frontend Services: 1
- Testing: 3
- Documentation: 3

### Code Files Modified: 6

- backend/app/models/**init**.py
- backend/app/api/v1/endpoints/websocket.py
- backend/app/main.py
- frontend/src/components/HUD.jsx
- frontend/src/services/api.js
- frontend/src/App.jsx

### Total Lines of Code: 3000+

- Backend Implementation: 1500+ lines
- Frontend Implementation: 600+ lines
- Tests: 500+ lines
- Documentation: 400+ lines

## Key Configuration Values

### Database

- Host: postgres (Docker Compose)
- Port: 5432
- Database: virtualworld
- Enums: biome (7 types), biometransactiontype (2 types)

### Background Worker

- Interval: 0.5 seconds
- Task: execute_redistribution()
- Broadcast: WebSocket pub/sub

### Market Economics

- Initial Price: 100 BDT/share
- Initial Shares: 1,000,000 per biome
- Initial Market Cash: 100,000,000 BDT total
- Redistribution Pool: 25% of Total Market Cash (TMC/4)
- Attention Reset: After each redistribution cycle

### WebSocket

- Route: /api/v1/ws
- Auth: JWT token (with guest fallback)
- Rooms: biome*market_all, biome_market*{biome}
- Update Frequency: 0.5 seconds (with redistribution)

### API Endpoints

- Base URL: /api/v1/biome-market
- Authentication: Bearer token (JWT)
- Response Format: JSON
- Pagination: offset/limit optional

## Dependencies Added

### Backend (Python)

- SQLAlchemy 2.0.23 (already present)
- Pydantic v2 (already present)
- Alembic 1.12.1 (already present)
- asyncio (built-in)
- uuid (built-in)
- decimal (built-in)

### Frontend (JavaScript)

- React 18 (already present)
- Zustand (already present)
- Axios (already present)
- Tailwind CSS (already present)
- React Router v6 (already present)
- Native WebSocket API (built-in)

### Docker

- No new images required
- Uses existing: python:3.11-slim, node:18-alpine, nginx:alpine

## Deployment Checklist

### Pre-Deployment

- [x] All code written and tested
- [x] Database migrations created
- [x] Frontend components built
- [x] API endpoints tested
- [x] WebSocket handlers implemented
- [x] Documentation created
- [x] Smoke tests passing

### Deployment Steps

1. Rebuild frontend: `docker-compose up -d --build frontend`
2. Rebuild backend: `docker-compose up -d --build backend`
3. Run migrations: Backend auto-runs on startup
4. Verify health: Check `/health` endpoint
5. Test workflows: Run smoke test
6. Monitor logs: Watch container logs

### Post-Deployment

- Monitor error rates
- Check WebSocket connections
- Verify redistribution running
- Monitor database growth
- Test with real users

---

## Quick Navigation

**Architecture**: See `BIOME_TRADING_SYSTEM_COMPLETE.md`
**Usage Guide**: See `BIOME_TRADING_QUICKSTART.md`
**Implementation Status**: See `BIOME_TRADING_IMPLEMENTATION_CHECKLIST.md`
**API Testing**: Run `smoke_test_biome_trading.py`
**API Docs**: Visit `http://localhost:8000/docs`

---

**Total Implementation Time**: Complete in single session
**Status**: READY FOR PRODUCTION ✓
**Last Updated**: 2025-12-25
