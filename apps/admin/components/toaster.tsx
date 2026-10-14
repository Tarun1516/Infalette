"use client";

import { useEffect, useState } from "react";

export type ToastKind = "info" | "success" | "error" | "warning";

export interface ToastInput {
  kind?: ToastKind;
  title: string;
  description?: string;
  /** ms before auto-dismiss. 0 = no auto-dismiss. */
  durationMs?: number;
}

export interface Toast extends Required<Omit<ToastInput, "description">> {
  id: string;
  description?: string;
}

// Module-level event bus. Components fire `toast({...})` and the
// mounted <Toaster/> subscribes and renders the stack. Survives route
// changes because the bus lives on `window`.
type Listener = (toast: Toast) => void;
const listeners = new Set<Listener>();

export function toast(input: ToastInput) {
  if (typeof window === "undefined") return;
  const evt: Toast = {
    id: Math.random().toString(36).slice(2) + Date.now().toString(36),
    kind: input.kind || "info",
    title: input.title,
    description: input.description,
    durationMs: input.durationMs ?? 4000,
  };
  listeners.forEach((fn) => fn(evt));
}

/** Promise helper: shows a loading toast then resolves to success/error. */
export async function promiseToast<T>(p: Promise<T>, messages: { loading: string; success: (v: T) => string; error: (e: any) => string }) {
  const id = Math.random().toString(36).slice(2) + Date.now().toString(36);
  const evt: Toast = { id, kind: "info", title: messages.loading, durationMs: 0 };
  listeners.forEach((fn) => fn(evt));
  try {
    const v = await p;
    // Replace by dispatching a success toast and dismissing the loading one
    dismiss(id);
    toast({ kind: "success", title: messages.success(v) });
    return v;
  } catch (e) {
    dismiss(id);
    toast({ kind: "error", title: messages.error(e) });
    throw e;
  }
}

export function dismiss(id: string) {
  window.dispatchEvent(new CustomEvent("infalette-toast-dismiss", { detail: { id } }));
}

export function Toaster() {
  const [items, setItems] = useState<Toast[]>([]);

  useEffect(() => {
    const onAdd: Listener = (t) => {
      setItems((prev) => [...prev, t]);
      if (t.durationMs > 0) {
        setTimeout(() => dismiss(t.id), t.durationMs);
      }
    };
    const onDismiss = (e: Event) => {
      const id = (e as CustomEvent<{ id: string }>).detail?.id;
      if (!id) return;
      setItems((prev) => prev.filter((p) => p.id !== id));
    };
    listeners.add(onAdd);
    window.addEventListener("infalette-toast-dismiss", onDismiss);
    return () => {
      listeners.delete(onAdd);
      window.removeEventListener("infalette-toast-dismiss", onDismiss);
    };
  }, []);

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm pointer-events-none">
      {items.map((t) => {
        const palette = PALETTE[t.kind];
        return (
          <div
            key={t.id}
            role="status"
            className={`pointer-events-auto rounded-lg shadow-lg border ${palette.border} ${palette.bg} text-sm text-gray-900 dark:text-gray-100 overflow-hidden`}
          >
            <div className="px-4 py-3 flex items-start gap-3">
              <span className={`mt-0.5 inline-flex w-5 h-5 items-center justify-center rounded-full ${palette.icon} text-white text-xs font-bold`}>
                {t.kind === "success" ? "✓" : t.kind === "error" ? "!" : t.kind === "warning" ? "!" : "i"}
              </span>
              <div className="flex-1">
                <div className="font-semibold">{t.title}</div>
                {t.description && (
                  <div className="mt-1 text-xs text-gray-700 dark:text-gray-300">{t.description}</div>
                )}
              </div>
              <button
                type="button"
                aria-label="Dismiss"
                onClick={() => dismiss(t.id)}
                className="ml-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
              >
                ×
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

const PALETTE: Record<ToastKind, { bg: string; border: string; icon: string }> = {
  info: {
    bg: "bg-white dark:bg-gray-800",
    border: "border-gray-200 dark:border-gray-700",
    icon: "bg-blue-500",
  },
  success: {
    bg: "bg-white dark:bg-gray-800",
    border: "border-green-300 dark:border-green-700",
    icon: "bg-green-500",
  },
  error: {
    bg: "bg-white dark:bg-gray-800",
    border: "border-red-300 dark:border-red-700",
    icon: "bg-red-500",
  },
  warning: {
    bg: "bg-white dark:bg-gray-800",
    border: "border-yellow-300 dark:border-yellow-700",
    icon: "bg-yellow-500",
  },
};
