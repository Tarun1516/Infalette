"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { storefrontApi } from "@/lib/api";

type ConsentFlags = {
  marketing_email: boolean;
  marketing_sms: boolean;
  marketing_whatsapp: boolean;
  data_processing: boolean; // always on, read-only
};

const DEFAULT_FLAGS: ConsentFlags = {
  marketing_email: false,
  marketing_sms: false,
  marketing_whatsapp: false,
  data_processing: true,
};

export default function ConsentPage({ params }: { params: { tenant: string } }) {
  const { tenant } = params;
  const [customerId, setCustomerId] = useState<string | null>(null);
  const [resolving, setResolving] = useState(true);
  const [resolveError, setResolveError] = useState<string | null>(null);

  const [flags, setFlags] = useState<ConsentFlags>(DEFAULT_FLAGS);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      setResolving(true);
      setResolveError(null);
      try {
        const id = await storefrontApi.getMyCustomerId(tenant);
        if (cancelled) return;
        setCustomerId(id);
        if (id) {
          const existing = await storefrontApi.getConsent(tenant, id);
          if (!cancelled && existing && typeof existing === "object") {
            setFlags((prev) => ({
              ...prev,
              ...existing,
              data_processing: true, // never disable from the UI
            }));
          }
        } else {
          setResolveError(
            "We couldn't find your customer profile yet. Place an order or sign up for an account first."
          );
        }
      } catch (err: any) {
        if (cancelled) return;
        const msg = err?.response?.data?.detail || err?.message || "Failed to load profile";
        setResolveError(typeof msg === "string" ? msg : "Failed to load profile");
      } finally {
        if (!cancelled) {
          setResolving(false);
          setLoaded(true);
        }
      }
    }
    bootstrap();
    return () => {
      cancelled = true;
    };
  }, [tenant]);

  async function save(next: Partial<ConsentFlags>) {
    if (!customerId) return;
    setSaving(true);
    setError(null);
    setFeedback(null);
    try {
      const merged = { ...flags, ...next };
      setFlags(merged);
      const payload = {
        marketing_email: !!merged.marketing_email,
        marketing_sms: !!merged.marketing_sms,
        marketing_whatsapp: !!merged.marketing_whatsapp,
      };
      await storefrontApi.updateConsent(tenant, customerId, payload);
      setFeedback("Consent saved.");
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || "Failed to save consent";
      setError(typeof msg === "string" ? msg : "Failed to save consent");
    } finally {
      setSaving(false);
    }
  }

  async function withdrawAll() {
    if (!customerId) return;
    const ok = window.confirm(
      "Withdraw all marketing consent? You can opt back in at any time."
    );
    if (!ok) return;
    setSaving(true);
    setError(null);
    setFeedback(null);
    try {
      await storefrontApi.withdrawAllConsent(tenant, customerId);
      setFlags({ ...DEFAULT_FLAGS, data_processing: true });
      setFeedback("All marketing consent withdrawn.");
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || "Failed to withdraw consent";
      setError(typeof msg === "string" ? msg : "Failed to withdraw consent");
    } finally {
      setSaving(false);
    }
  }

  async function exportData() {
    if (!customerId) return;
    setError(null);
    setFeedback(null);
    try {
      const data = await storefrontApi.exportCustomerData(tenant, customerId);
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `infalette-data-${customerId}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => window.URL.revokeObjectURL(url), 1000);
      setFeedback("Your data export is downloading.");
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || "Failed to export data";
      setError(typeof msg === "string" ? msg : "Failed to export data");
    }
  }

  async function deleteAccount() {
    if (!customerId) return;
    const ok = window.confirm(
      "Permanently delete your account and personal data? This cannot be undone."
    );
    if (!ok) return;
    setSaving(true);
    setError(null);
    setFeedback(null);
    try {
      await storefrontApi.eraseCustomerData(tenant, customerId);
      // Wipe local auth and bounce back to the storefront home.
      try {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
      } catch {
        /* ignore storage failures */
      }
      window.location.href = `/${tenant}`;
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || "Failed to delete account";
      setError(typeof msg === "string" ? msg : "Failed to delete account");
      setSaving(false);
    }
  }

  if (resolving && !loaded) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-10">
        <h1 className="text-3xl font-bold mb-2">Consent preferences</h1>
        <p className="text-sm text-gray-500">Loading…</p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-10 space-y-6">
      <div>
        <Link href={`/${tenant}/account`} className="text-sm text-gray-500 hover:underline">
          ← Back to account
        </Link>
        <h1 className="text-3xl font-bold mt-2">Consent preferences</h1>
        <p className="text-sm text-gray-500 mt-1">
          Manage how we communicate with you and what we do with your data.
          Required processing is always on; you can opt out of marketing any
          time.
        </p>
      </div>

      {resolveError && (
        <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 rounded-lg p-3 text-sm">
          {resolveError}
        </div>
      )}

      {customerId && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            save({});
          }}
          className="bg-white rounded-2xl border shadow-sm p-6 space-y-4"
        >
          <ConsentRow
            label="Marketing email"
            description="Emails about new products, restocks, and curated picks."
            checked={flags.marketing_email}
            disabled={saving}
            onChange={(v) => save({ marketing_email: v })}
          />
          <ConsentRow
            label="Marketing SMS"
            description="Text messages about your orders and occasional offers."
            checked={flags.marketing_sms}
            disabled={saving}
            onChange={(v) => save({ marketing_sms: v })}
          />
          <ConsentRow
            label="Marketing WhatsApp"
            description="Order updates and recommendations over WhatsApp."
            checked={flags.marketing_whatsapp}
            disabled={saving}
            onChange={(v) => save({ marketing_whatsapp: v })}
          />
          <ConsentRow
            label="Data processing"
            description="Required to run the store: account, orders, support."
            checked={flags.data_processing}
            disabled
            onChange={() => {}}
          />

          {feedback && <p className="text-sm text-green-700">{feedback}</p>}
          {error && <p className="text-sm text-red-700">{error}</p>}

          <button
            type="submit"
            disabled={saving}
            className="px-5 py-2.5 rounded-full bg-gray-900 text-white text-sm font-semibold disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save preferences"}
          </button>
        </form>
      )}

      {customerId && (
        <div className="bg-white rounded-2xl border shadow-sm p-6 space-y-3">
          <h2 className="font-semibold">Your data</h2>
          <p className="text-sm text-gray-500">
            Export a copy of everything we hold on you, or permanently
            delete your account.
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={exportData}
              disabled={saving}
              className="px-4 py-2 rounded-full border text-sm font-semibold hover:bg-gray-50 disabled:opacity-50"
            >
              Export my data
            </button>
            <button
              type="button"
              onClick={deleteAccount}
              disabled={saving}
              className="px-4 py-2 rounded-full border border-red-300 text-red-700 text-sm font-semibold hover:bg-red-50 disabled:opacity-50"
            >
              Delete my account
            </button>
          </div>
        </div>
      )}

      {customerId && (
        <div className="bg-white rounded-2xl border shadow-sm p-6 space-y-3">
          <h2 className="font-semibold">Withdraw all consent</h2>
          <p className="text-sm text-gray-500">
            Revoke every marketing opt-in. You can opt back in any time.
          </p>
          <button
            type="button"
            onClick={withdrawAll}
            disabled={saving}
            className="px-4 py-2 rounded-full bg-red-600 text-white text-sm font-semibold hover:bg-red-700 disabled:opacity-50"
          >
            {saving ? "Working…" : "Withdraw all consent"}
          </button>
        </div>
      )}
    </div>
  );
}

function ConsentRow({
  label,
  description,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="flex items-start gap-3">
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-1 h-4 w-4 rounded border-gray-300 text-gray-900 focus:ring-gray-900"
      />
      <div>
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-gray-500">{description}</p>
        {disabled && (
          <p className="text-xs text-gray-400 mt-0.5">Always on</p>
        )}
      </div>
    </label>
  );
}
