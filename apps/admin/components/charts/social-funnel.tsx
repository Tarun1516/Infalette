"use client";

import { useMemo } from "react";

interface FunnelData {
  comment?: number;
  reply?: number;
  viewed?: number;
  checkout?: number;
  paid?: number;
  stages?: Array<{ stage: string; count: number }>;
}

const STAGE_LABELS: Array<{ key: string; label: string; aliases: string[] }> = [
  { key: "comment", label: "Comment / DM", aliases: ["comment", "comments", "dm", "dms"] },
  { key: "reply", label: "Reply sent", aliases: ["reply", "replies"] },
  { key: "viewed", label: "Product viewed", aliases: ["viewed", "view", "views", "product_viewed"] },
  { key: "checkout", label: "Checkout created", aliases: ["checkout", "checkouts", "checkout_created"] },
  { key: "paid", label: "Paid", aliases: ["paid", "purchases"] },
];

export default function SocialFunnel({ data }: { data?: FunnelData }) {
  const stages = useMemo(() => {
    if (!data) return [];
    if (Array.isArray(data.stages) && data.stages.length > 0) {
      return STAGE_LABELS.map((s, i) => ({
        key: s.key,
        label: s.label,
        value: data.stages?.find((st) => {
          const stageKey = (st.stage || "").toLowerCase();
          return s.aliases.includes(stageKey) || s.key === stageKey;
        })?.count ?? data.stages?.[i]?.count ?? 0,
      }));
    }
    return STAGE_LABELS.map((s) => {
      let v: number | undefined;
      for (const alias of s.aliases) {
        const candidate = (data as any)[alias];
        if (typeof candidate === "number") {
          v = candidate;
          break;
        }
      }
      return { key: s.key, label: s.label, value: v ?? 0 };
    });
  }, [data]);

  if (stages.length === 0 || stages.every((s) => !s.value)) {
    return (
      <div className="h-48 flex items-center justify-center text-sm text-gray-400 text-center px-4">
        Social funnel data requires the Automation plan and recent Instagram/WhatsApp conversations.
      </div>
    );
  }

  const max = Math.max(...stages.map((s) => s.value), 1);
  const rowH = 30;
  const W = 360;
  const H = stages.length * (rowH + 6);
  const cx = W / 2;

  return (
    <div className="w-full">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        style={{ height: H }}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="Social funnel"
      >
        {stages.map((s, i) => {
          const ratio = s.value / max;
          const w = Math.max(40, ratio * W * 0.95);
          const y = i * (rowH + 6);
          const x = cx - w / 2;
          const color =
            i === stages.length - 1
              ? "#10b981"
              : i >= stages.length - 2
                ? "#2563eb"
                : i >= 2
                  ? "#7c3aed"
                  : "#a78bfa";
          return (
            <g key={s.key}>
              <text
                x={8}
                y={y + rowH * 0.65}
                fontSize="11"
                fill="#374151"
                fontWeight="500"
              >
                {s.label}
              </text>
              <rect
                x={x}
                y={y}
                width={w}
                height={rowH}
                rx={4}
                fill={color}
                opacity={0.85}
              />
              <text
                x={cx}
                y={y + rowH * 0.65}
                fontSize="11"
                fontWeight="700"
                fill="#fff"
                textAnchor="middle"
              >
                {s.value}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
