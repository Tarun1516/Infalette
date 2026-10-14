/**
 * ProductHighlights — three-up icon row that summarises the most
 * important product attributes. Pure presentational component.
 *
 * Pulls icons from the same lucide-style SVG icons we use elsewhere
 * so the entire storefront stays consistent (one icon language).
 */
export default function ProductHighlights({ product }: { product: any }) {
  const items: { label: string; value: string; icon: JSX.Element }[] = [];

  if (product.age_suitability) {
    items.push({
      label: "Age suitability",
      value: String(product.age_suitability).replace(/_/g, " "),
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="w-6 h-6">
          <circle cx="12" cy="8" r="4" />
          <path d="M4 21c1.5-4 5-6 8-6s6.5 2 8 6" />
        </svg>
      ),
    });
  }
  if (product.pregnancy_stage) {
    items.push({
      label: "Stage",
      value: String(product.pregnancy_stage).replace(/_/g, " "),
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="w-6 h-6">
          <path d="M12 21c4-3 7-6 7-11a7 7 0 1 0-14 0c0 5 3 8 7 11z" />
          <circle cx="12" cy="10" r="2.5" />
        </svg>
      ),
    });
  }
  if (product.tax_class) {
    items.push({
      label: "Tax class",
      value: product.tax_class === "reduced" ? "5% GST" : "Standard",
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="w-6 h-6">
          <path d="M4 4h12l4 4v12H4z" />
          <path d="M16 4v4h4M9 12h6M9 16h4" />
        </svg>
      ),
    });
  }
  // Always-on shipping/highlight
  items.push({
    label: "Delivery",
    value: "Pan-India · 2-5 days",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="w-6 h-6">
        <rect x="1" y="6" width="14" height="11" rx="2" />
        <path d="M15 9h4l3 4v4h-7M5.5 19.5a2 2 0 1 0 0-.4M18.5 19.5a2 2 0 1 0 0-.4" />
      </svg>
    ),
  });

  return (
    <section className="bg-gray-50 dark:bg-neutral-950 border-y border-gray-100 dark:border-neutral-900">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          {items.map((it, idx) => (
            <div key={idx} className="flex items-start gap-3">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-white dark:bg-neutral-900 border border-gray-200 dark:border-neutral-800 flex items-center justify-center text-gray-700 dark:text-neutral-300">
                {it.icon}
              </div>
              <div className="min-w-0">
                <p className="text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500">
                  {it.label}
                </p>
                <p className="mt-1 text-[15px] font-medium text-gray-900 dark:text-neutral-100 capitalize">
                  {it.value}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}