"use client";

import {
  AlertTriangle, Building2, CheckCircle2, LayoutDashboard, MessageSquareWarning,
  Users, Wallet,
} from "lucide-react";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { AppShell, PageHeader, type NavItem } from "@/components/AppShell";
import { Button, Chip, EmptyState, Tabs } from "@/components/ui";
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

export default function AdminPayoutsPage() {
  const [tab, setTab] = useState("pending");
  const [pending, setPending] = useState<any>(null);
  const [history, setHistory] = useState<any>(null);
  const [busy, setBusy] = useState<string | null>(null);

  function load() {
    adminApi.pendingPayouts().then(setPending);
    adminApi.payouts().then(setHistory);
  }
  useEffect(load, []);

  async function createPayout(gymId: number) {
    const now = new Date();
    setBusy(`create-${gymId}`);
    try {
      const res = await adminApi.createPayout({
        gym_id: gymId,
        period_month: now.getMonth() + 1,
        period_year: now.getFullYear(),
      });
      toast.success(`Payout ${res.payout_ref} created`);
      load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create payout");
    } finally {
      setBusy(null);
    }
  }

  async function release(id: number) {
    setBusy(`release-${id}`);
    try {
      const res = await adminApi.releasePayout(id);
      toast.success(res.message ?? "Payout released");
      load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not release");
    } finally {
      setBusy(null);
    }
  }

  return (
    <AppShell role="admin" nav={NAV} loginPath="/admin/login" brandLabel="Admin">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8">
        <PageHeader title="Payouts" subtitle="Monthly settlement to gym owners" />

        <Tabs
          tabs={[{ key: "pending", label: "Pending" }, { key: "history", label: "History" }]}
          active={tab}
          onChange={setTab}
        />

        {tab === "pending" && (
          <div className="mt-6">
            {!pending ? (
              <div className="skeleton h-64 w-full rounded-2xl" />
            ) : pending.gyms.length === 0 ? (
              <EmptyState icon={Wallet} title="Nothing pending this period" />
            ) : (
              <div className="space-y-3">
                <div className="card p-4 flex justify-between text-sm">
                  <span className="text-ink-400">Period {pending.period}</span>
                  <span className="font-semibold">{rupees(pending.totals.net_payable)} payable total</span>
                </div>
                {pending.gyms.map((g: any) => (
                  <div key={g.gym_id} className="card p-4 flex items-center gap-3 flex-wrap">
                    <div className="flex-1 min-w-[180px]">
                      <p className="font-medium text-sm">{g.gym?.name}</p>
                      <p className="text-xs text-ink-500">{g.count} payments · {g.gym?.locality}</p>
                    </div>
                    <div className="text-right min-w-[100px]">
                      <p className="font-semibold text-sm">{rupees(g.net)}</p>
                      <p className="text-xs text-ink-500">of {rupees(g.gross)} gross</p>
                    </div>
                    <Chip tone={g.owner?.bank_configured ? "success" : "danger"}>
                      {g.owner?.bank_configured ? "Bank ready" : "No bank details"}
                    </Chip>
                    <Button
                      size="sm"
                      disabled={g.payout_exists}
                      loading={busy === `create-${g.gym_id}`}
                      onClick={() => createPayout(g.gym_id)}
                    >
                      {g.payout_exists ? "Already created" : "Create payout"}
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === "history" && (
          <div className="mt-6">
            {!history ? (
              <div className="skeleton h-64 w-full rounded-2xl" />
            ) : history.payouts.length === 0 ? (
              <EmptyState icon={Wallet} title="No payouts yet" />
            ) : (
              <div className="space-y-3">
                {history.payouts.map((p: any) => (
                  <div key={p.id} className="card p-4 flex items-center gap-3 flex-wrap">
                    <div className="flex-1 min-w-[180px]">
                      <p className="font-medium text-sm">{p.gym?.name}</p>
                      <p className="text-xs text-ink-500">{p.period} · {p.payment_count} payments</p>
                    </div>
                    <p className="font-semibold text-sm">{rupees(p.net_payable)}</p>
                    <Chip tone={(STATUS_TONE[p.status]?.replace("chip-", "") as any) ?? "muted"}>
                      {p.status}
                    </Chip>
                    {p.status !== "paid" && (
                      <Button size="sm" icon={CheckCircle2} loading={busy === `release-${p.id}`} onClick={() => release(p.id)}>
                        Release
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </AppShell>
  );
}
