"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

/**
 * BackButton — top-left navigation control.
 *
 * Calls history.back() when there is a previous page in the same tab,
 * otherwise navigates to the canonical dashboard for the current app.
 * Hidden entirely on the dashboard root (home page).
 */
export function BackButton() {
  const router = useRouter();
  const pathname = usePathname() || "/";
  const [canGoBack, setCanGoBack] = useState(false);

  useEffect(() => {
    // history.length is tab-scoped and only meaningful in the browser.
    setCanGoBack(typeof window !== "undefined" && window.history.length > 1);
  }, [pathname]);

  const onHome =
    pathname === "/" ||
    pathname === "/dashboard" ||
    pathname === "/login";

  if (onHome) return null;

  const handleClick = () => {
    if (canGoBack) router.back();
    else router.push("/dashboard");
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      aria-label="Go back"
      title="Go back"
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 text-sm text-gray-700 dark:text-gray-200 transition-colors"
    >
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
        <polyline points="15 18 9 12 15 6" />
      </svg>
      <span>Back</span>
    </button>
  );
}
