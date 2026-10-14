"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { adminApi } from "@/lib/api";

export default function CustomersPage() {
  const [customers, setCustomers] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const perPage = 20;

  const fetchCustomers = async (p = page, q = search) => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = { page: String(p), per_page: String(perPage) };
      if (q) params.search = q;
      const res: any = await adminApi.getCustomers(params);
      const list = Array.isArray(res) ? res : res.data || res.items || [];
      setCustomers(list);
      setTotal(res.total ?? list.length);
    } catch (e: any) {
      setError(e.message || "Failed to load customers");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCustomers(1, "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchCustomers(1, search);
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold">Customers</h1>
          <p className="text-sm text-gray-500">{total} customer(s)</p>
        </div>
      </div>

      <form onSubmit={handleSearch} className="flex gap-2 mb-4">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by email, name, phone..."
          className="flex-1 border rounded-lg px-3 py-2 text-sm"
        />
        <button type="submit" className="px-4 py-2 bg-gray-900 text-white rounded-lg text-sm">
          Search
        </button>
      </form>

      <div className="bg-white rounded-lg shadow border overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-gray-500">Loading customers…</div>
        ) : error ? (
          <div className="p-8 text-center">
            <p className="text-red-600 text-sm">{error}</p>
            <button onClick={() => fetchCustomers(page, search)} className="mt-3 text-sm bg-gray-900 text-white px-4 py-2 rounded">
              Retry
            </button>
          </div>
        ) : customers.length === 0 ? (
          <div className="p-12 text-center">
            <p className="text-gray-500">No customers found</p>
            <p className="text-xs text-gray-400 mt-1">Customers appear after checkout or lead creation</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="text-left p-3 font-medium text-gray-600">Name</th>
                    <th className="text-left p-3 font-medium text-gray-600">Email</th>
                    <th className="text-left p-3 font-medium text-gray-600">Phone</th>
                    <th className="text-left p-3 font-medium text-gray-600">Orders</th>
                    <th className="text-left p-3 font-medium text-gray-600">Status</th>
                    <th className="text-right p-3 font-medium text-gray-600">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {customers.map((c) => (
                    <tr key={c.id} className="border-b hover:bg-gray-50">
                      <td className="p-3 font-medium">
                        {c.first_name || c.last_name ? `${c.first_name || ""} ${c.last_name || ""}`.trim() : "—"}
                      </td>
                      <td className="p-3 text-gray-600">{c.email || "—"}</td>
                      <td className="p-3 text-gray-600">{c.phone || "—"}</td>
                      <td className="p-3">{c.orders_count ?? c.order_count ?? 0}</td>
                      <td className="p-3">
                        <span className="inline-flex px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-600">
                          {c.status || "active"}
                        </span>
                      </td>
                      <td className="p-3 text-right">
                        <Link href={`/customers/${c.id}`} className="text-blue-600 hover:underline text-xs font-medium">
                          View
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {total > perPage && (
              <div className="flex items-center justify-between p-3 border-t bg-gray-50">
                <span className="text-xs text-gray-500">
                  Page {page} of {Math.ceil(total / perPage)}
                </span>
                <div className="flex gap-2">
                  <button
                    disabled={page <= 1}
                    onClick={() => {
                      const np = page - 1;
                      setPage(np);
                      fetchCustomers(np, search);
                    }}
                    className="px-3 py-1 border rounded text-xs disabled:opacity-40 bg-white"
                  >
                    Previous
                  </button>
                  <button
                    disabled={page >= Math.ceil(total / perPage)}
                    onClick={() => {
                      const np = page + 1;
                      setPage(np);
                      fetchCustomers(np, search);
                    }}
                    className="px-3 py-1 border rounded text-xs disabled:opacity-40 bg-white"
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
