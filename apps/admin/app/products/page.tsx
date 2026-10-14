"use client";

import { toast } from "@/components/toaster";
import { useEffect, useState } from "react";
import Link from "next/link";
import { adminApi } from "@/lib/api";

type Product = {
  id: string;
  name: string;
  slug?: string;
  sku?: string;
  price_cents?: number;
  sale_price_cents?: number | null;
  inventory_quantity?: number;
  inventory?: number;
  status?: string;
  image_url?: string | null;
  images?: string[];
  description?: string;
};

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<string | null>(null);
  const [view, setView] = useState<"grid" | "list">("grid");
  const perPage = 20;

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setImportResult(null);
    try {
      const res = await adminApi.importProducts(file);
      const errs = res.errors?.length ? ` — ${res.errors.length} issue(s): ${res.errors.slice(0, 3).join("; ")}${res.errors.length > 3 ? "…" : ""}` : "";
      setImportResult(`Imported: ${res.created} created, ${res.updated} updated, ${res.skipped} skipped${errs}`);
      fetchProducts(1, search);
    } catch (err: any) {
      setImportResult(`Import failed: ${err.message || "unknown error"}`);
    } finally {
      setImporting(false);
      e.target.value = "";
    }
  };

  const fetchProducts = async (p = page, q = search) => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = { page: String(p), per_page: String(perPage) };
      if (q) params.search = q;
      const res: any = await adminApi.getProducts(params);
      const list = Array.isArray(res) ? res : res.data || res.items || [];
      setProducts(list);
      setTotal(res.total ?? list.length);
    } catch (e: any) {
      setError(e.message || "Failed to load products");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProducts(1, search);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchProducts(1, search);
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this product?")) return;
    try {
      await adminApi.deleteProduct(id);
      fetchProducts(page, search);
    } catch (e: any) {
      toast({ kind: "error", title: "Something went wrong", description: e.message || "Failed to delete" });
    }
  };

  const imgSrc = (p: Product) => p.image_url || p.images?.[0];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <p className="text-[12px] uppercase tracking-[0.18em] text-gray-500 dark:text-neutral-500">
            Catalog
          </p>
          <h1 className="mt-2 text-[36px] sm:text-[44px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
            Products
          </h1>
          <p className="mt-1 text-[13px] text-gray-500 dark:text-neutral-500">
            {total} product{total === 1 ? "" : "s"} total
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="inline-flex h-10 px-4 items-center justify-center rounded-full border border-gray-200 dark:border-neutral-800 text-[13px] font-medium text-gray-900 dark:text-neutral-100 hover:bg-gray-50 dark:hover:bg-neutral-900 cursor-pointer">
            {importing ? "Importing…" : "Import CSV"}
            <input type="file" accept=".csv,text/csv" className="hidden" onChange={handleImport} disabled={importing} />
          </label>
          <Link
            href="/products/create"
            className="inline-flex h-10 px-5 items-center justify-center rounded-full bg-blue-600 text-white text-[14px] font-medium hover:bg-blue-700 transition-colors"
          >
            New product
          </Link>
        </div>
      </div>

      {importResult && (
        <div className="rounded-xl border border-gray-100 dark:border-neutral-800 bg-gray-50 dark:bg-neutral-900 px-4 py-3 text-[13px] text-gray-700 dark:text-neutral-300">
          {importResult}
        </div>
      )}

      <div className="flex flex-col sm:flex-row sm:items-center gap-3 justify-between">
        <form onSubmit={handleSearch} className="flex items-center gap-2 flex-1 max-w-md">
          <div className="relative flex-1">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
              <circle cx="11" cy="11" r="7" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by name or SKU…"
              className="w-full h-10 rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 pl-9 pr-3 text-[13px]"
            />
          </div>
          {search && (
            <button type="button" onClick={() => { setSearch(""); setPage(1); fetchProducts(1, ""); }} className="text-[12px] text-gray-500 hover:underline">
              Clear
            </button>
          )}
        </form>
        <div className="inline-flex items-center rounded-full border border-gray-200 dark:border-neutral-800 p-0.5">
          <button
            onClick={() => setView("grid")}
            className={`h-8 px-3 rounded-full text-[12px] font-medium ${view === "grid" ? "bg-gray-900 dark:bg-white text-white dark:text-black" : "text-gray-600 dark:text-neutral-400"}`}
          >
            Grid
          </button>
          <button
            onClick={() => setView("list")}
            className={`h-8 px-3 rounded-full text-[12px] font-medium ${view === "list" ? "bg-gray-900 dark:bg-white text-white dark:text-black" : "text-gray-600 dark:text-neutral-400"}`}
          >
            List
          </button>
        </div>
      </div>

      {error ? (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-6 dark:bg-red-900/10 dark:border-red-900">
          <p className="text-red-700 text-[14px] dark:text-red-300">{error}</p>
          <button onClick={() => fetchProducts(page, search)} className="mt-3 text-[13px] bg-gray-900 dark:bg-white text-white dark:text-black px-4 py-2 rounded-full">
            Retry
          </button>
        </div>
      ) : loading ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="animate-pulse rounded-2xl bg-gray-100 dark:bg-neutral-900 aspect-square" />
          ))}
        </div>
      ) : products.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-gray-300 dark:border-neutral-800 py-20 px-6 text-center">
          <p className="text-gray-500 dark:text-neutral-400">No products found</p>
          <Link href="/products/create" className="mt-3 inline-block text-[13px] text-blue-600 hover:underline">
            Create your first product →
          </Link>
        </div>
      ) : view === "grid" ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
          {products.map((p) => {
            const price = (p.sale_price_cents ?? p.price_cents ?? 0) / 100;
            const stock = p.inventory_quantity ?? p.inventory ?? 0;
            const stockClass =
              stock === 0 ? "text-red-600" : stock < 10 ? "text-amber-600" : "text-gray-500 dark:text-neutral-500";
            return (
              <div
                key={p.id}
                className="group rounded-2xl bg-white dark:bg-neutral-950 border border-gray-100 dark:border-neutral-900 overflow-hidden hover:shadow-[0_8px_30px_rgba(0,0,0,0.08)] dark:hover:shadow-[0_8px_30px_rgba(255,255,255,0.04)] transition-all"
              >
                <Link href={`/products/${p.id}`} className="block">
                  <div className="aspect-square bg-gray-100 dark:bg-neutral-900 overflow-hidden">
                    {imgSrc(p) ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={imgSrc(p)!} alt={p.name} className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-[1.03]" />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-xs text-gray-400">No image</div>
                    )}
                  </div>
                </Link>
                <div className="p-4 space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <Link href={`/products/${p.id}`} className="text-[14px] font-medium text-gray-900 dark:text-neutral-100 line-clamp-1 hover:underline">
                      {p.name}
                    </Link>
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium uppercase tracking-wider ${
                        p.status === "active"
                          ? "bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-300"
                          : "bg-gray-100 text-gray-600 dark:bg-neutral-900 dark:text-neutral-400"
                      }`}
                    >
                      {p.status || "active"}
                    </span>
                  </div>
                  <p className="text-[12px] text-gray-500 dark:text-neutral-500 line-clamp-1">{p.sku || "—"}</p>
                  <div className="flex items-baseline justify-between">
                    <div className="flex flex-col">
                      <span className="text-[15px] font-semibold text-gray-900 dark:text-neutral-100">
                        ₹{price.toFixed(2)}
                      </span>
                      {p.sale_price_cents != null && p.price_cents && p.sale_price_cents < p.price_cents && (
                        <span className="text-[12px] text-gray-400 dark:text-neutral-500 line-through">
                          ₹{((p.price_cents || 0) / 100).toFixed(2)}
                        </span>
                      )}
                    </div>
                    <span className={`text-[12px] ${stockClass}`}>
                      {stock} in stock
                    </span>
                  </div>
                  <div className="pt-2 flex items-center justify-end gap-2">
                    <button onClick={() => handleDelete(p.id)} className="text-[12px] text-gray-500 hover:text-red-600 hover:underline">
                      Delete
                    </button>
                    <Link href={`/products/${p.id}`} className="inline-flex h-7 px-3 items-center justify-center rounded-full border border-gray-200 dark:border-neutral-800 text-[12px] hover:bg-gray-50 dark:hover:bg-neutral-900">
                      Edit
                    </Link>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="rounded-2xl bg-white dark:bg-neutral-950 border border-gray-100 dark:border-neutral-900 overflow-hidden">
          <table className="w-full text-[13px]">
            <thead className="bg-gray-50 dark:bg-neutral-900 text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500">
              <tr>
                <th className="text-left px-4 py-3 font-medium">Product</th>
                <th className="text-left px-4 py-3 font-medium">SKU</th>
                <th className="text-left px-4 py-3 font-medium">Price</th>
                <th className="text-left px-4 py-3 font-medium">Stock</th>
                <th className="text-left px-4 py-3 font-medium">Status</th>
                <th className="text-right px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {products.map((p) => {
                const price = (p.sale_price_cents ?? p.price_cents ?? 0) / 100;
                const stock = p.inventory_quantity ?? p.inventory ?? 0;
                const stockClass = stock === 0 ? "text-red-600" : stock < 10 ? "text-amber-600" : "text-gray-700 dark:text-neutral-300";
                const onSale = p.sale_price_cents != null && p.price_cents && p.sale_price_cents < p.price_cents;
                return (
                  <tr key={p.id} className="border-t border-gray-100 dark:border-neutral-900">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-gray-100 dark:bg-neutral-900 overflow-hidden flex-shrink-0">
                          {imgSrc(p) ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={imgSrc(p)!} alt="" className="w-full h-full object-cover" />
                          ) : null}
                        </div>
                        <Link href={`/products/${p.id}`} className="font-medium text-gray-900 dark:text-neutral-100 hover:underline">
                          {p.name}
                        </Link>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-neutral-400">{p.sku || "—"}</td>
                    <td className="px-4 py-3">
                      {onSale ? (
                        <div className="flex flex-col leading-tight">
                          <span className="font-medium text-gray-900 dark:text-neutral-100">
                            ₹{price.toFixed(2)}
                          </span>
                          <span className="text-[11px] text-gray-400 dark:text-neutral-500 line-through">
                            ₹{((p.price_cents || 0) / 100).toFixed(2)}
                          </span>
                        </div>
                      ) : (
                        <span className="font-medium text-gray-900 dark:text-neutral-100">₹{price.toFixed(2)}</span>
                      )}
                    </td>
                    <td className={`px-4 py-3 ${stockClass}`}>{stock}</td>
                    <td className="px-4 py-3">
                      <span className="inline-flex px-2 py-0.5 rounded-full text-[11px] font-medium bg-gray-100 dark:bg-neutral-900 text-gray-700 dark:text-neutral-300">
                        {p.status || "active"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link href={`/products/${p.id}`} className="text-[12px] text-blue-600 dark:text-blue-400 hover:underline mr-3">Edit</Link>
                      <button onClick={() => handleDelete(p.id)} className="text-[12px] text-gray-500 hover:text-red-600 hover:underline">Delete</button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {total > perPage && (
        <div className="flex items-center justify-between text-[13px] text-gray-500 dark:text-neutral-500">
          <span>Page {page} of {Math.ceil(total / perPage)}</span>
          <div className="flex gap-2">
            <button
              disabled={page <= 1}
              onClick={() => { const np = page - 1; setPage(np); fetchProducts(np, search); }}
              className="h-9 px-4 inline-flex items-center justify-center rounded-full border border-gray-200 dark:border-neutral-800 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-neutral-900"
            >
              Previous
            </button>
            <button
              disabled={page >= Math.ceil(total / perPage)}
              onClick={() => { const np = page + 1; setPage(np); fetchProducts(np, search); }}
              className="h-9 px-4 inline-flex items-center justify-center rounded-full border border-gray-200 dark:border-neutral-800 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-neutral-900"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}