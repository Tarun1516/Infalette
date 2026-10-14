"use client";

/**
 * Tiny event bus + counter helpers for the storefront cart.
 *
 * Components (header badge, cart page, drawer, etc.) listen on
 * `window` for the `infalette-cart-changed` event. The
 * `refreshCartCount()` helper calls the public cart endpoint and
 * updates `localStorage['infalette-cart-count']`. Components that
 * want a fast, offline-capable counter can subscribe to that key.
 */

export const CART_COUNT_KEY = "infalette-cart-count";
export const CART_TOTAL_KEY = "infalette-cart-total";

type CartSummary = {
  count: number;
  totalCents: number;
};

let inFlight: Promise<void> | null = null;

function emit(tenant?: string) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent("infalette-cart-changed", { detail: { tenant } }));
  // Cross-tab ping via BroadcastChannel
  try {
    const bc = new BroadcastChannel("infalette-cart");
    bc.postMessage({ tenant });
    bc.close();
  } catch {
    /* unsupported */
  }
  // Last-ditch cross-tab sync (fallback)
  try {
    localStorage.setItem("infalette-cart-bus", String(Date.now()));
  } catch {
    /* ignore quota errors */
  }
}

export function notifyCartChanged(tenant?: string) {
  emit(tenant);
}

/**
 * Fetch the current cart and update the count + total in localStorage.
 * Safe to call repeatedly; concurrent calls coalesce into one request.
 */
export async function refreshCartCount(tenant?: string): Promise<CartSummary> {
  if (typeof window === "undefined") return { count: 0, totalCents: 0 };
  if (inFlight) {
    await inFlight;
    return readFromStorage();
  }
  inFlight = (async () => {
    try {
      // Discover tenant from the URL path if not explicitly given.
      const t = tenant || (window.location.pathname.split("/")[1] || "");
      if (!t) return;
      const res = await fetch(`/api/cart-summary?tenant=${encodeURIComponent(t)}`, {
        cache: "no-store",
      });
      if (!res.ok) return;
      const data: CartSummary = await res.json();
      localStorage.setItem(CART_COUNT_KEY, String(data.count));
      localStorage.setItem(CART_TOTAL_KEY, String(data.totalCents));
    } catch {
      /* offline / SSR — leave whatever was previously cached */
    } finally {
      inFlight = null;
    }
  })();
  await inFlight;
  return readFromStorage();
}

export function readFromStorage(): CartSummary {
  if (typeof window === "undefined") return { count: 0, totalCents: 0 };
  const count = Number(localStorage.getItem(CART_COUNT_KEY) || 0);
  const totalCents = Number(localStorage.getItem(CART_TOTAL_KEY) || 0);
  return { count: Number.isFinite(count) ? count : 0, totalCents: Number.isFinite(totalCents) ? totalCents : 0 };
}