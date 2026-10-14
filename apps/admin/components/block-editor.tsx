"use client";

import { GripVertical, ArrowUp, ArrowDown, Trash2 } from "lucide-react";
import { ReactNode } from "react";

/**
 * Block type catalog — matches PageBlockType enum in
 * packages/database/src/infalette_database/models/page.py
 */
export const BLOCK_TYPES = [
  "hero",
  "featured_products",
  "category_grid",
  "testimonials",
  "influencer_story",
  "video",
  "faq",
  "bundles",
  "newsletter",
  "instagram_gallery",
] as const;

export type BlockType = (typeof BLOCK_TYPES)[number];

export const BLOCK_LABELS: Record<BlockType, string> = {
  hero: "Hero",
  featured_products: "Featured Products",
  category_grid: "Category Grid",
  testimonials: "Testimonials",
  influencer_story: "Influencer Story",
  video: "Video",
  faq: "FAQ",
  bundles: "Bundles",
  newsletter: "Newsletter",
  instagram_gallery: "Instagram Gallery",
};

/**
 * Default payload for a freshly added block. Each block has a `data` object
 * that matches the storefront renderer field names.
 */
export function defaultBlockData(type: BlockType): any {
  switch (type) {
    case "hero":
      return {
        type,
        data: {
          title: "",
          subtitle: "",
          cta_label: "",
          cta_url: "",
          image_url: "",
          eyebrow: "",
        },
      };
    case "featured_products":
      return { type, data: { title: "", product_ids: [], columns: 4 } };
    case "category_grid":
      return { type, data: { title: "", category_ids: [], columns: 4 } };
    case "testimonials":
      return {
        type,
        data: { title: "", items: [{ author: "", quote: "", rating: 5 }] },
      };
    case "influencer_story":
      return { type, data: { title: "", body: "", image_url: "" } };
    case "video":
      return { type, data: { title: "", video_url: "", poster_url: "" } };
    case "faq":
      return { type, data: { title: "", items: [{ question: "", answer: "" }] } };
    case "bundles":
      return { type, data: { title: "", bundle_ids: [] } };
    case "newsletter":
      return { type, data: { title: "", description: "", button_label: "" } };
    case "instagram_gallery":
      return { type, data: { title: "", handle: "", post_count: 6 } };
  }
}

/** Normalize an existing block on load (handle both {type,data} and {type,...} shapes). */
export function normalizeBlock(raw: any): any {
  if (!raw || typeof raw !== "object") return { type: "hero", data: {} };
  if (raw.data && typeof raw.data === "object") {
    return { type: raw.type, data: { ...raw.data } };
  }
  // Flatten unknown shape into data envelope
  const { type, data: _d, ...rest } = raw;
  return { type: type || "hero", data: rest };
}

interface FieldProps {
  label: string;
  children: ReactNode;
  hint?: string;
}
export function Field({ label, children, hint }: FieldProps) {
  return (
    <div>
      <label className="text-xs font-medium text-gray-700 block mb-1">{label}</label>
      {children}
      {hint && <p className="text-xs text-gray-400 mt-0.5">{hint}</p>}
    </div>
  );
}

const inputClass = "w-full border rounded-lg px-3 py-2 text-sm";

interface BlockCardProps {
  index: number;
  total: number;
  block: any;
  onChange: (next: any) => void;
  onMove: (dir: "up" | "down") => void;
  onDelete: () => void;
}

export function BlockCard({ index, total, block, onChange, onMove, onDelete }: BlockCardProps) {
  const type = block.type as BlockType;
  const data = block.data || {};
  const setField = (key: string, value: any) => onChange({ ...block, data: { ...data, [key]: value } });

  const renderFields = () => {
    switch (type) {
      case "hero":
        return (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Field label="Eyebrow">
              <input
                className={inputClass}
                value={data.eyebrow || ""}
                onChange={(e) => setField("eyebrow", e.target.value)}
              />
            </Field>
            <Field label="Title">
              <input
                className={inputClass}
                value={data.title || ""}
                onChange={(e) => setField("title", e.target.value)}
              />
            </Field>
            <Field label="Subtitle" hint="Optional supporting copy.">
              <textarea
                rows={2}
                className={inputClass}
                value={data.subtitle || ""}
                onChange={(e) => setField("subtitle", e.target.value)}
              />
            </Field>
            <Field label="Image URL">
              <input
                className={inputClass}
                value={data.image_url || ""}
                onChange={(e) => setField("image_url", e.target.value)}
              />
            </Field>
            <Field label="CTA label">
              <input
                className={inputClass}
                value={data.cta_label || ""}
                onChange={(e) => setField("cta_label", e.target.value)}
              />
            </Field>
            <Field label="CTA URL">
              <input
                className={inputClass}
                value={data.cta_url || ""}
                onChange={(e) => setField("cta_url", e.target.value)}
              />
            </Field>
          </div>
        );
      case "featured_products":
        return (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <Field label="Title">
              <input
                className={inputClass}
                value={data.title || ""}
                onChange={(e) => setField("title", e.target.value)}
              />
            </Field>
            <Field label="Columns" hint="1–6">
              <input
                type="number"
                min={1}
                max={6}
                className={inputClass}
                value={data.columns ?? 4}
                onChange={(e) => setField("columns", parseInt(e.target.value) || 4)}
              />
            </Field>
            <Field label="Product IDs" hint="Comma-separated UUIDs.">
              <input
                className={`${inputClass} font-mono`}
                value={(data.product_ids || []).join(", ")}
                onChange={(e) =>
                  setField(
                    "product_ids",
                    e.target.value
                      .split(",")
                      .map((s) => s.trim())
                      .filter(Boolean),
                  )
                }
              />
            </Field>
          </div>
        );
      case "category_grid":
        return (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <Field label="Title">
              <input
                className={inputClass}
                value={data.title || ""}
                onChange={(e) => setField("title", e.target.value)}
              />
            </Field>
            <Field label="Columns" hint="1–6">
              <input
                type="number"
                min={1}
                max={6}
                className={inputClass}
                value={data.columns ?? 4}
                onChange={(e) => setField("columns", parseInt(e.target.value) || 4)}
              />
            </Field>
            <Field label="Category IDs" hint="Comma-separated UUIDs.">
              <input
                className={`${inputClass} font-mono`}
                value={(data.category_ids || []).join(", ")}
                onChange={(e) =>
                  setField(
                    "category_ids",
                    e.target.value
                      .split(",")
                      .map((s) => s.trim())
                      .filter(Boolean),
                  )
                }
              />
            </Field>
          </div>
        );
      case "testimonials":
        return (
          <div className="space-y-3">
            <Field label="Title">
              <input
                className={inputClass}
                value={data.title || ""}
                onChange={(e) => setField("title", e.target.value)}
              />
            </Field>
            <div>
              <p className="text-xs font-medium text-gray-700 mb-1">Testimonials</p>
              <div className="space-y-2">
                {(data.items || []).map((it: any, idx: number) => (
                  <div key={idx} className="border rounded-lg p-3 bg-gray-50 space-y-2">
                    <input
                      placeholder="Author"
                      className={inputClass}
                      value={it.author || ""}
                      onChange={(e) => {
                        const items = [...(data.items || [])];
                        items[idx] = { ...items[idx], author: e.target.value };
                        setField("items", items);
                      }}
                    />
                    <textarea
                      placeholder="Quote"
                      rows={2}
                      className={inputClass}
                      value={it.quote || ""}
                      onChange={(e) => {
                        const items = [...(data.items || [])];
                        items[idx] = { ...items[idx], quote: e.target.value };
                        setField("items", items);
                      }}
                    />
                    <div className="flex items-center gap-2">
                      <label className="text-xs text-gray-600">Rating</label>
                      <input
                        type="number"
                        min={1}
                        max={5}
                        className="w-20 border rounded px-2 py-1 text-sm"
                        value={it.rating ?? 5}
                        onChange={(e) => {
                          const items = [...(data.items || [])];
                          items[idx] = { ...items[idx], rating: parseInt(e.target.value) || 5 };
                          setField("items", items);
                        }}
                      />
                      <button
                        type="button"
                        onClick={() => {
                          const items = [...(data.items || [])];
                          items.splice(idx, 1);
                          setField("items", items);
                        }}
                        className="ml-auto text-xs text-red-600 hover:underline"
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() =>
                    setField("items", [...(data.items || []), { author: "", quote: "", rating: 5 }])
                  }
                  className="text-xs border px-3 py-1.5 rounded hover:bg-gray-50"
                >
                  + Add testimonial
                </button>
              </div>
            </div>
          </div>
        );
      case "influencer_story":
        return (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Field label="Title">
              <input
                className={inputClass}
                value={data.title || ""}
                onChange={(e) => setField("title", e.target.value)}
              />
            </Field>
            <Field label="Image URL">
              <input
                className={inputClass}
                value={data.image_url || ""}
                onChange={(e) => setField("image_url", e.target.value)}
              />
            </Field>
            <div className="md:col-span-2">
              <Field label="Body">
                <textarea
                  rows={4}
                  className={inputClass}
                  value={data.body || ""}
                  onChange={(e) => setField("body", e.target.value)}
                />
              </Field>
            </div>
          </div>
        );
      case "video":
        return (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Field label="Title">
              <input
                className={inputClass}
                value={data.title || ""}
                onChange={(e) => setField("title", e.target.value)}
              />
            </Field>
            <Field label="Video URL" hint="YouTube, Vimeo, or direct .mp4">
              <input
                className={`${inputClass} font-mono`}
                value={data.video_url || ""}
                onChange={(e) => setField("video_url", e.target.value)}
              />
            </Field>
            <Field label="Poster URL">
              <input
                className={inputClass}
                value={data.poster_url || ""}
                onChange={(e) => setField("poster_url", e.target.value)}
              />
            </Field>
          </div>
        );
      case "faq":
        return (
          <div className="space-y-3">
            <Field label="Title">
              <input
                className={inputClass}
                value={data.title || ""}
                onChange={(e) => setField("title", e.target.value)}
              />
            </Field>
            <div>
              <p className="text-xs font-medium text-gray-700 mb-1">Questions</p>
              <div className="space-y-2">
                {(data.items || []).map((it: any, idx: number) => (
                  <div key={idx} className="border rounded-lg p-3 bg-gray-50 space-y-2">
                    <input
                      placeholder="Question"
                      className={inputClass}
                      value={it.question || ""}
                      onChange={(e) => {
                        const items = [...(data.items || [])];
                        items[idx] = { ...items[idx], question: e.target.value };
                        setField("items", items);
                      }}
                    />
                    <textarea
                      placeholder="Answer"
                      rows={2}
                      className={inputClass}
                      value={it.answer || ""}
                      onChange={(e) => {
                        const items = [...(data.items || [])];
                        items[idx] = { ...items[idx], answer: e.target.value };
                        setField("items", items);
                      }}
                    />
                    <button
                      type="button"
                      onClick={() => {
                        const items = [...(data.items || [])];
                        items.splice(idx, 1);
                        setField("items", items);
                      }}
                      className="text-xs text-red-600 hover:underline"
                    >
                      Remove
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() =>
                    setField("items", [...(data.items || []), { question: "", answer: "" }])
                  }
                  className="text-xs border px-3 py-1.5 rounded hover:bg-gray-50"
                >
                  + Add question
                </button>
              </div>
            </div>
          </div>
        );
      case "bundles":
        return (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Field label="Title">
              <input
                className={inputClass}
                value={data.title || ""}
                onChange={(e) => setField("title", e.target.value)}
              />
            </Field>
            <Field label="Bundle IDs" hint="Comma-separated UUIDs.">
              <input
                className={`${inputClass} font-mono`}
                value={(data.bundle_ids || []).join(", ")}
                onChange={(e) =>
                  setField(
                    "bundle_ids",
                    e.target.value
                      .split(",")
                      .map((s) => s.trim())
                      .filter(Boolean),
                  )
                }
              />
            </Field>
          </div>
        );
      case "newsletter":
        return (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Field label="Title">
              <input
                className={inputClass}
                value={data.title || ""}
                onChange={(e) => setField("title", e.target.value)}
              />
            </Field>
            <Field label="Button label">
              <input
                className={inputClass}
                value={data.button_label || ""}
                onChange={(e) => setField("button_label", e.target.value)}
              />
            </Field>
            <div className="md:col-span-2">
              <Field label="Description">
                <textarea
                  rows={3}
                  className={inputClass}
                  value={data.description || ""}
                  onChange={(e) => setField("description", e.target.value)}
                />
              </Field>
            </div>
          </div>
        );
      case "instagram_gallery":
        return (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <Field label="Title">
              <input
                className={inputClass}
                value={data.title || ""}
                onChange={(e) => setField("title", e.target.value)}
              />
            </Field>
            <Field label="Handle" hint="Without @">
              <input
                className={inputClass}
                value={data.handle || ""}
                onChange={(e) => setField("handle", e.target.value)}
              />
            </Field>
            <Field label="Post count">
              <input
                type="number"
                min={1}
                max={20}
                className={inputClass}
                value={data.post_count ?? 6}
                onChange={(e) => setField("post_count", parseInt(e.target.value) || 6)}
              />
            </Field>
          </div>
        );
      default:
        return (
          <div>
            <p className="text-xs text-gray-500">Unknown block type. Edit raw JSON below.</p>
            <textarea
              rows={4}
              className={`${inputClass} font-mono mt-2`}
              value={JSON.stringify(block, null, 2)}
              onChange={(e) => {
                try {
                  const next = JSON.parse(e.target.value);
                  onChange(next);
                } catch {
                  /* ignore */
                }
              }}
            />
          </div>
        );
    }
  };

  return (
    <div className="bg-white border rounded-2xl shadow-sm">
      <div className="flex items-center gap-2 p-3 border-b bg-gray-50 rounded-t-2xl">
        <GripVertical className="h-4 w-4 text-gray-400" />
        <span className="text-sm font-semibold flex-1">
          {BLOCK_LABELS[type] || type}
        </span>
        <span className="text-xs text-gray-400 font-mono">#{index + 1}</span>
        <button
          type="button"
          onClick={() => onMove("up")}
          disabled={index === 0}
          className="p-1.5 rounded hover:bg-white disabled:opacity-30"
          title="Move up"
        >
          <ArrowUp className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => onMove("down")}
          disabled={index === total - 1}
          className="p-1.5 rounded hover:bg-white disabled:opacity-30"
          title="Move down"
        >
          <ArrowDown className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={onDelete}
          className="p-1.5 rounded hover:bg-white text-red-600"
          title="Delete block"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
      <div className="p-4">{renderFields()}</div>
    </div>
  );
}
