"use client";

import { toast } from "@/components/toaster";
import { useEffect, useState } from "react";
import Link from "next/link";
import { storefrontApi } from "@/lib/api";
import { notifyCartChanged } from "@/lib/cart-events";

export default function CartPage({ params }: { params: { tenant: string } }) {
  const [cart, setCart] = useState<any>(null);
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState<string | null>(null);

  const fetchCart = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await storefrontApi.getCart(params.tenant);
      const c = data?.cart || data?.data || data;
      setCart(c);
      const list = c?.items || c?.cart_items || data?.items || [];
      setItems(list);
    } catch (e: any) {
      setError(e.message || "Failed to load cart");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCart();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.tenant]);

  const updateQty = async (itemId: string, qty: number) => {
    if (qty < 1) return;
    setUpdating(itemId);
    try {
      await storefrontApi.updateCartItem(params.tenant, itemId, qty);
      await fetchCart();
      notifyCartChanged(params.tenant);
    } catch (e: any) {
      toast({ kind: "error", title: "Something went wrong", description: e.message });
    } finally {
      setUpdating(null);
    }
  };

  const removeItem = async (itemId: string) => {
    setUpdating(itemId);
    try {
      await storefrontApi.removeCartItem(params.tenant, itemId);
      await fetchCart();
      notifyCartChanged(params.tenant);
    } catch (e: any) {
      toast({ kind: "error", title: "Something went wrong", description: e.message });
    } finally {
      setUpdating(null);
    }
  };

  if (loading)
    return (
      <div className="max-w-5xl mx-auto px-6 py-24 text-center text-[15px] text-gray-500 dark:text-neutral-400">
        Loading your cart…
      </div>
    );
  if (error)
    return (
      <div className="max-w-3xl mx-auto px-6 py-24 text-center text-[14px] text-red-600">
        {error}
      </div>
    );

  const isEmpty = !cart || items.length === 0;
  const total =
    cart?.total_cents ??
    items.reduce((sum: number, it: any) => sum + (it.price_cents ?? 0) * (it.quantity ?? 1), 0);
  const itemCount = items.reduce((sum: number, it: any) => sum + (it.quantity ?? 1), 0);

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-12">
      <header className="mb-10">
        <p className="text-[12px] uppercase tracking-[0.18em] text-gray-500 dark:text-neutral-500">
          Your bag
        </p>
        <h1 className="mt-2 text-[36px] sm:text-[44px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
          {isEmpty ? "Your cart is empty." : `Cart — ${itemCount} item${itemCount === 1 ? "" : "s"}.`}
        </h1>
        {!isEmpty && (
          <p className="mt-2 text-[15px] text-gray-500 dark:text-neutral-400">
            Review your selections before checkout.
          </p>
        )}
      </header>

      {isEmpty ? (
        <div className="rounded-2xl border border-dashed border-gray-300 dark:border-neutral-800 py-20 px-6 text-center">
          <p className="text-[15px] text-gray-500 dark:text-neutral-400">
            Once you add products, they'll appear here.
          </p>
          <Link
            href={`/${params.tenant}/products`}
            className="mt-6 inline-flex h-10 px-6 items-center justify-center rounded-full bg-gray-900 dark:bg-white text-white dark:text-black text-[14px] font-medium hover:opacity-90 transition-opacity"
          >
            Continue shopping
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
          {/* Items */}
          <div className="lg:col-span-2 rounded-2xl bg-white dark:bg-neutral-950 divide-y divide-gray-100 dark:divide-neutral-900">
            {items.map((it: any) => (
              <div key={it.id} className="flex gap-4 py-6 first:pt-0">
                <Link
                  href={`/${params.tenant}/products/${it.product_id}`}
                  className="flex-shrink-0 w-24 h-24 sm:w-28 sm:h-28 rounded-xl bg-gray-100 dark:bg-neutral-900 overflow-hidden"
                >
                  {it.image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={it.image_url} alt={it.name || it.product?.name || "Product"} className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-xs text-gray-400">
                      No image
                    </div>
                  )}
                </Link>
                <div className="flex-1 min-w-0">
                  <Link
                    href={`/${params.tenant}/products/${it.product_id}`}
                    className="text-[15px] font-medium text-gray-900 dark:text-neutral-100 hover:underline truncate block"
                  >
                    {it.product?.name || it.name || it.product_name || "Product"}
                  </Link>
                  <p className="mt-1 text-[12px] text-gray-500 dark:text-neutral-500">
                    ₹{((it.price_cents ?? 0) / 100).toFixed(2)} each
                  </p>
                  <div className="mt-3 flex items-center gap-2">
                    <button
                      disabled={!!updating}
                      onClick={() => updateQty(it.id, (it.quantity || 1) - 1)}
                      className="w-7 h-7 border border-gray-200 dark:border-neutral-800 rounded-full text-sm disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-neutral-900"
                    >
                      −
                    </button>
                    <span className="text-[14px] w-6 text-center">{it.quantity}</span>
                    <button
                      disabled={!!updating}
                      onClick={() => updateQty(it.id, (it.quantity || 1) + 1)}
                      className="w-7 h-7 border border-gray-200 dark:border-neutral-800 rounded-full text-sm disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-neutral-900"
                    >
                      +
                    </button>
                    <button
                      onClick={() => removeItem(it.id)}
                      className="ml-3 text-[12px] text-gray-500 dark:text-neutral-400 hover:text-red-600 hover:underline"
                    >
                      Remove
                    </button>
                  </div>
                </div>
                <p className="text-[14px] font-medium text-gray-900 dark:text-neutral-100 whitespace-nowrap">
                  ₹{(((it.price_cents ?? 0) * (it.quantity ?? 1)) / 100).toFixed(2)}
                </p>
              </div>
            ))}
          </div>

          {/* Summary */}
          <aside className="rounded-2xl bg-gray-50 dark:bg-neutral-950 p-6 h-fit lg:sticky lg:top-20">
            <h2 className="text-[15px] font-semibold text-gray-900 dark:text-neutral-100">
              Order summary
            </h2>
            <div className="mt-4 space-y-2 text-[14px]">
              <div className="flex justify-between text-gray-600 dark:text-neutral-400">
                <span>Subtotal</span>
                <span>₹{(total / 100).toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-gray-600 dark:text-neutral-400">
                <span>Shipping</span>
                <span className="text-gray-500 dark:text-neutral-500">Calculated at checkout</span>
              </div>
            </div>
            <div className="mt-4 pt-4 border-t border-gray-200 dark:border-neutral-800 flex justify-between text-[15px] font-semibold text-gray-900 dark:text-neutral-100">
              <span>Total</span>
              <span>₹{(total / 100).toFixed(2)}</span>
            </div>
            <Link
              href={`/${params.tenant}/checkout`}
              className="mt-6 inline-flex h-11 w-full items-center justify-center rounded-full bg-blue-600 text-white text-[14px] font-medium hover:bg-blue-700 transition-colors"
            >
              Proceed to checkout
            </Link>
            <Link
              href={`/${params.tenant}/products`}
              className="mt-3 inline-flex h-11 w-full items-center justify-center rounded-full bg-white dark:bg-neutral-900 border border-gray-200 dark:border-neutral-800 text-[14px] font-medium text-gray-900 dark:text-neutral-100 hover:bg-gray-50 dark:hover:bg-neutral-800 transition-colors"
            >
              Continue shopping
            </Link>
            <p className="mt-4 text-[12px] text-gray-500 dark:text-neutral-500 text-center">
              Secure checkout · Razorpay, Stripe or COD · Inventory reserved on checkout.
            </p>
          </aside>
        </div>
      )}
    </div>
  );
}