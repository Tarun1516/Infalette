"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Save, Send, Plus, ChevronDown } from "lucide-react";
import { adminApi } from "@/lib/api";
import {
  BlockCard,
  BLOCK_TYPES,
  BLOCK_LABELS,
  defaultBlockData,
  normalizeBlock,
  type BlockType,
} from "@/components/block-editor";

export default function PageEditor() {
  const params = useParams();
  const router = useRouter();
  const pageId = params.id as string;

  const [page, setPage] = useState<any>(null);
  const [blocks, setBlocks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [showAddMenu, setShowAddMenu] = useState(false);
  const [toast, setToast] = useState<{ kind: "ok" | "err"; msg: string } | null>(null);

  const [meta, setMeta] = useState({
    title: "",
    slug: "",
    path: "",
    is_homepage: false,
    status: "draft",
    meta_title: "",
    meta_description: "",
  });

  useEffect(() => {
    if (!pageId) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        // Try dedicated GET /pages/{id} first; fall back to list+find so
        // older backends without the single-get endpoint still work.
        let found: any = null;
        try {
          found = await adminApi.getPage(pageId);
        } catch {
          const res: any = await adminApi.getPages();
          const list: any[] = Array.isArray(res) ? res : [];
          found = list.find((p) => p.id === pageId) || null;
        }
        if (!found) throw new Error("Page not found");
        if (cancelled) return;
        setPage(found);
        setMeta({
          title: found.title || "",
          slug: found.slug || "",
          path: found.path || (found.slug ? `/${found.slug}` : "/"),
          is_homepage: !!found.is_homepage,
          status: found.status || "draft",
          meta_title: found.meta_title || "",
          meta_description: found.meta_description || "",
        });
        const rawBlocks = Array.isArray(found.blocks_json) ? found.blocks_json : [];
        setBlocks(rawBlocks.map(normalizeBlock));
      } catch (e: any) {
        if (!cancelled) setError(e.message || "Failed to load page");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pageId]);

  const isDirty = useMemo(() => {
    if (!page) return false;
    if (meta.title !== (page.title || "")) return true;
    if (meta.slug !== (page.slug || "")) return true;
    if (meta.path !== (page.path || (page.slug ? `/${page.slug}` : "/"))) return true;
    if (meta.is_homepage !== !!page.is_homepage) return true;
    if (meta.status !== (page.status || "draft")) return true;
    if ((meta.meta_title || "") !== (page.meta_title || "")) return true;
    if ((meta.meta_description || "") !== (page.meta_description || "")) return true;
    // We don't track block-by-block diffing (would require memoizing the
    // original array), so the editor always advertises that the blocks list
    // may be unsaved. The Save button is always available.
    return true;
  }, [meta, page]);

  const updateBlock = (idx: number, next: any) => {
    setBlocks((bs) => bs.map((b, i) => (i === idx ? next : b)));
  };

  const moveBlock = (idx: number, dir: "up" | "down") => {
    setBlocks((bs) => {
      const j = dir === "up" ? idx - 1 : idx + 1;
      if (j < 0 || j >= bs.length) return bs;
      const next = [...bs];
      [next[idx], next[j]] = [next[j], next[idx]];
      return next;
    });
  };

  const deleteBlock = (idx: number) => {
    setBlocks((bs) => bs.filter((_, i) => i !== idx));
  };

  const addBlock = (type: BlockType) => {
    setBlocks((bs) => [...bs, defaultBlockData(type)]);
    setShowAddMenu(false);
  };

  const showToast = (kind: "ok" | "err", msg: string) => {
    setToast({ kind, msg });
    setTimeout(() => setToast(null), 2500);
  };

  const handleSave = async () => {
    if (!page) return;
    setSaving(true);
    try {
      const updated = await adminApi.updatePage(page.id, {
        title: meta.title,
        slug: meta.slug,
        path: meta.path,
        is_homepage: meta.is_homepage,
        status: meta.status,
        meta_title: meta.meta_title || null,
        meta_description: meta.meta_description || null,
        blocks_json: blocks,
      });
      setPage(updated);
      showToast("ok", "Saved");
    } catch (e: any) {
      showToast("err", e.message || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handlePublish = async () => {
    if (!page) return;
    setPublishing(true);
    try {
      // Save first (in case there are unsaved changes), then publish.
      await adminApi.updatePage(page.id, {
        title: meta.title,
        slug: meta.slug,
        path: meta.path,
        is_homepage: meta.is_homepage,
        status: meta.status,
        meta_title: meta.meta_title || null,
        meta_description: meta.meta_description || null,
        blocks_json: blocks,
      });
      await adminApi.publishPage(page.id);
      setPage((p: any) => ({ ...p, status: "published" }));
      setMeta((m) => ({ ...m, status: "published" }));
      showToast("ok", "Published");
    } catch (e: any) {
      showToast("err", e.message || "Publish failed");
    } finally {
      setPublishing(false);
    }
  };

  if (loading) {
    return <div className="p-12 text-center text-gray-500">Loading page…</div>;
  }
  if (error) {
    return (
      <div className="p-8 text-center">
        <p className="text-red-600 text-sm">{error}</p>
        <button
          onClick={() => router.push("/pages")}
          className="mt-3 text-sm border px-4 py-2 rounded"
        >
          Back to pages
        </button>
      </div>
    );
  }
  if (!page) return null;

  return (
    <div className="max-w-5xl space-y-6">
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <Link href="/pages" className="hover:underline flex items-center gap-1">
          <ArrowLeft className="h-3.5 w-3.5" /> Pages
        </Link>
        <span>›</span>
        <span className="font-medium text-gray-700">{meta.title || "Untitled"}</span>
      </div>

      <div className="bg-white rounded-2xl border shadow-sm p-5 space-y-4">
        <div className="flex flex-col sm:flex-row justify-between gap-3 sm:items-center">
          <div>
            <h1 className="text-2xl font-bold">Edit page</h1>
            <p className="text-xs text-gray-500 font-mono mt-1">id: {page.id}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="inline-flex items-center gap-1 px-4 py-2 border rounded-lg text-sm hover:bg-gray-50 disabled:opacity-50"
            >
              <Save className="h-4 w-4" /> {saving ? "Saving…" : "Save"}
            </button>
            <button
              type="button"
              onClick={handlePublish}
              disabled={publishing}
              className="inline-flex items-center gap-1 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              <Send className="h-4 w-4" /> {publishing ? "Publishing…" : "Publish"}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-medium text-gray-700 block mb-1">Title</label>
            <input
              value={meta.title}
              onChange={(e) => setMeta({ ...meta, title: e.target.value })}
              className="w-full border rounded-lg px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-700 block mb-1">Slug</label>
            <input
              value={meta.slug}
              onChange={(e) => setMeta({ ...meta, slug: e.target.value })}
              className="w-full border rounded-lg px-3 py-2 text-sm font-mono"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-700 block mb-1">Path</label>
            <input
              value={meta.path}
              onChange={(e) => setMeta({ ...meta, path: e.target.value })}
              placeholder="/about-us"
              className="w-full border rounded-lg px-3 py-2 text-sm font-mono"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-700 block mb-1">Status</label>
            <select
              value={meta.status}
              onChange={(e) => setMeta({ ...meta, status: e.target.value })}
              className="w-full border rounded-lg px-3 py-2 text-sm bg-white"
            >
              <option value="draft">draft</option>
              <option value="published">published</option>
              <option value="archived">archived</option>
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-gray-700 block mb-1">Meta title</label>
            <input
              value={meta.meta_title}
              onChange={(e) => setMeta({ ...meta, meta_title: e.target.value })}
              className="w-full border rounded-lg px-3 py-2 text-sm"
            />
          </div>
          <div className="flex items-end">
            <label className="inline-flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={meta.is_homepage}
                onChange={(e) => setMeta({ ...meta, is_homepage: e.target.checked })}
                className="rounded"
              />
              <span>Set as homepage</span>
            </label>
          </div>
          <div className="md:col-span-2">
            <label className="text-xs font-medium text-gray-700 block mb-1">Meta description</label>
            <textarea
              rows={2}
              value={meta.meta_description}
              onChange={(e) => setMeta({ ...meta, meta_description: e.target.value })}
              className="w-full border rounded-lg px-3 py-2 text-sm"
            />
          </div>
        </div>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Blocks</h2>
          <div className="relative">
            <button
              type="button"
              onClick={() => setShowAddMenu((s) => !s)}
              className="inline-flex items-center gap-1 px-3 py-1.5 border rounded-lg text-sm hover:bg-gray-50"
            >
              <Plus className="h-4 w-4" /> Add block <ChevronDown className="h-3.5 w-3.5" />
            </button>
            {showAddMenu && (
              <div className="absolute right-0 mt-1 w-56 bg-white border rounded-xl shadow-lg z-20 max-h-72 overflow-y-auto">
                {BLOCK_TYPES.map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => addBlock(t)}
                    className="block w-full text-left px-3 py-2 text-sm hover:bg-gray-50"
                  >
                    {BLOCK_LABELS[t]}
                    <span className="block text-xs text-gray-400 font-mono">{t}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {blocks.length === 0 ? (
          <div className="bg-white border-2 border-dashed rounded-2xl p-12 text-center">
            <p className="text-sm text-gray-500">No blocks yet</p>
            <p className="text-xs text-gray-400 mt-1">
              Click &quot;Add block&quot; to start composing your page.
            </p>
          </div>
        ) : (
          blocks.map((b, idx) => (
            <BlockCard
              key={idx}
              index={idx}
              total={blocks.length}
              block={b}
              onChange={(next) => updateBlock(idx, next)}
              onMove={(d) => moveBlock(idx, d)}
              onDelete={() => deleteBlock(idx)}
            />
          ))
        )}
      </div>

      {toast && (
        <div
          className={`fixed bottom-6 right-6 px-4 py-2 rounded-lg shadow-lg text-sm text-white ${
            toast.kind === "ok" ? "bg-green-600" : "bg-red-600"
          }`}
        >
          {toast.msg}
        </div>
      )}

      {isDirty && (
        <p className="text-xs text-gray-400 text-right">Unsaved changes — click Save to persist.</p>
      )}
    </div>
  );
}
