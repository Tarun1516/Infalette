"use client";

import { useEffect, useState } from "react";
import { adminApi, adminApiExt } from "@/lib/api";

export default function DomainsPage() {
  const [tenantId, setTenantId] = useState<string>("");
  const [domains, setDomains] = useState<any[]>([]);
  const [newDomain, setNewDomain] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    // Resolve the current tenant from the auth token profile
    adminApi
      .getProfile()
      .then((profile) => {
        const tid = profile?.tenant_id || profile?.tenant?.id;
        if (tid) {
          setTenantId(tid);
          return adminApiExt.getDomains(tid).then(setDomains).catch(() => setDomains([]));
        }
      })
      .catch((e) => setError(e.message));
  }, []);

  async function addDomain(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setMessage("");
    try {
      await adminApiExt.createDomain(tenantId, { domain: newDomain.trim().toLowerCase() });
      setDomains(await adminApiExt.getDomains(tenantId));
      setNewDomain("");
      setMessage("Domain added — point the CNAME at the platform, then verify.");
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function verify(domainId: string) {
    setError("");
    try {
      const result = await adminApiExt.verifyDomain(tenantId, domainId);
      setDomains(await adminApiExt.getDomains(tenantId));
      setMessage(result?.verified ? "Domain verified ✓" : "DNS not resolving yet — retry after CNAME propagates.");
    } catch (err: any) {
      setError(err.message);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Custom domains</h1>
      {error && <p className="text-red-600 text-sm mb-3">{error}</p>}
      {message && <p className="text-green-700 text-sm mb-3">{message}</p>}
      <form onSubmit={addDomain} className="flex gap-2 mb-6">
        <input
          required
          value={newDomain}
          onChange={(e) => setNewDomain(e.target.value)}
          placeholder="shop.influencer.com"
          className="p-2.5 border rounded w-72"
        />
        <button disabled={!tenantId} className="px-4 py-2 bg-blue-600 text-white rounded disabled:opacity-50">Add domain</button>
      </form>

      <table className="w-full bg-white rounded shadow text-sm">
        <thead>
          <tr className="text-left border-b bg-gray-50">
            <th className="p-3">Domain</th>
            <th className="p-3">Primary</th>
            <th className="p-3">Verified</th>
            <th className="p-3"></th>
          </tr>
        </thead>
        <tbody>
          {domains.map((d) => (
            <tr key={d.id} className="border-b">
              <td className="p-3 font-mono">{d.domain}</td>
              <td className="p-3">{d.is_primary ? "✓" : "—"}</td>
              <td className="p-3">{d.verified ? "✓ verified" : "pending"}</td>
              <td className="p-3 text-right">
                {!d.verified && (
                  <button onClick={() => verify(d.id)} className="px-3 py-1 border rounded hover:bg-gray-100">
                    Verify DNS
                  </button>
                )}
              </td>
            </tr>
          ))}
          {domains.length === 0 && (
            <tr><td colSpan={4} className="p-6 text-center text-gray-500">No domains yet.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
