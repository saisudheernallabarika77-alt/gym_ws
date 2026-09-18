"use client";

import { motion } from "framer-motion";
import {
  ArrowLeft, BadgeCheck, Clock, CreditCard, Dumbbell, Info, Instagram, Mail,
  MapPin, MapPinned, MessageSquare, Phone, Search, Snowflake, Sparkles, Star,
  User, Users, Wind,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { AppShell, type NavItem } from "@/components/AppShell";
import { Avatar, Button, Chip, EmptyState, Skeleton } from "@/components/ui";
import { api, getToken } from "@/lib/api";
import { cn, formatDate, getLocation, km, rupees } from "@/lib/utils";

const NAV: NavItem[] = [
  { href: "/chat", label: "Find a gym", icon: MessageSquare },
  { href: "/gyms", label: "Browse", icon: Search },
  { href: "/memberships", label: "My memberships", icon: CreditCard },
  { href: "/profile", label: "Profile", icon: User },
];

export default function GymDetailPage() {
  const params = useParams();
  const router = useRouter();
  const code = String(params.code);

  const [gym, setGym] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"overview" | "equipment" | "coaches" | "reviews">(
    "overview",
  );

  useEffect(() => {
    getLocation().then((loc) => {
      api
        .gym(code, loc?.lat, loc?.lon)
        .then(setGym)
        .catch(() => toast.error("Could not load this gym"))
        .finally(() => setLoading(false));
    });
  }, [code]);

  if (loading) {
    return (
      <AppShell role="user" nav={NAV} loginPath="/login">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 space-y-4">
          <Skeleton className="h-56 w-full rounded-2xl" />
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-32 w-full rounded-2xl" />
        </div>
      </AppShell>
    );
  }

  if (!gym) {
    return (
      <AppShell role="user" nav={NAV} loginPath="/login">
        <EmptyState icon={Dumbbell} title="Gym not found" />
      </AppShell>
    );
  }

  const isAC = gym.amenities.is_air_conditioned;

  function handleJoin() {
    if (!getToken("user")) {
      router.push("/login");
      return;
    }
    router.push(`/join/${code}`);
  }

  return (
    <AppShell role="user" nav={NAV} loginPath="/login">
      {/* ------------------------------------------------------------ hero */}
      <div className="relative h-52 sm:h-64 bg-gradient-to-br from-ink-700 via-ink-800 to-ink-900 overflow-hidden">
        <div className="absolute inset-0 grid place-items-center">
          <span className="text-8xl font-black text-ink-800 select-none">
            {gym.name[0]?.toUpperCase()}
          </span>
        </div>
        <div className="absolute inset-0 bg-gradient-to-t from-ink-950 via-ink-950/40 to-transparent" />
        <Link
          href="/gyms"
          className="absolute top-4 left-4 btn-secondary btn-sm !bg-ink-900/80 backdrop-blur-sm"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </Link>
      </div>

      <div className="max-w-5xl mx-auto px-4 sm:px-6 -mt-14 relative pb-32">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          className="card p-5 sm:p-7"
        >
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
                  {gym.name}
                </h1>
                {gym.verified && <BadgeCheck className="w-5 h-5 text-brand-400" />}
              </div>
              <p className="text-ink-400 mt-1.5 flex items-center gap-1.5 text-sm">
                <MapPin className="w-3.5 h-3.5" />
                {gym.location.address_line}, {gym.location.locality},{" "}
                {gym.location.district}
                {gym.location.distance_km != null && (
                  <span className="text-brand-400 font-medium">
                    · {km(gym.location.distance_km)} away
                  </span>
                )}
              </p>

              <div className="flex flex-wrap gap-2 mt-3">
                <Chip tone={isAC ? "brand" : "muted"} icon={isAC ? Snowflake : Wind}>
                  {gym.amenities.ac_status}
                </Chip>
                <Chip tone="muted">{gym.gym_type}</Chip>
                {gym.amenities.supplements_available && (
                  <Chip tone="success">Supplements available</Chip>
                )}
                {gym.pricing.trial_available && (
                  <Chip tone="warning">{gym.pricing.trial_days}-day free trial</Chip>
                )}
              </div>
            </div>

            <div className="flex items-center gap-1.5 shrink-0">
              <Star className="w-5 h-5 fill-warning text-warning" />
              <span className="text-lg font-bold">{gym.social.rating}</span>
              <span className="text-sm text-ink-500">
                ({gym.social.review_count} reviews)
              </span>
            </div>
          </div>

          <p className="text-sm text-ink-300 mt-4 leading-relaxed">{gym.description}</p>

          {/* Honest data-provenance note - most listings in this demo dataset
              are realistic placeholders anchored to real locations, not real
              gyms, since gym pricing/equipment data isn't published anywhere
              publicly. See README.md "The gym dataset" for the full explanation. */}
          <div
            className={cn(
              "mt-4 rounded-xl px-3.5 py-2.5 text-xs flex items-start gap-2",
              gym.data_source?.is_real_listing
                ? "bg-emerald-500/10 text-emerald-200"
                : "bg-ink-800/60 text-ink-400",
            )}
          >
            {gym.data_source?.is_real_listing ? (
              <MapPinned className="w-3.5 h-3.5 shrink-0 mt-0.5" />
            ) : (
              <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />
            )}
            <span>{gym.data_source?.label}</span>
          </div>
        </motion.div>

        {/* -------------------------------------------------- pricing card */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.08, ease: [0.16, 1, 0.3, 1] }}
          className="card p-5 sm:p-7 mt-4"
        >
          <h2 className="font-semibold mb-4 flex items-center gap-2">
            <CreditCard className="w-4 h-4 text-brand-400" />
            Pricing
          </h2>

          <div className="grid sm:grid-cols-2 gap-4">
            <div className="rounded-xl bg-ink-800/60 p-4">
              <p className="text-xs text-ink-400">Monthly membership</p>
              <p className="text-2xl font-bold gradient-text mt-1">
                {rupees(gym.pricing.monthly_fee)}
              </p>
            </div>
            <div className="rounded-xl bg-ink-800/60 p-4">
              <p className="text-xs text-ink-400">With personal coach</p>
              <p className="text-2xl font-bold mt-1">
                {rupees(gym.pricing.membership_with_coach)}
              </p>
            </div>
          </div>

          <div
            className={cn(
              "mt-4 rounded-xl p-3.5 text-sm font-medium",
              gym.pricing.coach_included
                ? "bg-success/10 text-emerald-200"
                : "bg-warning/10 text-amber-200",
            )}
          >
            {gym.pricing.coach_fee_note}
          </div>

          {gym.pricing.registration_fee > 0 && (
            <p className="text-xs text-ink-500 mt-3">
              + one-time registration fee of {rupees(gym.pricing.registration_fee)}
            </p>
          )}

          {/* plan ladder */}
          <div className="mt-5 grid grid-cols-2 sm:grid-cols-4 gap-2.5">
            {gym.pricing.plans.map((p: any) => (
              <div key={p.id} className="rounded-lg border border-ink-800 p-3 text-center">
                <p className="text-[11px] text-ink-500">{p.plan_name}</p>
                <p className="font-bold text-sm mt-1">{rupees(p.price)}</p>
                {p.savings > 0 && (
                  <p className="text-[10px] text-success mt-0.5">
                    Save {rupees(p.savings)}
                  </p>
                )}
              </div>
            ))}
          </div>
        </motion.div>

        {/* ----------------------------------------------------------- tabs */}
        <div className="mt-6">
          <div className="flex gap-1 overflow-x-auto no-scrollbar border-b border-ink-800">
            {[
              { key: "overview", label: "Overview" },
              { key: "equipment", label: `Equipment (${gym.equipment.total_items})` },
              { key: "coaches", label: `Coaches (${gym.coaches.length})` },
              { key: "reviews", label: `Reviews (${gym.social.review_count})` },
            ].map((t) => (
              <button
                key={t.key}
                onClick={() => setTab(t.key as any)}
                className={cn(
                  "px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-colors border-b-2 -mb-px",
                  tab === t.key
                    ? "text-white border-brand-500"
                    : "text-ink-400 border-transparent hover:text-ink-200",
                )}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="py-6">
            {tab === "overview" && (
              <div className="grid sm:grid-cols-2 gap-5">
                <div className="card p-5">
                  <h3 className="font-semibold text-sm mb-3 flex items-center gap-2">
                    <Clock className="w-4 h-4 text-brand-400" /> Timings
                  </h3>
                  <div className="text-sm text-ink-300 space-y-1.5">
                    <p>Morning: {gym.timings.morning}</p>
                    <p>Evening: {gym.timings.evening}</p>
                    <p className="text-ink-500">{gym.timings.open_days}</p>
                    {gym.timings.weekly_off && (
                      <p className="text-ink-500">Weekly off: {gym.timings.weekly_off}</p>
                    )}
                    {gym.timings.ladies_timing && (
                      <p className="text-violet-300">
                        Ladies-only: {gym.timings.ladies_timing}
                      </p>
                    )}
                  </div>
                </div>

                <div className="card p-5">
                  <h3 className="font-semibold text-sm mb-3 flex items-center gap-2">
                    <Phone className="w-4 h-4 text-brand-400" /> Contact
                  </h3>
                  <div className="text-sm text-ink-300 space-y-1.5">
                    <p className="flex items-center gap-2">
                      <Phone className="w-3.5 h-3.5 text-ink-500" /> {gym.contact.phone}
                    </p>
                    {gym.contact.email && (
                      <p className="flex items-center gap-2">
                        <Mail className="w-3.5 h-3.5 text-ink-500" /> {gym.contact.email}
                      </p>
                    )}
                    {gym.contact.instagram && (
                      <p className="flex items-center gap-2">
                        <Instagram className="w-3.5 h-3.5 text-ink-500" />
                        {gym.contact.instagram}
                      </p>
                    )}
                    {gym.location.google_maps_url && (
                      <a
                        href={gym.location.google_maps_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-brand-400 hover:text-brand-300 inline-flex items-center gap-1.5 mt-1"
                      >
                        <MapPin className="w-3.5 h-3.5" /> Open in Google Maps
                      </a>
                    )}
                  </div>
                </div>

                <div className="card p-5 sm:col-span-2">
                  <h3 className="font-semibold text-sm mb-3">Facilities</h3>
                  <div className="flex flex-wrap gap-2">
                    {gym.amenities.facilities.map((f: string) => (
                      <span key={f} className="chip-muted">
                        {f}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {tab === "equipment" && (
              <div className="space-y-6">
                {Object.entries(gym.equipment.categories).map(
                  ([cat, items]: [string, any]) => (
                    <div key={cat}>
                      <h3 className="font-semibold text-sm text-ink-300 mb-3">{cat}</h3>
                      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                        {items.map((it: any) => (
                          <div key={it.id} className="card p-3.5 flex gap-3">
                            <div className="w-12 h-12 rounded-lg bg-ink-800 grid place-items-center shrink-0">
                              <Dumbbell className="w-5 h-5 text-ink-500" />
                            </div>
                            <div className="min-w-0">
                              <p className="text-sm font-medium truncate">{it.name}</p>
                              <p className="text-xs text-ink-500 mt-0.5">
                                Qty {it.quantity} · {it.condition}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ),
                )}
              </div>
            )}

            {tab === "coaches" && (
              <div className="grid sm:grid-cols-2 gap-3">
                {gym.coaches.map((c: any) => (
                  <div key={c.id} className="card p-4 flex gap-3.5">
                    <Avatar name={c.name} src={c.photo_url} size={48} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <p className="font-medium text-sm">{c.name}</p>
                        <span className="text-xs text-ink-500 shrink-0">
                          {c.experience_years} yrs
                        </span>
                      </div>
                      <p className="text-xs text-ink-400 mt-1">
                        {c.specialisations.join(", ")}
                      </p>
                      {c.certifications.length > 0 && (
                        <p className="text-[11px] text-ink-600 mt-1">
                          {c.certifications[0]}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
                {gym.coaches.length === 0 && (
                  <EmptyState icon={Users} title="No coaches listed yet" />
                )}
              </div>
            )}

            {tab === "reviews" && (
              <div className="space-y-3">
                {gym.social.reviews.map((r: any) => (
                  <div key={r.id} className="card p-4">
                    <div className="flex items-center gap-3">
                      <Avatar name={r.user_name} src={r.user_photo} size={36} />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium">{r.user_name}</p>
                        <p className="text-[11px] text-ink-500">
                          {formatDate(r.created_at)}
                        </p>
                      </div>
                      <div className="flex items-center gap-1">
                        <Star className="w-3.5 h-3.5 fill-warning text-warning" />
                        <span className="text-sm font-semibold">{r.rating}</span>
                      </div>
                    </div>
                    {r.title && <p className="text-sm font-medium mt-2.5">{r.title}</p>}
                    {r.comment && (
                      <p className="text-sm text-ink-400 mt-1">{r.comment}</p>
                    )}
                  </div>
                ))}
                {gym.social.reviews.length === 0 && (
                  <EmptyState icon={Star} title="No reviews yet" />
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* --------------------------------------------------- sticky join */}
      <div className="fixed bottom-0 left-0 right-0 z-30">
        <div className="bg-gradient-to-t from-ink-950 via-ink-950/95 to-transparent pt-10 pb-5">
          <div className="max-w-5xl mx-auto px-4 sm:px-6">
            <div className="glass rounded-2xl p-4 flex items-center justify-between gap-4 shadow-2xl">
              <div>
                <p className="text-xs text-ink-400">Starting from</p>
                <p className="text-xl font-bold gradient-text">
                  {rupees(gym.pricing.monthly_fee)}
                  <span className="text-xs text-ink-500 font-normal">/month</span>
                </p>
              </div>
              <Button size="lg" onClick={handleJoin}>
                Join this gym
              </Button>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
