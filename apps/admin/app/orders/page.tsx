"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { adminApi } from "@/lib/api";

export default function OrdersPage() {
  const [orders, setOrders] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const perPage = 20;

  const fetchOrders = async (p = page, status = statusFilter) => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = { page: String(p), per_page: String(perPage) };
      if (status) params.status = status;
      const res: any = await adminApi.getOrders(params);
      const list = Array.isArray(res) ? res : res.data || res.items || [];
      setOrders(list);
      setTotal(res.total ?? list.length);
    } catch (e: any) {
      setError(e.message || "Failed to load orders");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrders(1, statusFilter);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleFilter = (s: string) => {
    setStatusFilter(s);
    setPage(1);
    fetchOrders(1, s);
  };

  const statusColor = (s: string) => {
    switch (s) {
      case "paid":
      case "confirmed":
        return "bg-green-100 text-green-700";
      case "pending":
        return "bg-amber-100 text-amber-700";
      case "fulfilled":
      case "shipped":
        return "bg-blue-100 text-blue-700";
      case "cancelled":
      case "refunded":
        return "bg-red-100 text-red-700";
      default:
        return "bg-gray-100 text-gray-600";
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <p className="text-[12px] uppercase tracking-[0.18em] text-gray-500 dark:text-neutral-500">
            Orders
          </p>
          <h1 className="mt-2 text-[36px] sm:text-[44px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
            All orders
          </h1>
          <p className="mt-1 text-[13px] text-gray-500 dark:text-neutral-500">
            {total} order{total === 1 ? "" : "s"} • {statusFilter || "all statuses"}
          </p>
        </div>
        <select
          value={statusFilter}
          onChange={(e) => handleFilter(e.target.value)}
          className="h-9 rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 text-[13px]"
        >
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="confirmed">Confirmed</option>
          <option value="paid">Paid</option>
          <option value="fulfilled">Fulfilled</option>
          <option value="shipped">Shipped</option>
          <option value="cancelled">Cancelled</option>
          <option value="refunded">Refunded</option>
        </select>
      </div>

      <div className="rounded-2xl bg-white dark:bg-neutral-950 border border-gray-100 dark:border-neutral-900 overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-gray-500 dark:text-neutral-500">Loading orders…</div>
        ) : error ? (
          <div className="p-8 text-center">
            <p className="text-red-600 text-[14px]">{error}</p>
            <button onClick={() => fetchOrders(page, statusFilter)} className="mt-3 text-[13px] bg-gray-900 dark:bg-white text-white dark:text-black px-4 py-2 rounded-full">
              Retry
            </button>
          </div>
        ) : orders.length === 0 ? (
          <div className="p-12 text-center">
            <p className="text-gray-500 dark:text-neutral-500">No orders found</p>
            <p className="text-xs text-gray-400 dark:text-neutral-600 mt-1">
              Orders will appear after successful checkouts.
            </p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead className="bg-gray-50 dark:bg-neutral-900 text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500">
                  <tr>
                    <th className="text-left px-4 py-3 font-medium">Order</th>
                    <th className="text-left px-4 py-3 font-medium">Customer</th>
                    <th className="text-left px-4 py-3 font-medium">Total</th>
                    <th className="text-left px-4 py-3 font-medium">Status</th>
                    <th className="text-left px-4 py-3 font-medium">Date</th>
                    <th className="text-right px-4 py-3 font-medium">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((o) => (
                    <tr key={o.id} className="border-t border-gray-100 dark:border-neutral-900">
                      <td className="px-4 py-3 font-mono text-xs text-gray-700 dark:text-neutral-300">#{String(o.id).slice(0, 8)}</td>
                      <td className="px-4 py-3">
                        <p className="font-medium text-gray-900 dark:text-neutral-100">{o.customer?.email || o.customer_email || "Guest"}</p>
                        <p className="text-xs text-gray-500 dark:text-neutral-500">{o.customer?.first_name || ""}</p>
                      </td>
                      <td className="px-4 py-3 font-medium text-gray-900 dark:text-neutral-100">₹{((o.total_cents ?? 0) / 100).toFixed(2)}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex px-2 py-0.5 rounded-full text-[11px] font-medium ${statusColor(o.status)}`}>
                          {o.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-500 dark:text-neutral-500 text-xs">
                        {o.created_at ? new Date(o.created_at).toLocaleDateString() : "—"}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Link href={`/orders/${o.id}`} className="inline-flex h-7 px-3 items-center justify-center rounded-full border border-gray-200 dark:border-neutral-800 text-[12px] hover:bg-gray-50 dark:hover:bg-neutral-900">
                          View
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {total > perPage && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 dark:border-neutral-900 text-[13px] text-gray-500 dark:text-neutral-500">
                <span>Page {page} of {Math.ceil(total / perPage)}</span>
                <div className="flex gap-2">
                  <button
                    disabled={page <= 1}
                    onClick={() => {
                      const np = page - 1;
                      setPage(np);
                      fetchOrders(np, statusFilter);
                    }}
                    className="h-8 px-4 inline-flex items-center justify-center rounded-full border border-gray-200 dark:border-neutral-800 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-neutral-900"
                  >
                    Previous
                  </button>
                  <button
                    disabled={page >= Math.ceil(total / perPage)}
                    onClick={() => {
                      const np = page + 1;
                      setPage(np);
                      fetchOrders(np, statusFilter);
                    }}
                    className="h-8 px-4 inline-flex items-center justify-center rounded-full border border-gray-200 dark:border-neutral-800 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-neutral-900"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
