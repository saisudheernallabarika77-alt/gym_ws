"use client";

import {
  AlertTriangle, Building2, LayoutDashboard, Mail, MessageSquareWarning,
  Sparkles, Users, Wallet,
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

  // "Send Warning" modal state
  const [warnTarget, setWarnTarget] = useState<any>(null);
  const [warnPreview, setWarnPreview] = useState<any>(null);
  const [warnMessage, setWarnMessage] = useState("");
  const [warnUseAuto, setWarnUseAuto] = useState(true);
  const [warnNote, setWarnNote] = useState("");
  const [warnBusy, setWarnBusy] = useState(false);
  const [warnLoading, setWarnLoading] = useState(false);

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

  async function openWarn(c: any) {
    setWarnTarget(c);
    setWarnLoading(true);
    setWarnUseAuto(true);
    setWarnNote("");
    try {
      const preview = await adminApi.warningPreview(c.id);
      setWarnPreview(preview);
      setWarnMessage(preview.auto_message);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not load warning preview");
      setWarnTarget(null);
    } finally {
      setWarnLoading(false);
    }
  }

  async function submitWarning(e: React.FormEvent) {
    e.preventDefault();
    setWarnBusy(true);
    try {
      // Auto mode sends the template as-is (null tells the backend to use
      // its own default); typed mode sends exactly what's in the textarea.
      const res = await adminApi.sendWarning(
        warnTarget.id,
        warnUseAuto ? null : warnMessage,
        warnNote || undefined,
      );
      toast.success(`Warning sent to ${res.recipient}`);
      setWarnTarget(null);
      setWarnPreview(null);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not send warning");
    } finally {
      setWarnBusy(false);
    }
  }

  return (
    <AppShell role="admin" nav={NAV} loginPath="/admin/login" brandLabel="Admin">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8">
        <PageHeader
          title="Complaints"
          subtitle="Raised by gym owners about members, and by members about gyms"
        />

        {complaints.length === 0 ? (
          <EmptyState icon={MessageSquareWarning} title="No complaints" />
        ) : (
          <div className="space-y-3">
            {complaints.map((c) => (
              <div key={c.id} className="card p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-sm">{c.subject}</p>
                      <Chip tone={c.direction === "owner_to_admin" ? "warning" : "brand"} className="text-[10px]">
                        {c.direction === "owner_to_admin" ? "Owner → Admin" : "Member → Admin"}
                      </Chip>
                    </div>
                    <p className="text-xs text-ink-500 mt-1">
                      {c.direction === "owner_to_admin" ? (
                        <>
                          {c.gym?.name} · against {c.against_user?.name ?? "unknown member"}
                        </>
                      ) : (
                        <>
                          about {c.gym?.name ?? "unknown gym"} · reported by {c.raised_by?.name}
                        </>
                      )}
                      {" · "}{formatDate(c.created_at)}
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
                <div className="flex gap-2 mt-3">
                  <Button size="sm" variant="secondary" icon={Mail} onClick={() => openWarn(c)}>
                    Send warning
                  </Button>
                  {c.status === "open" && (
                    <Button size="sm" variant="secondary" onClick={() => setTarget(c)}>
                      Take action
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* -------------------------------------------------- resolve modal */}
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

      {/* -------------------------------------------------- warning modal */}
      <Modal open={!!warnTarget} onClose={() => setWarnTarget(null)} title="Send warning email" wide>
        {warnLoading ? (
          <div className="skeleton h-40 w-full rounded-xl" />
        ) : warnPreview && !warnPreview.can_send ? (
          <p className="text-sm text-danger">
            Could not identify who to warn for this complaint (the target account
            may have been removed).
          </p>
        ) : (
          <form onSubmit={submitWarning} className="space-y-4">
            <div className="card p-3.5 bg-ink-800/50">
              <p className="text-xs text-ink-500">Sending to</p>
              <p className="text-sm font-medium mt-0.5">
                {warnPreview?.recipient?.name}{" "}
                <span className="text-ink-500 font-normal">
                  ({warnPreview?.recipient?.kind === "gym_owner" ? "gym owner" : "member"}
                  {warnPreview?.recipient?.gym_name ? ` · ${warnPreview.recipient.gym_name}` : ""})
                </span>
              </p>
              <p className="text-xs text-ink-500">{warnPreview?.recipient?.email}</p>
            </div>

            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  setWarnUseAuto(true);
                  setWarnMessage(warnPreview?.auto_message ?? "");
                }}
                className={`chip flex-1 justify-center ${warnUseAuto ? "bg-brand-500/15 text-brand-300 border-brand-500/40" : "chip-muted"}`}
              >
                <Sparkles className="w-3 h-3" /> Auto-generated
              </button>
              <button
                type="button"
                onClick={() => setWarnUseAuto(false)}
                className={`chip flex-1 justify-center ${!warnUseAuto ? "bg-brand-500/15 text-brand-300 border-brand-500/40" : "chip-muted"}`}
              >
                Type my own
              </button>
            </div>

            <Textarea
              label={warnUseAuto ? "Message (auto-generated — you can still edit it)" : "Your message"}
              value={warnMessage}
              onChange={(e) => setWarnMessage(e.target.value)}
              rows={5}
              required
            />
            <Textarea
              label="Internal admin note (optional, included in the email as a signed note)"
              value={warnNote}
              onChange={(e) => setWarnNote(e.target.value)}
            />

            <Button type="submit" loading={warnBusy} icon={Mail} className="w-full">
              Send warning email
            </Button>
          </form>
        )}
      </Modal>
    </AppShell>
  );
}
