"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { SignedIn, SignedOut, SignInButton, SignUpButton, UserButton } from "@clerk/nextjs";
import ThemeToggle from "./theme-toggle";
import { CART_COUNT_KEY, readFromStorage } from "@/lib/cart-events";

/**
 * Storefront chrome (top bar) — Apple-inspired minimal nav.
 *
 *  - Centered wordmark + nav on desktop.
 *  - Cart icon with a live count from localStorage (kept in sync by
 *    CartRefreshBridge mounted at the root).
 *  - Theme toggle on the right.
 *  - Back button is hidden on the tenant home route (`/${tenant}`).
 *    Everywhere else it appears on the left so deep pages can return.
 *  - The current route is reflected as an underline beneath the matching
 *    nav link (Shop / Orders / Account).
 */
export default function StorefrontHeader({
  tenant,
  storeName,
  logoUrl,
}: {
  tenant: string;
  storeName?: string;
  logoUrl?: string | null;
}) {
  const router = useRouter();
  const pathname = usePathname() || `/${tenant}`;
  const onHome = pathname === `/${tenant}` || pathname === `/${tenant}/`;
  const [cartCount, setCartCount] = useState(0);

  // Live cart count via the bridge
  useEffect(() => {
    setCartCount(readFromStorage().count);
    const onChange = () => setCartCount(readFromStorage().count);
    window.addEventListener("infalette-cart-changed", onChange);
    window.addEventListener("storage", (e) => {
      if (e.key === CART_COUNT_KEY) onChange();
    });
    return () => window.removeEventListener("infalette-cart-changed", onChange);
  }, []);

  const handleBack = () => {
    if (typeof window === "undefined") return;
    if (window.history.length > 1) router.back();
    else router.push(`/${tenant}`);
  };

  /**
   * isActive — returns true when `pathname` is inside the given section.
   * The "Account" link also matches /account/consent and any future
   * sub-routes so the indicator stays in sync while navigating inside.
   */
  const isActive = (href: string) => {
    if (pathname === href) return true;
    // Treat the home page as not active for any sub-section.
    if (pathname === `/${tenant}` || pathname === `/${tenant}/`) return false;
    return pathname.startsWith(href + "/") || pathname.startsWith(href);
  };

  const linkBase =
    "relative inline-flex h-14 items-center text-[13px] transition-colors";
  const linkColor = "text-gray-700 dark:text-neutral-300";
  const linkColorActive = "text-gray-900 dark:text-white font-medium";
  const linkHover = "hover:text-gray-900 dark:hover:text-white";
  const underline =
    "after:absolute after:left-0 after:right-0 after:bottom-0 after:h-[2px] after:bg-gray-900 after:dark:bg-white after:rounded-full";

  return (
    <header className="sticky top-0 z-30 w-full backdrop-blur-xl bg-white/80 dark:bg-black/70 border-b border-gray-200/70 dark:border-neutral-900">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center gap-3">
        {/* Back / wordmark */}
        <div className="flex items-center gap-2 min-w-0">
          {!onHome && (
            <button
              type="button"
              onClick={handleBack}
              aria-label="Go back"
              title="Go back"
              className="inline-flex h-9 w-9 items-center justify-center rounded-full text-gray-700 dark:text-neutral-200 hover:bg-gray-100 dark:hover:bg-neutral-900 transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
                <polyline points="15 18 9 12 15 6" />
              </svg>
            </button>
          )}
          <Link
            href={`/${tenant}`}
            className="flex items-center gap-2 text-[15px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100 truncate"
          >
            {logoUrl ? (
              <img src={logoUrl} alt={storeName || tenant} className="h-7 w-7 rounded-md object-cover" />
            ) : null}
            <span className="truncate">{storeName || "Infalette"}</span>
          </Link>
        </div>

        {/* Primary nav (desktop). The active link gets an underline + weight. */}
        <nav className="hidden md:flex items-center gap-7 ml-6">
          <Link
            href={`/${tenant}/products`}
            aria-current={isActive(`/${tenant}/products`) ? "page" : undefined}
            className={`${linkBase} ${isActive(`/${tenant}/products`) ? `${linkColorActive} ${underline}` : `${linkColor} ${linkHover}`}`}
          >
            Shop
          </Link>
          <Link
            href={`/${tenant}/orders`}
            aria-current={isActive(`/${tenant}/orders`) ? "page" : undefined}
            className={`${linkBase} ${isActive(`/${tenant}/orders`) ? `${linkColorActive} ${underline}` : `${linkColor} ${linkHover}`}`}
          >
            Orders
          </Link>
          <Link
            href={`/${tenant}/account`}
            aria-current={isActive(`/${tenant}/account`) ? "page" : undefined}
            className={`${linkBase} ${isActive(`/${tenant}/account`) ? `${linkColorActive} ${underline}` : `${linkColor} ${linkHover}`}`}
          >
            Account
          </Link>
        </nav>

        {/* Right-side actions */}
        <div className="ml-auto flex items-center gap-1.5">
          <ThemeToggle />
          <SignedOut>
            <SignInButton mode="modal">
              <button
                type="button"
                className="inline-flex h-9 px-4 items-center justify-center rounded-full text-[13px] font-medium text-gray-700 dark:text-neutral-200 hover:bg-gray-100 dark:hover:bg-neutral-900 transition-colors"
              >
                Sign in
              </button>
            </SignInButton>
            <SignUpButton mode="modal">
              <button
                type="button"
                className="inline-flex h-9 px-4 items-center justify-center rounded-full text-[13px] font-medium bg-gray-900 dark:bg-white text-white dark:text-black hover:opacity-90 transition-opacity"
              >
                Sign up
              </button>
            </SignUpButton>
          </SignedOut>
          <SignedIn>
            <UserButton afterSignOutUrl={`/${tenant}`} />
          </SignedIn>
          <Link
            href={`/${tenant}/cart`}
            aria-label="Cart"
            aria-current={isActive(`/${tenant}/cart`) ? "page" : undefined}
            className={`relative inline-flex h-9 w-9 items-center justify-center rounded-full transition-colors ${
              isActive(`/${tenant}/cart`)
                ? "bg-gray-100 dark:bg-neutral-900 text-gray-900 dark:text-white"
                : "text-gray-700 dark:text-neutral-200 hover:bg-gray-100 dark:hover:bg-neutral-900"
            }`}
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
              <circle cx="9" cy="20" r="1.5" />
              <circle cx="17" cy="20" r="1.5" />
              <path d="M3 4h2l2.4 9.2a2 2 0 0 0 2 1.6h7.2a2 2 0 0 0 2-1.5L21 8H6" />
            </svg>
            {cartCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 inline-flex items-center justify-center rounded-full text-[10px] font-semibold bg-blue-600 text-white">
                {cartCount > 99 ? "99+" : cartCount}
              </span>
            )}
          </Link>
        </div>
      </div>
    </header>
  );
}