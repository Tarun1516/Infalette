"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { adminApi } from "@/lib/api";

export default function ConversationsPage() {
  const [conversations, setConversations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [channel, setChannel] = useState("");
  const [status, setStatus] = useState("");

  const fetchConversations = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {};
      if (channel) params.channel = channel;
      if (status) params.status = status;
      const res: any = await adminApi.getConversations(Object.keys(params).length ? params : undefined);
      const list = Array.isArray(res) ? res : res.data || res.items || [];
      setConversations(list);
    } catch (e: any) {
      setError(e.message || "Failed to load conversations");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConversations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    fetchConversations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [channel, status]);

  return (
    <div>
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold">Conversations</h1>
          <p className="text-sm text-gray-500">{conversations.length} conversation(s) • unified inbox</p>
        </div>
        <div className="flex gap-2">
          <select value={channel} onChange={(e) => setChannel(e.target.value)} className="border rounded-lg px-3 py-2 text-sm bg-white">
            <option value="">All channels</option>
            <option value="instagram">Instagram</option>
            <option value="whatsapp">WhatsApp</option>
            <option value="website">Website</option>
          </select>
          <select value={status} onChange={(e) => setStatus(e.target.value)} className="border rounded-lg px-3 py-2 text-sm bg-white">
            <option value="">All statuses</option>
            <option value="open">Open</option>
            <option value="active">Active</option>
            <option value="closed">Closed</option>
          </select>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow border overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-gray-500">Loading conversations…</div>
        ) : error ? (
          <div className="p-8 text-center">
            <p className="text-red-600 text-sm">{error}</p>
            <button onClick={fetchConversations} className="mt-3 text-sm bg-gray-900 text-white px-4 py-2 rounded">
              Retry
            </button>
          </div>
        ) : conversations.length === 0 ? (
          <div className="p-12 text-center">
            <p className="text-gray-500">No conversations yet</p>
            <p className="text-xs text-gray-400 mt-1">Instagram comments, DMs and WhatsApp messages will appear here</p>
          </div>
        ) : (
          <div className="divide-y">
            {conversations.map((c) => (
              <Link key={c.id} href={`/conversations/${c.id}`} className="flex items-center justify-between p-4 hover:bg-gray-50">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-2 h-2 rounded-full ${
                      c.channel === "instagram" ? "bg-pink-500" : c.channel === "whatsapp" ? "bg-green-500" : "bg-blue-500"
                    }`}
                  />
                  <div>
                    <p className="font-medium text-sm">
                      {c.customer_name || c.customer?.first_name || "Unknown"} •{" "}
                      <span className="text-gray-500 font-normal">{c.channel || "website"}</span>
                    </p>
                    <p className="text-xs text-gray-400 truncate max-w-[420px]">{c.last_message || c.preview || "No messages yet"}</p>
                  </div>
                </div>
                <div className="text-right">
                  <span
                    className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                      c.status === "open" || c.status === "active" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {c.status || "open"}
                  </span>
                  <p className="text-xs text-gray-400 mt-1">{c.updated_at ? new Date(c.updated_at).toLocaleDateString() : ""}</p>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
