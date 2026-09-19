"use client";

import {
  CreditCard, MapPinned, MessageSquare, Search, User,
} from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AppShell, PageHeader, type NavItem } from "@/components/AppShell";
import { Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import type { MapPoint } from "@/components/GymMap";

const NAV: NavItem[] = [
  { href: "/chat", label: "Find a gym", icon: MessageSquare },
  { href: "/gyms", label: "Browse", icon: Search },
  { href: "/memberships", label: "My memberships", icon: CreditCard },
  { href: "/profile", label: "Profile", icon: User },
];

// Leaflet touches `window` on import, so the map component can only ever
// render in the browser - ssr: false keeps Next.js from trying to render it
// on the server, which would crash the build.
const GymMap = dynamic(() => import("@/components/GymMap"), {
  ssr: false,
  loading: () => <div className="skeleton h-[70vh] w-full rounded-2xl" />,
});

export default function GymsMapPage() {
  const [points, setPoints] = useState<MapPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [realCount, setRealCount] = useState(0);
  const [showRealOnly, setShowRealOnly] = useState(false);

  useEffect(() => {
    api
      .mapPoints()
      .then((r) => {
        setPoints(r.points);
        setRealCount(r.real_count);
      })
      .finally(() => setLoading(false));
  }, []);

  const visible = useMemo(
    () => (showRealOnly ? points.filter((p) => p.is_real_listing) : points),
    [points, showRealOnly],
  );

  return (
    <AppShell role="user" nav={NAV} loginPath="/login">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        <PageHeader
          title="Gym map"
          subtitle={
            loading
              ? undefined
              : `${points.length} gyms · ${realCount} verified real locations`
          }
          action={
            <Link href="/gyms" className="btn-secondary btn-sm">
              List view
            </Link>
          }
        />

        {/* legend + honesty note - this is the whole point of the page */}
        <div className="card p-4 mb-5 flex flex-wrap items-center gap-x-6 gap-y-3">
          <div className="flex items-center gap-2 text-sm">
            <span className="w-3 h-3 rounded-full bg-success shrink-0" />
            Real gym, verified via OpenStreetMap
          </div>
          <div className="flex items-center gap-2 text-sm">
            <span className="w-3 h-3 rounded-full bg-ink-500 shrink-0" />
            Demo listing (generated for this dataset)
          </div>
          <label className="flex items-center gap-2 text-sm ml-auto cursor-pointer">
            <input
              type="checkbox"
              checked={showRealOnly}
              onChange={(e) => setShowRealOnly(e.target.checked)}
              className="w-4 h-4 rounded accent-brand-500"
            />
            Show only real gyms
          </label>
        </div>

        {loading ? (
          <Skeleton className="h-[70vh] w-full rounded-2xl" />
        ) : (
          <GymMap points={visible} />
        )}

        <p className="text-xs text-ink-500 mt-4 flex items-start gap-1.5">
          <MapPinned className="w-3.5 h-3.5 shrink-0 mt-0.5" />
          Most listings here are realistic demo data anchored to real Kakinada-region
          locations, not physically-visitable gyms — see the "Real listing" badge on
          each gym's page, or filter to real gyms only above.
        </p>
      </div>
    </AppShell>
  );
}
