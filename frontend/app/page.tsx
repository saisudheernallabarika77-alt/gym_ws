"use client";

import { motion } from "framer-motion";
import {
  ArrowRight, Building2, Dumbbell, MapPin, MessageSquare,
  QrCode, Sparkles, User, Wallet,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const fadeUp = {
  hidden: { opacity: 0, y: 18 },
  show: (i = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, delay: i * 0.07, ease: [0.16, 1, 0.3, 1] as const },
  }),
};

export default function Landing() {
  const [stats, setStats] = useState<{
    total_gyms: number;
    ac_count: number;
    coach_included_count: number;
    fee_range: { min: number; max: number };
  } | null>(null);

  useEffect(() => {
    api.gymFilters().then(setStats).catch(() => {});
  }, []);

  return (
    <main className="min-h-screen">
      {/* ------------------------------------------------------------ nav */}
      <nav className="sticky top-0 z-40 glass border-b border-ink-800/70">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-brand-gradient grid place-items-center">
              <Dumbbell className="w-4 h-4 text-white" />
            </div>
            <span className="text-lg font-bold tracking-tight">Fitora</span>
          </Link>

          <div className="flex items-center gap-2">
            <Link href="/gyms" className="btn-ghost btn-sm hidden sm:inline-flex">
              Browse gyms
            </Link>
            <a href="#portals" className="btn-primary btn-sm">
              Get started
            </a>
          </div>
        </div>
      </nav>

      {/* ----------------------------------------------------------- hero */}
      <section className="relative overflow-hidden">
        {/* soft glow, purely decorative */}
        <div
          aria-hidden
          className="pointer-events-none absolute -top-40 left-1/2 -translate-x-1/2 w-[720px] h-[720px] rounded-full opacity-25 blur-3xl"
          style={{
            background:
              "radial-gradient(circle, rgba(255,77,46,.55) 0%, transparent 62%)",
          }}
        />

        <div className="relative max-w-6xl mx-auto px-4 sm:px-6 pt-16 pb-20 sm:pt-24 sm:pb-28">
          <motion.div
            variants={fadeUp}
            initial="hidden"
            animate="show"
            className="flex justify-center"
          >
            <span className="chip-brand">
              <MapPin className="w-3 h-3" />
              Kakinada &middot; 100 km radius
            </span>
          </motion.div>

          <motion.h1
            variants={fadeUp}
            initial="hidden"
            animate="show"
            custom={1}
            className="mt-6 text-center text-4xl sm:text-6xl font-extrabold tracking-tight text-balance leading-[1.08]"
          >
            Find your gym.
            <br />
            <span className="gradient-text">Join in minutes.</span>
          </motion.h1>

          <motion.p
            variants={fadeUp}
            initial="hidden"
            animate="show"
            custom={2}
            className="mt-5 text-center text-base sm:text-lg text-ink-300 max-w-2xl mx-auto text-balance"
          >
            Ask in plain language — <em>&ldquo;AC gym under ₹1,500 near me&rdquo;</em> — and
            get real matches with the coach fee stated upfront. Join online, pay by UPI,
            and walk in with a digital entry pass.
          </motion.p>

          {/* the only two ways in from the public site - pick a portal */}
          <motion.div
            variants={fadeUp}
            initial="hidden"
            animate="show"
            custom={3}
            id="portals"
            className="mt-9 grid sm:grid-cols-2 gap-4 max-w-2xl mx-auto"
          >
            <Link href="/signup" className="card-hover p-6 text-left group">
              <div className="w-11 h-11 rounded-xl bg-brand-500/[.12] grid place-items-center mb-3">
                <User className="w-5 h-5 text-brand-400" />
              </div>
              <h3 className="font-semibold flex items-center gap-1.5">
                I&apos;m looking for a gym
                <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
              </h3>
              <p className="text-sm text-ink-400 mt-1.5">
                Discover, compare and join a gym near you.
              </p>
            </Link>

            <Link href="/owner/signup" className="card-hover p-6 text-left group">
              <div className="w-11 h-11 rounded-xl bg-brand-500/[.12] grid place-items-center mb-3">
                <Building2 className="w-5 h-5 text-brand-400" />
              </div>
              <h3 className="font-semibold flex items-center gap-1.5">
                I run a gym
                <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
              </h3>
              <p className="text-sm text-ink-400 mt-1.5">
                List your gym and reach members through the chatbot.
              </p>
            </Link>
          </motion.div>

          <motion.p
            variants={fadeUp}
            initial="hidden"
            animate="show"
            custom={4}
            className="mt-5 text-center text-xs text-ink-500"
          >
            Already have an account?{" "}
            <Link href="/login" className="text-brand-400 hover:text-brand-300">
              Log in as a member
            </Link>
            {" · "}
            <Link href="/owner/login" className="text-brand-400 hover:text-brand-300">
              Log in as a partner
            </Link>
          </motion.p>

          {/* live stats from the real index */}
          <motion.div
            variants={fadeUp}
            initial="hidden"
            animate="show"
            custom={5}
            className="mt-14 grid grid-cols-2 sm:grid-cols-4 gap-3 max-w-3xl mx-auto"
          >
            {[
              { v: stats ? `${stats.total_gyms}+` : "—", l: "Gyms listed" },
              { v: stats ? `${stats.ac_count}` : "—", l: "AC gyms" },
              { v: stats ? `${stats.coach_included_count}` : "—", l: "Coach included" },
              {
                v: stats ? `₹${stats.fee_range.min}` : "—",
                l: "Starting from",
              },
            ].map((s) => (
              <div key={s.l} className="card p-4 text-center">
                <p className="text-2xl font-bold gradient-text tabular-nums">{s.v}</p>
                <p className="text-xs text-ink-400 mt-1">{s.l}</p>
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* -------------------------------------------------------- features */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 py-16 sm:py-20">
        <div className="text-center mb-12">
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight">
            Everything you need before you commit
          </h2>
          <p className="text-ink-400 mt-2.5 text-balance max-w-xl mx-auto">
            No calling around, no surprise charges at the counter.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[
            {
              icon: MessageSquare,
              title: "Ask, don't filter",
              body:
                "A chatbot trained on every listed gym. Type your budget, your goal, " +
                "your area — in English or Telugu — and it finds the fits.",
            },
            {
              icon: Wallet,
              title: "Coach fee, stated plainly",
              body:
                "Every listing says whether the trainer is included in the membership " +
                "or costs extra, and exactly how much extra.",
            },
            {
              icon: Dumbbell,
              title: "The actual equipment",
              body:
                "Real photos and exact model names uploaded by the gym — not stock " +
                "images. See what you're paying for.",
            },
            {
              icon: QrCode,
              title: "Digital entry pass",
              body:
                "Pay by UPI and get a signed QR pass with your photo, plan and goal. " +
                "Show it at the gate and walk in.",
            },
            {
              icon: MapPin,
              title: "Genuinely nearby",
              body:
                "Distance measured from where you actually are, across every town " +
                "within 100 km of Kakinada.",
            },
            {
              icon: Sparkles,
              title: "A diet chart with it",
              body:
                "Your calories and macros worked out from your height, weight and " +
                "goal, with an Andhra-friendly meal plan.",
            },
          ].map((f, i) => (
            <motion.div
              key={f.title}
              variants={fadeUp}
              initial="hidden"
              whileInView="show"
              viewport={{ once: true, margin: "-60px" }}
              custom={i % 3}
              className="card-hover p-6 group"
            >
              <div className="w-11 h-11 rounded-xl bg-brand-500/12 grid place-items-center mb-4 transition-transform group-hover:scale-105">
                <f.icon className="w-5 h-5 text-brand-400" />
              </div>
              <h3 className="font-semibold">{f.title}</h3>
              <p className="text-sm text-ink-400 mt-2 leading-relaxed">{f.body}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ------------------------------------------------------------ flow */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 py-12">
        <div className="card p-8 sm:p-12">
          <h2 className="text-2xl font-bold text-center tracking-tight">
            Four steps, start to gate
          </h2>
          <div className="mt-10 grid sm:grid-cols-4 gap-6">
            {[
              { n: "01", t: "Ask", d: "Tell the chatbot your budget and goal." },
              { n: "02", t: "Compare", d: "Pricing, equipment, trainers, distance." },
              { n: "03", t: "Join", d: "Form pre-fills. Pay by UPI." },
              { n: "04", t: "Enter", d: "Show your QR pass at the gym." },
            ].map((s, i) => (
              <motion.div
                key={s.n}
                variants={fadeUp}
                initial="hidden"
                whileInView="show"
                viewport={{ once: true }}
                custom={i}
                className="relative"
              >
                <span className="text-3xl font-extrabold text-ink-800">{s.n}</span>
                <h3 className="font-semibold mt-1">{s.t}</h3>
                <p className="text-sm text-ink-400 mt-1.5">{s.d}</p>
                {i < 3 && (
                  <ArrowRight className="hidden sm:block absolute top-3 -right-3 w-4 h-4 text-ink-700" />
                )}
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------- footer */}
      {/* Deliberately no admin link anywhere on the public site - the admin
          portal is reachable only by its own direct URL (/admin/login),
          never surfaced in navigation, for the obvious security reason. */}
      <footer className="border-t border-ink-800 mt-8">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-brand-gradient grid place-items-center">
              <Dumbbell className="w-3.5 h-3.5 text-white" />
            </div>
            <span className="font-semibold">Fitora</span>
          </div>
          <p className="text-xs text-ink-500 text-center">
            Kakinada, Andhra Pradesh &middot; Gym discovery, membership &amp; digital entry passes
          </p>
          <div className="flex gap-4 text-xs text-ink-500">
            <Link href="/gyms" className="hover:text-ink-300">Gyms</Link>
            <Link href="/owner/login" className="hover:text-ink-300">Partners</Link>
          </div>
        </div>
      </footer>
    </main>
  );
}
