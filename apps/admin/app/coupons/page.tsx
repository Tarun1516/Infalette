"use client";

import { toast } from "@/components/toaster";

import { useEffect, useState } from "react";
import { adminApi } from "@/lib/api";

export default function CouponsPage() {
  const [coupons, setCoupons] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ code: "", discount_type: "percentage", value: "10", minimum_order_cents: "0", usage_limit: "", expires_at: "" });

  const fetch = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminApi.getDiscounts();
      setCoupons(res);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetch();
  }, []);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await adminApi.createDiscount({
        code: form.code,
        discount_type: form.discount_type,
        value: parseInt(form.value),
        minimum_order_cents: parseInt(form.minimum_order_cents || "0"),
        usage_limit: form.usage_limit ? parseInt(form.usage_limit) : null,
        expires_at: form.expires_at ? new Date(form.expires_at).toISOString() : null,
      });
      setForm({ code: "", discount_type: "percentage", value: "10", minimum_order_cents: "0", usage_limit: "", expires_at: "" });
      fetch();
    } catch (e: any) {
      toast({ kind: "error", title: "Something went wrong", description: e.message });
    }
  };

  const remove = async (id: string) => {
    if (!confirm("Delete coupon?")) return;
    try {
      await adminApi.deleteDiscount(id);
      fetch();
    } catch (e: any) {
      toast({ kind: "error", title: "Something went wrong", description: e.message });
    }
  };

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <p className="text-[12px] uppercase tracking-[0.18em] text-gray-500 dark:text-neutral-500">
          Promotions
        </h1>
        <h1 className="mt-2 text-[36px] sm:text-[44px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
          Coupons
        </h1>
        <p className="mt-2 text-[13px] text-gray-500 dark:text-neutral-500">
          Per-tenant codes validated at checkout (percentage / fixed / free shipping).
          Customers enter the code at checkout to redeem.
        </p>
      </div>

      <form
        onSubmit={create}
        className="bg-white dark:bg-neutral-950 border border-gray-100 dark:border-neutral-900 p-5 rounded-2xl flex flex-col gap-3"
      >
        <p className="text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500">
          New coupon
        </p>
        <div className="grid md:grid-cols-4 gap-3">
          <input
            placeholder="CODE (SAVE10)"
            value={form.code}
            onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })}
            className="w-full h-10 rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 text-[13px]"
            required
          />
          <select
            value={form.discount_type}
            onChange={(e) => setForm({ ...form, discount_type: e.target.value })}
            className="w-full h-10 rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 text-[13px]"
          >
            <option value="percentage">percentage</option>
            <option value="fixed">fixed (cents)</option>
            <option value="free_shipping">free_shipping</option>
          </select>
          <input
            type="number"
            placeholder="Value"
            value={form.value}
            onChange={(e) => setForm({ ...form, value: e.target.value })}
            className="w-full h-10 rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 text-[13px]"
            required
          />
          <input
            type="number"
            placeholder="Min order (cents)"
            value={form.minimum_order_cents}
            onChange={(e) => setForm({ ...form, minimum_order_cents: e.target.value })}
            className="w-full h-10 rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 text-[13px]"
          />
        </div>
        <div className="grid md:grid-cols-3 gap-3">
          <input
            type="number"
            placeholder="Usage limit (empty = unlimited)"
            value={form.usage_limit}
            onChange={(e) => setForm({ ...form, usage_limit: e.target.value })}
            className="w-full h-10 rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 text-[13px]"
          />
          <input
            type="datetime-local"
            value={form.expires_at}
            onChange={(e) => setForm({ ...form, expires_at: e.target.value })}
            className="w-full h-10 rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 text-[13px]"
          />
          <button
            type="submit"
            className="h-10 rounded-full bg-blue-600 text-white text-[14px] font-medium hover:bg-blue-700 transition-colors"
          >
            Create coupon
          </button>
        </div>
      </form>

      <div className="bg-white dark:bg-neutral-950 border border-gray-100 dark:border-neutral-900 rounded-2xl overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-[13px] text-gray-500 dark:text-neutral-500">Loading…</div>
        ) : error ? (
          <div className="p-4 text-[13px] text-red-700 dark:text-red-300">{error}</div>
        ) : coupons.length === 0 ? (
          <div className="p-12 text-center text-[13px] text-gray-500 dark:text-neutral-500">
            No coupons yet. Create SAVE10 or FREESHIP to get started.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead className="bg-gray-50 dark:bg-neutral-900 text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500">
                <tr>
                  <th className="text-left px-4 py-3 font-medium">Code</th>
                  <th className="text-left px-4 py-3 font-medium">Type</th>
                  <th className="text-left px-4 py-3 font-medium">Value</th>
                  <th className="text-left px-4 py-3 font-medium">Used</th>
                  <th className="text-left px-4 py-3 font-medium">Min Order</th>
                  <th className="text-left px-4 py-3 font-medium">Expires</th>
                  <th className="text-right px-4 py-3 font-medium">Action</th>
                </tr>
              </thead>
              <tbody>
                {coupons.map((d) => (
                  <tr key={d.id} className="border-t border-gray-100 dark:border-neutral-900">
                    <td className="px-4 py-3 font-mono font-medium text-gray-900 dark:text-neutral-100">{d.code}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-neutral-400">{d.discount_type || d.type}</td>
                    <td className="px-4 py-3 text-gray-900 dark:text-neutral-100">
                      {d.discount_type === "percentage"
                        ? `${d.value}%`
                        : d.discount_type === "fixed"
                        ? `₹${(d.value / 100).toFixed(2)}`
                        : "Free ship"}
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-neutral-400">
                      {d.used_count ?? 0} {d.usage_limit ? `/ ${d.usage_limit}` : ""}
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-neutral-400">
                      ₹{((d.minimum_order_cents || 0) / 100).toFixed(2)}
                    </td>
                    <td className="px-4 py-3 text-[12px] text-gray-500 dark:text-neutral-500">
                      {d.expires_at ? new Date(d.expires_at).toLocaleString() : "—"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => remove(d.id)}
                        className="text-[12px] text-gray-500 dark:text-neutral-400 hover:text-red-600 hover:underline"
                      >
                        Delete
                      </button>
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