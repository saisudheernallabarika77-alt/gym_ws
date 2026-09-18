import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Indian rupee formatting — no decimals, lakh/crore grouping. */
export function rupees(n: number | null | undefined): string {
  if (n == null) return "—";
  return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

export function compactRupees(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 10_000_000) return `₹${(n / 10_000_000).toFixed(1)}Cr`;
  if (n >= 100_000) return `₹${(n / 100_000).toFixed(1)}L`;
  if (n >= 1_000) return `₹${(n / 1_000).toFixed(1)}K`;
  return rupees(n);
}

export function km(n: number | null | undefined): string {
  if (n == null) return "";
  if (n < 1) return `${Math.round(n * 1000)} m`;
  return `${n.toFixed(1)} km`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function initials(name: string | null | undefined): string {
  if (!name) return "?";
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join("");
}

/** Deterministic avatar colour so the same person keeps the same tint. */
export function avatarTint(seed: string): string {
  const palette = [
    "bg-brand-500/20 text-brand-300",
    "bg-emerald-500/20 text-emerald-300",
    "bg-sky-500/20 text-sky-300",
    "bg-violet-500/20 text-violet-300",
    "bg-amber-500/20 text-amber-300",
    "bg-rose-500/20 text-rose-300",
  ];
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  return palette[h % palette.length];
}

/** Ask the browser for a location fix; resolves null if denied or unavailable. */
export function getLocation(): Promise<{ lat: number; lon: number } | null> {
  return new Promise((resolve) => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      resolve(null);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
      () => resolve(null),
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 600_000 },
    );
  });
}

export const GOAL_LABELS: Record<string, string> = {
  weight_loss: "Weight Loss",
  muscle_gain: "Muscle Gain",
  strength: "Strength",
  general_fitness: "General Fitness",
  endurance: "Endurance",
  rehabilitation: "Rehabilitation",
};

export const STATUS_TONE: Record<string, string> = {
  active: "chip-success",
  due: "chip-warning",
  overdue: "chip-danger",
  expired: "chip-muted",
  cancelled: "chip-muted",
  removed: "chip-danger",
  pending_payment: "chip-warning",
  blocked: "chip-danger",
  pending_verification: "chip-warning",
  deleted: "chip-muted",
  draft: "chip-muted",
  suspended: "chip-danger",
  paid: "chip-success",
  scheduled: "chip-warning",
  processing: "chip-warning",
  success: "chip-success",
  failed: "chip-danger",
};
