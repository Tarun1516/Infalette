"use client";

/**
 * BarChart — minimal, dependency-free SVG bar chart for the admin
 * dashboard. Renders a series of values as vertical bars inside a
 * fixed-size SVG. Designed for the Apple-style admin look (hairline
 * grid, light/dark aware via currentColor).
 *
 * Usage:
 *   <BarChart
 *     data={[{label:'Mon', value:120}, {label:'Tue', value:80}, ...]}
 *     height={180}
 *     valueFormat={(v) => `₹${(v/100).toFixed(0)}`}
 *   />
 */
export type BarPoint = { label: string; value: number; sub?: string };

export function BarChart({
  data,
  height = 200,
  valueFormat,
  emptyText = "No data",
}: {
  data: BarPoint[];
  height?: number;
  valueFormat?: (v: number) => string;
  emptyText?: string;
}) {
  if (!data.length) {
    return (
      <div
        className="flex items-center justify-center text-sm text-gray-500 dark:text-neutral-500"
        style={{ height }}
      >
        {emptyText}
      </div>
    );
  }

  const max = Math.max(...data.map((d) => d.value), 1);
  const barWidth = 100 / data.length;
  const gap = Math.min(barWidth * 0.2, 6);
  const innerWidth = barWidth - gap;

  return (
    <div className="w-full">
      <svg
        viewBox={`0 0 100 ${height}`}
        preserveAspectRatio="none"
        className="w-full text-gray-900 dark:text-neutral-100"
        style={{ height }}
        role="img"
        aria-label="Bar chart"
      >
        {/* Hairline grid */}
        {[0.25, 0.5, 0.75].map((p) => (
          <line
            key={p}
            x1={0}
            x2={100}
            y1={height * p}
            y2={height * p}
            stroke="currentColor"
            strokeOpacity="0.08"
            strokeWidth={0.2}
          />
        ))}
        {data.map((d, i) => {
          const h = (d.value / max) * (height - 24);
          const x = i * barWidth + gap / 2;
          const y = height - 16 - h;
          return (
            <g key={i}>
              <rect
                x={x}
                y={y}
                width={innerWidth}
                height={Math.max(h, 0.5)}
                rx={0.6}
                className="fill-blue-600 dark:fill-blue-400"
                opacity="0.92"
              />
            </g>
          );
        })}
        {/* Baseline */}
        <line
          x1={0}
          x2={100}
          y1={height - 16}
          y2={height - 16}
          stroke="currentColor"
          strokeOpacity="0.15"
          strokeWidth={0.2}
        />
      </svg>
      <div
        className="mt-2 grid text-[10px] text-gray-500 dark:text-neutral-500"
        style={{ gridTemplateColumns: `repeat(${data.length}, minmax(0, 1fr))` }}
      >
        {data.map((d, i) => (
          <div key={i} className="text-center truncate">
            {d.label}
          </div>
        ))}
      </div>
      {valueFormat && (
        <div
          className="mt-1 grid text-[11px] text-gray-700 dark:text-neutral-300"
          style={{ gridTemplateColumns: `repeat(${data.length}, minmax(0, 1fr))` }}
        >
          {data.map((d, i) => (
            <div key={i} className="text-center truncate font-medium">
              {valueFormat(d.value)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}