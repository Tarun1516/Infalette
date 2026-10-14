"use client";

import { useState } from "react";
import { SignedIn, SignedOut, SignInButton, SignUpButton, UserButton } from "@clerk/nextjs";
import { adminApi } from "@/lib/api";
import { AuthManager } from "@/lib/auth";
import { toast } from "@/components/toaster";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const data = await adminApi.login(email, password);
      AuthManager.setToken(data.access_token);
      window.location.href = "/dashboard";
    } catch (error: any) {
      toast({ kind: "error", title: "Login failed", description: error?.message });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-black px-6">
      <div className="w-full max-w-sm">
        <div className="text-center">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-gray-900 dark:bg-white text-white dark:text-black text-[18px] font-semibold">
            I
          </div>
          <h1 className="mt-6 text-[28px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
            Infalette Admin
          </h1>
          <p className="mt-2 text-[14px] text-gray-500 dark:text-neutral-500">
            Sign in to manage your storefront.
          </p>
        </div>

        <form onSubmit={handleLogin} className="mt-8 space-y-3">
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full h-12 rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-5 text-[14px] focus:outline-none focus:ring-2 focus:ring-blue-500"
            required
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full h-12 rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-5 text-[14px] focus:outline-none focus:ring-2 focus:ring-blue-500"
            required
          />
          <button
            type="submit"
            disabled={submitting}
            className="w-full h-12 rounded-full bg-blue-600 disabled:bg-gray-300 text-white text-[15px] font-medium hover:bg-blue-700 transition-colors"
          >
            {submitting ? "Signing in…" : "Sign in with password"}
          </button>
        </form>

        <div className="mt-6 flex items-center gap-3">
          <span className="h-px flex-1 bg-gray-200 dark:bg-neutral-800" />
          <span className="text-[12px] text-gray-500">or continue with Clerk</span>
          <span className="h-px flex-1 bg-gray-200 dark:bg-neutral-800" />
        </div>

        <div className="mt-4 flex items-center justify-center gap-3">
          <SignedOut>
            <SignInButton mode="modal">
              <button
                type="button"
                className="h-11 px-6 rounded-full bg-gray-900 dark:bg-white text-white dark:text-black text-[14px] font-medium hover:opacity-90"
              >
                Sign in
              </button>
            </SignInButton>
            <SignUpButton mode="modal">
              <button
                type="button"
                className="h-11 px-6 rounded-full border border-gray-200 dark:border-neutral-800 text-[14px] font-medium hover:bg-gray-50 dark:hover:bg-neutral-950"
              >
                Sign up
              </button>
            </SignUpButton>
          </SignedOut>
          <SignedIn>
            <UserButton afterSignOutUrl="/login" />
          </SignedIn>
        </div>

        <p className="mt-6 text-center text-[12px] text-gray-500 dark:text-neutral-500">
          Default: owner@demo.test / demo1234
        </p>
      </div>
    </div>
  );
}