"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";

type Theme = "light" | "dark" | "system";

interface ThemeContextValue {
  theme: Theme;
  effectiveTheme: "light" | "dark";
  setTheme: (theme: Theme) => void;
  toggle: () => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

const STORAGE_KEY = "infalette-theme";

function getSystemTheme(): "light" | "dark" {
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(theme: Theme) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  const effective = theme === "system" ? getSystemTheme() : theme;
  if (effective === "dark") {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
  root.setAttribute("data-theme", effective);
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("system");
  const [effectiveTheme, setEffectiveTheme] = useState<"light" | "dark">("light");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    // Load saved theme
    const saved = (typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null) as Theme | null;
    const initial: Theme = saved || "system";
    setThemeState(initial);
    const eff = initial === "system" ? getSystemTheme() : initial;
    setEffectiveTheme(eff);
    applyTheme(initial);
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    if (theme !== "system") {
      const eff = theme === "dark" ? "dark" : "light";
      setEffectiveTheme(eff);
      applyTheme(theme);
      return;
    }
    // System theme change listener
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => {
      const eff = mq.matches ? "dark" : "light";
      setEffectiveTheme(eff);
      applyTheme("system");
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [theme, mounted]);

  const setTheme = (next: Theme) => {
    setThemeState(next);
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY, next);
    }
    const eff = next === "system" ? getSystemTheme() : next;
    setEffectiveTheme(eff);
    applyTheme(next);
  };

  const toggle = () => {
    const next = effectiveTheme === "dark" ? "light" : "dark";
    setTheme(next);
  };

  return (
    <ThemeContext.Provider value={{ theme, effectiveTheme, setTheme, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    // Allow components used outside provider (e.g. some static pages) to
    // still call the hook without crashing — return a no-op.
    return {
      theme: "system" as Theme,
      effectiveTheme: "light" as const,
      setTheme: () => {},
      toggle: () => {},
    };
  }
  return ctx;
}
