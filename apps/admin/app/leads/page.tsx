"use client";

import { toast } from "@/components/toaster";

import { useEffect, useMemo, useState } from "react";
import { X, Mail, Phone, Calendar, ExternalLink, RefreshCw, MessageCircle } from "lucide-react";
import { adminApi } from "@/lib/api";

const STAGES = [
  "new_lead",
  "engaged",
  "product_selected",
  "checkout_created",
  "paid",
  "fulfilled",
  "repeat_customer",
] as const;

type Stage = (typeof STAGES)[number];

const STAGE_LABELS: Record<Stage, string> = {
  new_lead: "New Lead",
  engaged: "Engaged",
  product_selected: "Product Selected",
  checkout_created: "Checkout Created",
  paid: "Paid",
  fulfilled: "Fulfilled",
  repeat_customer: "Repeat Customer",
};

const STAGE_COLORS: Record<Stage, string> = {
  new_lead: "border-t-gray-400",
  engaged: "border-t-blue-400",
  product_selected: "border-t-indigo-400",
  checkout_created: "border-t-amber-400",
  paid: "border-t-emerald-400",
  fulfilled: "border-t-green-500",
  repeat_customer: "border-t-purple-500",
};

const STAGE_ACCENT: Record<Stage, string> = {
  new_lead: "bg-gray-500",
  engaged: "bg-blue-500",
  product_selected: "bg-indigo-500",
  checkout_created: "bg-amber-500",
  paid: "bg-emerald-500",
  fulfilled: "bg-green-600",
  repeat_customer: "bg-purple-500",
};

interface Lead {
  id: string;
  first_name?: string | null;
  last_name?: string | null;
  email?: string | null;
  phone?: string | null;
  source?: string | null;
  status?: string | null;
  stage?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  assigned_to?: string | null;
  tags?: any;
  score?: number;
}

function leadStage(l: Lead): Stage {
  const raw = (l.status || l.stage || "new_lead") as string;
  if (STAGES.includes(raw as Stage)) return raw as Stage;
  // legacy alias
  if (raw === "new") return "new_lead";
  if (raw === "converted") return "repeat_customer";
  return "new_lead";
}

function lastActivity(l: Lead): string | null {
  return l.updated_at || l.created_at || null;
}

function timeAgo(iso?: string | null) {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "—";
  const diff = Date.now() - t;
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 30) return `${d}d ago`;
  return new Date(iso).toLocaleDateString();
}

export default function LeadsKanban() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState<{ id: string; from: Stage } | null>(null);
  const [hoverCol, setHoverCol] = useState<Stage | null>(null);
  const [openLead, setOpenLead] = useState<Lead | null>(null);
  const [search, setSearch] = useState("");

  const fetchLeads = async () => {
    setLoading(true);
    setError(null);
    try {
      const res: any = await adminApi.getLeads();
      const list: any[] = Array.isArray(res) ? res : res.data || res.items || [];
      setLeads(list);
    } catch (e: any) {
      setError(e.message || "Failed to load leads");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLeads();
  }, []);

  const filtered = useMemo(() => {
    if (!search.trim()) return leads;
    const q = search.toLowerCase();
    return leads.filter(
      (l) =>
        (l.email || "").toLowerCase().includes(q) ||
        (l.first_name || "").toLowerCase().includes(q) ||
        (l.last_name || "").toLowerCase().includes(q) ||
        (l.phone || "").toLowerCase().includes(q),
    );
  }, [leads, search]);

  const grouped = useMemo(() => {
    const map: Record<Stage, Lead[]> = {
      new_lead: [],
      engaged: [],
      product_selected: [],
      checkout_created: [],
      paid: [],
      fulfilled: [],
      repeat_customer: [],
    };
    for (const l of filtered) {
      map[leadStage(l)].push(l);
    }
    return map;
  }, [filtered]);

  const onDragStart = (e: React.DragEvent, lead: Lead) => {
    setDragging({ id: lead.id, from: leadStage(lead) });
    e.dataTransfer.effectAllowed = "move";
    // Some browsers need data to actually fire drop events
    e.dataTransfer.setData("text/plain", lead.id);
  };

  const onDragEnd = () => {
    setDragging(null);
    setHoverCol(null);
  };

  const onColumnDragOver = (e: React.DragEvent, col: Stage) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    if (hoverCol !== col) setHoverCol(col);
  };

  const onColumnDrop = async (e: React.DragEvent, col: Stage) => {
    e.preventDefault();
    const leadId = e.dataTransfer.getData("text/plain") || dragging?.id;
    setHoverCol(null);
    setDragging(null);
    if (!leadId) return;
    const lead = leads.find((l) => l.id === leadId);
    if (!lead) return;
    const from = leadStage(lead);
    if (from === col) return;
    // Optimistic update
    setLeads((cur) =>
      cur.map((l) => (l.id === leadId ? { ...l, status: col, stage: col } : l)),
    );
    try {
      await adminApi.updateLeadStage(leadId, col);
    } catch (e: any) {
      // Revert
      setLeads((cur) =>
        cur.map((l) => (l.id === leadId ? { ...l, status: from, stage: from } : l)),
      );
      toast({ kind: "error", title: "Something went wrong", description: e.message || "Failed to update stage" });
    }
  };

  const moveTo = async (leadId: string, col: Stage) => {
    const lead = leads.find((l) => l.id === leadId);
    if (!lead) return;
    const from = leadStage(lead);
    if (from === col) return;
    setLeads((cur) => cur.map((l) => (l.id === leadId ? { ...l, status: col, stage: col } : l)));
    try {
      await adminApi.updateLeadStage(leadId, col);
    } catch (e: any) {
      setLeads((cur) => cur.map((l) => (l.id === leadId ? { ...l, status: from, stage: from } : l)));
      toast({ kind: "error", title: "Something went wrong", description: e.message || "Failed to update stage" });
    }
  };

  const total = leads.length;

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
        <div>
          <h1 className="text-2xl font-bold">Leads</h1>
          <p className="text-sm text-gray-500">
            {total} lead{total === 1 ? "" : "s"} • Drag a card between columns to change stage.
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, email, phone…"
            className="border rounded-lg px-3 py-2 text-sm bg-white w-64"
          />
          <button
            onClick={fetchLeads}
            className="inline-flex items-center gap-1 px-3 py-2 border rounded-lg text-sm hover:bg-gray-50"
            title="Refresh"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <label className="px-3 py-2 border rounded-lg text-sm bg-white cursor-pointer hover:bg-gray-50">
            Import CSV
            <input
              type="file"
              accept=".csv"
              className="hidden"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                try {
                  await adminApi.bulkImportLeads(file);
                  fetchLeads();
                } catch (err: any) {
                  toast({ kind: "error", title: "Something went wrong", description: err.message || "Import failed" });
                }
              }}
            />
          </label>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <div className="bg-white border rounded-2xl p-12 text-center text-gray-500">
          Loading leads…
        </div>
      ) : (
        <div className="overflow-x-auto pb-4">
          <div className="grid grid-cols-7 gap-3 min-w-[1500px]">
            {STAGES.map((stage) => {
              const list = grouped[stage];
              const isHover = hoverCol === stage;
              return (
                <div
                  key={stage}
                  onDragOver={(e) => onColumnDragOver(e, stage)}
                  onDragLeave={() => setHoverCol((c) => (c === stage ? null : c))}
                  onDrop={(e) => onColumnDrop(e, stage)}
                  className={`bg-gray-50 rounded-2xl border ${STAGE_COLORS[stage]} border-t-4 ${
                    isHover ? "ring-2 ring-blue-400 bg-blue-50" : ""
                  } flex flex-col`}
                >
                  <div className="p-3 flex items-center justify-between border-b bg-white rounded-t-2xl">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className={`h-2 w-2 rounded-full ${STAGE_ACCENT[stage]}`} />
                      <span className="text-sm font-semibold truncate">
                        {STAGE_LABELS[stage]}
                      </span>
                    </div>
                    <span className="text-xs font-medium bg-gray-100 px-2 py-0.5 rounded-full">
                      {list.length}
                    </span>
                  </div>
                  <div className="p-2 space-y-2 flex-1 min-h-[120px]">
                    {list.length === 0 ? (
                      <p className="text-xs text-gray-400 text-center py-6">No leads</p>
                    ) : (
                      list.map((l) => (
                        <div
                          key={l.id}
                          draggable
                          onDragStart={(e) => onDragStart(e, l)}
                          onDragEnd={onDragEnd}
                          onClick={() => setOpenLead(l)}
                          className="bg-white border rounded-xl p-3 shadow-sm cursor-pointer hover:shadow-md transition-shadow"
                        >
                          <p className="text-sm font-medium truncate">
                            {[l.first_name, l.last_name].filter(Boolean).join(" ") || l.email || "Unnamed"}
                          </p>
                          {l.email && (
                            <p className="text-xs text-gray-500 truncate mt-0.5">{l.email}</p>
                          )}
                          <div className="flex items-center justify-between mt-2 text-[10px] text-gray-400">
                            <span className="truncate max-w-[60%]">
                              {l.source || "—"}
                            </span>
                            <span>{timeAgo(lastActivity(l))}</span>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {openLead && (
        <LeadSidePanel
          lead={openLead}
          onClose={() => setOpenLead(null)}
          onMoveStage={(s) => {
            moveTo(openLead.id, s);
            setOpenLead((p) => (p ? { ...p, status: s, stage: s } : p));
          }}
        />
      )}
    </div>
  );
}

function LeadSidePanel({
  lead,
  onClose,
  onMoveStage,
}: {
  lead: Lead;
  onClose: () => void;
  onMoveStage: (s: Stage) => void;
}) {
  const [timeline, setTimeline] = useState<any[]>([]);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [conversations, setConversations] = useState<any[]>([]);
  const [conversationsLoading, setConversationsLoading] = useState(false);
  const [converting, setConverting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setTimelineLoading(true);
    (async () => {
      try {
        const tl = await adminApi.getLeadTimeline(lead.id).catch(() => []);
        if (!cancelled) setTimeline(Array.isArray(tl) ? tl : []);
      } finally {
        if (!cancelled) setTimelineLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [lead.id]);

  useEffect(() => {
    let cancelled = false;
    setConversationsLoading(true);
    (async () => {
      try {
        const res: any = await adminApi.getConversations().catch(() => null);
        if (cancelled) return;
        const list: any[] = Array.isArray(res) ? res : res?.data || res?.items || [];
        setConversations(list.filter((c: any) => c.lead_id === lead.id));
      } finally {
        if (!cancelled) setConversationsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [lead.id]);

  const name = [lead.first_name, lead.last_name].filter(Boolean).join(" ") || lead.email || "Unnamed";

  const handleConvert = async () => {
    setConverting(true);
    try {
      await adminApi.convertLead(lead.id);
      toast({ kind: "success", title: "Lead converted to customer" });
      onClose();
    } catch (e: any) {
      toast({ kind: "error", title: "Something went wrong", description: e.message || "Convert failed" });
    } finally {
      setConverting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-40 flex">
      <div className="flex-1 bg-black/30" onClick={onClose} />
      <div className="w-full max-w-md bg-white shadow-2xl overflow-y-auto">
        <div className="sticky top-0 bg-white border-b p-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Lead details</h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-4 space-y-4">
          <div>
            <h3 className="text-xl font-bold">{name}</h3>
            <p className="text-xs text-gray-500 font-mono mt-1">id: {lead.id}</p>
          </div>

          <div className="space-y-2 text-sm">
            {lead.email && (
              <div className="flex items-center gap-2 text-gray-700">
                <Mail className="h-4 w-4 text-gray-400" />
                <a href={`mailto:${lead.email}`} className="hover:underline">
                  {lead.email}
                </a>
              </div>
            )}
            {lead.phone && (
              <div className="flex items-center gap-2 text-gray-700">
                <Phone className="h-4 w-4 text-gray-400" />
                <a href={`tel:${lead.phone}`} className="hover:underline">
                  {lead.phone}
                </a>
              </div>
            )}
            <div className="flex items-center gap-2 text-gray-700">
              <Calendar className="h-4 w-4 text-gray-400" />
              <span>Created {lead.created_at ? new Date(lead.created_at).toLocaleString() : "—"}</span>
            </div>
            <div className="text-xs text-gray-500">
              Source: {lead.source || "—"} • Assigned: {lead.assigned_to || "Unassigned"}
            </div>
            {Array.isArray(lead.tags) && lead.tags.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {lead.tags.map((t: any, i: number) => (
                  <span key={i} className="text-[10px] bg-gray-100 px-2 py-0.5 rounded-full">
                    {String(t)}
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="border-t pt-3">
            <p className="text-xs font-medium text-gray-700 mb-2">Update stage</p>
            <div className="flex flex-wrap gap-1">
              {STAGES.map((s) => (
                <button
                  key={s}
                  onClick={() => onMoveStage(s)}
                  className={`text-xs px-2 py-1 rounded-full border ${
                    leadStage(lead) === s
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white hover:bg-gray-50"
                  }`}
                >
                  {STAGE_LABELS[s]}
                </button>
              ))}
            </div>
          </div>

          <div className="border-t pt-3 flex flex-wrap gap-2">
            <a
              href={`/leads/${lead.id}`}
              className="inline-flex items-center gap-1 px-3 py-1.5 border rounded-lg text-sm hover:bg-gray-50"
            >
              <ExternalLink className="h-4 w-4" /> Edit
            </a>
            <button
              onClick={handleConvert}
              disabled={converting}
              className="px-3 py-1.5 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 disabled:opacity-50"
            >
              {converting ? "Converting…" : "Convert to customer"}
            </button>
          </div>

          <div className="border-t pt-3">
            <p className="text-xs font-medium text-gray-700 mb-2">Timeline</p>
            {timelineLoading ? (
              <p className="text-xs text-gray-400">Loading…</p>
            ) : timeline.length === 0 ? (
              <p className="text-xs text-gray-400">No events yet</p>
            ) : (
              <ol className="space-y-2">
                {timeline.map((e: any) => (
                  <li key={e.id} className="text-xs border-l-2 border-blue-300 pl-2">
                    <p className="font-medium">{e.event_type || "event"}</p>
                    <p className="text-gray-500">
                      {e.created_at ? new Date(e.created_at).toLocaleString() : ""}
                    </p>
                    {e.payload && Object.keys(e.payload).length > 0 && (
                      <pre className="text-[10px] bg-gray-50 p-1.5 rounded mt-1 overflow-auto">
                        {JSON.stringify(e.payload, null, 2)}
                      </pre>
                    )}
                  </li>
                ))}
              </ol>
            )}
          </div>

          <div className="border-t pt-3">
            <p className="text-xs font-medium text-gray-700 mb-2 flex items-center gap-1">
              <MessageCircle className="h-3.5 w-3.5" /> Conversations
            </p>
            {conversationsLoading ? (
              <p className="text-xs text-gray-400">Loading…</p>
            ) : conversations.length === 0 ? (
              <p className="text-xs text-gray-400">No conversations linked to this lead</p>
            ) : (
              <ul className="space-y-1">
                {conversations.map((c: any) => (
                  <li key={c.id} className="text-xs">
                    <a href={`/conversations/${c.id}`} className="text-blue-600 hover:underline">
                      {c.channel || "conversation"} • {c.id?.slice(0, 8)}
                    </a>
                    {c.last_message_at && (
                      <span className="text-gray-400 ml-1">
                        • {new Date(c.last_message_at).toLocaleDateString()}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
