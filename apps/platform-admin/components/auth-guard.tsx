"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { AuthManager } from "@/lib/auth";

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const isPublic = pathname === "/login";
  // Avoid touching localStorage during SSR/prerender — check after mount.
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    setAuthenticated(AuthManager.isAuthenticated());
  }, [pathname]);

  useEffect(() => {
    if (authenticated === false && !isPublic) {
      router.push("/login");
    }
  }, [authenticated, isPublic, router]);

  if (isPublic) return <>{children}</>;
  if (authenticated === null || authenticated === false) {
    if (authenticated === false) return null;
    return <div className="p-12 text-center text-gray-500">Loading…</div>;
  }
  return <>{children}</>;
}
