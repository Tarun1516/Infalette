"use client";

import { toast } from "@/components/toaster";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { adminApi } from "@/lib/api";

interface VariantDraft {
  sku: string;
  price_cents: string;
  sale_price_cents: string;
  inventory_quantity: string;
}

const emptyDraft: VariantDraft = { sku: "", price_cents: "", sale_price_cents: "", inventory_quantity: "0" };

export default function ProductDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id;

  const [product, setProduct] = useState<any>(null);
  const [variants, setVariants] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingProduct, setSavingProduct] = useState(false);

  const [summary, setSummary] = useState({
    name: "",
    sku: "",
    price_cents: "",
    sale_price_cents: "",
    inventory_quantity: "",
    status: "active",
  });
  const [newVariant, setNewVariant] = useState<VariantDraft>(emptyDraft);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<VariantDraft>(emptyDraft);
  const [variantBusy, setVariantBusy] = useState(false);

  const fetchAll = async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [p, vs] = await Promise.all([adminApi.getProduct(id), adminApi.getVariants(id)]);
      setProduct(p);
      setSummary({
        name: p.name || "",
        sku: p.sku || "",
        price_cents: String(p.price_cents ?? ""),
        sale_price_cents: p.sale_price_cents != null ? String(p.sale_price_cents) : "",
        inventory_quantity: String(p.inventory_quantity ?? p.inventory ?? 0),
        status: p.status || "active",
      });
      setVariants(Array.isArray(vs) ? vs : []);
    } catch (e: any) {
      setError(e.message || "Failed to load product");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const handleSaveSummary = async () => {
    if (!id) return;
    setSavingProduct(true);
    try {
      const salePriceCents = summary.sale_price_cents
        ? parseInt(summary.sale_price_cents, 10)
        : null;
      const priceCents = parseInt(summary.price_cents, 10) || 0;
      // A sale price is only meaningful when it's strictly less than the
      // list price. We send null otherwise so the storefront doesn't show
      // a crossed-out price equal to the current price.
      const finalSale = salePriceCents != null && salePriceCents < priceCents ? salePriceCents : null;
      await adminApi.updateProduct(id, {
        name: summary.name,
        slug: product.slug,
        sku: summary.sku,
        price_cents: priceCents,
        sale_price_cents: finalSale,
        inventory: parseInt(summary.inventory_quantity, 10) || 0,
        inventory_quantity: parseInt(summary.inventory_quantity, 10) || 0,
        status: summary.status,
      });
      await fetchAll();
    } catch (e: any) {
      toast({ kind: "error", title: "Something went wrong", description: e.message || "Failed to save product" });
    } finally {
      setSavingProduct(false);
    }
  };

  const handleAddVariant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;
    setVariantBusy(true);
    try {
      await adminApi.createVariant(id, {
        sku: newVariant.sku || undefined,
        price_cents: parseInt(newVariant.price_cents, 10) || 0,
        sale_price_cents: newVariant.sale_price_cents ? parseInt(newVariant.sale_price_cents, 10) : null,
        inventory_quantity: parseInt(newVariant.inventory_quantity, 10) || 0,
      });
      setNewVariant(emptyDraft);
      await fetchAll();
    } catch (e: any) {
      toast({ kind: "error", title: "Something went wrong", description: e.message || "Failed to add variant" });
    } finally {
      setVariantBusy(false);
    }
  };

  const startEdit = (v: any) => {
    setEditingId(v.id);
    setEditDraft({
      sku: v.sku || "",
      price_cents: String(v.price_cents ?? ""),
      sale_price_cents: v.sale_price_cents != null ? String(v.sale_price_cents) : "",
      inventory_quantity: String(v.inventory ?? v.inventory_quantity ?? 0),
    });
  };

  const handleUpdateVariant = async () => {
    if (!id || !editingId) return;
    setVariantBusy(true);
    try {
      await adminApi.updateVariant(id, editingId, {
        sku: editDraft.sku,
        price_cents: parseInt(editDraft.price_cents, 10) || 0,
        sale_price_cents: editDraft.sale_price_cents ? parseInt(editDraft.sale_price_cents, 10) : null,
        inventory_quantity: parseInt(editDraft.inventory_quantity, 10) || 0,
      });
      setEditingId(null);
      await fetchAll();
    } catch (e: any) {
      toast({ kind: "error", title: "Something went wrong", description: e.message || "Failed to update variant" });
    } finally {
      setVariantBusy(false);
    }
  };

  const handleDeleteVariant = async (variantId: string) => {
    if (!id || !confirm("Delete this variant?")) return;
    try {
      await adminApi.deleteVariant(id, variantId);
      await fetchAll();
    } catch (e: any) {
      toast({ kind: "error", title: "Something went wrong", description: e.message || "Failed to delete variant" });
    }
  };

  const cellInput = "w-full border rounded px-2 py-1 text-sm";

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow border p-12 text-center text-gray-500">Loading product…</div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow border p-8 text-center">
        <p className="text-red-600 text-sm">{error}</p>
        <div className="mt-3 flex justify-center gap-2">
          <button onClick={fetchAll} className="text-sm bg-gray-900 text-white px-4 py-2 rounded">
            Retry
          </button>
          <Link href="/products" className="text-sm border px-4 py-2 rounded">
            Back to products
          </Link>
        </div>
      </div>
    );
  }

  if (!product) {
    return (
      <div className="bg-white rounded-lg shadow border p-12 text-center">
        <p className="text-gray-500">Product not found</p>
        <Link href="/products" className="text-sm text-blue-600 hover:underline mt-2 inline-block">
          ← Back to products
        </Link>
      </div>
    );
  }

  return (
    <div>
      <Link href="/products" className="text-sm text-blue-600 hover:underline mb-4 inline-block">
        ← Back to products
      </Link>

      {/* Product summary */}
      <div className="bg-white rounded-lg shadow border p-6 mb-6">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-4">
          <h1 className="text-xl font-bold">{product.name}</h1>
          <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
            {product.status || "active"}
          </span>
        </div>
        <div className="grid md:grid-cols-2 gap-4 mb-4">
          <label className="block">
            <span className="block text-xs font-medium text-gray-600 mb-1">Name</span>
            <input
              value={summary.name}
              onChange={(e) => setSummary((s) => ({ ...s, name: e.target.value }))}
              className={`${cellInput} w-full`}
            />
          </label>
          <label className="block">
            <span className="block text-xs font-medium text-gray-600 mb-1">SKU</span>
            <input
              value={summary.sku}
              onChange={(e) => setSummary((s) => ({ ...s, sku: e.target.value }))}
              className={`${cellInput} w-full`}
            />
          </label>
        </div>
        <div className="grid md:grid-cols-4 gap-4">
          <label className="block">
            <span className="block text-xs font-medium text-gray-600 mb-1">
              Original price (₹{((parseInt(summary.price_cents, 10) || 0) / 100).toFixed(2)})
            </span>
            <input
              type="number"
              value={summary.price_cents}
              onChange={(e) => setSummary((s) => ({ ...s, price_cents: e.target.value }))}
              className={`${cellInput} w-full`}
            />
          </label>
          <label className="block">
            <span className="block text-xs font-medium text-gray-600 mb-1">
              Sale price{" "}
              {summary.sale_price_cents &&
              parseInt(summary.sale_price_cents, 10) < (parseInt(summary.price_cents, 10) || 0) ? (
                <span className="text-green-600">
                  (₹{(parseInt(summary.sale_price_cents, 10) / 100).toFixed(2)} on sale)
                </span>
              ) : (
                <span className="text-gray-400">(leave empty for no discount)</span>
              )}
            </span>
            <input
              type="number"
              value={summary.sale_price_cents}
              onChange={(e) => setSummary((s) => ({ ...s, sale_price_cents: e.target.value }))}
              placeholder="0"
              className={`${cellInput} w-full`}
            />
          </label>
          <label className="block">
            <span className="block text-xs font-medium text-gray-600 mb-1">Inventory quantity</span>
            <input
              type="number"
              value={summary.inventory_quantity}
              onChange={(e) => setSummary((s) => ({ ...s, inventory_quantity: e.target.value }))}
              className={`${cellInput} w-full`}
            />
          </label>
          <label className="block">
            <span className="block text-xs font-medium text-gray-600 mb-1">Status</span>
            <select
              value={summary.status}
              onChange={(e) => setSummary((s) => ({ ...s, status: e.target.value }))}
              className={`${cellInput} w-full bg-white`}
            >
              <option value="active">Active</option>
              <option value="draft">Draft</option>
              <option value="archived">Archived</option>
            </select>
          </label>
        </div>
        <div className="mt-4">
          <button
            onClick={handleSaveSummary}
            disabled={savingProduct}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {savingProduct ? "Saving…" : "Save"}
          </button>
        </div>
      </div>

      {/* Variants */}
      <h2 className="text-lg font-bold mb-3">Variants</h2>
      <div className="bg-white rounded-lg shadow border overflow-hidden mb-6">
        {variants.length === 0 ? (
          <div className="p-8 text-center text-gray-500 text-sm">
            No variants yet. Add one below — leave SKU blank to auto-generate.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left p-3 font-medium text-gray-600">SKU</th>
                  <th className="text-left p-3 font-medium text-gray-600">Price</th>
                  <th className="text-left p-3 font-medium text-gray-600">Sale Price</th>
                  <th className="text-left p-3 font-medium text-gray-600">Inventory</th>
                  <th className="text-right p-3 font-medium text-gray-600">Actions</th>
                </tr>
              </thead>
              <tbody>
                {variants.map((v) => (
                  <tr key={v.id} className="border-b hover:bg-gray-50">
                    {editingId === v.id ? (
                      <>
                        <td className="p-3">
                          <input value={editDraft.sku} onChange={(e) => setEditDraft((d) => ({ ...d, sku: e.target.value }))} className={cellInput} />
                        </td>
                        <td className="p-3">
                          <input type="number" value={editDraft.price_cents} onChange={(e) => setEditDraft((d) => ({ ...d, price_cents: e.target.value }))} className={cellInput} />
                        </td>
                        <td className="p-3">
                          <input type="number" value={editDraft.sale_price_cents} onChange={(e) => setEditDraft((d) => ({ ...d, sale_price_cents: e.target.value }))} className={cellInput} />
                        </td>
                        <td className="p-3">
                          <input type="number" value={editDraft.inventory_quantity} onChange={(e) => setEditDraft((d) => ({ ...d, inventory_quantity: e.target.value }))} className={cellInput} />
                        </td>
                        <td className="p-3 text-right">
                          <div className="flex justify-end gap-2">
                            <button onClick={handleUpdateVariant} disabled={variantBusy} className="text-green-600 hover:underline text-xs disabled:opacity-50">
                              Save
                            </button>
                            <button onClick={() => setEditingId(null)} className="text-gray-500 hover:underline text-xs">
                              Cancel
                            </button>
                          </div>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="p-3 font-medium">{v.sku}</td>
                        <td className="p-3">
                          ₹{((v.price_cents ?? 0) / 100).toFixed(2)}
                        </td>
                        <td className="p-3">
                          {v.sale_price_cents != null ? `₹${(v.sale_price_cents / 100).toFixed(2)}` : "—"}
                        </td>
                        <td className="p-3">
                          <span className={(v.inventory ?? 0) === 0 ? "text-red-600" : ""}>
                            {v.inventory ?? v.inventory_quantity ?? 0}
                          </span>
                        </td>
                        <td className="p-3 text-right">
                          <div className="flex justify-end gap-2">
                            <button onClick={() => startEdit(v)} className="text-blue-600 hover:underline text-xs">
                              Edit
                            </button>
                            <button onClick={() => handleDeleteVariant(v.id)} className="text-red-600 hover:underline text-xs">
                              Delete
                            </button>
                          </div>
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add variant */}
      <form onSubmit={handleAddVariant} className="bg-white rounded-lg shadow border p-4">
        <h3 className="text-sm font-bold mb-3">Add variant</h3>
        <div className="grid sm:grid-cols-5 gap-2 items-end">
          <label className="block">
            <span className="block text-xs font-medium text-gray-600 mb-1">SKU (optional)</span>
            <input value={newVariant.sku} onChange={(e) => setNewVariant((d) => ({ ...d, sku: e.target.value }))} placeholder="auto" className={cellInput} />
          </label>
          <label className="block">
            <span className="block text-xs font-medium text-gray-600 mb-1">Price (cents)</span>
            <input required type="number" value={newVariant.price_cents} onChange={(e) => setNewVariant((d) => ({ ...d, price_cents: e.target.value }))} className={cellInput} />
          </label>
          <label className="block">
            <span className="block text-xs font-medium text-gray-600 mb-1">Sale price (cents)</span>
            <input type="number" value={newVariant.sale_price_cents} onChange={(e) => setNewVariant((d) => ({ ...d, sale_price_cents: e.target.value }))} className={cellInput} />
          </label>
          <label className="block">
            <span className="block text-xs font-medium text-gray-600 mb-1">Inventory</span>
            <input type="number" value={newVariant.inventory_quantity} onChange={(e) => setNewVariant((d) => ({ ...d, inventory_quantity: e.target.value }))} className={cellInput} />
          </label>
          <button type="submit" disabled={variantBusy} className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 whitespace-nowrap">
            {variantBusy ? "Adding…" : "Add variant"}
          </button>
        </div>
      </form>
    </div>
  );
}
