"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { storefrontApi } from "@/lib/api";
import AuthGate from "@/components/auth-gate";

type Address = {
  full_name?: string;
  first_name?: string;
  last_name?: string;
  address1?: string;
  address2?: string;
  city?: string;
  state?: string;
  postal_code?: string;
  zip?: string;
  country?: string;
  phone?: string;
  email?: string;
};

function formatAddress(addr: Address | null | undefined): string | null {
  if (!addr || typeof addr !== "object") return null;
  const name =
    addr.full_name ||
    [addr.first_name, addr.last_name].filter(Boolean).join(" ") ||
    "";
  const line1 = addr.address1 || "";
  const line2 = addr.address2 || "";
  const city = addr.city || "";
  const state = addr.state || "";
  const postal = addr.postal_code || addr.zip || "";
  const country = addr.country || "";
  const phone = addr.phone || "";

  const parts = [
    name,
    line1,
    line2,
    [city, state, postal].filter(Boolean).join(", "),
    country,
  ].filter((p) => p && String(p).trim().length > 0);

  if (parts.length === 0) return null;
  return phone ? `${parts.join("\n")}\n${phone}` : parts.join("\n");
}

function formatMoney(cents: number | null | undefined, currency = "INR"): string {
  if (cents == null) return "—";
  const value = (cents / 100).toFixed(2);
  return currency === "INR" ? `₹${value}` : `${currency} ${value}`;
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return String(iso);
  }
}

const STATUS_BADGE: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  confirmed: "bg-blue-100 text-blue-800",
  processing: "bg-indigo-100 text-indigo-800",
  shipped: "bg-purple-100 text-purple-800",
  delivered: "bg-green-100 text-green-800",
  cancelled: "bg-red-100 text-red-800",
  refunded: "bg-gray-200 text-gray-800",
  returned: "bg-orange-100 text-orange-800",
};

function statusClass(s: string | undefined): string {
  if (!s) return "bg-gray-100 text-gray-800";
  return STATUS_BADGE[s.toLowerCase()] || "bg-gray-100 text-gray-800";
}

/**
 * The order detail page (customer self-service).
 *
 * Pulls the order from GET /api/v1/orders/{id} and the related fulfillments
 * from /orders/{id}/fulfillments. The API does not include line items in
 * the order payload (the Order model has no relationship to OrderItem), so
 * we render a TODO empty state and rely on the invoice page for line items.
 */
export default function OrderDetailPage({
  params,
}: {
  params: { tenant: string; id: string };
}) {
  const { tenant, id } = params;
  return (
    <AuthGate tenant={tenant}>
      <OrderDetail tenant={tenant} id={id} />
    </AuthGate>
  );
}

function OrderDetail({ tenant, id }: { tenant: string; id: string }) {
  const [order, setOrder] = useState<any | null>(null);
  const [fulfillments, setFulfillments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showReturn, setShowReturn] = useState(false);
  const [returnReason, setReturnReason] = useState("");
  const [returnQty, setReturnQty] = useState<Record<string, number>>({});
  const [returnSubmitting, setReturnSubmitting] = useState(false);
  const [returnError, setReturnError] = useState<string | null>(null);

  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [downloadingInvoice, setDownloadingInvoice] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [orderData, fulfillmentData] = await Promise.all([
          storefrontApi.getOrder(tenant, id),
          storefrontApi.getOrderFulfillments(tenant, id).catch(() => []),
        ]);
        if (cancelled) return;
        setOrder(orderData);
        setFulfillments(
          Array.isArray(fulfillmentData)
            ? fulfillmentData
            : fulfillmentData?.data || []
        );
      } catch (err: any) {
        if (cancelled) return;
        const msg =
          err?.response?.data?.detail || err?.message || "Failed to load order";
        setError(typeof msg === "string" ? msg : "Failed to load order");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [tenant, id]);

  const status: string = useMemo(() => {
    if (!order) return "";
    return String(order.status || "").toLowerCase();
  }, [order]);

  const currency: string = order?.currency || "INR";

  // The Order model doesn't currently expose line items through the API
  // (no /orders/{id}/items endpoint, no relationship on the model). We
  // surface what we know and leave line items as a TODO so the page still
  // renders rather than 500'ing when the backend gap bites.
  const lineItems: any[] = Array.isArray(order?.line_items)
    ? order.line_items
    : Array.isArray(order?.items)
      ? order.items
      : [];

  const subtotal: number | null =
    order?.subtotal_cents ?? order?.items_subtotal_cents ?? null;
  const shipping: number | null = order?.shipping_cents ?? null;
  const tax: number | null = order?.tax_cents ?? null;
  const discount: number | null = order?.discount_cents ?? null;
  const total: number | null = order?.total_cents ?? null;

  const shippingAddress: Address = order?.shipping_address_json || order?.shipping_address || null;
  const billingAddress: Address = order?.billing_address_json || order?.billing_address || null;
  const shippingStr = formatAddress(shippingAddress);
  const billingStr = formatAddress(billingAddress);

  async function handleCancel() {
    if (!order) return;
    const ok = window.confirm(
      "Cancel this order? This cannot be undone."
    );
    if (!ok) return;
    setCancelling(true);
    setCancelError(null);
    try {
      const updated = await storefrontApi.cancelOrder(tenant, order.id);
      setOrder((prev: any) => ({ ...(prev || {}), ...(updated || {}), status: updated?.status || "cancelled" }));
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || "Failed to cancel order";
      setCancelError(typeof msg === "string" ? msg : "Failed to cancel order");
    } finally {
      setCancelling(false);
    }
  }

  async function handleDownloadInvoice() {
    if (!order) return;
    setDownloadingInvoice(true);
    setDownloadError(null);
    try {
      const blob = await storefrontApi.downloadInvoice(tenant, order.id, "html");
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `invoice-${order.id}.html`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      // Revoke after a tick so the browser has time to start the download.
      setTimeout(() => window.URL.revokeObjectURL(url), 1000);
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || "Failed to download invoice";
      setDownloadError(typeof msg === "string" ? msg : "Failed to download invoice");
    } finally {
      setDownloadingInvoice(false);
    }
  }

  async function handleSubmitReturn() {
    if (!order) return;
    if (!returnReason.trim()) {
      setReturnError("Please enter a reason for the return.");
      return;
    }
    const selected = Object.entries(returnQty)
      .filter(([, q]) => Number(q) > 0)
      .map(([product_id, quantity]) => ({ product_id, quantity }));
    if (selected.length === 0) {
      setReturnError("Please select at least one item to return.");
      return;
    }
    setReturnSubmitting(true);
    setReturnError(null);
    try {
      await storefrontApi.requestReturn(tenant, order.id, selected, returnReason.trim());
      setShowReturn(false);
      setReturnQty({});
      setReturnReason("");
      // Refresh order to pick up the new status.
      const refreshed = await storefrontApi.getOrder(tenant, order.id).catch(() => null);
      if (refreshed) setOrder(refreshed);
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || "Failed to submit return";
      setReturnError(typeof msg === "string" ? msg : "Failed to submit return");
    } finally {
      setReturnSubmitting(false);
    }
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold">Order details</h1>
          <p className="text-sm text-gray-500 mt-1">
            <Link href={`/${tenant}/account`} className="hover:underline">← Back to account</Link>
          </p>
        </div>
        {order && (
          <span
            className={`text-xs px-3 py-1 rounded-full capitalize ${statusClass(status)}`}
          >
            {status || "unknown"}
          </span>
        )}
      </div>

      {loading && (
        <div className="bg-white rounded-2xl border p-6 text-sm text-gray-500">Loading…</div>
      )}

      {error && !loading && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm">
          {error}
        </div>
      )}

      {!loading && !error && order && (
        <div className="space-y-6">
          {/* Summary card */}
          <div className="bg-white rounded-2xl border shadow-sm p-6">
            <div className="grid md:grid-cols-3 gap-4 text-sm">
              <div>
                <p className="text-gray-500">Order ID</p>
                <p className="font-medium break-all">{order.id}</p>
              </div>
              <div>
                <p className="text-gray-500">Placed</p>
                <p className="font-medium">{formatDate(order.placed_at || order.created_at)}</p>
              </div>
              <div>
                <p className="text-gray-500">Total</p>
                <p className="font-medium">{formatMoney(total, currency)}</p>
              </div>
            </div>
          </div>

          {/* Line items */}
          <div className="bg-white rounded-2xl border shadow-sm p-6">
            <h2 className="font-semibold mb-4">Items</h2>
            {lineItems.length === 0 ? (
              // TODO(backend): OrderItem is a separate table joined only in
              // admin/internal surfaces. Once /orders/{id}/items exists we
              // can render image, name, sku, qty, unit price, line total here.
              <p className="text-sm text-gray-500">
                Line items are not exposed in the public order payload yet.
                The invoice download contains the full breakdown.
              </p>
            ) : (
              <ul className="divide-y">
                {lineItems.map((item: any, idx: number) => (
                  <li key={item.id || idx} className="py-3 flex items-center gap-3">
                    <div className="w-14 h-14 rounded-lg bg-gray-100 flex-shrink-0 overflow-hidden">
                      {item.image_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={item.image_url} alt={item.name} className="w-full h-full object-cover" />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-gray-400 text-xs">—</div>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm truncate">{item.name || item.title}</p>
                      {item.sku && <p className="text-xs text-gray-500">SKU: {item.sku}</p>}
                      <p className="text-xs text-gray-500">Qty: {item.quantity}</p>
                    </div>
                    <div className="text-sm font-medium">
                      {formatMoney((item.price_cents || 0) * (item.quantity || 1), currency)}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Totals */}
          <div className="bg-white rounded-2xl border shadow-sm p-6">
            <h2 className="font-semibold mb-4">Totals</h2>
            <dl className="text-sm space-y-2">
              <div className="flex justify-between">
                <dt className="text-gray-500">Subtotal</dt>
                <dd>{formatMoney(subtotal, currency)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Shipping</dt>
                <dd>{formatMoney(shipping, currency)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Tax</dt>
                <dd>{formatMoney(tax, currency)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Discount</dt>
                <dd>{formatMoney(discount != null ? -Math.abs(discount) : null, currency)}</dd>
              </div>
              <div className="flex justify-between font-semibold text-base border-t pt-2 mt-2">
                <dt>Total</dt>
                <dd>{formatMoney(total, currency)}</dd>
              </div>
            </dl>
          </div>

          {/* Addresses */}
          <div className="grid md:grid-cols-2 gap-6">
            <div className="bg-white rounded-2xl border shadow-sm p-6">
              <h2 className="font-semibold mb-3">Shipping address</h2>
              {shippingStr ? (
                <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans">{shippingStr}</pre>
              ) : (
                <p className="text-sm text-gray-500">Not available</p>
              )}
            </div>
            <div className="bg-white rounded-2xl border shadow-sm p-6">
              <h2 className="font-semibold mb-3">Billing address</h2>
              {billingStr ? (
                <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans">{billingStr}</pre>
              ) : (
                <p className="text-sm text-gray-500">Not available</p>
              )}
            </div>
          </div>

          {/* Fulfillments */}
          <div className="bg-white rounded-2xl border shadow-sm p-6">
            <h2 className="font-semibold mb-3">Shipments</h2>
            {fulfillments.length === 0 ? (
              <p className="text-sm text-gray-500">No shipments yet.</p>
            ) : (
              <ul className="space-y-2">
                {fulfillments.map((f: any, i: number) => (
                  <li key={f.id || i} className="text-sm flex justify-between border-b last:border-b-0 pb-2 last:pb-0">
                    <div>
                      <p className="font-medium">{f.carrier || "Carrier"}</p>
                      {f.tracking_number ? (
                        <a
                          href={`https://www.google.com/search?q=${encodeURIComponent((f.carrier || "") + " tracking " + f.tracking_number)}`}
                          target="_blank"
                          rel="noreferrer"
                          className="text-blue-600 underline break-all"
                        >
                          {f.tracking_number}
                        </a>
                      ) : (
                        <span className="text-gray-400">Tracking pending</span>
                      )}
                    </div>
                    {f.status && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 capitalize self-start">
                        {String(f.status).toLowerCase()}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Actions */}
          <div className="bg-white rounded-2xl border shadow-sm p-6">
            <h2 className="font-semibold mb-3">Actions</h2>
            <div className="flex flex-wrap gap-2">
              {(status === "paid" || status === "processing" || status === "shipped" || status === "delivered") && (
                <button
                  type="button"
                  onClick={() => setShowReturn(true)}
                  className="px-4 py-2 rounded-full border text-sm font-semibold hover:bg-gray-50"
                >
                  Request return
                </button>
              )}
              {status === "delivered" && (
                <button
                  type="button"
                  onClick={handleDownloadInvoice}
                  disabled={downloadingInvoice}
                  className="px-4 py-2 rounded-full bg-gray-900 text-white text-sm font-semibold disabled:opacity-50"
                >
                  {downloadingInvoice ? "Preparing…" : "Download invoice"}
                </button>
              )}
              {(status === "pending" || status === "confirmed") && (
                <button
                  type="button"
                  onClick={handleCancel}
                  disabled={cancelling}
                  className="px-4 py-2 rounded-full border border-red-300 text-red-700 text-sm font-semibold hover:bg-red-50 disabled:opacity-50"
                >
                  {cancelling ? "Cancelling…" : "Cancel order"}
                </button>
              )}
            </div>
            {cancelError && (
              <p className="text-sm text-red-700 mt-2">{cancelError}</p>
            )}
            {downloadError && (
              <p className="text-sm text-red-700 mt-2">{downloadError}</p>
            )}
          </div>
        </div>
      )}

      {/* Return modal */}
      {showReturn && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border shadow-lg w-full max-w-lg p-6">
            <h2 className="font-semibold text-lg mb-2">Request a return</h2>
            <p className="text-xs text-gray-500 mb-4">
              Select the items you&apos;d like to return and tell us why. We&apos;ll
              email you next steps.
            </p>

            {/* Items list */}
            <div className="space-y-2 max-h-48 overflow-auto border rounded-lg p-3 mb-3">
              {lineItems.length === 0 ? (
                <p className="text-sm text-gray-500">
                  We don&apos;t have a per-item breakdown for this order. To
                  request a return for the whole order, enter the quantity
                  you&apos;d like to return against the product id below.
                </p>
              ) : (
                lineItems.map((item: any) => (
                  <div key={item.id || item.product_id} className="flex items-center gap-2 text-sm">
                    <span className="flex-1 truncate">{item.name || item.title || item.product_id}</span>
                    <input
                      type="number"
                      min={0}
                      max={item.quantity}
                      value={returnQty[item.product_id] ?? 0}
                      onChange={(e) =>
                        setReturnQty((prev) => ({
                          ...prev,
                          [item.product_id]: Math.max(0, Number(e.target.value) || 0),
                        }))
                      }
                      className="w-16 border rounded p-1 text-right"
                    />
                  </div>
                ))
              )}
            </div>

            <label className="block text-xs font-medium text-gray-600 mb-1">Reason *</label>
            <textarea
              value={returnReason}
              onChange={(e) => setReturnReason(e.target.value)}
              rows={3}
              className="w-full p-2 border rounded-lg text-sm"
              placeholder="e.g. Wrong size, damaged on arrival, etc."
            />

            {returnError && (
              <p className="text-sm text-red-700 mt-2">{returnError}</p>
            )}

            <div className="flex justify-end gap-2 mt-4">
              <button
                type="button"
                onClick={() => {
                  setShowReturn(false);
                  setReturnError(null);
                }}
                className="px-4 py-2 rounded-full border text-sm"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSubmitReturn}
                disabled={returnSubmitting}
                className="px-4 py-2 rounded-full bg-gray-900 text-white text-sm font-semibold disabled:opacity-50"
              >
                {returnSubmitting ? "Submitting…" : "Submit return"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
