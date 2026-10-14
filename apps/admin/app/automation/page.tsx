"use client";

import { toast } from "@/components/toaster";

import { useEffect, useState } from "react";
import Link from "next/link";
import { adminApi } from "@/lib/api";

export default function AutomationPage() {
  const [rules, setRules] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRules = async () => {
    setLoading(true);
    setError(null);
    try {
      const res: any = await adminApi.getAutomationRules();
      const list = Array.isArray(res) ? res : res.data || res.items || [];
      setRules(list);
    } catch (e: any) {
      setError(e.message || "Failed to load automation rules");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRules();
  }, []);

  const toggleRule = async (id: string) => {
    try {
      await adminApi.toggleAutomationRule(id);
      fetchRules();
    } catch (e: any) {
      toast({ kind: "error", title: "Something went wrong", description: e.message || "Failed to toggle" });
    }
  };

  const deleteRule = async (id: string) => {
    if (!confirm("Delete this rule?")) return;
    try {
      await adminApi.deleteAutomationRule(id);
      fetchRules();
    } catch (e: any) {
      toast({ kind: "error", title: "Something went wrong", description: e.message || "Failed to delete" });
    }
  };

  const testRule = async (id: string) => {
    const payload = prompt('Enter test payload JSON (or leave empty for default):', '{"text":"buy now","channel":"instagram"}');
    let parsed: any = { text: "price", channel: "instagram" };
    if (payload) {
      try {
        parsed = JSON.parse(payload);
      } catch {
        toast({ kind: "error", title: "Invalid JSON" });
        return;
      }
    }
    try {
      const res = await adminApi.testAutomationRule(id, parsed);
      toast({ kind: "success", title: "Test result", description: JSON.stringify(res, null, 2) });
    } catch (e: any) {
      toast({ kind: "error", title: "Something went wrong", description: e.message || "Test failed" });
    }
  };

  return (
    <div>
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold">Automation Rules</h1>
          <p className="text-sm text-gray-500">{rules.length} rule(s) • triggers from Instagram, WhatsApp, checkout</p>
        </div>
        <Link href="/automation/create" className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700">
          Create Rule
        </Link>
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4 text-xs text-amber-800">
        Instagram private replies are subject to Meta’s 7-day messaging window and user-initiated conversations only. Avoid promising bulk unsolicited DMs.
      </div>

      <div className="bg-white rounded-lg shadow border overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-gray-500">Loading rules…</div>
        ) : error ? (
          <div className="p-8 text-center">
            <p className="text-red-600 text-sm">{error}</p>
            <button onClick={fetchRules} className="mt-3 text-sm bg-gray-900 text-white px-4 py-2 rounded">
              Retry
            </button>
          </div>
        ) : rules.length === 0 ? (
          <div className="p-12 text-center">
            <p className="text-gray-500">No automation rules yet</p>
            <p className="text-xs text-gray-400 mt-1">Create a rule for comment keywords, DM product lookup, or abandoned checkout</p>
            <Link href="/automation/create" className="text-sm text-blue-600 hover:underline mt-3 inline-block">
              Create first rule →
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left p-3 font-medium text-gray-600">Name</th>
                  <th className="text-left p-3 font-medium text-gray-600">Trigger</th>
                  <th className="text-left p-3 font-medium text-gray-600">Actions</th>
                  <th className="text-left p-3 font-medium text-gray-600">Status</th>
                  <th className="text-right p-3 font-medium text-gray-600">Controls</th>
                </tr>
              </thead>
              <tbody>
                {rules.map((r) => (
                  <tr key={r.id} className="border-b hover:bg-gray-50">
                    <td className="p-3">
                      <span className="font-medium">
                        {r.name}
                      </span>
                      <p className="text-xs text-gray-400 truncate max-w-[260px]">{r.description || ""}</p>
                    </td>
                    <td className="p-3">
                      <span className="inline-flex px-2 py-0.5 rounded bg-gray-100 text-gray-700 text-xs">{r.trigger_type}</span>
                    </td>
                    <td className="p-3 text-gray-600 text-xs">
                      {Array.isArray(r.actions) ? r.actions.map((a: any) => a.action_type || a.type).join(", ") : r.actions || "—"}
                    </td>
                    <td className="p-3">
                      <span
                        className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                          r.status === "active" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"
                        }`}
                      >
                        {r.status}
                      </span>
                    </td>
                    <td className="p-3">
                      <div className="flex justify-end gap-2">
                        <button onClick={() => toggleRule(r.id)} className="text-xs border px-2 py-1 rounded hover:bg-gray-50">
                          {r.status === "active" ? "Disable" : "Enable"}
                        </button>
                        <button onClick={() => testRule(r.id)} className="text-xs border px-2 py-1 rounded hover:bg-gray-50">
                          Test
                        </button>
                        <button onClick={() => deleteRule(r.id)} className="text-xs text-red-600 hover:underline">
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
