"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { storefrontApi } from "@/lib/api";
import AuthGate from "@/components/auth-gate";

/**
 * All-orders list for the signed-in customer. Mirrors the data on the
 * account page but lives at its own URL so the "Orders" nav link has
 * somewhere to land. Each row links into the order detail page.
 *
 * Auth: wrapped in AuthGate so visitors without a token get a friendly
 * sign-in / sign-up prompt instead of a 401.
 */
export default function OrdersListPage({ params }: { params: { tenant: string } }) {
  const { tenant } = params;
  return (
    <AuthGate tenant={tenant}>
      <OrdersList tenant={tenant} />
    </AuthGate>
  );
}

function OrdersList({ tenant }: { tenant: string }) {
  const [orders, setOrders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const list = await storefrontApi.listOrders(tenant);
        if (cancelled) return;
        setOrders(Array.isArray(list) ? list : []);
      } catch (err: any) {
        if (cancelled) return;
        const msg = err?.response?.data?.detail || err?.message || "Failed to load orders";
        setError(typeof msg === "string" ? msg : "Failed to load orders");
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
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-12">
      <header className="mb-8">
        <p className="text-[12px] uppercase tracking-[0.18em] text-gray-500 dark:text-neutral-500">
          Order history
        </p>
        <h1 className="mt-2 text-[36px] sm:text-[44px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
          My orders
        </h1>
        <p className="mt-2 text-[15px] text-gray-500 dark:text-neutral-400">
          Every order you&apos;ve placed. Click into one to see shipment
          status, download an invoice, or request a return.
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

      {!loading && !error && orders.length === 0 && (
        <div className="rounded-2xl border border-dashed border-gray-300 dark:border-neutral-800 py-16 px-6 text-center bg-white dark:bg-neutral-950">
          <p className="text-[15px] text-gray-700 dark:text-neutral-300">
            You haven&apos;t placed any orders yet.
          </p>
          <p className="mt-1 text-[13px] text-gray-500 dark:text-neutral-500">
            When you do, they&apos;ll appear here with status, tracking and
            invoice download.
          </p>
          <Link
            href={`/${tenant}/products`}
            className="mt-6 inline-flex h-11 px-6 items-center justify-center rounded-full bg-gray-900 dark:bg-white text-white dark:text-black text-[14px] font-medium hover:opacity-90 transition-opacity"
          >
            Start shopping
          </Link>
        </div>
      )}

      {!loading && !error && orders.length > 0 && (
        <div className="space-y-3">
          {orders.map((order: any) => (
            <Link
              key={order.id}
              href={`/${tenant}/orders/${order.id}`}
              className="block rounded-2xl border border-gray-100 dark:border-neutral-900 bg-white dark:bg-neutral-950 p-4 hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)] dark:hover:shadow-[0_8px_30px_rgba(255,255,255,0.04)] transition-shadow"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-semibold text-[14px] text-gray-900 dark:text-neutral-100">
                    Order #{String(order.id).slice(0, 8)}
                  </p>
                  <p className="text-[12px] text-gray-500 dark:text-neutral-500 mt-0.5">
                    Placed {new Date(order.placed_at || order.created_at).toLocaleString()}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-[14px] font-semibold text-gray-900 dark:text-neutral-100">
                    ₹{((order.total_cents || 0) / 100).toFixed(2)} {order.currency || "INR"}
                  </p>
                  <span className="inline-block mt-1 text-[11px] px-2 py-0.5 rounded-full bg-gray-100 dark:bg-neutral-900 text-gray-700 dark:text-neutral-300 capitalize">
                    {order.status}
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}