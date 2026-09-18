"use client";

import { motion } from "framer-motion";
import {
  Building2, Check, Clock, CreditCard, MapPin, Phone, Snowflake, Wind,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import toast from "react-hot-toast";
import { Button, Input, Select, Textarea } from "@/components/ui";
import { ownerApi, ApiError } from "@/lib/api";
import { getLocation } from "@/lib/utils";

const FACILITY_OPTIONS = [
  "Changing Room", "Locker Facility", "Shower", "Drinking Water / RO", "Parking",
  "CCTV Surveillance", "Wi-Fi", "Music System", "Personal Training", "Group Classes",
  "Zumba / Aerobics", "Yoga Classes", "Steam Bath / Sauna", "Cardio Zone",
  "Diet Consultation", "Supplements Store", "Ladies Only Timing",
];

export default function OnboardingPage() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [locating, setLocating] = useState(false);
  const [step, setStep] = useState(1);

  const [form, setForm] = useState({
    name: "", description: "", gym_type: "Unisex",
    address_line: "", locality: "", district: "", pincode: "",
    latitude: 16.9891, longitude: 82.2475,
    phone: "", email: "",
    morning_open: "05:30", morning_close: "11:00",
    evening_open: "16:30", evening_close: "22:00",
    open_days: "Monday - Saturday", weekly_off: "Sunday",
    monthly_fee: 1200, registration_fee: 0,
    coach_included: false, coach_fee_separate: 800,
    trial_available: false, trial_days: 0,
    is_air_conditioned: false, supplements_available: false,
    facilities: [] as string[],
    established_year: new Date().getFullYear(),
  });

  function set<K extends keyof typeof form>(k: K, v: (typeof form)[K]) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  function toggleFacility(f: string) {
    set(
      "facilities",
      form.facilities.includes(f)
        ? form.facilities.filter((x) => x !== f)
        : [...form.facilities, f],
    );
  }

  async function useLocation() {
    setLocating(true);
    const loc = await getLocation();
    setLocating(false);
    if (loc) {
      set("latitude", loc.lat);
      set("longitude", loc.lon);
      toast.success("Location captured");
    } else {
      toast.error("Could not get location");
    }
  }

  async function submit() {
    if (!form.name || !form.address_line || !form.locality || !form.phone) {
      toast.error("Fill in the required fields");
      return;
    }
    setBusy(true);
    try {
      const res = await ownerApi.saveGym(form, true);
      toast.success(res.message ?? "Gym published!");
      router.push("/owner/dashboard");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save gym");
    } finally {
      setBusy(false);
    }
  }

  const steps = ["Basics", "Location & Timings", "Pricing", "Amenities"];

  return (
    <main className="min-h-screen">
      <header className="border-b border-ink-800 px-4 sm:px-6 h-16 flex items-center max-w-4xl mx-auto w-full">
        <div className="w-8 h-8 rounded-xl bg-brand-gradient grid place-items-center">
          <Building2 className="w-4 h-4 text-white" />
        </div>
        <span className="text-lg font-bold ml-2">Set up your gym</span>
      </header>

      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8 pb-24">
        <div className="flex items-center gap-2 mb-8">
          {steps.map((s, i) => (
            <div key={s} className="flex items-center gap-2 flex-1">
              <div
                className={`w-8 h-8 rounded-full grid place-items-center text-xs font-bold shrink-0 ${
                  step === i + 1
                    ? "bg-brand-gradient text-white"
                    : step > i + 1
                      ? "bg-success text-white"
                      : "bg-ink-800 text-ink-500"
                }`}
              >
                {step > i + 1 ? <Check className="w-4 h-4" /> : i + 1}
              </div>
              {i < steps.length - 1 && <div className="h-px flex-1 bg-ink-800" />}
            </div>
          ))}
        </div>

        <motion.div
          key={step}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-5"
        >
          {step === 1 && (
            <>
              <h2 className="font-semibold text-lg">Tell us about your gym</h2>
              <Input label="Gym name" value={form.name} onChange={(e) => set("name", e.target.value)} required />
              <Textarea
                label="Description"
                placeholder="What makes your gym special?"
                value={form.description}
                onChange={(e) => set("description", e.target.value)}
              />
              <Select label="Gym type" value={form.gym_type} onChange={(e) => set("gym_type", e.target.value)}>
                <option value="Unisex">Unisex</option>
                <option value="Men Only">Men Only</option>
                <option value="Ladies Only">Ladies Only</option>
              </Select>
              <Input
                label="Established year"
                type="number"
                value={form.established_year}
                onChange={(e) => set("established_year", Number(e.target.value))}
              />
            </>
          )}

          {step === 2 && (
            <>
              <h2 className="font-semibold text-lg">Location &amp; timings</h2>
              <Input label="Address" icon={MapPin} value={form.address_line} onChange={(e) => set("address_line", e.target.value)} required />
              <div className="grid grid-cols-2 gap-4">
                <Input label="Locality / area" value={form.locality} onChange={(e) => set("locality", e.target.value)} required />
                <Input label="District" value={form.district} onChange={(e) => set("district", e.target.value)} />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <Input label="Pincode" value={form.pincode} onChange={(e) => set("pincode", e.target.value)} />
                <Input label="Phone" icon={Phone} value={form.phone} onChange={(e) => set("phone", e.target.value)} required />
              </div>
              <button
                type="button"
                onClick={useLocation}
                disabled={locating}
                className="text-xs text-brand-400 hover:text-brand-300 inline-flex items-center gap-1.5"
              >
                <MapPin className="w-3 h-3" />
                {locating ? "Getting location…" : "Use my current location"}
              </button>

              <div className="grid grid-cols-2 gap-4 pt-2">
                <Input label="Morning open" icon={Clock} value={form.morning_open} onChange={(e) => set("morning_open", e.target.value)} placeholder="05:30" />
                <Input label="Morning close" value={form.morning_close} onChange={(e) => set("morning_close", e.target.value)} placeholder="11:00" />
                <Input label="Evening open" value={form.evening_open} onChange={(e) => set("evening_open", e.target.value)} placeholder="16:30" />
                <Input label="Evening close" value={form.evening_close} onChange={(e) => set("evening_close", e.target.value)} placeholder="22:00" />
              </div>
              <Input label="Weekly off" value={form.weekly_off} onChange={(e) => set("weekly_off", e.target.value)} placeholder="Sunday" />
            </>
          )}

          {step === 3 && (
            <>
              <h2 className="font-semibold text-lg">Pricing</h2>
              <Input
                label="Monthly membership fee (₹)"
                icon={CreditCard}
                type="number"
                value={form.monthly_fee}
                onChange={(e) => set("monthly_fee", Number(e.target.value))}
                required
              />
              <Input
                label="One-time registration fee (₹) — optional"
                type="number"
                value={form.registration_fee}
                onChange={(e) => set("registration_fee", Number(e.target.value))}
              />

              <label className="flex items-center gap-3 card p-4 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.coach_included}
                  onChange={(e) => set("coach_included", e.target.checked)}
                  className="w-4 h-4 rounded accent-brand-500"
                />
                <div>
                  <p className="text-sm font-medium">Coach fee included in membership</p>
                  <p className="text-xs text-ink-400">
                    If off, you'll set a separate coach charge below
                  </p>
                </div>
              </label>

              {!form.coach_included && (
                <Input
                  label="Personal coach fee (₹/month)"
                  type="number"
                  value={form.coach_fee_separate}
                  onChange={(e) => set("coach_fee_separate", Number(e.target.value))}
                />
              )}

              <label className="flex items-center gap-3 card p-4 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.trial_available}
                  onChange={(e) => set("trial_available", e.target.checked)}
                  className="w-4 h-4 rounded accent-brand-500"
                />
                <p className="text-sm font-medium">Offer a free trial</p>
              </label>
              {form.trial_available && (
                <Input
                  label="Trial days"
                  type="number"
                  value={form.trial_days}
                  onChange={(e) => set("trial_days", Number(e.target.value))}
                />
              )}
            </>
          )}

          {step === 4 && (
            <>
              <h2 className="font-semibold text-lg">Amenities</h2>
              <div className="grid grid-cols-2 gap-2.5">
                <button
                  type="button"
                  onClick={() => set("is_air_conditioned", !form.is_air_conditioned)}
                  className={`card p-3.5 flex items-center gap-2.5 text-sm font-medium transition-all ${
                    form.is_air_conditioned ? "border-brand-500 bg-brand-500/10" : ""
                  }`}
                >
                  {form.is_air_conditioned ? (
                    <Snowflake className="w-4 h-4 text-sky-400" />
                  ) : (
                    <Wind className="w-4 h-4 text-ink-500" />
                  )}
                  {form.is_air_conditioned ? "AC Gym" : "Non-AC Gym"}
                </button>
                <button
                  type="button"
                  onClick={() => set("supplements_available", !form.supplements_available)}
                  className={`card p-3.5 text-sm font-medium transition-all ${
                    form.supplements_available ? "border-brand-500 bg-brand-500/10" : ""
                  }`}
                >
                  Supplements sold here
                </button>
              </div>

              <div>
                <label className="label">Facilities</label>
                <div className="flex flex-wrap gap-2">
                  {FACILITY_OPTIONS.map((f) => (
                    <button
                      key={f}
                      type="button"
                      onClick={() => toggleFacility(f)}
                      className={`chip transition-all ${
                        form.facilities.includes(f)
                          ? "bg-brand-500/15 text-brand-300 border-brand-500/40"
                          : "chip-muted hover:border-ink-600"
                      }`}
                    >
                      {f}
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}
        </motion.div>

        <div className="flex gap-3 mt-8">
          {step > 1 && (
            <Button variant="secondary" onClick={() => setStep((s) => s - 1)}>
              Back
            </Button>
          )}
          {step < 4 ? (
            <Button className="flex-1" onClick={() => setStep((s) => s + 1)}>
              Continue
            </Button>
          ) : (
            <Button className="flex-1" loading={busy} onClick={submit}>
              Publish my gym
            </Button>
          )}
        </div>
      </div>
    </main>
  );
}
