"use client";

/**
 * Minimal modal dialog.
 *
 * Apple-style: rounded-3xl, dimmed backdrop, no Tailwind plugin
 * dependency. Renders a labelled title, optional description, and
 * whatever children the caller supplies (usually a form).
 */
import { useEffect } from "react";

export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  size = "md",
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  size?: "sm" | "md" | "lg";
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    // Lock background scroll while the dialog is open
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  if (!open) return null;

  const widths = {
    sm: "max-w-sm",
    md: "max-w-md",
    lg: "max-w-2xl",
  } as const;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="dialog-title"
    >
      <div
        className={`w-full ${widths[size]} rounded-3xl bg-white dark:bg-neutral-950 border border-gray-100 dark:border-neutral-900 shadow-2xl overflow-hidden`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-6 py-5 border-b border-gray-100 dark:border-neutral-900">
          <h2 id="dialog-title" className="text-[20px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
            {title}
          </h2>
          {description && (
            <p className="mt-1 text-[13px] text-gray-500 dark:text-neutral-500">{description}</p>
          )}
        </div>
        <div className="px-6 py-5">{children}</div>
      </div>
    </div>
  );
}