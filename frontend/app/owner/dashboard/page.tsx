"use client";

import {
  AlertTriangle, Building2, CreditCard, Dumbbell, LayoutDashboard,
  MessageSquareWarning, Star, Users, Wallet,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell, PageHeader, type NavItem } from "@/components/AppShell";
import { Chip, EmptyState, StatTile } from "@/components/ui";
import { ownerApi } from "@/lib/api";
import { compactRupees, formatDate, rupees, STATUS_TONE } from "@/lib/utils";

const NAV: NavItem[] = [
  { href: "/owner/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/owner/equipment", label: "Equipment", icon: Dumbbell },
  { href: "/owner/coaches", label: "Coaches", icon: Users },
  { href: "/owner/members", label: "Members", icon: Users },
  { href: "/owner/dues", label: "Dues", icon: AlertTriangle },
  { href: "/owner/earnings", label: "Earnings", icon: Wallet },
  { href: "/owner/reviews", label: "Reviews", icon: Star },
];

export default function OwnerDashboard() {
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    ownerApi.dashboard().then(setData);
  }, []);

  if (!data) {
    return (
      <AppShell role="gym_owner" nav={NAV} loginPath="/owner/login" brandLabel="Partner Portal">
        <div className="max-w-6xl mx-auto px-4 py-10">
          <div className="skeleton h-64 w-full rounded-2xl" />
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell role="gym_owner" nav={NAV} loginPath="/owner/login" brandLabel="Partner Portal">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        <PageHeader
          title={data.gym?.name ?? "Your gym"}
          subtitle={
            data.gym
              ? `${data.gym.locality} · ${data.gym.status} ${
                  data.gym.indexed_in_rag ? "· Live in chatbot" : ""
                }`
              : undefined
          }
        />

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatTile
            label="Total members"
            value={data.stats.total_members}
            sub={`${data.stats.paid_members} paid up`}
            icon={Users}
            tone="brand"
          />
          <StatTile
            label="Due / Overdue"
            value={data.stats.due_members + data.stats.overdue_members}
            sub={rupees(data.stats.pending_amount) + " pending"}
            icon={AlertTriangle}
            tone={data.stats.overdue_members > 0 ? "danger" : "default"}
            delay={0.05}
          />
          <StatTile
            label="This month"
            value={compactRupees(data.earnings.this_month_share)}
            sub="your share"
            icon={Wallet}
            tone="success"
            delay={0.1}
          />
          <StatTile
            label="Awaiting payout"
            value={compactRupees(data.earnings.awaiting_payout)}
            sub="settled monthly by admin"
            icon={CreditCard}
            delay={0.15}
          />
        </div>

        <div className="grid lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 card p-5">
            <h2 className="font-semibold mb-4">Recent members</h2>
            {data.recent_members.length === 0 ? (
              <EmptyState icon={Users} title="No members yet" />
            ) : (
              <div className="space-y-3">
                {data.recent_members.map((m: any) => (
                  <div key={m.membership_code} className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-full bg-ink-800 grid place-items-center text-xs font-semibold text-ink-400 shrink-0">
                      {m.name[0]}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{m.name}</p>
                      <p className="text-xs text-ink-500">
                        Joined {formatDate(m.joined)} · {rupees(m.plan_amount)}
                      </p>
                    </div>
                    <Chip tone={(STATUS_TONE[m.status]?.replace("chip-", "") as any) ?? "muted"}>
                      {m.status}
                    </Chip>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card p-5">
            <h2 className="font-semibold mb-4">Gym stats</h2>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-ink-400">Equipment items</span>
                <span className="font-medium">{data.stats.equipment_count}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-400">Coaches</span>
                <span className="font-medium">{data.stats.coach_count}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-400">Plans</span>
                <span className="font-medium">{data.stats.plan_count}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-400">Rating</span>
                <span className="font-medium flex items-center gap-1">
                  <Star className="w-3.5 h-3.5 fill-warning text-warning" />
                  {data.gym.rating} ({data.gym.review_count})
                </span>
              </div>
            </div>
            <p className="text-xs text-ink-500 mt-4 leading-relaxed">
              {data.earnings.note}
            </p>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
