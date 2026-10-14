"use client";

import { useEffect } from "react";
import { refreshCartCount } from "@/lib/cart-events";

/**
 * CartRefreshBridge — listens for cart change events dispatched by the
 * add-to-cart / remove / update flows and re-fetches the cart summary
 * so any component subscribed to the cart count can refresh without
 * a full page reload. Also keeps multiple tabs in sync via the
 * BroadcastChannel API + the storage event.
 *
 * Mount once at the root layout.
 */
export function CartRefreshBridge() {
  useEffect(() => {
    const handler = () => {
      void refreshCartCount();
    };
    if (typeof window === "undefined") return;

    window.addEventListener("infalette-cart-changed", handler);

    let bc: BroadcastChannel | null = null;
    try {
      bc = new BroadcastChannel("infalette-cart");
      bc.onmessage = handler;
    } catch {
      /* BroadcastChannel not supported — fall back to storage events */
    }

    const onStorage = (e: StorageEvent) => {
      if (e.key === "infalette-cart-bus") handler();
    };
    window.addEventListener("storage", onStorage);

    // Initial fetch so the cart counter is up to date on first paint.
    void refreshCartCount();

    return () => {
      window.removeEventListener("infalette-cart-changed", handler);
      window.removeEventListener("storage", onStorage);
      bc?.close();
    };
  }, []);

  return null;
}