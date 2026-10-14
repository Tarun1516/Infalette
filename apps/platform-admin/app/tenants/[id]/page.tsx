"use client";

import { toast } from "@/components/toaster";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { platformApi } from "@/lib/api";

interface Tenant {
  id: string;
  name: string;
  slug: string;
  plan?: string;
  plan_slug?: string;
  status?: string;
  created_at?: string;
  updated_at?: string;
}

interface Subscription {
  id: string;
  tenant_id: string;
  plan_id?: string;
  status: string;
  current_period_start?: string;
  current_period_end?: string;
  cancelled_at?: string;
}

interface Domain {
  id: string;
  domain: string;
  is_primary: boolean;
  verified: boolean;
  created_at?: string;
}

interface Plan {
  id: string;
  slug: string;
  name: string;
  price_cents: number;
}

export default function TenantDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params?.id as string;

  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [subs, setSubs] = useState<Subscription[]>([]);
  const [domains, setDomains] = useState<Domain[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAssign, setShowAssign] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<string>("");
  const [trialDays, setTrialDays] = useState<number>(0);
  const [assigning, setAssigning] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [t, s, d, p] = await Promise.all([
        platformApi.getTenant(id).catch((e: any) => {
          throw new Error(e.message || "Failed to load tenant");
        }),
        platformApi
          .getSubscriptions({ tenant_id: id })
          .catch(() => []),
        platformApi.getTenantDomains(id).catch(() => []),
        platformApi.getPlans().catch(() => []),
      ]);
      setTenant(t as Tenant);
      const sList = Array.isArray(s) ? s : s.data || s.items || [];
      const dList = Array.isArray(d) ? d : d.data || d.items || [];
      const pList = Array.isArray(p) ? p : p.data || p.items || [];
      setSubs(sList.filter((x: Subscription) => x.tenant_id === id));
      setDomains(dList);
      setPlans(pList);
      if (pList.length) setSelectedPlan(pList[0].slug);
    } catch (e: any) {
      setError(e.message || "Failed to load tenant detail");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (id) fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const handleAssign = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPlan) return;
    setAssigning(true);
    try {
      await platformApi.assignPlan(id, selectedPlan, trialDays);
      setShowAssign(false);
      await fetchData();
    } catch (err: any) {
      toast({ kind: "error", title: "Something went wrong", description: err.message || "Failed to assign plan" });
    } finally {
      setAssigning(false);
    }
  };

  const handleCancel = async (subId: string) => {
    if (!confirm("Cancel this subscription?")) return;
    try {
      await platformApi.cancelSubscription(subId);
      await fetchData();
    } catch (e: any) {
      toast({ kind: "error", title: "Something went wrong", description: e.message || "Failed to cancel" });
    }
  };

  if (loading)
    return <div className="p-12 text-center text-gray-500">Loading tenant…</div>;
  if (error || !tenant)
    return (
      <div className="p-8 text-center">
        <p className="text-red-600 text-sm">{error || "Tenant not found"}</p>
        <button
          onClick={() => router.push("/tenants")}
          className="mt-3 text-sm bg-gray-900 text-white px-4 py-2 rounded"
        >
          Back to tenants
        </button>
      </div>
    );

  const currentSub = subs.find((s) => s.status === "active" || s.status === "trialing");

  return (
    <div className="space-y-6">
      <div>
        <Link href="/tenants" className="text-xs text-blue-600 hover:underline">
          ← Tenants
        </Link>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mt-1">
          <div>
            <h1 className="text-2xl font-bold">{tenant.name}</h1>
            <p className="text-sm text-gray-500 font-mono">{tenant.slug}</p>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`px-2 py-0.5 rounded-full text-xs ${
                (tenant.status || "active") === "active"
                  ? "bg-green-100 text-green-700"
                  : "bg-gray-100 text-gray-600"
              }`}
            >
              {tenant.status || "active"}
            </span>
            <button
              onClick={() => setShowAssign(true)}
              className="bg-gray-900 text-white px-3 py-1.5 rounded text-sm"
            >
              Assign plan
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-lg shadow border">
          <p className="text-xs text-gray-500">Plan</p>
          <p className="text-sm font-bold mt-1">{tenant.plan || tenant.plan_slug || "—"}</p>
        </div>
        <div className="bg-white p-4 rounded-lg shadow border">
          <p className="text-xs text-gray-500">Status</p>
          <p className="text-sm font-bold mt-1">{tenant.status || "active"}</p>
        </div>
        <div className="bg-white p-4 rounded-lg shadow border">
          <p className="text-xs text-gray-500">Domains</p>
          <p className="text-sm font-bold mt-1">{domains.length}</p>
        </div>
        <div className="bg-white p-4 rounded-lg shadow border">
          <p className="text-xs text-gray-500">Created</p>
          <p className="text-sm font-bold mt-1">
            {tenant.created_at ? new Date(tenant.created_at).toLocaleDateString() : "—"}
          </p>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow border">
        <div className="p-4 border-b flex justify-between items-center">
          <h3 className="font-semibold">Subscription</h3>
          {currentSub && (
            <button
              onClick={() => handleCancel(currentSub.id)}
              className="text-xs text-red-600 hover:underline"
            >
              Cancel
            </button>
          )}
        </div>
        {subs.length === 0 ? (
          <div className="p-8 text-center">
            <p className="text-sm text-gray-500">No subscription yet</p>
            <button
              onClick={() => setShowAssign(true)}
              className="mt-3 text-sm bg-gray-900 text-white px-4 py-2 rounded"
            >
              Assign a plan
            </button>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left p-3 font-medium text-gray-600">Status</th>
                <th className="text-left p-3 font-medium text-gray-600">Period start</th>
                <th className="text-left p-3 font-medium text-gray-600">Period end</th>
                <th className="text-left p-3 font-medium text-gray-600">Cancelled</th>
              </tr>
            </thead>
            <tbody>
              {subs.map((s) => (
                <tr key={s.id} className="border-b">
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
                  <td className="p-3 text-xs">
                    {s.current_period_start
                      ? new Date(s.current_period_start).toLocaleDateString()
                      : "—"}
                  </td>
                  <td className="p-3 text-xs">
                    {s.current_period_end
                      ? new Date(s.current_period_end).toLocaleDateString()
                      : "—"}
                  </td>
                  <td className="p-3 text-xs">
                    {s.cancelled_at
                      ? new Date(s.cancelled_at).toLocaleDateString()
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="bg-white rounded-lg shadow border">
        <div className="p-4 border-b">
          <h3 className="font-semibold">Domains</h3>
        </div>
        {domains.length === 0 ? (
          <div className="p-8 text-center text-sm text-gray-500">
            No domains configured for this tenant
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left p-3 font-medium text-gray-600">Domain</th>
                <th className="text-left p-3 font-medium text-gray-600">Primary</th>
                <th className="text-left p-3 font-medium text-gray-600">Verified</th>
                <th className="text-left p-3 font-medium text-gray-600">Created</th>
              </tr>
            </thead>
            <tbody>
              {domains.map((d) => (
                <tr key={d.id} className="border-b">
                  <td className="p-3 font-mono text-xs">{d.domain}</td>
                  <td className="p-3 text-xs">
                    {d.is_primary ? (
                      <span className="px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">
                        primary
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="p-3 text-xs">
                    {d.verified ? (
                      <span className="text-green-600 font-medium">✓ verified</span>
                    ) : (
                      <span className="text-amber-600">pending</span>
                    )}
                  </td>
                  <td className="p-3 text-xs text-gray-500">
                    {d.created_at ? new Date(d.created_at).toLocaleDateString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="bg-white rounded-lg shadow border p-4 text-xs text-gray-500">
        <p>
          <span className="font-medium">Last activity:</span>{" "}
          {tenant.updated_at
            ? `record updated ${new Date(tenant.updated_at).toLocaleString()}`
            : "not exposed by the API"}
        </p>
      </div>

      {showAssign && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-lg w-full max-w-md">
            <div className="p-5 border-b flex justify-between items-center">
              <h2 className="font-semibold">Assign Plan</h2>
              <button
                onClick={() => setShowAssign(false)}
                className="text-gray-500 hover:text-gray-800 text-xl"
                aria-label="Close"
              >
                ×
              </button>
            </div>
            <form onSubmit={handleAssign} className="p-5 space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Plan</label>
                <select
                  value={selectedPlan}
                  onChange={(e) => setSelectedPlan(e.target.value)}
                  className="w-full border rounded p-2 text-sm bg-white"
                  required
                >
                  {plans.map((p) => (
                    <option key={p.slug} value={p.slug}>
                      {p.name} (₹{(p.price_cents / 100).toFixed(0)}/mo)
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Trial days
                </label>
                <input
                  type="number"
                  min={0}
                  max={90}
                  value={trialDays}
                  onChange={(e) => setTrialDays(parseInt(e.target.value || "0", 10))}
                  className="w-full border rounded p-2 text-sm"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAssign(false)}
                  className="px-4 py-2 text-sm border rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={assigning}
                  className="px-4 py-2 text-sm bg-gray-900 text-white rounded disabled:opacity-50"
                >
                  {assigning ? "Assigning…" : "Assign"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
