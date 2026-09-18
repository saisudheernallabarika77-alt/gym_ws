"use client";

import {
  AlertTriangle, CreditCard, Dumbbell, LayoutDashboard, Star, Users, Wallet,
} from "lucide-react";
import { useEffect, useState } from "react";
import { AppShell, PageHeader, type NavItem } from "@/components/AppShell";
import { Chip, EmptyState, StatTile } from "@/components/ui";
import { ownerApi } from "@/lib/api";
import { formatDateTime, rupees, STATUS_TONE } from "@/lib/utils";

const NAV: NavItem[] = [
  { href: "/owner/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/owner/equipment", label: "Equipment", icon: Dumbbell },
  { href: "/owner/coaches", label: "Coaches", icon: Users },
  { href: "/owner/members", label: "Members", icon: Users },
  { href: "/owner/dues", label: "Dues", icon: AlertTriangle },
  { href: "/owner/earnings", label: "Earnings", icon: Wallet },
  { href: "/owner/reviews", label: "Reviews", icon: Star },
];

export default function EarningsPage() {
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    ownerApi.earnings().then(setData);
  }, []);

  if (!data) {
    return (
      <AppShell role="gym_owner" nav={NAV} loginPath="/owner/login" brandLabel="Partner Portal">
        <div className="max-w-5xl mx-auto px-4 py-10">
          <div className="skeleton h-64 w-full rounded-2xl" />
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell role="gym_owner" nav={NAV} loginPath="/owner/login" brandLabel="Partner Portal">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8">
        <PageHeader title="Earnings" subtitle={data.note} />

        <div className="grid sm:grid-cols-3 gap-4 mb-8">
          <StatTile label="Lifetime share" value={rupees(data.totals.lifetime_gym_share)} icon={Wallet} tone="brand" />
          <StatTile label="Paid out" value={rupees(data.totals.paid_out)} icon={CreditCard} tone="success" delay={0.05} />
          <StatTile label="Awaiting payout" value={rupees(data.totals.awaiting_payout)} icon={AlertTriangle} tone="warning" delay={0.1} />
        </div>

        <div className="card p-5 mb-6">
          <h2 className="font-semibold mb-3">Payout account</h2>
          {data.bank.configured ? (
            <div className="grid sm:grid-cols-3 gap-4 text-sm">
              <div><p className="text-ink-500 text-xs">Account</p><p className="font-medium">{data.bank.account_number ?? "—"}</p></div>
              <div><p className="text-ink-500 text-xs">IFSC</p><p className="font-medium">{data.bank.ifsc ?? "—"}</p></div>
              <div><p className="text-ink-500 text-xs">UPI</p><p className="font-medium">{data.bank.upi_id ?? "—"}</p></div>
            </div>
          ) : (
            <p className="text-sm text-warning">No payout account configured yet.</p>
          )}
        </div>

        <h2 className="font-semibold mb-3">Payout history</h2>
        {data.payouts.length === 0 ? (
          <EmptyState icon={Wallet} title="No payouts yet" description="The admin releases your share monthly." />
        ) : (
          <div className="space-y-2 mb-8">
            {data.payouts.map((p: any) => (
              <div key={p.payout_ref} className="card p-4 flex items-center justify-between">
                <div>
                  <p className="font-medium text-sm">{p.period}</p>
                  <p className="text-xs text-ink-500">{p.payment_count} payments · ref {p.payout_ref}</p>
                </div>
                <div className="text-right">
                  <p className="font-semibold">{rupees(p.net_payable)}</p>
                  <Chip tone={(STATUS_TONE[p.status]?.replace("chip-", "") as any) ?? "muted"}>{p.status}</Chip>
                </div>
              </div>
            ))}
          </div>
        )}

        <h2 className="font-semibold mb-3">Recent payments</h2>
        {data.recent_payments.length === 0 ? (
          <EmptyState icon={CreditCard} title="No payments yet" />
        ) : (
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-ink-800 text-left text-xs text-ink-500">
                  <th className="p-3">Ref</th><th className="p-3">Amount</th>
                  <th className="p-3">Your share</th><th className="p-3">Date</th><th className="p-3">Settled</th>
                </tr>
              </thead>
              <tbody>
                {data.recent_payments.map((p: any) => (
                  <tr key={p.payment_ref} className="border-b border-ink-800/60 last:border-0">
                    <td className="p-3 text-xs text-ink-500">{p.payment_ref}</td>
                    <td className="p-3">{rupees(p.amount)}</td>
                    <td className="p-3 font-medium">{rupees(p.your_share)}</td>
                    <td className="p-3 text-ink-400">{formatDateTime(p.completed_at)}</td>
                    <td className="p-3">
                      <Chip tone={p.settled ? "success" : "warning"}>{p.settled ? "Settled" : "Pending"}</Chip>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AppShell>
  );
}
