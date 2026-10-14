"use client";

import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export default function NewsletterForm({
  storeId,
  themeColor,
}: {
  storeId?: string | null;
  themeColor: string;
}) {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "loading" | "done" | "error">("idle");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.includes("@")) {
      setState("error");
      return;
    }
    setState("loading");
    try {
      const res = await fetch(`${API_URL}/public/newsletter`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, store_id: storeId }),
      });
      setState(res.ok ? "done" : "error");
      if (res.ok) setEmail("");
    } catch {
      setState("error");
    }
  }

  return (
    <form onSubmit={submit} className="flex gap-2 mt-4 max-w-md mx-auto">
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Your email"
        className="flex-1 border rounded-full px-4 py-2 text-sm"
        required
      />
      <button
        type="submit"
        disabled={state === "loading"}
        className="px-6 py-2 rounded-full text-white font-medium disabled:opacity-60"
        style={{ backgroundColor: themeColor }}
      >
        {state === "done" ? "Subscribed ✓" : state === "loading" ? "..." : "Subscribe"}
      </button>
      {state === "error" && (
        <p className="text-xs text-red-500 self-center">Try again</p>
      )}
    </form>
  );
}
