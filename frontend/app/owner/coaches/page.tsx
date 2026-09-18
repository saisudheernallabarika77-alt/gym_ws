"use client";

import {
  AlertTriangle, CreditCard, Dumbbell, LayoutDashboard, Plus, Star, Trash2, Users, Wallet,
} from "lucide-react";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { AppShell, PageHeader, type NavItem } from "@/components/AppShell";
import { Avatar, Button, EmptyState, Input, Modal, Select, Textarea } from "@/components/ui";
import { ownerApi, ApiError } from "@/lib/api";

const NAV: NavItem[] = [
  { href: "/owner/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/owner/equipment", label: "Equipment", icon: Dumbbell },
  { href: "/owner/coaches", label: "Coaches", icon: Users },
  { href: "/owner/members", label: "Members", icon: Users },
  { href: "/owner/dues", label: "Dues", icon: AlertTriangle },
  { href: "/owner/earnings", label: "Earnings", icon: Wallet },
  { href: "/owner/reviews", label: "Reviews", icon: Star },
];

const SPECS = [
  "Strength & Conditioning", "Weight Loss", "Bodybuilding", "CrossFit",
  "Functional Training", "Powerlifting", "Yoga & Flexibility", "HIIT & Cardio",
];

export default function CoachesPage() {
  const [coaches, setCoaches] = useState<any[]>([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    name: "", gender: "Male", experience_years: 1,
    specialisations: [] as string[], certifications: [] as string[],
    bio: "", photo_url: "",
  });

  function load() {
    ownerApi.coaches().then((r) => setCoaches(r.coaches));
  }
  useEffect(load, []);

  function toggleSpec(s: string) {
    setForm((f) => ({
      ...f,
      specialisations: f.specialisations.includes(s)
        ? f.specialisations.filter((x) => x !== s)
        : [...f.specialisations, s],
    }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await ownerApi.addCoach(form);
      toast.success("Coach added");
      setOpen(false);
      setForm({ name: "", gender: "Male", experience_years: 1, specialisations: [], certifications: [], bio: "", photo_url: "" });
      load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not add coach");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    try {
      await ownerApi.deleteCoach(id);
      toast.success("Removed");
      load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not remove");
    }
  }

  return (
    <AppShell role="gym_owner" nav={NAV} loginPath="/owner/login" brandLabel="Partner Portal">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8">
        <PageHeader
          title="Coaches"
          subtitle={`${coaches.length} coaches listed`}
          action={<Button icon={Plus} onClick={() => setOpen(true)}>Add coach</Button>}
        />

        {coaches.length === 0 ? (
          <EmptyState
            icon={Users}
            title="No coaches listed yet"
            action={<Button icon={Plus} onClick={() => setOpen(true)}>Add your first coach</Button>}
          />
        ) : (
          <div className="grid sm:grid-cols-2 gap-3">
            {coaches.map((c) => (
              <div key={c.id} className="card p-4 flex gap-3.5">
                <Avatar name={c.name} src={c.photo_url} size={48} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-medium text-sm">{c.name}</p>
                    <span className="text-xs text-ink-500">{c.experience_years} yrs</span>
                  </div>
                  <p className="text-xs text-ink-400 mt-1">{c.specialisations.join(", ")}</p>
                </div>
                <button onClick={() => remove(c.id)} className="text-ink-600 hover:text-danger">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title="Add coach">
        <form onSubmit={submit} className="space-y-4">
          <Input label="Coach name" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} required />
          <div className="grid grid-cols-2 gap-4">
            <Select label="Gender" value={form.gender} onChange={(e) => setForm((f) => ({ ...f, gender: e.target.value }))}>
              <option>Male</option><option>Female</option>
            </Select>
            <Input label="Experience (years)" type="number" value={form.experience_years} onChange={(e) => setForm((f) => ({ ...f, experience_years: Number(e.target.value) }))} />
          </div>
          <div>
            <label className="label">Specialisations</label>
            <div className="flex flex-wrap gap-2">
              {SPECS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => toggleSpec(s)}
                  className={`chip transition-all ${form.specialisations.includes(s) ? "bg-brand-500/15 text-brand-300 border-brand-500/40" : "chip-muted"}`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
          <Textarea label="Bio (optional)" value={form.bio} onChange={(e) => setForm((f) => ({ ...f, bio: e.target.value }))} />
          <Button type="submit" loading={busy} className="w-full">Add coach</Button>
        </form>
      </Modal>
    </AppShell>
  );
}
