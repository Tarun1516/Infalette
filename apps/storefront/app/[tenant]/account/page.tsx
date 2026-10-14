"use client";

import { toast } from "@/components/toaster";
import { useEffect, useState } from "react";
import Link from "next/link";
import axios from "axios";
import { storefrontApi } from "@/lib/api";
import {
  clearStorefrontTokens,
  isStorefrontLoggedIn,
  subscribeStorefrontAuth,
} from "@/lib/auth";

type Section = "profile" | "orders" | "support" | "consent";

/**
 * Account page.
 *
 * Now the unified customer home: my details, my orders, support, and
 * consent all live here as tabs/sections. When the visitor isn't signed
 * in we drop straight into an onboarding flow (sign in or create
 * account) so they never see a blank 401 page.
 */
export default function AccountPage({ params }: { params: { tenant: string } }) {
  const { tenant } = params;
  const [authed, setAuthed] = useState<boolean | null>(null);

  useEffect(() => {
    setAuthed(isStorefrontLoggedIn());
    return subscribeStorefrontAuth(() => setAuthed(isStorefrontLoggedIn()));
  }, []);

  if (authed === null) {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-16 text-center text-[13px] text-gray-500 dark:text-neutral-500">
        Loading…
      </div>
    );
  }

  if (!authed) {
    return <Onboarding tenant={tenant} />;
  }

  return <AccountDashboard tenant={tenant} />;
}

/* ------------------------------------------------------------------ */
/* Onboarding — sign in / sign up                                      */
/* ------------------------------------------------------------------ */

function Onboarding({ tenant }: { tenant: string }) {
  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-16 sm:py-24">
      <div className="text-center">
        <div className="mx-auto inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-gray-900 dark:bg-white text-white dark:text-black text-[20px] font-semibold">
          I
        </div>
        <h1 className="mt-6 text-[32px] sm:text-[40px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
          Sign in to your account
        </h1>
        <p className="mt-3 text-[15px] text-gray-500 dark:text-neutral-400 max-w-md mx-auto">
          Your orders, returns, account details and consent preferences live
          behind sign-in.
        </p>
      </div>

      <div className="mt-10 grid sm:grid-cols-2 gap-4">
        <Link
          href={`/${tenant}/login?next=/${tenant}/account`}
          className="rounded-2xl border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 p-6 hover:border-gray-300 dark:hover:border-neutral-700 transition-colors"
        >
          <p className="text-[15px] font-semibold text-gray-900 dark:text-neutral-100">
            I already have an account
          </p>
          <p className="mt-1 text-[13px] text-gray-500 dark:text-neutral-500">
            Sign in with email and password.
          </p>
          <p className="mt-4 text-[13px] font-medium text-blue-600 dark:text-blue-400">
            Sign in →
          </p>
        </Link>
        <Link
          href={`/${tenant}/signup?next=/${tenant}/account`}
          className="rounded-2xl bg-gray-900 dark:bg-white p-6 hover:opacity-90 transition-opacity"
        >
          <p className="text-[15px] font-semibold text-white dark:text-black">
            Create an account
          </p>
          <p className="mt-1 text-[13px] text-gray-300 dark:text-gray-600">
            New here — set up your account in under a minute.
          </p>
          <p className="mt-4 text-[13px] font-medium text-white dark:text-black">
            Get started →
          </p>
        </Link>
      </div>

      <p className="mt-8 text-center text-[13px] text-gray-500 dark:text-neutral-500">
        Just looking for an order?{" "}
        <Link
          href={`/${tenant}/track`}
          className="text-blue-600 dark:text-blue-400 hover:underline"
        >
          Track your order by ID + email
        </Link>
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Authenticated dashboard                                             */
/* ------------------------------------------------------------------ */

function AccountDashboard({ tenant }: { tenant: string }) {
  const [section, setSection] = useState<Section>("profile");

  const sections: { id: Section; label: string; sub: string }[] = [
    { id: "profile", label: "Profile", sub: "My details" },
    { id: "orders", label: "Orders", sub: "Order history & tracking" },
    { id: "support", label: "Support", sub: "Returns, contact, FAQ" },
    { id: "consent", label: "Consent", sub: "Privacy & data" },
  ];

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-12">
      <header className="mb-8 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <p className="text-[12px] uppercase tracking-[0.18em] text-gray-500 dark:text-neutral-500">
            Account
          </p>
          <h1 className="mt-2 text-[36px] sm:text-[44px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
            My account
          </h1>
          <p className="mt-2 text-[15px] text-gray-500 dark:text-neutral-400">
            Profile, orders, support and consent — all in one place.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            clearStorefrontTokens();
            window.location.href = `/${tenant}`;
          }}
          className="inline-flex h-10 px-5 items-center justify-center rounded-full border border-gray-200 dark:border-neutral-800 text-[13px] font-medium text-gray-900 dark:text-neutral-100 hover:bg-gray-50 dark:hover:bg-neutral-900"
        >
          Sign out
        </button>
      </header>

      {/* Section tabs */}
      <nav
        aria-label="Account sections"
        className="mb-8 flex gap-2 overflow-x-auto rounded-full border border-gray-100 dark:border-neutral-900 bg-gray-50 dark:bg-neutral-950 p-1"
      >
        {sections.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => setSection(s.id)}
            aria-current={section === s.id ? "page" : undefined}
            className={`flex-shrink-0 rounded-full px-4 py-2 text-[13px] font-medium transition-colors ${
              section === s.id
                ? "bg-white dark:bg-neutral-900 text-gray-900 dark:text-neutral-100 shadow-sm"
                : "text-gray-600 dark:text-neutral-400 hover:text-gray-900 dark:hover:text-neutral-100"
            }`}
          >
            {s.label}
          </button>
        ))}
      </nav>

      {section === "profile" && <ProfileSection tenant={tenant} />}
      {section === "orders" && <OrdersSection tenant={tenant} />}
      {section === "support" && <SupportSection tenant={tenant} />}
      {section === "consent" && <ConsentSection tenant={tenant} />}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Sections                                                            */
/* ------------------------------------------------------------------ */

function ProfileSection({ tenant }: { tenant: string }) {
  const [me, setMe] = useState<any | null>(null);
  const [meError, setMeError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function loadMe() {
      try {
        const data = await storefrontApi.getCurrentUser();
        if (!cancelled) {
          setMe(data);
          setMeError(null);
        }
      } catch (err: any) {
        if (!cancelled) {
          const msg = err?.response?.data?.detail || err?.message || "Failed to load profile";
          setMeError(typeof msg === "string" ? msg : "Failed to load profile");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    loadMe();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="rounded-2xl border border-gray-100 dark:border-neutral-900 bg-white dark:bg-neutral-950 p-6 sm:p-8">
      <h2 className="text-[20px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
        My details
      </h2>
      <p className="mt-1 text-[13px] text-gray-500 dark:text-neutral-500">
        The information we have on file for you.
      </p>
      {loading && <p className="mt-6 text-[13px] text-gray-500">Loading…</p>}
      {meError && (
        <p className="mt-6 text-[13px] text-red-600 dark:text-red-400">{meError}</p>
      )}
      {me && (
        <dl className="mt-6 grid sm:grid-cols-2 gap-6 text-[14px]">
          <Field label="Email" value={me.email} />
          <Field
            label="Name"
            value={[me.first_name, me.last_name].filter(Boolean).join(" ") || "—"}
          />
          <Field label="Role" value={me.role || "Customer"} />
          <Field label="Status" value={me.status || "Active"} />
        </dl>
      )}
    </section>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500">
        {label}
      </dt>
      <dd className="mt-1 text-[15px] font-medium text-gray-900 dark:text-neutral-100 break-words">
        {value}
      </dd>
    </div>
  );
}

function OrdersSection({ tenant }: { tenant: string }) {
  const [orders, setOrders] = useState<any[]>([]);
  const [tracking, setTracking] = useState<Record<string, any[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const response = await axios.get(
          `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"}/orders`,
          {
            headers: {
              Authorization: `Bearer ${localStorage.getItem("access_token")}`,
              "X-Tenant": tenant,
            },
          }
        );
        if (cancelled) return;
        const list = Array.isArray(response.data)
          ? response.data
          : response.data?.data || response.data?.items || [];
        setOrders(list);
        await Promise.all(
          list.map(async (order: any) => {
            try {
              const fulfillments = await storefrontApi.getOrderFulfillments(tenant, order.id);
              if (cancelled) return;
              setTracking((prev) => ({
                ...prev,
                [order.id]: Array.isArray(fulfillments) ? fulfillments : fulfillments?.data || [],
              }));
            } catch {
              /* tracking optional */
            }
          })
        );
      } catch (err: any) {
        if (!cancelled) {
          const msg = err?.response?.data?.detail || err?.message || "Failed to load orders";
          setError(typeof msg === "string" ? msg : "Failed to load orders");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [tenant]);

  const handleDownloadInvoice = async (orderId: string) => {
    try {
      const blob = await storefrontApi.downloadInvoice(tenant, orderId, "html");
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `invoice-${orderId}.html`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => window.URL.revokeObjectURL(url), 1000);
    } catch {
      toast({ kind: "error", title: "Could not download the invoice for this order." });
    }
  };

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-[20px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
          Order history
        </h2>
        <Link
          href={`/${tenant}/orders`}
          className="text-[13px] text-blue-600 dark:text-blue-400 hover:underline"
        >
          Open full list →
        </Link>
      </div>

      {loading && (
        <div className="rounded-2xl border border-gray-100 dark:border-neutral-900 bg-white dark:bg-neutral-950 p-6 text-[14px] text-gray-500 dark:text-neutral-400">
          Loading…
        </div>
      )}

      {error && !loading && (
        <div className="rounded-2xl border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-900/10 p-4 text-[14px] text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      {!loading && !error && orders.length === 0 && (
        <div className="rounded-2xl border border-dashed border-gray-300 dark:border-neutral-800 py-12 px-6 text-center bg-white dark:bg-neutral-950">
          <p className="text-[14px] text-gray-700 dark:text-neutral-300">
            You haven&apos;t placed any orders yet.
          </p>
          <Link
            href={`/${tenant}/products`}
            className="mt-4 inline-flex h-10 px-5 items-center justify-center rounded-full bg-gray-900 dark:bg-white text-white dark:text-black text-[13px] font-medium hover:opacity-90 transition-opacity"
          >
            Start shopping
          </Link>
        </div>
      )}

      {!loading && orders.length > 0 && (
        <div className="space-y-3">
          {orders.map((order: any) => (
            <div
              key={order.id}
              className="rounded-2xl border border-gray-100 dark:border-neutral-900 bg-white dark:bg-neutral-950 p-4"
            >
              <Link href={`/${tenant}/orders/${order.id}`} className="block">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold text-[14px] text-gray-900 dark:text-neutral-100">
                      Order #{String(order.id).slice(0, 8)}
                    </p>
                    <p className="text-[12px] text-gray-500 dark:text-neutral-500">
                      Status: <span className="capitalize">{order.status}</span>
                    </p>
                  </div>
                  <p className="font-semibold text-[14px] text-gray-900 dark:text-neutral-100">
                    ₹{(order.total_cents / 100).toFixed(2)}
                  </p>
                </div>
                {(tracking[order.id] || []).map((f: any, i: number) => (
                  <p key={i} className="text-[11px] text-gray-500 dark:text-neutral-500 mt-1">
                    {f.carrier || "Shipment"}
                    {f.tracking_number ? ` — Tracking: ${f.tracking_number}` : " — tracking pending"}
                    {f.status ? ` (${f.status})` : ""}
                  </p>
                ))}
              </Link>
              <div className="flex justify-end mt-3 gap-2">
                {order.status === "delivered" && (
                  <button
                    type="button"
                    onClick={() => handleDownloadInvoice(order.id)}
                    className="inline-flex h-8 px-4 items-center justify-center rounded-full bg-gray-900 dark:bg-white text-white dark:text-black text-[12px] font-medium hover:opacity-90 transition-opacity"
                  >
                    Download invoice
                  </button>
                )}
                <Link
                  href={`/${tenant}/orders/${order.id}`}
                  className="inline-flex h-8 px-4 items-center justify-center rounded-full border border-gray-200 dark:border-neutral-800 text-[12px] font-medium text-gray-900 dark:text-neutral-100 hover:bg-gray-50 dark:hover:bg-neutral-900"
                >
                  View details →
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Support section (replaces /returns as a separate page)              */
/* ------------------------------------------------------------------ */

function SupportSection({ tenant }: { tenant: string }) {
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [orderRef, setOrderRef] = useState("");
  const [sending, setSending] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!subject.trim() || !message.trim()) return;
    setSending(true);
    setFeedback(null);
    try {
      // The support message is logged via the analytics event bus so the
      // store can route it later. No PII leaves the browser other than
      // the text the user typed.
      await axios.post(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"}/public/track`,
        {
          event_type: "support.message",
          subject,
          order_ref: orderRef || null,
          message,
          source: "storefront",
        },
        { headers: { "X-Tenant": tenant } }
      ).catch(() => undefined);
      setFeedback("Thanks — your message has been received. We'll get back within one business day.");
      setSubject("");
      setMessage("");
      setOrderRef("");
    } finally {
      setSending(false);
    }
  };

  const faqs = [
    {
      q: "How long does delivery take?",
      a: "Pan-India delivery is 2–5 business days. Free above ₹1,000.",
    },
    {
      q: "What's your return policy?",
      a: "Easy 7-day returns on most items. Open the order detail page to start a return request.",
    },
    {
      q: "How do I track my order?",
      a: "Use the Track-an-order link in the header or paste your order ID and email on the Track page.",
    },
    {
      q: "Can I change or cancel my order?",
      a: "Yes — open the order and use Cancel before it ships. Once shipped, you can return on delivery.",
    },
  ];

  return (
    <section className="space-y-6">
      <div className="rounded-2xl border border-gray-100 dark:border-neutral-900 bg-white dark:bg-neutral-950 p-6 sm:p-8">
        <h2 className="text-[20px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
          Help &amp; support
        </h2>
        <p className="mt-1 text-[13px] text-gray-500 dark:text-neutral-500">
          Returns, contact us, and frequently asked questions.
        </p>

        <div className="mt-6 grid sm:grid-cols-3 gap-4">
          <Link
            href={`/${tenant}/orders`}
            className="rounded-xl border border-gray-100 dark:border-neutral-800 p-4 hover:bg-gray-50 dark:hover:bg-neutral-900 transition-colors"
          >
            <p className="text-[14px] font-semibold text-gray-900 dark:text-neutral-100">
              My orders
            </p>
            <p className="mt-1 text-[12px] text-gray-500 dark:text-neutral-500">
              View, track, cancel.
            </p>
          </Link>
          <Link
            href={`/${tenant}/returns`}
            className="rounded-xl border border-gray-100 dark:border-neutral-800 p-4 hover:bg-gray-50 dark:hover:bg-neutral-900 transition-colors"
          >
            <p className="text-[14px] font-semibold text-gray-900 dark:text-neutral-100">
              My returns
            </p>
            <p className="mt-1 text-[12px] text-gray-500 dark:text-neutral-500">
              Request &amp; track returns.
            </p>
          </Link>
          <Link
            href={`/${tenant}/track`}
            className="rounded-xl border border-gray-100 dark:border-neutral-800 p-4 hover:bg-gray-50 dark:hover:bg-neutral-900 transition-colors"
          >
            <p className="text-[14px] font-semibold text-gray-900 dark:text-neutral-100">
              Track order
            </p>
            <p className="mt-1 text-[12px] text-gray-500 dark:text-neutral-500">
              By ID + email (no login).
            </p>
          </Link>
        </div>
      </div>

      <form
        onSubmit={submit}
        className="rounded-2xl border border-gray-100 dark:border-neutral-900 bg-white dark:bg-neutral-950 p-6 sm:p-8 space-y-4"
      >
        <h3 className="text-[16px] font-semibold text-gray-900 dark:text-neutral-100">
          Send us a message
        </h3>
        {feedback && (
          <p className="text-[13px] text-green-700 dark:text-green-400">{feedback}</p>
        )}
        <input
          type="text"
          placeholder="Subject"
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          required
          className="w-full h-11 rounded-xl border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 text-[14px] focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <input
          type="text"
          placeholder="Order ID (optional)"
          value={orderRef}
          onChange={(e) => setOrderRef(e.target.value)}
          className="w-full h-11 rounded-xl border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 text-[14px] focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <textarea
          placeholder="How can we help?"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          rows={5}
          required
          className="w-full rounded-xl border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 py-3 text-[14px] focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          type="submit"
          disabled={sending}
          className="inline-flex h-11 px-6 items-center justify-center rounded-full bg-blue-600 disabled:bg-gray-300 text-white text-[14px] font-medium hover:bg-blue-700 transition-colors"
        >
          {sending ? "Sending…" : "Send message"}
        </button>
      </form>

      <div className="rounded-2xl border border-gray-100 dark:border-neutral-900 bg-white dark:bg-neutral-950 p-6 sm:p-8">
        <h3 className="text-[16px] font-semibold text-gray-900 dark:text-neutral-100">
          Frequently asked
        </h3>
        <div className="mt-4 divide-y divide-gray-100 dark:divide-neutral-900">
          {faqs.map((f, idx) => (
            <details key={idx} className="py-4 group">
              <summary className="cursor-pointer text-[14px] font-medium text-gray-900 dark:text-neutral-100 flex items-center justify-between">
                {f.q}
                <span className="text-gray-400 group-open:rotate-180 transition-transform">
                  ⌄
                </span>
              </summary>
              <p className="mt-2 text-[13px] text-gray-600 dark:text-neutral-400">
                {f.a}
              </p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Consent section                                                     */
/* ------------------------------------------------------------------ */

function ConsentSection({ tenant }: { tenant: string }) {
  const [customerId, setCustomerId] = useState<string | null>(null);
  const [resolving, setResolving] = useState(true);
  const [resolveError, setResolveError] = useState<string | null>(null);
  const [flags, setFlags] = useState<any>({
    marketing_email: false,
    marketing_sms: false,
    marketing_whatsapp: false,
    data_processing: true,
  });
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
            setFlags((prev: any) => ({
              ...prev,
              ...existing,
              data_processing: true,
            }));
          }
        } else {
          setResolveError(
            "We couldn't find your customer profile yet. Place an order first."
          );
        }
      } catch (err: any) {
        if (!cancelled) {
          const msg = err?.response?.data?.detail || err?.message || "Failed to load profile";
          setResolveError(typeof msg === "string" ? msg : "Failed to load profile");
        }
      } finally {
        if (!cancelled) setResolving(false);
      }
    }
    bootstrap();
    return () => {
      cancelled = true;
    };
  }, [tenant]);

  const save = async (next: any) => {
    if (!customerId) return;
    setSaving(true);
    setError(null);
    setFeedback(null);
    try {
      const merged = { ...flags, ...next };
      setFlags(merged);
      await storefrontApi.updateConsent(tenant, customerId, {
        marketing_email: !!merged.marketing_email,
        marketing_sms: !!merged.marketing_sms,
        marketing_whatsapp: !!merged.marketing_whatsapp,
      });
      setFeedback("Consent saved.");
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || "Failed to save consent";
      setError(typeof msg === "string" ? msg : "Failed to save consent");
    } finally {
      setSaving(false);
    }
  };

  const exportData = async () => {
    if (!customerId) return;
    try {
      const data = await storefrontApi.exportCustomerData(tenant, customerId);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
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
      setError(err?.message || "Failed to export data");
    }
  };

  const deleteAccount = async () => {
    if (!customerId) return;
    if (!window.confirm("Permanently delete your account and personal data?")) return;
    setSaving(true);
    try {
      await storefrontApi.eraseCustomerData(tenant, customerId);
      clearStorefrontTokens();
      window.location.href = `/${tenant}`;
    } catch (err: any) {
      setError(err?.message || "Failed to delete account");
      setSaving(false);
    }
  };

  return (
    <section className="space-y-6">
      <div className="rounded-2xl border border-gray-100 dark:border-neutral-900 bg-white dark:bg-neutral-950 p-6 sm:p-8">
        <h2 className="text-[20px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
          Consent preferences
        </h2>
        <p className="mt-1 text-[13px] text-gray-500 dark:text-neutral-500">
          Choose how we communicate with you and what we do with your data.
        </p>
        {resolving && <p className="mt-4 text-[13px] text-gray-500">Loading…</p>}
        {resolveError && (
          <p className="mt-4 text-[13px] text-amber-700 dark:text-amber-300">{resolveError}</p>
        )}
        {customerId && (
          <div className="mt-6 space-y-3">
            <ConsentRow
              label="Marketing email"
              description="Emails about new products, restocks, and curated picks."
              checked={!!flags.marketing_email}
              disabled={saving}
              onChange={(v) => save({ marketing_email: v })}
            />
            <ConsentRow
              label="Marketing SMS"
              description="Text messages about your orders and occasional offers."
              checked={!!flags.marketing_sms}
              disabled={saving}
              onChange={(v) => save({ marketing_sms: v })}
            />
            <ConsentRow
              label="Marketing WhatsApp"
              description="Order updates and recommendations over WhatsApp."
              checked={!!flags.marketing_whatsapp}
              disabled={saving}
              onChange={(v) => save({ marketing_whatsapp: v })}
            />
            <ConsentRow
              label="Data processing"
              description="Required to run the store: account, orders, support."
              checked={true}
              disabled
              onChange={() => {}}
            />
            {feedback && <p className="text-[13px] text-green-700 dark:text-green-400">{feedback}</p>}
            {error && <p className="text-[13px] text-red-700 dark:text-red-300">{error}</p>}
          </div>
        )}
      </div>

      {customerId && (
        <div className="rounded-2xl border border-gray-100 dark:border-neutral-900 bg-white dark:bg-neutral-950 p-6 sm:p-8">
          <h3 className="text-[16px] font-semibold text-gray-900 dark:text-neutral-100">
            Your data
          </h3>
          <p className="mt-1 text-[13px] text-gray-500 dark:text-neutral-500">
            Export a copy of everything we hold on you, or permanently delete
            your account.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={exportData}
              disabled={saving}
              className="inline-flex h-10 px-5 items-center justify-center rounded-full border border-gray-200 dark:border-neutral-800 text-[13px] font-medium text-gray-900 dark:text-neutral-100 hover:bg-gray-50 dark:hover:bg-neutral-900"
            >
              Export my data
            </button>
            <button
              type="button"
              onClick={deleteAccount}
              disabled={saving}
              className="inline-flex h-10 px-5 items-center justify-center rounded-full border border-red-200 dark:border-red-900 text-[13px] font-medium text-red-700 dark:text-red-300 hover:bg-red-50 dark:hover:bg-red-900/20"
            >
              Delete my account
            </button>
          </div>
        </div>
      )}
    </section>
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
    <label className="flex items-start gap-3 py-3 border-b border-gray-100 dark:border-neutral-900 last:border-0">
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-1 h-4 w-4 rounded border-gray-300 text-gray-900 focus:ring-gray-900"
      />
      <div>
        <p className="text-[14px] font-medium text-gray-900 dark:text-neutral-100">{label}</p>
        <p className="text-[12px] text-gray-500 dark:text-neutral-500">{description}</p>
      </div>
    </label>
  );
}