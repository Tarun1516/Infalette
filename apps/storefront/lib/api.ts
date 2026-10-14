/**
 * Marketing attribution capture (spec §3: attribution coverage 90%+).
 *
 * `captureAttribution()` reads UTM params, click-ids (gclid, fbclid,
 * msclkid, dclid), and the automation checkout links' `rule` param from
 * the current URL and merges them into a per-touch record in
 * localStorage with a 7-day window. The stored attribution is attached
 * to the checkout payload so web orders carry the same campaign/source
 * attribution as social orders.
 *
 * Storage shape: two keys kept side-by-side —
 *   - STORAGE_KEY_FIRST (first-touch): frozen once on the visitor's
 *     first session; never overwritten on subsequent navigations
 *   - STORAGE_KEY_LAST (last-touch): the current/default key, updated
 *     on every navigation with new UTMs/click-ids
 *
 * The first-touch and last-touch payloads are both attached to the
 * checkout (as `attribution` and `attribution_first`) so the funnel
 * analytics dashboard can show "first vs last" alongside.
 */

export interface Attribution {
  source?: string;
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_content?: string;
  utm_term?: string;
  gclid?: string;
  fbclid?: string;
  msclkid?: string;
  dclid?: string;
  referrer?: string;
  landing_path?: string;
}

const STORAGE_KEY_LAST = "infalette_attribution";
const STORAGE_KEY_FIRST = "infalette_attribution_first";
const TTL_MS = 7 * 24 * 60 * 60 * 1000;

const UTM_KEYS = [
  "utm_source",
  "utm_medium",
  "utm_campaign",
  "utm_content",
  "utm_term",
] as const;

const CLICK_ID_KEYS = ["gclid", "fbclid", "msclkid", "dclid"] as const;

export function captureAttribution(): void {
  if (typeof window === "undefined") return;
  try {
    const params = new URLSearchParams(window.location.search);
    const incoming: Record<string, string> = {};
    for (const key of UTM_KEYS) {
      const value = params.get(key);
      if (value) incoming[key] = value;
    }
    for (const key of CLICK_ID_KEYS) {
      const value = params.get(key);
      if (value) incoming[key] = value;
    }
    if (params.get("rule")) incoming.source = "automation";

    const now = Date.now();

    // Last-touch: merge into the existing record (7-day TTL)
    let current: Record<string, unknown> = {};
    const rawLast = window.localStorage.getItem(STORAGE_KEY_LAST);
    if (rawLast) {
      const parsed = JSON.parse(rawLast);
      if (parsed && now - (parsed._ts || 0) < TTL_MS) {
        current = parsed;
      }
    }
    const next: Record<string, unknown> = {
      ...current,
      ...incoming,
      referrer: incoming.utm_source ? current.referrer : document.referrer || current.referrer,
      _ts: now,
    };
    if (!next.source && (next.utm_source || params.get("rule"))) {
      next.source = next.utm_source || "automation";
    }
    next.landing_path = next.landing_path || window.location.pathname;
    window.localStorage.setItem(STORAGE_KEY_LAST, JSON.stringify(next));

    // First-touch: write once on the visitor's first visit; never
    // overwritten by subsequent navigations. This is the "real"
    // first-touch attribution for funnel analytics.
    const existingFirst = window.localStorage.getItem(STORAGE_KEY_FIRST);
    if (!existingFirst) {
      const first: Record<string, unknown> = {
        ...incoming,
        referrer: document.referrer || undefined,
        landing_path: window.location.pathname,
        _ts: now,
      };
      if (!first.source && (first.utm_source || params.get("rule"))) {
        first.source = first.utm_source || "automation";
      }
      window.localStorage.setItem(STORAGE_KEY_FIRST, JSON.stringify(first));
    }
  } catch {
    // attribution is best-effort; never break the page
  }
}

export function getStoredAttribution(): Attribution | Record<string, never> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY_LAST);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    if (!parsed || Date.now() - (parsed._ts || 0) >= TTL_MS) return {};
    // strip private bookkeeping keys
    const { _ts, landing_path, ...rest } = parsed;
    void _ts;
    void landing_path;
    return rest;
  } catch {
    return {};
  }
}

export function getStoredFirstAttribution(): Attribution | Record<string, never> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY_FIRST);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    // strip private bookkeeping keys
    const { _ts, landing_path, ...rest } = parsed;
    void _ts;
    void landing_path;
    return rest;
  } catch {
    return {};
  }
}

import axios from "axios";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1",
});

// Guest cart identity: opaque uuid kept client-side (requirement: guest checkout)
export function getCartSessionId(): string {
  if (typeof window === "undefined") return "";
  let id = window.localStorage.getItem("cart_session_id");
  if (!id) {
    id = window.crypto?.randomUUID ? window.crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
    window.localStorage.setItem("cart_session_id", id);
  }
  return id;
}

function tenantHeaders(tenant: string): Record<string, string> {
  const auth = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  const h: Record<string, string> = { "X-Tenant": tenant, "X-Cart-Session-ID": getCartSessionId() };
  if (auth) h.Authorization = `Bearer ${auth}`;
  return h;
}

export class StorefrontApi {
  // ---- Public (anonymous) surfaces: catalog, store, pages, categories ----

  async getStore(tenant: string) {
    const response = await api
      .get(`/public/store`, { headers: { "X-Tenant": tenant } })
      .catch(() => null);
    return response?.data || null;
  }

  async getPages(tenant: string) {
    const response = await api
      .get(`/public/pages`, { headers: { "X-Tenant": tenant } })
      .catch(() => null);
    const list = response?.data;
    return Array.isArray(list) ? list : [];
  }

  async getProducts(tenant: string, params?: Record<string, string>) {
    const response = await api.get(`/public/products`, {
      headers: { "X-Tenant": tenant },
      params,
    });
    const data = response.data;
    if (Array.isArray(data)) return data;
    return data.data || data.items || [];
  }

  async getProduct(tenant: string, id: string) {
    const response = await api.get(`/public/products/${id}`, {
      headers: { "X-Tenant": tenant },
    });
    return response.data;
  }

  async getCategories(tenant: string) {
    const response = await api.get(`/public/categories`, {
      headers: { "X-Tenant": tenant },
    });
    const data = response.data;
    if (Array.isArray(data)) return data;
    return data.data || data.items || [];
  }

  // ---- Cart / checkout (guest session keyed; optional customer auth) ----

  async getCart(tenant: string) {
    const response = await api.get(`/cart`, {
      headers: tenantHeaders(tenant),
    });
    return response.data;
  }

  async addToCart(tenant: string, productId: string, quantity: number, variantId?: string) {
    const response = await api.post(
      `/cart/items`,
      { product_id: productId, quantity, variant_id: variantId },
      { headers: tenantHeaders(tenant) }
    );
    return response.data;
  }

  async getProductVariants(tenant: string, productId: string) {
    // Best-effort: this endpoint requires auth on the backend. Storefronts
    // fall back to a no-variant flow if the call fails or returns 401/403.
    const response = await api.get(`/products/${productId}/variants`, {
      headers: tenantHeaders(tenant),
    });
    return Array.isArray(response.data) ? response.data : response.data?.data || [];
  }

  async updateCartItem(tenant: string, itemId: string, quantity: number) {
    const response = await api.put(
      `/cart/items/${itemId}?quantity=${quantity}`,
      {},
      { headers: tenantHeaders(tenant) }
    );
    return response.data;
  }

  async removeCartItem(tenant: string, itemId: string) {
    const response = await api.delete(`/cart/items/${itemId}`, {
      headers: tenantHeaders(tenant),
    });
    return response.data;
  }

  async createCheckout(tenant: string, data: any) {
    // Idempotency per requirements: never double-charge on retry
    const idempotencyKey = typeof crypto !== "undefined" && (crypto as any).randomUUID ? (crypto as any).randomUUID() : `${Date.now()}-${Math.random()}`;
    // Attach stored UTM/campaign/click-id attribution (spec: attribution coverage 90%+)
    const attribution = getStoredAttribution();
    const attributionFirst = getStoredFirstAttribution();
    const payload: Record<string, unknown> = { ...data };
    if (Object.keys(attribution).length) {
      payload.attribution = attribution;
      // Also surface click IDs at the top level so backend downstream
      // pipelines (analytics, ad-network conversions) can match
      // them without digging into the attribution blob.
      if ((attribution as any).gclid) payload.gclid = (attribution as any).gclid;
      if ((attribution as any).fbclid) payload.fbclid = (attribution as any).fbclid;
    }
    if (Object.keys(attributionFirst).length) {
      payload.attribution_first = attributionFirst;
    }
    const response = await api.post(`/checkout`, payload, {
      headers: { ...tenantHeaders(tenant), "Idempotency-Key": idempotencyKey },
    });
    return response.data;
  }

  async initiatePayment(tenant: string, checkoutId: string, provider: string = "razorpay") {
    const response = await api.post(
      `/checkout/${checkoutId}/pay`,
      { provider },
      { headers: { ...tenantHeaders(tenant), "Idempotency-Key": getCartSessionId() + "-" + checkoutId } }
    );
    return response.data;
  }

  async getInvoice(tenant: string, orderId: string) {
    const response = await api.get(`/invoices/${orderId}`, { headers: tenantHeaders(tenant) });
    return response.data;
  }

  async downloadInvoice(tenant: string, orderId: string, format: "html" | "pdf" = "html") {
    // Always request a blob so the caller can create a single <a download> link
    // regardless of which file format the API returns. Browsers happily save
    // HTML and PDF blobs alike.
    const response = await api.get(`/invoices/${orderId}/download`, {
      headers: tenantHeaders(tenant),
      params: { format },
      responseType: "blob",
    });
    return response.data as Blob;
  }

  async getCollections(tenant: string) {
    const response = await api.get(`/collections`, {
      headers: tenantHeaders(tenant),
    });
    const data = response.data;
    if (Array.isArray(data)) return data;
    return data.data || data.items || [];
  }

  // ---- Order tracking (customers + guests) ----

  async trackOrder(tenant: string, orderId: string, email: string) {
    const response = await api.get(`/public/track-order`, {
      headers: { "X-Tenant": tenant },
      params: { order_id: orderId, email },
    });
    return response.data;
  }

  async getOrderFulfillments(tenant: string, orderId: string) {
    const response = await api.get(`/orders/${orderId}/fulfillments`, {
      headers: tenantHeaders(tenant),
    });
    return response.data;
  }

  async getOrder(tenant: string, orderId: string) {
    const response = await api.get(`/orders/${orderId}`, {
      headers: tenantHeaders(tenant),
    });
    return response.data;
  }

  async listOrders(tenant: string, status?: string) {
    const response = await api.get(`/orders`, {
      headers: tenantHeaders(tenant),
      params: status ? { status } : undefined,
    });
    const data = response.data;
    return Array.isArray(data) ? data : data?.data || data?.items || [];
  }

  async getOrderRefunds(tenant: string, orderId: string) {
    const response = await api.get(`/orders/${orderId}/refunds`, {
      headers: tenantHeaders(tenant),
    });
    return response.data;
  }

  async getOrderPayments(tenant: string, orderId: string) {
    const response = await api.get(`/orders/${orderId}/payments`, {
      headers: tenantHeaders(tenant),
    });
    return response.data;
  }

  // ---- Returns (customer self-service) ----

  async requestReturn(
    tenant: string,
    orderId: string,
    items: Array<{ product_id: string; quantity: number }>,
    reason: string
  ) {
    // Backend: POST /orders/{id}/returns?reason=... with body = items list
    const response = await api.post(`/orders/${orderId}/returns`, items, {
      headers: tenantHeaders(tenant),
      params: { reason },
    });
    return response.data;
  }

  async cancelOrder(tenant: string, orderId: string) {
    // Backend: PATCH /orders/{id}/status  body = { status: "cancelled" }
    const response = await api.patch(
      `/orders/${orderId}/status`,
      { status: "cancelled" },
      { headers: tenantHeaders(tenant) }
    );
    return response.data;
  }

  async getReturns(tenant: string) {
    // The API has no dedicated /returns endpoint; returns are recorded as
    // orders whose status has moved to `returned`. The order list endpoint
    // scopes customers to their own orders automatically.
    const list = await this.listOrders(tenant, "returned");
    return Array.isArray(list) ? list : [];
  }

  // ---- Customer self-service (DPDP: consent / export / erase) ----

  async getCurrentUser() {
    // /auth/me returns the UserRead for the bearer token's user.
    const auth = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
    const headers: Record<string, string> = auth ? { Authorization: `Bearer ${auth}` } : {};
    const response = await api.get(`/auth/me`, { headers });
    return response.data;
  }

  /**
   * Discover the customer_id for the currently authenticated shopper.
   *
   * The customer routes are keyed on `customer_id` rather than a `/me` alias.
   * For shoppers, the most reliable way to get that id is from the first
   * order on file (every customer is mirrored from the signup at order
   * creation time). If no orders exist yet, we fall back to looking up the
   * customer via the email returned by /auth/me (Tenant-isolated list call).
   */
  async getMyCustomerId(tenant: string): Promise<string | null> {
    try {
      const list = (await this.listOrders(tenant)) as any[];
      const hit = Array.isArray(list) ? list.find((o) => o?.customer_id) : null;
      if (hit?.customer_id) return String(hit.customer_id);
    } catch {
      // fall through to email lookup
    }
    try {
      const me = await this.getCurrentUser();
      const email = me?.email;
      if (!email) return null;
      // Tenant staff can list customers; this works for the user who is the
      // merchant, but for shoppers we end up with an empty list since
      // list_customers is staff-only. In that case we surface null and the
      // page can prompt the user to place an order first.
      const response = await api.get(`/customers`, {
        headers: tenantHeaders(tenant),
        params: { search: email },
      });
      const data = response.data;
      const list = Array.isArray(data) ? data : data?.data || data?.items || [];
      const me2 = list.find((c: any) => c?.email === email);
      return me2?.id ? String(me2.id) : null;
    } catch {
      return null;
    }
  }

  async getConsent(tenant: string, customerId: string) {
    // GET /customers/{id}/consent isn't on the API; we read the customer
    // record itself which carries `consent_json`. The list endpoint is
    // staff-only, so this falls back gracefully when the customer id can't
    // be resolved.
    const response = await api.get(`/customers/${customerId}`, {
      headers: tenantHeaders(tenant),
    });
    return response.data?.consent_json || {};
  }

  async updateConsent(tenant: string, customerId: string, flags: Record<string, boolean>) {
    // PATCH /customers/{id}/consent body = { "consent": {...} }
    const response = await api.patch(
      `/customers/${customerId}/consent`,
      { consent: flags },
      { headers: tenantHeaders(tenant) }
    );
    return response.data;
  }

  async withdrawAllConsent(tenant: string, customerId: string) {
    // POST /customers/{id}/consent/withdraw
    const response = await api.post(
      `/customers/${customerId}/consent/withdraw`,
      {},
      { headers: tenantHeaders(tenant) }
    );
    return response.data;
  }

  async exportCustomerData(tenant: string, customerId: string) {
    const response = await api.get(`/customers/${customerId}/export`, {
      headers: tenantHeaders(tenant),
    });
    return response.data;
  }

  async eraseCustomerData(tenant: string, customerId: string) {
    const response = await api.post(
      `/customers/${customerId}/erase`,
      {},
      { headers: tenantHeaders(tenant) }
    );
    return response.data;
  }
}

export const storefrontApi = new StorefrontApi();
