"use client";

import { Building2, Lock, Mail } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import toast from "react-hot-toast";
import { Button, Input } from "@/components/ui";
import { ownerApi, ApiError, setProfile, setToken } from "@/lib/api";

export default function OwnerLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await ownerApi.login(email.trim(), password);
      setToken("gym_owner", res.access_token);
      setProfile("gym_owner", res.profile);
      toast.success(`Welcome, ${res.profile.full_name.split(" ")[0]}`);
      router.push(res.profile.needs_onboarding ? "/owner/onboarding" : "/owner/dashboard");
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Login failed";
      setError(msg);
      toast.error(msg);
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
        <Link href="/owner/signup" className="btn-ghost btn-sm">
          Register your gym
        </Link>
      </header>

      <div className="flex-1 grid place-items-center px-4 py-8">
        <div className="w-full max-w-md">
          <h1 className="text-2xl font-bold tracking-tight">Gym partner login</h1>
          <p className="text-sm text-ink-400 mt-1.5">
            Manage your gym profile, pricing, coaches and members.
          </p>

          <form onSubmit={submit} className="mt-7 space-y-4">
            <Input
              label="Email"
              icon={Mail}
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <Input
              label="Password"
              icon={Lock}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              error={error}
              required
            />
            <Button type="submit" loading={busy} className="w-full btn-lg">
              Log in
            </Button>
          </form>

          <p className="text-sm text-ink-400 text-center mt-6">
            Don't have a partner account?{" "}
            <Link href="/owner/signup" className="text-brand-400 hover:text-brand-300 font-medium">
              Register your gym
            </Link>
          </p>

          <div className="divider my-7" />
          <div className="flex justify-center gap-5 text-xs text-ink-500">
            <Link href="/login" className="hover:text-ink-300">Member login</Link>
            <Link href="/admin/login" className="hover:text-ink-300">Admin login</Link>
          </div>
        </div>
      </div>
    </main>
  );
}
