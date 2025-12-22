# Frontend Component Roadmap

## Overview
This document outlines the React components that need to be built to consume all Phase 2 backend APIs. The frontend has all the services in place; this describes what UI components are needed.

---

## Component Architecture

```
App
├── Layout
│   ├── Header (navigation, user menu)
│   ├── Sidebar (instrument selector, watchlist)
│   └── Footer (market status, time)
├── Pages
│   ├── Dashboard (portfolio summary, recent trades)
│   ├── Trading (order entry, order book, recent trades)
│   ├── Portfolio (positions, balance, margin info)
│   ├── Instruments (instrument search, specifications)
│   ├── Market (quotes, candles, depth)
│   └── Settlement (positions, pending settlements)
└── Components
    ├── Charts (price, volume, OHLC)
    ├── Forms (order entry, amendment)
    ├── Tables (positions, orders, trades)
    └── Alerts (notifications, warnings)
```

---

## Phase 3.1: Core Trading Interface

### 1. Order Entry Form Component
**Purpose**: Create buy/sell orders  
**Consumes**: `POST /orders`  
**Data**: symbol, side, quantity, price, type (MARKET/LIMIT), time_in_force

```jsx
// Components/OrderEntryForm.jsx
export function OrderEntryForm() {
  const [symbol, setSymbol] = useState('AAPL');
  const [side, setSide] = useState('BUY');
  const [quantity, setQuantity] = useState(100);
  const [price, setPrice] = useState(0);
  const [type, setType] = useState('MARKET');

  const handleSubmit = async (e) => {
    e.preventDefault();
    const order = await ordersService.createOrder({
      symbol, side, quantity, price, type,
      time_in_force: 'GTC'
    });
    // Show success notification
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* Inputs for symbol, side, quantity, price, type */}
      {/* Submit button */}
    </form>
  );
}
```

**Features**:
- ✓ Symbol autocomplete (uses instruments API)
- ✓ Side selector (BUY/SELL)
- ✓ Quantity input
- ✓ Price input (disabled for MARKET orders)
- ✓ Order type selector
- ✓ Validation
- ✓ Submit handling
- ✓ Error display

---

### 2. Order Book Component
**Purpose**: Display real-time order book  
**Consumes**: `GET /market/depth`, WebSocket `depth` channel  
**Data**: bids, asks, symbol

```jsx
// Components/OrderBook.jsx
export function OrderBook({ symbol }) {
  const [depth, setDepth] = useState(null);

  useEffect(() => {
    // Fetch initial depth
    const loadDepth = async () => {
      const data = await marketService.getDepth(symbol);
      setDepth(data);
    };
    loadDepth();

    // Subscribe to real-time updates
    websocketService.subscribe('depth', { instrument: symbol });
    websocketService.on('depth_update', (update) => {
      if (update.symbol === symbol) {
        setDepth(update);
      }
    });
  }, [symbol]);

  return (
    <div className="order-book">
      <div className="bids">
        {depth?.bids.map(([price, size]) => (
          <div key={price} className="bid">
            {price} x {size}
          </div>
        ))}
      </div>
      <div className="mid-price">
        {depth?.mid_price}
      </div>
      <div className="asks">
        {depth?.asks.map(([price, size]) => (
          <div key={price} className="ask">
            {price} x {size}
          </div>
        ))}
      </div>
    </div>
  );
}
```

**Features**:
- ✓ Display bids (red, descending)
- ✓ Display asks (green, ascending)
- ✓ Mid price indicator
- ✓ Real-time updates via WebSocket
- ✓ Spread calculation
- ✓ Color-coded size visualization
- ✓ Click to place order at price

---

### 3. Recent Trades Component
**Purpose**: Show recent market trades  
**Consumes**: `GET /market/trades`, WebSocket `trades` channel  
**Data**: symbol, price, size, side, timestamp

```jsx
// Components/RecentTrades.jsx
export function RecentTrades({ symbol, limit = 50 }) {
  const [trades, setTrades] = useState([]);

  useEffect(() => {
    const loadTrades = async () => {
      const data = await marketService.getTrades(symbol, limit);
      setTrades(data);
    };
    loadTrades();

    websocketService.subscribe('trades', { instrument: symbol });
    websocketService.on('trade', (trade) => {
      if (trade.symbol === symbol) {
        setTrades(prev => [trade, ...prev].slice(0, limit));
      }
    });
  }, [symbol]);

  return (
    <table>
      <thead>
        <tr>
          <th>Time</th>
          <th>Price</th>
          <th>Size</th>
          <th>Side</th>
        </tr>
      </thead>
      <tbody>
        {trades.map(trade => (
          <tr key={trade.id} className={trade.side.toLowerCase()}>
            <td>{new Date(trade.timestamp).toLocaleTimeString()}</td>
            <td>${trade.price}</td>
            <td>{trade.size}</td>
            <td>{trade.side}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

**Features**:
- ✓ Display last 50 trades
- ✓ Color code by side (BUY/SELL)
- ✓ Real-time updates
- ✓ Timestamp formatting
- ✓ Scrollable with max height

---

### 4. Price Chart Component
**Purpose**: Display price candles  
**Consumes**: `GET /market/candles`, WebSocket `candles` channel  
**Data**: symbol, timeframe, OHLCV

```jsx
// Components/PriceChart.jsx
import { LineChart, BarChart } from 'recharts';

export function PriceChart({ symbol, timeframe = '1m' }) {
  const [candles, setCandles] = useState([]);

  useEffect(() => {
    const loadCandles = async () => {
      const data = await marketService.getCandles(symbol, timeframe, 100);
      setCandles(data);
    };
    loadCandles();

    websocketService.subscribe('candles', { 
      instrument: symbol, 
      timeframe 
    });
    websocketService.on('candle', (candle) => {
      if (candle.symbol === symbol && candle.timeframe === timeframe) {
        setCandles(prev => {
          const updated = [...prev];
          updated[updated.length - 1] = candle; // Update last candle
          return updated;
        });
      }
    });
  }, [symbol, timeframe]);

  const chartData = candles.map(c => ({
    time: new Date(c.time).toLocaleTimeString(),
    open: c.open,
    high: c.high,
    low: c.low,
    close: c.close,
    volume: c.volume
  }));

  return (
    <div className="chart">
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="time" />
        <YAxis />
        <Tooltip />
        <Legend />
        <Line type="monotone" dataKey="close" stroke="#8884d8" />
      </LineChart>
      <BarChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="time" />
        <YAxis yAxisId="right" orientation="right" />
        <Tooltip />
        <Bar yAxisId="right" dataKey="volume" fill="#82ca9d" />
      </BarChart>
    </div>
  );
}
```

**Features**:
- ✓ Line chart for price (OHLC)
- ✓ Bar chart for volume
- ✓ Multiple timeframes (1m, 5m, 15m, 1h, 1d)
- ✓ Real-time candle updates
- ✓ Tooltip with details
- ✓ Zoom/pan capability (recharts)

---

## Phase 3.2: Portfolio Management

### 5. Portfolio Summary Component
**Purpose**: Display account overview  
**Consumes**: `GET /portfolio/summary`  
**Data**: balance, equity, P&L, margin_level

```jsx
// Components/PortfolioSummary.jsx
export function PortfolioSummary() {
  const [portfolio, setPortfolio] = useState(null);

  useEffect(() => {
    const loadPortfolio = async () => {
      const data = await api.get('/portfolio/summary');
      setPortfolio(data);
    };
    loadPortfolio();

    const interval = setInterval(loadPortfolio, 5000); // Refresh every 5s
    return () => clearInterval(interval);
  }, []);

  if (!portfolio) return <div>Loading...</div>;

  const pnl = portfolio.equity - portfolio.balance;
  const pnlPercent = (pnl / portfolio.balance) * 100;

  return (
    <div className="portfolio-summary">
      <div className="card">
        <label>Account Balance</label>
        <value>${portfolio.balance.toFixed(2)}</value>
      </div>
      
      <div className="card">
        <label>Total Equity</label>
        <value>${portfolio.equity.toFixed(2)}</value>
      </div>
      
      <div className={`card ${pnl >= 0 ? 'profit' : 'loss'}`}>
        <label>P&L</label>
        <value>${pnl.toFixed(2)} ({pnlPercent.toFixed(2)}%)</value>
      </div>
      
      <div className={`card ${portfolio.margin_level > 80 ? 'warning' : ''}`}>
        <label>Margin Used</label>
        <value>{portfolio.margin_level.toFixed(1)}%</value>
      </div>
      
      <div className="card">
        <label>Margin Available</label>
        <value>${portfolio.available_margin.toFixed(2)}</value>
      </div>
    </div>
  );
}
```

**Features**:
- ✓ Display balance, equity, P&L
- ✓ Color code P&L (green/red)
- ✓ Display margin metrics
- ✓ Warning when margin high
- ✓ Auto-refresh every 5 seconds

---

### 6. Positions Table Component
**Purpose**: List current positions  
**Consumes**: `GET /portfolio/positions`  
**Data**: symbol, quantity, price, P&L

```jsx
// Components/PositionsTable.jsx
export function PositionsTable() {
  const [positions, setPositions] = useState([]);

  useEffect(() => {
    const loadPositions = async () => {
      const data = await api.get('/portfolio/positions');
      setPositions(data);
    };
    loadPositions();

    const interval = setInterval(loadPositions, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <table className="positions-table">
      <thead>
        <tr>
          <th>Symbol</th>
          <th>Quantity</th>
          <th>Entry Price</th>
          <th>Current Price</th>
          <th>P&L</th>
          <th>P&L %</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {positions.map(pos => {
          const pnl = (pos.current_price - pos.entry_price) * pos.quantity;
          const pnlPercent = ((pos.current_price - pos.entry_price) / pos.entry_price) * 100;
          
          return (
            <tr key={pos.symbol} className={pnl >= 0 ? 'profit' : 'loss'}>
              <td>{pos.symbol}</td>
              <td>{pos.quantity}</td>
              <td>${pos.entry_price}</td>
              <td>${pos.current_price}</td>
              <td>${pnl.toFixed(2)}</td>
              <td>{pnlPercent.toFixed(2)}%</td>
              <td>
                <button onClick={() => closePosition(pos.symbol)}>Close</button>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
```

**Features**:
- ✓ List all positions
- ✓ Show entry and current prices
- ✓ Calculate P&L and percentage
- ✓ Color code by profit/loss
- ✓ Close position action
- ✓ Auto-refresh

---

## Phase 3.3: Order Management

### 7. Orders List Component
**Purpose**: Show all orders (open, filled, cancelled)  
**Consumes**: `GET /orders`, WebSocket `orders` channel  
**Data**: id, symbol, side, quantity, status, filled

```jsx
// Components/OrdersList.jsx
export function OrdersList() {
  const [orders, setOrders] = useState([]);
  const [filter, setFilter] = useState('OPEN');

  useEffect(() => {
    const loadOrders = async () => {
      const data = await ordersService.getOrders();
      setOrders(data);
    };
    loadOrders();

    websocketService.subscribe('orders');
    websocketService.on('order_update', (update) => {
      setOrders(prev => {
        const updated = [...prev];
        const idx = updated.findIndex(o => o.id === update.id);
        if (idx >= 0) {
          updated[idx] = update;
        } else {
          updated.push(update);
        }
        return updated;
      });
    });
  }, []);

  const filtered = orders.filter(o => o.status === filter);

  return (
    <div>
      <div className="filters">
        <button onClick={() => setFilter('OPEN')}>Open</button>
        <button onClick={() => setFilter('FILLED')}>Filled</button>
        <button onClick={() => setFilter('CANCELLED')}>Cancelled</button>
      </div>

      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Symbol</th>
            <th>Side</th>
            <th>Quantity</th>
            <th>Price</th>
            <th>Filled</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map(order => (
            <tr key={order.id}>
              <td>{order.id}</td>
              <td>{order.symbol}</td>
              <td className={order.side.toLowerCase()}>{order.side}</td>
              <td>{order.quantity}</td>
              <td>${order.price}</td>
              <td>{order.filled} / {order.quantity}</td>
              <td>{order.status}</td>
              <td>
                {order.status === 'OPEN' && (
                  <>
                    <button onClick={() => cancelOrder(order.id)}>Cancel</button>
                    <button onClick={() => amendOrder(order.id)}>Amend</button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

**Features**:
- ✓ List orders with filters
- ✓ Real-time status updates
- ✓ Cancel order action
- ✓ Amend order action
- ✓ Show fill percentage

---

### 8. Order Amendment Modal
**Purpose**: Modify open orders  
**Consumes**: `PATCH /orders/{id}`  
**Data**: quantity, price

```jsx
// Components/AmendOrderModal.jsx
export function AmendOrderModal({ order, onClose }) {
  const [quantity, setQuantity] = useState(order.quantity);
  const [price, setPrice] = useState(order.price);

  const handleSubmit = async () => {
    const amended = await ordersService.amendOrder(order.id, {
      quantity,
      price
    });
    onClose();
  };

  return (
    <modal>
      <h2>Amend Order {order.id}</h2>
      <input 
        type="number" 
        value={quantity} 
        onChange={e => setQuantity(e.target.value)} 
        label="New Quantity"
      />
      <input 
        type="number" 
        value={price} 
        onChange={e => setPrice(e.target.value)} 
        label="New Price"
      />
      <button onClick={handleSubmit}>Amend</button>
      <button onClick={onClose}>Cancel</button>
    </modal>
  );
}
```

**Features**:
- ✓ Modify quantity
- ✓ Modify price
- ✓ Validation
- ✓ Confirmation before submit
- ✓ Error handling

---

## Phase 3.4: Market Data

### 9. Instruments Search Component
**Purpose**: Find instruments  
**Consumes**: `GET /instruments`  
**Data**: symbol, name, specs

```jsx
// Components/InstrumentsSearch.jsx
export function InstrumentsSearch({ onSelect }) {
  const [search, setSearch] = useState('');
  const [results, setResults] = useState([]);

  const handleSearch = async (query) => {
    setSearch(query);
    if (query.length > 0) {
      const instruments = await instrumentsService.search(query);
      setResults(instruments);
    }
  };

  return (
    <div className="search">
      <input 
        type="text" 
        placeholder="Search instruments..."
        value={search}
        onChange={e => handleSearch(e.target.value)}
      />
      <div className="results">
        {results.map(instr => (
          <div 
            key={instr.symbol} 
            onClick={() => onSelect(instr.symbol)}
            className="result"
          >
            <strong>{instr.symbol}</strong>
            <span>{instr.name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

**Features**:
- ✓ Search by symbol/name
- ✓ Autocomplete suggestions
- ✓ Show instrument details
- ✓ Click to select

---

### 10. Market Quotes Component
**Purpose**: Display market data  
**Consumes**: `GET /market/quotes`, WebSocket `quotes` channel  
**Data**: symbol, bid, ask, last, volume

```jsx
// Components/MarketQuotes.jsx
export function MarketQuotes({ symbols }) {
  const [quotes, setQuotes] = useState({});

  useEffect(() => {
    const loadQuotes = async () => {
      const data = await marketService.getQuotes(symbols);
      setQuotes(data.reduce((acc, q) => {
        acc[q.symbol] = q;
        return acc;
      }, {}));
    };
    loadQuotes();

    websocketService.subscribe('quotes', { instruments: symbols });
    websocketService.on('quote', (quote) => {
      setQuotes(prev => ({
        ...prev,
        [quote.symbol]: quote
      }));
    });
  }, [symbols]);

  return (
    <div className="quotes">
      {symbols.map(symbol => {
        const quote = quotes[symbol];
        if (!quote) return null;

        return (
          <div key={symbol} className="quote-card">
            <div className="symbol">{symbol}</div>
            <div className="bid">{quote.bid}</div>
            <div className="ask">{quote.ask}</div>
            <div className="last">{quote.last}</div>
            <div className="spread">{(quote.ask - quote.bid).toFixed(4)}</div>
            <div className="volume">{quote.volume}</div>
          </div>
        );
      })}
    </div>
  );
}
```

**Features**:
- ✓ Display bid, ask, last
- ✓ Show volume
- ✓ Calculate spread
- ✓ Real-time updates
- ✓ Card-based layout

---

## Phase 3.5: Settlement & Admin

### 11. Settlement Positions Component
**Purpose**: View settled positions  
**Consumes**: `GET /settlement/summary`, `GET /settlement/positions`  
**Data**: symbol, quantity, value, status

```jsx
// Components/SettlementPositions.jsx
export function SettlementPositions() {
  const [positions, setPositions] = useState([]);

  useEffect(() => {
    const loadPositions = async () => {
      const data = await api.get('/settlement/positions');
      setPositions(data);
    };
    loadPositions();

    const interval = setInterval(loadPositions, 10000); // Refresh every 10s
    return () => clearInterval(interval);
  }, []);

  return (
    <table className="settlement-table">
      <thead>
        <tr>
          <th>Symbol</th>
          <th>Quantity</th>
          <th>Settlement Value</th>
          <th>Status</th>
          <th>Settlement Date</th>
        </tr>
      </thead>
      <tbody>
        {positions.map(pos => (
          <tr key={pos.symbol}>
            <td>{pos.symbol}</td>
            <td>{pos.quantity}</td>
            <td>${pos.settlement_value}</td>
            <td>{pos.status}</td>
            <td>{new Date(pos.settlement_date).toLocaleDateString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

**Features**:
- ✓ Show settled positions
- ✓ Display settlement values
- ✓ Show settlement status
- ✓ Display settlement dates

---

### 12. Admin Controls Component (if applicable)
**Purpose**: Administrative functions  
**Consumes**: `GET/POST /admin/*`  
**Data**: system settings, risk controls, surveillance

```jsx
// Components/AdminControls.jsx
export function AdminControls() {
  const [settings, setSettings] = useState(null);

  useEffect(() => {
    const loadSettings = async () => {
      const data = await api.get('/admin/settings');
      setSettings(data);
    };
    loadSettings();
  }, []);

  const handleUpdateRisk = async (newLimits) => {
    await api.post('/admin/risk-controls', newLimits);
  };

  return (
    <div className="admin-panel">
      <h2>Risk Controls</h2>
      <div>Max Position Size: {settings?.max_position_size}</div>
      <button onClick={() => handleUpdateRisk({ max_position_size: 1000000 })}>
        Update
      </button>
    </div>
  );
}
```

**Features**:
- ✓ View system settings
- ✓ Update risk controls
- ✓ Monitor surveillance

---

## Component Dependencies Map

```
App
├── AuthProvider (login/logout)
├── WebSocketProvider (real-time connection)
├── Layout
│   ├── Header
│   │   └── UserMenu
│   ├── Sidebar
│   │   └── InstrumentsSearch
│   └── Footer
└── Router
    ├── LoginPage
    ├── DashboardPage
    │   ├── PortfolioSummary
    │   ├── PositionsTable
    │   └── RecentTrades
    ├── TradingPage
    │   ├── InstrumentsSearch
    │   ├── OrderEntryForm
    │   ├── OrderBook
    │   ├── RecentTrades
    │   └── PriceChart
    ├── PortfolioPage
    │   ├── PortfolioSummary
    │   ├── PositionsTable
    │   └── OrdersList
    ├── MarketPage
    │   ├── MarketQuotes
    │   └── PriceChart
    └── SettlementPage
        └── SettlementPositions
```

---

## Implementation Checklist

### Phase 3.1: Trading (Priority: High)
- [ ] OrderEntryForm component
- [ ] OrderBook component  
- [ ] RecentTrades component
- [ ] PriceChart component
- [ ] TradingPage integration

### Phase 3.2: Portfolio (Priority: High)
- [ ] PortfolioSummary component
- [ ] PositionsTable component
- [ ] DashboardPage integration
- [ ] Auto-refresh mechanism

### Phase 3.3: Orders (Priority: Medium)
- [ ] OrdersList component
- [ ] AmendOrderModal component
- [ ] Order cancellation flow
- [ ] PortfolioPage integration

### Phase 3.4: Market Data (Priority: Medium)
- [ ] InstrumentsSearch component
- [ ] MarketQuotes component
- [ ] MarketPage integration
- [ ] Symbol selection/watchlist

### Phase 3.5: Settlement (Priority: Low)
- [ ] SettlementPositions component
- [ ] SettlementPage integration

### Phase 3.6: Admin (Priority: Low)
- [ ] AdminControls component
- [ ] Settings page
- [ ] Risk controls UI

---

## Backend API Readiness Verification

✅ All endpoints ready for frontend consumption:
- ✅ Authentication (register, login, refresh, logout, me)
- ✅ Instruments (list, get, stats)
- ✅ Orders (create, list, get, update, cancel, amend)
- ✅ Trades (list, get, statistics)
- ✅ Market Data (quotes, depth, candles, trades, WebSocket)
- ✅ Portfolio (summary, positions, balance, equity, margin, performance)
- ✅ Settlement (summary, positions, pending, statistics)
- ✅ Monitoring (health, metrics, dashboard)
- ✅ Admin (settings, risk controls, surveillance)

**Frontend services are fully configured and ready!** 🚀

---

## Next Steps

1. ✅ Backend APIs documented and ready
2. ✅ Frontend services configured (api.js, websocket.js, etc.)
3. ⏳ **Build Phase 3.1 components** (TradingPage priority)
4. ⏳ **Build Phase 3.2 components** (PortfolioPage)
5. ⏳ **Build Phase 3.3 components** (OrderList, Amendments)
6. ⏳ Integrate WebSocket real-time updates
7. ⏳ Add error handling and loading states
8. ⏳ Style components (CSS/Tailwind)
9. ⏳ Add unit tests
10. ⏳ Performance optimization and deployment

---

**The frontend is ready for Phase 3 component development!** 🎉
