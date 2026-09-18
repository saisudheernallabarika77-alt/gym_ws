"use client";

import {
  AlertTriangle, Building2, LayoutDashboard, MessageSquareWarning,
  Search, Shield, ShieldOff, Trash2, Users, Wallet,
} from "lucide-react";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { AppShell, PageHeader, type NavItem } from "@/components/AppShell";
import { Avatar, Button, Chip, EmptyState, Modal, Textarea } from "@/components/ui";
import { adminApi, ApiError } from "@/lib/api";
import { rupees, STATUS_TONE } from "@/lib/utils";

const NAV: NavItem[] = [
  { href: "/admin/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/admin/users", label: "Users", icon: Users },
  { href: "/admin/gyms", label: "Gyms", icon: Building2 },
  { href: "/admin/dues", label: "Dues", icon: AlertTriangle },
  { href: "/admin/payouts", label: "Payouts", icon: Wallet },
  { href: "/admin/complaints", label: "Complaints", icon: MessageSquareWarning },
];

export default function AdminUsersPage() {
  const [users, setUsers] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [blockTarget, setBlockTarget] = useState<any>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  function load() {
    setLoading(true);
    adminApi.users({ q: q || undefined, page_size: 50 })
      .then((r) => { setUsers(r.users); setTotal(r.total); })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    const t = setTimeout(load, 300);
    return () => clearTimeout(t);
  }, [q]);

  async function block(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await adminApi.blockUser(blockTarget.id, reason);
      toast.success(`${blockTarget.full_name} blocked`);
      setBlockTarget(null);
      setReason("");
      load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not block");
    } finally {
      setBusy(false);
    }
  }

  async function unblock(u: any) {
    try {
      await adminApi.unblockUser(u.id);
      toast.success(`${u.full_name} unblocked`);
      load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not unblock");
    }
  }

  async function remove(u: any) {
    if (!confirm(`Delete ${u.full_name}'s account? This cannot be undone.`)) return;
    try {
      await adminApi.deleteUser(u.id);
      toast.success("User deleted");
      load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not delete");
    }
  }

  return (
    <AppShell role="admin" nav={NAV} loginPath="/admin/login" brandLabel="Admin">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        <PageHeader title="Users" subtitle={`${total} registered`} />

        <div className="relative mb-5 max-w-sm">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-500" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, email or phone" className="input pl-10" />
        </div>

        {loading ? (
          <div className="skeleton h-64 w-full rounded-2xl" />
        ) : users.length === 0 ? (
          <EmptyState icon={Users} title="No users found" />
        ) : (
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-ink-800 text-left text-xs text-ink-500">
                    <th className="p-4">User</th>
                    <th className="p-4">Memberships</th>
                    <th className="p-4">Spent</th>
                    <th className="p-4">Status</th>
                    <th className="p-4"></th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id} className="border-b border-ink-800/60 last:border-0">
                      <td className="p-4">
                        <div className="flex items-center gap-2.5">
                          <Avatar name={u.full_name} src={u.photo_url} size={32} />
                          <div>
                            <p className="font-medium">{u.full_name}</p>
                            <p className="text-xs text-ink-500">{u.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="p-4 text-ink-300">
                        {u.active_memberships} active
                        {u.overdue_memberships > 0 && (
                          <span className="text-danger"> · {u.overdue_memberships} overdue</span>
                        )}
                      </td>
                      <td className="p-4 font-medium">{rupees(u.total_spent)}</td>
                      <td className="p-4">
                        <Chip tone={(STATUS_TONE[u.status]?.replace("chip-", "") as any) ?? "muted"}>
                          {u.status.replace("_", " ")}
                        </Chip>
                      </td>
                      <td className="p-4">
                        <div className="flex items-center gap-1.5 justify-end">
                          {u.status === "blocked" ? (
                            <Button size="sm" variant="secondary" icon={Shield} onClick={() => unblock(u)}>
                              Unblock
                            </Button>
                          ) : (
                            <Button size="sm" variant="secondary" icon={ShieldOff} onClick={() => setBlockTarget(u)}>
                              Block
                            </Button>
                          )}
                          <button onClick={() => remove(u)} className="text-ink-600 hover:text-danger p-2">
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      <Modal open={!!blockTarget} onClose={() => setBlockTarget(null)} title="Block user">
        <form onSubmit={block} className="space-y-4">
          <p className="text-sm text-ink-400">
            Blocking <span className="text-ink-200 font-medium">{blockTarget?.full_name}</span> disables
            their login and deactivates their entry passes.
          </p>
          <Textarea placeholder="Reason for blocking" value={reason} onChange={(e) => setReason(e.target.value)} required />
          <Button type="submit" loading={busy} variant="danger" className="w-full">Block user</Button>
        </form>
      </Modal>
    </AppShell>
  );
}
