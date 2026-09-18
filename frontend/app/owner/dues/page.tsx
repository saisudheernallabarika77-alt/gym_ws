"use client";

import {
  AlertTriangle, CreditCard, Dumbbell, LayoutDashboard, MessageSquareWarning,
  Shield, Star, Users, Wallet,
} from "lucide-react";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { AppShell, PageHeader, type NavItem } from "@/components/AppShell";
import { Avatar, Banner, Button, Chip, EmptyState, Modal, Textarea } from "@/components/ui";
import { ownerApi, ApiError } from "@/lib/api";
import { formatDate, rupees } from "@/lib/utils";

const NAV: NavItem[] = [
  { href: "/owner/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/owner/equipment", label: "Equipment", icon: Dumbbell },
  { href: "/owner/coaches", label: "Coaches", icon: Users },
  { href: "/owner/members", label: "Members", icon: Users },
  { href: "/owner/dues", label: "Dues", icon: AlertTriangle },
  { href: "/owner/earnings", label: "Earnings", icon: Wallet },
  { href: "/owner/reviews", label: "Reviews", icon: Star },
];

export default function OwnerDuesPage() {
  const [data, setData] = useState<any>(null);
  const [complaintTarget, setComplaintTarget] = useState<any>(null);
  const [subject, setSubject] = useState("");
  const [details, setDetails] = useState("");
  const [busy, setBusy] = useState(false);

  function load() {
    ownerApi.dues().then(setData);
  }
  useEffect(load, []);

  async function submitComplaint(e: React.FormEvent) {
    e.preventDefault();
    if (!complaintTarget) return;
    setBusy(true);
    try {
      await ownerApi.raiseComplaint({
        against_user_id: complaintTarget.user.id,
        membership_id: complaintTarget.membership_id,
        category: "payment_default",
        subject,
        details,
      });
      toast.success("Complaint sent to the admin");
      setComplaintTarget(null);
      setSubject("");
      setDetails("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not send complaint");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell role="gym_owner" nav={NAV} loginPath="/owner/login" brandLabel="Partner Portal">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8">
        <PageHeader
          title="Dues"
          subtitle={data ? `${data.summary.overdue_members} overdue · ${rupees(data.summary.pending_amount)} pending` : undefined}
        />

        <Banner tone="info">
          <Shield className="w-4 h-4 inline mr-1.5" />
          {data?.permissions.note ?? "You can view dues and raise a complaint. Only the admin can extend grace periods or remove a member."}
        </Banner>

        <div className="mt-6">
          {!data ? (
            <div className="skeleton h-64 w-full rounded-2xl" />
          ) : data.dues.length === 0 ? (
            <EmptyState icon={AlertTriangle} title="No pending dues" description="Everyone is paid up." />
          ) : (
            <div className="space-y-3">
              {data.dues.map((d: any) => (
                <div key={d.membership_id} className="card p-4 flex items-center gap-3">
                  <Avatar name={d.user.name} src={d.user.photo_url} size={40} />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm">{d.user.name}</p>
                    <p className="text-xs text-ink-500">
                      {rupees(d.amount)} · due {formatDate(d.due_date)} · grace ends {formatDate(d.grace_ends_on)}
                    </p>
                  </div>
                  <Chip tone={d.state === "overdue" ? "danger" : "warning"}>
                    {d.state === "overdue" ? `${d.days_overdue}d overdue` : `${d.days_left_in_grace}d left`}
                  </Chip>
                  <Button
                    size="sm"
                    variant="secondary"
                    icon={MessageSquareWarning}
                    onClick={() => setComplaintTarget(d)}
                  >
                    Report
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <Modal open={!!complaintTarget} onClose={() => setComplaintTarget(null)} title="Report to admin">
        <form onSubmit={submitComplaint} className="space-y-4">
          <p className="text-sm text-ink-400">
            About <span className="font-medium text-ink-200">{complaintTarget?.user.name}</span>
          </p>
          <input
            className="input"
            placeholder="Subject"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            required
          />
          <Textarea
            placeholder="Details (optional)"
            value={details}
            onChange={(e) => setDetails(e.target.value)}
          />
          <Button type="submit" loading={busy} className="w-full">Send to admin</Button>
        </form>
      </Modal>
    </AppShell>
  );
}
