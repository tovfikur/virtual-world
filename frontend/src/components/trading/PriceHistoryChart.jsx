/**
 * PriceHistoryChart Component
 * Displays interactive candlestick chart with volume for price history
 */

import { useEffect, useState, useMemo, useCallback } from "react";
import PropTypes from "prop-types";
import { historyAPI } from "../../services/history";

const TIMEFRAME_OPTIONS = [
  { value: "1m", label: "1 Min" },
  { value: "5m", label: "5 Min" },
  { value: "15m", label: "15 Min" },
  { value: "30m", label: "30 Min" },
  { value: "1h", label: "1 Hour" },
  { value: "4h", label: "4 Hours" },
  { value: "1d", label: "1 Day" },
];

const HOURS_OPTIONS = [
  { value: 1, label: "1H" },
  { value: 6, label: "6H" },
  { value: 24, label: "24H" },
  { value: 72, label: "3D" },
  { value: 168, label: "1W" },
  { value: 720, label: "30D" },
];

const formatNumber = (value, digits = 2) => {
  if (value === null || value === undefined) return "-";
  const num = Number(value);
  if (Number.isNaN(num) || !Number.isFinite(num)) return "-";
  return num.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
};

const formatTime = (timestamp) => {
  const date = new Date(timestamp);
  return date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });
};

const formatDate = (timestamp) => {
  const date = new Date(timestamp);
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
};

/**
 * Interactive Candlestick Chart with Volume
 */
const CandlestickChart = ({
  candles,
  height = 400,
  showVolume = true,
  onCandleHover,
}) => {
  const [hoveredIndex, setHoveredIndex] = useState(null);

  // Calculate all values first (before any early returns to follow hooks rules)
  const safeCandles = candles && candles.length > 0 ? candles : [];
  const hasData = safeCandles.length > 0;

  const chartHeight = showVolume ? height * 0.7 : height - 20;
  const volumeHeight = showVolume ? height * 0.25 : 0;
  const paddingX = 50;
  const paddingY = 20;
  const width = 800;

  // Calculate price range (with safe defaults)
  const highs = hasData
    ? safeCandles.map((c) => c.high ?? c.close ?? c.open ?? 0)
    : [0];
  const lows = hasData
    ? safeCandles.map((c) => c.low ?? c.close ?? c.open ?? 0)
    : [0];
  const volumes = hasData ? safeCandles.map((c) => c.volume ?? 0) : [0];

  const maxPrice = Math.max(...highs);
  const minPrice = Math.min(...lows);
  const maxVolume = Math.max(...volumes);

  const priceSpan = Math.max(maxPrice - minPrice, 0.01);
  const volumeSpan = Math.max(maxVolume, 1);

  const innerWidth = width - paddingX * 2;
  const barSpace = innerWidth / Math.max(safeCandles.length, 1);
  const barWidth = Math.max(3, Math.min(barSpace * 0.7, 12));

  const scaleY = (value) => {
    return (
      paddingY +
      chartHeight -
      paddingY * 2 -
      ((value - minPrice) / priceSpan) * (chartHeight - paddingY * 2)
    );
  };

  const scaleVolumeY = (value) => {
    const volTop = chartHeight + 10;
    const volBottom = chartHeight + volumeHeight - 5;
    return volBottom - (value / volumeSpan) * (volBottom - volTop);
  };

  // Generate price grid lines - must be called unconditionally (hooks rule)
  const priceGridLines = useMemo(() => {
    const lines = [];
    const step = priceSpan / 5;
    for (let i = 0; i <= 5; i++) {
      const price = minPrice + step * i;
      const y =
        paddingY +
        chartHeight -
        paddingY * 2 -
        ((price - minPrice) / priceSpan) * (chartHeight - paddingY * 2);
      lines.push({ price, y });
    }
    return lines;
  }, [minPrice, priceSpan, paddingY, chartHeight]);

  // Early return AFTER all hooks are called
  if (!hasData) {
    return (
      <div
        className="flex items-center justify-center text-gray-400 text-sm bg-gray-900/50 rounded"
        style={{ height }}
      >
        No price history data available
      </div>
    );
  }

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        style={{ height: `${height}px` }}
      >
        {/* Background */}
        <rect x="0" y="0" width={width} height={height} fill="#111827" rx="4" />

        {/* Price grid lines */}
        {priceGridLines.map((line, idx) => (
          <g key={`grid-${idx}`}>
            <line
              x1={paddingX}
              x2={width - paddingX}
              y1={line.y}
              y2={line.y}
              stroke="#374151"
              strokeWidth="0.5"
              strokeDasharray="4,4"
            />
            <text
              x={paddingX - 5}
              y={line.y + 4}
              fill="#9CA3AF"
              fontSize="10"
              textAnchor="end"
            >
              {formatNumber(line.price, 2)}
            </text>
          </g>
        ))}

        {/* Volume background */}
        {showVolume && (
          <rect
            x={paddingX}
            y={chartHeight + 5}
            width={innerWidth}
            height={volumeHeight - 5}
            fill="#1f2937"
            rx="2"
          />
        )}

        {/* Candles */}
        {safeCandles.map((candle, idx) => {
          const x = paddingX + idx * barSpace + barSpace / 2;
          const open = candle.open ?? candle.close ?? 0;
          const close = candle.close ?? candle.open ?? 0;
          const high = candle.high ?? Math.max(open, close);
          const low = candle.low ?? Math.min(open, close);
          const volume = candle.volume ?? 0;
          const bullish = close >= open;
          const isHovered = idx === hoveredIndex;

          const color = bullish ? "#10B981" : "#EF4444";
          const yOpen = scaleY(open);
          const yClose = scaleY(close);
          const yHigh = scaleY(high);
          const yLow = scaleY(low);
          const bodyTop = Math.min(yOpen, yClose);
          const bodyHeight = Math.max(Math.abs(yClose - yOpen), 1);

          return (
            <g
              key={idx}
              className="cursor-pointer"
              onMouseEnter={() => {
                setHoveredIndex(idx);
                onCandleHover?.(candle, idx);
              }}
              onMouseLeave={() => {
                setHoveredIndex(null);
                onCandleHover?.(null, null);
              }}
            >
              {/* Wick */}
              <line
                x1={x}
                x2={x}
                y1={yHigh}
                y2={yLow}
                stroke={color}
                strokeWidth={isHovered ? 2 : 1}
              />
              {/* Body */}
              <rect
                x={x - barWidth / 2}
                y={bodyTop}
                width={barWidth}
                height={bodyHeight}
                fill={bullish ? color : color}
                stroke={isHovered ? "#fff" : color}
                strokeWidth={isHovered ? 2 : 0.5}
                opacity={isHovered ? 1 : 0.9}
              />
              {/* Volume bar */}
              {showVolume && (
                <rect
                  x={x - barWidth / 2}
                  y={scaleVolumeY(volume)}
                  width={barWidth}
                  height={chartHeight + volumeHeight - 5 - scaleVolumeY(volume)}
                  fill={bullish ? "#10B981" : "#EF4444"}
                  opacity={isHovered ? 0.8 : 0.4}
                />
              )}
            </g>
          );
        })}

        {/* Time axis labels */}
        {safeCandles
          .filter(
            (_, idx) =>
              idx % Math.max(Math.floor(safeCandles.length / 6), 1) === 0
          )
          .map((candle, idx, arr) => {
            const realIdx =
              idx * Math.max(Math.floor(safeCandles.length / 6), 1);
            const x = paddingX + realIdx * barSpace + barSpace / 2;
            return (
              <text
                key={`time-${idx}`}
                x={x}
                y={height - 5}
                fill="#9CA3AF"
                fontSize="9"
                textAnchor="middle"
              >
                {formatTime(candle.timestamp)}
              </text>
            );
          })}

        {/* Volume label */}
        {showVolume && (
          <text x={paddingX} y={chartHeight + 15} fill="#6B7280" fontSize="10">
            Volume
          </text>
        )}
      </svg>
    </div>
  );
};

/**
 * Price History Stats Panel
 */
const PriceStats = ({ candles, currentCandle }) => {
  const stats = useMemo(() => {
    if (!candles || candles.length === 0) {
      return null;
    }

    const first = candles[0];
    const last = currentCandle || candles[candles.length - 1];
    const opens = candles.map((c) => c.open);
    const highs = candles.map((c) => c.high);
    const lows = candles.map((c) => c.low);
    const closes = candles.map((c) => c.close);
    const volumes = candles.map((c) => c.volume || 0);
    const tradeCounts = candles.map((c) => c.trade_count || 0);

    const change = last.close - first.open;
    const changePercent = first.open !== 0 ? (change / first.open) * 100 : 0;

    return {
      open: first.open,
      high: Math.max(...highs),
      low: Math.min(...lows),
      close: last.close,
      change,
      changePercent,
      totalVolume: volumes.reduce((a, b) => a + b, 0),
      totalTrades: tradeCounts.reduce((a, b) => a + b, 0),
      avgVolume: volumes.reduce((a, b) => a + b, 0) / volumes.length,
      vwap: last.vwap,
      candleCount: candles.length,
    };
  }, [candles, currentCandle]);

  if (!stats) {
    return null;
  }

  const isPositive = stats.change >= 0;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 p-4 bg-gray-800/50 rounded-lg border border-gray-700">
      <div>
        <p className="text-xs text-gray-500">Open</p>
        <p className="text-sm font-semibold text-gray-200">
          {formatNumber(stats.open)}
        </p>
      </div>
      <div>
        <p className="text-xs text-gray-500">High</p>
        <p className="text-sm font-semibold text-green-400">
          {formatNumber(stats.high)}
        </p>
      </div>
      <div>
        <p className="text-xs text-gray-500">Low</p>
        <p className="text-sm font-semibold text-red-400">
          {formatNumber(stats.low)}
        </p>
      </div>
      <div>
        <p className="text-xs text-gray-500">Close</p>
        <p className="text-sm font-semibold text-gray-200">
          {formatNumber(stats.close)}
        </p>
      </div>
      <div>
        <p className="text-xs text-gray-500">Change</p>
        <p
          className={`text-sm font-semibold ${
            isPositive ? "text-green-400" : "text-red-400"
          }`}
        >
          {isPositive ? "+" : ""}
          {formatNumber(stats.change)} ({formatNumber(stats.changePercent)}%)
        </p>
      </div>
      <div>
        <p className="text-xs text-gray-500">Volume</p>
        <p className="text-sm font-semibold text-blue-400">
          {formatNumber(stats.totalVolume, 0)}
        </p>
      </div>
      <div>
        <p className="text-xs text-gray-500">Total Trades</p>
        <p className="text-sm font-semibold text-purple-400">
          {stats.totalTrades}
        </p>
      </div>
      <div>
        <p className="text-xs text-gray-500">VWAP</p>
        <p className="text-sm font-semibold text-gray-200">
          {stats.vwap ? formatNumber(stats.vwap) : "-"}
        </p>
      </div>
      <div>
        <p className="text-xs text-gray-500">Candles</p>
        <p className="text-sm font-semibold text-gray-400">
          {stats.candleCount}
        </p>
      </div>
    </div>
  );
};

/**
 * Hovered Candle Info Tooltip
 */
const CandleTooltip = ({ candle }) => {
  if (!candle) return null;

  const isPositive = candle.close >= candle.open;

  return (
    <div className="absolute top-2 right-2 bg-gray-900 border border-gray-700 rounded-lg p-3 shadow-lg z-10">
      <p className="text-xs text-gray-400 mb-2">
        {new Date(candle.timestamp).toLocaleString()}
      </p>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <span className="text-gray-500">O:</span>{" "}
          <span className="font-semibold">{formatNumber(candle.open)}</span>
        </div>
        <div>
          <span className="text-gray-500">H:</span>{" "}
          <span className="text-green-400 font-semibold">
            {formatNumber(candle.high)}
          </span>
        </div>
        <div>
          <span className="text-gray-500">L:</span>{" "}
          <span className="text-red-400 font-semibold">
            {formatNumber(candle.low)}
          </span>
        </div>
        <div>
          <span className="text-gray-500">C:</span>{" "}
          <span
            className={`font-semibold ${
              isPositive ? "text-green-400" : "text-red-400"
            }`}
          >
            {formatNumber(candle.close)}
          </span>
        </div>
        <div className="col-span-2">
          <span className="text-gray-500">Vol:</span>{" "}
          <span className="text-blue-400 font-semibold">
            {formatNumber(candle.volume, 0)}
          </span>
          <span className="text-gray-500 ml-2">Trades:</span>{" "}
          <span className="text-purple-400 font-semibold">
            {candle.trade_count || 0}
          </span>
        </div>
      </div>
    </div>
  );
};

/**
 * Main Price History Chart Component
 */
function PriceHistoryChart({ instrumentId, symbol = "", height = 450 }) {
  const [candles, setCandles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [timeframe, setTimeframe] = useState("5m");
  const [hours, setHours] = useState(24);
  const [hoveredCandle, setHoveredCandle] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const loadPriceHistory = useCallback(async () => {
    if (!instrumentId) {
      setError("No instrument selected");
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const res = await historyAPI.getInstrumentPriceHistory(instrumentId, {
        timeframe,
        hours,
      });

      if (res.data && Array.isArray(res.data)) {
        // Validate and sanitize candle data
        const validCandles = res.data
          .filter((c) => {
            // Validate OHLCV data
            const hasTimestamp = c.timestamp;
            const hasValidPrices =
              typeof c.open === "number" &&
              typeof c.high === "number" &&
              typeof c.low === "number" &&
              typeof c.close === "number";
            const hasValidOHLC =
              c.high >= c.open &&
              c.high >= c.close &&
              c.low <= c.open &&
              c.low <= c.close;

            return hasTimestamp && hasValidPrices && hasValidOHLC;
          })
          .map((c) => ({
            ...c,
            volume: c.volume ?? 0,
            trade_count: c.trade_count ?? 0,
            vwap: c.vwap ?? null,
          }));

        setCandles(validCandles);

        if (validCandles.length === 0 && res.data.length > 0) {
          setError("Data validation failed - invalid OHLCV format");
        }
      } else {
        setCandles([]);
      }
    } catch (err) {
      console.error("Failed to load price history:", err);
      // Ensure error is always a string (not an object)
      const errorDetail = err.response?.data?.detail;
      const errorMessage =
        typeof errorDetail === "string"
          ? errorDetail
          : errorDetail?.message ||
            err.message ||
            "Failed to load price history";
      setError(String(errorMessage));
      setCandles([]);
    } finally {
      setLoading(false);
    }
  }, [instrumentId, timeframe, hours]);

  useEffect(() => {
    loadPriceHistory();
  }, [loadPriceHistory]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(loadPriceHistory, 30000);
    return () => clearInterval(interval);
  }, [autoRefresh, loadPriceHistory]);

  const handleCandleHover = (candle, idx) => {
    setHoveredCandle(candle);
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 shadow-lg">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-100">
            📊 Price History{" "}
            {symbol && <span className="text-blue-400">({symbol})</span>}
          </h3>
          <p className="text-xs text-gray-500 mt-1">
            OHLCV candlestick data with volume analysis
          </p>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Timeframe selector */}
          <div className="flex items-center gap-1">
            {TIMEFRAME_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setTimeframe(opt.value)}
                className={`px-2 py-1 text-xs rounded transition-colors ${
                  timeframe === opt.value
                    ? "bg-blue-600 text-white"
                    : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {/* Period selector */}
          <div className="flex items-center gap-1">
            {HOURS_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setHours(opt.value)}
                className={`px-2 py-1 text-xs rounded transition-colors ${
                  hours === opt.value
                    ? "bg-green-600 text-white"
                    : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {/* Auto-refresh toggle */}
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`px-2 py-1 text-xs rounded transition-colors ${
              autoRefresh
                ? "bg-green-600/20 text-green-400 border border-green-600"
                : "bg-gray-800 text-gray-400"
            }`}
          >
            {autoRefresh ? "🔄 Auto" : "⏸ Manual"}
          </button>

          {/* Refresh button */}
          <button
            onClick={loadPriceHistory}
            disabled={loading}
            className="px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded transition-colors disabled:opacity-50"
          >
            {loading ? "Loading..." : "Refresh"}
          </button>
        </div>
      </div>

      {/* Error display */}
      {error && (
        <div className="mb-4 p-3 bg-red-900/30 border border-red-700 rounded text-red-400 text-sm">
          ⚠️ {error}
        </div>
      )}

      {/* Stats panel */}
      <PriceStats candles={candles} currentCandle={hoveredCandle} />

      {/* Chart container */}
      <div className="relative mt-4">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-900/80 z-10 rounded">
            <div className="flex items-center gap-2 text-gray-400">
              <div className="animate-spin w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full" />
              Loading price history...
            </div>
          </div>
        )}

        <CandleTooltip candle={hoveredCandle} />

        <CandlestickChart
          candles={candles}
          height={height - 150}
          showVolume={true}
          onCandleHover={handleCandleHover}
        />
      </div>

      {/* Footer info */}
      <div className="mt-4 flex items-center justify-between text-xs text-gray-500">
        <span>
          {candles.length > 0
            ? `Showing ${candles.length} candles from ${formatDate(
                candles[0]?.timestamp
              )} to ${formatDate(candles[candles.length - 1]?.timestamp)}`
            : "No data available"}
        </span>
        <span>Last updated: {new Date().toLocaleTimeString()}</span>
      </div>
    </div>
  );
}

PriceHistoryChart.propTypes = {
  instrumentId: PropTypes.string.isRequired,
  symbol: PropTypes.string,
  height: PropTypes.number,
};

export default PriceHistoryChart;
