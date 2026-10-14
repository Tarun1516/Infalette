"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { SignedIn, SignedOut, SignInButton, UserButton } from "@clerk/nextjs";
import AuthGuard from "./auth-guard";
import ThemeToggle from "./theme-toggle";
import { AuthManager } from "@/lib/auth";
import { Toaster } from "./toaster";

/**
 * AppShell wraps the admin layout. Apple-inspired chrome:
 *  - Slim sidebar (collapses to icons on smaller screens)
 *  - Translucent top bar with optional back button
 *  - Quiet, hairline rules and generous vertical rhythm
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || "/";
  const router = useRouter();
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    setIsLoggedIn(AuthManager.isAuthenticated());
  }, [pathname]);

  const isLogin = pathname === "/login";
  const showChrome = !isLogin && isLoggedIn;

  const navItems = [
    { href: "/dashboard", label: "Dashboard", icon: <IconHome /> },
    { href: "/products", label: "Products", icon: <IconBox /> },
    { href: "/orders", label: "Orders", icon: <IconReceipt /> },
    { href: "/customers", label: "Customers", icon: <IconUser /> },
    { href: "/conversations", label: "Conversations", icon: <IconChat /> },
    { href: "/leads", label: "Leads", icon: <IconTarget /> },
    { href: "/pages", label: "Pages", icon: <IconFile /> },
    { href: "/automation", label: "Automation", icon: <IconBolt /> },
    { href: "/analytics", label: "Analytics", icon: <IconChart /> },
    { href: "/campaigns", label: "Campaigns", icon: <IconSend /> },
    { href: "/coupons", label: "Coupons", icon: <IconTag /> },
    { href: "/reports", label: "Reports", icon: <IconDoc /> },
    { href: "/media", label: "Media", icon: <IconImage /> },
    { href: "/inventory", label: "Inventory", icon: <IconLayers /> },
    { href: "/seo", label: "SEO", icon: <IconSearch /> },
    { href: "/webhooks", label: "Webhooks", icon: <IconLink /> },
    { href: "/domains", label: "Domains", icon: <IconGlobe /> },
    { href: "/team", label: "Team", icon: <IconTeam /> },
    { href: "/settings", label: "Settings", icon: <IconCog /> },
  ];

  return (
    <div className="flex h-screen bg-white text-gray-900 dark:bg-black dark:text-neutral-100">
      {showChrome && (
        <nav className="w-64 flex-shrink-0 border-r border-gray-100 dark:border-neutral-900 bg-white dark:bg-black flex flex-col">
          <div className="px-5 py-5 border-b border-gray-100 dark:border-neutral-900">
            <Link href="/dashboard" className="flex items-center gap-2">
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-gray-900 dark:bg-white text-white dark:text-black font-semibold">
                I
              </span>
              <span className="text-[15px] font-semibold tracking-tight">Infalette Admin</span>
            </Link>
          </div>
          <ul className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
            {navItems.map((it) => {
              const active = pathname === it.href || pathname.startsWith(it.href + "/");
              return (
                <li key={it.href}>
                  <Link
                    href={it.href}
                    className={`flex items-center gap-3 px-3 h-9 rounded-lg text-[13.5px] transition-colors ${
                      active
                        ? "bg-gray-100 dark:bg-neutral-900 text-gray-900 dark:text-neutral-100 font-medium"
                        : "text-gray-600 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-950"
                    }`}
                  >
                    <span className="w-4 h-4 flex items-center justify-center">{it.icon}</span>
                    <span>{it.label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      )}
      <main className="flex-1 overflow-y-auto bg-white dark:bg-black">
        {showChrome && (
          <div className="sticky top-0 z-10 backdrop-blur-xl bg-white/80 dark:bg-black/70 border-b border-gray-100 dark:border-neutral-900 h-14 px-4 sm:px-6 flex items-center justify-between">
            {pathname !== "/dashboard" && pathname !== "/" && pathname !== "/login" ? (
              <button
                type="button"
                onClick={() => {
                  if (window.history.length > 1) router.back();
                  else router.push("/dashboard");
                }}
                aria-label="Go back"
                title="Go back"
                className="inline-flex h-9 w-9 items-center justify-center rounded-full text-gray-700 dark:text-neutral-200 hover:bg-gray-100 dark:hover:bg-neutral-900 transition-colors"
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
                  <polyline points="15 18 9 12 15 6" />
                </svg>
              </button>
            ) : (
              <span />
            )}
            <div className="flex items-center gap-1.5">
              <ThemeToggle />
              <SignedOut>
                <SignInButton mode="modal">
                  <button
                    type="button"
                    className="inline-flex h-9 px-4 items-center justify-center rounded-full text-[13px] font-medium bg-gray-900 dark:bg-white text-white dark:text-black hover:opacity-90 transition-opacity"
                  >
                    Sign in
                  </button>
                </SignInButton>
              </SignedOut>
              <SignedIn>
                <UserButton afterSignOutUrl="/login" />
              </SignedIn>
              {/* Legacy JWT sign-out — remove once Clerk fully replaces /login */}
              <button
                type="button"
                title="Clear legacy API token"
                onClick={() => {
                  AuthManager.clearToken();
                  window.location.href = "/login";
                }}
                className="inline-flex h-9 px-3 items-center justify-center rounded-full text-[12px] text-gray-500 dark:text-neutral-500 hover:bg-gray-100 dark:hover:bg-neutral-900 transition-colors"
              >
                Legacy sign out
              </button>
            </div>
          </div>
        )}
        <div className="px-4 sm:px-6 py-6">
          <AuthGuard>{children}</AuthGuard>
        </div>
      </main>
      <Toaster />
    </div>
  );
}

/* — Inline icon set (lucide-style). One consistent language across the admin shell. — */

function IconHome() { return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M3 11l9-7 9 7v9a2 2 0 0 1-2 2h-4v-7H9v7H5a2 2 0 0 1-2-2z" /></svg>; }
function IconBox() { return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M3 7l9-4 9 4v10l-9 4-9-4zM12 3v18M3 7l9 4 9-4" /></svg>; }
function IconReceipt() { return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M5 3h14v18l-3-2-3 2-3-2-3 2-2-2zM9 7h6M9 11h6M9 15h4" /></svg>; }
function IconUser() { return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="8" r="4" /><path d="M4 21c1.5-4 5-6 8-6s6.5 2 8 6" /></svg>; }
function IconChat() { return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12a8 8 0 1 1-3-6.2L21 4l-1 4.2A8 8 0 0 1 21 12z" /></svg>; }
function IconTarget() { return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1.5" /></svg>; }
function IconFile() { return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6M9 13h6M9 17h4" /></svg>; }
function IconBolt() { return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10" /></svg>; }
function IconChart() { return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M3 3v18h18M7 14l4-4 3 3 5-7" /></svg>; }
function IconSend() { return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4z" /></svg>; }
function IconTag() { return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M20.59 13.41L13 21a2 2 0 0 1-2.83 0L3 13.83V4a2 2 0 0 1 2-2h9.83l7.17 7.17a2 2 0 0 1 0 2.83z" /><circle cx="7.5" cy="7.5" r="1.2" /></svg>; }
function IconDoc() { return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4h12l4 4v12H4z" /><path d="M16 4v4h4M8 12h8M8 16h6" /></svg>; }
function IconImage() { return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8.5" cy="8.5" r="1.5" /><path d="M21 15l-5-5L5 21" /></svg>; }
function IconLayers() { return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><polygon points="12 2 2 7 12 12 22 7" /><polyline points="2 17 12 22 22 17" /><polyline points="2 12 12 17 22 12" /></svg>; }
function IconSearch() { return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="7" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></svg>; }
function IconLink() { return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M10 13a5 5 0 0 0 7.07 0l3-3a5 5 0 0 0-7.07-7.07l-1.5 1.5" /><path d="M14 11a5 5 0 0 0-7.07 0l-3 3a5 5 0 0 0 7.07 7.07l1.5-1.5" /></svg>; }
function IconGlobe() { return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a13 13 0 0 1 0 18M12 3a13 13 0 0 0 0 18" /></svg>; }
function IconTeam() { return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></svg>; }
function IconCog() { return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3h.1a1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8v.1a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></svg>; }