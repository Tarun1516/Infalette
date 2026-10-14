/**
 * API client for the Infalette Admin application.
 * Connects to the FastAPI backend with proper authentication and tenant isolation.
 */

const RAW_API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_URL = RAW_API_URL.endsWith("/api/v1") ? RAW_API_URL : `${RAW_API_URL.replace(/\/$/, "")}/api/v1`;

interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  per_page: number;
}

class ApiClient {
  private baseUrl: string;
  private token: string | null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
    this.token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  }

  setToken(token: string | null) {
    this.token = token;
    if (typeof window !== "undefined") {
      if (token) {
        localStorage.setItem("access_token", token);
      } else {
        localStorage.removeItem("access_token");
      }
    }
  }

  getToken(): string | null {
    if (typeof window !== "undefined") {
      return localStorage.getItem("access_token");
    }
    return this.token;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };

    const token = this.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || error.message || response.statusText);
    }

    if (response.status === 204) return undefined as T;
    const text = await response.text();
    return text ? JSON.parse(text) : (undefined as T);
  }

  // Auth
  async login(email: string, password: string): Promise<{ access_token: string; refresh_token: string }> {
    return this.request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  }

  async logout(): Promise<void> {
    return this.request("/auth/logout", { method: "POST" });
  }

  async getProfile(): Promise<any> {
    return this.request("/auth/me");
  }

  // Tenants
  async getTenants(params?: Record<string, string>): Promise<PaginatedResponse<any>> {
    const query = new URLSearchParams(params).toString();
    return this.request(`/tenants${query ? `?${query}` : ""}`);
  }

  async getTenant(id: string): Promise<any> {
    return this.request(`/tenants/${id}`);
  }

  async createTenant(data: any): Promise<any> {
    return this.request("/tenants", { method: "POST", body: JSON.stringify(data) });
  }

  async updateTenant(id: string, data: any): Promise<any> {
    return this.request(`/tenants/${id}`, { method: "PATCH", body: JSON.stringify(data) });
  }

  // Products
  async getProducts(params?: Record<string, string>): Promise<PaginatedResponse<any> | any[]> {
    const query = new URLSearchParams(params).toString();
    return this.request(`/products${query ? `?${query}` : ""}`);
  }

  async getProduct(id: string): Promise<any> {
    return this.request(`/products/${id}`);
  }

  async createProduct(data: any): Promise<any> {
    return this.request("/products", { method: "POST", body: JSON.stringify(data) });
  }

  async updateProduct(id: string, data: any): Promise<any> {
    return this.request(`/products/${id}`, { method: "PATCH", body: JSON.stringify(data) });
  }

  // Lightweight partial update for the inventory stepper. Doesn't
  // require the full ProductCreate shape, so callers can patch just
  // inventory_quantity without sending every other field.
  async adjustStock(id: string, inventory_quantity: number): Promise<any> {
    return this.request(`/products/${id}/stock`, {
      method: "PATCH",
      body: JSON.stringify({ inventory_quantity }),
    });
  }

  async deleteProduct(id: string): Promise<void> {
    return this.request(`/products/${id}`, { method: "DELETE" });
  }

  async importProducts(
    file: File,
  ): Promise<{ created: number; updated: number; skipped: number; errors: string[] }> {
    // FormData upload: never set Content-Type manually (browser sets the
    // multipart boundary); Authorization only.
    const form = new FormData();
    form.append("file", file);
    const token = this.getToken();
    const response = await fetch(`${this.baseUrl}/products/import`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      body: form,
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || error.message || response.statusText);
    }
    return response.json();
  }

  // Product Variants
  async getVariants(productId: string): Promise<any[]> {
    const res: any = await this.request(`/products/${productId}/variants`);
    return Array.isArray(res) ? res : res.data || [];
  }

  async createVariant(productId: string, data: any): Promise<any> {
    return this.request(`/products/${productId}/variants`, { method: "POST", body: JSON.stringify(data) });
  }

  async updateVariant(productId: string, variantId: string, data: any): Promise<any> {
    return this.request(`/products/${productId}/variants/${variantId}`, { method: "PATCH", body: JSON.stringify(data) });
  }

  async deleteVariant(productId: string, variantId: string): Promise<void> {
    return this.request(`/products/${productId}/variants/${variantId}`, { method: "DELETE" });
  }

  // Categories
  async getCategories(params?: Record<string, string>): Promise<any> {
    const query = new URLSearchParams(params).toString();
    return this.request(`/categories${query ? `?${query}` : ""}`);
  }

  async getCategoryTree(): Promise<any[]> {
    return this.request("/categories/tree");
  }

  // Collections
  async getCollections(params?: Record<string, string>): Promise<any> {
    const query = new URLSearchParams(params).toString();
    return this.request(`/collections${query ? `?${query}` : ""}`);
  }

  // Orders
  async getOrders(params?: Record<string, string>): Promise<PaginatedResponse<any> | any> {
    const query = new URLSearchParams(params).toString();
    return this.request(`/orders${query ? `?${query}` : ""}`);
  }

  async getOrder(id: string): Promise<any> {
    return this.request(`/orders/${id}`);
  }

  async updateOrderStatus(id: string, status: string): Promise<any> {
    return this.request(`/orders/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
  }

  async getOrderFulfillments(id: string): Promise<any[]> {
    return this.request(`/orders/${id}/fulfillments`);
  }

  async createFulfillment(orderId: string, data: any): Promise<any> {
    return this.request(`/orders/${orderId}/fulfillments`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async createRefund(orderId: string, data: any): Promise<any> {
    return this.request(`/orders/${orderId}/refunds`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  // Customers
  async getCustomers(params?: Record<string, string>): Promise<PaginatedResponse<any> | any> {
    const query = new URLSearchParams(params).toString();
    return this.request(`/customers${query ? `?${query}` : ""}`);
  }

  async getCustomer(id: string): Promise<any> {
    return this.request(`/customers/${id}`);
  }

  async updateCustomer(id: string, data: any): Promise<any> {
    return this.request(`/customers/${id}`, { method: "PATCH", body: JSON.stringify(data) });
  }

  async getCustomerOrders(customerId: string): Promise<any[]> {
    return this.request(`/customers/${customerId}/orders`);
  }

  async getCustomerStats(): Promise<any> {
    return this.request("/customers/stats/overview");
  }

  // Conversations
  async getConversations(params?: Record<string, string>): Promise<any> {
    const query = new URLSearchParams(params).toString();
    return this.request(`/conversations${query ? `?${query}` : ""}`);
  }

  async getConversation(id: string): Promise<any> {
    return this.request(`/conversations/${id}`);
  }

  async getConversationMessages(id: string): Promise<any[]> {
    return this.request(`/conversations/${id}/messages`);
  }

  async sendMessage(conversationId: string, content: string): Promise<any> {
    return this.request(`/conversations/${conversationId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
    });
  }

  async assignConversation(conversationId: string, userId: string): Promise<any> {
    return this.request(`/conversations/${conversationId}/assign`, {
      method: "POST",
      body: JSON.stringify({ user_id: userId }),
    });
  }

  async closeConversation(conversationId: string): Promise<any> {
    return this.request(`/conversations/${conversationId}/close`, { method: "POST" });
  }

  // Leads
  async getLeads(params?: Record<string, string>): Promise<PaginatedResponse<any> | any> {
    const query = new URLSearchParams(params).toString();
    return this.request(`/leads${query ? `?${query}` : ""}`);
  }

  async getLead(id: string): Promise<any> {
    return this.request(`/leads/${id}`);
  }

  async createLead(data: any): Promise<any> {
    return this.request("/leads", { method: "POST", body: JSON.stringify(data) });
  }

  async updateLead(id: string, data: any): Promise<any> {
    return this.request(`/leads/${id}`, { method: "PATCH", body: JSON.stringify(data) });
  }

  async convertLead(id: string): Promise<any> {
    return this.request(`/leads/${id}/convert`, { method: "POST" });
  }

  async updateLeadStage(id: string, stage: string): Promise<any> {
    return this.request(`/leads/${id}/stage`, { method: "PATCH", body: JSON.stringify({ stage }) });
  }

  async getLeadTimeline(id: string): Promise<any[]> {
    const res: any = await this.request(`/leads/${id}/timeline`);
    return Array.isArray(res) ? res : res?.data || [];
  }

  async bulkImportLeads(file: File): Promise<any> {
    const formData = new FormData();
    formData.append("file", file);
    const token = this.getToken();
    return fetch(`${this.baseUrl}/leads/import`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    }).then((r) => r.json());
  }

  // Automation
  async getAutomationRules(params?: Record<string, string>): Promise<any> {
    const query = new URLSearchParams(params).toString();
    return this.request(`/automation${query ? `?${query}` : ""}`);
  }

  async getAutomationRule(id: string): Promise<any> {
    return this.request(`/automation/${id}`);
  }

  async createAutomationRule(data: any): Promise<any> {
    return this.request("/automation", { method: "POST", body: JSON.stringify(data) });
  }

  async updateAutomationRule(id: string, data: any): Promise<any> {
    return this.request(`/automation/${id}`, { method: "PATCH", body: JSON.stringify(data) });
  }

  async toggleAutomationRule(id: string): Promise<any> {
    return this.request(`/automation/${id}/toggle`, { method: "POST" });
  }

  async deleteAutomationRule(id: string): Promise<void> {
    return this.request(`/automation/${id}`, { method: "DELETE" });
  }

  async testAutomationRule(id: string, payload: any): Promise<any> {
    return this.request(`/automation/${id}/test`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  // Analytics
  async getDashboardData(days: number = 30): Promise<any> {
    return this.request(`/analytics/dashboard?days=${days}`);
  }

  async getSalesAnalytics(days: number = 30): Promise<any> {
    return this.request(`/analytics/sales?days=${days}`);
  }

  async getTopProducts(limit: number = 10): Promise<any[]> {
    return this.request(`/analytics/top-products?limit=${limit}`);
  }

  async getFunnelData(days: number = 30): Promise<any> {
    return this.request(`/analytics/funnel?days=${days}`);
  }

  async getChannelAttribution(days: number = 30): Promise<any> {
    return this.request(`/analytics/attribution?days=${days}`);
  }

  async getSocialFunnel(days: number = 30): Promise<any> {
    return this.request(`/analytics/social-funnel?days=${days}`);
  }

  async getAbandonedSegments(hours: number = 24): Promise<any> {
    return this.request(`/analytics/abandoned-segments?hours=${hours}`);
  }

  async getReportSchedules(): Promise<any[]> {
    const res: any = await this.request("/reports");
    return Array.isArray(res) ? res : res.data || [];
  }

  async createReportSchedule(data: any): Promise<any> {
    return this.request("/reports", { method: "POST", body: JSON.stringify(data) });
  }

  async deleteReportSchedule(id: string): Promise<void> {
    await this.request(`/reports/${id}`, { method: "DELETE" });
  }

  // Integrations
  async getIntegrations(): Promise<any[]> {
    const res: any = await this.request("/integrations");
    return Array.isArray(res) ? res : res.data || [];
  }

  async getIntegration(id: string): Promise<any> {
    return this.request(`/integrations/${id}`);
  }

  async createIntegration(data: any): Promise<any> {
    return this.request("/integrations", { method: "POST", body: JSON.stringify(data) });
  }

  async updateIntegration(id: string, data: any): Promise<any> {
    return this.request(`/integrations/${id}`, { method: "PATCH", body: JSON.stringify(data) });
  }

  async deleteIntegration(id: string): Promise<void> {
    return this.request(`/integrations/${id}`, { method: "DELETE" });
  }

  async testIntegration(id: string): Promise<any> {
    return this.request(`/integrations/${id}/test`, { method: "POST" });
  }

  async getAvailableProviders(): Promise<any[]> {
    return this.request("/integrations/providers");
  }

  // Webhooks
  async getWebhooks(): Promise<any[]> {
    const res: any = await this.request("/webhooks");
    return Array.isArray(res) ? res : res.data || [];
  }

  async createWebhook(data: any): Promise<any> {
    return this.request("/webhooks", { method: "POST", body: JSON.stringify(data) });
  }

  async testWebhook(id: string): Promise<any> {
    return this.request(`/webhooks/${id}/test`, { method: "POST" });
  }

  // SEO
  async getSeoPages(params?: Record<string, string>): Promise<any> {
    const query = new URLSearchParams(params).toString();
    return this.request(`/seo${query ? `?${query}` : ""}`);
  }

  async createSeoPage(data: any): Promise<any> {
    return this.request("/seo", { method: "POST", body: JSON.stringify(data) });
  }

  async updateSeoPage(id: string, data: any): Promise<any> {
    return this.request(`/seo/${id}`, { method: "PATCH", body: JSON.stringify(data) });
  }

  async deleteSeoPage(id: string): Promise<void> {
    return this.request(`/seo/${id}`, { method: "DELETE" });
  }

  async getSitemap(): Promise<any> {
    return this.request("/seo/sitemap");
  }

  // Store / Settings
  async getStores(): Promise<any[]> {
    const res: any = await this.request("/stores");
    return Array.isArray(res) ? res : res.data || [];
  }

  async getStore(id: string): Promise<any> {
    return this.request(`/stores/${id}`);
  }

  async getStoreSettings(): Promise<any> {
    return this.request("/stores/settings");
  }

  async updateStoreSettings(data: any): Promise<any> {
    return this.request("/stores/settings", { method: "PATCH", body: JSON.stringify(data) });
  }

  async getStorePages(storeId: string): Promise<any[]> {
    return this.request(`/stores/${storeId}/pages`);
  }

  // Cart / Checkout (admin view)
  async getCarts(params?: Record<string, string>): Promise<any> {
    const query = new URLSearchParams(params).toString();
    return this.request(`/cart${query ? `?${query}` : ""}`);
  }

  // Coupons (admin UI calls these "Coupons"; the backend still mounts
  // them at /discounts for backward compatibility with the storefront's
  // discount-code validation flow).
  async getCoupons(): Promise<any[]> {
    const res: any = await this.request("/discounts");
    return Array.isArray(res) ? res : res.data || [];
  }
  async createCoupon(data: any): Promise<any> {
    return this.request("/discounts", { method: "POST", body: JSON.stringify(data) });
  }
  async updateCoupon(id: string, data: any): Promise<any> {
    return this.request(`/discounts/${id}`, { method: "PATCH", body: JSON.stringify(data) });
  }
  async deleteCoupon(id: string): Promise<void> {
    return this.request(`/discounts/${id}`, { method: "DELETE" });
  }
  async validateCoupon(code: string, orderTotalCents: number): Promise<any> {
    return this.request(`/discounts/${code}/validate`, { method: "POST", body: JSON.stringify({ order_total_cents: orderTotalCents }) });
  }
  // Backward-compat aliases (some legacy callers still use the old names)
  getDiscounts = this.getCoupons.bind(this);
  createDiscount = this.createCoupon.bind(this);
  updateDiscount = this.updateCoupon.bind(this);
  deleteDiscount = this.deleteCoupon.bind(this);
  validateDiscount = this.validateCoupon.bind(this);

  // Media
  async uploadMedia(file: File): Promise<any> {
    const formData = new FormData();
    formData.append("file", file);
    const token = this.getToken();
    const res = await fetch(`${this.baseUrl}/media/upload`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  // Pages & Themes
  async getPages(): Promise<any[]> {
    const res: any = await this.request("/pages");
    return Array.isArray(res) ? res : res.data || [];
  }
  async createPage(data: any): Promise<any> {
    return this.request("/pages", { method: "POST", body: JSON.stringify(data) });
  }
  async getPage(id: string): Promise<any> {
    return this.request(`/pages/${id}`);
  }
  async updatePage(id: string, data: any): Promise<any> {
    return this.request(`/pages/${id}`, { method: "PATCH", body: JSON.stringify(data) });
  }
  async publishPage(id: string): Promise<any> {
    return this.request(`/pages/${id}/publish`, { method: "POST" });
  }
  async deletePage(id: string): Promise<void> {
    return this.request(`/pages/${id}`, { method: "DELETE" });
  }
  async getThemes(): Promise<any[]> {
    const res: any = await this.request("/themes");
    return Array.isArray(res) ? res : res.data || [];
  }
  async getThemePresets(): Promise<any[]> {
    return this.request("/themes/presets");
  }
  async applyTheme(data: any): Promise<any> {
    return this.request("/themes/apply", { method: "POST", body: JSON.stringify(data) });
  }

  // Invoices
  async getInvoice(orderId: string): Promise<any> {
    return this.request(`/invoices/${orderId}`);
  }
}

export const apiClient = new ApiClient(API_URL);
export const adminApi = apiClient;
export default apiClient;

// ---------------------------------------------------------------------------
// Extended admin surfaces: team, domains, webhooks deliveries, SEO redirects,
// returns, CSV exports
// ---------------------------------------------------------------------------

class AdminApiExtensions {
  private get token(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("access_token");
  }

  private async req(path: string, options: RequestInit = {}): Promise<any> {
    const base = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
    const url = path.startsWith("http") ? path : `${base}/api/v1${path}`;
    const headers: Record<string, string> = {
      "content-type": "application/json",
      ...((options.headers as Record<string, string>) || {}),
    };
    if (this.token) headers.Authorization = `Bearer ${this.token}`;
    const res = await fetch(url, { ...options, headers });
    if (res.status === 204) return null;
    const text = await res.text();
    const data = text ? JSON.parse(text) : null;
    if (!res.ok) throw new Error((data && (data.detail || data.message)) || `Request failed (${res.status})`);
    return data;
  }

  // Team management -------------------------------------------------------
  getUsers(): Promise<any[]> {
    return this.req("/auth/users");
  }

  createUser(data: {
    email: string;
    first_name: string;
    last_name: string;
    role: string;
    password: string;
    mfa_required?: boolean;
    status?: string;
  }): Promise<any> {
    return this.req("/auth/users", { method: "POST", body: JSON.stringify(data) });
  }

  // Domains ----------------------------------------------------------------
  getDomains(tenantId: string): Promise<any[]> {
    return this.req(`/tenants/${tenantId}/domains`);
  }

  createDomain(tenantId: string, data: { domain: string; is_primary?: boolean }): Promise<any> {
    return this.req(`/tenants/${tenantId}/domains`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  verifyDomain(tenantId: string, domainId: string): Promise<any> {
    return this.req(`/tenants/${tenantId}/domains/${domainId}/verify`, { method: "POST" });
  }

  // Webhook deliveries -----------------------------------------------------
  getWebhookDeliveries(endpointId: string): Promise<any[]> {
    return this.req(`/webhooks/${endpointId}/deliveries`);
  }

  // SEO redirects ------------------------------------------------------------
  getSeoRedirects(): Promise<any[]> {
    return this.req("/seo/redirects");
  }

  createSeoRedirect(data: { old_path: string; new_path: string; status_code?: number }): Promise<any> {
    return this.req("/seo/redirects", { method: "POST", body: JSON.stringify(data) });
  }

  deleteSeoRedirect(id: string): Promise<void> {
    return this.req(`/seo/redirects/${id}`, { method: "DELETE" });
  }

  // Media ------------------------------------------------------------------
  listMedia(prefix = ""): Promise<any> {
    return this.req(`/media?prefix=${encodeURIComponent(prefix)}`);
  }

  deleteMedia(key: string): Promise<void> {
    return this.req(`/media/${encodeURIComponent(key)}`, { method: "DELETE" });
  }

  // Inventory --------------------------------------------------------------
  getLowInventory(threshold = 10): Promise<any> {
    return this.req(`/analytics/low-inventory?threshold=${threshold}`);
  }

  // Returns / CSV exports ---------------------------------------------------
  createReturn(orderId: string, items: any[], reason: string): Promise<any> {
    return this.req(
      `/orders/${orderId}/returns?reason=${encodeURIComponent(reason)}`,
      { method: "POST", body: JSON.stringify(items) }
    );
  }

  async exportCsv(reportType: "orders" | "customers" | "leads"): Promise<Blob> {
    const base = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
    const res = await fetch(`${base}/api/v1/reports/export/${reportType}`, {
      headers: this.token ? { Authorization: `Bearer ${this.token}` } : {},
    });
    if (!res.ok) throw new Error(`Export failed (${res.status})`);
    return res.blob();
  }
}

export const adminApiExt = new AdminApiExtensions();
