"use client";

import { toast } from "@/components/toaster";

import { useEffect, useState } from "react";
import Link from "next/link";
import { platformApi } from "@/lib/api";

export default function TenantsPage() {
  const [tenants, setTenants] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", slug: "", plan: "store" });
  const [saving, setSaving] = useState(false);

  const fetchTenants = async () => {
    setLoading(true);
    setError(null);
    try {
      const res: any = await platformApi.getTenants();
      const list = Array.isArray(res) ? res : res.data || res.items || [];
      setTenants(list);
      setTotal(res.total ?? list.length);
    } catch (e: any) {
      setError(e.message || "Failed to load tenants");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTenants();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const created: any = await platformApi.createTenant(form);
      setShowCreate(false);
      setForm({ name: "", slug: "", plan: "store" });
      const creds =
        created && typeof created === "object" && "admin_email" in created
          ? `\n\nOwner login — email: ${created.admin_email}  password: ${created.admin_password}`
          : "";
      toast({ kind: "error", title: "Something went wrong", description: "Tenant created successfully." + creds });
      fetchTenants();
    } catch (e: any) {
      toast({ kind: "error", title: "Something went wrong", description: e.message || "Failed to create tenant" });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold">Tenants</h1>
          <p className="text-sm text-gray-500">
            {total} tenant(s) • platform owner view
          </p>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700"
        >
          {showCreate ? "Cancel" : "Add Tenant"}
        </button>
      </div>

      {showCreate && (
        <form
          onSubmit={handleCreate}
          className="bg-white rounded-lg shadow border p-6 mb-6 space-y-4"
        >
          <h3 className="font-semibold">New Tenant</h3>
          <div className="grid md:grid-cols-3 gap-4">
            <input
              placeholder="Name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="border rounded-lg px-3 py-2 text-sm"
              required
            />
            <input
              placeholder="Slug (e.g. anaya)"
              value={form.slug}
              onChange={(e) => setForm({ ...form, slug: e.target.value })}
              className="border rounded-lg px-3 py-2 text-sm"
            />
            <select
              value={form.plan}
              onChange={(e) => setForm({ ...form, plan: e.target.value })}
              className="border rounded-lg px-3 py-2 text-sm bg-white"
            >
              <option value="store">Store</option>
              <option value="store_automation">Store + Automation</option>
              <option value="store_automation_crm">Store + Automation + CRM</option>
            </select>
          </div>
          <button
            type="submit"
            disabled={saving}
            className="bg-gray-900 text-white px-5 py-2 rounded-lg text-sm disabled:opacity-50"
          >
            {saving ? "Creating…" : "Create Tenant"}
          </button>
        </form>
      )}

      <div className="bg-white rounded-lg shadow border overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-gray-500">Loading tenants…</div>
        ) : error ? (
          <div className="p-8 text-center">
            <p className="text-red-600 text-sm">{error}</p>
            <button
              onClick={fetchTenants}
              className="mt-3 text-sm bg-gray-900 text-white px-4 py-2 rounded"
            >
              Retry
            </button>
          </div>
        ) : tenants.length === 0 ? (
          <div className="p-12 text-center">
            <p className="text-gray-500">No tenants yet</p>
            <p className="text-xs text-gray-400 mt-1">
              Create the first influencer tenant to assign domain, theme, and merchant account
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left p-3 font-medium text-gray-600">Name</th>
                  <th className="text-left p-3 font-medium text-gray-600">Slug</th>
                  <th className="text-left p-3 font-medium text-gray-600">Plan</th>
                  <th className="text-left p-3 font-medium text-gray-600">Status</th>
                  <th className="text-left p-3 font-medium text-gray-600">Created</th>
                  <th className="text-left p-3 font-medium text-gray-600"></th>
                </tr>
              </thead>
              <tbody>
                {tenants.map((t) => (
                  <tr key={t.id} className="border-b hover:bg-gray-50">
                    <td className="p-3 font-medium">
                      <Link
                        href={`/tenants/${t.id}`}
                        className="text-blue-600 hover:underline"
                      >
                        {t.name}
                      </Link>
                    </td>
                    <td className="p-3 font-mono text-xs">{t.slug}</td>
                    <td className="p-3">
                      <span className="px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 text-xs">
                        {t.plan || t.plan_slug}
                      </span>
                    </td>
                    <td className="p-3">
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs ${
                          t.status === "active"
                            ? "bg-green-100 text-green-700"
                            : "bg-gray-100 text-gray-600"
                        }`}
                      >
                        {t.status || "active"}
                      </span>
                    </td>
                    <td className="p-3 text-xs text-gray-500">
                      {t.created_at ? new Date(t.created_at).toLocaleDateString() : "—"}
                    </td>
                    <td className="p-3 text-right">
                      <Link
                        href={`/tenants/${t.id}`}
                        className="text-xs text-blue-600 hover:underline"
                      >
                        View →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
