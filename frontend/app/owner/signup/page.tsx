"use client";

import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, Building2, Lock, Mail, Phone, User as UserIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { Button, Input } from "@/components/ui";
import { ownerApi, ApiError } from "@/lib/api";

type Step = "form" | "otp";

export default function OwnerSignupPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("form");
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [form, setForm] = useState({
    full_name: "", email: "", phone: "", business_name: "",
    password: "", confirm_password: "",
  });
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
    setErrors((p) => ({ ...p, [k]: "" }));
  };

  function validate() {
    const e: Record<string, string> = {};
    if (form.full_name.trim().length < 2) e.full_name = "Enter your name";
    if (!/^\S+@\S+\.\S+$/.test(form.email)) e.email = "Enter a valid email";
    if (form.phone.replace(/\D/g, "").length < 10) e.phone = "Enter a 10-digit number";
    if (form.business_name.trim().length < 2) e.business_name = "Enter your gym's name";
    if (form.password.length < 6) e.password = "At least 6 characters";
    if (form.password !== form.confirm_password) e.confirm_password = "Passwords do not match";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function submitForm(ev: React.FormEvent) {
    ev.preventDefault();
    if (!validate()) return;
    setBusy(true);
    try {
      await ownerApi.signup(form);
      setStep("otp");
      setSecondsLeft(60);
      toast.success(`Verification code sent to ${form.email}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Signup failed");
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

  async function verifyOtp(ev: React.FormEvent) {
    ev.preventDefault();
    const joined = code.join("");
    if (joined.length !== 6) return toast.error("Enter all six digits");
    setBusy(true);
    try {
      await ownerApi.verifyOtp(form.email, joined);
      toast.success("Verified! Log in to set up your gym.");
      router.push(`/owner/login`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Verification failed");
      setCode(["", "", "", "", "", ""]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen flex flex-col">
      <header className="px-4 sm:px-6 h-16 flex items-center justify-between max-w-6xl mx-auto w-full">
        <Link href="/" className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-brand-gradient grid place-items-center">
            <Building2 className="w-4 h-4 text-white" />
          </div>
          <span className="text-lg font-bold">Fitora Partners</span>
        </Link>
        <Link href="/owner/login" className="btn-ghost btn-sm">Already registered?</Link>
      </header>

      <div className="flex-1 grid place-items-center px-4 py-8">
        <div className="w-full max-w-md">
          <AnimatePresence mode="wait">
            {step === "form" ? (
              <motion.div key="form" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -14 }}>
                <h1 className="text-2xl font-bold tracking-tight">List your gym on Fitora</h1>
                <p className="text-sm text-ink-400 mt-1.5">
                  Reach members across the Kakinada region. Set up your profile in minutes.
                </p>

                <form onSubmit={submitForm} className="mt-7 space-y-4">
                  <Input label="Your name" icon={UserIcon} value={form.full_name} onChange={set("full_name")} error={errors.full_name} />
                  <Input label="Gym / business name" icon={Building2} value={form.business_name} onChange={set("business_name")} error={errors.business_name} />
                  <Input label="Email" icon={Mail} type="email" value={form.email} onChange={set("email")} error={errors.email} hint="We'll send a 6-digit code here" />
                  <Input label="Phone" icon={Phone} type="tel" value={form.phone} onChange={set("phone")} error={errors.phone} />
                  <div className="grid grid-cols-2 gap-4">
                    <Input label="Password" icon={Lock} type="password" value={form.password} onChange={set("password")} error={errors.password} />
                    <Input label="Confirm password" icon={Lock} type="password" value={form.confirm_password} onChange={set("confirm_password")} error={errors.confirm_password} />
                  </div>
                  <Button type="submit" loading={busy} className="w-full btn-lg">Send verification code</Button>
                </form>
              </motion.div>
            ) : (
              <motion.div key="otp" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -14 }}>
                <button onClick={() => setStep("form")} className="btn-ghost btn-sm -ml-3 mb-4">
                  <ArrowLeft className="w-4 h-4" /> Back
                </button>
                <h1 className="text-2xl font-bold tracking-tight">Check your email</h1>
                <p className="text-sm text-ink-400 mt-1.5">Code sent to {form.email}</p>

                <form onSubmit={verifyOtp} className="mt-8">
                  <div className="flex gap-2 justify-center">
                    {code.map((d, i) => (
                      <input
                        key={i}
                        ref={(el) => { otpRefs.current[i] = el; }}
                        value={d}
                        onChange={(e) => onOtpChange(i, e.target.value)}
                        onKeyDown={(e) => onOtpKey(i, e)}
                        inputMode="numeric"
                        maxLength={1}
                        className="w-12 h-14 sm:w-14 sm:h-16 text-center text-2xl font-bold bg-ink-900 border border-ink-800 rounded-xl focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20"
                      />
                    ))}
                  </div>
                  <Button type="submit" loading={busy} className="w-full btn-lg mt-7" disabled={code.join("").length !== 6}>
                    Verify and continue
                  </Button>
                </form>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </main>
  );
}
