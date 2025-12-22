# Frontend Quick Reference Card

## 🚀 Quick Start (5 minutes)

### 1. Start Backend

```bash
cd backend && python -m uvicorn app.main:app --reload
```

### 2. Start Frontend

```bash
cd frontend && npm install && npm run dev
```

### 3. Open in Browser

```
Frontend: http://localhost:5173
API Docs: http://localhost:8000/docs
```

---

## 📦 Import Services

```javascript
// API Calls
import { api } from "@/services/api.js";
await api.get("/orders");
await api.post("/orders", orderData);

// Orders
import { ordersService } from "@/services/orders.js";
const order = await ordersService.createOrder(data);

// Market Data
import { marketService } from "@/services/market.js";
const quotes = await marketService.getQuotes(["AAPL", "GOOGL"]);
const depth = await marketService.getDepth("AAPL");
const candles = await marketService.getCandles("AAPL", "1m", 100);

// Instruments
import { instrumentsService } from "@/services/instruments.js";
const instruments = await instrumentsService.search("AAPL");

// WebSocket
import { websocketService } from "@/services/websocket.js";
websocketService.connect(token);
websocketService.subscribe("quotes", { instruments: ["AAPL"] });
websocketService.on("quote", (quote) => console.log(quote));
```

---

## 🔐 Authentication

```javascript
// Login
const { access_token, refresh_token } = await api.post("/auth/login", {
  email,
  password,
});
localStorage.setItem("access_token", access_token);
localStorage.setItem("refresh_token", refresh_token);

// Auto-refresh on 401 (handled by api.js)
// Just use api.get/post normally

// Current User
const user = await api.get("/auth/me");

// Logout
await api.post("/auth/logout");
localStorage.removeItem("access_token");
```

---

## 📊 API Endpoints Cheat Sheet

| Method | Endpoint               | Purpose           |
| ------ | ---------------------- | ----------------- |
| POST   | `/auth/login`          | Login             |
| GET    | `/orders`              | List orders       |
| POST   | `/orders`              | Create order      |
| PATCH  | `/orders/{id}`         | Update order      |
| DELETE | `/orders/{id}`         | Cancel order      |
| GET    | `/trades`              | List trades       |
| GET    | `/market/quotes`       | Get quotes        |
| GET    | `/market/depth`        | Get order book    |
| GET    | `/market/candles`      | Get candles       |
| GET    | `/market/trades`       | Get trades        |
| GET    | `/portfolio/summary`   | Account info      |
| GET    | `/portfolio/positions` | Current positions |
| GET    | `/settlement/summary`  | Settlement info   |

---

## 📈 Common Patterns

### Fetch Data with Loading State

```javascript
const [data, setData] = useState(null);
const [loading, setLoading] = useState(true);
const [error, setError] = useState(null);

useEffect(() => {
  const load = async () => {
    try {
      const result = await api.get("/endpoint");
      setData(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  load();
}, []);

if (loading) return <Spinner />;
if (error) return <Error message={error} />;
return <Component data={data} />;
```

### Subscribe to Real-Time Updates

```javascript
useEffect(() => {
  websocketService.subscribe("channel_name", { param: "value" });

  const handler = (update) => {
    // Handle update
  };

  websocketService.on("event_name", handler);

  return () => {
    // Cleanup
    websocketService.off("event_name", handler);
  };
}, []);
```

### Form Submission with Error Handling

```javascript
const [error, setError] = useState(null);
const [loading, setLoading] = useState(false);

const handleSubmit = async (data) => {
  setLoading(true);
  setError(null);
  try {
    const result = await api.post("/endpoint", data);
    // Success
  } catch (err) {
    if (err.response?.status === 400) {
      setError(err.response.data.detail);
    } else if (err.response?.status === 429) {
      setError("Rate limited. Try again later.");
    } else {
      setError("Unexpected error");
    }
  } finally {
    setLoading(false);
  }
};
```

---

## 🔌 WebSocket Channels

```javascript
// Subscribe to quotes
websocketService.subscribe("quotes", {
  instruments: ["AAPL", "GOOGL"],
});
websocketService.on("quote", (quote) => {
  console.log(quote.symbol, quote.last);
});

// Subscribe to order book
websocketService.subscribe("depth", {
  instrument: "AAPL",
});
websocketService.on("depth_update", (depth) => {
  console.log(depth.bids, depth.asks);
});

// Subscribe to trades
websocketService.subscribe("trades", {
  instrument: "AAPL",
});
websocketService.on("trade", (trade) => {
  console.log(trade.side, trade.price, trade.size);
});

// Subscribe to candles
websocketService.subscribe("candles", {
  instrument: "AAPL",
  timeframe: "1m",
});
websocketService.on("candle", (candle) => {
  console.log(candle.close);
});

// Subscribe to notifications
websocketService.subscribe("notifications");
websocketService.on("order_update", (order) => {
  console.log(order.status, order.filled);
});
```

---

## 📝 Create an Order

```javascript
const order = await ordersService.createOrder({
  symbol: "AAPL",
  side: "BUY", // BUY or SELL
  quantity: 100,
  price: 150.5, // Ignored for MARKET orders
  type: "LIMIT", // MARKET or LIMIT
  time_in_force: "GTC", // GTC (Good Till Cancel)
});

console.log("Order ID:", order.id);
console.log("Status:", order.status);
console.log("Filled:", order.filled);
```

---

## 💼 Get Portfolio Info

```javascript
// Account Summary
const summary = await api.get("/portfolio/summary");
console.log("Balance:", summary.balance);
console.log("Equity:", summary.equity);
console.log("P&L:", summary.equity - summary.balance);
console.log("Margin %:", summary.margin_level);

// Current Positions
const positions = await api.get("/portfolio/positions");
positions.forEach((pos) => {
  const pnl = (pos.current_price - pos.entry_price) * pos.quantity;
  console.log(`${pos.symbol}: ${pnl}`);
});
```

---

## 💹 Get Market Data

```javascript
// Single symbol
const quote = await marketService.getQuotes(["AAPL"]);
console.log(quote[0].bid, quote[0].ask);

// Order book
const depth = await marketService.getDepth("AAPL", 10);
depth.bids.forEach(([price, size]) => {
  console.log(`BID ${price} x ${size}`);
});

// Candles
const candles = await marketService.getCandles("AAPL", "1m", 100);
candles.forEach((c) => {
  console.log(`${c.time}: O:${c.open} C:${c.close}`);
});

// Recent trades
const trades = await marketService.getTrades("AAPL", 50);
trades.forEach((t) => {
  console.log(`${t.side} ${t.size} @ ${t.price}`);
});
```

---

## ❌ Error Handling

```javascript
// API Errors
try {
  await api.post("/orders", data);
} catch (error) {
  if (error.response?.status === 400) {
    console.error("Invalid data:", error.response.data);
  } else if (error.response?.status === 401) {
    console.error("Not authenticated");
  } else if (error.response?.status === 403) {
    console.error("Insufficient margin");
  } else if (error.response?.status === 429) {
    console.error("Rate limited, wait:", error.response.headers["retry-after"]);
  } else {
    console.error("Unknown error:", error.message);
  }
}

// WebSocket Errors
websocketService.on("error", (error) => {
  console.error("WebSocket error:", error);
});

websocketService.on("disconnected", () => {
  console.log("Disconnected, will reconnect...");
});
```

---

## 🧪 Testing an Endpoint

```javascript
// In browser console
const token = localStorage.getItem("access_token");
const response = await fetch("http://localhost:8000/api/v1/orders", {
  headers: {
    Authorization: `Bearer ${token}`,
  },
});
const data = await response.json();
console.log(data);
```

---

## 🔍 Debugging Tips

```javascript
// Log all API requests
api.interceptors.request.use((config) => {
  console.log("API Request:", config.method.toUpperCase(), config.url);
  return config;
});

// Log all responses
api.interceptors.response.use((response) => {
  console.log("API Response:", response.status, response.config.url);
  return response;
});

// Check token
console.log("Token:", localStorage.getItem("access_token"));

// Check WebSocket status
console.log("Connected:", websocketService.isConnected);

// View API docs
window.open("http://localhost:8000/docs");
```

---

## 📱 Component Template

```javascript
import { useState, useEffect } from "react";
import { api } from "@/services/api";

export function MyComponent() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const load = async () => {
      try {
        const result = await api.get("/endpoint");
        setData(result);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;

  return <div>{/* Use data here */}</div>;
}
```

---

## 🚨 Common Issues & Fixes

| Issue                    | Fix                                                      |
| ------------------------ | -------------------------------------------------------- |
| 401 Unauthorized         | Check token: `localStorage.getItem('access_token')`      |
| CORS Error               | Check frontend origin in backend CORS config             |
| WebSocket Not Connecting | Check URL: should be `ws://` not `http://`               |
| Rate Limit Error         | Wait `Retry-After` seconds, reduce request frequency     |
| API Timeout              | Increase `VITE_API_TIMEOUT` in .env                      |
| Token Expired            | Refresh token automatic, but ensure refresh token exists |
| WebSocket Disconnect     | Automatic reconnect, check network/backend health        |

---

## 📚 More Information

- **Setup Guide**: See `FRONTEND_CONFIGURATION_GUIDE.md`
- **Component Specs**: See `FRONTEND_COMPONENT_ROADMAP.md`
- **Full Integration**: See `FRONTEND_INTEGRATION_COMPLETE.md`
- **API Docs**: http://localhost:8000/docs
- **Backend Code**: `backend/app/api/v1/`

---

## ✅ Before You Start

1. ✅ Backend running on `http://localhost:8000`
2. ✅ Frontend running on `http://localhost:5173`
3. ✅ npm dependencies installed
4. ✅ `.env` files configured
5. ✅ Can access `http://localhost:8000/docs`

---

**You're ready to build components! 🎉**

Start with the component roadmap and use these snippets as templates.
