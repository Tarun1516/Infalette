"use client";

/**
 * LineChart — small SVG line/area chart for trend panels on the
 * dashboard. Zero dependencies, theme-aware via currentColor.
 */
export type LinePoint = { label: string; value: number };

export function LineChart({
  data,
  height = 180,
  valueFormat,
  emptyText = "No data",
}: {
  data: LinePoint[];
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
  const min = Math.min(...data.map((d) => d.value), 0);
  const span = Math.max(max - min, 1);
  const xStep = data.length > 1 ? 100 / (data.length - 1) : 100;
  const padY = 18;
  const usable = height - padY * 2;

  const points = data.map((d, i) => {
    const x = i * xStep;
    const y = padY + usable - ((d.value - min) / span) * usable;
    return [x, y] as const;
  });
  const linePath = points
    .map(([x, y], i) => `${i === 0 ? "M" : "L"}${x},${y}`)
    .join(" ");
  const areaPath = `${linePath} L100,${height - padY} L0,${height - padY} Z`;

  return (
    <div className="w-full">
      <svg
        viewBox={`0 0 100 ${height}`}
        preserveAspectRatio="none"
        className="w-full text-gray-900 dark:text-neutral-100"
        style={{ height }}
        role="img"
        aria-label="Line chart"
      >
        <defs>
          <linearGradient id="lineArea" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="currentColor" stopOpacity="0.35" />
            <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
          </linearGradient>
        </defs>

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

        <path d={areaPath} fill="url(#lineArea)" className="text-blue-600 dark:text-blue-400" />
        <path
          d={linePath}
          fill="none"
          stroke="currentColor"
          className="text-blue-600 dark:text-blue-400"
          strokeWidth={0.7}
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
        {points.map(([x, y], i) => (
          <circle
            key={i}
            cx={x}
            cy={y}
            r={0.7}
            className="fill-blue-600 dark:fill-blue-400"
            vectorEffect="non-scaling-stroke"
          />
        ))}
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