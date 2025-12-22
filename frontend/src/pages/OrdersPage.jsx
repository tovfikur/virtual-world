import { useEffect, useState } from "react";
import toast from "react-hot-toast";

import { ordersAPI } from "../services/orders";
import { instrumentsAPI } from "../services/instruments";
import { tradesAPI } from "../services/api";
import { marketAPI } from "../services/market";
import useAuthStore from "../stores/authStore";

const ORDER_TYPES = [
  "market",
  "limit",
  "stop",
  "stop_limit",
  "trailing_stop",
  "iceberg",
];

function OrdersPage() {
  const [orders, setOrders] = useState([]);
  const [trades, setTrades] = useState([]);
  const [instruments, setInstruments] = useState([]);
  const [marketStatus, setMarketStatus] = useState({ state: "open", reason: null });
  const { user } = useAuthStore();
  const isAdmin = user?.role === "admin";

  const [form, setForm] = useState({
    instrument_id: "",
    side: "buy",
    order_type: "limit",
    quantity: 1,
    price: 1,
    stop_price: "",
    trailing_offset: "",
    iceberg_visible: "",
    oco_group_id: "",
    time_in_force: "gtc",
  });

  const [instrumentForm, setInstrumentForm] = useState({
    symbol: "",
    name: "",
    asset_class: "equity",
    tick_size: 0.01,
    lot_size: 1,
    leverage_max: 1,
    is_margin_allowed: false,
    is_short_selling_allowed: false,
    status: "active",
  });

  const [filters, setFilters] = useState({
    instrument_id: "",
    side: "",
    status: "",
  });

  const loadData = async () => {
    try {
      const [o, i, t, m] = await Promise.all([
        ordersAPI.listOrders({
          instrument_id: filters.instrument_id || undefined,
          side: filters.side || undefined,
          status_filter: filters.status || undefined,
        }),
        instrumentsAPI.list(),
        tradesAPI.listTrades({ instrument_id: filters.instrument_id || undefined }),
        marketAPI.getStatus(),
      ]);
      setOrders(o.data || []);
      setInstruments(i.data || []);
      setTrades(t.data || []);
      setMarketStatus(m.data || { state: "open" });
    } catch (e) {
      toast.error("Failed to load exchange data");
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    try {
      await ordersAPI.placeOrder({
        instrument_id: form.instrument_id,
        side: form.side,
        order_type: form.order_type,
        quantity: Number(form.quantity),
        price:
          form.order_type === "limit" || form.order_type === "stop_limit"
            ? Number(form.price)
            : undefined,
        stop_price:
          form.order_type === "stop" ||
          form.order_type === "stop_limit" ||
          form.order_type === "trailing_stop"
            ? Number(form.stop_price)
            : undefined,
        trailing_offset: form.order_type === "trailing_stop" ? Number(form.trailing_offset) : undefined,
        iceberg_visible: form.order_type === "iceberg" ? Number(form.iceberg_visible) : undefined,
        oco_group_id: form.oco_group_id || undefined,
        time_in_force: form.time_in_force,
      });
      toast.success("Order placed");
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to place order");
    }
  };

  const cancel = async (orderId) => {
    try {
      await ordersAPI.cancelOrder(orderId);
      toast.success("Order cancelled");
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Cancel failed");
    }
  };

  const createInstrument = async (e) => {
    e.preventDefault();
    try {
      await instrumentsAPI.create({
        ...instrumentForm,
        tick_size: Number(instrumentForm.tick_size),
        lot_size: Number(instrumentForm.lot_size),
        leverage_max: Number(instrumentForm.leverage_max),
      });
      toast.success("Instrument created");
      setInstrumentForm({
        symbol: "",
        name: "",
        asset_class: "equity",
        tick_size: 0.01,
        lot_size: 1,
        leverage_max: 1,
        is_margin_allowed: false,
        is_short_selling_allowed: false,
        status: "active",
      });
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to create instrument");
    }
  };

  const updateMarketState = async (state) => {
    try {
      const res = await marketAPI.setStatus({ state });
      setMarketStatus(res.data);
      toast.success(`Market ${state}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to update market state");
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-2xl font-bold">Order Entry (Phase 2)</h1>
            <p className="text-sm text-gray-400">Advanced order types, market controls, and trades.</p>
          </div>
          <div className="text-sm">
            <span className="px-2 py-1 rounded-full border border-gray-700 bg-gray-800 mr-2">
              Market:{" "}
              <span
                className={`font-semibold ${
                  marketStatus.state === "open" ? "text-green-400" : "text-yellow-300"
                }`}
              >
                {marketStatus.state}
              </span>
            </span>
            {marketStatus.reason && <span className="text-xs text-gray-400">({marketStatus.reason})</span>}
          </div>
        </div>

        {isAdmin && (
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 flex flex-wrap gap-2 text-sm">
            <button onClick={() => updateMarketState("open")} className="px-3 py-1 rounded bg-green-700 hover:bg-green-600">
              Open
            </button>
            <button onClick={() => updateMarketState("halted")} className="px-3 py-1 rounded bg-yellow-700 hover:bg-yellow-600">
              Halt
            </button>
            <button onClick={() => updateMarketState("closed")} className="px-3 py-1 rounded bg-red-700 hover:bg-red-600">
              Close
            </button>
          </div>
        )}

        <form onSubmit={submit} className="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <label className="text-sm">
              Instrument
              <select
                className="mt-1 w-full rounded bg-gray-900 border border-gray-700 px-2 py-1"
                value={form.instrument_id}
                onChange={(e) => setForm({ ...form, instrument_id: e.target.value })}
                required
              >
                <option value="">Select</option>
                {instruments.map((inst) => (
                  <option key={inst.instrument_id} value={inst.instrument_id}>
                    {inst.symbol}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              Side
              <select
                className="mt-1 w-full rounded bg-gray-900 border border-gray-700 px-2 py-1"
                value={form.side}
                onChange={(e) => setForm({ ...form, side: e.target.value })}
              >
                <option value="buy">Buy</option>
                <option value="sell">Sell</option>
              </select>
            </label>
            <label className="text-sm">
              Type
              <select
                className="mt-1 w-full rounded bg-gray-900 border border-gray-700 px-2 py-1"
                value={form.order_type}
                onChange={(e) => setForm({ ...form, order_type: e.target.value })}
              >
                {ORDER_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {(form.order_type === "limit" || form.order_type === "stop_limit") && (
            <label className="text-sm">
              Price
              <input
                type="number"
                step="0.0001"
                className="mt-1 w-full rounded bg-gray-900 border border-gray-700 px-2 py-1"
                value={form.price}
                onChange={(e) => setForm({ ...form, price: e.target.value })}
                required
              />
            </label>
          )}
          {(form.order_type === "stop" ||
            form.order_type === "stop_limit" ||
            form.order_type === "trailing_stop") && (
            <label className="text-sm">
              Stop Price
              <input
                type="number"
                step="0.0001"
                className="mt-1 w-full rounded bg-gray-900 border border-gray-700 px-2 py-1"
                value={form.stop_price}
                onChange={(e) => setForm({ ...form, stop_price: e.target.value })}
                required={form.order_type !== "trailing_stop"}
              />
            </label>
          )}
          {form.order_type === "trailing_stop" && (
            <label className="text-sm">
              Trailing Offset
              <input
                type="number"
                step="0.0001"
                className="mt-1 w-full rounded bg-gray-900 border border-gray-700 px-2 py-1"
                value={form.trailing_offset}
                onChange={(e) => setForm({ ...form, trailing_offset: e.target.value })}
                required
              />
            </label>
          )}
          {form.order_type === "iceberg" && (
            <label className="text-sm">
              Iceberg Visible
              <input
                type="number"
                step="0.0001"
                className="mt-1 w-full rounded bg-gray-900 border border-gray-700 px-2 py-1"
                value={form.iceberg_visible}
                onChange={(e) => setForm({ ...form, iceberg_visible: e.target.value })}
                required
              />
            </label>
          )}
          <label className="text-sm">
            Quantity
            <input
              type="number"
              step="0.0001"
              className="mt-1 w-full rounded bg-gray-900 border border-gray-700 px-2 py-1"
              value={form.quantity}
              onChange={(e) => setForm({ ...form, quantity: e.target.value })}
              required
            />
          </label>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <label className="text-sm">
              Time In Force
              <select
                className="mt-1 w-full rounded bg-gray-900 border border-gray-700 px-2 py-1"
                value={form.time_in_force}
                onChange={(e) => setForm({ ...form, time_in_force: e.target.value })}
              >
                <option value="gtc">GTC</option>
                <option value="ioc">IOC</option>
                <option value="fok">FOK</option>
              </select>
            </label>
            <label className="text-sm">
              OCO Group (optional)
              <input
                type="text"
                className="mt-1 w-full rounded bg-gray-900 border border-gray-700 px-2 py-1"
                value={form.oco_group_id}
                onChange={(e) => setForm({ ...form, oco_group_id: e.target.value })}
              />
            </label>
          </div>
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-400">Supports market/limit/stop/stop-limit/trailing/iceberg.</div>
            <button
              type="submit"
              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 rounded text-sm font-medium"
            >
              Place Order
            </button>
          </div>
        </form>

        <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-3">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
            <h2 className="text-lg font-semibold">My Orders</h2>
            <div className="flex flex-wrap gap-2 text-sm">
              <select
                className="rounded bg-gray-900 border border-gray-700 px-2 py-1"
                value={filters.instrument_id}
                onChange={(e) => setFilters({ ...filters, instrument_id: e.target.value })}
              >
                <option value="">All Instruments</option>
                {instruments.map((inst) => (
                  <option key={inst.instrument_id} value={inst.instrument_id}>
                    {inst.symbol}
                  </option>
                ))}
              </select>
              <select
                className="rounded bg-gray-900 border border-gray-700 px-2 py-1"
                value={filters.side}
                onChange={(e) => setFilters({ ...filters, side: e.target.value })}
              >
                <option value="">All Sides</option>
                <option value="buy">Buy</option>
                <option value="sell">Sell</option>
              </select>
              <select
                className="rounded bg-gray-900 border border-gray-700 px-2 py-1"
                value={filters.status}
                onChange={(e) => setFilters({ ...filters, status: e.target.value })}
              >
                <option value="">All Statuses</option>
                <option value="pending">Pending</option>
                <option value="partial">Partial</option>
                <option value="filled">Filled</option>
                <option value="cancelled">Cancelled</option>
              </select>
              <button
                onClick={loadData}
                className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded text-sm font-medium"
              >
                Apply
              </button>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 border-b border-gray-700">
                  <th className="py-2 pr-3">ID</th>
                  <th className="py-2 pr-3">Symbol</th>
                  <th className="py-2 pr-3">Side</th>
                  <th className="py-2 pr-3">Type</th>
                  <th className="py-2 pr-3">Qty</th>
                  <th className="py-2 pr-3">Price</th>
                  <th className="py-2 pr-3">Status</th>
                  <th className="py-2 pr-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {orders.length === 0 && (
                  <tr>
                    <td className="py-3 text-gray-500" colSpan={8}>
                      No orders yet.
                    </td>
                  </tr>
                )}
                {orders.map((o) => (
                  <tr key={o.order_id} className="border-b border-gray-800">
                    <td className="py-2 pr-3">{o.order_id.slice(0, 8)}</td>
                    <td className="py-2 pr-3">
                      {instruments.find((i) => i.instrument_id === o.instrument_id)?.symbol || o.instrument_id}
                    </td>
                    <td className="py-2 pr-3 uppercase">{o.side}</td>
                    <td className="py-2 pr-3">{o.order_type}</td>
                    <td className="py-2 pr-3">{o.quantity}</td>
                    <td className="py-2 pr-3">{o.price ?? "-"}</td>
                    <td className="py-2 pr-3 capitalize">{o.status}</td>
                    <td className="py-2 pr-3 text-right">
                      <button
                        onClick={() => cancel(o.order_id)}
                        className="px-2 py-1 text-xs rounded bg-red-600 hover:bg-red-700"
                      >
                        Cancel
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {isAdmin && (
            <form onSubmit={createInstrument} className="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">Create Instrument</h2>
                <button type="submit" className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 rounded text-sm font-medium">
                  Create
                </button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <label className="text-sm">
                  Symbol
                  <input
                    className="mt-1 w-full rounded bg-gray-900 border border-gray-700 px-2 py-1 uppercase"
                    value={instrumentForm.symbol}
                    onChange={(e) => setInstrumentForm({ ...instrumentForm, symbol: e.target.value })}
                    required
                  />
                </label>
                <label className="text-sm">
                  Name
                  <input
                    className="mt-1 w-full rounded bg-gray-900 border border-gray-700 px-2 py-1"
                    value={instrumentForm.name}
                    onChange={(e) => setInstrumentForm({ ...instrumentForm, name: e.target.value })}
                    required
                  />
                </label>
                <label className="text-sm">
                  Asset Class
                  <select
                    className="mt-1 w-full rounded bg-gray-900 border border-gray-700 px-2 py-1"
                    value={instrumentForm.asset_class}
                    onChange={(e) => setInstrumentForm({ ...instrumentForm, asset_class: e.target.value })}
                  >
                    <option value="equity">Equity</option>
                    <option value="forex">Forex</option>
                    <option value="commodity">Commodity</option>
                    <option value="index">Index</option>
                    <option value="crypto">Crypto</option>
                    <option value="derivative">Derivative</option>
                  </select>
                </label>
                <label className="text-sm">
                  Tick Size
                  <input
                    type="number"
                    step="0.0001"
                    className="mt-1 w-full rounded bg-gray-900 border border-gray-700 px-2 py-1"
                    value={instrumentForm.tick_size}
                    onChange={(e) => setInstrumentForm({ ...instrumentForm, tick_size: e.target.value })}
                  />
                </label>
                <label className="text-sm">
                  Lot Size
                  <input
                    type="number"
                    step="0.0001"
                    className="mt-1 w-full rounded bg-gray-900 border border-gray-700 px-2 py-1"
                    value={instrumentForm.lot_size}
                    onChange={(e) => setInstrumentForm({ ...instrumentForm, lot_size: e.target.value })}
                  />
                </label>
                <label className="text-sm">
                  Leverage Max
                  <input
                    type="number"
                    step="0.1"
                    className="mt-1 w-full rounded bg-gray-900 border border-gray-700 px-2 py-1"
                    value={instrumentForm.leverage_max}
                    onChange={(e) => setInstrumentForm({ ...instrumentForm, leverage_max: e.target.value })}
                  />
                </label>
                <label className="text-sm flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={instrumentForm.is_margin_allowed}
                    onChange={(e) => setInstrumentForm({ ...instrumentForm, is_margin_allowed: e.target.checked })}
                  />
                  <span>Margin Allowed</span>
                </label>
                <label className="text-sm flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={instrumentForm.is_short_selling_allowed}
                    onChange={(e) => setInstrumentForm({ ...instrumentForm, is_short_selling_allowed: e.target.checked })}
                  />
                  <span>Short Selling Allowed</span>
                </label>
              </div>
            </form>
          )}

          <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Recent Trades</h2>
              <button onClick={loadData} className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded text-sm font-medium">
                Refresh
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-400 border-b border-gray-700">
                    <th className="py-2 pr-3">Price</th>
                    <th className="py-2 pr-3">Qty</th>
                    <th className="py-2 pr-3">Side</th>
                  </tr>
                </thead>
                <tbody>
                  {trades.length === 0 && (
                    <tr>
                      <td className="py-3 text-gray-500" colSpan={3}>
                        No trades yet.
                      </td>
                    </tr>
                  )}
                  {trades.map((t) => (
                    <tr key={t.trade_id} className="border-b border-gray-800">
                      <td className="py-2 pr-3">{t.price}</td>
                      <td className="py-2 pr-3">{t.quantity}</td>
                      <td className="py-2 pr-3">{t.buyer_id === user?.user_id ? "Buy" : "Sell"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default OrdersPage;
