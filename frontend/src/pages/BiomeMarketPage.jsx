import { useEffect, useMemo, useState } from "react";
import { biomeMarketAPI } from "../services/api";
import { wsService } from "../services/websocket";
import useAuthStore from "../stores/authStore";
import BiomeSparkline from "../components/BiomeSparkline";
import toast from "react-hot-toast";

const biomeList = [
  "ocean",
  "beach",
  "plains",
  "forest",
  "desert",
  "mountain",
  "snow",
];

export default function BiomeMarketPage() {
  const { user, isAuthenticated } = useAuthStore();
  const [markets, setMarkets] = useState([]);
  const [portfolio, setPortfolio] = useState(null);
  const [selectedBiome, setSelectedBiome] = useState("ocean");
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [buyAmount, setBuyAmount] = useState("");
  const [sellShares, setSellShares] = useState("");
  const [subscribed, setSubscribed] = useState(false);

  // Fetch initial data
  useEffect(() => {
    if (!isAuthenticated) return;
    loadAll();
  }, [isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated) return;
    fetchHistory(selectedBiome);
  }, [selectedBiome, isAuthenticated]);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [mRes, pRes] = await Promise.all([
        biomeMarketAPI.getMarkets(),
        biomeMarketAPI.portfolio(),
      ]);
      setMarkets(mRes.data.markets || mRes.data.data || mRes.data || []);
      setPortfolio(pRes.data);
    } catch (e) {
      toast.error("Failed to load biome markets");
    } finally {
      setLoading(false);
    }
  };

  const fetchHistory = async (biome) => {
    try {
      const res = await biomeMarketAPI.getPriceHistory(biome, 24);
      setHistory(res.data.history || []);
    } catch (e) {
      setHistory([]);
    }
  };

  // WebSocket subscriptions
  useEffect(() => {
    if (!isAuthenticated) return;

    // ensure socket connected (auth store already connects on login)
    const unsubMarketUpdate = wsService.on("biome_market_update", (msg) => {
      if (msg?.markets) setMarkets(msg.markets);
    });

    const unsubAttention = wsService.on("biome_attention_update", (msg) => {
      // optional surface attention in markets list
      if (!msg?.biome) return;
      setMarkets((prev) =>
        prev.map((m) =>
          m.biome === msg.biome
            ? { ...m, attention_score: msg.total_attention }
            : m
        )
      );
    });

    // subscribe to room
    if (!subscribed) {
      wsService.send("subscribe_biome_market", {});
      setSubscribed(true);
    }

    return () => {
      if (unsubMarketUpdate) unsubMarketUpdate();
      if (unsubAttention) unsubAttention();
    };
  }, [isAuthenticated, subscribed]);

  const selectedMarket = useMemo(
    () => markets.find((m) => m.biome === selectedBiome),
    [markets, selectedBiome]
  );

  const holding = useMemo(() => {
    if (!portfolio?.holdings) return null;
    return portfolio.holdings.find((h) => h.biome === selectedBiome) || null;
  }, [portfolio, selectedBiome]);

  const handleBuy = async () => {
    if (!buyAmount) return;
    try {
      await biomeMarketAPI.buy(selectedBiome, Number(buyAmount));
      toast.success("Buy executed");
      setBuyAmount("");
      await Promise.all([loadAll(), fetchHistory(selectedBiome)]);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Buy failed");
    }
  };

  const handleSell = async () => {
    if (!sellShares) return;
    try {
      await biomeMarketAPI.sell(selectedBiome, Number(sellShares));
      toast.success("Sell executed");
      setSellShares("");
      await Promise.all([loadAll(), fetchHistory(selectedBiome)]);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Sell failed");
    }
  };

  if (!isAuthenticated) {
    return <div className="p-6 text-white">Please log in.</div>;
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <div className="bg-gray-800 border-b border-gray-700 p-4 md:p-6">
        <h1 className="text-2xl md:text-3xl font-bold">Biome Market</h1>
        <p className="text-gray-400">
          Real-time biome trading powered by attention scores.
        </p>
      </div>

      <div className="max-w-6xl mx-auto p-4 md:p-6 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
            <p className="text-sm text-gray-400">Balance</p>
            <p className="text-2xl font-bold">
              {portfolio?.cash_balance_bdt ?? user?.balance_bdt ?? 0} BDT
            </p>
          </div>
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
            <p className="text-sm text-gray-400">Invested</p>
            <p className="text-2xl font-bold">
              {portfolio?.total_invested_bdt ?? 0} BDT
            </p>
          </div>
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
            <p className="text-sm text-gray-400">Current Value</p>
            <p className="text-2xl font-bold">
              {portfolio?.total_current_value_bdt ?? 0} BDT
            </p>
          </div>
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
            <p className="text-sm text-gray-400">Unrealized Gain</p>
            <p className="text-2xl font-bold">
              {portfolio?.total_unrealized_gain_bdt ?? 0} BDT
              <span className="text-sm text-gray-400 ml-2">
                {portfolio?.total_unrealized_gain_percent?.toFixed?.(2) ?? 0}%
              </span>
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 bg-gray-800 border border-gray-700 rounded-lg p-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold">Markets</h2>
              <select
                value={selectedBiome}
                onChange={(e) => setSelectedBiome(e.target.value)}
                className="bg-gray-700 border border-gray-600 rounded px-3 py-2"
              >
                {biomeList.map((b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </select>
            </div>

            {loading ? (
              <div className="text-gray-400">Loading...</div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {markets.map((m) => (
                  <div
                    key={m.biome}
                    className={`rounded-lg border ${
                      m.biome === selectedBiome
                        ? "border-blue-500"
                        : "border-gray-700"
                    } bg-gray-900 p-4`}
                    onClick={() => setSelectedBiome(m.biome)}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-gray-400">Biome</p>
                        <p className="text-lg font-semibold capitalize">
                          {m.biome}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm text-gray-400">Price</p>
                        <p className="text-xl font-bold">
                          {m.share_price_bdt.toFixed?.(2) ?? m.share_price_bdt}{" "}
                          BDT
                        </p>
                      </div>
                    </div>
                    <div className="mt-2 flex items-center justify-between text-sm text-gray-400">
                      <span>
                        Attention:{" "}
                        {m.attention_score?.toFixed?.(2) ?? m.attention_score}
                      </span>
                      <span>Cash: {m.market_cash_bdt}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-4">
            <h3 className="text-lg font-semibold">Trade {selectedBiome}</h3>
            <div className="space-y-2">
              <p className="text-sm text-gray-400">Buy (BDT)</p>
              <div className="flex gap-2">
                <input
                  type="number"
                  value={buyAmount}
                  onChange={(e) => setBuyAmount(e.target.value)}
                  className="flex-1 bg-gray-900 border border-gray-700 rounded px-3 py-2"
                />
                <button
                  onClick={handleBuy}
                  className="bg-blue-600 hover:bg-blue-700 rounded px-3 py-2 font-semibold"
                >
                  Buy
                </button>
              </div>
            </div>
            <div className="space-y-2">
              <p className="text-sm text-gray-400">Sell (shares)</p>
              <div className="flex gap-2">
                <input
                  type="number"
                  value={sellShares}
                  onChange={(e) => setSellShares(e.target.value)}
                  className="flex-1 bg-gray-900 border border-gray-700 rounded px-3 py-2"
                />
                <button
                  onClick={handleSell}
                  className="bg-amber-600 hover:bg-amber-700 rounded px-3 py-2 font-semibold"
                >
                  Sell
                </button>
              </div>
            </div>
            <div className="text-sm text-gray-300 space-y-1">
              <div>Shares owned: {holding?.shares?.toFixed?.(4) ?? 0}</div>
              <div>
                Avg buy: {holding?.average_buy_price_bdt?.toFixed?.(2) ?? 0} BDT
              </div>
              <div>Total invested: {holding?.total_invested_bdt ?? 0} BDT</div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 bg-gray-800 border border-gray-700 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-semibold">
                Price history ({selectedBiome})
              </h3>
              <span className="text-gray-400 text-sm">Last 24h</span>
            </div>
            <BiomeSparkline points={history} color="#22d3ee" />
          </div>

          <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
            <h3 className="text-lg font-semibold mb-2">Portfolio</h3>
            {portfolio?.holdings?.length ? (
              <div className="space-y-2 text-sm">
                {portfolio.holdings.map((h) => (
                  <div
                    key={h.biome}
                    className="flex items-center justify-between bg-gray-900 border border-gray-700 rounded px-3 py-2"
                  >
                    <div>
                      <p className="font-semibold capitalize">{h.biome}</p>
                      <p className="text-gray-400">
                        {h.shares?.toFixed?.(4)} shares
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-gray-300">
                        Invested: {h.total_invested_bdt} BDT
                      </p>
                      <p className="text-gray-400 text-xs">
                        Avg: {h.average_buy_price_bdt?.toFixed?.(2)} BDT
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 text-sm">No holdings yet.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
