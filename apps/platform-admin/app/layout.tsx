import "./globals.css";
import { Inter } from "next/font/google";
import { ClerkProvider, SignedIn, SignedOut, SignInButton, UserButton } from "@clerk/nextjs";
import AuthGuard from "@/components/auth-guard";
import LogoutButton from "@/components/logout-button";
import { ThemeProvider } from "@/components/theme-provider";
import ThemeToggle from "@/components/theme-toggle";
import { Toaster } from "@/components/toaster";
import { BackButton } from "@/components/back-button";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  weight: ["300", "400", "500", "600", "700"],
});

export const metadata = {
  title: "Infalette Platform",
  description: "Internal operations console for Infalette",
};

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/tenants", label: "Tenants" },
  { href: "/subscriptions", label: "Subscriptions" },
  { href: "/users", label: "Users" },
  { href: "/themes", label: "Themes" },
  { href: "/integrations", label: "Integrations" },
  { href: "/health", label: "Health" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: "(function(){try{var t=localStorage.getItem('infalette-theme');var e=(t==='dark'||t==='light')?t:(window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');if(e==='dark'){document.documentElement.classList.add('dark');}document.documentElement.setAttribute('data-theme',e);}catch(e){}})();",
          }}
        />
      </head>
      <body
        className={`${inter.className} font-sans antialiased`}
        style={{ fontFeatureSettings: '"ss01", "cv11"' }}
      >
        <ClerkProvider>
          <ThemeProvider>
          <div className="flex h-screen bg-white text-gray-900 dark:bg-black dark:text-neutral-100">
            <nav className="w-64 flex-shrink-0 border-r border-gray-100 dark:border-neutral-900 bg-white dark:bg-black flex flex-col">
              <div className="px-5 py-5 border-b border-gray-100 dark:border-neutral-900">
                <div className="flex items-center gap-2">
                  <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-gray-900 dark:bg-white text-white dark:text-black font-semibold text-[14px]">
                    P
                  </span>
                  <div>
                    <p className="text-[15px] font-semibold tracking-tight">Platform</p>
                    <p className="text-[11px] text-gray-500 dark:text-neutral-500">Infalette</p>
                  </div>
                </div>
              </div>
              <ul className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
                {NAV.map((n) => (
                  <li key={n.href}>
                    <a
                      href={n.href}
                      className="block px-3 h-9 leading-9 rounded-lg text-[13.5px] text-gray-600 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-950 transition-colors"
                    >
                      {n.label}
                    </a>
                  </li>
                ))}
              </ul>
              <div className="px-3 py-3 border-t border-gray-100 dark:border-neutral-900 flex items-center justify-between">
                <LogoutButton />
                <ThemeToggle />
              </div>
            </nav>
            <main className="flex-1 overflow-y-auto bg-white dark:bg-black">
              <div className="sticky top-0 z-10 backdrop-blur-xl bg-white/80 dark:bg-black/70 border-b border-gray-100 dark:border-neutral-900 h-14 px-4 sm-6 flex items-center justify-between">
                <BackButton />
                <div className="flex items-center gap-2">
                  <SignedOut>
                    <SignInButton mode="modal">
                      <button
                        type="button"
                        className="inline-flex h-9 px-4 items-center justify-center rounded-full text-[13px] font-medium bg-gray-900 dark:bg-white text-white dark:text-black"
                      >
                        Sign in
                      </button>
                    </SignInButton>
                  </SignedOut>
                  <SignedIn>
                    <UserButton afterSignOutUrl="/login" />
                  </SignedIn>
                </div>
              </div>
              <div className="px-4 sm:px-6 py-6">
                <AuthGuard>{children}</AuthGuard>
              </div>
            </main>
          </div>
          <Toaster />
          </ThemeProvider>
        </ClerkProvider>
      </body>
    </html>
  );
}