"use client";

import { useEffect, useState } from "react";
import { adminApi, adminApiExt } from "@/lib/api";

export default function WebhooksPage() {
  const [endpoints, setEndpoints] = useState<any[]>([]);
  const [deliveries, setDeliveries] = useState<any[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", url: "", events: "order.created,payment.succeeded" });
  const [error, setError] = useState("");

  async function load() {
    try {
      const list: any = await adminApi.getWebhooks();
      setEndpoints(Array.isArray(list) ? list : (list?.items || []));
    } catch (e: any) {
      setError(e.message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function selectEndpoint(id: string) {
    setSelectedId(id);
    try {
      setDeliveries(await adminApiExt.getWebhookDeliveries(id));
    } catch {
      setDeliveries([]);
    }
  }

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await adminApi.createWebhook({
        name: form.name,
        url: form.url,
        events: form.events.split(",").map((s) => s.trim()).filter(Boolean),
      });
      setForm({ name: "", url: "", events: form.events });
      await load();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function test(id: string) {
    setError("");
    try {
      await adminApi.testWebhook(id);
      if (selectedId === id) selectEndpoint(id);
    } catch (err: any) {
      setError(err.message);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Webhooks</h1>
      {error && <p className="text-red-600 text-sm mb-3">{error}</p>}

      <form onSubmit={create} className="bg-white p-4 rounded shadow mb-6 grid grid-cols-1 md:grid-cols-4 gap-2">
        <input required placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="p-2.5 border rounded" />
        <input required type="url" placeholder="https://your-app.example/hook" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} className="p-2.5 border rounded md:col-span-2" />
        <input placeholder="Events (comma separated)" value={form.events} onChange={(e) => setForm({ ...form, events: e.target.value })} className="p-2.5 border rounded md:col-span-3" />
        <button className="px-4 py-2 bg-blue-600 text-white rounded">Create endpoint</button>
      </form>

      <div className="grid md:grid-cols-2 gap-6">
        <table className="w-full bg-white rounded shadow text-sm">
          <thead>
            <tr className="text-left border-b bg-gray-50"><th className="p-3">Endpoint</th><th className="p-3">Status</th><th></th></tr>
          </thead>
          <tbody>
            {endpoints.map((w) => (
              <tr key={w.id} className={`border-b cursor-pointer ${selectedId === w.id ? "bg-blue-50" : ""}`} onClick={() => selectEndpoint(w.id)}>
                <td className="p-3">
                  <div className="font-medium">{w.name}</div>
                  <div className="text-xs text-gray-500 truncate max-w-[240px]">{w.url}</div>
                </td>
                <td className="p-3 capitalize">{w.status || "active"}</td>
                <td className="p-3 text-right">
                  <button onClick={(e) => { e.stopPropagation(); test(w.id); }} className="px-3 py-1 border rounded hover:bg-gray-100">Send test</button>
                </td>
              </tr>
            ))}
            {endpoints.length === 0 && <tr><td colSpan={3} className="p-6 text-center text-gray-500">No webhook endpoints.</td></tr>}
          </tbody>
        </table>

        <table className="w-full bg-white rounded shadow text-sm">
          <thead>
            <tr className="text-left border-b bg-gray-50"><th className="p-3" colSpan={3}>Recent deliveries{selectedId ? "" : " (select an endpoint)"}</th></tr>
            <tr className="text-left border-b">
              <th className="p-3">Event</th><th className="p-3">Status</th><th className="p-3">Response</th>
            </tr>
          </thead>
          <tbody>
            {deliveries.map((d) => (
              <tr key={d.id} className="border-b">
                <td className="p-3">{d.event_type}</td>
                <td className="p-3">{d.status}{d.response_code ? ` (${d.response_code})` : ""}</td>
                <td className="p-3 text-xs text-gray-500 truncate max-w-[200px]">{d.error || d.response_body || ""}</td>
              </tr>
            ))}
            {deliveries.length === 0 && <tr><td colSpan={3} className="p-6 text-center text-gray-500">No deliveries yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
