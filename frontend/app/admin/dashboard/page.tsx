"use client";

import {
  AlertTriangle, Building2, LayoutDashboard, MessageSquareWarning,
  ShieldCheck, Users, Wallet,
} from "lucide-react";
import { useEffect, useState } from "react";
import { AppShell, PageHeader, type NavItem } from "@/components/AppShell";
import { Chip, EmptyState, StatTile } from "@/components/ui";
import { adminApi } from "@/lib/api";
import { compactRupees, formatDateTime, rupees } from "@/lib/utils";

const NAV: NavItem[] = [
  { href: "/admin/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/admin/users", label: "Users", icon: Users },
  { href: "/admin/gyms", label: "Gyms", icon: Building2 },
  { href: "/admin/dues", label: "Dues", icon: AlertTriangle },
  { href: "/admin/payouts", label: "Payouts", icon: Wallet },
  { href: "/admin/complaints", label: "Complaints", icon: MessageSquareWarning },
];

export default function AdminDashboard() {
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    adminApi.dashboard().then(setData);
  }, []);

  if (!data) {
    return (
      <AppShell role="admin" nav={NAV} loginPath="/admin/login" brandLabel="Admin">
        <div className="max-w-6xl mx-auto px-4 py-10">
          <div className="skeleton h-64 w-full rounded-2xl" />
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell role="admin" nav={NAV} loginPath="/admin/login" brandLabel="Admin">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        <PageHeader title="Platform overview" />

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <StatTile label="Total collected" value={compactRupees(data.money.total_collected)} icon={Wallet} tone="brand" />
          <StatTile label="Platform commission" value={compactRupees(data.money.platform_commission)} icon={ShieldCheck} tone="success" delay={0.05} />
          <StatTile label="Owed to gyms" value={compactRupees(data.money.owed_to_gyms)} icon={Building2} tone="warning" delay={0.1} />
          <StatTile label="Pending dues" value={compactRupees(data.money.pending_dues_amount)} icon={AlertTriangle} tone="danger" delay={0.15} />
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatTile label="Users" value={data.counts.users} sub={`${data.counts.blocked_users} blocked`} icon={Users} delay={0.2} />
          <StatTile label="Gyms" value={data.counts.gyms_total} sub={`${data.counts.gyms_active} active`} icon={Building2} delay={0.25} />
          <StatTile label="Active memberships" value={data.counts.active_memberships} icon={ShieldCheck} tone="success" delay={0.3} />
          <StatTile label="Overdue" value={data.counts.overdue_memberships} tone="danger" icon={AlertTriangle} delay={0.35} />
        </div>

        <div className="grid lg:grid-cols-2 gap-4">
          <div className="card p-5">
            <h2 className="font-semibold mb-4">Recent payments</h2>
            {data.recent_payments.length === 0 ? (
              <EmptyState icon={Wallet} title="No payments yet" />
            ) : (
              <div className="space-y-3">
                {data.recent_payments.map((p: any) => (
                  <div key={p.payment_ref} className="flex items-center justify-between text-sm">
                    <div>
                      <p className="font-medium">{p.user ?? "Unknown"}</p>
                      <p className="text-xs text-ink-500">{p.gym} · {formatDateTime(p.completed_at)}</p>
                    </div>
                    <p className="font-semibold">{rupees(p.amount)}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card p-5">
            <h2 className="font-semibold mb-4">Top gyms by members</h2>
            <div className="space-y-3">
              {data.top_gyms.map((g: any, i: number) => (
                <div key={g.gym_code} className="flex items-center gap-3 text-sm">
                  <span className="text-ink-600 font-bold w-4">{i + 1}</span>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">{g.name}</p>
                    <p className="text-xs text-ink-500">{g.locality}</p>
                  </div>
                  <Chip tone="muted">{g.member_count} members</Chip>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
