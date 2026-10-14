"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { adminApiExt, adminApi } from "@/lib/api";
import { toast } from "@/components/toaster";

type StockFilter = "all" | "in_stock" | "low" | "out_of_stock";

export default function InventoryPage() {
  const [low, setLow] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [threshold, setThreshold] = useState(10);
  const [search, setSearch] = useState("");
  const [stockFilter, setStockFilter] = useState<StockFilter>("all");
  const [pending, setPending] = useState<Record<string, boolean>>({});

  async function load() {
    setError("");
    try {
      const [lowRes, prodRes] = await Promise.all([
        adminApiExt.getLowInventory(threshold).catch(() => ({ items: [] })),
        adminApi.getProducts({ per_page: "100" }).catch(() => ({ items: [] })),
      ]);
      const lowList = Array.isArray(lowRes) ? lowRes : lowRes.items || lowRes.data || [];
      const prodList = Array.isArray((prodRes as any)) ? (prodRes as any) : (prodRes as any).items || (prodRes as any).data || [];
      setLow(lowList);
      setProducts(prodList);
    } catch (e: any) {
      setError(e.message);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threshold]);

  // Auto-decrement on every order is handled server-side via the
  // checkout inventory reservation. The buttons below let the seller
  // make manual adjustments (counts, received deliveries, damage).
  async function adjustStock(productId: string, delta: number) {
    if (pending[productId]) return;
    const product = products.find((p: any) => p.id === productId);
    if (!product) return;
    const current = Number(product.inventory_quantity ?? product.inventory ?? 0);
    const next = Math.max(0, current + delta);

    setPending((p) => ({ ...p, [productId]: true }));
    // Optimistic update so the stepper feels instant.
    setProducts((rows) =>
      rows.map((r) =>
        r.id === productId
          ? { ...r, inventory_quantity: next, inventory: next }
          : r,
      ),
    );

    try {
      // Use the dedicated stock endpoint so the request only carries
      // the inventory fields (no need to send the full ProductCreate
      // shape — that's the cause of past "Method Not Allowed" 405s
      // when a row was missing required fields like `slug`).
      await adminApi.adjustStock(productId, next);
      toast({
        kind: "success",
        title: delta > 0 ? "Stock added" : "Stock reduced",
        description: `${product.name}: ${current} → ${next}`,
      });
    } catch (e: any) {
      // Roll back on failure
      setProducts((rows) =>
        rows.map((r) =>
          r.id === productId
            ? { ...r, inventory_quantity: current, inventory: current }
            : r,
        ),
      );
      toast({
        kind: "error",
        title: "Could not update stock",
        description: e?.message || "Please try again",
      });
    } finally {
      setPending((p) => ({ ...p, [productId]: false }));
    }
  }

  // Filter products by stock status — uses real-time in-memory state so
  // changes from the stepper are reflected without a refetch.
  const filteredProducts = products
((p) => {
    const matchesSearch = !search
      || p.name?.toLowerCase().includes(search.toLowerCase())
      || p.sku?.toLowerCase().includes(search.toLowerCase());
    if (!matchesSearch) return false;
    const stock = Number(p.inventory_quantity ?? p.inventory ?? 0);
    if (stockFilter === "out_of_stock") return stock === 0;
    if (stockFilter === "low") return stock > 0 && stock <= threshold;
    if (stockFilter === "in_stock") return stock > threshold;
    return true;
  });

  const outOfStock = products.filter(
    (p) => Number(p.inventory_quantity ?? p.inventory ?? 0) === 0,
  ).length;
  const lowStock = products.filter((p) => {
    const stock = Number(p.inventory_quantity ?? p.inventory ?? 0);
    return stock > 0 && stock <= threshold;
  }).length;

  const stockBadge = (stock: number) => {
    if (stock === 0)
      return "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300";
    if (stock <= threshold)
      return "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300";
    return "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300";
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <p className="text-[12px] uppercase tracking-[0.18em] text-gray-500 dark:text-neutral-500">
            Stock
          </p>
          <h1 className="mt-2 text-[36px] sm:text-[44px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
            Inventory
          </h1>
          <p className="mt-1 text-[13px] text-gray-500 dark:text-neutral-500">
            Stock is decremented automatically when a customer checks out.
            Use the stepper below for manual adjustments (restocks, damage).
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[12px] text-gray-500 dark:text-neutral-500">Low-stock at</span>
          <input
            type="number"
            min={1}
            value={threshold}
            onChange={(e) => setThreshold(Math.max(1, Number(e.target.value) || 10))}
            className="h-9 w-20 rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-3 text-[13px]"
          />
        </div>
      </div>

      {error && (
        <div className="rounded-2xl border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-900/10 px-4 py-3 text-[13px] text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div className="rounded-2xl bg-white dark:bg-neutral-950 border border-gray-100 dark:border-neutral-900 p-5">
          <p className="text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500">
            Total products
          </p>
          <p className="mt-3 text-[28px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
            {products.length}
          </p>
        </div>
        <div className="rounded-2xl bg-white dark:bg-neutral-950 border border-gray-100 dark:border-neutral-900 p-5">
          <p className="text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500">
            Low stock
          </p>
          <p className="mt-3 text-[28px] font-semibold tracking-tight text-amber-600 dark:text-amber-300">
            {lowStock}
          </p>
        </div>
        <div className="rounded-2xl bg-white dark:bg-neutral-950 border border-gray-100 dark:border-neutral-900 p-5">
          <p className="text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500">
            Out of stock
          </p>
          <p className="mt-3 text-[28px] font-semibold tracking-tight text-red-600 dark:text-red-300">
            {outOfStock}
          </p>
        </div>
      </div>

      <section className="rounded-2xl bg-white dark:bg-neutral-950 border border-gray-100 dark:border-neutral-900 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 dark:border-neutral-900 flex flex-wrap items-center gap-3">
          <div>
            <h2 className="text-[15px] font-semibold text-gray-900 dark:text-neutral-100">
              Stock levels
            </h2>
            <p className="text-[12px] text-gray-500 dark:text-neutral-500">
              Adjust with − / +. Real-time updates — no need to refresh.
            </p>
          </div>
          <div className="ml-auto flex items-center gap-2 flex-wrap">
            <div className="relative">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                <circle cx="11" cy="11" r="7" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by name or SKU"
                className="h-9 rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 pl-9 pr-4 text-[13px] w-56"
              />
            </div>
            <div className="inline-flex rounded-full border border-gray-200 dark:border-neutral-800 p-0.5">
              {(
                [
                  { id: "all", label: "All" },
                  { id: "in_stock", label: "In stock" },
                  { id: "low", label: "Low" },
                  { id: "out_of_stock", label: "Out" },
                ] as { id: StockFilter; label: string }[]
              ).map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setStockFilter(s.id)}
                  className={`h-8 px-3 rounded-full text-[12px] font-medium ${
                    stockFilter === s.id
                      ? "bg-gray-900 dark:bg-white text-white dark:text-black"
                      : "text-gray-600 dark:text-neutral-400"
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {filteredProducts.length === 0 ? (
          <div className="p-12 text-center text-[13px] text-gray-500 dark:text-neutral-500">
            {products.length === 0
              ? "No products yet — create one to start tracking stock."
              : "No products match the current filter."}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead className="bg-gray-50 dark:bg-neutral-900 text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500">
                <tr>
                  <th className="text-left px-5 py-3 font-medium">Product</th>
                  <th className="text-left px-5 py-3 font-medium">SKU</th>
                  <th className="text-left px-5 py-3 font-medium">Status</th>
                  <th className="text-right px-5 py-3 font-medium">Quantity</th>
                  <th className="text-right px-5 py-3 font-medium">Adjust</th>
                </tr>
              </thead>
              <tbody>
                {filteredProducts.map((p) => {
                  const stock = Number(p.inventory_quantity ?? p.inventory ?? 0);
                  const busy = !!pending[p.id];
                  return (
                    <tr key={p.id} className="border-t border-gray-100 dark:border-neutral-900">
                      <td className="px-5 py-3">
                        <Link
                          href={`/products/${p.id}`}
                          className="font-medium text-gray-900 dark:text-neutral-100 hover:underline"
                        >
                          {p.name}
                        </Link>
                      </td>
                      <td className="px-5 py-3 text-gray-600 dark:text-neutral-400 font-mono text-[12px]">
                        {p.sku || "—"}
                      </td>
                      <td className="px-5 py-3">
                        <span
                          className={`inline-flex px-2 py-0.5 rounded-full text-[11px] font-medium ${stockBadge(stock)}`}
                        >
                          {stock === 0 ? "Out of stock" : stock <= threshold ? "Low stock" : "In stock"}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-right">
                        <span
                          className={`font-mono text-[15px] font-semibold ${
                            stock === 0
                              ? "text-red-600 dark:text-red-400"
                              : stock <= threshold
                              ? "text-amber-600 dark:text-amber-400"
                              : "text-gray-900 dark:text-neutral-100"
                          }`}
                        >
                          {stock}
                        </span>
                      </td>
                      <td className="px-5 py-3">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            type="button"
                            disabled={busy || stock <= 0}
                            onClick={() => adjustStock(p.id, -1)}
                            className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-gray-200 dark:border-neutral-800 hover:bg-gray-50 dark:hover:bg-neutral-900 disabled:opacity-40 disabled:cursor-not-allowed text-[15px]"
                            aria-label={`Decrease ${p.name}`}
                          >
                            −
                          </button>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => adjustStock(p.id, 1)}
                            className="inline-flex h-8 px-3 items-center justify-center rounded-full border border-gray-200 dark:border-neutral-800 hover:bg-gray-50 dark:hover:bg-neutral-900 disabled:opacity-40 disabled:cursor-not-allowed text-[13px] font-medium"
                            aria-label={`Increase ${p.name}`}
                          >
                            +1
                          </button>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => adjustStock(p.id, 10)}
                            className="inline-flex h-8 px-3 items-center justify-center rounded-full border border-gray-200 dark:border-neutral-800 hover:bg-gray-50 dark:hover:bg-neutral-900 disabled:opacity-40 disabled:cursor-not-allowed text-[13px] font-medium"
                            aria-label={`Add 10 to ${p.name}`}
                          >
                            +10
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {low.length > 0 && (
        <section className="rounded-2xl bg-white dark:bg-neutral-950 border border-amber-200 dark:border-amber-900 overflow-hidden">
          <div className="px-5 py-4 border-b border-amber-200 dark:border-amber-900 flex items-center gap-2">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 text-amber-600">
              <path d="M10.29 3.86L1.82 18a2  2 0 0 0 1.71 3h16.94a2  2 0 0 0 1.71-3L13.71 3.86a2  2 0 0 0-3.42 0zM12 9v4M12 17h.01" />
            </svg>
            <h2 className="text-[15px] font-semibold text-amber-700 dark:text-amber-300">
              Low stock alerts ({low.length})
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead className="bg-amber-50/50 dark:bg-amber-900/10 text-[12px] uppercase tracking-[0.16em] text-amber-700 dark:text-amber-300">
                <tr>
                  <th className="text-left px-5 py-3 font-medium">Product</th>
                  <th className="text-left px-5 py-3 font-medium">SKU</th>
                  <th className="text-right px-5 py-3 font-medium">Stock</th>
                </tr>
              </thead>
              <tbody>
                {low.map((p: any) => (
                  <tr key={p.id} className="border-t border-amber-100 dark:border-amber-900/50">
                    <td className="px-5 py-3">
                      <Link
                        href={`/products/${p.id}`}
                        className="font-medium text-gray-900 dark:text-neutral-100 hover:underline"
                      >
                        {p.name}
                      </Link>
                    </td>
                    <td className="px-5 py-3 text-gray-600 dark:text-neutral-400 font-mono text-[12px]">
                      {p.sku || "—"}
                    </td>
                    <td className="px-5 py-3 text-right font-mono font-semibold text-amber-700 dark:text-amber-300">
                      {Number(p.inventory_quantity ?? p.inventory ?? 0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}