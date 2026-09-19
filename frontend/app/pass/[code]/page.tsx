"use client";

import { motion } from "framer-motion";
import {
  Apple, Calendar, CreditCard, Dumbbell, Download, Droplet, Flame, MapPin,
  MessageSquare, Phone, Search, Sparkles, User, Utensils,
} from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { AppShell, type NavItem } from "@/components/AppShell";
import { Avatar, Button, Chip, EmptyState, Skeleton, Tabs } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { cn, formatDate, rupees } from "@/lib/utils";

const NAV: NavItem[] = [
  { href: "/chat", label: "Find a gym", icon: MessageSquare },
  { href: "/gyms", label: "Browse", icon: Search },
  { href: "/memberships", label: "My memberships", icon: CreditCard },
  { href: "/profile", label: "Profile", icon: User },
];

export default function PassPage() {
  const params = useParams();
  const code = String(params.code);

  const [tab, setTab] = useState("pass");
  const [pass, setPass] = useState<any>(null);
  const [diet, setDiet] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    Promise.all([api.pass(code), api.diet(code).catch(() => null)])
      .then(([p, d]) => {
        setPass(p);
        setDiet(d);
      })
      .catch((err) => toast.error(err instanceof ApiError ? err.message : "Could not load pass"))
      .finally(() => setLoading(false));
  }, [code]);

  async function downloadDiet() {
    setDownloading(true);
    try {
      await api.downloadDietPdf(code);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not download the diet chart");
    } finally {
      setDownloading(false);
    }
  }

  if (loading) {
    return (
      <AppShell role="user" nav={NAV} loginPath="/login">
        <div className="max-w-md mx-auto px-4 py-10">
          <Skeleton className="h-96 w-full rounded-3xl" />
        </div>
      </AppShell>
    );
  }

  if (!pass) {
    return (
      <AppShell role="user" nav={NAV} loginPath="/login">
        <EmptyState icon={CreditCard} title="Pass not found" />
      </AppShell>
    );
  }

  const statusTone =
    pass.membership.status === "active"
      ? "success"
      : pass.membership.status === "expiring_soon"
        ? "warning"
        : "danger";

  return (
    <AppShell role="user" nav={NAV} loginPath="/login">
      <div className="max-w-md mx-auto px-4 sm:px-6 py-8">
        <Tabs
          tabs={[
            { key: "pass", label: "Entry Pass" },
            { key: "diet", label: "Diet Chart" },
          ]}
          active={tab}
          onChange={setTab}
        />

        {tab === "pass" && (
          <motion.div
            initial={{ opacity: 0, y: 16, rotateX: -8 }}
            animate={{ opacity: 1, y: 0, rotateX: 0 }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            className="mt-6"
          >
            {/* -------------------------------------------------- the card */}
            <div className="relative rounded-3xl overflow-hidden bg-gradient-to-br from-ink-800 via-ink-900 to-ink-950 border border-ink-700 shadow-2xl">
              {/* decorative brand stripe */}
              <div className="h-2 bg-brand-gradient" />

              <div className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-[10px] text-ink-500 tracking-widest uppercase">
                      Fitora Entry Pass
                    </p>
                    <p className="font-bold text-lg mt-0.5">{pass.gym.name}</p>
                  </div>
                  <Dumbbell className="w-6 h-6 text-brand-400" />
                </div>

                <div className="flex items-center gap-4 mt-6">
                  <Avatar name={pass.member.name} src={pass.member.photo_url} size={64} />
                  <div className="min-w-0">
                    <p className="font-semibold truncate">{pass.member.name}</p>
                    <p className="text-xs text-ink-400 mt-0.5">
                      Member since {formatDate(pass.member.member_since)}
                    </p>
                    <Chip tone="brand" className="mt-1.5 text-[10px]">
                      {pass.member.goal}
                    </Chip>
                  </div>
                </div>

                {/* QR block */}
                <div className="mt-6 bg-white rounded-2xl p-4 flex flex-col items-center">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={pass.qr_data_uri} alt="Entry QR code" className="w-44 h-44" />
                  <p className="text-ink-950 text-xs font-mono mt-2 tracking-wider">
                    {pass.pass_code}
                  </p>
                </div>

                <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <p className="text-ink-500 text-xs">Plan</p>
                    <p className="font-medium">{pass.membership.plan}</p>
                  </div>
                  <div>
                    <p className="text-ink-500 text-xs">Coach</p>
                    <p className="font-medium">
                      {pass.membership.with_coach
                        ? pass.membership.coach_name ?? "Assigned"
                        : "Not included"}
                    </p>
                  </div>
                  <div>
                    <p className="text-ink-500 text-xs">Valid until</p>
                    <p className="font-medium">
                      {formatDate(pass.membership.valid_until)}
                    </p>
                  </div>
                  <div>
                    <p className="text-ink-500 text-xs">Amount paid</p>
                    <p className="font-medium">{rupees(pass.membership.amount_paid)}</p>
                  </div>
                </div>

                <div className="mt-5 flex items-center justify-between">
                  <Chip tone={statusTone as any}>
                    {pass.membership.days_remaining} days remaining
                  </Chip>
                  <p className="text-[11px] text-ink-500 flex items-center gap-1">
                    <Phone className="w-3 h-3" /> {pass.gym.phone}
                  </p>
                </div>
              </div>
            </div>

            <p className="text-center text-xs text-ink-500 mt-5 flex items-center justify-center gap-1.5">
              <MapPin className="w-3 h-3" />
              Show this QR code at {pass.gym.name}'s entrance
            </p>
          </motion.div>
        )}

        {tab === "diet" && diet && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6 space-y-5"
          >
            <div className="card p-5">
              <div className="flex items-center justify-between gap-3">
                <h2 className="font-semibold flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-brand-400" />
                  {diet.goal_label} plan
                </h2>
                <Button size="sm" variant="secondary" icon={Download} loading={downloading} onClick={downloadDiet}>
                  Download PDF
                </Button>
              </div>
              <div className="grid grid-cols-4 gap-2 mt-4 text-center">
                <div>
                  <Flame className="w-4 h-4 text-warning mx-auto" />
                  <p className="font-bold text-sm mt-1">{diet.targets.calories}</p>
                  <p className="text-[10px] text-ink-500">kcal/day</p>
                </div>
                <div>
                  <Dumbbell className="w-4 h-4 text-brand-400 mx-auto" />
                  <p className="font-bold text-sm mt-1">{diet.targets.protein_g}g</p>
                  <p className="text-[10px] text-ink-500">protein</p>
                </div>
                <div>
                  <Utensils className="w-4 h-4 text-emerald-400 mx-auto" />
                  <p className="font-bold text-sm mt-1">{diet.targets.carbs_g}g</p>
                  <p className="text-[10px] text-ink-500">carbs</p>
                </div>
                <div>
                  <Droplet className="w-4 h-4 text-sky-400 mx-auto" />
                  <p className="font-bold text-sm mt-1">{diet.targets.water_litres}L</p>
                  <p className="text-[10px] text-ink-500">water</p>
                </div>
              </div>
              <p className="text-xs text-ink-500 mt-3 text-center">
                BMI {diet.targets.bmi} ({diet.targets.bmi_band})
                {diet.estimated_weeks_to_target &&
                  ` · ~${diet.estimated_weeks_to_target} weeks to target weight`}
              </p>
            </div>

            <div className="space-y-3">
              {Object.entries(diet.chart).map(([slot, info]: [string, any]) => (
                <div key={slot} className="card p-4">
                  <p className="text-xs font-medium text-brand-400">{slot}</p>
                  <ul className="mt-2 space-y-1">
                    {info.options.map((o: string, i: number) => (
                      <li key={i} className="text-sm text-ink-300 flex gap-2">
                        <span className="text-ink-600">•</span> {o}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>

            <div className="card p-4">
              <p className="text-xs font-medium text-ink-300 mb-2">Tips</p>
              <ul className="space-y-1.5">
                {diet.tips.map((t: string, i: number) => (
                  <li key={i} className="text-xs text-ink-400 flex gap-2">
                    <span className="text-success">✓</span> {t}
                  </li>
                ))}
              </ul>
            </div>

            <p className="text-[11px] text-ink-600 text-center px-4">{diet.disclaimer}</p>
          </motion.div>
        )}
      </div>
    </AppShell>
  );
}
