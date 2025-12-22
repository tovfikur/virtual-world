# Frontend Configuration & Setup Guide

## Quick Setup (5 minutes)

### 1. Configure Environment Variables

**Create `frontend/.env`**:

```env
# API Configuration
VITE_API_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws
VITE_API_TIMEOUT=30000

# Features
VITE_ENABLE_DEMO_MODE=false
VITE_ENABLE_PAPER_TRADING=true
VITE_ENABLE_CHARTS=true

# Logging
VITE_LOG_LEVEL=info
```

### 2. Install Dependencies

```bash
cd frontend
npm install
```

### 3. Start Development Server

```bash
npm run dev
# Opens http://localhost:5173
```

### 4. Start Backend (in another terminal)

```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Verify Connection

```bash
# In browser console:
console.log('API URL:', import.meta.env.VITE_API_URL);
// Should see: http://localhost:8000/api/v1
```

---

## API Endpoint Reference

### Trading Endpoints

```javascript
// Orders
GET    /orders                 - List user orders
POST   /orders                 - Create order
GET    /orders/{id}            - Get order details
PATCH  /orders/{id}            - Update order
DELETE /orders/{id}            - Cancel order
POST   /orders/{id}/amend      - Amend order

// Trades
GET    /trades                 - List user trades
GET    /trades/{id}            - Get trade details
GET    /trades/statistics      - Trade statistics
```

### Market Data Endpoints

```javascript
// Quotes
GET    /market/quotes?symbols=AAPL,GOOGL

// Depth (Order Book)
GET    /market/depth?symbol=AAPL&levels=10

// Candles
GET    /market/candles?symbol=AAPL&timeframe=1m&limit=100

// Trades
GET    /market/trades?symbol=AAPL&limit=50

// Instrument Info
GET    /instruments                    - All instruments
GET    /instruments/AAPL               - Specific instrument
```

### Portfolio Endpoints

```javascript
GET    /portfolio/summary              - Account summary
GET    /portfolio/positions            - Current positions
GET    /portfolio/balance              - Account balance
GET    /portfolio/equity               - Total equity
GET    /portfolio/margin               - Margin info
GET    /portfolio/performance          - P&L statistics
```

### WebSocket Channels

```javascript
// Subscribe to real-time updates
ws.send(
  JSON.stringify({
    type: "subscribe",
    channel: "quotes",
    instruments: ["AAPL", "GOOGL"],
  })
);

ws.send(
  JSON.stringify({
    type: "subscribe",
    channel: "depth",
    instrument: "AAPL",
  })
);

ws.send(
  JSON.stringify({
    type: "subscribe",
    channel: "trades",
    instrument: "AAPL",
  })
);

ws.send(
  JSON.stringify({
    type: "subscribe",
    channel: "notifications",
  })
);
```

---

## Frontend Service Usage Examples

### 1. Authentication

```javascript
import { api } from "./services/api";

// Login
const response = await api.post("/auth/login", {
  email: "user@example.com",
  password: "password123",
});

// Store token
localStorage.setItem("access_token", response.data.access_token);

// Get current user
const user = await api.get("/auth/me");
```

### 2. Creating an Order

```javascript
import { ordersService } from "./services/orders";

const order = await ordersService.createOrder({
  symbol: "AAPL",
  side: "BUY",
  quantity: 100,
  price: 150.5,
  type: "LIMIT",
  time_in_force: "GTC",
});

console.log("Order created:", order.id);
```

### 3. Getting Quotes

```javascript
import { marketService } from "./services/market";

const quotes = await marketService.getQuotes(["AAPL", "GOOGL"]);

quotes.forEach((quote) => {
  console.log(`${quote.symbol}: ${quote.bid} - ${quote.ask}`);
});
```

### 4. Getting Portfolio Summary

```javascript
import { api } from "./services/api";

const portfolio = await api.get("/portfolio/summary");

console.log("Balance:", portfolio.balance);
console.log("Equity:", portfolio.equity);
console.log("Used Margin:", portfolio.used_margin);
console.log("Margin Level:", portfolio.margin_level + "%");
```

### 5. WebSocket Connection

```javascript
import { websocketService } from "./services/websocket";

// Connect
websocketService.connect("ws://localhost:8000/ws");

// Subscribe to market data
websocketService.subscribe("quotes", {
  instruments: ["AAPL"],
});

// Listen for updates
websocketService.on("quote", (quote) => {
  console.log(`${quote.instrument}: ${quote.last}`);
});

// Listen for orders
websocketService.subscribe("notifications");
websocketService.on("order_update", (order) => {
  console.log("Order update:", order.status);
});
```

---

## Common Frontend Tasks

### Display Order Book

```javascript
async function displayOrderBook(symbol) {
  const depth = await marketService.getDepth(symbol, 10);

  // Render bids (red, descending)
  depth.bids.forEach(([price, size]) => {
    console.log(`BID  ${price} x ${size}`);
  });

  // Render asks (green, ascending)
  depth.asks.forEach(([price, size]) => {
    console.log(`ASK  ${price} x ${size}`);
  });
}
```

### Monitor Portfolio P&L

```javascript
async function monitorPortfolio() {
  const portfolio = await api.get("/portfolio/summary");

  const pnl = portfolio.equity - portfolio.balance;
  const pnl_pct = (pnl / portfolio.balance) * 100;

  console.log(`P&L: $${pnl.toFixed(2)} (${pnl_pct.toFixed(2)}%)`);
  console.log(`Margin Used: ${portfolio.margin_level}%`);

  if (portfolio.margin_level > 80) {
    console.warn("High margin usage!");
  }
}
```

### Create and Monitor Order

```javascript
async function createAndMonitorOrder() {
  // Create order
  const order = await ordersService.createOrder({
    symbol: "AAPL",
    side: "BUY",
    quantity: 100,
    type: "MARKET",
  });

  console.log("Order created:", order.id);

  // Subscribe to order updates
  websocketService.subscribe("orders");
  websocketService.on("order_update", (update) => {
    if (update.id === order.id) {
      console.log(`Order status: ${update.status}, Filled: ${update.filled}`);

      if (update.status === "FILLED") {
        console.log("Order fully filled!");
      }
    }
  });
}
```

### Real-Time Candles

```javascript
async function displayRealTimeCandles(symbol, timeframe) {
  // Get historical candles
  const candles = await marketService.getCandles(symbol, timeframe, 100);

  console.log("Latest candles:");
  candles.slice(-5).forEach((candle) => {
    console.log(
      `${candle.time}: O:${candle.open} H:${candle.high} L:${candle.low} C:${candle.close}`
    );
  });

  // Subscribe to trades
  websocketService.subscribe("trades", { instrument: symbol });

  // Build candles from trades
  websocketService.on("trade", (trade) => {
    if (trade.symbol === symbol) {
      // Aggregate trades into candles
      updateCandle(trade);
    }
  });
}
```

---

## Error Handling

### Handle API Errors

```javascript
try {
  const order = await ordersService.createOrder(orderData);
} catch (error) {
  if (error.response?.status === 400) {
    console.error("Invalid order:", error.response.data.detail);
  } else if (error.response?.status === 429) {
    console.error(
      "Rate limited. Retry after:",
      error.response.headers["retry-after"],
      "seconds"
    );
  } else if (error.response?.status === 403) {
    console.error("Insufficient margin");
  } else {
    console.error("Unexpected error:", error.message);
  }
}
```

### Handle WebSocket Errors

```javascript
websocketService.on("error", (error) => {
  console.error("WebSocket error:", error);
  console.log("Attempting to reconnect...");
});

websocketService.on("disconnected", () => {
  console.log("Disconnected. Will reconnect...");
});

websocketService.on("connected", () => {
  console.log("Connected to server");
});
```

---

## Performance Optimization

### Cache Market Data

```javascript
const cache = new Map();
const CACHE_TTL = 1000; // 1 second

async function getCachedQuote(symbol) {
  const cached = cache.get(symbol);

  if (cached && Date.now() - cached.time < CACHE_TTL) {
    return cached.data;
  }

  const quote = await marketService.getQuotes([symbol]);
  cache.set(symbol, { data: quote, time: Date.now() });
  return quote;
}
```

### Debounce Order Submissions

```javascript
import debounce from "lodash/debounce";

const submitOrder = debounce(async (orderData) => {
  try {
    const order = await ordersService.createOrder(orderData);
    console.log("Order submitted:", order.id);
  } catch (error) {
    console.error("Failed to submit order:", error);
  }
}, 300);

// User types in order form - calls are debounced
```

### Batch API Requests

```javascript
async function getBatchQuotes(symbols) {
  // Instead of N requests, get all in one
  const params = symbols.join(",");
  return api.get(`/market/quotes?symbols=${params}`);
}
```

---

## Testing

### Test Order Creation

```javascript
test("should create buy order", async () => {
  const order = await ordersService.createOrder({
    symbol: "AAPL",
    side: "BUY",
    quantity: 100,
    type: "MARKET",
  });

  expect(order.id).toBeDefined();
  expect(order.status).toBe("OPEN");
  expect(order.filled).toBe(0);
});
```

### Test WebSocket

```javascript
test("should receive quote updates", async () => {
  const quotes = [];

  websocketService.subscribe("quotes", { instruments: ["AAPL"] });
  websocketService.on("quote", (quote) => {
    quotes.push(quote);
  });

  // Wait for at least one quote
  await new Promise((resolve) => setTimeout(resolve, 1000));

  expect(quotes.length).toBeGreaterThan(0);
});
```

---

## Production Deployment

### Build for Production

```bash
cd frontend
npm run build
# Creates dist/ folder with optimized assets
```

### Environment Configuration

**`.env.production`**:

```env
VITE_API_URL=https://api.example.com/api/v1
VITE_WS_URL=wss://api.example.com/ws
VITE_LOG_LEVEL=warn
```

### Docker Deployment

```dockerfile
# frontend/Dockerfile
FROM node:18-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

---

## Monitoring

### Log API Metrics

```javascript
api.interceptors.response.use((response) => {
  const duration = response.config.metadata?.startTime
    ? Date.now() - response.config.metadata.startTime
    : 0;

  console.log(
    `[API] ${response.status} ${response.config.url} (${duration}ms)`
  );
  return response;
});
```

### Monitor WebSocket Health

```javascript
setInterval(() => {
  if (websocketService.isConnected()) {
    console.log("✓ WebSocket connected");
  } else {
    console.warn("✗ WebSocket disconnected");
  }
}, 30000);
```

### Rate Limit Monitoring

```javascript
api.interceptors.response.use((response) => {
  const limit = response.headers["x-ratelimit-limit"];
  const remaining = response.headers["x-ratelimit-remaining"];
  const reset = response.headers["x-ratelimit-reset"];

  console.log(
    `Rate Limit: ${remaining}/${limit} (resets at ${new Date(reset * 1000)})`
  );

  if (remaining < limit * 0.2) {
    console.warn("⚠ Approaching rate limit!");
  }

  return response;
});
```

---

## Troubleshooting

### CORS Error

```
Access to XMLHttpRequest has been blocked by CORS policy
```

**Solution**: Ensure backend CORS includes frontend origin:

```python
# In main.py
allow_origins=[
    "http://localhost:5173",
    "http://localhost:3000",
    "https://example.com"
]
```

### 401 Unauthorized

```
Status: 401, Error: Unauthorized
```

**Solution**:

1. Check token in localStorage: `localStorage.getItem('access_token')`
2. Verify token is not expired
3. Try logging in again
4. Check `/auth/refresh` endpoint works

### WebSocket Connection Failed

```
WebSocket is closed before the connection is established
```

**Solution**:

1. Verify WS URL is correct (should be `ws://` not `http://`)
2. Check backend is running
3. Check firewall allows WebSocket
4. Verify no proxy blocking WebSocket upgrade

### Rate Limit Error

```
Status: 429, Error: Too Many Requests
```

**Solution**:

1. Wait for `Retry-After` seconds
2. Reduce request frequency
3. Upgrade account tier for higher limits
4. Batch requests when possible

---

## Support & Resources

- **API Documentation**: http://localhost:8000/docs (Swagger UI)
- **OpenAPI Schema**: http://localhost:8000/openapi.json
- **Frontend README**: `frontend/README.md`
- **Backend README**: `backend/README.md`

---

**Frontend is fully configured and ready to consume all Phase 2 backend APIs!** 🎉
