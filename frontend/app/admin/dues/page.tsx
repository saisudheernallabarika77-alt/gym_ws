"use client";

import {
  AlertTriangle, Building2, Calendar, LayoutDashboard, MessageSquareWarning,
  Trash2, Users, Wallet,
} from "lucide-react";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { AppShell, PageHeader, type NavItem } from "@/components/AppShell";
import { Avatar, Button, Chip, EmptyState, Input, Modal, Textarea } from "@/components/ui";
import { adminApi, ApiError } from "@/lib/api";
import { formatDate, rupees } from "@/lib/utils";

const NAV: NavItem[] = [
  { href: "/admin/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/admin/users", label: "Users", icon: Users },
  { href: "/admin/gyms", label: "Gyms", icon: Building2 },
  { href: "/admin/dues", label: "Dues", icon: AlertTriangle },
  { href: "/admin/payouts", label: "Payouts", icon: Wallet },
  { href: "/admin/complaints", label: "Complaints", icon: MessageSquareWarning },
];

export default function AdminDuesPage() {
  const [data, setData] = useState<any>(null);
  const [graceTarget, setGraceTarget] = useState<any>(null);
  const [removeTarget, setRemoveTarget] = useState<any>(null);
  const [extraDays, setExtraDays] = useState(7);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  function load() {
    adminApi.dues().then(setData);
  }
  useEffect(load, []);

  async function extendGrace(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await adminApi.extendGrace(graceTarget.membership_id, extraDays, reason);
      toast.success(`Grace extended by ${extraDays} days`);
      setGraceTarget(null);
      setReason("");
      load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not extend grace");
    } finally {
      setBusy(false);
    }
  }

  async function removeMember(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await adminApi.removeMember(removeTarget.membership_id, reason);
      toast.success("Member removed");
      setRemoveTarget(null);
      setReason("");
      load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not remove member");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell role="admin" nav={NAV} loginPath="/admin/login" brandLabel="Admin">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        <PageHeader
          title="Dues across all gyms"
          subtitle={data ? `${data.total} pending · ${rupees(data.total_pending_amount)} total` : undefined}
        />

        {!data ? (
          <div className="skeleton h-64 w-full rounded-2xl" />
        ) : data.dues.length === 0 ? (
          <EmptyState icon={AlertTriangle} title="No pending dues" />
        ) : (
          <div className="space-y-3">
            {data.dues.map((d: any) => (
              <div key={d.membership_id} className="card p-4 flex items-center gap-3 flex-wrap">
                <Avatar name={d.user.name} src={d.user.photo_url} size={40} />
                <div className="flex-1 min-w-[180px]">
                  <p className="font-medium text-sm">{d.user.name}</p>
                  <p className="text-xs text-ink-500">{d.gym.name} · {d.gym.locality}</p>
                </div>
                <div className="text-right min-w-[110px]">
                  <p className="font-semibold text-sm">{rupees(d.amount)}</p>
                  <p className="text-xs text-ink-500">due {formatDate(d.due_date)}</p>
                </div>
                <Chip tone={d.state === "overdue" ? "danger" : "warning"}>
                  {d.state === "overdue" ? `${d.days_overdue}d overdue` : `${d.days_left_in_grace}d left`}
                </Chip>
                <div className="flex gap-1.5">
                  <Button size="sm" variant="secondary" icon={Calendar} onClick={() => setGraceTarget(d)}>
                    Extend grace
                  </Button>
                  <Button size="sm" variant="danger" icon={Trash2} onClick={() => setRemoveTarget(d)}>
                    Remove
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <Modal open={!!graceTarget} onClose={() => setGraceTarget(null)} title="Extend grace period">
        <form onSubmit={extendGrace} className="space-y-4">
          <p className="text-sm text-ink-400">
            For <span className="text-ink-200 font-medium">{graceTarget?.user.name}</span>
          </p>
          <Input label="Extra days" type="number" value={extraDays} onChange={(e) => setExtraDays(Number(e.target.value))} required />
          <Textarea placeholder="Reason (optional)" value={reason} onChange={(e) => setReason(e.target.value)} />
          <Button type="submit" loading={busy} className="w-full">Extend</Button>
        </form>
      </Modal>

      <Modal open={!!removeTarget} onClose={() => setRemoveTarget(null)} title="Remove member">
        <form onSubmit={removeMember} className="space-y-4">
          <p className="text-sm text-ink-400">
            This deactivates <span className="text-ink-200 font-medium">{removeTarget?.user.name}</span>'s
            entry pass for {removeTarget?.gym.name}. This cannot be undone.
          </p>
          <Textarea placeholder="Reason" value={reason} onChange={(e) => setReason(e.target.value)} required />
          <Button type="submit" loading={busy} variant="danger" className="w-full">Remove member</Button>
        </form>
      </Modal>
    </AppShell>
  );
}
