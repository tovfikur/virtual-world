import React from "react";

// Lightweight sparkline using inline SVG
export default function BiomeSparkline({
  points = [],
  width = 160,
  height = 48,
  color = "#38bdf8",
}) {
  if (!points.length) {
    return (
      <div className="h-12 w-full flex items-center justify-center text-xs text-gray-500">
        No data
      </div>
    );
  }

  const maxY = Math.max(...points.map((p) => p.price_bdt));
  const minY = Math.min(...points.map((p) => p.price_bdt));
  const range = maxY - minY || 1;

  const step = points.length > 1 ? width / (points.length - 1) : width;

  const path = points
    .map((p, idx) => {
      const x = idx * step;
      const y = height - ((p.price_bdt - minY) / range) * height;
      return `${idx === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full h-12"
      preserveAspectRatio="none"
    >
      <path d={path} fill="none" stroke={color} strokeWidth="2" />
    </svg>
  );
}
