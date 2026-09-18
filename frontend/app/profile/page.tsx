"use client";

import {
  CreditCard, MessageSquare, Ruler, Save, Search, Target, User, Weight,
} from "lucide-react";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { AppShell, PageHeader, type NavItem } from "@/components/AppShell";
import { Avatar, Button, Input, Select } from "@/components/ui";
import { api, ApiError, getProfile, setProfile } from "@/lib/api";
import { GOAL_LABELS } from "@/lib/utils";

const NAV: NavItem[] = [
  { href: "/chat", label: "Find a gym", icon: MessageSquare },
  { href: "/gyms", label: "Browse", icon: Search },
  { href: "/memberships", label: "My memberships", icon: CreditCard },
  { href: "/profile", label: "Profile", icon: User },
];

export default function ProfilePage() {
  const [form, setForm] = useState<any>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.me().then((p) => setForm(p));
  }, []);

  function set(k: string, v: any) {
    setForm((f: any) => ({ ...f, [k]: v }));
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const res = await api.updateProfile({
        full_name: form.full_name,
        phone: form.phone,
        address: form.address,
        height_cm: form.height_cm ? Number(form.height_cm) : undefined,
        weight_kg: form.weight_kg ? Number(form.weight_kg) : undefined,
        fitness_goal: form.fitness_goal || undefined,
        emergency_contact_name: form.emergency_contact_name,
        emergency_contact_phone: form.emergency_contact_phone,
      });
      setProfile("user", res.profile);
      toast.success("Profile updated");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  if (!form) {
    return (
      <AppShell role="user" nav={NAV} loginPath="/login">
        <div className="max-w-2xl mx-auto px-4 py-10">
          <div className="skeleton h-64 w-full rounded-2xl" />
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell role="user" nav={NAV} loginPath="/login">
      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8">
        <PageHeader title="Your profile" subtitle="Kept up to date, this pre-fills every gym you join" />

        <div className="flex items-center gap-4 mb-7">
          <Avatar name={form.full_name} src={form.photo_url} size={64} />
          <div>
            <p className="font-semibold">{form.full_name}</p>
            <p className="text-sm text-ink-400">{form.email}</p>
          </div>
        </div>

        <form onSubmit={save} className="space-y-4">
          <div className="grid sm:grid-cols-2 gap-4">
            <Input
              label="Full name"
              value={form.full_name ?? ""}
              onChange={(e) => set("full_name", e.target.value)}
            />
            <Input
              label="Phone"
              value={form.phone ?? ""}
              onChange={(e) => set("phone", e.target.value)}
            />
          </div>

          <Input
            label="Address"
            value={form.address ?? ""}
            onChange={(e) => set("address", e.target.value)}
          />

          <div className="grid sm:grid-cols-2 gap-4">
            <Input
              label="Height (cm)"
              icon={Ruler}
              type="number"
              value={form.height_cm ?? ""}
              onChange={(e) => set("height_cm", e.target.value)}
            />
            <Input
              label="Weight (kg)"
              icon={Weight}
              type="number"
              value={form.weight_kg ?? ""}
              onChange={(e) => set("weight_kg", e.target.value)}
            />
          </div>

          <Select
            label="Fitness goal"
            value={form.fitness_goal ?? ""}
            onChange={(e) => set("fitness_goal", e.target.value)}
          >
            <option value="">Not set</option>
            {Object.entries(GOAL_LABELS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </Select>

          <div className="grid sm:grid-cols-2 gap-4">
            <Input
              label="Emergency contact name"
              value={form.emergency_contact_name ?? ""}
              onChange={(e) => set("emergency_contact_name", e.target.value)}
            />
            <Input
              label="Emergency contact phone"
              value={form.emergency_contact_phone ?? ""}
              onChange={(e) => set("emergency_contact_phone", e.target.value)}
            />
          </div>

          <Button type="submit" loading={busy} icon={Save}>
            Save changes
          </Button>
        </form>
      </div>
    </AppShell>
  );
}
