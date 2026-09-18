"use client";

import {
  AlertTriangle, CreditCard, Dumbbell, LayoutDashboard, Star, Users, Wallet,
} from "lucide-react";
import { useEffect, useState } from "react";
import { AppShell, PageHeader, type NavItem } from "@/components/AppShell";
import { Avatar, EmptyState } from "@/components/ui";
import { ownerApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";

const NAV: NavItem[] = [
  { href: "/owner/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/owner/equipment", label: "Equipment", icon: Dumbbell },
  { href: "/owner/coaches", label: "Coaches", icon: Users },
  { href: "/owner/members", label: "Members", icon: Users },
  { href: "/owner/dues", label: "Dues", icon: AlertTriangle },
  { href: "/owner/earnings", label: "Earnings", icon: Wallet },
  { href: "/owner/reviews", label: "Reviews", icon: Star },
];

export default function ReviewsPage() {
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    ownerApi.reviews().then(setData);
  }, []);

  return (
    <AppShell role="gym_owner" nav={NAV} loginPath="/owner/login" brandLabel="Partner Portal">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8">
        <PageHeader
          title="Reviews"
          subtitle={data ? `${data.rating} average from ${data.review_count} reviews` : undefined}
        />

        {!data ? (
          <div className="skeleton h-64 w-full rounded-2xl" />
        ) : data.reviews.length === 0 ? (
          <EmptyState icon={Star} title="No reviews yet" />
        ) : (
          <div className="space-y-3">
            {data.reviews.map((r: any) => (
              <div key={r.id} className="card p-4">
                <div className="flex items-center gap-3">
                  <Avatar name={r.user.name} src={r.user.photo_url} size={36} />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">{r.user.name}</p>
                    <p className="text-[11px] text-ink-500">{formatDate(r.created_at)}</p>
                  </div>
                  <div className="flex items-center gap-1">
                    <Star className="w-3.5 h-3.5 fill-warning text-warning" />
                    <span className="text-sm font-semibold">{r.rating}</span>
                  </div>
                </div>
                {r.title && <p className="text-sm font-medium mt-2.5">{r.title}</p>}
                {r.comment && <p className="text-sm text-ink-400 mt-1">{r.comment}</p>}
              </div>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
