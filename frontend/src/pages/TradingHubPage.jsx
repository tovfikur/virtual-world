/**
 * Trading Hub Page - Single Entry Point for All Trading System
 * Unified trading system for users and admins
 * Combines: Exchange, Portfolio, and Admin Controls
 */

import { useState, useEffect } from "react";
import useAuthStore from "../stores/authStore";
import { historyAPI } from "../services/history";
import { instrumentsAPI } from "../services/instruments";
import OverviewRealtimeBoard from "../components/trading/OverviewRealtimeBoard";

// Import sub-components
import OrdersPageContent from "../components/trading/OrdersPageContent";
import PortfolioPageContent from "../components/trading/PortfolioPageContent";
import AdminTradingContent from "../components/trading/AdminTradingContent";
import PriceHistoryChart from "../components/trading/PriceHistoryChart";

const TABS = {
  OVERVIEW: "overview",
  EXCHANGE: "exchange",
  PORTFOLIO: "portfolio",
  PRICE_HISTORY: "price_history",
  ADMIN: "admin",
};

function TradingHubPage() {
  const { user } = useAuthStore();
  const [activeTab, setActiveTab] = useState(TABS.OVERVIEW);
  const [portfolio, setPortfolio] = useState(null);

  const isAdmin = user?.role === "admin";

  // Portfolio data is loaded by child components
  // No need to load it here

  useEffect(() => {
    const fetchSnapshot = async () => {
      try {
        const res = await historyAPI.getUserPortfolioSnapshots({ limit: 1 });
        const snap = res.data?.[0];
        if (snap) {
          setPortfolio({
            summary: {
              total_value_bdt: snap.total_equity,
              unrealized_pnl: snap.unrealized_pnl,
            },
            positions: [],
          });
        }
      } catch (error) {
        console.error("Failed to load portfolio snapshot", error);
      }
    };

    fetchSnapshot();
  }, []);

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      {/* Header */}
      <div className="border-b border-gray-700 bg-gray-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold">Trading System</h1>
              <p className="text-gray-400 text-sm mt-1">
                Unified trading hub for all market operations
              </p>
            </div>
            <div className="flex items-center space-x-4">
              <div className="text-right">
                <p className="text-sm text-gray-400">Balance</p>
                <p className="text-xl font-semibold text-green-400">
                  {user?.balance_bdt ?? 0} BDT
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="border-t border-gray-700">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex overflow-x-auto space-x-1 py-0">
              {/* Overview Tab */}
              <button
                onClick={() => setActiveTab(TABS.OVERVIEW)}
                className={`px-4 py-3 font-medium transition-all whitespace-nowrap border-b-2 ${
                  activeTab === TABS.OVERVIEW
                    ? "border-blue-500 text-blue-400"
                    : "border-transparent text-gray-400 hover:text-gray-300"
                }`}
              >
                📊 Overview
              </button>

              {/* Exchange Tab */}
              <button
                onClick={() => setActiveTab(TABS.EXCHANGE)}
                className={`px-4 py-3 font-medium transition-all whitespace-nowrap border-b-2 ${
                  activeTab === TABS.EXCHANGE
                    ? "border-blue-500 text-blue-400"
                    : "border-transparent text-gray-400 hover:text-gray-300"
                }`}
              >
                📈 Exchange
              </button>

              {/* Portfolio Tab */}
              <button
                onClick={() => setActiveTab(TABS.PORTFOLIO)}
                className={`px-4 py-3 font-medium transition-all whitespace-nowrap border-b-2 ${
                  activeTab === TABS.PORTFOLIO
                    ? "border-blue-500 text-blue-400"
                    : "border-transparent text-gray-400 hover:text-gray-300"
                }`}
              >
                💼 Portfolio
              </button>

              {/* Price History Tab */}
              <button
                onClick={() => setActiveTab(TABS.PRICE_HISTORY)}
                className={`px-4 py-3 font-medium transition-all whitespace-nowrap border-b-2 ${
                  activeTab === TABS.PRICE_HISTORY
                    ? "border-purple-500 text-purple-400"
                    : "border-transparent text-gray-400 hover:text-gray-300"
                }`}
              >
                📉 Price History
              </button>

              {/* Admin Tab (if admin) */}
              {isAdmin && (
                <button
                  onClick={() => setActiveTab(TABS.ADMIN)}
                  className={`px-4 py-3 font-medium transition-all whitespace-nowrap border-b-2 ${
                    activeTab === TABS.ADMIN
                      ? "border-yellow-500 text-yellow-400"
                      : "border-transparent text-gray-400 hover:text-gray-300"
                  }`}
                >
                  ⚙️ Admin Controls
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Content Area */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Overview Tab */}
        {activeTab === TABS.OVERVIEW && (
          <OverviewTab portfolio={portfolio} user={user} />
        )}

        {/* Exchange Tab */}
        {activeTab === TABS.EXCHANGE && <OrdersPageContent />}

        {/* Portfolio Tab */}
        {activeTab === TABS.PORTFOLIO && <PortfolioPageContent />}

        {/* Price History Tab */}
        {activeTab === TABS.PRICE_HISTORY && <PriceHistoryTab />}

        {/* Admin Controls Tab */}
        {activeTab === TABS.ADMIN && isAdmin && <AdminTradingContent />}
      </div>
    </div>
  );
}

/**
 * Overview Tab Component
 * Shows quick stats and realtime board
 */
function OverviewTab({ portfolio, user }) {
  return (
    <div className="space-y-6">
      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
          <p className="text-gray-400 text-sm mb-1">Total Balance</p>
          <p className="text-2xl font-bold text-green-400">
            {user?.balance_bdt ?? 0} BDT
          </p>
        </div>

        <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
          <p className="text-gray-400 text-sm mb-1">Portfolio Value</p>
          <p className="text-2xl font-bold text-blue-400">
            {portfolio?.summary?.total_value_bdt?.toFixed(2) ?? "0.00"} BDT
          </p>
        </div>

        <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
          <p className="text-gray-400 text-sm mb-1">Open Positions</p>
          <p className="text-2xl font-bold text-purple-400">
            {portfolio?.positions?.length ?? 0}
          </p>
        </div>

        <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
          <p className="text-gray-400 text-sm mb-1">Unrealized P/L</p>
          <p
            className={`text-2xl font-bold ${
              (portfolio?.summary?.unrealized_pnl ?? 0) >= 0
                ? "text-green-400"
                : "text-red-400"
            }`}
          >
            {portfolio?.summary?.unrealized_pnl?.toFixed(2) ?? "0.00"} BDT
          </p>
        </div>
      </div>

      <OverviewRealtimeBoard />
    </div>
  );
}

/**
 * Price History Tab Component
 * Shows interactive price history chart with instrument selector
 */
function PriceHistoryTab() {
  const [instruments, setInstruments] = useState([]);
  const [selectedInstrument, setSelectedInstrument] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadInstruments = async () => {
      try {
        setLoading(true);
        const res = await instrumentsAPI.list();
        const data = res.data || [];
        setInstruments(data);
        // Auto-select first instrument
        if (data.length > 0 && !selectedInstrument) {
          setSelectedInstrument(data[0]);
        }
      } catch (error) {
        console.error("Failed to load instruments:", error);
      } finally {
        setLoading(false);
      }
    };

    loadInstruments();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="flex items-center gap-2 text-gray-400">
          <div className="animate-spin w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full" />
          Loading instruments...
        </div>
      </div>
    );
  }

  if (instruments.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-400">No instruments available</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Instrument Selector */}
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">
              Select Instrument
            </label>
            <select
              value={selectedInstrument?.instrument_id || ""}
              onChange={(e) => {
                const inst = instruments.find(
                  (i) => i.instrument_id === e.target.value
                );
                setSelectedInstrument(inst);
              }}
              className="px-3 py-2 bg-gray-900 border border-gray-600 rounded text-gray-200 text-sm min-w-[200px]"
            >
              {instruments.map((inst) => (
                <option key={inst.instrument_id} value={inst.instrument_id}>
                  {inst.symbol} - {inst.name}
                </option>
              ))}
            </select>
          </div>

          {/* Quick selection buttons */}
          <div className="flex flex-wrap gap-2">
            {instruments.slice(0, 6).map((inst) => (
              <button
                key={inst.instrument_id}
                onClick={() => setSelectedInstrument(inst)}
                className={`px-3 py-1.5 text-xs rounded transition-colors ${
                  selectedInstrument?.instrument_id === inst.instrument_id
                    ? "bg-blue-600 text-white"
                    : "bg-gray-700 text-gray-300 hover:bg-gray-600"
                }`}
              >
                {inst.symbol}
              </button>
            ))}
          </div>

          {/* Selected instrument info */}
          {selectedInstrument && (
            <div className="ml-auto text-right">
              <p className="text-sm text-gray-400">Current Price</p>
              <p className="text-lg font-bold text-green-400">
                {Number(selectedInstrument.current_price || 0).toLocaleString(
                  undefined,
                  { minimumFractionDigits: 2 }
                )}{" "}
                BDT
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Price History Chart */}
      {selectedInstrument && (
        <PriceHistoryChart
          instrumentId={selectedInstrument.instrument_id}
          symbol={selectedInstrument.symbol}
          height={500}
        />
      )}
    </div>
  );
}

export default TradingHubPage;
