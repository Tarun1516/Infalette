"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { platformApi } from "@/lib/api";

interface TenantRow {
  id: string;
  name: string;
  slug: string;
  plan?: string;
  status?: string;
  created_at?: string;
}

interface SubscriptionRow {
  id: string;
  tenant_id: string;
  plan_id?: string;
  status: string;
  current_period_end?: string;
}

interface PlanRow {
  slug: string;
  name: string;
  price_cents: number;
}

export default function DashboardPage() {
  const [tenants, setTenants] = useState<TenantRow[]>([]);
  const [subs, setSubs] = useState<SubscriptionRow[]>([]);
  const [plans, setPlans] = useState<PlanRow[]>([]);
  const [health, setHealth] = useState<any>(null);
  const [usersCount, setUsersCount] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [tenantsRes, subsRes, plansRes, healthRes, usersRes] = await Promise.all([
          platformApi.getTenants().catch(() => []),
          platformApi.getSubscriptions().catch(() => []),
          platformApi.getPlans().catch(() => []),
          platformApi.getHealth().catch(() => null),
          platformApi.getUsers().catch(() => []),
        ]);
        const tList = Array.isArray(tenantsRes) ? tenantsRes : tenantsRes.data || tenantsRes.items || [];
        const sList = Array.isArray(subsRes) ? subsRes : subsRes.data || subsRes.items || [];
        const pList = Array.isArray(plansRes) ? plansRes : plansRes.data || plansRes.items || [];
        setTenants(tList);
        setSubs(sList);
        setPlans(pList);
        setHealth(healthRes);
        setUsersCount(Array.isArray(usersRes) ? usersRes.length : 0);
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, []);

  const activeTenants = tenants.filter((t) => (t.status || "active") === "active").length;
  const activeSubs = subs.filter((s) => s.status === "active" || s.status === "trialing");

  // MRR estimate: sum of plan prices for active/trialing subs.
  // We need the plan slug from the plan_id; the platform/subscriptions
  // payload returns plan_id but not plan_slug, so we fall back to
  // matching plan_id against the plans list and unknown plans default to ₹0.
  const mrrCents = activeSubs.reduce((acc, s) => {
    const plan = plans.find((p: any) => p.id === s.plan_id);
    return acc + (plan?.price_cents || 0);
  }, 0);

  const recentSignups = [...tenants]
    .filter((t) => t.created_at)
    .sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""))
    .slice(0, 10);

  const fmtINR = (cents: number) => `₹${(cents / 100).toFixed(0)}`;

  const stats = [
    { label: "Total Tenants", value: String(tenants.length), sub: `${activeTenants} active` },
    { label: "Active Tenants", value: String(activeTenants), sub: `${tenants.length - activeTenants} other` },
    { label: "Total Users", value: usersCount == null ? "—" : String(usersCount), sub: "cross-tenant" },
    { label: "MRR (estimate)", value: fmtINR(mrrCents), sub: `${activeSubs.length} active sub(s)` },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Platform Dashboard</h1>
        <p className="text-sm text-gray-500">Tenants, subscriptions and system health at a glance</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {stats.map((s) => (
          <div key={s.label} className="bg-white p-5 rounded-lg shadow border">
            <h3 className="text-sm font-medium text-gray-500">{s.label}</h3>
            <p className="text-2xl font-bold mt-1">{loading ? "…" : s.value}</p>
            <p className="text-xs text-gray-400 mt-1">{s.sub}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow border p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold">Recent Tenants</h3>
            <Link href="/tenants" className="text-xs text-blue-600 hover:underline">
              View all →
            </Link>
          </div>
          {recentSignups.length === 0 ? (
            <p className="text-sm text-gray-400">No tenants yet</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {recentSignups.map((t) => (
                <li
                  key={t.id}
                  className="flex items-center justify-between border-b last:border-0 pb-2"
                >
                  <div>
                    <Link
                      href={`/tenants/${t.id}`}
                      className="font-medium hover:underline"
                    >
                      {t.name}
                    </Link>
                    <p className="text-xs text-gray-500 font-mono">{t.slug}</p>
                  </div>
                  <span className="text-xs text-gray-500">
                    {t.created_at ? new Date(t.created_at).toLocaleDateString() : "—"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="bg-white rounded-lg shadow border p-5">
          <h3 className="font-semibold mb-3">System Health</h3>
          {health ? (
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span>API</span>
                <span
                  className={
                    health.status === "healthy" ? "text-green-600 font-medium" : "text-amber-600"
                  }
                >
                  {health.status === "healthy" ? "✓ Healthy" : health.status || "—"}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Database</span>
                <span
                  className={
                    health.components?.database === "healthy"
                      ? "text-green-600 font-medium"
                      : "text-gray-500"
                  }
                >
                  {health.components?.database || "—"}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Redis</span>
                <span
                  className={
                    health.components?.redis === "healthy"
                      ? "text-green-600 font-medium"
                      : "text-gray-500"
                  }
                >
                  {health.components?.redis || "—"}
                </span>
              </div>
              <div className="pt-2 border-t">
                <Link
                  href="/health"
                  className="text-xs text-blue-600 hover:underline"
                >
                  Detailed health →
                </Link>
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-400">Health endpoint unreachable</p>
          )}
        </div>
      </div>

      <div className="bg-white rounded-lg shadow border p-5">
        <h3 className="font-semibold mb-3">Quick Actions</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Link href="/tenants" className="p-4 border rounded-lg hover:bg-gray-50 text-center">
            <p className="text-sm font-medium">Add Tenant</p>
            <p className="text-xs text-gray-500 mt-1">Onboard influencer</p>
          </Link>
          <Link href="/users" className="p-4 border rounded-lg hover:bg-gray-50 text-center">
            <p className="text-sm font-medium">View Users</p>
            <p className="text-xs text-gray-500 mt-1">Cross-tenant team</p>
          </Link>
          <Link href="/themes" className="p-4 border rounded-lg hover:bg-gray-50 text-center">
            <p className="text-sm font-medium">Theme Presets</p>
            <p className="text-xs text-gray-500 mt-1">Design tokens</p>
          </Link>
          <Link href="/integrations" className="p-4 border rounded-lg hover:bg-gray-50 text-center">
            <p className="text-sm font-medium">Integrations</p>
            <p className="text-xs text-gray-500 mt-1">Provider health</p>
          </Link>
        </div>
      </div>
    </div>
  );
}
