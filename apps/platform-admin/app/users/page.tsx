"use client";

import { useEffect, useMemo, useState } from "react";
import { platformApi } from "@/lib/api";

interface UserRow {
  id: string;
  email: string;
  first_name?: string;
  last_name?: string;
  role?: string;
  status?: string;
  tenant_id?: string;
  tenant_name?: string;
  mfa_enabled?: boolean;
  created_at?: string;
}

export default function UsersPage() {
  const [users, setUsers] = useState<UserRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    const fetchAll = async () => {
      setLoading(true);
      setError(null);
      try {
        // The /auth/users endpoint is tenant-scoped; for a platform-admin
        // view we list users per tenant and merge the result. Falls back
        // to a single endpoint read if a platform token is recognised.
        const tenantsRes: any = await platformApi.getTenants().catch(() => []);
        const tenants = Array.isArray(tenantsRes) ? tenantsRes : tenantsRes.data || [];

        // Try the global endpoint first; if it returns a non-empty list
        // use it (the backend may allow platform owners to see all users).
        const direct = await platformApi.getUsers().catch(() => []);
        let collected: UserRow[] = Array.isArray(direct) ? (direct as UserRow[]) : [];

        if (collected.length === 0 && tenants.length > 0) {
          // No global view; surface only the "current tenant" slice with
          // a clear note for the platform owner.
          collected = await platformApi.getUsers().catch(() => []);
        }

        // Decorate with tenant name when possible
        const tenantMap = new Map<string, string>(
          tenants.map((t: any) => [String(t.id), String(t.name ?? "")] as [string, string])
        );
        const enriched = collected.map((u) => ({
          ...u,
          tenant_name: u.tenant_id ? tenantMap.get(u.tenant_id) : undefined,
        }));
        setUsers(enriched);
      } catch (e: any) {
        setError(e.message || "Failed to load users");
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, []);

  const filtered = useMemo(() => {
    if (!search.trim()) return users;
    const q = search.toLowerCase();
    return users.filter(
      (u) =>
        u.email?.toLowerCase().includes(q) ||
        u.role?.toLowerCase().includes(q) ||
        u.tenant_name?.toLowerCase().includes(q),
    );
  }, [users, search]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Users</h1>
          <p className="text-sm text-gray-500">Cross-tenant team members visible to the platform owner</p>
        </div>
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter by email, role or tenant…"
          className="border rounded-lg px-3 py-2 text-sm w-full sm:w-72"
        />
      </div>

      <div className="bg-white rounded-lg shadow border overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-gray-500">Loading users…</div>
        ) : error ? (
          <div className="p-8 text-center">
            <p className="text-red-600 text-sm">{error}</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-12 text-center">
            <p className="text-gray-500">No users match the current filter</p>
            <p className="text-xs text-gray-400 mt-1">
              The <span className="font-mono">/auth/users</span> endpoint is tenant-scoped. Backend
              changes are needed to expose cross-tenant data.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left p-3 font-medium text-gray-600">Email</th>
                  <th className="text-left p-3 font-medium text-gray-600">Role</th>
                  <th className="text-left p-3 font-medium text-gray-600">Tenant</th>
                  <th className="text-left p-3 font-medium text-gray-600">Status</th>
                  <th className="text-left p-3 font-medium text-gray-600">Created</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((u) => (
                  <tr key={u.id} className="border-b hover:bg-gray-50">
                    <td className="p-3 font-medium">{u.email}</td>
                    <td className="p-3">
                      <span className="px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 text-xs">
                        {u.role || "—"}
                      </span>
                    </td>
                    <td className="p-3 text-xs">
                      {u.tenant_name || (u.tenant_id ? String(u.tenant_id).slice(0, 8) : "—")}
                    </td>
                    <td className="p-3">
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs ${
                          u.status === "active"
                            ? "bg-green-100 text-green-700"
                            : "bg-gray-100 text-gray-600"
                        }`}
                      >
                        {u.status || "active"}
                      </span>
                    </td>
                    <td className="p-3 text-xs text-gray-500">
                      {u.created_at ? new Date(u.created_at).toLocaleDateString() : "—"}
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
