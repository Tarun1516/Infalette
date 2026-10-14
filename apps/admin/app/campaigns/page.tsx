"use client";

import { toast } from "@/components/toaster";

import { Fragment, useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const base = API_URL.endsWith("/api/v1")
  ? API_URL
  : API_URL.replace(/\/$/, "") + "/api/v1";

async function req(path: string, init?: RequestInit) {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  const res = await fetch(base + path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {}
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}

const EMPTY_FORM = { name: "", source: "instagram", utm_source: "", utm_medium: "", utm_campaign: "", status: "active" };

function SkeletonRow() {
  return (
    <tr className="border-b">
      {[...Array(5)].map((_, i) => (
        <td key={i} className="p-3"><div className="h-4 bg-gray-200 rounded animate-pulse" /></td>
      ))}
    </tr>
  );
}

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [perf, setPerf] = useState<Record<string, any>>({});
  const [perfLoading, setPerfLoading] = useState<string | null>(null);

  const fetchCampaigns = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await req("/campaigns");
      setCampaigns(Array.isArray(data) ? data : []);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCampaigns();
  }, []);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await req("/campaigns", {
        method: "POST",
        body: JSON.stringify({
          name: form.name,
          source: form.source,
          utm_source: form.utm_source || null,
          utm_medium: form.utm_medium || null,
          utm_campaign: form.utm_campaign || null,
          status: form.status,
        }),
      });
      setForm({ ...EMPTY_FORM });
      fetchCampaigns();
    } catch (e: any) {
      toast({ kind: "error", title: "Something went wrong", description: e.message });
    }
  };

  const toggleStatus = async (c: any) => {
    const next = c.status === "active" ? "paused" : "active";
    try {
      await req(`/campaigns/${c.id}`, { method: "PATCH", body: JSON.stringify({ status: next }) });
      fetchCampaigns();
    } catch (e: any) {
      toast({ kind: "error", title: "Something went wrong", description: e.message });
    }
  };

  const remove = async (id: string) => {
    if (!confirm("Delete this campaign?")) return;
    try {
      await req(`/campaigns/${id}`, { method: "DELETE" });
      if (expandedId === id) {
        setExpandedId(null);
      }
      fetchCampaigns();
    } catch (e: any) {
      toast({ kind: "error", title: "Something went wrong", description: e.message });
    }
  };

  const viewPerformance = async (id: string) => {
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(id);
    setPerfLoading(id);
    try {
      const data = await req(`/campaigns/${id}/performance`);
      setPerf((prev) => ({ ...prev, [id]: data }));
    } catch (e: any) {
      setPerf((prev) => ({ ...prev, [id]: { error: e.message } }));
    } finally {
      setPerfLoading(null);
    }
  };

  const statusColor = (s: string) => {
    switch (s) {
      case "active":
        return "bg-green-100 text-green-700";
      case "paused":
        return "bg-amber-100 text-amber-700";
      case "archived":
        return "bg-gray-100 text-gray-600";
      default:
        return "bg-gray-100 text-gray-600";
    }
  };

  const total = campaigns.length;
  const activeCount = campaigns.filter((c) => c.status === "active").length;

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Campaigns</h1>
        <p className="text-xs text-gray-500">UTM-attributed marketing campaigns (Instagram / WhatsApp / website) linked to lead and order performance.</p>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <div className="bg-white rounded-lg shadow border p-4">
          <div className="text-xs text-gray-500 uppercase">Total Campaigns</div>
          <div className="text-2xl font-bold">{total}</div>
        </div>
        <div className="bg-white rounded-lg shadow border p-4">
          <div className="text-xs text-gray-500 uppercase">Active</div>
          <div className="text-2xl font-bold text-green-600">{activeCount}</div>
        </div>
      </div>

      <form onSubmit={create} className="bg-white p-5 rounded-lg shadow border flex flex-col gap-3">
        <div className="grid md:grid-cols-3 gap-3">
          <input placeholder="Campaign name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="border rounded-lg px-3 py-2 text-sm" required />
          <select value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} className="border rounded-lg px-3 py-2 text-sm bg-white">
            <option value="instagram">instagram</option>
            <option value="whatsapp">whatsapp</option>
            <option value="website">website</option>
          </select>
          <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} className="border rounded-lg px-3 py-2 text-sm bg-white">
            <option value="active">active</option>
            <option value="paused">paused</option>
            <option value="archived">archived</option>
          </select>
        </div>
        <div className="grid md:grid-cols-3 gap-3">
          <input placeholder="utm_source (e.g. bio)" value={form.utm_source} onChange={(e) => setForm({ ...form, utm_source: e.target.value })} className="border rounded-lg px-3 py-2 text-sm" />
          <input placeholder="utm_medium (e.g. social)" value={form.utm_medium} onChange={(e) => setForm({ ...form, utm_medium: e.target.value })} className="border rounded-lg px-3 py-2 text-sm" />
          <input placeholder="utm_campaign (e.g. launch_week)" value={form.utm_campaign} onChange={(e) => setForm({ ...form, utm_campaign: e.target.value })} className="border rounded-lg px-3 py-2 text-sm" />
        </div>
        <button type="submit" className="self-start bg-blue-600 text-white rounded-lg px-4 py-2 text-sm font-medium">Create Campaign</button>
      </form>

      <div className="bg-white rounded-lg shadow border overflow-hidden">
        {loading ? (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left p-3">Name</th>
                <th className="text-left p-3">Source</th>
                <th className="text-left p-3">Status</th>
                <th className="text-left p-3">Created</th>
                <th className="text-right p-3">Actions</th>
              </tr>
            </thead>
            <tbody>{[...Array(3)].map((_, i) => <SkeletonRow key={i} />)}</tbody>
          </table>
        ) : error ? (
          <div className="p-6 text-center space-y-2">
            <div className="text-sm text-red-600">{error}</div>
            <button onClick={fetchCampaigns} className="text-xs bg-blue-600 text-white rounded-lg px-3 py-1.5">Retry</button>
          </div>
        ) : campaigns.length === 0 ? (
          <div className="p-8 text-center text-sm text-gray-500">No campaigns yet. Create your first UTM campaign above.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left p-3">Name</th>
                  <th className="text-left p-3">Source</th>
                  <th className="text-left p-3">Status</th>
                  <th className="text-left p-3">Created</th>
                  <th className="text-right p-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {campaigns.map((c) => (
                  <Fragment key={c.id}>
                    <tr className="border-b">
                      <td className="p-3 font-medium">{c.name}</td>
                      <td className="p-3">{c.source || "—"}</td>
                      <td className="p-3">
                        <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${statusColor(c.status)}`}>{c.status}</span>
                      </td>
                      <td className="p-3 text-xs text-gray-500">{c.created_at ? new Date(c.created_at).toLocaleDateString() : "—"}</td>
                      <td className="p-3 text-right space-x-3 whitespace-nowrap">
                        <button onClick={() => viewPerformance(c.id)} className="text-xs text-blue-600 underline">
                          {expandedId === c.id ? "Hide perf" : "View perf"}
                        </button>
                        <button onClick={() => toggleStatus(c)} className="text-xs text-amber-600 underline">
                          {c.status === "active" ? "Pause" : "Activate"}
                        </button>
                        <button onClick={() => remove(c.id)} className="text-xs text-red-600 underline">Delete</button>
                      </td>
                    </tr>
                    {expandedId === c.id && (
                      <tr className="border-b bg-gray-50">
                        <td colSpan={5} className="p-4">
                          {perfLoading === c.id ? (
                            <div className="space-y-2 max-w-md">
                              <div className="h-4 bg-gray-200 rounded animate-pulse" />
                              <div className="h-4 bg-gray-200 rounded animate-pulse w-2/3" />
                              <div className="h-4 bg-gray-200 rounded animate-pulse w-1/2" />
                            </div>
                          ) : !perf[c.id] || perf[c.id].error ? (
                            <div className="flex items-center gap-3">
                              <span className="text-sm text-red-600">{perf[c.id]?.error || "Failed to load performance"}</span>
                              <button onClick={() => viewPerformance(c.id)} className="text-xs bg-blue-600 text-white rounded-lg px-3 py-1.5">Retry</button>
                            </div>
                          ) : (
                            <div className="text-sm grid md:grid-cols-2 gap-4">
                              <div>
                                <div className="font-medium mb-1">Leads by stage</div>
                                {Object.entries(perf[c.id].leads_by_stage || {}).length === 0 ? (
                                  <div className="text-gray-500">No leads attributed yet.</div>
                                ) : (
                                  <ul className="space-y-1">
                                    {Object.entries(perf[c.id].leads_by_stage).map(([stage, count]) => (
                                      <li key={stage} className="flex justify-between max-w-xs">
                                        <span className="capitalize">{String(stage).replace(/_/g, " ")}</span>
                                        <span className="font-mono">{String(count)}</span>
                                      </li>
                                    ))}
                                  </ul>
                                )}
                              </div>
                              <dl className="space-y-1">
                                <div className="flex justify-between max-w-xs"><dt>Total leads</dt><dd className="font-mono">{perf[c.id].total_leads ?? 0}</dd></div>
                                <div className="flex justify-between max-w-xs"><dt>Attributed orders</dt><dd className="font-mono">{perf[c.id].attributed_orders ?? 0}</dd></div>
                                <div className="flex justify-between max-w-xs"><dt>Revenue</dt><dd className="font-mono">₹{((perf[c.id].attributed_revenue_cents || 0) / 100).toFixed(2)}</dd></div>
                                <div className="flex justify-between max-w-xs"><dt>Conversion rate</dt><dd className="font-mono">{perf[c.id].conversion_rate ?? 0}%</dd></div>
                              </dl>
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
