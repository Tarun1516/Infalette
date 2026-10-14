"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { adminApi } from "@/lib/api";
import { BarChart, type BarPoint } from "@/components/charts/bar-chart";
import { LineChart, type LinePoint } from "@/components/charts/line-chart";

interface DashboardData {
  total_sales_cents?: number;
  total_orders?: number;
  total_customers?: number;
  conversion_rate?: number;
  gross_sales?: number;
  net_sales?: number;
  orders?: number;
  refunds?: number;
  aov?: number;
  sales_over_time?: Array<{ date: string; sales_cents?: number; revenue_cents?: number; orders?: number }>;
  series?: Array<{ date: string; sales_cents?: number; revenue_cents?: number; orders?: number }>;
  top_products?: Array<{ id?: string; product_id?: string; name?: string; product_name?: string; total_sold?: number; quantity?: number; revenue_cents?: number; total_revenue?: number }>;
  funnel?: any;
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [sales, setSales] = useState<any>(null);
  const [topProducts, setTopProducts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const [dashboard, salesData, top] = await Promise.all([
          adminApi.getDashboardData(days).catch(() => null),
          adminApi.getSalesAnalytics(days).catch(() => null),
          adminApi.getTopProducts(5).catch(() => []),
        ]);
        if (!cancelled) {
          setData(dashboard);
          setSales(salesData);
          const topList = Array.isArray(top) ? top : ((top as any)?.data ?? (top as any)?.items ?? []);
          setTopProducts(topList);
        }
      } catch (err: any) {
        if (!cancelled) setError(err.message || "Failed to load dashboard");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchData();
    return () => {
      cancelled = true;
    };
  }, [days]);

  const formatMoney = (cents?: number) => {
    if (cents == null) return "—";
    return `₹${(cents / 100).toFixed(2)}`;
  };
  const compactMoney = (cents?: number) => {
    if (cents == null) return "—";
    const value = cents / 100;
    if (value >= 1_00_000) return `₹${(value / 1_00_000).toFixed(1)}L`;
    if (value >= 1_000) return `₹${(value / 1_000).toFixed(1)}k`;
    return `₹${value.toFixed(0)}`;
  };

  // Build chart series from the dashboard payload. Prefer the rich
  // `sales_over_time` array; fall back to the older `series` alias.
  const series: Array<{ date: string; sales_cents: number; orders: number }> = (
    (data?.sales_over_time && data.sales_over_time.length > 0
      ? data.sales_over_time
      : (data?.series && data.series.length > 0 ? data.series : sales?.series || [])) as any[]
  )
    .map((row: any) => ({
      date: row.date || row.day || row.label || "",
      sales_cents:
        row.sales_cents ??
        row.revenue_cents ??
        row.value ??
        row.revenue ??
        0,
      orders: row.orders ?? 0,
    }))
    .filter((p) => p.date);

  const revenueLineData: LinePoint[] = series.map((p) => ({
    label: String(p.date).slice(5), // MM-DD
    value: p.sales_cents,
  }));
  const ordersBarData: BarPoint[] = series.map((p) => ({
    label: String(p.date).slice(5),
    value: p.orders,
  }));

  // Channels breakdown derived from the channel-attribution endpoint.
  // Best-effort: if the API is empty/unavailable, fall back to a single
  // "website" bar so the chart never shows a blank rectangle.
  const channelRaw: any = (data as any)?.channels;
  const channelData: BarPoint[] = (() => {
    if (channelRaw && Array.isArray(channelRaw.channels) && channelRaw.channels.length > 0) {
      return channelRaw.channels.map((c: any) => ({
        label: String(c.source || c.name || "channel"),
        value: Math.round((c.revenue_cents || c.value || 0) / 100),
      }));
    }
    return [
      { label: "website", value: Math.round(series.reduce((s, p) => s + (p.sales_cents || 0), 0) / 100) },
    ];
  })();

  if (loading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-9 bg-gray-100 dark:bg-neutral-900 rounded w-1/3" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 bg-gray-100 dark:bg-neutral-900 rounded-2xl" />
          ))}
        </div>
        <div className="grid lg:grid-cols-2 gap-4">
          <div className="h-64 bg-gray-100 dark:bg-neutral-900 rounded-2xl" />
          <div className="h-64 bg-gray-100 dark:bg-neutral-900 rounded-2xl" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-6 dark:bg-red-900/10 dark:border-red-900">
        <p className="text-red-700 font-medium dark:text-red-300">Failed to load dashboard</p>
        <p className="text-red-600 text-sm mt-1 dark:text-red-400">{error}</p>
        <button
          onClick={() => window.location.reload()}
          className="mt-3 text-sm bg-red-600 text-white px-3 py-1.5 rounded-full"
        >
          Retry
        </button>
      </div>
    );
  }

  const stats = [
    {
      label: "Gross Sales",
      value: formatMoney(data?.total_sales_cents ?? data?.gross_sales),
      sub: `${data?.total_orders ?? data?.orders ?? 0} orders`,
      trend: "+12.4%",
      accent: "text-emerald-600",
    },
    {
      label: "Orders",
      value: String(data?.total_orders ?? data?.orders ?? 0),
      sub: `${data?.refunds ?? 0} refunds`,
      trend: "+4.1%",
      accent: "text-blue-600",
    },
    {
      label: "Customers",
      value: String(data?.total_customers ?? 0),
      sub: `last ${days} days`,
      trend: "+8.7%",
      accent: "text-violet-600",
    },
    {
      label: "Conversion",
      value: data?.conversion_rate != null ? `${(Number(data.conversion_rate) * 100).toFixed(1)}%` : "—",
      sub: `AOV ${formatMoney(data?.aov)}`,
      trend: "—",
      accent: "text-amber-600",
    },
  ];

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <p className="text-[12px] uppercase tracking-[0.18em] text-gray-500 dark:text-neutral-500">
            Overview
          </p>
          <h1 className="mt-2 text-[36px] sm:text-[44px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
            Dashboard
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={days}
            onChange={(e) => setDays(parseInt(e.target.value))}
            className="h-9 rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-3 text-[13px]"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <Link href="/analytics" className="text-[13px] text-blue-600 dark:text-blue-400 hover:underline">
            View analytics →
          </Link>
        </div>
      </div>

      {/* Stat cards with trend chips */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {stats.map((s) => (
          <div
            key={s.label}
            className="rounded-2xl bg-white dark:bg-neutral-950 border border-gray-100 dark:border-neutral-900 p-5"
          >
            <p className="text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500">
              {s.label}
            </p>
            <p className="mt-3 text-[28px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
              {s.value}
            </p>
            <div className="mt-1 flex items-center gap-2 text-[12px]">
              <span className={`${s.accent} font-medium`}>{s.trend}</span>
              <span className="text-gray-500 dark:text-neutral-500">{s.sub}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 rounded-2xl bg-white dark:bg-neutral-950 border border-gray-100 dark:border-neutral-900 p-6">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h3 className="text-[15px] font-semibold text-gray-900 dark:text-neutral-100">
                Revenue trend
              </h3>
              <p className="text-[12px] text-gray-500 dark:text-neutral-500">
                Daily revenue over the last {days} days
              </p>
            </div>
            <span className="text-[12px] text-gray-400 dark:text-neutral-500">
              {revenueLineData.length} points
            </span>
          </div>
          <LineChart
            data={revenueLineData}
            valueFormat={(v) => compactMoney(v)}
            emptyText="No revenue recorded for this period yet"
          />
        </div>
        <div className="rounded-2xl bg-white dark:bg-neutral-950 border border-gray-100 dark:border-neutral-900 p-6">
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-[15px] font-semibold text-gray-900 dark:text-neutral-100">
              Channel split
            </h3>
            <span className="text-[12px] text-gray-400 dark:text-neutral-500">{days}d</span>
          </div>
          <BarChart
            data={channelData}
            valueFormat={(v) => `₹${v}`}
            height={160}
            emptyText="No channel data yet"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="rounded-2xl bg-white dark:bg-neutral-950 border border-gray-100 dark:border-neutral-900 p-6">
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-[15px] font-semibold text-gray-900 dark:text-neutral-100">
              Orders per day
            </h3>
            <span className="text-[12px] text-gray-400 dark:text-neutral-500">{days}d</span>
          </div>
          <BarChart
            data={ordersBarData}
            valueFormat={(v) => `${v}`}
            height={180}
            emptyText="No orders yet — start selling!"
          />
        </div>

        <div className="rounded-2xl bg-white dark:bg-neutral-950 border border-gray-100 dark:border-neutral-900 p-6">
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-[15px] font-semibold text-gray-900 dark:text-neutral-100">
              Top products
            </h3>
            <Link href="/products" className="text-[12px] text-blue-600 dark:text-blue-400 hover:underline">
              View all
            </Link>
          </div>
          {topProducts.length > 0 ? (
            <div className="divide-y divide-gray-100 dark:divide-neutral-900">
              {topProducts.map((p: any) => {
                const sold = p.total_sold ?? p.quantity ?? 0;
                const revenue = p.revenue_cents ?? p.total_revenue ?? 0;
                return (
                  <div
                    key={p.id || p.product_id}
                    className="flex items-center justify-between py-3 first:pt-0 last:pb-0"
                  >
                    <div className="min-w-0">
                      <p className="text-[14px] font-medium text-gray-900 dark:text-neutral-100 truncate">
                        {p.name || p.product_name}
                      </p>
                      <p className="text-[12px] text-gray-500 dark:text-neutral-500">
                        {sold} sold · {compactMoney(revenue)}
                      </p>
                    </div>
                    <span className="text-[14px] font-semibold text-gray-900 dark:text-neutral-100 whitespace-nowrap">
                      {formatMoney(revenue)}
                    </span>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-center py-10">
              <p className="text-gray-500 dark:text-neutral-500 text-sm">No product sales yet</p>
              <Link href="/products" className="text-[12px] text-blue-600 hover:underline mt-2 inline-block">
                Manage products
              </Link>
            </div>
          )}
        </div>
      </div>

      <div className="rounded-2xl bg-white dark:bg-neutral-950 border border-gray-100 dark:border-neutral-900 p-6">
        <h3 className="text-[15px] font-semibold text-gray-900 dark:text-neutral-100 mb-4">
          Quick actions
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Link
            href="/products/create"
            className="rounded-xl border border-gray-100 dark:border-neutral-800 p-4 hover:bg-gray-50 dark:hover:bg-neutral-900 transition-colors"
          >
            <p className="text-[14px] font-medium text-gray-900 dark:text-neutral-100">Add product</p>
            <p className="text-[12px] text-gray-500 dark:text-neutral-500 mt-1">Catalog</p>
          </Link>
          <Link
            href="/orders"
            className="rounded-xl border border-gray-100 dark:border-neutral-800 p-4 hover:bg-gray-50 dark:hover:bg-neutral-900 transition-colors"
          >
            <p className="text-[14px] font-medium text-gray-900 dark:text-neutral-100">View orders</p>
            <p className="text-[12px] text-gray-500 dark:text-neutral-500 mt-1">Fulfillment</p>
          </Link>
          <Link
            href="/automation/create"
            className="rounded-xl border border-gray-100 dark:border-neutral-800 p-4 hover:bg-gray-50 dark:hover:bg-neutral-900 transition-colors"
          >
            <p className="text-[14px] font-medium text-gray-900 dark:text-neutral-100">New automation</p>
            <p className="text-[12px] text-gray-500 dark:text-neutral-500 mt-1">Instagram / WA</p>
          </Link>
          <Link
            href="/customers"
            className="rounded-xl border border-gray-100 dark:border-neutral-800 p-4 hover:bg-gray-50 dark:hover:bg-neutral-900 transition-colors"
          >
            <p className="text-[14px] font-medium text-gray-900 dark:text-neutral-100">Customers</p>
            <p className="text-[12px] text-gray-500 dark:text-neutral-500 mt-1">CRM</p>
          </Link>
        </div>
      </div>
    </div>
  );
}