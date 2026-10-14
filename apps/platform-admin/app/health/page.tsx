"use client";

import { useEffect, useState } from "react";
import { platformApi } from "@/lib/api";

export default function HealthPage() {
  const [health, setHealth] = useState<any>(null);
  const [detailed, setDetailed] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchHealth = async () => {
      setLoading(true);
      setError(null);
      try {
        const [h, d] = await Promise.all([
          platformApi.getHealth().catch((e) => {
            throw e;
          }),
          platformApi.getHealthDetailed().catch(() => null),
        ]);
        setHealth(h);
        setDetailed(d);
      } catch (e: any) {
        setError(e.message || "Health check failed");
      } finally {
        setLoading(false);
      }
    };
    fetchHealth();
    const id = setInterval(fetchHealth, 30000);
    return () => clearInterval(id);
  }, []);

  if (loading) return <div className="p-12 text-center text-gray-500">Checking platform health…</div>;

  const components = detailed?.components || {};
  const dbOk = components.database === "healthy";
  const redisOk = components.redis === "healthy";

  // Celery worker is a separate process; the API doesn't directly inspect it.
  // We surface a "Celery worker" row whose status is "unverified" (no probe),
  // so the page always shows the same three subsystems the platform owns.
  const celeryState = "unverified";

  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-2xl font-bold">Platform Health</h1>

      {error ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-700 font-medium">Unhealthy</p>
          <p className="text-sm text-red-600 mt-1">{error}</p>
        </div>
      ) : (
        <div
          className={`rounded-lg p-4 border ${
            health?.status === "healthy"
              ? "bg-green-50 border-green-200"
              : "bg-amber-50 border-amber-200"
          }`}
        >
          <p className={`font-medium ${health?.status === "healthy" ? "text-green-700" : "text-amber-700"}`}>
            {health?.status === "healthy" ? "All systems operational" : "Degraded — check components below"}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            Last checked: {new Date().toLocaleString()} • auto-refresh every 30s
          </p>
        </div>
      )}

      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow border p-5">
          <h3 className="font-semibold text-sm">API</h3>
          <p className="text-2xl font-bold mt-2">
            {health?.status === "healthy" ? "✓ Healthy" : health?.status || "—"}
          </p>
          <p className="text-xs text-gray-400 mt-1">Version {health?.version || "0.1.0"}</p>
        </div>
        <div className="bg-white rounded-lg shadow border p-5">
          <h3 className="font-semibold text-sm">Database</h3>
          <p className={`text-lg font-bold mt-2 ${dbOk ? "text-green-600" : components.database ? "text-red-600" : "text-gray-400"}`}>
            {dbOk ? "✓ Connected" : (components.database || "checking…")}
          </p>
          <p className="text-xs text-gray-400 mt-1">PostgreSQL with tenant RLS</p>
        </div>
        <div className="bg-white rounded-lg shadow border p-5">
          <h3 className="font-semibold text-sm">Redis</h3>
          <p className={`text-lg font-bold mt-2 ${redisOk ? "text-green-600" : components.redis ? "text-red-600" : "text-gray-400"}`}>
            {redisOk ? "✓ Connected" : (components.redis || "checking…")}
          </p>
          <p className="text-xs text-gray-400 mt-1">Rate limits · Celery broker · idempotency cache</p>
        </div>
        <div className="bg-white rounded-lg shadow border p-5">
          <h3 className="font-semibold text-sm">Celery Worker</h3>
          <p className="text-lg font-bold mt-2 text-gray-500">
            ? {celeryState}
          </p>
          <p className="text-xs text-gray-400 mt-1">Inspect with `celery -A apps.workers status`</p>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow border p-5">
        <h3 className="font-semibold mb-3">Background Workers (Celery beat)</h3>
        <div className="space-y-2 text-sm">
          {[
            ["Scheduled CSV reports", "daily @ 02:00 UTC"],
            ["Social token refresh", "every 6 hours"],
            ["Analytics aggregation", "hourly at :15"],
            ["Abandoned cart recovery", "hourly at :30"],
            ["Payment reconciliation", "every 4 hours"],
            ["Sitemap generation", "daily @ 03:00 UTC"],
          ].map(([name, sched]) => (
            <div key={name} className="flex justify-between py-2 border-b last:border-0">
              <span>{name}</span>
              <span className="text-xs text-gray-500">{sched}</span>
            </div>
          ))}
        </div>
      </div>

      {(health || detailed) && (
        <pre className="bg-gray-900 text-green-400 text-xs p-4 rounded-lg overflow-auto">
          {JSON.stringify({ ...health, components: detailed?.components }, null, 2)}
        </pre>
      )}
    </div>
  );
}
