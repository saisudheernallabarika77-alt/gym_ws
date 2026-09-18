"use client";

import { CreditCard, MessageSquare, QrCode, Search, User } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell, PageHeader, type NavItem } from "@/components/AppShell";
import { CardSkeleton, Chip, EmptyState } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDate, rupees, STATUS_TONE } from "@/lib/utils";

const NAV: NavItem[] = [
  { href: "/chat", label: "Find a gym", icon: MessageSquare },
  { href: "/gyms", label: "Browse", icon: Search },
  { href: "/memberships", label: "My memberships", icon: CreditCard },
  { href: "/profile", label: "Profile", icon: User },
];

export default function MembershipsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .myMemberships()
      .then((r) => setItems(r.memberships))
      .finally(() => setLoading(false));
  }, []);

  return (
    <AppShell role="user" nav={NAV} loginPath="/login">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8">
        <PageHeader title="My memberships" subtitle="Every gym you've joined" />

        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <CardSkeleton key={i} />
            ))}
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            icon={CreditCard}
            title="No memberships yet"
            description="Ask the chatbot to find a gym that fits your budget."
            action={
              <Link href="/chat" className="btn-primary btn-md">
                Find a gym
              </Link>
            }
          />
        ) : (
          <div className="space-y-3">
            {items.map((m) => (
              <div key={m.membership_code} className="card p-5 flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-ink-800 grid place-items-center shrink-0 font-bold text-ink-500">
                  {m.gym?.name?.[0] ?? "?"}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-semibold truncate">{m.gym?.name}</p>
                    <Chip tone={(STATUS_TONE[m.status]?.replace("chip-", "") as any) ?? "muted"}>
                      {m.status.replace("_", " ")}
                    </Chip>
                  </div>
                  <p className="text-xs text-ink-400 mt-1">
                    {m.plan} · {rupees(m.total_amount)} · valid until{" "}
                    {formatDate(m.end_date)}
                  </p>
                  {m.due_info && m.due_info.state !== "upcoming" && (
                    <p className="text-xs text-warning mt-1">
                      Payment {m.due_info.state} — {rupees(m.due_info.amount)} due
                    </p>
                  )}
                </div>
                {m.has_pass && (
                  <Link
                    href={`/pass/${m.membership_code}`}
                    className="btn-secondary btn-sm shrink-0"
                  >
                    <QrCode className="w-4 h-4" /> Pass
                  </Link>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
