"use client";

import { Suspense, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";

function ResetForm() {
  const params = useParams<{ tenant: string }>();
  const search = useSearchParams();
  const [token, setToken] = useState(search.get("token") || "");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<"idle" | "done" | "error">("idle");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      const res = await fetch(`${base}/auth/reset-password`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ token, new_password: password }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || "Reset failed");
      setStatus("done");
    } catch (err: any) {
      setStatus("error");
      setMessage(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
      <form onSubmit={submit} className="bg-white p-8 rounded-2xl shadow w-full max-w-md space-y-4">
        <h1 className="text-2xl font-bold">Set a new password</h1>
        {status === "done" ? (
          <p className="text-green-700 text-sm">Password updated. You can now log in.</p>
        ) : (
          <>
            {status === "error" && <p className="text-red-600 text-sm">{message}</p>}
            <input required className="w-full p-3 border rounded-lg font-mono text-xs" placeholder="Reset token" value={token} onChange={(e) => setToken(e.target.value)} />
            <input type="password" required minLength={8} className="w-full p-3 border rounded-lg" placeholder="New password (min 8 chars)" value={password} onChange={(e) => setPassword(e.target.value)} />
            <button disabled={busy} className="w-full py-3 rounded-lg text-white font-semibold bg-blue-600 disabled:opacity-50">
              {busy ? "Updating…" : "Update password"}
            </button>
          </>
        )}
      </form>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-gray-50" />}>
      <ResetForm />
    </Suspense>
  );
}
