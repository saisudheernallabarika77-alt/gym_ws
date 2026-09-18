"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowLeft, Check, CheckCircle2, CreditCard, Loader2, QrCode,
  Ruler, Target, Weight,
} from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { AppShell, type NavItem } from "@/components/AppShell";
import { Button, Input, Select, Skeleton } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { cn, rupees } from "@/lib/utils";
import {
  MessageSquare, Search, User,
} from "lucide-react";

const NAV: NavItem[] = [
  { href: "/chat", label: "Find a gym", icon: MessageSquare },
  { href: "/gyms", label: "Browse", icon: Search },
  { href: "/memberships", label: "My memberships", icon: CreditCard },
  { href: "/profile", label: "Profile", icon: User },
];

type Step = "form" | "payment" | "success";

export default function JoinPage() {
  const params = useParams();
  const router = useRouter();
  const code = String(params.code);

  const [loading, setLoading] = useState(true);
  const [pre, setPre] = useState<any>(null);
  const [step, setStep] = useState<Step>("form");
  const [busy, setBusy] = useState(false);

  const [planId, setPlanId] = useState<number | null>(null);
  const [withCoach, setWithCoach] = useState(false);
  const [weight, setWeight] = useState("");
  const [height, setHeight] = useState("");
  const [targetWeight, setTargetWeight] = useState("");
  const [goal, setGoal] = useState("");
  const [activity, setActivity] = useState("moderate");

  const [order, setOrder] = useState<any>(null);
  const [payRef, setPayRef] = useState("");
  const [membershipCode, setMembershipCode] = useState("");
  const [upiId, setUpiId] = useState("");
  const [breakdown, setBreakdown] = useState<any>(null);

  useEffect(() => {
    api
      .joinPrefill(code)
      .then((r) => {
        setPre(r);
        setPlanId(r.plans[0]?.id ?? null);
        setWeight(String(r.prefill.weight_kg ?? ""));
        setHeight(String(r.prefill.height_cm ?? ""));
        setGoal(r.prefill.goal ?? r.goals[0]?.value ?? "general_fitness");
        setWithCoach(r.gym.coach_included);
      })
      .catch((err) => {
        toast.error(err instanceof ApiError ? err.message : "Could not load join form");
        router.push(`/gyms/${code}`);
      })
      .finally(() => setLoading(false));
  }, [code, router]);

  async function submitJoin(e: React.FormEvent) {
    e.preventDefault();
    if (!planId || !weight || !height || !goal) {
      toast.error("Fill in all the fields");
      return;
    }
    setBusy(true);
    try {
      const res = await api.join(code, {
        plan_id: planId,
        with_coach: withCoach,
        weight_kg: Number(weight),
        height_cm: Number(height),
        target_weight_kg: targetWeight ? Number(targetWeight) : null,
        goal,
        activity_level: activity,
      });
      setOrder(res.payment);
      setPayRef(res.payment.ref);
      setMembershipCode(res.membership_code);
      setBreakdown(res.breakdown);
      setStep("payment");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create membership");
    } finally {
      setBusy(false);
    }
  }

  async function submitPayment(e: React.FormEvent) {
    e.preventDefault();
    if (!upiId.includes("@")) {
      toast.error("Enter a valid UPI ID, e.g. yourname@ybl");
      return;
    }
    setBusy(true);
    try {
      await api.pay(payRef, { upi_id: upiId });
      setStep("success");
      toast.success("Payment successful!");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Payment failed");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <AppShell role="user" nav={NAV} loginPath="/login">
        <div className="max-w-2xl mx-auto px-4 py-10 space-y-4">
          <Skeleton className="h-8 w-1/2" />
          <Skeleton className="h-64 w-full rounded-2xl" />
        </div>
      </AppShell>
    );
  }

  const selectedPlan = pre?.plans.find((p: any) => p.id === planId);

  return (
    <AppShell role="user" nav={NAV} loginPath="/login">
      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8 pb-24">
        <button
          onClick={() => router.push(`/gyms/${code}`)}
          className="btn-ghost btn-sm -ml-3 mb-4"
        >
          <ArrowLeft className="w-4 h-4" /> Back to gym
        </button>

        {/* progress */}
        <div className="flex items-center gap-2 mb-8">
          {["form", "payment", "success"].map((s, i) => (
            <div key={s} className="flex items-center gap-2 flex-1">
              <div
                className={cn(
                  "w-8 h-8 rounded-full grid place-items-center text-xs font-bold shrink-0 transition-colors",
                  step === s
                    ? "bg-brand-gradient text-white"
                    : ["form", "payment", "success"].indexOf(step) > i
                      ? "bg-success text-white"
                      : "bg-ink-800 text-ink-500",
                )}
              >
                {["form", "payment", "success"].indexOf(step) > i ? (
                  <Check className="w-4 h-4" />
                ) : (
                  i + 1
                )}
              </div>
              {i < 2 && <div className="h-px flex-1 bg-ink-800" />}
            </div>
          ))}
        </div>

        <AnimatePresence mode="wait">
          {step === "form" && (
            <motion.div
              key="form"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
            >
              <h1 className="text-2xl font-bold tracking-tight">
                Join {pre.gym.name}
              </h1>
              <p className="text-sm text-ink-400 mt-1.5">{pre.gym.coach_fee_note}</p>

              <form onSubmit={submitJoin} className="mt-7 space-y-6">
                {/* pre-filled profile block */}
                <div className="card p-4">
                  <p className="text-xs font-medium text-ink-400 mb-3">
                    Your details (from your profile)
                  </p>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <p className="text-ink-500 text-xs">Name</p>
                      <p className="font-medium">{pre.prefill.full_name}</p>
                    </div>
                    <div>
                      <p className="text-ink-500 text-xs">Phone</p>
                      <p className="font-medium">{pre.prefill.phone}</p>
                    </div>
                    <div className="col-span-2">
                      <p className="text-ink-500 text-xs">Address</p>
                      <p className="font-medium">{pre.prefill.address}</p>
                    </div>
                  </div>
                </div>

                {/* plan */}
                <div>
                  <label className="label">Choose a plan</label>
                  <div className="grid grid-cols-2 gap-2.5">
                    {pre.plans.map((p: any) => (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => setPlanId(p.id)}
                        className={cn(
                          "rounded-xl border p-3.5 text-left transition-all",
                          planId === p.id
                            ? "border-brand-500 bg-brand-500/10"
                            : "border-ink-800 hover:border-ink-700",
                        )}
                      >
                        <p className="text-xs text-ink-400">{p.plan_name}</p>
                        <p className="font-bold mt-1">{rupees(p.price)}</p>
                        {p.savings > 0 && (
                          <p className="text-[11px] text-success mt-0.5">
                            Save {rupees(p.savings)}
                          </p>
                        )}
                      </button>
                    ))}
                  </div>
                </div>

                {/* coach */}
                {!pre.gym.coach_included && (
                  <label className="flex items-center gap-3 card p-4 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={withCoach}
                      onChange={(e) => setWithCoach(e.target.checked)}
                      className="w-4 h-4 rounded accent-brand-500"
                    />
                    <div>
                      <p className="text-sm font-medium">Add a personal coach</p>
                      <p className="text-xs text-ink-400">
                        +{rupees(pre.gym.coach_fee_separate)}/month extra
                      </p>
                    </div>
                  </label>
                )}

                {/* body metrics + goal */}
                <div className="grid grid-cols-2 gap-4">
                  <Input
                    label="Weight (kg)"
                    icon={Weight}
                    type="number"
                    step="0.1"
                    value={weight}
                    onChange={(e) => setWeight(e.target.value)}
                    required
                  />
                  <Input
                    label="Height (cm)"
                    icon={Ruler}
                    type="number"
                    step="0.1"
                    value={height}
                    onChange={(e) => setHeight(e.target.value)}
                    required
                  />
                </div>

                <Input
                  label="Target weight (kg) — optional"
                  icon={Target}
                  type="number"
                  step="0.1"
                  value={targetWeight}
                  onChange={(e) => setTargetWeight(e.target.value)}
                  placeholder="e.g. 68"
                />

                <Select label="What's your goal?" value={goal} onChange={(e) => setGoal(e.target.value)}>
                  {pre.goals.map((g: any) => (
                    <option key={g.value} value={g.value}>
                      {g.label}
                    </option>
                  ))}
                </Select>

                <Select
                  label="Activity level"
                  value={activity}
                  onChange={(e) => setActivity(e.target.value)}
                >
                  {pre.activity_levels.map((a: any) => (
                    <option key={a.value} value={a.value}>
                      {a.label}
                    </option>
                  ))}
                </Select>

                {selectedPlan && (
                  <div className="card p-4 bg-brand-500/5 border-brand-500/20">
                    <div className="flex justify-between text-sm">
                      <span className="text-ink-400">Plan ({selectedPlan.plan_name})</span>
                      <span>{rupees(selectedPlan.price)}</span>
                    </div>
                    {withCoach && !pre.gym.coach_included && (
                      <div className="flex justify-between text-sm mt-1.5">
                        <span className="text-ink-400">
                          Coach ({selectedPlan.duration_months} mo)
                        </span>
                        <span>
                          {rupees(pre.gym.coach_fee_separate * selectedPlan.duration_months)}
                        </span>
                      </div>
                    )}
                    <div className="flex justify-between font-bold mt-2 pt-2 border-t border-ink-800">
                      <span>Total</span>
                      <span className="gradient-text">
                        {rupees(
                          selectedPlan.price +
                            (withCoach && !pre.gym.coach_included
                              ? pre.gym.coach_fee_separate * selectedPlan.duration_months
                              : 0),
                        )}
                      </span>
                    </div>
                  </div>
                )}

                <Button type="submit" loading={busy} className="w-full btn-lg">
                  Continue to payment
                </Button>
              </form>
            </motion.div>
          )}

          {step === "payment" && order && (
            <motion.div
              key="payment"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              className="text-center"
            >
              <h1 className="text-2xl font-bold tracking-tight">Complete payment</h1>
              <p className="text-sm text-ink-400 mt-1.5">
                Scan the QR or enter your UPI ID below
              </p>

              <div className="card p-6 mt-6 inline-block">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={order.qr_data_uri}
                  alt="Payment QR code"
                  className="w-48 h-48 rounded-xl"
                />
                <p className="text-2xl font-bold gradient-text mt-4">
                  {rupees(order.amount)}
                </p>
                <p className="text-xs text-ink-500 mt-1">to {order.payee_name}</p>
              </div>

              <form onSubmit={submitPayment} className="mt-6 max-w-xs mx-auto space-y-4">
                <Input
                  label="Your UPI ID"
                  placeholder="yourname@ybl"
                  value={upiId}
                  onChange={(e) => setUpiId(e.target.value)}
                  required
                />
                <Button type="submit" loading={busy} className="w-full btn-lg">
                  <CreditCard className="w-4 h-4" />
                  Pay {rupees(order.amount)}
                </Button>
                <p className="text-[11px] text-ink-600">
                  This is a simulated payment for demo purposes. No real money moves.
                </p>
              </form>
            </motion.div>
          )}

          {step === "success" && (
            <motion.div
              key="success"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="text-center py-8"
            >
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", stiffness: 200, damping: 12, delay: 0.1 }}
                className="inline-grid place-items-center w-20 h-20 rounded-full bg-success/15 mb-5"
              >
                <CheckCircle2 className="w-10 h-10 text-success" />
              </motion.div>
              <h1 className="text-2xl font-bold tracking-tight">You're in!</h1>
              <p className="text-sm text-ink-400 mt-2">
                Payment successful. Your digital entry pass is ready.
              </p>

              <Button
                size="lg"
                icon={QrCode}
                className="mt-7"
                onClick={() => router.push(`/pass/${membershipCode}`)}
              >
                View my entry pass
              </Button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </AppShell>
  );
}
