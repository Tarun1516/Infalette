"use client";

import { toast } from "@/components/toaster";

import { useEffect, useState } from "react";
import { adminApi, adminApiExt } from "@/lib/api";

type Schedule = {
  id: string;
  report_type: string;
  frequency: string;
  recipients_json?: string[];
  is_active?: boolean;
  last_run_at?: string | null;
  run_count?: number;
};

export default function ReportsPage() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [segments, setSegments] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ report_type: "orders", frequency: "daily", recipients: "" });
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [sched, segs] = await Promise.all([
        adminApi.getReportSchedules().catch(() => []),
        adminApi.getAbandonedSegments(24).catch(() => null),
      ]);
      const list = Array.isArray(sched) ? sched : (sched as any)?.data || [];
      setSchedules(list);
      setSegments(segs);
    } catch (e: any) {
      setError(e.message || "Failed to load reports");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const recipients = form.recipients
        .split(",")
        .map((r) => r.trim())
        .filter(Boolean);
      await adminApi.createReportSchedule({
        report_type: form.report_type,
        frequency: form.frequency,
        recipients_json: recipients,
        is_active: true,
      });
      setForm({ report_type: "orders", frequency: "daily", recipients: "" });
      await load();
    } catch (e: any) {
      toast({ kind: "error", title: "Something went wrong", description: e.message || "Failed to create schedule" });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this schedule?")) return;
    try {
      await adminApi.deleteReportSchedule(id);
      await load();
    } catch (e: any) {
      toast({ kind: "error", title: "Something went wrong", description: e.message || "Failed to delete" });
    }
  };

  if (loading) return <div className="p-8">Loading…</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Reports & Segments</h1>
      {error && <div className="bg-red-50 text-red-700 border border-red-200 rounded-lg p-3 text-sm">{error}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Abandoned segments (CRM plan) */}
        <section className="bg-white rounded-lg shadow border p-5">
          <h2 className="font-semibold mb-3">Abandoned Segments (24h)</h2>
          {!segments ? (
            <p className="text-sm text-gray-400">Not available on your plan or nothing to show.</p>
          ) : (
            <div className="space-y-4 text-sm">
              <div>
                <p className="font-medium">Abandoned carts ({segments.abandoned_carts?.length ?? 0})</p>
                <ul className="mt-1 space-y-1 text-gray-600">
                  {(segments.abandoned_carts || []).slice(0, 5).map((c: any) => (
                    <li key={c.cart_id}>
                      {c.email || c.session_key?.slice(0, 8) || "guest"} — ₹
                      {((c.total_cents || 0) / 100).toFixed(0)}
                    </li>
                  ))}
                  {!segments.abandoned_carts?.length && (
                    <li className="text-gray-400">None</li>
                  )}
                </ul>
              </div>
              <div>
                <p className="font-medium">
                  Abandoned social checkouts ({segments.abandoned_social_checkouts?.length ?? 0})
                </p>
                <ul className="mt-1 space-y-1 text-gray-600">
                  {(segments.abandoned_social_checkouts || []).slice(0, 5).map((l: any) => (
                    <li key={l.lead_id}>
                      {l.first_name || l.email} — stage: {l.stage} ({l.source})
                    </li>
                  ))}
                  {!segments.abandoned_social_checkouts?.length && (
                    <li className="text-gray-400">None</li>
                  )}
                </ul>
              </div>
            </div>
          )}
        </section>

        {/* Scheduled reports */}
        <section className="bg-white rounded-lg shadow border p-5">
          <h2 className="font-semibold mb-3">Scheduled Reports</h2>
          {schedules.length === 0 ? (
            <p className="text-sm text-gray-400 mb-4">No schedules yet.</p>
          ) : (
            <table className="w-full text-sm mb-4">
              <thead>
                <tr className="text-left text-gray-500 border-b">
                  <th className="py-2">Type</th>
                  <th>Frequency</th>
                  <th>Last run</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {schedules.map((s) => (
                  <tr key={s.id} className="border-b last:border-0">
                    <td className="py-2 capitalize">{s.report_type}</td>
                    <td className="capitalize">{s.frequency}</td>
                    <td className="text-gray-500">
                      {s.last_run_at ? new Date(s.last_run_at).toLocaleString() : "never"}
                    </td>
                    <td className="text-right">
                      <button
                        onClick={() => handleDelete(s.id)}
                        className="text-red-600 hover:underline text-xs"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <div className="flex gap-2 mb-3">
            {(["orders", "customers", "leads"] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={async () => {
                  try {
                    const blob = await adminApiExt.exportCsv(t);
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = `${t}_${new Date().toISOString().slice(0, 10)}.csv`;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    URL.revokeObjectURL(url);
                  } catch (e: any) {
                    toast({ kind: "error", title: "Something went wrong", description: e.message || "Export failed" });
                  }
                }}
                className="flex-1 py-2 rounded-lg border text-xs font-medium hover:bg-gray-50 capitalize"
              >
                Download {t} CSV
              </button>
            ))}
          </div>

          <form onSubmit={handleCreate} className="space-y-3 border-t pt-4">
            <div className="grid grid-cols-2 gap-3">
              <select
                value={form.report_type}
                onChange={(e) => setForm({ ...form, report_type: e.target.value })}
                className="border rounded-lg px-3 py-2 text-sm bg-white"
              >
                <option value="orders">Orders</option>
                <option value="customers">Customers</option>
                <option value="leads">Leads</option>
              </select>
              <select
                value={form.frequency}
                onChange={(e) => setForm({ ...form, frequency: e.target.value })}
                className="border rounded-lg px-3 py-2 text-sm bg-white"
              >
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
              </select>
            </div>
            <input
              type="text"
              placeholder="Recipient emails, comma-separated"
              value={form.recipients}
              onChange={(e) => setForm({ ...form, recipients: e.target.value })}
              className="w-full border rounded-lg px-3 py-2 text-sm"
            />
            <button
              type="submit"
              disabled={saving}
              className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:bg-gray-300"
            >
              {saving ? "Saving…" : "Schedule report"}
            </button>
          </form>
        </section>
      </div>
    </div>
  );
}
