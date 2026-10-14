"use client";

import { useState } from "react";
import Link from "next/link";
import { storefrontApi } from "@/lib/api";

/**
 * Order tracking (spec §1 customer role: "track orders").
 * Works for guests and customers alike: order id + checkout email are
 * verified server-side against the tenant's records.
 */
export default function TrackOrderPage({ params }: { params: { tenant: string } }) {
  const [orderId, setOrderId] = useState("");
  const [email, setEmail] = useState("");
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleTrack = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await storefrontApi.trackOrder(params.tenant, orderId.trim(), email.trim());
      setResult(data);
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || "Order not found";
      setError(typeof msg === "string" ? msg : "Order not found");
    } finally {
      setLoading(false);
    }
  };

  const stageLabels: Record<string, string> = {
    confirmed: "Order confirmed",
    processing: "Packing",
    shipped: "Shipped",
    delivered: "Delivered",
  };

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-12 sm:py-16">
      <header className="mb-8">
        <p className="text-[12px] uppercase tracking-[0.18em] text-gray-500 dark:text-neutral-500">
          Tracking
        </p>
        <h1 className="mt-2 text-[36px] sm:text-[44px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
          Track your order
        </h1>
        <p className="mt-2 text-[15px] text-gray-500 dark:text-neutral-400">
          Enter the order ID from your confirmation page or email, plus the
          email you used at checkout.
        </p>
      </header>

      <form
        onSubmit={handleTrack}
        className="rounded-2xl border border-gray-100 dark:border-neutral-900 bg-white dark:bg-neutral-950 p-6 sm:p-8 space-y-4"
      >
        <div>
          <label className="block text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500 mb-1">
            Order ID
          </label>
          <input
            type="text"
            value={orderId}
            onChange={(e) => setOrderId(e.target.value)}
            placeholder="e.g. 3f2c9a1e-…"
            required
            className="w-full h-11 rounded-xl border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 text-[14px] focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500 mb-1">
            Email used at checkout
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            required
            className="w-full h-11 rounded-xl border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 text-[14px] focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="w-full h-11 rounded-full bg-gray-900 dark:bg-white text-white dark:text-black text-[14px] font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
        >
          {loading ? "Checking…" : "Track order"}
        </button>
      </form>

      {error && (
        <div className="mt-4 rounded-2xl border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-900/10 px-4 py-3 text-[14px] text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-6 rounded-2xl border border-gray-100 dark:border-neutral-900 bg-white dark:bg-neutral-950 p-6 sm:p-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-[16px] font-semibold text-gray-900 dark:text-neutral-100">
              Order #{String(result.order_id).slice(0, 8)}
            </h2>
            <span className="text-[11px] px-2 py-1 rounded-full bg-gray-100 dark:bg-neutral-900 text-gray-700 dark:text-neutral-300 capitalize">
              {result.status}
            </span>
          </div>
          <p className="text-[14px] text-gray-600 dark:text-neutral-400">
            Total: ₹{(result.total_cents / 100).toFixed(2)} {result.currency ? `· ${result.currency}` : ""}
          </p>

          <ol className="mt-4 space-y-2">
            {["confirmed", "processing", "shipped", "delivered"].map((stage) => {
              const done = (result.timeline || []).includes(stage);
              return (
                <li
                  key={stage}
                  className={`flex items-center gap-2 text-[14px] ${
                    done ? "text-green-700 dark:text-green-400" : "text-gray-400 dark:text-neutral-600"
                  }`}
                >
                  <span
                    className={`w-3.5 h-3.5 rounded-full border ${
                      done
                        ? "bg-green-600 border-green-600 dark:bg-green-500 dark:border-green-500"
                        : "border-gray-300 dark:border-neutral-700"
                    }`}
                  />
                  {stageLabels[stage]}
                </li>
              );
            })}
          </ol>

          {(result.tracking || []).length > 0 && (
            <div className="mt-4 border-t border-gray-100 dark:border-neutral-900 pt-4">
              <h3 className="text-[14px] font-semibold mb-2 text-gray-900 dark:text-neutral-100">Shipments</h3>
              {result.tracking.map((t: any, i: number) => (
                <div key={i} className="text-[14px] text-gray-600 dark:text-neutral-400 mb-2">
                  <p className="font-medium">{t.carrier || "Carrier"}</p>
                  {t.tracking_number ? (
                    <p>
                      Tracking number:{" "}
                      <a
                        href={`https://www.google.com/search?q=${encodeURIComponent((t.carrier || "") + " tracking " + t.tracking_number)}`}
                        target="_blank"
                        rel="noreferrer"
                        className="text-blue-600 dark:text-blue-400 underline break-all"
                      >
                        {t.tracking_number}
                      </a>
                    </p>
                  ) : (
                    <p className="text-gray-400 dark:text-neutral-600">Awaiting pickup — tracking number pending.</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="mt-8 text-center">
        <Link
          href={`/${params.tenant}`}
          className="text-[13px] text-gray-500 dark:text-neutral-500 hover:underline"
        >
          ← Back to store
        </Link>
      </div>
    </div>
  );
}
