"use client";

import { toast } from "@/components/toaster";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Mail, Phone, Calendar, Save, RefreshCw, MessageCircle } from "lucide-react";
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

const STAGE_LABELS: Record<(typeof STAGES)[number], string> = {
  new_lead: "New Lead",
  engaged: "Engaged",
  product_selected: "Product Selected",
  checkout_created: "Checkout Created",
  paid: "Paid",
  fulfilled: "Fulfilled",
  repeat_customer: "Repeat Customer",
};

export default function LeadDetailPage() {
  const params = useParams();
  const router = useRouter();
  const leadId = params.id as string;

  const [lead, setLead] = useState<any>(null);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [conversations, setConversations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [notes, setNotes] = useState("");
  const [score, setScore] = useState(0);

  const fetchAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const [l, tl, convs]: any[] = await Promise.all([
        adminApi.getLead(leadId),
        adminApi.getLeadTimeline(leadId).catch(() => []),
        adminApi.getConversations().catch(() => null),
      ]);
      setLead(l);
      setTimeline(Array.isArray(tl) ? tl : []);
      const convList: any[] = Array.isArray(convs) ? convs : convs?.data || convs?.items || [];
      setConversations(convList.filter((c: any) => c.lead_id === leadId));
      setNotes(l?.metadata_json?.notes || l?.notes || "");
      setScore(l?.score || 0);
    } catch (e: any) {
      setError(e.message || "Failed to load lead");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (leadId) fetchAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [leadId]);

  const handleStage = async (s: string) => {
    if (!lead) return;
    try {
      await adminApi.updateLeadStage(lead.id, s);
      setLead({ ...lead, status: s, stage: s });
    } catch (e: any) {
      toast({ kind: "error", title: "Something went wrong", description: e.message || "Failed" });
    }
  };

  const handleSave = async () => {
    if (!lead) return;
    setSaving(true);
    try {
      const updated = await adminApi.updateLead(lead.id, {
        score,
        metadata_json: { ...(lead.metadata_json || {}), notes },
      });
      setLead(updated);
    } catch (e: any) {
      toast({ kind: "error", title: "Something went wrong", description: e.message || "Save failed" });
    } finally {
      setSaving(false);
    }
  };

  const handleConvert = async () => {
    if (!lead) return;
    if (!confirm("Convert this lead to a customer?")) return;
    try {
      const res = await adminApi.convertLead(lead.id);
      toast({ kind: "success", title: "Converted. New customer id: \" + (res?.customer_id || \"—" }));
      router.push("/leads");
    } catch (e: any) {
      toast({ kind: "error", title: "Something went wrong", description: e.message || "Convert failed" });
    }
  };

  if (loading) {
    return <div className="p-12 text-center text-gray-500">Loading lead…</div>;
  }
  if (error) {
    return (
      <div className="p-8 text-center">
        <p className="text-red-600 text-sm">{error}</p>
        <button
          onClick={() => router.push("/leads")}
          className="mt-3 text-sm border px-4 py-2 rounded"
        >
          Back to leads
        </button>
      </div>
    );
  }
  if (!lead) return null;

  const name = [lead.first_name, lead.last_name].filter(Boolean).join(" ") || lead.email || "Unnamed";

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <Link href="/leads" className="hover:underline flex items-center gap-1">
          <ArrowLeft className="h-3.5 w-3.5" /> Leads
        </Link>
        <span>›</span>
        <span className="font-medium text-gray-700">{name}</span>
      </div>

      <div className="flex flex-col sm:flex-row justify-between gap-3 sm:items-center">
        <div>
          <h1 className="text-2xl font-bold">{name}</h1>
          <p className="text-xs text-gray-500 font-mono mt-1">id: {lead.id}</p>
        </div>
        <button
          onClick={handleConvert}
          className="px-4 py-2 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700"
        >
          Convert to customer
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl border shadow-sm p-5 space-y-3">
          <h3 className="font-semibold">Profile</h3>
          <div className="space-y-2 text-sm">
            {lead.email && (
              <div className="flex items-center gap-2 text-gray-700">
                <Mail className="h-4 w-4 text-gray-400" />
                <a href={`mailto:${lead.email}`} className="hover:underline">{lead.email}</a>
              </div>
            )}
            {lead.phone && (
              <div className="flex items-center gap-2 text-gray-700">
                <Phone className="h-4 w-4 text-gray-400" />
                <a href={`tel:${lead.phone}`} className="hover:underline">{lead.phone}</a>
              </div>
            )}
            <div className="flex items-center gap-2 text-gray-700">
              <Calendar className="h-4 w-4 text-gray-400" />
              <span>Created {lead.created_at ? new Date(lead.created_at).toLocaleString() : "—"}</span>
            </div>
            <p className="text-xs text-gray-500">Source: {lead.source || "—"}</p>
            <p className="text-xs text-gray-500">Assigned: {lead.assigned_to || "Unassigned"}</p>
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
        </div>

        <div className="bg-white rounded-2xl border shadow-sm p-5 space-y-3">
          <h3 className="font-semibold">Stage</h3>
          <div className="flex flex-wrap gap-1">
            {STAGES.map((s) => {
              const active = (lead.status || lead.stage) === s;
              return (
                <button
                  key={s}
                  onClick={() => handleStage(s)}
                  className={`text-xs px-2 py-1 rounded-full border ${
                    active ? "bg-blue-600 text-white border-blue-600" : "bg-white hover:bg-gray-50"
                  }`}
                >
                  {STAGE_LABELS[s]}
                </button>
              );
            })}
          </div>
          <div>
            <label className="text-xs font-medium text-gray-700 block mb-1 mt-3">Score</label>
            <input
              type="number"
              value={score}
              onChange={(e) => setScore(parseInt(e.target.value) || 0)}
              className="w-24 border rounded px-2 py-1 text-sm"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-700 block mb-1">Notes</label>
            <textarea
              rows={4}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full border rounded-lg px-3 py-2 text-sm"
              placeholder="Free-form notes about this lead…"
            />
          </div>
          <button
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            <Save className="h-4 w-4" /> {saving ? "Saving…" : "Save notes & score"}
          </button>
        </div>
      </div>

      <div className="bg-white rounded-2xl border shadow-sm p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold">Timeline</h3>
          <button
            onClick={fetchAll}
            className="inline-flex items-center gap-1 text-xs border px-2 py-1 rounded hover:bg-gray-50"
          >
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </button>
        </div>
        {timeline.length === 0 ? (
          <p className="text-sm text-gray-400">No events yet for this lead</p>
        ) : (
          <ol className="space-y-3">
            {timeline.map((e: any) => (
              <li key={e.id} className="text-sm border-l-2 border-blue-300 pl-3">
                <p className="font-medium">{e.event_type || "event"}</p>
                <p className="text-xs text-gray-500">
                  {e.created_at ? new Date(e.created_at).toLocaleString() : ""}
                </p>
                {e.payload && Object.keys(e.payload).length > 0 && (
                  <pre className="text-[11px] bg-gray-50 p-2 rounded mt-1 overflow-auto">
                    {JSON.stringify(e.payload, null, 2)}
                  </pre>
                )}
              </li>
            ))}
          </ol>
        )}
      </div>

      <div className="bg-white rounded-2xl border shadow-sm p-5">
        <h3 className="font-semibold mb-3 flex items-center gap-1">
          <MessageCircle className="h-4 w-4" /> Conversations
        </h3>
        {conversations.length === 0 ? (
          <p className="text-sm text-gray-400">No conversations linked to this lead</p>
        ) : (
          <ul className="space-y-2">
            {conversations.map((c: any) => (
              <li key={c.id} className="text-sm border rounded p-2 flex justify-between">
                <a href={`/conversations/${c.id}`} className="text-blue-600 hover:underline">
                  {c.channel || "conversation"} • {c.id?.slice(0, 8)}
                </a>
                <span className="text-xs text-gray-500">
                  {c.last_message_at ? new Date(c.last_message_at).toLocaleString() : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
