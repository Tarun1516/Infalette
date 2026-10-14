"use client";

import { useMemo } from "react";

interface Slot {
  key: string;
  label: string;
  value: number;
  color: string;
}

export default function ChannelDonut({
  data,
  tones,
}: {
  data?: any;
  tones: string[];
}) {
  const slots: Slot[] = useMemo(() => {
    if (!data) return [];
    if (Array.isArray(data)) {
      return data.map((c: any, i: number) => ({
        key: c.channel || c.name || `ch-${i}`,
        label: c.channel || c.name || `Channel ${i + 1}`,
        value: c.revenue_cents ?? c.orders ?? c.count ?? 0,
        color: tones[i % tones.length],
      }));
    }
    if (typeof data === "object") {
      const arr = (data.channels || data.data || []) as any[];
      if (arr.length > 0) {
        return arr.map((c: any, i: number) => ({
          key: c.channel || c.name || `ch-${i}`,
          label: c.channel || c.name || `Channel ${i + 1}`,
          value: c.revenue_cents ?? c.orders ?? c.count ?? 0,
          color: tones[i % tones.length],
        }));
      }
      // object map { "instagram": 1234, "whatsapp": 567 }
      return Object.entries(data)
        .filter(([, v]) => typeof v === "number")
        .map(([k, v], i) => ({
          key: k,
          label: k,
          value: v as number,
          color: tones[i % tones.length],
        }));
    }
    return [];
  }, [data, tones]);

  if (slots.length === 0) {
    return (
      <div className="h-48 flex items-center justify-center text-sm text-gray-400">
        No channel data yet
      </div>
    );
  }

  const total = slots.reduce((s, r) => s + r.value, 0) || 1;

  const W = 220;
  const H = 200;
  const cx = W / 2;
  const cy = H / 2;
  const r = 80;
  const ir = 50;

  let cursor = -Math.PI / 2;
  const arcs = slots.map((s) => {
    const angle = (s.value / total) * Math.PI * 2;
    const start = cursor;
    const end = cursor + angle;
    cursor = end;
    return { ...s, start, end, angle };
  });

  const arcPath = (start: number, end: number) => {
    const large = end - start > Math.PI ? 1 : 0;
    const x1 = cx + r * Math.cos(start);
    const y1 = cy + r * Math.sin(start);
    const x2 = cx + r * Math.cos(end);
    const y2 = cy + r * Math.sin(end);
    const x3 = cx + ir * Math.cos(end);
    const y3 = cy + ir * Math.sin(end);
    const x4 = cx + ir * Math.cos(start);
    const y4 = cy + ir * Math.sin(start);
    return [
      `M${x1.toFixed(2)},${y1.toFixed(2)}`,
      `A${r},${r} 0 ${large} 1 ${x2.toFixed(2)},${y2.toFixed(2)}`,
      `L${x3.toFixed(2)},${y3.toFixed(2)}`,
      `A${ir},${ir} 0 ${large} 0 ${x4.toFixed(2)},${y4.toFixed(2)}`,
      "Z",
    ].join(" ");
  };

  return (
    <div className="flex flex-col md:flex-row gap-3 items-center">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-44 h-44"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="Channel attribution donut chart"
      >
        {arcs.map((a) => (
          <path
            key={a.key}
            d={arcPath(a.start, a.end)}
            fill={a.color}
            stroke="#fff"
            strokeWidth="1.5"
          >
            <title>
              {a.label}: {a.value} ({((a.value / total) * 100).toFixed(1)}%)
            </title>
          </path>
        ))}
        <text
          x={cx}
          y={cy - 4}
          textAnchor="middle"
          fontSize="11"
          fill="#6b7280"
        >
          Total
        </text>
        <text
          x={cx}
          y={cy + 12}
          textAnchor="middle"
          fontSize="14"
          fontWeight="700"
          fill="#111827"
        >
          {total >= 100 ? `${(total / 100).toFixed(0)}` : total.toFixed(0)}
        </text>
      </svg>
      <ul className="flex-1 space-y-1 text-xs">
        {arcs.map((a) => (
          <li key={a.key} className="flex items-center gap-2">
            <span
              className="h-2.5 w-2.5 rounded-full inline-block"
              style={{ background: a.color }}
            />
            <span className="font-medium">{a.label}</span>
            <span className="text-gray-500">
              {((a.value / total) * 100).toFixed(1)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
