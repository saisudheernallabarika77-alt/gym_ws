"use client";

import { motion } from "framer-motion";
import {
  BadgeCheck, MapPin, MapPinned, Snowflake, Star, Users, Wind,
} from "lucide-react";
import Link from "next/link";
import { cn, km, rupees } from "@/lib/utils";

export type GymCardData = {
  gym_code: string;
  name: string;
  cover_image?: string | null;
  locality: string;
  district?: string;
  distance_km?: number | null;
  monthly_fee: number;
  coach_included: boolean;
  coach_fee_separate: number;
  fee_with_coach?: number;
  coach_fee_note?: string;
  ac_status: string;
  gym_type?: string;
  supplements_available?: boolean;
  rating: number;
  review_count: number;
  member_count?: number;
  verified?: boolean;
  facilities?: string[];
  // true only for the handful of gyms sourced from real OpenStreetMap data;
  // everything else is a realistic demo listing generated to fill out the
  // catalogue (see the "Data source" note on the gym detail page).
  is_real_listing?: boolean;
};

export function GymCard({
  gym,
  index = 0,
  compact,
}: {
  gym: GymCardData;
  index?: number;
  compact?: boolean;
}) {
  const isAC = gym.ac_status === "AC";

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.05, ease: [0.16, 1, 0.3, 1] }}
    >
      <Link href={`/gyms/${gym.gym_code}`} className="block group">
        <div className="card-hover overflow-hidden h-full flex flex-col">
          {/* ---------------------------------------------------- cover */}
          {!compact && (
            <div className="relative h-36 bg-ink-800 overflow-hidden shrink-0">
              {/* Dataset covers are placeholders, so the tile is a gradient with
                  the gym's initial rather than a broken image box. */}
              <div className="absolute inset-0 bg-gradient-to-br from-ink-700 via-ink-800 to-ink-900 grid place-items-center">
                <span className="text-5xl font-black text-ink-700 select-none">
                  {gym.name[0]?.toUpperCase()}
                </span>
              </div>
              <div className="absolute inset-0 bg-gradient-to-t from-ink-950/90 via-transparent to-transparent" />

              <div className="absolute top-2.5 left-2.5 flex gap-1.5">
                <span
                  className={cn(
                    "chip text-[10px] px-2 py-0.5 backdrop-blur-sm",
                    isAC
                      ? "bg-sky-500/20 text-sky-200 border-sky-400/30"
                      : "bg-ink-900/80 text-ink-300 border-ink-700",
                  )}
                >
                  {isAC ? <Snowflake className="w-2.5 h-2.5" /> : <Wind className="w-2.5 h-2.5" />}
                  {gym.ac_status}
                </span>
                {gym.gym_type && gym.gym_type !== "Unisex" && (
                  <span className="chip text-[10px] px-2 py-0.5 bg-violet-500/20 text-violet-200 border-violet-400/30 backdrop-blur-sm">
                    {gym.gym_type}
                  </span>
                )}
                {gym.is_real_listing && (
                  <span
                    className="chip text-[10px] px-2 py-0.5 bg-emerald-500/20 text-emerald-200 border-emerald-400/30 backdrop-blur-sm"
                    title="Real gym, verified via OpenStreetMap public map data"
                  >
                    <MapPinned className="w-2.5 h-2.5" />
                    Real listing
                  </span>
                )}
              </div>

              {gym.distance_km != null && (
                <span className="absolute top-2.5 right-2.5 chip text-[10px] px-2 py-0.5 bg-ink-900/85 text-ink-200 border-ink-700 backdrop-blur-sm">
                  <MapPin className="w-2.5 h-2.5" />
                  {km(gym.distance_km)}
                </span>
              )}
            </div>
          )}

          {/* ---------------------------------------------------- body */}
          <div className="p-4 flex-1 flex flex-col">
            <div className="flex items-start justify-between gap-2">
              <h3 className="font-semibold leading-snug group-hover:text-brand-300 transition-colors line-clamp-2">
                {gym.name}
              </h3>
              {gym.verified && (
                <BadgeCheck className="w-4 h-4 text-brand-400 shrink-0 mt-0.5" />
              )}
            </div>

            <p className="text-xs text-ink-400 mt-1 flex items-center gap-1">
              <MapPin className="w-3 h-3 shrink-0" />
              <span className="truncate">
                {gym.locality}
                {gym.district ? `, ${gym.district}` : ""}
              </span>
              {compact && gym.distance_km != null && (
                <span className="text-ink-500 shrink-0">· {km(gym.distance_km)}</span>
              )}
            </p>

            {/* ---- the pricing block: the thing people actually compare ---- */}
            <div className="mt-3 pt-3 border-t border-ink-800">
              <div className="flex items-baseline gap-1.5">
                <span className="text-xl font-bold gradient-text tabular-nums">
                  {rupees(gym.monthly_fee)}
                </span>
                <span className="text-xs text-ink-500">/month</span>
              </div>

              <p
                className={cn(
                  "text-xs mt-1.5 font-medium",
                  gym.coach_included ? "text-success" : "text-warning",
                )}
              >
                {gym.coach_included
                  ? "✓ Coach included in this fee"
                  : `+ ${rupees(gym.coach_fee_separate)}/mo for a personal coach`}
              </p>

              {!gym.coach_included && gym.fee_with_coach && (
                <p className="text-[11px] text-ink-500 mt-0.5">
                  With coach: {rupees(gym.fee_with_coach)}/month
                </p>
              )}
            </div>

            {/* ---- social proof ---- */}
            <div className="mt-3 pt-3 border-t border-ink-800 flex items-center justify-between text-xs">
              <span className="flex items-center gap-1 text-ink-300">
                <Star className="w-3.5 h-3.5 fill-warning text-warning" />
                <span className="font-semibold">{gym.rating}</span>
                <span className="text-ink-500">({gym.review_count})</span>
              </span>
              {gym.member_count != null && (
                <span className="flex items-center gap-1 text-ink-500">
                  <Users className="w-3.5 h-3.5" />
                  {gym.member_count} members
                </span>
              )}
            </div>

            {!compact && gym.facilities && gym.facilities.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1">
                {gym.facilities.slice(0, 3).map((f) => (
                  <span
                    key={f}
                    className="text-[10px] px-2 py-0.5 rounded-md bg-ink-800/80 text-ink-400"
                  >
                    {f}
                  </span>
                ))}
                {gym.facilities.length > 3 && (
                  <span className="text-[10px] px-2 py-0.5 rounded-md bg-ink-800/80 text-ink-500">
                    +{gym.facilities.length - 3}
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
      </Link>
    </motion.div>
  );
}
