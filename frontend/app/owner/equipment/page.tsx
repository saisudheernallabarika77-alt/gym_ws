"use client";

import {
  AlertTriangle, Building2, CreditCard, Dumbbell, LayoutDashboard,
  Plus, Star, Trash2, Users, Wallet,
} from "lucide-react";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { AppShell, PageHeader, type NavItem } from "@/components/AppShell";
import { Button, EmptyState, Input, Modal, Select, Textarea } from "@/components/ui";
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

const CATEGORIES = ["Cardio", "Free Weights", "Strength Machines", "Functional"];

export default function EquipmentPage() {
  const [data, setData] = useState<any>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    name: "", category: "Strength Machines", quantity: 1,
    description: "", image_url: "", condition: "Good",
  });

  function load() {
    ownerApi.equipment().then(setData);
  }
  useEffect(load, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await ownerApi.addEquipment(form);
      toast.success("Equipment added");
      setOpen(false);
      setForm({ name: "", category: "Strength Machines", quantity: 1, description: "", image_url: "", condition: "Good" });
      load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not add");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    try {
      await ownerApi.deleteEquipment(id);
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
          title="Equipment"
          subtitle={data ? `${data.total_items} items, ${data.total_units} units total` : undefined}
          action={
            <Button icon={Plus} onClick={() => setOpen(true)}>
              Add equipment
            </Button>
          }
        />

        {!data ? (
          <div className="skeleton h-64 w-full rounded-2xl" />
        ) : data.total_items === 0 ? (
          <EmptyState
            icon={Dumbbell}
            title="No equipment listed yet"
            description="Add your real equipment with photos — customers see exactly what you have."
            action={<Button icon={Plus} onClick={() => setOpen(true)}>Add your first item</Button>}
          />
        ) : (
          <div className="space-y-6">
            {Object.entries(data.categories).map(([cat, items]: [string, any]) => (
              <div key={cat}>
                <h3 className="font-semibold text-sm text-ink-300 mb-3">{cat}</h3>
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {items.map((it: any) => (
                    <div key={it.id} className="card p-4 flex gap-3">
                      <div className="w-12 h-12 rounded-lg bg-ink-800 grid place-items-center shrink-0">
                        <Dumbbell className="w-5 h-5 text-ink-500" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium truncate">{it.name}</p>
                        <p className="text-xs text-ink-500 mt-0.5">
                          Qty {it.quantity} · {it.condition}
                        </p>
                      </div>
                      <button
                        onClick={() => remove(it.id)}
                        className="text-ink-600 hover:text-danger shrink-0"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title="Add equipment">
        <form onSubmit={submit} className="space-y-4">
          <Input label="Equipment name" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} required placeholder="e.g. Smith Machine" />
          <Select label="Category" value={form.category} onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}>
            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </Select>
          <div className="grid grid-cols-2 gap-4">
            <Input label="Quantity" type="number" value={form.quantity} onChange={(e) => setForm((f) => ({ ...f, quantity: Number(e.target.value) }))} />
            <Select label="Condition" value={form.condition} onChange={(e) => setForm((f) => ({ ...f, condition: e.target.value }))}>
              <option>New</option><option>Excellent</option><option>Good</option>
            </Select>
          </div>
          <Textarea label="Description (optional)" value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} />
          <Input label="Image URL" value={form.image_url} onChange={(e) => setForm((f) => ({ ...f, image_url: e.target.value }))} hint="Upload a photo elsewhere and paste the link, or leave blank for now" />
          <Button type="submit" loading={busy} className="w-full">Add equipment</Button>
        </form>
      </Modal>
    </AppShell>
  );
}
