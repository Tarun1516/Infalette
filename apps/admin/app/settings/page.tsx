"use client";

import { toast } from "@/components/toaster";

import { useEffect, useState } from "react";
import { adminApi } from "@/lib/api";

export default function SettingsPage() {
  const [settings, setSettings] = useState<any>(null);
  const [integrations, setIntegrations] = useState<any[]>([]);
  const [presets, setPresets] = useState<any[]>([]);
  const [themes, setThemes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    description: "",
    custom_domain: "",
    logo: "",
    primary_color: "#000000",
    currency: "INR",
    tax_rate: "18",
  });
  const [shippingRules, setShippingRules] = useState("{}");
  const [socialLinks, setSocialLinks] = useState("{}");
  const [menus, setMenus] = useState("[]");
  const [legalPages, setLegalPages] = useState("{}");

  useEffect(() => {
    const fetchSettings = async () => {
      setLoading(true);
      try {
        const [storeRes, intRes, presetRes, themesRes] = await Promise.all([
          adminApi.getStoreSettings().catch(() => null),
          adminApi.getIntegrations().catch(() => []),
          adminApi.getThemePresets().catch(() => []),
          adminApi.getThemes().catch(() => []),
        ]);
        setPresets(Array.isArray(presetRes) ? presetRes : (presetRes as any)?.data || []);
        setThemes(Array.isArray(themesRes) ? themesRes : (themesRes as any)?.data || []);
        if (storeRes) {
          setSettings(storeRes);
          const s = storeRes.store || storeRes;
          setForm({
            name: s.name || "",
            description: s.description || "",
            custom_domain: s.custom_domain || s.domain || "",
            logo: s.logo || s.logo_url || "",
            primary_color: s.theme_config?.primary_color || s.primary_color || "#000000",
            currency: s.currency || "INR",
            tax_rate: String(s.tax_rate ?? 18),
          });
          try {
            const sr = (storeRes as any).shipping_rules ?? (storeRes as any).shipping_rules_json;
            if (sr && Object.keys(sr).length) setShippingRules(JSON.stringify(sr, null, 2));
          } catch {}
          try {
            const sl = (storeRes as any).social_links ?? (storeRes as any).social_links_json;
            if (sl && Object.keys(sl).length) setSocialLinks(JSON.stringify(sl, null, 2));
          } catch {}
          try {
            const m = (storeRes as any).menus ?? (storeRes as any).menus_json;
            if (m && Array.isArray(m) && m.length) setMenus(JSON.stringify(m, null, 2));
          } catch {}
          try {
            const lp = (storeRes as any).legal_pages ?? (storeRes as any).legal_pages_json;
            if (lp && Object.keys(lp).length) setLegalPages(JSON.stringify(lp, null, 2));
          } catch {}
        }
        setIntegrations(Array.isArray(intRes) ? intRes : (intRes as any)?.data || []);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    fetchSettings();
  }, []);

  function parseJsonField(value: string, label: string): boolean {
    if (!value.trim()) return false;
    try {
      JSON.parse(value);
      return true;
    } catch (e: any) {
      setError(`${label} is not valid JSON: ${e.message}`);
      throw e;
    }
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      await adminApi.updateStoreSettings({
        name: form.name,
        description: form.description,
        custom_domain: form.custom_domain,
        logo: form.logo,
        theme_config: { primary_color: form.primary_color },
        currency: form.currency,
        tax_rate: parseFloat(form.tax_rate),
        ...(shippingRules.trim() && parseJsonField(shippingRules, "Shipping rules") ? { shipping_rules: JSON.parse(shippingRules) } : {}),
        ...(socialLinks.trim() && socialLinks.trim() !== "{}" && parseJsonField(socialLinks, "Social links") ? { social_links: JSON.parse(socialLinks) } : {}),
        ...(menus.trim() && menus.trim() !== "[]" && parseJsonField(menus, "Menus") ? { menus: JSON.parse(menus) } : {}),
        ...(legalPages.trim() && legalPages.trim() !== "{}" && parseJsonField(legalPages, "Legal pages") ? { legal_pages: JSON.parse(legalPages) } : {}),
      });
      setMessage("Settings saved successfully");
    } catch (e: any) {
      setError(e.message || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="p-12 text-center text-gray-500">Loading settings…</div>;

  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-2xl font-bold">Store Settings</h1>

      {error && <div className="bg-red-50 border border-red-200 text-red-700 rounded p-3 text-sm">{error}</div>}
      {message && <div className="bg-green-50 border border-green-200 text-green-700 rounded p-3 text-sm">{message}</div>}

      <form onSubmit={handleSave} className="space-y-6">
        <div className="bg-white p-6 rounded-lg shadow border space-y-4">
          <h3 className="font-semibold">Store Information</h3>
          <div>
            <label className="block text-sm font-medium mb-1">Store Name</label>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full border rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Description</label>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={3}
              className="w-full border rounded-lg px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Custom Domain</label>
            <input
              value={form.custom_domain}
              onChange={(e) => setForm({ ...form, custom_domain: e.target.value })}
              placeholder="shop.yourdomain.com"
              className="w-full border rounded-lg px-3 py-2 text-sm"
            />
            <p className="text-xs text-gray-400 mt-1">Configure DNS CNAME to point to the platform after saving</p>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Logo URL</label>
            <input value={form.logo} onChange={(e) => setForm({ ...form, logo: e.target.value })} className="w-full border rounded-lg px-3 py-2 text-sm" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Primary Color</label>
              <div className="flex gap-2">
                <input type="color" value={form.primary_color} onChange={(e) => setForm({ ...form, primary_color: e.target.value })} className="w-12 h-10 border rounded" />
                <input value={form.primary_color} onChange={(e) => setForm({ ...form, primary_color: e.target.value })} className="flex-1 border rounded-lg px-3 py-2 text-sm" />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Currency</label>
              <select value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })} className="w-full border rounded-lg px-3 py-2 text-sm bg-white">
                <option value="INR">INR</option>
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
              </select>
            </div>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow border space-y-4">
          <h3 className="font-semibold">Tax & Shipping</h3>
          <div>
            <label className="block text-sm font-medium mb-1">Default GST Rate (%)</label>
            <input type="number" value={form.tax_rate} onChange={(e) => setForm({ ...form, tax_rate: e.target.value })} className="w-full border rounded-lg px-3 py-2 text-sm" />
          </div>
          <p className="text-xs text-gray-500">Shipping zones and rates are managed via the Shipping service. Contact support to configure zones.</p>
        </div>

        <div className="bg-white p-6 rounded-lg shadow border space-y-4">
          <h3 className="font-semibold">Theme</h3>
          <p className="text-xs text-gray-500">Apply a preset theme, or pick one of your saved themes.</p>
          <div className="flex flex-wrap gap-2">
            {presets.map((p: any) => (
              <button
                key={p.slug || p.name}
                type="button"
                onClick={async () => {
                  try {
                    await adminApi.applyTheme({ preset: p.slug || p.name });
                    setMessage(`Theme "${p.name || p.slug}" applied`);
                  } catch (e: any) {
                    setError(e.message || "Failed to apply theme");
                  }
                }}
                className="border rounded-full px-4 py-1.5 text-sm hover:bg-gray-50"
              >
                {p.name || p.slug}
              </button>
            ))}
            {themes.map((t: any) => (
              <button
                key={t.id}
                type="button"
                onClick={async () => {
                  try {
                    await adminApi.applyTheme({ theme_id: t.id });
                    setMessage(`Theme "${t.name}" applied`);
                  } catch (e: any) {
                    setError(e.message || "Failed to apply theme");
                  }
                }}
                className="border rounded-full px-4 py-1.5 text-sm hover:bg-gray-50"
              >
                {t.name} (saved)
              </button>
            ))}
            {presets.length === 0 && themes.length === 0 && (
              <span className="text-sm text-gray-400">No themes available</span>
            )}
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow border">
          <h3 className="font-semibold mb-3">Connected Integrations</h3>
          {integrations.length === 0 ? (
            <p className="text-sm text-gray-500">No integrations connected. Payment and social integrations are configured per tenant.</p>
          ) : (
            <div className="space-y-2">
              {integrations.map((i: any) => (
                <div key={i.id} className="flex justify-between items-center py-2 border-b last:border-0">
                  <div>
                    <p className="text-sm font-medium">{i.provider}</p>
                    <p className="text-xs text-gray-400">{i.status}</p>
                  </div>
                  <button
                    type="button"
                    onClick={async () => {
                      try {
                        await adminApi.testIntegration(i.id);
                        toast({ kind: "info", title: "Connection test succeeded" });
                      } catch (e: any) {
                        toast({ kind: "error", title: "Something went wrong", description: e.message || "Test failed" });
                      }
                    }}
                    className="text-xs border px-3 py-1 rounded hover:bg-gray-50"
                  >
                    Test
                  </button>
                </div>
              ))}
            </div>
          )}
          <div className="mt-4 flex gap-2">
            <span className="text-xs text-gray-400">
              Payment & social integrations are configured per tenant by the platform team.
            </span>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow border space-y-4">
          <h3 className="font-semibold">Storefront Menus</h3>
          <p className="text-xs text-gray-500">JSON array of navigation links — each with label and path.</p>
          <textarea value={menus} onChange={(e) => setMenus(e.target.value)} rows={3} className="w-full border rounded-lg px-3 py-2 text-xs font-mono" placeholder={'[{"label":"Shop","path":"/products"}]'} />
        </div>

        <div className="bg-white p-6 rounded-lg shadow border space-y-4">
          <h3 className="font-semibold">Social Links</h3>
          <p className="text-xs text-gray-500">JSON object with your social handles.</p>
          <textarea value={socialLinks} onChange={(e) => setSocialLinks(e.target.value)} rows={3} className="w-full border rounded-lg px-3 py-2 text-xs font-mono" placeholder={"instagram handle, e.g. @yourbrand"} />
        </div>

        <div className="bg-white p-6 rounded-lg shadow border space-y-4">
          <h3 className="font-semibold">Shipping Rules</h3>
          <p className="text-xs text-gray-500">Tenant shipping overrides for free-shipping threshold, per-type prices, and zone prices.</p>
          <textarea value={shippingRules} onChange={(e) => setShippingRules(e.target.value)} rows={4} className="w-full border rounded-lg px-3 py-2 text-xs font-mono" placeholder={'{"free_shipping_threshold_cents":120000}'} />
        </div>

        <div className="bg-white p-6 rounded-lg shadow border space-y-4">
          <h3 className="font-semibold mb-2">Legal Pages</h3>
          <p className="text-sm text-gray-500 mb-3">Create pages for privacy policy, terms, and return policy via the Page builder. Store page-ids here for footer links.</p>
          <textarea value={legalPages} onChange={(e) => setLegalPages(e.target.value)} rows={3} className="w-full border rounded-lg px-3 py-2 text-xs font-mono" placeholder={'{"privacy":"<page-id>","terms":"<page-id>"}'} />
          <div className="text-xs text-gray-400">Blocks: hero, featured-products, category-grid, testimonials, influencer-story, video, FAQ, bundles, newsletter, instagram-gallery</div>
        </div>

        <button type="submit" disabled={saving} className="bg-blue-600 text-white px-6 py-2.5 rounded-lg font-medium disabled:opacity-50">
          {saving ? "Saving…" : "Save Settings"}
        </button>
      </form>
    </div>
  );
}
