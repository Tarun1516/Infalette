"use client";

import { useEffect, useState } from "react";
import { platformApi } from "@/lib/api";

export default function IntegrationsPage() {
  const [integrations, setIntegrations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, any>>({});

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res: any = await platformApi.getIntegrations();
      const list = Array.isArray(res) ? res : res.data || res.items || [];
      setIntegrations(list);
    } catch (e: any) {
      setError(e.message || "Failed to load integrations");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleTest = async (id: string) => {
    setTesting(id);
    try {
      const result = await platformApi.testIntegration(id);
      setTestResults((r) => ({ ...r, [id]: { ok: true, ...result } }));
    } catch (e: any) {
      setTestResults((r) => ({ ...r, [id]: { ok: false, error: e.message } }));
    } finally {
      setTesting(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Platform Integrations</h1>
        <p className="text-sm text-gray-500">
          Razorpay / Stripe, Instagram, WhatsApp, Shipping, Email — per tenant
        </p>
      </div>

      <div className="grid md:grid-cols-4 gap-4">
        {[
          { name: "Razorpay", desc: "India linked accounts", match: (l: any[]) => l.filter((i) => i.provider === "razorpay").length },
          { name: "Stripe Connect", desc: "International", match: (l: any[]) => l.filter((i) => String(i.provider).includes("stripe")).length },
          { name: "Instagram", desc: "Graph API & webhooks", match: (l: any[]) => l.filter((i) => i.provider === "instagram").length },
          { name: "WhatsApp", desc: "Cloud API & Flows", match: (l: any[]) => l.filter((i) => i.provider === "whatsapp").length },
        ].map((p) => {
          const active = p.match(integrations);
          const status = active > 0 ? `${active} tenant${active > 1 ? "s" : ""} connected` : "available";
          return (
            <div key={p.name} className="bg-white rounded-lg shadow border p-4">
              <h3 className="font-semibold text-sm">{p.name}</h3>
              <p className="text-xs text-gray-500 mt-1">{p.desc}</p>
              <span
                className={`inline-flex mt-2 px-2 py-0.5 rounded-full text-xs ${
                  active > 0 ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"
                }`}
              >
                {status}
              </span>
            </div>
          );
        })}
      </div>

      <div className="bg-white rounded-lg shadow border overflow-hidden">
        <div className="p-4 border-b flex justify-between items-center">
          <h3 className="font-semibold">Tenant Integrations</h3>
          <span className="text-xs text-gray-500">{integrations.length} connection(s)</span>
        </div>
        {loading ? (
          <div className="p-12 text-center text-gray-500">Loading integrations…</div>
        ) : error ? (
          <div className="p-8 text-center">
            <p className="text-red-600 text-sm">{error}</p>
            <button
              onClick={fetchData}
              className="mt-3 text-sm bg-gray-900 text-white px-4 py-2 rounded"
            >
              Retry
            </button>
          </div>
        ) : integrations.length === 0 ? (
          <div className="p-12 text-center">
            <p className="text-gray-500 text-sm">No tenant integrations yet</p>
            <p className="text-xs text-gray-400 mt-1">
              Tenants connect payment and social accounts via OAuth in their admin
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left p-3 font-medium text-gray-600">Tenant</th>
                  <th className="text-left p-3 font-medium text-gray-600">Provider</th>
                  <th className="text-left p-3 font-medium text-gray-600">Status</th>
                  <th className="text-left p-3 font-medium text-gray-600">Last tested</th>
                  <th className="text-left p-3 font-medium text-gray-600">Updated</th>
                  <th className="text-right p-3 font-medium text-gray-600"></th>
                </tr>
              </thead>
              <tbody>
                {integrations.map((i) => {
                  const test = testResults[i.id];
                  return (
                    <tr key={i.id} className="border-b">
                      <td className="p-3 font-mono text-xs">
                        {String(i.tenant_id).slice(0, 8)}
                      </td>
                      <td className="p-3 font-medium">{i.provider}</td>
                      <td className="p-3">
                        <span
                          className={`px-2 py-0.5 rounded-full text-xs ${
                            i.status === "connected" || i.status === "active"
                              ? "bg-green-100 text-green-700"
                              : "bg-gray-100 text-gray-600"
                          }`}
                        >
                          {i.status}
                        </span>
                      </td>
                      <td className="p-3 text-xs">
                        {i.last_tested_at
                          ? new Date(i.last_tested_at).toLocaleString()
                          : "—"}
                        {test && (
                          <span
                            className={`ml-2 ${
                              test.ok ? "text-green-600" : "text-red-600"
                            }`}
                          >
                            {test.ok ? "✓" : "✗"}
                          </span>
                        )}
                      </td>
                      <td className="p-3 text-xs text-gray-500">
                        {i.updated_at ? new Date(i.updated_at).toLocaleDateString() : "—"}
                      </td>
                      <td className="p-3 text-right">
                        <button
                          onClick={() => handleTest(i.id)}
                          disabled={testing === i.id}
                          className="text-xs bg-gray-900 text-white px-3 py-1 rounded disabled:opacity-50"
                        >
                          {testing === i.id ? "Testing…" : "Test"}
                        </button>
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
