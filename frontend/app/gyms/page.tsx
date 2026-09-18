"use client";

import {
  CreditCard, Filter, MapPin, MessageSquare, Search, SlidersHorizontal,
  User, X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { AppShell, PageHeader, type NavItem } from "@/components/AppShell";
import { GymCard, type GymCardData } from "@/components/GymCard";
import { CardSkeleton, EmptyState } from "@/components/ui";
import { api } from "@/lib/api";
import { cn, getLocation, rupees } from "@/lib/utils";

const NAV: NavItem[] = [
  { href: "/chat", label: "Find a gym", icon: MessageSquare },
  { href: "/gyms", label: "Browse", icon: Search },
  { href: "/memberships", label: "My memberships", icon: CreditCard },
  { href: "/profile", label: "Profile", icon: User },
];

type Filters = {
  q: string;
  max_fee?: number;
  is_ac?: boolean;
  coach_included?: boolean;
  sort: string;
};

export default function GymsPage() {
  const [gyms, setGyms] = useState<GymCardData[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [meta, setMeta] = useState<any>(null);

  const [filters, setFilters] = useState<Filters>({ q: "", sort: "relevance" });

  useEffect(() => {
    getLocation().then((loc) => loc && setCoords(loc));
    api.gymFilters().then(setMeta).catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    const t = setTimeout(() => {
      api
        .gyms({
          q: filters.q || undefined,
          max_fee: filters.max_fee,
          is_ac: filters.is_ac,
          coach_included: filters.coach_included,
          sort: filters.sort,
          lat: coords?.lat,
          lon: coords?.lon,
          page,
          page_size: 12,
        })
        .then((r) => {
          setGyms(r.results);
          setTotal(r.total);
          setTotalPages(r.total_pages);
        })
        .finally(() => setLoading(false));
    }, 300);
    return () => clearTimeout(t);
  }, [filters, page, coords]);

  function update<K extends keyof Filters>(key: K, value: Filters[K]) {
    setFilters((f) => ({ ...f, [key]: value }));
    setPage(1);
  }

  const activeCount =
    (filters.max_fee ? 1 : 0) +
    (filters.is_ac !== undefined ? 1 : 0) +
    (filters.coach_included !== undefined ? 1 : 0);

  return (
    <AppShell role="user" nav={NAV} loginPath="/login">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
        <PageHeader
          title="Browse gyms"
          subtitle={`${total} gyms within 100 km of Kakinada`}
        />

        {/* --------------------------------------------------- search bar */}
        <div className="flex gap-2 mb-5">
          <div className="relative flex-1">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-500" />
            <input
              value={filters.q}
              onChange={(e) => update("q", e.target.value)}
              placeholder="Search by name or area…"
              className="input pl-10"
            />
          </div>
          <button
            onClick={() => setShowFilters((s) => !s)}
            className={cn(
              "btn-secondary btn-md shrink-0",
              activeCount > 0 && "border-brand-500/50 text-brand-300",
            )}
          >
            <SlidersHorizontal className="w-4 h-4" />
            Filters {activeCount > 0 && `(${activeCount})`}
          </button>
        </div>

        {/* ------------------------------------------------------ filters */}
        {showFilters && (
          <div className="card p-4 sm:p-5 mb-6 animate-fade-up">
            <div className="grid sm:grid-cols-4 gap-4">
              <div>
                <label className="label">Max monthly fee</label>
                <select
                  className="input"
                  value={filters.max_fee ?? ""}
                  onChange={(e) =>
                    update("max_fee", e.target.value ? Number(e.target.value) : undefined)
                  }
                >
                  <option value="">Any budget</option>
                  {[800, 1000, 1500, 2000, 2500, 3000].map((v) => (
                    <option key={v} value={v}>
                      Under {rupees(v)}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="label">AC</label>
                <select
                  className="input"
                  value={filters.is_ac === undefined ? "" : String(filters.is_ac)}
                  onChange={(e) =>
                    update(
                      "is_ac",
                      e.target.value === "" ? undefined : e.target.value === "true",
                    )
                  }
                >
                  <option value="">Any</option>
                  <option value="true">AC only</option>
                  <option value="false">Non-AC only</option>
                </select>
              </div>

              <div>
                <label className="label">Coach</label>
                <select
                  className="input"
                  value={
                    filters.coach_included === undefined
                      ? ""
                      : String(filters.coach_included)
                  }
                  onChange={(e) =>
                    update(
                      "coach_included",
                      e.target.value === "" ? undefined : e.target.value === "true",
                    )
                  }
                >
                  <option value="">Any</option>
                  <option value="true">Included in fee</option>
                  <option value="false">Separate charge</option>
                </select>
              </div>

              <div>
                <label className="label">Sort by</label>
                <select
                  className="input"
                  value={filters.sort}
                  onChange={(e) => update("sort", e.target.value)}
                >
                  <option value="relevance">Relevance</option>
                  <option value="price_low">Price: Low to High</option>
                  <option value="price_high">Price: High to Low</option>
                  <option value="rating">Highest Rated</option>
                  <option value="distance">Nearest</option>
                  <option value="popular">Most Popular</option>
                </select>
              </div>
            </div>

            {activeCount > 0 && (
              <button
                onClick={() =>
                  setFilters({ q: filters.q, sort: filters.sort })
                }
                className="text-xs text-ink-400 hover:text-danger mt-3 inline-flex items-center gap-1"
              >
                <X className="w-3 h-3" />
                Clear filters
              </button>
            )}
          </div>
        )}

        {/* --------------------------------------------------------- grid */}
        {loading ? (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <CardSkeleton key={i} />
            ))}
          </div>
        ) : gyms.length === 0 ? (
          <EmptyState
            icon={Filter}
            title="No gyms match those filters"
            description="Try widening your budget or clearing a filter."
          />
        ) : (
          <>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {gyms.map((g, i) => (
                <GymCard key={g.gym_code} gym={g} index={i} />
              ))}
            </div>

            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-8">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="btn-secondary btn-sm"
                >
                  Previous
                </button>
                <span className="text-sm text-ink-400 px-3">
                  Page {page} of {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="btn-secondary btn-sm"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
}
