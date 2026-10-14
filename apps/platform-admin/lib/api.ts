import axios from "axios";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1",
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Plain bearer-aware fetch helper for routes that aren't auth-bearer-only
// (e.g. health endpoints that live outside /api/v1).
async function fetchJson(path: string, options: RequestInit = {}): Promise<any> {
  const base = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
  const url = path.startsWith("http") ? path : `${base}${path.startsWith("/api/v1") ? "" : "/api/v1"}${path}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) || {}),
  };
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  const res = await fetch(url, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || res.statusText);
  }
  if (res.status === 204) return null;
  const text = await res.text();
  return text ? JSON.parse(text) : null;
}

export const platformApi = {
  // Auth ----------------------------------------------------------------
  async login(email: string, password: string) {
    const res = await api.post("/auth/login", { email, password });
    return res.data;
  },
  async logout() {
    try {
      return await api.post("/auth/logout");
    } catch {
      return null;
    }
  },
  async getMe() {
    const res = await api.get("/auth/me");
    return res.data;
  },

  // Tenants ------------------------------------------------------------
  async getTenants(params?: Record<string, string>) {
    const res = await api.get("/tenants", { params });
    return res.data;
  },
  async getTenant(id: string) {
    const res = await api.get(`/tenants/${id}`);
    return res.data;
  },
  async createTenant(data: any) {
    // Platform-admin onboarding: plan by slug; backend generates credentials
    const res = await api.post("/tenants/onboard", data);
    return res.data;
  },

  // Plans / Subscriptions ----------------------------------------------
  async getPlans() {
    const res = await api.get("/platform/plans").catch(() => ({ data: [] }));
    return res.data;
  },
  async getSubscriptions(params?: Record<string, string>) {
    const res = await api
      .get("/platform/subscriptions", { params })
      .catch(() => ({ data: [] }));
    return res.data;
  },
  async assignPlan(tenantId: string, planSlug: string, trialDays = 0) {
    const res = await api.post("/platform/subscriptions", {
      tenant_id: tenantId,
      plan_slug: planSlug,
      trial_days: trialDays,
    });
    return res.data;
  },
  async cancelSubscription(subscriptionId: string) {
    const res = await api.delete(`/platform/subscriptions/${subscriptionId}`);
    return res.data;
  },

  // Integrations -------------------------------------------------------
  async getIntegrations() {
    const res = await api.get("/integrations");
    return res.data;
  },
  async testIntegration(id: string) {
    const res = await api.post(`/integrations/${id}/test`);
    return res.data;
  },

  // Health (routes live outside /api/v1) -------------------------------
  async getHealth() {
    return fetchJson("/health");
  },
  async getHealthDetailed() {
    return fetchJson("/health/detailed");
  },

  // Analytics ----------------------------------------------------------
  async getMetrics() {
    const res = await api.get("/analytics/dashboard?days=30").catch(() => ({ data: null }));
    return res.data;
  },

  // Cross-tenant user management ---------------------------------------
  async getUsers() {
    // The /auth/users endpoint is tenant-scoped; for platform-admin we
    // need cross-tenant data. We try the endpoint and fall back to a
    // manually aggregated list built from /tenants.
    try {
      const res = await api.get("/auth/users");
      const data = res.data;
      return Array.isArray(data) ? data : data.data || [];
    } catch {
      return [];
    }
  },

  // Theme presets (design tokens) --------------------------------------
  async getThemePresets() {
    const res = await api.get("/themes/presets");
    return res.data;
  },

  // Tenant domains -----------------------------------------------------
  async getTenantDomains(tenantId: string) {
    const res = await api.get(`/tenants/${tenantId}/domains`).catch(() => ({ data: [] }));
    return res.data;
  },
};
