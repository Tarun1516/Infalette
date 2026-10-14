import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";
import AttributionCapture from "@/components/attribution-capture";
import { ThemeProvider } from "@/components/theme-provider";
import { Toaster } from "@/components/toaster";
import { CartRefreshBridge } from "@/components/cart-refresh-bridge";

const inter = Inter({
  subsets: ["latin"],
  // System-font weight axes — the storefront now leans on the same
  // tight, geometric feel as Apple's SF Pro. Inter is the closest
  // open-source proxy we can ship without bundling proprietary fonts.
  display: "swap",
  weight: ["300", "400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Infalette",
  description: "White-label social commerce platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/*
          Inline pre-hydration script: applies the saved theme class on
          first paint so the page never flashes the wrong colors while
          React is still booting. The value comes from the same
          localStorage key the ThemeProvider writes.
        */}
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
            <AttributionCapture />
            <CartRefreshBridge />
            {children}
            <Toaster />
          </ThemeProvider>
        </ClerkProvider>
      </body>
    </html>
  );
}