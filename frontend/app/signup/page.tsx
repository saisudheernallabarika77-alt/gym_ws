"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowLeft, Dumbbell, Lock, Mail, MapPin, Phone, User as UserIcon,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { api, ApiError } from "@/lib/api";
import { Button, Input } from "@/components/ui";
import { getLocation } from "@/lib/utils";

type Step = "form" | "otp";

export default function SignupPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("form");
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [locating, setLocating] = useState(false);

  const [form, setForm] = useState({
    full_name: "",
    email: "",
    phone: "",
    address: "",
    password: "",
    confirm_password: "",
  });

  /* ------------------------------------------------------------- OTP state */
  const [code, setCode] = useState(["", "", "", "", "", ""]);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const otpRefs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    if (secondsLeft <= 0) return;
    const t = setTimeout(() => setSecondsLeft((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [secondsLeft]);

  useEffect(() => {
    if (step === "otp") otpRefs.current[0]?.focus();
  }, [step]);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((f) => ({ ...f, [k]: e.target.value }));
    setErrors((prev) => ({ ...prev, [k]: "" }));
  };

  async function useMyLocation() {
    setLocating(true);
    const loc = await getLocation();
    setLocating(false);
    if (loc) {
      setCoords(loc);
      toast.success("Location captured — we'll show gyms near you");
    } else {
      toast.error("Could not get your location. You can still continue.");
    }
  }

  function validate() {
    const e: Record<string, string> = {};
    if (form.full_name.trim().length < 2) e.full_name = "Enter your name";
    if (!/^\S+@\S+\.\S+$/.test(form.email)) e.email = "Enter a valid email";
    if (form.phone.replace(/\D/g, "").length < 10) e.phone = "Enter a 10-digit number";
    if (form.address.trim().length < 3) e.address = "Enter your address";
    if (form.password.length < 6) e.password = "At least 6 characters";
    if (form.password !== form.confirm_password)
      e.confirm_password = "Passwords do not match";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function submitForm(ev: React.FormEvent) {
    ev.preventDefault();
    if (!validate()) return;

    setBusy(true);
    try {
      await api.signup({
        ...form,
        latitude: coords?.lat ?? null,
        longitude: coords?.lon ?? null,
      });
      setStep("otp");
      setSecondsLeft(60);
      toast.success(`Verification code sent to ${form.email}`);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Signup failed";
      toast.error(msg);
      if (msg.toLowerCase().includes("email")) setErrors({ email: msg });
      else if (msg.toLowerCase().includes("phone")) setErrors({ phone: msg });
    } finally {
      setBusy(false);
    }
  }

  function onOtpChange(i: number, v: string) {
    const digit = v.replace(/\D/g, "").slice(-1);
    const next = [...code];
    next[i] = digit;
    setCode(next);
    if (digit && i < 5) otpRefs.current[i + 1]?.focus();
  }

  function onOtpKey(i: number, e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Backspace" && !code[i] && i > 0) otpRefs.current[i - 1]?.focus();
  }

  function onOtpPaste(e: React.ClipboardEvent) {
    const text = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (!text) return;
    e.preventDefault();
    const next = [...code];
    for (let i = 0; i < 6; i++) next[i] = text[i] ?? "";
    setCode(next);
    otpRefs.current[Math.min(text.length, 5)]?.focus();
  }

  async function verifyOtp(ev?: React.FormEvent) {
    ev?.preventDefault();
    const joined = code.join("");
    if (joined.length !== 6) {
      toast.error("Enter all six digits");
      return;
    }
    setBusy(true);
    try {
      await api.verifyOtp(form.email, joined);
      toast.success("Email verified. You can log in now.");
      router.push(`/login?email=${encodeURIComponent(form.email)}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Verification failed");
      setCode(["", "", "", "", "", ""]);
      otpRefs.current[0]?.focus();
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    if (secondsLeft > 0) return;
    try {
      await api.resendOtp(form.email);
      setSecondsLeft(60);
      toast.success("New code sent");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not resend");
    }
  }

  return (
    <main className="min-h-screen flex flex-col">
      <header className="px-4 sm:px-6 h-16 flex items-center justify-between max-w-6xl mx-auto w-full">
        <Link href="/" className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-brand-gradient grid place-items-center">
            <Dumbbell className="w-4 h-4 text-white" />
          </div>
          <span className="text-lg font-bold">Fitora</span>
        </Link>
        <Link href="/login" className="btn-ghost btn-sm">
          Already a member?
        </Link>
      </header>

      <div className="flex-1 grid place-items-center px-4 py-8">
        <div className="w-full max-w-md">
          <AnimatePresence mode="wait">
            {step === "form" ? (
              <motion.div
                key="form"
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -14 }}
                transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
              >
                <h1 className="text-2xl font-bold tracking-tight">Create your account</h1>
                <p className="text-sm text-ink-400 mt-1.5">
                  One account to discover, join and manage every gym membership.
                </p>

                <form onSubmit={submitForm} className="mt-7 space-y-4">
                  <Input
                    label="Full name"
                    icon={UserIcon}
                    placeholder="Praveen Kumar"
                    value={form.full_name}
                    onChange={set("full_name")}
                    error={errors.full_name}
                    autoComplete="name"
                  />
                  <Input
                    label="Email"
                    icon={Mail}
                    type="email"
                    placeholder="you@example.com"
                    value={form.email}
                    onChange={set("email")}
                    error={errors.email}
                    autoComplete="email"
                    hint="We'll send a 6-digit code here"
                  />
                  <Input
                    label="Phone"
                    icon={Phone}
                    type="tel"
                    inputMode="numeric"
                    placeholder="9876543210"
                    value={form.phone}
                    onChange={set("phone")}
                    error={errors.phone}
                    autoComplete="tel"
                  />

                  <div>
                    <Input
                      label="Address / area"
                      icon={MapPin}
                      placeholder="Main Road, Kakinada"
                      value={form.address}
                      onChange={set("address")}
                      error={errors.address}
                    />
                    <button
                      type="button"
                      onClick={useMyLocation}
                      disabled={locating}
                      className="mt-2 text-xs text-brand-400 hover:text-brand-300 disabled:opacity-60 inline-flex items-center gap-1.5"
                    >
                      <MapPin className="w-3 h-3" />
                      {locating
                        ? "Getting your location…"
                        : coords
                          ? `Location set (${coords.lat.toFixed(3)}, ${coords.lon.toFixed(3)})`
                          : "Use my current location for accurate distances"}
                    </button>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <Input
                      label="Password"
                      icon={Lock}
                      type="password"
                      placeholder="••••••••"
                      value={form.password}
                      onChange={set("password")}
                      error={errors.password}
                      autoComplete="new-password"
                    />
                    <Input
                      label="Confirm password"
                      icon={Lock}
                      type="password"
                      placeholder="••••••••"
                      value={form.confirm_password}
                      onChange={set("confirm_password")}
                      error={errors.confirm_password}
                      autoComplete="new-password"
                    />
                  </div>

                  <Button type="submit" loading={busy} className="w-full btn-lg">
                    Send verification code
                  </Button>
                </form>

                <p className="text-xs text-ink-500 text-center mt-6">
                  Running a gym instead?{" "}
                  <Link href="/owner/signup" className="text-brand-400 hover:text-brand-300">
                    Register as a partner
                  </Link>
                </p>
              </motion.div>
            ) : (
              <motion.div
                key="otp"
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -14 }}
                transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
              >
                <button
                  onClick={() => setStep("form")}
                  className="btn-ghost btn-sm -ml-3 mb-4"
                >
                  <ArrowLeft className="w-4 h-4" />
                  Back
                </button>

                <h1 className="text-2xl font-bold tracking-tight">Check your email</h1>
                <p className="text-sm text-ink-400 mt-1.5">
                  We sent a 6-digit code to{" "}
                  <span className="text-ink-200 font-medium">{form.email}</span>
                </p>

                <form onSubmit={verifyOtp} className="mt-8">
                  <div className="flex gap-2 justify-center" onPaste={onOtpPaste}>
                    {code.map((d, i) => (
                      <input
                        key={i}
                        ref={(el) => {
                          otpRefs.current[i] = el;
                        }}
                        value={d}
                        onChange={(e) => onOtpChange(i, e.target.value)}
                        onKeyDown={(e) => onOtpKey(i, e)}
                        inputMode="numeric"
                        maxLength={1}
                        aria-label={`Digit ${i + 1}`}
                        className="w-12 h-14 sm:w-14 sm:h-16 text-center text-2xl font-bold
                                   bg-ink-900 border border-ink-800 rounded-xl
                                   focus:outline-none focus:border-brand-500
                                   focus:ring-2 focus:ring-brand-500/20 transition-all"
                      />
                    ))}
                  </div>

                  <Button
                    type="submit"
                    loading={busy}
                    className="w-full btn-lg mt-7"
                    disabled={code.join("").length !== 6}
                  >
                    Verify and continue
                  </Button>
                </form>

                <div className="text-center mt-5">
                  <button
                    onClick={resend}
                    disabled={secondsLeft > 0}
                    className="text-sm text-ink-400 hover:text-brand-400 disabled:hover:text-ink-400 disabled:opacity-60"
                  >
                    {secondsLeft > 0
                      ? `Resend code in ${secondsLeft}s`
                      : "Didn't get it? Resend code"}
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </main>
  );
}
