"use client";

import { toast } from "@/components/toaster";

import { useState, useEffect } from "react";
import { adminApi } from "@/lib/api";

export default function CreateProductPage() {
  const [formData, setFormData] = useState({
    name: "",
    slug: "",
    description: "",
    sku: "",
    price_cents: 250000,
    sale_price_cents: "" as any,
    inventory_quantity: 100,
    inventory_track: true,
    inventory_policy: "deny",
    category_id: "",
    collection_id: "",
    tax_class: "standard",
    ingredients: "",
    safety_info: "",
    age_suitability: "all",
    pregnancy_stage: "",
    meta_title: "",
    meta_description: "",
    image_url: "",
    gallery_urls: "" as any,
  });
  const [categories, setCategories] = useState<any[]>([]);
  const [collections, setCollections] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    adminApi.getCategories().then((r: any) => setCategories(Array.isArray(r) ? r : r.data || [])).catch(() => {});
    adminApi.getCollections().then((r: any) => setCollections(Array.isArray(r) ? r : r.data || [])).catch(() => {});
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target as any;
    setFormData((prev) => ({ ...prev, [name]: type === "checkbox" ? (e.target as any).checked : value }));
  };

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      // Try presigned S3 upload, fallback to image_url as data URL preview
      const form = new FormData();
      form.append("file", file);
      const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
      const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      const res = await fetch(`${base.replace(/\/$/, "")}/media/upload`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      });
      if (res.ok) {
        const data = await res.json();
        const url = data.url || data.location || data.key ? `${data.url || data.key}` : "";
        if (url) {
          setFormData((p) => ({ ...p, image_url: url }));
        } else {
          // fallback: use location header
          setFormData((p) => ({ ...p, image_url: data.url || data.signed_url || "" }));
        }
      } else {
        // fallback: preview as object URL (not persisted, but lets user see)
        const preview = URL.createObjectURL(file);
        setFormData((p) => ({ ...p, image_url: preview }));
        toast({ kind: "error", title: "S3 upload failed, using preview. Configure S3_BUCKET." });
      }
    } catch (err) {
      toast({ kind: "error", title: "Upload failed" });
    } finally {
      setUploading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload: any = {
        name: formData.name,
        slug: formData.slug,
        description: formData.description,
        sku: formData.sku,
        price_cents: parseInt(String(formData.price_cents)),
        sale_price_cents: formData.sale_price_cents ? parseInt(String(formData.sale_price_cents)) : null,
        inventory_quantity: parseInt(String(formData.inventory_quantity)),
        inventory_track: !!formData.inventory_track,
        inventory_policy: formData.inventory_policy,
        inventory: parseInt(String(formData.inventory_quantity)),
        tax_class: formData.tax_class,
        ingredients: formData.ingredients || null,
        safety_info: formData.safety_info || null,
        age_suitability: formData.age_suitability || null,
        pregnancy_stage: formData.pregnancy_stage || null,
        meta_title: formData.meta_title || null,
        meta_description: formData.meta_description || null,
        image_url: formData.image_url || null,
        gallery_urls: formData.gallery_urls ? String(formData.gallery_urls).split(",").map((s) => s.trim()).filter(Boolean) : [],
        category_id: formData.category_id || null,
        collection_id: formData.collection_id || null,
      };
      await adminApi.createProduct(payload);
      window.location.href = "/products";
    } catch (error: any) {
      toast({ kind: "error", title: "Something went wrong", description: error.message || "Failed to create product" });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold mb-2">Create Product</h1>
      <p className="text-xs text-gray-500 mb-6">All money in minor units (cents/paise). Images via S3 presigned upload. Tax/shipping calculated at checkout per tax_class.</p>
      <form onSubmit={handleSubmit} className="space-y-4 bg-white p-6 rounded-xl shadow border">
        <div className="grid md:grid-cols-2 gap-4">
          <input type="text" name="name" placeholder="Product Name *" value={formData.name} onChange={handleChange} className="w-full p-3 border rounded-lg text-sm" required />
          <input type="text" name="slug" placeholder="slug-like-this *" value={formData.slug} onChange={handleChange} className="w-full p-3 border rounded-lg text-sm" required />
        </div>
        <textarea name="description" placeholder="Description" value={formData.description} onChange={handleChange} className="w-full p-3 border rounded-lg text-sm" rows={3} />
        <div className="grid md:grid-cols-2 gap-4">
          <input type="text" name="sku" placeholder="SKU * (unique)" value={formData.sku} onChange={handleChange} className="w-full p-3 border rounded-lg text-sm" required />
          <select name="tax_class" value={formData.tax_class} onChange={handleChange} className="w-full p-3 border rounded-lg text-sm bg-white">
            <option value="standard">standard (18% GST)</option>
            <option value="reduced">reduced (5% GST)</option>
            <option value="zero">zero</option>
            <option value="exempt">exempt</option>
          </select>
        </div>
        <div className="grid md:grid-cols-3 gap-4">
          <input type="number" name="price_cents" placeholder="Price (cents) *" value={formData.price_cents} onChange={handleChange} className="w-full p-3 border rounded-lg text-sm" required />
          <input type="number" name="sale_price_cents" placeholder="Sale Price (cents)" value={formData.sale_price_cents} onChange={handleChange} className="w-full p-3 border rounded-lg text-sm" />
          <div className="flex gap-2">
            <input type="number" name="inventory_quantity" placeholder="Inventory" value={formData.inventory_quantity} onChange={handleChange} className="flex-1 p-3 border rounded-lg text-sm" />
            <label className="flex items-center gap-1 text-xs"><input type="checkbox" name="inventory_track" checked={!!formData.inventory_track} onChange={handleChange} /> Track</label>
          </div>
        </div>
        <div className="grid md:grid-cols-3 gap-4">
          <select name="inventory_policy" value={formData.inventory_policy} onChange={handleChange} className="w-full p-3 border rounded-lg text-sm bg-white">
            <option value="deny">deny (oversell blocked)</option>
            <option value="continue">continue (allow negative)</option>
          </select>
          <select name="category_id" value={formData.category_id} onChange={handleChange} className="w-full p-3 border rounded-lg text-sm bg-white">
            <option value="">No category</option>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <select name="collection_id" value={formData.collection_id} onChange={handleChange} className="w-full p-3 border rounded-lg text-sm bg-white">
            <option value="">No collection</option>
            {collections.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div className="grid md:grid-cols-2 gap-4">
          <select name="age_suitability" value={formData.age_suitability} onChange={handleChange} className="w-full p-3 border rounded-lg text-sm bg-white">
            <option value="all">all ages</option>
            <option value="newborn">newborn</option>
            <option value="infant">infant</option>
            <option value="toddler">toddler</option>
            <option value="child">child</option>
          </select>
          <input type="text" name="pregnancy_stage" placeholder="Pregnancy stage (preconception, pregnancy_..., postpartum)" value={formData.pregnancy_stage} onChange={handleChange} className="w-full p-3 border rounded-lg text-sm" />
        </div>
        <input type="text" name="ingredients" placeholder="Ingredients/materials (comma separated, required trust)" value={formData.ingredients} onChange={handleChange} className="w-full p-3 border rounded-lg text-sm" />
        <input type="text" name="safety_info" placeholder="Safety info / warnings / manufacturer" value={formData.safety_info} onChange={handleChange} className="w-full p-3 border rounded-lg text-sm" />
        <div className="grid md:grid-cols-2 gap-4">
          <input type="text" name="meta_title" placeholder="SEO meta title" value={formData.meta_title} onChange={handleChange} className="w-full p-3 border rounded-lg text-sm" />
          <input type="text" name="meta_description" placeholder="SEO meta description" value={formData.meta_description} onChange={handleChange} className="w-full p-3 border rounded-lg text-sm" />
        </div>
        <div className="border rounded-xl p-4 bg-gray-50">
          <label className="block text-xs font-medium mb-2">Product Image (S3)</label>
          <input type="file" accept="image/*" onChange={handleImageUpload} className="w-full text-sm" />
          {uploading && <p className="text-xs text-gray-500 mt-1">Uploading…</p>}
          <input type="text" name="image_url" placeholder="Or paste image_url (https://...)" value={formData.image_url} onChange={handleChange} className="w-full p-2 border rounded-lg text-sm mt-2" />
          {formData.image_url && <img src={formData.image_url} alt="preview" className="mt-2 w-24 h-24 object-cover rounded border" />}
          <input type="text" name="gallery_urls" placeholder="Gallery urls, comma separated" value={formData.gallery_urls} onChange={handleChange} className="w-full p-2 border rounded-lg text-sm mt-2" />
        </div>
        <button type="submit" disabled={saving || uploading} className="w-full bg-blue-600 text-white px-6 py-3 rounded-full font-medium disabled:opacity-50">
          {saving ? "Creating…" : "Create Product"}
        </button>
      </form>
    </div>
  );
}
