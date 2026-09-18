"use client";

import {
  AlertTriangle, Building2, LayoutDashboard, MessageSquareWarning, Users, Wallet,
} from "lucide-react";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { AppShell, PageHeader, type NavItem } from "@/components/AppShell";
import { Button, Chip, EmptyState, Modal, Textarea } from "@/components/ui";
import { adminApi, ApiError } from "@/lib/api";
import { formatDate } from "@/lib/utils";

const NAV: NavItem[] = [
  { href: "/admin/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/admin/users", label: "Users", icon: Users },
  { href: "/admin/gyms", label: "Gyms", icon: Building2 },
  { href: "/admin/dues", label: "Dues", icon: AlertTriangle },
  { href: "/admin/payouts", label: "Payouts", icon: Wallet },
  { href: "/admin/complaints", label: "Complaints", icon: MessageSquareWarning },
];

export default function AdminComplaintsPage() {
  const [complaints, setComplaints] = useState<any[]>([]);
  const [target, setTarget] = useState<any>(null);
  const [action, setAction] = useState<"resolved" | "dismissed" | "reviewing">("resolved");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  function load() {
    adminApi.complaints().then((r) => setComplaints(r.complaints));
  }
  useEffect(load, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await adminApi.actOnComplaint(target.id, action, note);
      toast.success("Complaint updated");
      setTarget(null);
      setNote("");
      load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not update");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell role="admin" nav={NAV} loginPath="/admin/login" brandLabel="Admin">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8">
        <PageHeader title="Complaints" subtitle="Raised by gym owners about members" />

        {complaints.length === 0 ? (
          <EmptyState icon={MessageSquareWarning} title="No complaints" />
        ) : (
          <div className="space-y-3">
            {complaints.map((c) => (
              <div key={c.id} className="card p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-sm">{c.subject}</p>
                    <p className="text-xs text-ink-500 mt-1">
                      {c.gym?.name} · against {c.against_user?.name} · {formatDate(c.created_at)}
                    </p>
                    {c.details && <p className="text-sm text-ink-400 mt-2">{c.details}</p>}
                    {c.admin_action && (
                      <p className="text-xs text-brand-400 mt-2">Admin: {c.admin_action}</p>
                    )}
                  </div>
                  <Chip tone={c.status === "open" ? "warning" : c.status === "resolved" ? "success" : "muted"}>
                    {c.status}
                  </Chip>
                </div>
                {c.status === "open" && (
                  <Button size="sm" variant="secondary" className="mt-3" onClick={() => setTarget(c)}>
                    Take action
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <Modal open={!!target} onClose={() => setTarget(null)} title="Resolve complaint">
        <form onSubmit={submit} className="space-y-4">
          <div className="flex gap-2">
            {(["resolved", "reviewing", "dismissed"] as const).map((a) => (
              <button
                key={a}
                type="button"
                onClick={() => setAction(a)}
                className={`chip ${action === a ? "bg-brand-500/15 text-brand-300 border-brand-500/40" : "chip-muted"}`}
              >
                {a}
              </button>
            ))}
          </div>
          <Textarea placeholder="What action did you take?" value={note} onChange={(e) => setNote(e.target.value)} required />
          <Button type="submit" loading={busy} className="w-full">Save</Button>
        </form>
      </Modal>
    </AppShell>
  );
}
