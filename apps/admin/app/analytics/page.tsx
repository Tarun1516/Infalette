"use client";

import { useEffect, useState } from "react";
import { adminApi } from "@/lib/api";
import SalesLineChart from "@/components/charts/sales-line-chart";
import TopProductsBars from "@/components/charts/top-products-bars";
import ChannelDonut from "@/components/charts/channel-donut";
import SocialFunnel from "@/components/charts/social-funnel";

export interface DashboardData {
  total_sales_cents?: number;
  gross_sales?: number;
  gross_sales_cents?: number;
  net_sales_cents?: number;
  net_sales?: number;
  total_orders?: number;
  orders?: number;
  aov?: number;
  refunds?: number;
  refund_cents?: number;
  conversion_rate?: number;
  sales_over_time?: Array<{ date: string; value?: number; sales_cents?: number; orders?: number }>;
  top_products?: Array<{
    id?: string;
    product_id?: string;
    name?: string;
    product_name?: string;
    total_sold?: number;
    quantity?: number;
    revenue_cents?: number;
  }>;
  channel_attribution?:
    | Array<{ channel?: string; name?: string; orders?: number; count?: number; revenue_cents?: number }>
    | Record<string, any>;
  social_funnel?: {
    comment?: number;
    reply?: number;
    viewed?: number;
    checkout?: number;
    paid?: number;
    stages?: Array<{ stage: string; count: number }>;
  };
}

function formatMoney(cents?: number) {
  if (cents == null) return "—";
  return `₹${(cents / 100).toFixed(2)}`;
}

const PRIMARY = "#2563eb";
const TONES = ["#2563eb", "#7c3aed", "#db2777", "#f59e0b", "#10b981", "#0ea5e9", "#ef4444", "#6366f1"];

export default function AnalyticsPage() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await adminApi.getDashboardData(days);
        if (!cancelled) setData((res as DashboardData) || {});
      } catch (e: any) {
        if (!cancelled) setError(e.message || "Failed to load analytics");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [days]);

  const gross =
    data?.total_sales_cents ?? data?.gross_sales_cents ?? data?.gross_sales ?? 0;
  const net = data?.net_sales_cents ?? data?.net_sales ?? 0;
  const orders = data?.total_orders ?? data?.orders ?? 0;
  const refunds = data?.refunds ?? data?.refund_cents ? Math.round((data.refund_cents ?? 0) / 100) : 0;
  // aov is returned in rupees (route divides by 100), so multiply back to cents
  // for our money formatter.
  const aovCents =
    data?.aov != null
      ? Math.round(data.aov * 100)
      : orders > 0
        ? Math.round(net / orders)
        : 0;
  const conversion =
    data?.conversion_rate != null
      ? data.conversion_rate <= 1
        ? data.conversion_rate * 100
        : data.conversion_rate
      : null;

  const kpis = [
    { label: "Gross Sales", value: formatMoney(gross), accent: PRIMARY },
    { label: "Net Sales", value: formatMoney(net), accent: "#7c3aed" },
    { label: "Orders", value: String(orders), accent: "#10b981" },
    { label: "Refunds", value: String(refunds), accent: "#ef4444" },
    { label: "AOV", value: formatMoney(aovCents), accent: "#f59e0b" },
    {
      label: "Conversion",
      value: conversion != null ? `${conversion.toFixed(1)}%` : "—",
      accent: "#0ea5e9",
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold">Analytics</h1>
          <p className="text-sm text-gray-500">
            {loading ? "Loading…" : `Last ${days} days`}
          </p>
        </div>
        <div className="inline-flex border rounded-lg overflow-hidden bg-white">
          {[7, 30, 90].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-2 text-sm ${
                days === d
                  ? "bg-blue-600 text-white"
                  : "text-gray-700 hover:bg-gray-50"
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {kpis.map((k) => (
          <div
            key={k.label}
            className="bg-white rounded-2xl border shadow-sm p-4"
          >
            <p className="text-xs text-gray-500">{k.label}</p>
            <p className="text-lg font-bold mt-1" style={{ color: k.accent }}>
              {loading ? <span className="inline-block h-6 w-20 bg-gray-200 rounded animate-pulse" /> : k.value}
            </p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl border shadow-sm p-5">
          <h3 className="font-semibold mb-3">Sales over time</h3>
          {loading ? (
            <div className="h-48 bg-gray-50 rounded animate-pulse" />
          ) : (
            <SalesLineChart series={data?.sales_over_time} />
          )}
        </div>

        <div className="bg-white rounded-2xl border shadow-sm p-5">
          <h3 className="font-semibold mb-3">Channel attribution</h3>
          {loading ? (
            <div className="h-48 bg-gray-50 rounded animate-pulse" />
          ) : (
            <ChannelDonut data={data?.channel_attribution} tones={TONES} />
          )}
        </div>

        <div className="bg-white rounded-2xl border shadow-sm p-5">
          <h3 className="font-semibold mb-3">Top products</h3>
          {loading ? (
            <div className="h-48 bg-gray-50 rounded animate-pulse" />
          ) : (
            <TopProductsBars data={data?.top_products} />
          )}
        </div>

        <div className="bg-white rounded-2xl border shadow-sm p-5">
          <h3 className="font-semibold mb-3">Social funnel</h3>
          {loading ? (
            <div className="h-48 bg-gray-50 rounded animate-pulse" />
          ) : (
            <SocialFunnel data={data?.social_funnel} />
          )}
        </div>
      </div>
    </div>
  );
}
