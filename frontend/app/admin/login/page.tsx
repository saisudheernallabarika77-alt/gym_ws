"use client";

import { Lock, Mail, Shield } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import toast from "react-hot-toast";
import { Button, Input } from "@/components/ui";
import { adminApi, ApiError, setProfile, setToken } from "@/lib/api";

export default function AdminLoginPage() {
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
      const res = await adminApi.login(email.trim(), password);
      setToken("admin", res.access_token);
      setProfile("admin", res.profile);
      toast.success("Welcome back, admin");
      router.push("/admin/dashboard");
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
      <header className="px-4 sm:px-6 h-16 flex items-center max-w-6xl mx-auto w-full">
        <Link href="/" className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-ink-800 grid place-items-center border border-ink-700">
            <Shield className="w-4 h-4 text-brand-400" />
          </div>
          <span className="text-lg font-bold">Fitora Admin</span>
        </Link>
      </header>

      <div className="flex-1 grid place-items-center px-4 py-8">
        <div className="w-full max-w-sm">
          <h1 className="text-2xl font-bold tracking-tight">Admin login</h1>
          <p className="text-sm text-ink-400 mt-1.5">Full platform control.</p>

          <form onSubmit={submit} className="mt-7 space-y-4">
            <Input label="Email" icon={Mail} type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            <Input label="Password" icon={Lock} type="password" value={password} onChange={(e) => setPassword(e.target.value)} error={error} required />
            <Button type="submit" loading={busy} className="w-full btn-lg">Log in</Button>
          </form>
        </div>
      </div>
    </main>
  );
}
