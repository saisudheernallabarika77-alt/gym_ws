"use client";

import { motion } from "framer-motion";
import { Dumbbell, Lock, Mail } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import toast from "react-hot-toast";
import { api, ApiError, setProfile, setToken } from "@/lib/api";
import { Button, Input } from "@/components/ui";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState(params.get("email") ?? "");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await api.login(email.trim(), password);
      setToken("user", res.access_token);
      setProfile("user", res.profile);
      toast.success(`Welcome back, ${res.profile.full_name.split(" ")[0]}`);
      router.push("/chat");
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Login failed";
      setError(msg);
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      className="w-full max-w-md"
    >
      <h1 className="text-2xl font-bold tracking-tight">Welcome back</h1>
      <p className="text-sm text-ink-400 mt-1.5">
        Log in to find gyms, manage memberships and open your entry pass.
      </p>

      <form onSubmit={submit} className="mt-7 space-y-4">
        <Input
          label="Email"
          icon={Mail}
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            setError("");
          }}
          autoComplete="email"
          required
        />
        <Input
          label="Password"
          icon={Lock}
          type="password"
          placeholder="••••••••"
          value={password}
          onChange={(e) => {
            setPassword(e.target.value);
            setError("");
          }}
          error={error}
          autoComplete="current-password"
          required
        />

        <Button type="submit" loading={busy} className="w-full btn-lg">
          Log in
        </Button>
      </form>

      <p className="text-sm text-ink-400 text-center mt-6">
        New to Fitora?{" "}
        <Link href="/signup" className="text-brand-400 hover:text-brand-300 font-medium">
          Create an account
        </Link>
      </p>

      <div className="divider my-7" />

      <div className="flex justify-center gap-5 text-xs text-ink-500">
        <Link href="/owner/login" className="hover:text-ink-300">
          Gym partner login
        </Link>
        <Link href="/admin/login" className="hover:text-ink-300">
          Admin login
        </Link>
      </div>
    </motion.div>
  );
}

export default function LoginPage() {
  return (
    <main className="min-h-screen flex flex-col">
      <header className="px-4 sm:px-6 h-16 flex items-center justify-between max-w-6xl mx-auto w-full">
        <Link href="/" className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-brand-gradient grid place-items-center">
            <Dumbbell className="w-4 h-4 text-white" />
          </div>
          <span className="text-lg font-bold">Fitora</span>
        </Link>
        <Link href="/signup" className="btn-ghost btn-sm">
          Sign up
        </Link>
      </header>

      <div className="flex-1 grid place-items-center px-4 py-8">
        <Suspense fallback={<div className="skeleton h-96 w-full max-w-md rounded-2xl" />}>
          <LoginForm />
        </Suspense>
      </div>
    </main>
  );
}
