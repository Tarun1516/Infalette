"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { Plus, FileText, ExternalLink, Home as HomeIcon } from "lucide-react";
import { adminApi } from "@/lib/api";

interface PageRow {
  id: string;
  title: string;
  slug: string;
  path?: string | null;
  status: string;
  is_homepage: boolean;
  updated_at?: string | null;
  store_id?: string | null;
}

export default function PagesListPage() {
  const [pages, setPages] = useState<PageRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [stores, setStores] = useState<any[]>([]);

  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const [path, setPath] = useState("/");
  const [storeId, setStoreId] = useState("");
  const [blocksJson, setBlocksJson] = useState("[]");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const fetchPages = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminApi.getPages();
      setPages(Array.isArray(res) ? res : []);
    } catch (e: any) {
      setError(e.message || "Failed to load pages");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPages();
    adminApi
      .getStores()
      .then((s) => setStores(Array.isArray(s) ? s : []))
      .catch(() => undefined);
  }, []);

  const slugify = (s: string) =>
    s
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "");

  const handleTitleChange = (v: string) => {
    setTitle(v);
    if (!slug || slug === slugify(title)) {
      setSlug(slugify(v));
    }
  };

  const validateBlocksJson = (s: string): string | null => {
    try {
      const parsed = JSON.parse(s);
      if (!Array.isArray(parsed)) return "blocks_json must be a JSON array";
      return null;
    } catch {
      return "Invalid JSON";
    }
  };

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    setCreateError(null);
    const jerr = validateBlocksJson(blocksJson);
    if (jerr) {
      setCreateError(jerr);
      return;
    }
    setCreating(true);
    try {
      const payload: any = {
        title: title.trim(),
        slug: slug.trim(),
        path: path.trim() || `/${slug.trim()}`,
        blocks_json: JSON.parse(blocksJson),
      };
      if (storeId) payload.store_id = storeId;
      const created = await adminApi.createPage(payload);
      setShowModal(false);
      setTitle("");
      setSlug("");
      setPath("/");
      setBlocksJson("[]");
      setStoreId("");
      if (created?.id) {
        window.location.href = `/pages/${created.id}`;
      } else {
        fetchPages();
      }
    } catch (e: any) {
      setCreateError(e.message || "Failed to create page");
    } finally {
      setCreating(false);
    }
  };

  const statusBadge = (s: string) => {
    const base = "inline-flex px-2 py-0.5 rounded-full text-xs font-medium";
    if (s === "published") return `${base} bg-green-100 text-green-700`;
    if (s === "archived") return `${base} bg-gray-200 text-gray-600`;
    return `${base} bg-amber-100 text-amber-700`;
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <FileText className="h-6 w-6" /> Pages
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Build block-based pages for your storefront.
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" /> Create new page
        </button>
      </div>

      <div className="bg-white rounded-2xl shadow-sm border overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-gray-500">Loading pages…</div>
        ) : error ? (
          <div className="p-8 text-center">
            <p className="text-red-600 text-sm">{error}</p>
            <button
              onClick={fetchPages}
              className="mt-3 text-sm bg-gray-900 text-white px-4 py-2 rounded"
            >
              Retry
            </button>
          </div>
        ) : pages.length === 0 ? (
          <div className="p-12 text-center">
            <p className="text-gray-500">No pages yet</p>
            <p className="text-xs text-gray-400 mt-1">
              Click &quot;Create new page&quot; to add your first block-based page.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left p-3 font-medium text-gray-600">Title</th>
                  <th className="text-left p-3 font-medium text-gray-600">Slug</th>
                  <th className="text-left p-3 font-medium text-gray-600">Path</th>
                  <th className="text-left p-3 font-medium text-gray-600">Status</th>
                  <th className="text-left p-3 font-medium text-gray-600">Home?</th>
                  <th className="text-left p-3 font-medium text-gray-600">Updated</th>
                  <th className="text-right p-3 font-medium text-gray-600">Action</th>
                </tr>
              </thead>
              <tbody>
                {pages.map((p) => (
                  <tr key={p.id} className="border-b hover:bg-gray-50">
                    <td className="p-3 font-medium">{p.title}</td>
                    <td className="p-3 text-gray-600 font-mono text-xs">{p.slug}</td>
                    <td className="p-3 text-gray-600 font-mono text-xs">
                      {p.path || `/${p.slug}`}
                    </td>
                    <td className="p-3">
                      <span className={statusBadge(p.status)}>{p.status}</span>
                    </td>
                    <td className="p-3">
                      {p.is_homepage ? (
                        <span className="inline-flex items-center gap-1 text-blue-600">
                          <HomeIcon className="h-3.5 w-3.5" /> yes
                        </span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="p-3 text-xs text-gray-500">
                      {p.updated_at ? new Date(p.updated_at).toLocaleString() : "—"}
                    </td>
                    <td className="p-3 text-right">
                      <Link
                        href={`/pages/${p.id}`}
                        className="inline-flex items-center gap-1 text-blue-600 hover:underline text-xs font-medium"
                      >
                        <ExternalLink className="h-3.5 w-3.5" /> Edit
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showModal && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-white rounded-2xl shadow-xl border w-full max-w-2xl my-8">
            <div className="p-5 border-b">
              <h2 className="text-lg font-semibold">Create new page</h2>
              <p className="text-xs text-gray-500 mt-1">
                Configure page metadata and an initial empty blocks list.
              </p>
            </div>
            <form onSubmit={handleCreate} className="p-5 space-y-4">
              <div>
                <label className="text-xs font-medium text-gray-700 block mb-1">Title</label>
                <input
                  type="text"
                  required
                  value={title}
                  onChange={(e) => handleTitleChange(e.target.value)}
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-medium text-gray-700 block mb-1">Slug</label>
                  <input
                    type="text"
                    required
                    value={slug}
                    onChange={(e) => setSlug(slugify(e.target.value))}
                    className="w-full border rounded-lg px-3 py-2 text-sm font-mono"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-700 block mb-1">Path</label>
                  <input
                    type="text"
                    value={path}
                    onChange={(e) => setPath(e.target.value)}
                    placeholder="/about-us"
                    className="w-full border rounded-lg px-3 py-2 text-sm font-mono"
                  />
                </div>
              </div>
              {stores.length > 0 && (
                <div>
                  <label className="text-xs font-medium text-gray-700 block mb-1">Store</label>
                  <select
                    value={storeId}
                    onChange={(e) => setStoreId(e.target.value)}
                    className="w-full border rounded-lg px-3 py-2 text-sm bg-white"
                  >
                    <option value="">— Default —</option>
                    {stores.map((s: any) => (
                      <option key={s.id} value={s.id}>
                        {s.name || s.slug || s.id}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <div>
                <label className="text-xs font-medium text-gray-700 block mb-1">
                  Initial blocks_json (array)
                </label>
                <textarea
                  value={blocksJson}
                  onChange={(e) => setBlocksJson(e.target.value)}
                  rows={5}
                  className="w-full border rounded-lg px-3 py-2 text-xs font-mono"
                />
                <p className="text-xs text-gray-400 mt-1">
                  You can paste a JSON array. After creation, use the editor to add blocks visually.
                </p>
              </div>
              {createError && (
                <p className="text-xs text-red-600 bg-red-50 border border-red-100 rounded p-2">
                  {createError}
                </p>
              )}
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowModal(false);
                    setCreateError(null);
                  }}
                  className="px-4 py-2 border rounded-lg text-sm hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
                >
                  {creating ? "Creating…" : "Create page"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
