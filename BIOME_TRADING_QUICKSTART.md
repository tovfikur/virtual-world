# Biome Trading System - Quick Start Guide

## Prerequisites

- Docker & Docker Compose running
- Backend and frontend containers up and healthy

## Starting the System

```bash
cd k:\VirtualWorld
docker-compose up -d
```

Wait for all containers to be healthy:

```bash
docker-compose ps
# Should show all containers as "healthy" or "running"
```

## Accessing the System

1. **Frontend**: Navigate to http://localhost:3000
2. **Backend API**: http://localhost:8000
3. **API Docs**: http://localhost:8000/docs (Swagger UI)

## User Workflow

### 1. Register & Login

- Click "Login" button (or navigate to /login)
- Create new account with email and password
- Login with credentials

### 2. Access Biome Market

- Click "Biome Market" link in header navigation
- Or navigate directly to `/biome-market`

### 3. View Markets

- See all 7 biome markets with current prices
- Prices updated in real-time via WebSocket
- Select a biome to see detailed trading panel

### 4. Trade Shares

- **Buy**: Enter BDT amount, click "Buy"

  - Requires sufficient balance
  - Deducts from wallet immediately
  - Shares added to portfolio

- **Sell**: Enter number of shares, click "Sell"
  - Requires sufficient holdings
  - Proceeds added to wallet
  - Transaction recorded with realized gain/loss

### 5. Track Performance

- Portfolio shows:

  - Total balance
  - Total invested
  - Current portfolio value
  - Unrealized P&L

- Holdings detail shows per-biome:
  - Shares owned
  - Average buy price
  - Current value
  - Gain/loss per biome

### 6. Monitor Price History

- Select biome to view 24-hour sparkline chart
- Shows price movement over last 24 hours
- Updates as new data arrives

## API Endpoints (for testing)

### Market Data

```bash
# Get all markets
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/biome-market/markets

# Get specific biome
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/biome-market/markets/ocean

# Get price history
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/biome-market/price-history/forest?hours=24
```

### Trading

```bash
# Buy shares
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"biome": "ocean", "amount_bdt": 1000}' \
  http://localhost:8000/api/v1/biome-market/buy

# Sell shares
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"biome": "ocean", "shares": 5}' \
  http://localhost:8000/api/v1/biome-market/sell

# Get portfolio
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/biome-market/portfolio

# Get transaction history
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/biome-market/transactions
```

### Attention & Updates

```bash
# Track attention (triggers price redistribution)
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"biome": "forest", "score": 50}' \
  http://localhost:8000/api/v1/biome-market/track-attention
```

## WebSocket Real-Time Updates

The frontend automatically connects to WebSocket when user logs in.

**Subscribe to market updates:**

```json
{
  "action": "subscribe_biome_market",
  "room": "biome_market_all"
}
```

**Receive market updates:**

```json
{
  "type": "biome_market_update",
  "markets": [...],
  "redistributions": [...]
}
```

## Running the Smoke Test

```bash
cd k:\VirtualWorld
python smoke_test_biome_trading.py
```

This validates all basic functionality:

- API connectivity
- Authentication
- Market data access
- Trading operations
- Attention tracking
- WebSocket framework

## Checking Logs

### Backend Logs

```bash
docker logs virtualworld-backend -f
```

### Frontend Logs

```bash
docker logs virtualworld-frontend -f
```

### Database Logs

```bash
docker logs virtualworld-postgres -f
```

## Troubleshooting

### "Insufficient balance" error

- New users start with 0 BDT
- Users need initial funding from admin or game mechanics
- Balance shown in portfolio panel

### "Unable to connect to WebSocket"

- Check that backend is running: `docker ps`
- Check browser console for auth errors
- Verify token is valid (logout and re-login)

### Price not updating

- Ensure backend worker is running (check logs for "Starting redistribution")
- Check that at least one biome has attention tracked
- Try tracking attention manually to trigger update

### Transaction fails

- Verify sufficient balance (for buys) or shares (for sells)
- Ensure biome name is valid (ocean, beach, plains, forest, desert, mountain, snow)
- Check backend logs for detailed error message

## Key Statistics

- **Biomes**: 7 (ocean, beach, plains, forest, desert, mountain, snow)
- **Initial Price**: 100 BDT per share
- **Initial Shares**: 1 million per biome
- **Redistribution Cycle**: 0.5 seconds
- **Redistribution Pool**: 25% of Total Market Cash
- **Attention Reset**: After each redistribution

## Next Steps

1. **Test the system**: Use smoke test or manual testing
2. **Integrate funding**: Add mechanism to give users initial BDT
3. **Monitor activity**: Check logs and database for trading patterns
4. **Optimize performance**: Monitor WebSocket connection count, redistribution latency
5. **Add features**: Implement leaderboards, advanced orders, limits as needed

---

**System Status**: READY FOR TESTING ✓
**Last Updated**: 2025-12-25
