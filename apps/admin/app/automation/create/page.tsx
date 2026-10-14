"use client";

import { toast } from "@/components/toaster";

import { useState } from "react";
import { adminApi } from "@/lib/api";

export default function CreateAutomationRulePage() {
  const [formData, setFormData] = useState({
    name: "",
    trigger_type: "comment_keyword",
    conditions: {} as Record<string, any>,
    actions: [] as any[],
    status: "draft",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await adminApi.createAutomationRule(formData);
      window.location.href = "/automation";
    } catch (error) {
      toast({ kind: "error", title: "Failed to create rule" });
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Create Automation Rule</h1>
      <form onSubmit={handleSubmit} className="space-y-4 bg-white p-6 rounded shadow">
        <input
          type="text"
          placeholder="Rule Name"
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          className="w-full p-3 border rounded"
          required
        />
        <select
          value={formData.trigger_type}
          onChange={(e) => setFormData({ ...formData, trigger_type: e.target.value })}
          className="w-full p-3 border rounded"
        >
          <option value="comment_keyword">Comment Keyword</option>
          <option value="dm_product_sku">DM Product SKU</option>
          <option value="story_response">Story Response</option>
          <option value="whatsapp_flow">WhatsApp Flow</option>
          <option value="checkout_unpaid">Checkout Unpaid</option>
        </select>
        <select
          value={formData.status}
          onChange={(e) => setFormData({ ...formData, status: e.target.value })}
          className="w-full p-3 border rounded"
        >
          <option value="draft">Draft</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
        <button type="submit" className="bg-blue-600 text-white px-6 py-3 rounded-lg">Create Rule</button>
      </form>
    </div>
  );
}
