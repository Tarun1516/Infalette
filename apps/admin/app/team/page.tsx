"use client";

import { useEffect, useState } from "react";
import { adminApiExt } from "@/lib/api";
import { toast } from "@/components/toaster";
import { Dialog } from "@/components/dialog";

/**
 * Team management.
 *
 * Lists every member of the current tenant. The "Add member" button
 * opens a small dialog that captures name, email, role, MFA, and
 * status. Admin accounts MUST have MFA enabled — the dialog disables
 * the uncheck and shows a hint, and the backend rejects the request
 * if the box is left unticked.
 */
export default function TeamPage() {
  const [users, setUsers] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    email: "",
    role: "store_manager",
    password: "",
    mfa_required: true,
    status: "active",
  });

  async function load() {
    setError("");
    setLoading(true);
    try {
      const data = await adminApiExt.getUsers();
      setUsers(Array.isArray(data) ? data : []);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  function resetForm() {
    setForm({
      first_name: "",
      last_name: "",
      email: "",
      role: "store_manager",
      password: "",
      mfa_required: true,
      status: "active",
    });
  }

  function openDialog() {
    resetForm();
    setDialogOpen(true);
  }

  function closeDialog() {
    if (submitting) return;
    setDialogOpen(false);
  }

  // Role change — admin forces MFA on (and locks the box); other roles
  // let the caller decide.
  function updateRole(role: string) {
    setForm((prev) => ({
      ...prev,
      role,
      mfa_required: role === "admin" ? true : prev.mfa_required,
    }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (form.role === "admin" && !form.mfa_required) {
      toast({
        kind: "error",
        title: "MFA required",
        description: "Admin accounts must have MFA enabled. Tick the MFA box to continue.",
      });
      return;
    }
    setSubmitting(true);
    try {
      await adminApiExt.createUser({
        first_name: form.first_name,
        last_name: form.last_name,
        email: form.email,
        role: form.role,
        password: form.password,
        mfa_required: form.mfa_required,
        status: form.status,
      });
      toast({
        kind: "success",
        title: "Member added",
        description: `${form.first_name} ${form.last_name} can now sign in.`,
      });
      setDialogOpen(false);
      resetForm();
      await load();
    } catch (e: any) {
      toast({
        kind: "error",
        title: "Could not add member",
        description: e?.message || "Please try again",
      });
    } finally {
      setSubmitting(false);
    }
  }

  const mfaHint =
    form.role === "admin"
      ? "Admins must complete MFA enrollment on first login before they can access the admin app."
      : "When MFA is required, the new user will be prompted to enroll on first login.";

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <p className="text-[12px] uppercase tracking-[0.18em] text-gray-500 dark:text-neutral-500">
            People
          </p>
          <h1 className="mt-2 text-[36px] sm:text-[44px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
            Team
          </h1>
          <p className="mt-1 text-[13px] text-gray-500 dark:text-neutral-500">
            Everyone with access to this tenant. Admins can sign in to the
            admin app once MFA is enrolled.
          </p>
        </div>
        <button
          type="button"
          onClick={openDialog}
          className="inline-flex h-10 px-5 items-center justify-center rounded-full bg-blue-600 text-white text-[14px] font-medium hover:bg-blue-700 transition-colors"
        >
          Add member
        </button>
      </div>

      {error && (
        <div className="rounded-2xl border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-900/10 px-4 py-3 text-[13px] text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      {loading ? (
        <div className="rounded-2xl border border-gray-100 dark:border-neutral-900 bg-white dark:bg-neutral-950 p-12 text-center text-[13px] text-gray-500 dark:text-neutral-500">
          Loading…
        </div>
      ) : users.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-gray-300 dark:border-neutral-800 py-16 px-6 text-center bg-white dark:bg-neutral-950">
          <p className="text-[15px] text-gray-700 dark:text-neutral-300">No team members yet.</p>
          <p className="mt-1 text-[13px] text-gray-500 dark:text-neutral-500">
            Click <span className="font-medium">Add member</span> to invite the first person.
          </p>
        </div>
      ) : (
        <div className="rounded-2xl bg-white dark:bg-neutral-950 border border-gray-100 dark:border-neutral-900 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead className="bg-gray-50 dark:bg-neutral-900 text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500">
                <tr>
                  <th className="text-left px-5 py-3 font-medium">Name</th>
                  <th className="text-left px-5 py-3 font-medium">Email</th>
                  <th className="text-left px-5 py-3 font-medium">Role</th>
                  <th className="text-left px-5 py-3 font-medium">MFA</th>
                  <th className="text-left px-5 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-t border-gray-100 dark:border-neutral-900">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        <div className="h-9 w-9 rounded-full bg-gradient-to-br from-blue-500 to-violet-500 flex items-center justify-center text-white text-[12px] font-semibold">
                          {String(u.first_name || u.email || "?").slice(0, 1).toUpperCase()}
                        </div>
                        <div>
                          <p className="font-medium text-gray-900 dark:text-neutral-100">
                            {[u.first_name, u.last_name].filter(Boolean).join(" ") || "—"}
                          </p>
                          <p className="text-[11px] text-gray-500 dark:text-neutral-500">
                            Joined {u.created_at ? new Date(u.created_at).toLocaleDateString() : "—"}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3 text-gray-700 dark:text-neutral-300 font-mono text-[12px]">{u.email}</td>
                    <td className="px-5 py-3">
                      <span
                        className={`inline-flex px-2 py-0.5 rounded-full text-[11px] font-medium ${
                          u.role === "admin" || u.role === "tenant_owner"
                            ? "bg-violet-50 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300"
                            : "bg-gray-100 dark:bg-neutral-900 text-gray-700 dark:text-neutral-300"
                        } capitalize`}
                      >
                        {String(u.role || "—").replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      {u.mfa_enabled ? (
                        <span className="inline-flex items-center gap-1 text-emerald-700 dark:text-emerald-300 text-[12px]">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5">
                            <polyline points="20 6 9 17 4 12" />
                          </svg>
                          Enabled
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-amber-700 dark:text-amber-300 text-[12px]">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5">
                            <circle cx="12" cy="12" r="10" />
                            <line x1="12" y1="8" x2="12" y2="12" />
                            <line x1="12" y1="16" x2="12.01" y2="16" />
                          </svg>
                          Pending
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`inline-flex px-2 py-0.5 rounded-full text-[11px] font-medium capitalize ${
                          u.status === "active"
                            ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300"
                            : u.status === "invited"
                            ? "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300"
                            : "bg-gray-100 dark:bg-neutral-900 text-gray-700 dark:text-neutral-300"
                        }`}
                      >
                        {u.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <Dialog
        open={dialogOpen}
        onClose={closeDialog}
        title="Add a team member"
        description="They'll receive the new password by your preferred channel and can sign in immediately."
        size="md"
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="block text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500 mb-1">
                First name *
              </span>
              <input
                required
                value={form.first_name}
                onChange={(e) => setForm({ ...form, first_name: e.target.value })}
                placeholder="Ada"
                className="h-10 w-full rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 text-[13px]"
              />
            </label>
            <label className="block">
              <span className="block text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500 mb-1">
                Last name *
              </span>
              <input
                required
                value={form.last_name}
                onChange={(e) => setForm({ ...form, last_name: e.target.value })}
                placeholder="Lovelace"
                className="h-10 w-full rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 text-[13px]"
              />
            </label>
          </div>
          <label className="block">
            <span className="block text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500 mb-1">
              Email *
            </span>
            <input
              type="email"
              required
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              placeholder="ada@infalette.com"
              className="h-10 w-full rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 text-[13px]"
            />
          </label>
          <label className="block">
            <span className="block text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500 mb-1">
              Initial password *
            </span>
            <input
              type="password"
              required
              minLength={8}
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              placeholder="At least 8 characters"
              className="h-10 w-full rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 text-[13px]"
            />
            <p className="mt-1 text-[11px] text-gray-500 dark:text-neutral-500">
              The user can change this after first login.
            </p>
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="block text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500 mb-1">
                Role *
              </span>
              <select
                value={form.role}
                onChange={(e) => updateRole(e.target.value)}
                className="h-10 w-full rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 text-[13px]"
              >
                <option value="store_manager">Store manager</option>
                <option value="tenant_owner">Tenant owner</option>
                <option value="admin">Admin</option>
                <option value="customer">Customer</option>
              </select>
            </label>
            <label className="block">
              <span className="block text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500 mb-1">
                Status
              </span>
              <select
                value={form.status}
                onChange={(e) => setForm({ ...form, status: e.target.value })}
                className="h-10 w-full rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 text-[13px]"
              >
                <option value="active">Active</option>
                <option value="invited">Invited</option>
                <option value="suspended">Suspended</option>
              </select>
            </label>
          </div>
          <label
            className={`flex items-start gap-3 p-3 rounded-2xl border ${
              form.role === "admin"
                ? "border-violet-200 dark:border-violet-900 bg-violet-50/50 dark:bg-violet-900/10"
                : "border-gray-100 dark:border-neutral-900 bg-gray-50/50 dark:bg-neutral-950"
            }`}
          >
            <input
              type="checkbox"
              checked={form.mfa_required}
              onChange={(e) => {
                if (form.role === "admin" && !e.target.checked) return;
                setForm({ ...form, mfa_required: e.target.checked });
              }}
              disabled={form.role === "admin"}
              className="mt-1 h-4 w-4 rounded border-gray-300 text-gray-900 focus:ring-gray-900 disabled:opacity-60"
            />
            <div>
              <p className="text-[13px] font-medium text-gray-900 dark:text-neutral-100">
                MFA required
                {form.role === "admin" && (
                  <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300">
                    Compulsory for admin
                  </span>
                )}
              </p>
              <p className="text-[12px] text-gray-500 dark:text-neutral-500 mt-0.5">{mfaHint}</p>
            </div>
          </label>

          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={closeDialog}
              disabled={submitting}
              className="inline-flex h-10 px-4 items-center justify-center rounded-full border border-gray-200 dark:border-neutral-800 text-[13px] font-medium text-gray-700 dark:text-neutral-300 hover:bg-gray-50 dark:hover:bg-neutral-900 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex h-10 px-5 items-center justify-center rounded-full bg-blue-600 text-white text-[13px] font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {submitting ? "Adding…" : "Add member"}
            </button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}