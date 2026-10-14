"use client";

import { toast } from "@/components/toaster";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { adminApi } from "@/lib/api";

export default function ConversationDetailPage() {
  const params = useParams();
  const conversationId = params.id as string;
  const [conversation, setConversation] = useState<any>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newMessage, setNewMessage] = useState("");
  const [sending, setSending] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const c = await adminApi.getConversation(conversationId);
      setConversation(c);
      // try to fetch messages via nested endpoint; fallback to conversation.messages
      let msgs: any[] = c.messages || [];
      try {
        const m = await adminApi.getConversationMessages(conversationId);
        if (Array.isArray(m)) msgs = m;
        else if ((m as any)?.data) msgs = (m as any).data;
      } catch {}
      setMessages(msgs);
    } catch (e: any) {
      setError(e.message || "Failed to load conversation");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId]);

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newMessage.trim()) return;
    setSending(true);
    try {
      await adminApi.sendMessage(conversationId, newMessage);
      setNewMessage("");
      fetchData();
    } catch (err: any) {
      toast({ kind: "error", title: "Something went wrong", description: err.message || "Failed to send" });
    } finally {
      setSending(false);
    }
  };

  if (loading) return <div className="p-8 text-center text-gray-500">Loading conversation…</div>;
  if (error) return <div className="p-8 text-center text-red-600 text-sm">{error}</div>;
  if (!conversation) return <div className="p-8 text-center text-gray-500">Conversation not found</div>;

  return (
    <div className="max-w-4xl space-y-4">
      <Link href="/conversations" className="text-sm text-gray-500 hover:underline">
        ← Back to inbox
      </Link>

      <div className="bg-white rounded-lg shadow border p-4 flex justify-between items-center">
        <div>
          <h1 className="font-bold">Conversation #{String(conversation.id).slice(0, 8)}</h1>
          <p className="text-xs text-gray-500">
            Channel: {conversation.channel} • Status: {conversation.status} • Customer: {conversation.customer_name || "Unknown"}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={async () => {
              const userId = prompt("Assign to user ID:");
              if (!userId) return;
              try {
                await adminApi.assignConversation(conversationId, userId);
                toast({ kind: "success", title: "Assigned" });
                fetchData();
              } catch (e: any) {
                toast({ kind: "error", title: "Something went wrong", description: e.message });
              }
            }}
            className="text-xs border px-3 py-1.5 rounded hover:bg-gray-50"
          >
            Assign
          </button>
          <button
            onClick={async () => {
              try {
                await adminApi.closeConversation(conversationId);
                toast({ kind: "success", title: "Closed" });
                fetchData();
              } catch (e: any) {
                toast({ kind: "error", title: "Something went wrong", description: e.message });
              }
            }}
            className="text-xs border px-3 py-1.5 rounded hover:bg-gray-50"
          >
            Close
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow border flex flex-col" style={{ minHeight: 380 }}>
        <div className="flex-1 p-4 space-y-3 overflow-y-auto max-h-[520px]">
          {messages.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-12">No messages yet</p>
          ) : (
            messages.map((m: any) => (
              <div
                key={m.id}
                className={`max-w-[75%] rounded-2xl px-4 py-2 text-sm ${
                  m.direction === "outbound" || m.from === "agent" ? "ml-auto bg-blue-600 text-white" : "bg-gray-100 text-gray-900"
                }`}
              >
                <p>{m.content || m.text || m.body}</p>
                <p className={`text-[10px] mt-1 ${m.direction === "outbound" ? "text-blue-100" : "text-gray-400"}`}>
                  {m.created_at ? new Date(m.created_at).toLocaleString() : ""}
                </p>
              </div>
            ))
          )}
        </div>

        <form onSubmit={sendMessage} className="border-t p-3 flex gap-2">
          <input
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            placeholder="Type a reply… (respects channel consent & 24h window)"
            className="flex-1 border rounded-full px-4 py-2 text-sm"
          />
          <button type="submit" disabled={sending || !newMessage.trim()} className="bg-blue-600 text-white px-5 py-2 rounded-full text-sm font-medium disabled:opacity-50">
            {sending ? "Sending…" : "Send"}
          </button>
        </form>
      </div>

      <div className="bg-white rounded-lg shadow border p-4">
        <h3 className="font-semibold text-sm mb-2">Context</h3>
        <div className="text-xs space-y-1">
          <p>
            <span className="text-gray-500">Lead:</span> {conversation.lead_id ? <Link href={`/leads/${conversation.lead_id}`} className="text-blue-600 hover:underline">{conversation.lead_id}</Link> : "—"}
          </p>
          <p>
            <span className="text-gray-500">External ID:</span> {conversation.external_id || "—"}
          </p>
          <p>
            <span className="text-gray-500">Attribution:</span> {JSON.stringify(conversation.attribution || {}, null, 2)}
          </p>
        </div>
      </div>
    </div>
  );
}
