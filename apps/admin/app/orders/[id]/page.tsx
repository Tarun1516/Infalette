"use client";

import { toast } from "@/components/toaster";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { adminApi, adminApiExt } from "@/lib/api";

export default function OrderDetailPage() {
  const params = useParams();
  const orderId = params.id as string;
  const [order, setOrder] = useState<any>(null);
  const [fulfillments, setFulfillments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState(false);

  const fetchOrder = async () => {
    setLoading(true);
    setError(null);
    try {
      const [o, f] = await Promise.all([
        adminApi.getOrder(orderId),
        adminApi.getOrderFulfillments(orderId).catch(() => []),
      ]);
      setOrder(o);
      setFulfillments(Array.isArray(f) ? f : (f as any)?.data || []);
    } catch (e: any) {
      setError(e.message || "Failed to load order");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrder();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orderId]);

  const updateStatus = async (status: string) => {
    setUpdating(true);
    try {
      await adminApi.updateOrderStatus(orderId, status);
      const o = await adminApi.getOrder(orderId);
      setOrder(o);
    } catch (e: any) {
      toast({ kind: "error", title: "Something went wrong", description: e.message || "Failed to update" });
    } finally {
      setUpdating(false);
    }
  };

  const handleRefund = async () => {
    const amount = prompt("Refund amount in cents (leave empty for full):", "");
    const reason = prompt("Reason:", "Customer request");
    try {
      await adminApi.createRefund(orderId, {
        amount_cents: amount ? parseInt(amount) : undefined,
        reason,
      });
      toast({ kind: "info", title: "Refund initiated" });
      fetchOrder();
    } catch (e: any) {
      toast({ kind: "error", title: "Something went wrong", description: e.message });
    }
  };

  const handleInvoice = async (format: "html" | "pdf" = "html") => {
    try {
      // Use direct fetch to handle binary pdf
      const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
      const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      const url = `${base.replace(/\/$/, "")}/invoices/${orderId}/download?format=${format}`;
      const res = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
      if (!res.ok) throw new Error(await res.text());
      if (format === "pdf") {
        const blob = await res.blob();
        const u = URL.createObjectURL(blob);
        window.open(u, "_blank");
      } else {
        const html = await res.text();
        const w = window.open("", "_blank");
        if (w) {
          w.document.write(html);
          w.document.close();
        }
      }
    } catch (e: any) {
      toast({ kind: "error", title: "Something went wrong", description: e.message || "Invoice not available yet (only for paid orders })");
    }
  };

  if (loading) return <div className="p-8 text-center text-gray-500">Loading order…</div>;
  if (error) return <div className="p-8 text-center text-red-600 text-sm">{error}</div>;
  if (!order) return <div className="p-8 text-center text-gray-500">Order not found</div>;

  const isPaid = ["paid", "confirmed", "processing", "shipped", "fulfilled", "delivered"].includes(order.status);
  const isCOD = order.payment_provider === "cod" || order.payment?.provider === "cod";

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <Link href="/orders" className="hover:underline">Orders</Link>
        <span>›</span>
        <span className="font-mono text-gray-700">#{String(order.id).slice(0, 8)}</span>
        {isCOD && <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 text-xs font-medium">COD</span>}
      </div>

      <div className="flex flex-col sm:flex-row justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Order #{String(order.id).slice(0, 8)}</h1>
          <p className="text-sm text-gray-500">{order.created_at ? new Date(order.created_at).toLocaleString() : ""} • Attribution: {order.attribution_json?.source || order.attribution?.source || "website"}</p>
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          <span className="px-3 py-1 rounded-full text-xs font-medium bg-gray-100">{order.status}</span>
          <select disabled={updating} value={order.status} onChange={(e) => updateStatus(e.target.value)} className="border rounded-lg px-3 py-2 text-sm bg-white">
            <option value="pending">pending</option>
            <option value="confirmed">confirmed</option>
            <option value="paid">paid</option>
            <option value="processing">processing</option>
            <option value="shipped">shipped</option>
            <option value="fulfilled">fulfilled</option>
            <option value="delivered">delivered</option>
            <option value="cancelled">cancelled</option>
            <option value="refunded">refunded</option>
            <option value="returned">returned</option>
          </select>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <button onClick={() => handleInvoice("html")} disabled={!isPaid} className="px-4 py-2 border rounded-lg text-sm disabled:opacity-40 hover:bg-gray-50">Download Invoice (HTML)</button>
        <button onClick={() => handleInvoice("pdf")} disabled={!isPaid} className="px-4 py-2 border rounded-lg text-sm disabled:opacity-40 hover:bg-gray-50">Download Invoice (PDF)</button>
        <button onClick={handleRefund} className="px-4 py-2 border rounded-lg text-sm hover:bg-gray-50">Refund</button>
        <button
          onClick={async () => {
            if (order.status !== "delivered") {
              toast({ kind: "info", title: "Returns are only valid from delivered orders." });
              return;
            }
            const reason = prompt("Return reason:", "Damaged") || "Customer return";
            try {
              await adminApiExt.createReturn(orderId, [], reason);
              toast({ kind: "info", title: "Return recorded — inventory restocked." });
              fetchOrder();
            } catch (e: any) {
              toast({ kind: "error", title: "Something went wrong", description: e.message || "Return failed" });
            }
          }}
          className="px-4 py-2 border rounded-lg text-sm hover:bg-gray-50"
        >
          Return order
        </button>
        <Link href={`/customers/${order.customer_id}`} className="px-4 py-2 border rounded-lg text-sm hover:bg-gray-50">View Customer</Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow border p-5">
          <h3 className="font-semibold mb-3">Summary</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-gray-500">Total</span><span className="font-bold">₹{((order.total_cents ?? 0) / 100).toFixed(2)}</span></div>
            <div className="flex justify-between"><span className="text-gray-500">Currency</span><span>{order.currency || "INR"}</span></div>
            <div className="flex justify-between"><span className="text-gray-500">Payment</span><span className="text-xs">{order.payment_provider || order.payment?.provider || "—"} {order.payment?.status ? `(${order.payment.status})` : ""}</span></div>
            <div className="flex justify-between"><span className="text-gray-500">Checkout</span><span className="font-mono text-xs">{order.checkout_id ? String(order.checkout_id).slice(0, 8) : "—"}</span></div>
            <div className="flex justify-between"><span className="text-gray-500">Customer</span><Link href={`/customers/${order.customer_id}`} className="text-blue-600 hover:underline">{order.customer_id ? String(order.customer_id).slice(0, 8) : "Guest"}</Link></div>
            {order.discounts_json && order.discounts_json.length > 0 && <div className="flex justify-between"><span className="text-gray-500">Coupons</span><span className="text-xs">{order.discounts_json.join(", ")}</span></div>}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow border p-5">
          <h3 className="font-semibold mb-3">Addresses</h3>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide">Shipping</p>
              <pre className="mt-1 text-xs bg-gray-50 p-2 rounded whitespace-pre-wrap break-words">{JSON.stringify(order.shipping_address_json || order.shipping_address || {}, null, 2)}</pre>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide">Billing</p>
              <pre className="mt-1 text-xs bg-gray-50 p-2 rounded whitespace-pre-wrap break-words">{JSON.stringify(order.billing_address_json || order.billing_address || {}, null, 2)}</pre>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow border p-5">
        <h3 className="font-semibold mb-3">Items — immutable snapshots (price/tax at purchase)</h3>
        {(order.items || order.order_items || order.items_json || []).length === 0 ? (
          <p className="text-sm text-gray-400">No items. {order.items_json ? `${order.items_json.length} in legacy JSON` : ""}</p>
        ) : (
          <div className="space-y-2">
            {(order.items || order.order_items || order.items_json || []).map((it: any, idx: number) => (
              <div key={idx} className="flex justify-between py-2 border-b last:border-0 text-sm">
                <div>
                  <p className="font-medium">{it.product_snapshot?.name || it.name || it.product_id}</p>
                  <p className="text-xs text-gray-400">Qty {it.quantity} • SKU {it.product_snapshot?.sku || it.sku || "—"} • Tax {it.product_snapshot?.tax_class || "standard"}</p>
                </div>
                <span className="font-medium">₹{((it.price_cents ?? 0) / 100).toFixed(2)} × {it.quantity}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-white rounded-lg shadow border p-5">
        <div className="flex justify-between items-center mb-3">
          <h3 className="font-semibold">Fulfillments — tracking</h3>
          <button
            onClick={async () => {
              const tracking = prompt("Tracking number:", "");
              if (tracking === null) return;
              const carrier = prompt("Carrier (Delhivery, Bluedart, DTDC, Ecom):", "Delhivery");
              try {
                await adminApi.createFulfillment(orderId, { tracking_number: tracking || undefined, carrier: carrier || undefined });
                const f = await adminApi.getOrderFulfillments(orderId);
                setFulfillments(Array.isArray(f) ? f : (f as any).data || []);
              } catch (e: any) {
                toast({ kind: "error", title: "Something went wrong", description: e.message });
              }
            }}
            className="text-xs border px-3 py-1.5 rounded hover:bg-gray-50"
          >
            Add Fulfillment
          </button>
        </div>
        {fulfillments.length === 0 ? (
          <p className="text-sm text-gray-400">No fulfillments yet — shipment tracking appears here. Low inventory alerts in Analytics.</p>
        ) : (
          <div className="space-y-2">
            {fulfillments.map((f: any) => (
              <div key={f.id} className="p-3 border rounded text-sm flex justify-between">
                <div>
                  <p><strong>Status:</strong> {f.status}</p>
                  <p className="text-xs text-gray-500">{f.tracking_number ? `Tracking: ${f.tracking_number}` : "No tracking"} {f.carrier ? `| Carrier: ${f.carrier}` : ""}</p>
                </div>
                {f.tracking_number && (
                  <a
                    href={`https://www.${(f.carrier || "dtdc").toLowerCase().replace(/\s+/g, "")}.com/track${f.tracking_number ? `?trackingNumber=${encodeURIComponent(f.tracking_number)}` : ""}`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-blue-600 underline self-center"
                  >
                    Track →
                  </a>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-white rounded-lg shadow border p-5">
        <h3 className="font-semibold mb-2">Audit & Timeline</h3>
        <p className="text-xs text-gray-500">Events drive notifications, CRM, analytics without coupling. Every checkout/order/payment emits immutable events.</p>
        <div className="mt-3 flex gap-2">
          <Link href={`/customers/${order.customer_id}`} className="text-xs text-blue-600 underline">Customer timeline →</Link>
          <span className="text-xs text-gray-300">•</span>
          <span className="text-xs text-gray-400">Order events: checkout.created, payment.succeeded, order.created, order.cod_created</span>
        </div>
      </div>
    </div>
  );
}
