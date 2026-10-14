"use client";

import { useEffect, useState } from "react";
import { platformApi } from "@/lib/api";

interface ThemePreset {
  slug: string;
  name: string;
  is_preset?: boolean;
  config_json?: {
    colors?: Record<string, string>;
    typography?: { fontFamily?: string };
  };
  description?: string;
}

const PRESET_DESCRIPTIONS: Record<string, string> = {
  default: "Indigo + violet accent — a balanced, modern storefront.",
  minimal: "Black & white with restrained greys — premium and clean.",
  vibrant: "Pink + amber + green — bold and energetic for lifestyle brands.",
};

export default function ThemesPage() {
  const [presets, setPresets] = useState<ThemePreset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activePreset, setActivePreset] = useState<ThemePreset | null>(null);

  useEffect(() => {
    const fetchPresets = async () => {
      setLoading(true);
      setError(null);
      try {
        const res: any = await platformApi.getThemePresets();
        const list = Array.isArray(res) ? res : res.data || res.items || [];
        setPresets(list);
      } catch (e: any) {
        setError(e.message || "Failed to load theme presets");
      } finally {
        setLoading(false);
      }
    };
    fetchPresets();
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Theme Presets</h1>
        <p className="text-sm text-gray-500">
          Design-token bundles mirrored from <span className="font-mono">packages/themes</span>.
          Tenants can apply these to their storefront.
        </p>
      </div>

      {loading ? (
        <div className="bg-white rounded-lg shadow border p-12 text-center text-gray-500">
          Loading presets…
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-700 font-medium">Could not load presets</p>
          <p className="text-sm text-red-600 mt-1">{error}</p>
        </div>
      ) : presets.length === 0 ? (
        <div className="bg-white rounded-lg shadow border p-12 text-center text-gray-500">
          No theme presets registered.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {presets.map((p) => {
            const colors = p.config_json?.colors || {};
            return (
              <div
                key={p.slug}
                className="bg-white rounded-lg shadow border overflow-hidden flex flex-col"
              >
                <div className="p-5 flex-1">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-lg">{p.name}</h3>
                    {p.is_preset && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">
                        preset
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 font-mono mt-1">{p.slug}</p>
                  <p className="text-sm text-gray-600 mt-3">
                    {PRESET_DESCRIPTIONS[p.slug] || p.description || "Theme preset"}
                  </p>

                  <div className="mt-4">
                    <p className="text-xs font-medium text-gray-500 mb-2">Colors</p>
                    <div className="flex gap-2">
                      {[
                        { key: "primary", label: "Primary" },
                        { key: "secondary", label: "Secondary" },
                        { key: "accent", label: "Accent" },
                        { key: "background", label: "BG" },
                      ].map((c) => (
                        <div key={c.key} className="flex flex-col items-center">
                          <div
                            className="w-10 h-10 rounded border shadow-sm"
                            style={{ backgroundColor: colors[c.key] || "#e5e7eb" }}
                            title={`${c.label}: ${colors[c.key] || "—"}`}
                          />
                          <span className="text-[10px] text-gray-500 mt-1">{c.label}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="mt-4">
                    <p className="text-xs font-medium text-gray-500 mb-1">Font</p>
                    <p className="text-xs text-gray-700 font-mono break-all">
                      {p.config_json?.typography?.fontFamily || "—"}
                    </p>
                  </div>
                </div>
                <div className="border-t p-3">
                  <button
                    onClick={() => setActivePreset(p)}
                    className="w-full bg-gray-900 text-white text-sm py-2 rounded-lg hover:bg-gray-800"
                  >
                    View
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {activePreset && (
        <ThemeDetailModal preset={activePreset} onClose={() => setActivePreset(null)} />
      )}
    </div>
  );
}

function ThemeDetailModal({ preset, onClose }: { preset: ThemePreset; onClose: () => void }) {
  const colors = preset.config_json?.colors || {};
  const typo = preset.config_json?.typography || {};
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-lg w-full max-w-2xl max-h-[80vh] overflow-y-auto">
        <div className="p-5 border-b flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">{preset.name}</h2>
            <p className="text-xs text-gray-500 font-mono">{preset.slug}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-800 text-xl"
            aria-label="Close"
          >
            ×
          </button>
        </div>
        <div className="p-5 space-y-5">
          <section>
            <h3 className="text-sm font-semibold mb-2">Colors</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {Object.entries(colors).map(([name, value]) => (
                <div
                  key={name}
                  className="flex items-center gap-2 p-2 border rounded text-xs"
                >
                  <div
                    className="w-6 h-6 rounded border"
                    style={{ backgroundColor: value }}
                  />
                  <div>
                    <p className="font-mono">{name}</p>
                    <p className="text-gray-500">{value}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>
          <section>
            <h3 className="text-sm font-semibold mb-2">Typography</h3>
            <pre className="bg-gray-50 border rounded p-3 text-xs overflow-x-auto">
              {JSON.stringify(typo, null, 2)}
            </pre>
          </section>
          {preset.config_json && (
            <section>
              <h3 className="text-sm font-semibold mb-2">Full config</h3>
              <pre className="bg-gray-900 text-green-300 text-xs p-3 rounded overflow-x-auto max-h-64">
                {JSON.stringify(preset.config_json, null, 2)}
              </pre>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
