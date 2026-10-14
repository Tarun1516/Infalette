"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { isStorefrontLoggedIn, subscribeStorefrontAuth } from "@/lib/auth";

/**
 * AuthGate — wraps pages that require a logged-in customer.
 *
 * - If the visitor has a token, render the children.
 * - Otherwise render a friendly onboarding screen with sign-in and
 *   sign-up CTAs (and a Track-an-order escape hatch for guests).
 * - Watches localStorage so logging in elsewhere updates this view.
 *
 * Intentionally unstyled chrome here so it inherits the page padding;
 * child pages still own their layout.
 */
export default function AuthGate({
  tenant,
  children,
}: {
  tenant: string;
  children: React.ReactNode;
}) {
  const [authed, setAuthed] = useState<boolean | null>(null);

  useEffect(() => {
    setAuthed(isStorefrontLoggedIn());
    const unsub = subscribeStorefrontAuth(() => setAuthed(isStorefrontLoggedIn()));
    return unsub;
  }, []);

  if (authed === null) {
    // Avoid flashing the gate during the first hydration tick.
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-16 text-center text-[13px] text-gray-500 dark:text-neutral-500">
        Loading…
      </div>
    );
  }

  if (!authed) {
    return <SignInPrompt tenant={tenant} />;
  }

  return <>{children}</>;
}

function SignInPrompt({ tenant }: { tenant: string }) {
  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-16 sm:py-24">
      <div className="text-center">
        <div className="mx-auto inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-gray-900 dark:bg-white text-white dark:text-black text-[20px] font-semibold">
          I
        </div>
        <h1 className="mt-6 text-[32px] sm:text-[40px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
          Sign in to continue
        </h1>
        <p className="mt-3 text-[15px] text-gray-500 dark:text-neutral-400 max-w-md mx-auto">
          Your orders, returns, account details and consent preferences live
          behind sign-in. New here — create an account in under a minute.
        </p>
      </div>

      <div className="mt-10 grid sm:grid-cols-2 gap-4">
        <Link
          href={`/${tenant}/login?next=/${tenant}/account`}
          className="rounded-2xl border border-gray-100 dark:border-neutral-900 bg-white dark:bg-neutral-950 p-6 hover:border-gray-300 dark:hover:border-neutral-700 transition-colors"
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
          className="rounded-2xl border border-gray-900 dark:border-white bg-gray-900 dark:bg-white p-6 hover:opacity-90 transition-opacity"
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