"use client";

import { useEffect, useState } from "react";
import { adminApi, adminApiExt } from "@/lib/api";
import { toast } from "@/components/toaster";

/**
 * SEO console.
 *
 * Three surfaces in one page so the team can manage every SEO touch
 * point from a single screen:
 *  1. Per-URL metadata (title, description, keywords, focus keyword,
 *     canonical URL, robots directives, structured data).
 *  2. URL redirects (old_path -> new_path, 301/302/308).
 *  3. Sitemap generator.
 */
export default function SeoPage() {
  const [seoPages, setSeoPages] = useState<any[]>([]);
  const [redirects, setRedirects] = useState<any[]>([]);
  const [pageForm, setPageForm] = useState({
    url_path: "",
    title: "",
    meta_description: "",
    meta_keywords: "",
    focus_keyword: "",
    canonical_url: "",
    robots_index: true,
    robots_follow: true,
  });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [redirectForm, setRedirectForm] = useState({ old_path: "", new_path: "", status_code: 301 });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function loadAll() {
    try {
      const [pages, dirs] = await Promise.all([
        adminApi.getSeoPages().catch(() => []),
        adminApiExt.getSeoRedirects().catch(() => []),
      ]);
      setSeoPages(Array.isArray(pages) ? pages : pages.items || []);
      setRedirects(Array.isArray(dirs) ? dirs : []);
    } catch (e: any) {
      setError(e.message);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  function resetPageForm() {
    setPageForm({
      url_path: "",
      title: "",
      meta_description: "",
      meta_keywords: "",
      focus_keyword: "",
      canonical_url: "",
      robots_index: true,
      robots_follow: true,
    });
    setEditingId(null);
  }

  async function saveSeoPage(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const payload: any = {
        ...pageForm,
        structured_data: {
          "@context": "https://schema.org",
          ...(pageForm.focus_keyword ? { "keywords": pageForm.focus_keyword } : {}),
        },
      };
      if (editingId) {
        await adminApi.updateSeoPage(editingId, payload);
        toast({ kind: "success", title: "SEO entry updated" });
      } else {
        await adminApi.createSeoPage(payload);
        toast({ kind: "success", title: "SEO entry created" });
      }
      resetPageForm();
      await loadAll();
    } catch (err: any) {
      setError(err.message);
      toast({ kind: "error", title: "Could not save SEO entry", description: err?.message });
    } finally {
      setBusy(false);
    }
  }

  function startEditPage(p: any) {
    setEditingId(p.id);
    setPageForm({
      url_path: p.url_path || "",
      title: p.title || "",
      meta_description: p.meta_description || "",
      meta_keywords: p.meta_keywords || "",
      focus_keyword: p.focus_keyword || "",
      canonical_url: p.canonical_url || "",
      robots_index: p.robots_index !== false,
      robots_follow: p.robots_follow !== false,
    });
  }

  async function removeSeoPage(id: string) {
    if (!confirm("Delete this SEO entry?")) return;
    try {
      await adminApi.deleteSeoPage(id);
      await loadAll();
      if (editingId === id) resetPageForm();
      toast({ kind: "success", title: "SEO entry deleted" });
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function addRedirect(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await adminApiExt.createSeoRedirect(redirectForm);
      setRedirectForm({ old_path: "", new_path: "", status_code: 301 });
      await loadAll();
      toast({ kind: "success", title: "Redirect added" });
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function removeRedirect(id: string) {
    try {
      await adminApiExt.deleteSeoRedirect(id);
      await loadAll();
    } catch (err: any) {
      setError(err.message);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <p className="text-[12px] uppercase tracking-[0.18em] text-gray-500 dark:text-neutral-500">
          Marketing
        </p>
        <h1 className="mt-2 text-[36px] sm:text-[44px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
          SEO
        </h1>
        <p className="mt-1 text-[13px] text-gray-500 dark:text-neutral-500">
          Manage meta tags, keywords, redirects and structured data for every URL.
        </p>
      </div>

      {error && (
        <div className="rounded-2xl border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-900/10 px-4 py-3 text-[13px] text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      {/* Per-URL metadata */}
      <section className="rounded-2xl bg-white dark:bg-neutral-950 border border-gray-100 dark:border-neutral-900 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 dark:border-neutral-900">
          <h2 className="text-[15px] font-semibold text-gray-900 dark:text-neutral-100">
            Page metadata
          </h2>
          <p className="text-[12px] text-gray-500 dark:text-neutral-500">
            Per-URL SEO overrides — keywords, focus keyword, canonical URL and robots directives.
          </p>
        </div>

        <form onSubmit={saveSeoPage} className="px-5 py-5 space-y-4 border-b border-gray-100 dark:border-neutral-900 bg-gray-50/50 dark:bg-neutral-950">
          <div className="grid md:grid-cols-2 gap-3">
            <label className="block">
              <span className="block text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500 mb-1">
                URL path *
              </span>
              <input
                required
                value={pageForm.url_path}
                onChange={(e) => setPageForm({ ...pageForm, url_path: e.target.value })}
                placeholder="/products/lotion"
                className="h-10 w-full rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 text-[13px] font-mono"
              />
            </label>
            <label className="block">
              <span className="block text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500 mb-1">
                Canonical URL
              </span>
              <input
                value={pageForm.canonical_url}
                onChange={(e) => setPageForm({ ...pageForm, canonical_url: e.target.value })}
                placeholder="https://store.infalette.com/products/lotion"
                className="h-10 w-full rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 text-[13px] font-mono"
              />
            </label>
          </div>
          <label className="block">
            <span className="block text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500 mb-1">
              Page title
            </span>
            <input
              value={pageForm.title}
              onChange={(e) => setPageForm({ ...pageForm, title: e.target.value })}
              placeholder="Organic Baby Lotion — Infalette"
              className="h-10 w-full rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 text-[13px]"
            />
          </label>
          <label className="block">
            <span className="block text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500 mb-1">
              Meta description
            </span>
            <textarea
              value={pageForm.meta_description}
              onChange={(e) => setPageForm({ ...pageForm, meta_description: e.target.value })}
              placeholder="A short summary of the page for search results."
              rows={2}
              className="w-full rounded-2xl border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 py-3 text-[13px] resize-none"
            />
          </label>
          <div className="grid md:grid-cols-2 gap-3">
            <label className="block">
              <span className="block text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500 mb-1">
                Focus keyword
              </span>
              <input
                value={pageForm.focus_keyword}
                onChange={(e) => setPageForm({ ...pageForm, focus_keyword: e.target.value })}
                placeholder="organic baby lotion"
                className="h-10 w-full rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 text-[13px]"
              />
            </label>
            <label className="block">
              <span className="block text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500 mb-1">
                Keywords / tags
              </span>
              <input
                value={pageForm.meta_keywords}
                onChange={(e) => setPageForm({ ...pageForm, meta_keywords: e.target.value })}
                placeholder="lotion, baby, organic, sensitive skin"
                className="h-10 w-full rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 text-[13px]"
              />
            </label>
          </div>
          <div className="flex items-center gap-6 text-[13px]">
            <label className="inline-flex items-center gap-2">
              <input
                type="checkbox"
                checked={pageForm.robots_index}
                onChange={(e) => setPageForm({ ...pageForm, robots_index: e.target.checked })}
                className="h-4 w-4 rounded border-gray-300 text-gray-900 focus:ring-gray-900"
              />
              <span className="text-gray-700 dark:text-neutral-300">Allow indexing</span>
            </label>
            <label className="inline-flex items-center gap-2">
              <input
                type="checkbox"
                checked={pageForm.robots_follow}
                onChange={(e) => setPageForm({ ...pageForm, robots_follow: e.target.checked })}
                className="h-4 w-4 rounded border-gray-300 text-gray-900 focus:ring-gray-900"
              />
              <span className="text-gray-700 dark:text-neutral-300">Follow outbound links</span>
            </label>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="submit"
              disabled={busy}
              className="inline-flex h-10 px-5 items-center justify-center rounded-full bg-blue-600 text-white text-[13px] font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {busy ? "Saving…" : editingId ? "Update SEO entry" : "Create SEO entry"}
            </button>
            {editingId && (
              <button
                type="button"
                onClick={resetPageForm}
                className="inline-flex h-10 px-4 items-center justify-center rounded-full border border-gray-200 dark:border-neutral-800 text-[13px] font-medium text-gray-700 dark:text-neutral-300 hover:bg-gray-50 dark:hover:bg-neutral-900"
              >
                Cancel
              </button>
            )}
          </div>
        </form>

        {seoPages.length === 0 ? (
          <div className="p-12 text-center text-[13px] text-gray-500 dark:text-neutral-500">
            No SEO overrides yet — product/page metadata is generated automatically.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead className="bg-gray-50 dark:bg-neutral-900 text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500">
                <tr>
                  <th className="text-left px-5 py-3 font-medium">URL</th>
                  <th className="text-left px-5 py-3 font-medium">Title</th>
                  <th className="text-left px-5 py-3 font-medium">Keywords</th>
                  <th className="text-left px-5 py-3 font-medium">Focus</th>
                  <th className="text-left px-5 py-3 font-medium">Robots</th>
                  <th className="text-right px-5 py-3 font-medium">Action</th>
                </tr>
              </thead>
              <tbody>
                {seoPages.map((p) => (
                  <tr key={p.id} className="border-t border-gray-100 dark:border-neutral-900">
                    <td className="px-5 py-3 font-mono text-gray-900 dark:text-neutral-100">{p.url_path}</td>
                    <td className="px-5 py-3 text-gray-700 dark:text-neutral-300 max-w-[200px] truncate">{p.title || "—"}</td>
                    <td className="px-5 py-3 text-gray-500 dark:text-neutral-500 max-w-[200px] truncate">{p.meta_keywords || "—"}</td>
                    <td className="px-5 py-3 text-gray-700 dark:text-neutral-300">{p.focus_keyword || "—"}</td>
                    <td className="px-5 py-3 text-[12px] text-gray-500 dark:text-neutral-500">
                      {p.robots_index === false ? "noindex" : "index"} / {p.robots_follow === false ? "nofollow" : "follow"}
                    </td>
                    <td className="px-5 py-3 text-right space-x-3">
                      <button
                        onClick={() => startEditPage(p)}
                        className="text-[12px] text-blue-600 dark:text-blue-400 hover:underline"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => removeSeoPage(p.id)}
                        className="text-[12px] text-gray-500 dark:text-neutral-400 hover:text-red-600 hover:underline"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Redirects */}
      <section className="rounded-2xl bg-white dark:bg-neutral-950 border border-gray-100 dark:border-neutral-900 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 dark:border-neutral-900">
          <h2 className="text-[15px] font-semibold text-gray-900 dark:text-neutral-100">
            URL redirects
          </h2>
          <p className="text-[12px] text-gray-500 dark:text-neutral-500">
            Send visitors from old URLs to new ones. 301 is permanent, 302 is temporary, 308 preserves the request method.
          </p>
        </div>
        <form
          onSubmit={addRedirect}
          className="px-5 py-4 border-b border-gray-100 dark:border-neutral-900 bg-gray-50/50 dark:bg-neutral-950 grid md:grid-cols-4 gap-2"
        >
          <input
            required
            placeholder="/old-path"
            value={redirectForm.old_path}
            onChange={(e) => setRedirectForm({ ...redirectForm, old_path: e.target.value })}
            className="h-10 w-full rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 text-[13px] font-mono"
          />
          <input
            required
            placeholder="/new-path"
            value={redirectForm.new_path}
            onChange={(e) => setRedirectForm({ ...redirectForm, new_path: e.target.value })}
            className="h-10 w-full rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 text-[13px] font-mono"
          />
          <select
            value={redirectForm.status_code}
            onChange={(e) => setRedirectForm({ ...redirectForm, status_code: Number(e.target.value) })}
            className="h-10 w-full rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 text-[13px]"
          >
            <option value={301}>301 permanent</option>
            <option value={302}>302 temporary</option>
            <option value={308}>308 permanent (preserve method)</option>
          </select>
          <button className="h-10 rounded-full bg-blue-600 text-white text-[13px] font-medium hover:bg-blue-700 transition-colors">
            Add redirect
          </button>
        </form>

        {redirects.length === 0 ? (
          <div className="p-12 text-center text-[13px] text-gray-500 dark:text-neutral-500">
            No redirects configured.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead className="bg-gray-50 dark:bg-neutral-900 text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500">
                <tr>
                  <th className="text-left px-5 py-3 font-medium">From</th>
                  <th className="text-left px-5 py-3 font-medium">To</th>
                  <th className="text-left px-5 py-3 font-medium">Code</th>
                  <th className="text-right px-5 py-3 font-medium">Action</th>
                </tr>
              </thead>
              <tbody>
                {redirects.map((r) => (
                  <tr key={r.id} className="border-t border-gray-100 dark:border-neutral-900">
                    <td className="px-5 py-3 font-mono text-gray-900 dark:text-neutral-100">{r.old_path}</td>
                    <td className="px-5 py-3 font-mono text-gray-700 dark:text-neutral-300">{r.new_path}</td>
                    <td className="px-5 py-3 text-gray-500 dark:text-neutral-500">{r.status_code}</td>
                    <td className="px-5 py-3 text-right">
                      <button
                        onClick={() => removeRedirect(r.id)}
                        className="text-[12px] text-gray-500 dark:text-neutral-400 hover:text-red-600 hover:underline"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}