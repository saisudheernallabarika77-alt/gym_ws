"use client";

import {
  AlertTriangle, BadgeCheck, Building2, LayoutDashboard, MapPin,
  MessageSquareWarning, Plus, Search, Snowflake, Users, Wallet, Wind,
} from "lucide-react";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { AppShell, PageHeader, type NavItem } from "@/components/AppShell";
import { Button, Chip, EmptyState, Input, Modal, Select, Textarea } from "@/components/ui";
import { adminApi, ApiError } from "@/lib/api";
import { rupees } from "@/lib/utils";

const NAV: NavItem[] = [
  { href: "/admin/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/admin/users", label: "Users", icon: Users },
  { href: "/admin/gyms", label: "Gyms", icon: Building2 },
  { href: "/admin/dues", label: "Dues", icon: AlertTriangle },
  { href: "/admin/payouts", label: "Payouts", icon: Wallet },
  { href: "/admin/complaints", label: "Complaints", icon: MessageSquareWarning },
];

const FACILITY_OPTIONS = [
  "Changing Room", "Locker Facility", "Shower", "Drinking Water / RO", "Parking",
  "CCTV Surveillance", "Personal Training", "Cardio Zone",
];

const emptyForm = {
  name: "", description: "", gym_type: "Unisex",
  address_line: "", locality: "", district: "", pincode: "",
  latitude: 16.9891, longitude: 82.2475,
  phone: "", email: "",
  morning_open: "05:30", morning_close: "11:00",
  evening_open: "16:30", evening_close: "22:00",
  open_days: "Monday - Saturday", weekly_off: "Sunday",
  monthly_fee: 1000, registration_fee: 0,
  coach_included: false, coach_fee_separate: 700,
  trial_available: false, trial_days: 0,
  is_air_conditioned: false, supplements_available: false,
  facilities: [] as string[],
  established_year: new Date().getFullYear(),
  create_owner_account: false,
  owner_name: "", owner_email: "", owner_phone: "", owner_password: "",
  publish: true,
};

export default function AdminGymsPage() {
  const [gyms, setGyms] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState(emptyForm);

  function load() {
    setLoading(true);
    adminApi.gyms({ q: q || undefined, page_size: 50 })
      .then((r) => { setGyms(r.gyms); setTotal(r.total); })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    const t = setTimeout(load, 300);
    return () => clearTimeout(t);
  }, [q]);

  function set<K extends keyof typeof form>(k: K, v: (typeof form)[K]) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  function toggleFacility(f: string) {
    set("facilities", form.facilities.includes(f) ? form.facilities.filter((x) => x !== f) : [...form.facilities, f]);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name || !form.address_line || !form.locality || !form.phone) {
      toast.error("Fill in the required fields");
      return;
    }
    setBusy(true);
    try {
      const res = await adminApi.createGym(form);
      toast.success(res.message ?? "Gym added");
      setOpen(false);
      setForm(emptyForm);
      load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not add gym");
    } finally {
      setBusy(false);
    }
  }

  async function suspend(g: any) {
    const reason = prompt(`Reason for suspending ${g.name}?`);
    if (!reason) return;
    try {
      await adminApi.suspendGym(g.id, reason);
      toast.success("Gym suspended");
      load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not suspend");
    }
  }

  async function approve(g: any) {
    try {
      await adminApi.approveGym(g.id);
      toast.success("Gym approved and live");
      load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not approve");
    }
  }

  return (
    <AppShell role="admin" nav={NAV} loginPath="/admin/login" brandLabel="Admin">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        <PageHeader
          title="Gyms"
          subtitle={`${total} listed`}
          action={<Button icon={Plus} onClick={() => setOpen(true)}>Add gym manually</Button>}
        />

        <div className="relative mb-5 max-w-sm">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-500" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name or area" className="input pl-10" />
        </div>

        {loading ? (
          <div className="skeleton h-64 w-full rounded-2xl" />
        ) : gyms.length === 0 ? (
          <EmptyState icon={Building2} title="No gyms found" />
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {gyms.map((g) => (
              <div key={g.id} className="card p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <p className="font-medium text-sm truncate">{g.name}</p>
                      {g.verified && <BadgeCheck className="w-3.5 h-3.5 text-brand-400 shrink-0" />}
                    </div>
                    <p className="text-xs text-ink-500 flex items-center gap-1 mt-0.5">
                      <MapPin className="w-3 h-3" /> {g.locality}
                    </p>
                  </div>
                  {g.ac_status === "AC" ? (
                    <Snowflake className="w-4 h-4 text-sky-400 shrink-0" />
                  ) : (
                    <Wind className="w-4 h-4 text-ink-500 shrink-0" />
                  )}
                </div>

                <div className="flex items-center gap-2 mt-3">
                  <p className="font-bold text-sm">{rupees(g.monthly_fee)}/mo</p>
                  <Chip tone="muted" className="text-[10px]">{g.member_count} members</Chip>
                </div>

                <div className="flex items-center gap-1.5 mt-2">
                  <Chip tone={g.status === "active" ? "success" : g.status === "suspended" ? "danger" : "warning"} className="text-[10px]">
                    {g.status}
                  </Chip>
                  {g.indexed_in_rag && <Chip tone="brand" className="text-[10px]">In chatbot</Chip>}
                  {g.created_by_admin && <Chip tone="muted" className="text-[10px]">Admin-added</Chip>}
                  <Chip
                    tone={g.data_source === "openstreetmap" ? "success" : "muted"}
                    className="text-[10px]"
                  >
                    {g.data_source === "openstreetmap" ? "Real (OSM)" : "Demo data"}
                  </Chip>
                </div>

                <div className="flex gap-1.5 mt-3">
                  {g.status !== "active" ? (
                    <Button size="sm" variant="secondary" className="flex-1" onClick={() => approve(g)}>Approve</Button>
                  ) : (
                    <Button size="sm" variant="secondary" className="flex-1" onClick={() => suspend(g)}>Suspend</Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title="Add a gym manually" wide>
        <form onSubmit={submit} className="space-y-5">
          <p className="text-xs text-ink-500">
            Use this for gyms without a partner account yet — e.g. a gym in a village. It goes
            live in the chatbot immediately when published.
          </p>

          <div className="grid sm:grid-cols-2 gap-4">
            <Input label="Gym name" value={form.name} onChange={(e) => set("name", e.target.value)} required />
            <Select label="Gym type" value={form.gym_type} onChange={(e) => set("gym_type", e.target.value)}>
              <option value="Unisex">Unisex</option>
              <option value="Men Only">Men Only</option>
              <option value="Ladies Only">Ladies Only</option>
            </Select>
          </div>
          <Textarea label="Description" value={form.description} onChange={(e) => set("description", e.target.value)} />

          <div className="grid sm:grid-cols-2 gap-4">
            <Input label="Address" value={form.address_line} onChange={(e) => set("address_line", e.target.value)} required />
            <Input label="Locality / village" value={form.locality} onChange={(e) => set("locality", e.target.value)} required />
            <Input label="District" value={form.district} onChange={(e) => set("district", e.target.value)} />
            <Input label="Pincode" value={form.pincode} onChange={(e) => set("pincode", e.target.value)} />
            <Input label="Latitude" type="number" step="0.0001" value={form.latitude} onChange={(e) => set("latitude", Number(e.target.value))} />
            <Input label="Longitude" type="number" step="0.0001" value={form.longitude} onChange={(e) => set("longitude", Number(e.target.value))} />
            <Input label="Phone" value={form.phone} onChange={(e) => set("phone", e.target.value)} required />
            <Input label="Email (optional)" value={form.email} onChange={(e) => set("email", e.target.value)} />
          </div>

          <div className="grid sm:grid-cols-2 gap-4">
            <Input label="Monthly fee (₹)" type="number" value={form.monthly_fee} onChange={(e) => set("monthly_fee", Number(e.target.value))} required />
            <Input label="Coach fee (₹/mo, if separate)" type="number" value={form.coach_fee_separate} onChange={(e) => set("coach_fee_separate", Number(e.target.value))} />
          </div>

          <label className="flex items-center gap-3 card p-3">
            <input type="checkbox" checked={form.coach_included} onChange={(e) => set("coach_included", e.target.checked)} className="w-4 h-4 accent-brand-500" />
            <span className="text-sm">Coach included in membership</span>
          </label>
          <label className="flex items-center gap-3 card p-3">
            <input type="checkbox" checked={form.is_air_conditioned} onChange={(e) => set("is_air_conditioned", e.target.checked)} className="w-4 h-4 accent-brand-500" />
            <span className="text-sm">Air conditioned</span>
          </label>

          <div>
            <label className="label">Facilities</label>
            <div className="flex flex-wrap gap-2">
              {FACILITY_OPTIONS.map((f) => (
                <button key={f} type="button" onClick={() => toggleFacility(f)}
                  className={`chip ${form.facilities.includes(f) ? "bg-brand-500/15 text-brand-300 border-brand-500/40" : "chip-muted"}`}>
                  {f}
                </button>
              ))}
            </div>
          </div>

          <label className="flex items-center gap-3 card p-3">
            <input type="checkbox" checked={form.create_owner_account} onChange={(e) => set("create_owner_account", e.target.checked)} className="w-4 h-4 accent-brand-500" />
            <span className="text-sm">Create a partner login for this gym now</span>
          </label>

          {form.create_owner_account && (
            <div className="grid sm:grid-cols-2 gap-4">
              <Input label="Owner name" value={form.owner_name} onChange={(e) => set("owner_name", e.target.value)} />
              <Input label="Owner email" value={form.owner_email} onChange={(e) => set("owner_email", e.target.value)} />
              <Input label="Owner phone" value={form.owner_phone} onChange={(e) => set("owner_phone", e.target.value)} />
              <Input label="Owner password" type="password" value={form.owner_password} onChange={(e) => set("owner_password", e.target.value)} />
            </div>
          )}

          <Button type="submit" loading={busy} className="w-full btn-lg">Publish gym</Button>
        </form>
      </Modal>
    </AppShell>
  );
}
