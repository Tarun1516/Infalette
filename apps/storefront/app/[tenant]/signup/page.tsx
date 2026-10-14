"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { setStorefrontTokens } from "@/lib/auth";

export default function SignupPage() {
  const params = useParams<{ tenant: string }>();
  const search = useSearchParams();
  const next = search.get("next") || `/${params.tenant}/account`;

  const [form, setForm] = useState({ email: "", password: "", first_name: "", last_name: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"}/auth/customer/register`,
        {
          method: "POST",
          headers: { "content-type": "application/json", "X-Tenant": params.tenant },
          body: JSON.stringify(form),
        }
      );
      if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail || "Signup failed");
      const data = await res.json();
      setStorefrontTokens(data.access_token, data.refresh_token);
      window.location.href = next;
    } catch (err: any) {
      setError(err.message || "Signup failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-black px-4">
      <form onSubmit={submit} className="w-full max-w-md rounded-2xl border border-gray-100 dark:border-neutral-900 bg-white dark:bg-neutral-950 p-8 space-y-3">
        <div className="text-center">
          <h1 className="text-[28px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
            Create your account
          </h1>
          <p className="mt-2 text-[13px] text-gray-500 dark:text-neutral-500">
            Set up your account in under a minute.
          </p>
        </div>
        {error && (
          <p className="text-[13px] text-red-700 dark:text-red-300 rounded-xl border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-900/10 px-4 py-2">
            {error}
          </p>
        )}
        <input
          className="w-full h-12 rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-5 text-[14px] focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="First name"
          value={form.first_name}
          onChange={(e) => setForm({ ...form, first_name: e.target.value })}
        />
        <input
          className="w-full h-12 rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-5 text-[14px] focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Last name"
          value={form.last_name}
          onChange={(e) => setForm({ ...form, last_name: e.target.value })}
        />
        <input
          type="email"
          required
          className="w-full h-12 rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-5 text-[14px] focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Email"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
        />
        <input
          type="password"
          required
          minLength={8}
          className="w-full h-12 rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-5 text-[14px] focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Password (min 8 chars)"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
        />
        <button
          type="submit"
          disabled={busy}
          className="w-full h-12 rounded-full bg-blue-600 disabled:bg-gray-300 text-white text-[15px] font-medium hover:bg-blue-700 transition-colors"
        >
          {busy ? "Creating…" : "Create account"}
        </button>
        <p className="text-[13px] text-gray-500 dark:text-neutral-500 text-center mt-2">
          Already have an account?{" "}
          <Link
            href={`/${params.tenant}/login?next=${encodeURIComponent(next)}`}
            className="text-blue-600 dark:text-blue-400 hover:underline"
          >
            Sign in
          </Link>
        </p>
      </form>
    </div>
  );
}