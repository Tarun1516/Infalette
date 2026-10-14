"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { adminApi } from "@/lib/api";

export default function CustomerDetailPage() {
  const params = useParams();
  const customerId = params.id as string;
  const [customer, setCustomer] = useState<any>(null);
  const [orders, setOrders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const [c, o] = await Promise.all([
          adminApi.getCustomer(customerId),
          adminApi.getCustomerOrders(customerId).catch(() => []),
        ]);
        setCustomer(c);
        setOrders(Array.isArray(o) ? o : (o as any)?.data || []);
      } catch (e: any) {
        setError(e.message || "Failed to load customer");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [customerId]);

  if (loading) return <div className="p-8 text-center text-gray-500">Loading customer…</div>;
  if (error) return <div className="p-8 text-center text-red-600 text-sm">{error}</div>;
  if (!customer) return <div className="p-8 text-center text-gray-500">Customer not found</div>;

  return (
    <div className="max-w-4xl space-y-6">
      <Link href="/customers" className="text-sm text-gray-500 hover:underline">
        ← Back to customers
      </Link>

      <div className="bg-white rounded-lg shadow border p-6">
        <h1 className="text-2xl font-bold">
          {[customer.first_name, customer.last_name].filter(Boolean).join(" ") || customer.email || "Customer"}
        </h1>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4 text-sm">
          <div className="space-y-2">
            <p>
              <span className="text-gray-500">Email:</span> {customer.email || "—"}
            </p>
            <p>
              <span className="text-gray-500">Phone:</span> {customer.phone || "—"}
            </p>
            <p>
              <span className="text-gray-500">Status:</span> <span className="px-2 py-0.5 rounded-full bg-gray-100 text-xs">{customer.status || "active"}</span>
            </p>
          </div>
          <div className="space-y-2">
            <p>
              <span className="text-gray-500">Tags:</span> {customer.tags?.join(", ") || "—"}
            </p>
            <p>
              <span className="text-gray-500">Consent:</span> {customer.consent ? "granted" : "—"}
            </p>
            <p>
              <span className="text-gray-500">Created:</span> {customer.created_at ? new Date(customer.created_at).toLocaleString() : "—"}
            </p>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow border p-6">
        <h3 className="font-semibold mb-3">Orders ({orders.length})</h3>
        {orders.length === 0 ? (
          <p className="text-sm text-gray-400">No orders yet</p>
        ) : (
          <div className="space-y-2">
            {orders.map((o: any) => (
              <Link key={o.id} href={`/orders/${o.id}`} className="flex justify-between items-center py-2 border-b last:border-0 hover:bg-gray-50 px-2 rounded">
                <span className="font-mono text-xs">#{String(o.id).slice(0, 8)}</span>
                <span className="text-sm font-medium">₹{((o.total_cents ?? 0) / 100).toFixed(2)}</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100">{o.status}</span>
              </Link>
            ))}
          </div>
        )}
      </div>

      <div className="bg-white rounded-lg shadow border p-6">
        <h3 className="font-semibold mb-3">Timeline</h3>
        <p className="text-sm text-gray-400">Lead stages, conversations, and orders will appear on the unified timeline as events are recorded.</p>
        {customer.timeline && customer.timeline.length > 0 ? (
          <div className="mt-3 space-y-2">
            {customer.timeline.map((ev: any, idx: number) => (
              <div key={idx} className="text-xs border-l-2 pl-3 py-1">
                <p className="font-medium">{ev.event_type || ev.type}</p>
                <p className="text-gray-400">{ev.created_at ? new Date(ev.created_at).toLocaleString() : ""}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-gray-300 mt-2">No timeline events yet</p>
        )}
      </div>
    </div>
  );
}
