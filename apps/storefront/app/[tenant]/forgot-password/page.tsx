"use client";

import { useState } from "react";
import { useParams } from "next/navigation";

export default function ForgotPasswordPage() {
  const params = useParams<{ tenant: string }>();
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "sent" | "error">("idle");
  const [devToken, setDevToken] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      const res = await fetch(`${base}/auth/forgot-password`, {
        method: "POST",
        headers: { "content-type": "application/json", "X-Tenant": params.tenant },
        body: JSON.stringify({ email }),
      });
      const data = await res.json().catch(() => ({}));
      setStatus(res.ok ? "sent" : "error");
      setDevToken(data?.reset_token || null);
    } catch {
      setStatus("error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
      <form onSubmit={submit} className="bg-white p-8 rounded-2xl shadow w-full max-w-md space-y-4">
        <h1 className="text-2xl font-bold">Forgot password</h1>
        {status === "sent" ? (
          <>
            <p className="text-green-700 text-sm">If the account exists, a reset link has been sent.</p>
            {devToken && (
              <p className="text-xs text-gray-500 break-all">
                Dev token (non-production):{" "}
                <a className="underline" href={`/${params.tenant}/reset-password?token=${devToken}`}>
                  open reset page
                </a>
              </p>
            )}
          </>
        ) : (
          <>
            {status === "error" && <p className="text-red-600 text-sm">Something went wrong.</p>}
            <input type="email" required className="w-full p-3 border rounded-lg" placeholder="Your account email" value={email} onChange={(e) => setEmail(e.target.value)} />
            <button disabled={busy} className="w-full py-3 rounded-lg text-white font-semibold bg-blue-600 disabled:opacity-50">
              {busy ? "Sending…" : "Send reset link"}
            </button>
          </>
        )}
      </form>
    </div>
  );
}
