"use client";

import {
  AlertTriangle, CreditCard, Dumbbell, LayoutDashboard, Star, Users, Wallet,
} from "lucide-react";
import { useEffect, useState } from "react";
import { AppShell, PageHeader, type NavItem } from "@/components/AppShell";
import { Avatar, Chip, EmptyState } from "@/components/ui";
import { ownerApi } from "@/lib/api";
import { formatDate, GOAL_LABELS, rupees, STATUS_TONE } from "@/lib/utils";

const NAV: NavItem[] = [
  { href: "/owner/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/owner/equipment", label: "Equipment", icon: Dumbbell },
  { href: "/owner/coaches", label: "Coaches", icon: Users },
  { href: "/owner/members", label: "Members", icon: Users },
  { href: "/owner/dues", label: "Dues", icon: AlertTriangle },
  { href: "/owner/earnings", label: "Earnings", icon: Wallet },
  { href: "/owner/reviews", label: "Reviews", icon: Star },
];

export default function MembersPage() {
  const [members, setMembers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    ownerApi.members().then((r) => setMembers(r.members)).finally(() => setLoading(false));
  }, []);

  return (
    <AppShell role="gym_owner" nav={NAV} loginPath="/owner/login" brandLabel="Partner Portal">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8">
        <PageHeader title="Members" subtitle={`${members.length} total`} />

        {loading ? (
          <div className="skeleton h-64 w-full rounded-2xl" />
        ) : members.length === 0 ? (
          <EmptyState icon={Users} title="No members yet" />
        ) : (
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-ink-800 text-left text-xs text-ink-500">
                    <th className="p-4">Member</th>
                    <th className="p-4">Goal</th>
                    <th className="p-4">Coach</th>
                    <th className="p-4">Amount</th>
                    <th className="p-4">Status</th>
                    <th className="p-4">Ends</th>
                  </tr>
                </thead>
                <tbody>
                  {members.map((m) => (
                    <tr key={m.membership_code} className="border-b border-ink-800/60 last:border-0">
                      <td className="p-4">
                        <div className="flex items-center gap-2.5">
                          <Avatar name={m.user.name} src={m.user.photo_url} size={32} />
                          <div>
                            <p className="font-medium">{m.user.name}</p>
                            <p className="text-xs text-ink-500">{m.user.phone}</p>
                          </div>
                        </div>
                      </td>
                      <td className="p-4 text-ink-300">{GOAL_LABELS[m.goal] ?? m.goal}</td>
                      <td className="p-4 text-ink-300">{m.coach_name ?? "—"}</td>
                      <td className="p-4 font-medium">{rupees(m.total_amount)}</td>
                      <td className="p-4">
                        <Chip tone={(STATUS_TONE[m.status]?.replace("chip-", "") as any) ?? "muted"}>
                          {m.status.replace("_", " ")}
                        </Chip>
                      </td>
                      <td className="p-4 text-ink-400">{formatDate(m.end_date)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
