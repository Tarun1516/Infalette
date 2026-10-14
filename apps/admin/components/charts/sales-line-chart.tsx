"use client";

import { useMemo } from "react";

interface Point {
  date: string;
  value?: number;
  sales_cents?: number;
  orders?: number;
}

export default function SalesLineChart({ series }: { series?: Point[] }) {
  const points = useMemo(() => {
    if (!series || series.length === 0) return null;
    const data = series.map((p) => ({
      date: p.date,
      value: p.sales_cents ?? p.value ?? 0,
    }));
    return data;
  }, [series]);

  if (!points || points.length === 0) {
    return (
      <div className="h-48 flex items-center justify-center text-sm text-gray-400">
        No sales data for this period
      </div>
    );
  }

  const W = 560;
  const H = 200;
  const padL = 50;
  const padR = 16;
  const padT = 16;
  const padB = 30;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;

  const max = Math.max(...points.map((p) => p.value), 1);
  const min = 0;
  const range = max - min || 1;

  const xy = points.map((p, i) => {
    const x = padL + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW);
    const y = padT + innerH - ((p.value - min) / range) * innerH;
    return { x, y, value: p.value, date: p.date };
  });

  const path = xy
    .map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`)
    .join(" ");

  const area = `${path} L${xy[xy.length - 1].x.toFixed(1)},${(padT + innerH).toFixed(1)} L${xy[0].x.toFixed(1)},${(padT + innerH).toFixed(1)} Z`;

  const ticks = 4;
  const tickValues = Array.from({ length: ticks + 1 }, (_, i) => (max * i) / ticks);

  return (
    <div className="w-full">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-48"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="Sales over time line chart"
      >
        {/* Y grid lines + labels */}
        {tickValues.map((v, i) => {
          const y = padT + innerH - (v / range) * innerH;
          return (
            <g key={i}>
              <line
                x1={padL}
                x2={W - padR}
                y1={y}
                y2={y}
                stroke="#e5e7eb"
                strokeDasharray="3 3"
              />
              <text
                x={padL - 6}
                y={y + 3}
                fontSize="10"
                fill="#6b7280"
                textAnchor="end"
              >
                {formatTick(v)}
              </text>
            </g>
          );
        })}

        {/* X labels (first / middle / last) */}
        {[0, Math.floor(xy.length / 2), xy.length - 1].map((idx) => {
          if (idx < 0 || idx >= xy.length) return null;
          const p = xy[idx];
          return (
            <text
              key={idx}
              x={p.x}
              y={H - 8}
              fontSize="10"
              fill="#6b7280"
              textAnchor="middle"
            >
              {p.date?.slice(5) || ""}
            </text>
          );
        })}

        {/* Area fill */}
        <path d={area} fill="#2563eb" fillOpacity="0.08" />
        {/* Line */}
        <path d={path} fill="none" stroke="#2563eb" strokeWidth="2" />

        {/* Points */}
        {xy.map((p, i) => (
          <g key={i}>
            <circle cx={p.x} cy={p.y} r="3" fill="#fff" stroke="#2563eb" strokeWidth="2" />
            <title>{`${p.date}: ₹${(p.value / 100).toFixed(2)}`}</title>
          </g>
        ))}
      </svg>
    </div>
  );
}

function formatTick(v: number) {
  if (v >= 1_00_000) return `${(v / 1_00_000).toFixed(0)}L`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)}k`;
  return `${v.toFixed(0)}`;
}
