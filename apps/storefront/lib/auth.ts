"use client";

/**
 * Storefront auth helpers.
 *
 * Customer auth state lives entirely client-side: a JWT bearer token in
 * `localStorage.access_token`. These helpers centralise the read/clear
 * logic so pages don't sprinkle `localStorage.getItem("access_token")`
 * everywhere.
 */

export const STOREFRONT_TOKEN_KEY = "access_token";
export const STOREFRONT_REFRESH_KEY = "refresh_token";

export function getStorefrontToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(STOREFRONT_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function isStorefrontLoggedIn(): boolean {
  return !!getStorefrontToken();
}

export function setStorefrontTokens(access: string, refresh?: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STOREFRONT_TOKEN_KEY, access);
    if (refresh) window.localStorage.setItem(STOREFRONT_REFRESH_KEY, refresh);
  } catch {
    /* ignore quota errors */
  }
}

export function clearStorefrontTokens(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(STOREFRONT_TOKEN_KEY);
    window.localStorage.removeItem(STOREFRONT_REFRESH_KEY);
  } catch {
    /* ignore */
  }
}

/**
 * Watches the access_token key so consumers can re-render on login/logout
 * across tabs.
 */
export function subscribeStorefrontAuth(handler: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  const onStorage = (e: StorageEvent) => {
    if (e.key === STOREFRONT_TOKEN_KEY || e.key === STOREFRONT_REFRESH_KEY) handler();
  };
  window.addEventListener("storage", onStorage);
  return () => window.removeEventListener("storage", onStorage);
}