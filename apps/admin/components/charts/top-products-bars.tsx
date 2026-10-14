"use client";

import { useMemo } from "react";

interface Bar {
  id?: string;
  product_id?: string;
  name?: string;
  product_name?: string;
  total_sold?: number;
  quantity?: number;
  revenue_cents?: number;
}

const TONES = ["#2563eb", "#7c3aed", "#db2777", "#f59e0b", "#10b981"];

export default function TopProductsBars({ data }: { data?: Bar[] }) {
  const rows = useMemo(() => {
    if (!data) return [];
    return data.slice(0, 8).map((b) => ({
      key: b.id || b.product_id || b.name || b.product_name || Math.random().toString(),
      name: b.name || b.product_name || "Product",
      sold: b.total_sold ?? b.quantity ?? 0,
      revenue: b.revenue_cents ?? 0,
    }));
  }, [data]);

  if (rows.length === 0) {
    return (
      <div className="h-48 flex items-center justify-center text-sm text-gray-400">
        No products sold in this window
      </div>
    );
  }

  const max = Math.max(...rows.map((r) => r.sold), 1);
  const barH = 18;
  const gap = 8;
  const totalH = rows.length * (barH + gap);
  const labelW = 110;
  const valueW = 64;
  const trackW = 300;
  const W = labelW + trackW + valueW + 16;

  return (
    <div className="w-full">
      <svg
        viewBox={`0 0 ${W} ${totalH}`}
        className="w-full"
        style={{ height: totalH }}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="Top products bar chart"
      >
        {rows.map((r, i) => {
          const y = i * (barH + gap);
          const w = (r.sold / max) * trackW;
          const tone = TONES[i % TONES.length];
          return (
            <g key={r.key}>
              <text
                x={0}
                y={y + barH * 0.7}
                fontSize="11"
                fill="#374151"
                textAnchor="start"
              >
                {r.name.length > 18 ? r.name.slice(0, 17) + "…" : r.name}
              </text>
              <rect
                x={labelW}
                y={y}
                width={trackW}
                height={barH}
                rx={3}
                fill="#f3f4f6"
              />
              <rect
                x={labelW}
                y={y}
                width={Math.max(2, w)}
                height={barH}
                rx={3}
                fill={tone}
              />
              <text
                x={labelW + trackW + 8}
                y={y + barH * 0.7}
                fontSize="11"
                fill="#111827"
                textAnchor="start"
                fontWeight="600"
              >
                {r.sold} sold
              </text>
              <text
                x={labelW + trackW + 8}
                y={y + barH * 0.7}
                fontSize="10"
                fill="#6b7280"
                textAnchor="start"
                transform={`translate(0, 12)`}
              >
                ₹{(r.revenue / 100).toFixed(0)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
