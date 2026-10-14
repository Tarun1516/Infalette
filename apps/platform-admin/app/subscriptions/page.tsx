"use client";

import { toast } from "@/components/toaster";

import { useEffect, useState } from "react";
import { platformApi } from "@/lib/api";

const PLANS = [
  { slug: "store", name: "Store", price: "₹999/mo", features: ["Custom storefront & domain", "Products & inventory", "Cart & checkout", "Orders & refunds", "SEO markup", "Basic reports"] },
  { slug: "store_automation", name: "Store + Automation", price: "₹2499/mo", features: ["Everything in Store", "Instagram DM & comments", "WhatsApp commerce", "Automated checkout links", "Unified inbox"] },
  { slug: "store_automation_crm", name: "Store + Automation + CRM", price: "₹4999/mo", features: ["Everything +", "Full CRM & profiles", "Funnel & attribution", "Abandoned segments", "Advanced dashboard", "CSV & scheduled reports"] },
];

export default function SubscriptionsPage() {
  const [subscriptions, setSubscriptions] = useState<any[]>([]);
  const [plans, setPlans] = useState<any[]>(PLANS);
  const [tenants, setTenants] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [cancelling, setCancelling] = useState<string | null>(null);

  const tenantMap = new Map(tenants.map((t: any) => [t.id, t]));
  const planMap = new Map(plans.map((p: any) => [p.slug, p]));

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [subsRes, plansRes, tenantsRes] = await Promise.all([
          platformApi.getSubscriptions().catch(() => null),
          platformApi.getPlans().catch(() => null),
          platformApi.getTenants().catch(() => null),
        ]);
        if (subsRes) {
          const list = Array.isArray(subsRes) ? subsRes : subsRes.data || subsRes.items || [];
          setSubscriptions(list);
        }
        if (plansRes) {
          const plist = Array.isArray(plansRes) ? plansRes : plansRes.data || plansRes.items || [];
          if (plist.length) {
            setPlans(
              plist.map((p: any) => ({
                slug: p.slug,
                name: p.name,
                price: `₹${((p.price_cents ?? 0) / 100).toFixed(0)}/${p.interval || "mo"}`,
                features:
                  p.features_json && typeof p.features_json === "object"
                    ? Object.entries(p.features_json)
                        .filter(([, v]) => v)
                        .map(([k]) =>
                          k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
                        )
                    : PLANS.find((x) => x.slug === p.slug)?.features || [p.description || ""],
              })),
            );
          }
        }
        if (tenantsRes) {
          const tList = Array.isArray(tenantsRes) ? tenantsRes : tenantsRes.data || tenantsRes.items || [];
          setTenants(tList);
        }
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, []);

  const handleCancel = async (subId: string) => {
    if (!confirm("Cancel this subscription?")) return;
    setCancelling(subId);
    try {
      await platformApi.cancelSubscription(subId);
      const subsRes = await platformApi.getSubscriptions().catch(() => null);
      if (subsRes) {
        const list = Array.isArray(subsRes) ? subsRes : subsRes.data || subsRes.items || [];
        setSubscriptions(list);
      }
    } catch (e: any) {
      toast({ kind: "error", title: "Something went wrong", description: e.message || "Failed to cancel" });
    } finally {
      setCancelling(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Subscriptions & Plans</h1>
        <p className="text-sm text-gray-500">Feature flags and quotas — not three separate apps</p>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        {plans.map((p) => (
          <div key={p.slug} className="bg-white rounded-xl shadow border p-6 flex flex-col">
            <h3 className="font-bold">{p.name}</h3>
            <p className="text-2xl font-extrabold mt-1">{p.price}</p>
            <ul className="mt-4 space-y-1.5 flex-1">
              {p.features.map((f: string) => (
                <li key={f} className="text-xs text-gray-600 flex gap-2">
                  <span className="text-green-600">✓</span> {f}
                </li>
              ))}
            </ul>
            <button className="mt-4 w-full border rounded-lg py-2 text-sm font-medium hover:bg-gray-50" disabled>
              Managed via tenant plan
            </button>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-lg shadow border p-6">
        <h3 className="font-semibold mb-3">Active Subscriptions</h3>
        {loading ? (
          <p className="text-sm text-gray-400">Loading…</p>
        ) : subscriptions.length === 0 ? (
          <p className="text-sm text-gray-400">No subscriptions yet. Tenants are assigned a plan on creation.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left p-3 font-medium">Tenant</th>
                  <th className="text-left p-3 font-medium">Plan</th>
                  <th className="text-left p-3 font-medium">Status</th>
                  <th className="text-left p-3 font-medium">Next billing</th>
                  <th className="text-right p-3 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {subscriptions.map((s: any) => {
                  const tenant = tenantMap.get(s.tenant_id);
                  const plan = plans.find((p: any) => p.id === s.plan_id);
                  return (
                    <tr key={s.id} className="border-b">
                      <td className="p-3">
                        <div className="font-medium">{tenant?.name || "—"}</div>
                        <div className="text-xs text-gray-500 font-mono">
                          {String(s.tenant_id).slice(0, 8)}
                        </div>
                      </td>
                      <td className="p-3 text-xs">{plan?.name || s.plan_id || "—"}</td>
                      <td className="p-3">
                        <span
                          className={`px-2 py-0.5 rounded-full text-xs ${
                            s.status === "active" || s.status === "trialing"
                              ? "bg-green-100 text-green-700"
                              : "bg-gray-100 text-gray-600"
                          }`}
                        >
                          {s.status}
                        </span>
                      </td>
                      <td className="p-3 text-xs text-gray-500">
                        {s.current_period_end
                          ? new Date(s.current_period_end).toLocaleDateString()
                          : "—"}
                      </td>
                      <td className="p-3 text-right">
                        {s.status !== "canceled" && (
                          <button
                            onClick={() => handleCancel(s.id)}
                            disabled={cancelling === s.id}
                            className="text-xs text-red-600 hover:underline disabled:opacity-50"
                          >
                            {cancelling === s.id ? "Cancelling…" : "Cancel"}
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
