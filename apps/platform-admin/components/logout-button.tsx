"use client";

import { useRouter } from "next/navigation";
import { AuthManager } from "@/lib/auth";
import { platformApi } from "@/lib/api";

export default function LogoutButton() {
  const router = useRouter();

  const handleLogout = async () => {
    try {
      await platformApi.logout();
    } catch {
      /* best-effort — clear locally regardless */
    }
    AuthManager.clearToken();
    router.push("/login");
  };

  return (
    <button
      onClick={handleLogout}
      className="inline-flex h-8 px-3 items-center justify-center rounded-full text-[12.5px] font-medium text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
    >
      Sign out
    </button>
  );
}