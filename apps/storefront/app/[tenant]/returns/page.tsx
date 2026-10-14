"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { storefrontApi } from "@/lib/api";
import AuthGate from "@/components/auth-gate";

type ReturnRecord = {
  id: string;
  order_id: string;
  reason: string;
  status: string;
  items: Array<{ product_id: string; quantity: number }>;
};

/**
 * Customer-facing returns list.
 *
 * The API doesn't expose a dedicated /returns endpoint; returns are
 * recorded as orders whose status has moved to "returned". We fetch the
 * customer's orders with status=returned and render one card per order.
 *
 * Support returns/contact moved inside the Account page as a section
 * (see /account). This page is the dedicated self-service "Returns"
 * tab.
 */
export default function ReturnsPage({ params }: { params: { tenant: string } }) {
  const { tenant } = params;
  return (
    <AuthGate tenant={tenant}>
      <ReturnsList tenant={tenant} />
    </AuthGate>
  );
}

function ReturnsList({ tenant }: { tenant: string }) {
  const [returns, setReturns] = useState<ReturnRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const list = (await storefrontApi.getReturns(tenant)) as any[];
        if (cancelled) return;
        setReturns(
          list.map((o: any) => ({
            id: String(o.id),
            order_id: String(o.id),
            reason: o.return_reason || o.reason || "Return requested",
            status: String(o.status || "pending").toLowerCase(),
            items: Array.isArray(o.return_items) ? o.return_items : [],
          }))
        );
      } catch (err: any) {
        if (cancelled) return;
        const msg = err?.response?.data?.detail || err?.message || "Failed to load returns";
        setError(typeof msg === "string" ? msg : "Failed to load returns");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [tenant]);

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-12">
      <header className="mb-8">
        <p className="text-[12px] uppercase tracking-[0.18em] text-gray-500 dark:text-neutral-500">
          After-sales
        </p>
        <h1 className="mt-2 text-[36px] sm:text-[44px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
          My returns
        </h1>
        <p className="mt-2 text-[15px] text-gray-500 dark:text-neutral-400">
          Track the status of every return you&apos;ve requested.
        </p>
      </header>

      {loading && (
        <div className="rounded-2xl border border-gray-100 dark:border-neutral-900 bg-white dark:bg-neutral-950 p-6 text-[14px] text-gray-500 dark:text-neutral-400">
          Loading…
        </div>
      )}

      {error && !loading && (
        <div className="rounded-2xl border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-900/10 p-4 text-[14px] text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      {!loading && !error && returns.length === 0 && (
        <div className="rounded-2xl border border-dashed border-gray-300 dark:border-neutral-800 py-16 px-6 text-center bg-white dark:bg-neutral-950">
          <p className="text-[15px] text-gray-700 dark:text-neutral-300">
            No returns yet.
          </p>
          <p className="mt-1 text-[13px] text-gray-500 dark:text-neutral-500">
            When you request a return on an order, it will show up here.
          </p>
          <Link
            href={`/${tenant}/orders`}
            className="mt-6 inline-flex h-11 px-6 items-center justify-center rounded-full bg-gray-900 dark:bg-white text-white dark:text-black text-[14px] font-medium hover:opacity-90 transition-opacity"
          >
            View your orders
          </Link>
        </div>
      )}

      {!loading && !error && returns.length > 0 && (
        <ul className="space-y-3">
          {returns.map((r) => (
            <li key={r.id} className="rounded-2xl border border-gray-100 dark:border-neutral-900 bg-white dark:bg-neutral-950 p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-semibold text-[14px] text-gray-900 dark:text-neutral-100">
                    Return for order #{r.order_id.slice(0, 8)}
                  </p>
                  <p className="text-[12px] text-gray-500 dark:text-neutral-500 mt-1">Reason: {r.reason}</p>
                  {r.items.length > 0 && (
                    <ul className="mt-2 text-[12px] text-gray-600 dark:text-neutral-400 list-disc list-inside">
                      {r.items.map((it, idx) => (
                        <li key={idx}>
                          Product {String(it.product_id).slice(0, 8)} — qty {it.quantity}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <span className="text-[11px] px-2.5 py-1 rounded-full bg-orange-100 dark:bg-orange-900/30 text-orange-800 dark:text-orange-300 capitalize">
                  {r.status}
                </span>
              </div>
              <div className="mt-3">
                <Link
                  href={`/${tenant}/orders/${r.order_id}`}
                  className="text-[12px] text-blue-600 dark:text-blue-400 hover:underline"
                >
                  View order →
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}