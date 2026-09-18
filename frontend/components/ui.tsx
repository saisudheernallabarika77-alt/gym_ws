"use client";

import { motion } from "framer-motion";
import { Loader2, type LucideIcon } from "lucide-react";
import React from "react";
import { cn, avatarTint, initials } from "@/lib/utils";

/* ------------------------------------------------------------------ Button */
type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  icon?: LucideIcon;
};

export function Button({
  variant = "primary",
  size = "md",
  loading,
  icon: Icon,
  className,
  children,
  disabled,
  ...rest
}: ButtonProps) {
  const variants = {
    primary: "btn-primary",
    secondary: "btn-secondary",
    ghost: "btn-ghost",
    danger: "btn-danger",
  };
  return (
    <button
      className={cn(variants[variant], `btn-${size}`, className)}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? (
        <Loader2 className="w-4 h-4 animate-spin" />
      ) : Icon ? (
        <Icon className="w-4 h-4" />
      ) : null}
      {children}
    </button>
  );
}

/* ------------------------------------------------------------------- Input */
type InputProps = React.InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
  error?: string;
  hint?: string;
  icon?: LucideIcon;
};

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  function Input({ label, error, hint, icon: Icon, className, ...rest }, ref) {
    return (
      <div>
        {label && <label className="label">{label}</label>}
        <div className="relative">
          {Icon && (
            <Icon className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-500 pointer-events-none" />
          )}
          <input
            ref={ref}
            className={cn(
              "input",
              Icon && "pl-10",
              error && "border-danger/60 focus:border-danger focus:ring-danger/20",
              className,
            )}
            {...rest}
          />
        </div>
        {error ? (
          <p className="field-error">{error}</p>
        ) : hint ? (
          <p className="text-xs text-ink-500 mt-1.5">{hint}</p>
        ) : null}
      </div>
    );
  },
);

/* ------------------------------------------------------------------ Select */
type SelectProps = React.SelectHTMLAttributes<HTMLSelectElement> & {
  label?: string;
  error?: string;
};

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  function Select({ label, error, className, children, ...rest }, ref) {
    return (
      <div>
        {label && <label className="label">{label}</label>}
        <select
          ref={ref}
          className={cn("input appearance-none cursor-pointer", className)}
          {...rest}
        >
          {children}
        </select>
        {error && <p className="field-error">{error}</p>}
      </div>
    );
  },
);

/* ---------------------------------------------------------------- Textarea */
export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement> & { label?: string; error?: string }
>(function Textarea({ label, error, className, ...rest }, ref) {
  return (
    <div>
      {label && <label className="label">{label}</label>}
      <textarea ref={ref} className={cn("input resize-y min-h-[88px]", className)} {...rest} />
      {error && <p className="field-error">{error}</p>}
    </div>
  );
});

/* -------------------------------------------------------------------- Chip */
export function Chip({
  tone = "muted",
  icon: Icon,
  children,
  className,
}: {
  tone?: "brand" | "muted" | "success" | "warning" | "danger";
  icon?: LucideIcon;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span className={cn(`chip-${tone}`, className)}>
      {Icon && <Icon className="w-3 h-3" />}
      {children}
    </span>
  );
}

/* ------------------------------------------------------------------ Avatar */
export function Avatar({
  name,
  src,
  size = 40,
  className,
}: {
  name: string;
  src?: string | null;
  size?: number;
  className?: string;
}) {
  const [failed, setFailed] = React.useState(false);
  const show = src && !failed;

  return (
    <div
      className={cn(
        "rounded-full overflow-hidden flex items-center justify-center font-semibold shrink-0",
        !show && avatarTint(name),
        className,
      )}
      style={{ width: size, height: size, fontSize: size * 0.36 }}
    >
      {show ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src!}
          alt={name}
          className="w-full h-full object-cover"
          onError={() => setFailed(true)}
        />
      ) : (
        initials(name)
      )}
    </div>
  );
}

/* -------------------------------------------------------------- StatTile */
export function StatTile({
  label,
  value,
  sub,
  icon: Icon,
  tone = "default",
  delay = 0,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  icon?: LucideIcon;
  tone?: "default" | "brand" | "success" | "warning" | "danger";
  delay?: number;
}) {
  const tones = {
    default: "text-ink-100",
    brand: "text-brand-400",
    success: "text-success",
    warning: "text-warning",
    danger: "text-danger",
  };
  const iconTones = {
    default: "bg-ink-800 text-ink-400",
    brand: "bg-brand-500/15 text-brand-400",
    success: "bg-success/15 text-success",
    warning: "bg-warning/15 text-warning",
    danger: "bg-danger/15 text-danger",
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay, ease: [0.16, 1, 0.3, 1] }}
      className="card p-4 sm:p-5"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs text-ink-400 font-medium truncate">{label}</p>
          <p className={cn("text-2xl font-bold mt-1.5 tabular-nums", tones[tone])}>
            {value}
          </p>
          {sub && <p className="text-xs text-ink-500 mt-1 truncate">{sub}</p>}
        </div>
        {Icon && (
          <div className={cn("p-2.5 rounded-xl shrink-0", iconTones[tone])}>
            <Icon className="w-5 h-5" />
          </div>
        )}
      </div>
    </motion.div>
  );
}

/* ------------------------------------------------------------ EmptyState */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-16 px-6">
      {Icon && (
        <div className="p-4 rounded-2xl bg-ink-800/70 mb-4">
          <Icon className="w-7 h-7 text-ink-500" />
        </div>
      )}
      <h3 className="font-semibold text-ink-100">{title}</h3>
      {description && (
        <p className="text-sm text-ink-400 mt-1.5 max-w-sm">{description}</p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

/* -------------------------------------------------------------- Skeleton */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} />;
}

export function CardSkeleton() {
  return (
    <div className="card p-4 space-y-3">
      <Skeleton className="h-32 w-full rounded-xl" />
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-3 w-1/2" />
      <div className="flex gap-2 pt-1">
        <Skeleton className="h-6 w-16 rounded-full" />
        <Skeleton className="h-6 w-20 rounded-full" />
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------- Modal */
export function Modal({
  open,
  onClose,
  title,
  children,
  wide,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  wide?: boolean;
}) {
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />
      <motion.div
        initial={{ opacity: 0, y: 24, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
        className={cn(
          "relative glass rounded-t-3xl sm:rounded-2xl w-full max-h-[90vh] overflow-y-auto",
          wide ? "sm:max-w-2xl" : "sm:max-w-md",
        )}
      >
        <div className="sticky top-0 z-10 flex items-center justify-between px-5 py-4 border-b border-ink-800 bg-ink-900/90 backdrop-blur-xl rounded-t-3xl sm:rounded-t-2xl">
          <h3 className="font-semibold">{title}</h3>
          <button
            onClick={onClose}
            className="text-ink-400 hover:text-white text-xl leading-none px-2 -mr-2"
            aria-label="Close"
          >
            ×
          </button>
        </div>
        <div className="p-5">{children}</div>
      </motion.div>
    </div>
  );
}

/* ----------------------------------------------------------------- Toast */
export function Banner({
  tone = "info",
  children,
}: {
  tone?: "info" | "success" | "warning" | "danger";
  children: React.ReactNode;
}) {
  const tones = {
    info: "bg-sky-500/10 border-sky-500/25 text-sky-200",
    success: "bg-success/10 border-success/25 text-emerald-200",
    warning: "bg-warning/10 border-warning/25 text-amber-200",
    danger: "bg-danger/10 border-danger/25 text-red-200",
  };
  return (
    <div className={cn("rounded-xl border px-4 py-3 text-sm", tones[tone])}>
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ Tabs */
export function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: { key: string; label: string; count?: number }[];
  active: string;
  onChange: (key: string) => void;
}) {
  return (
    <div className="flex gap-1 overflow-x-auto no-scrollbar border-b border-ink-800">
      {tabs.map((t) => (
        <button
          key={t.key}
          onClick={() => onChange(t.key)}
          className={cn(
            "relative px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-colors",
            active === t.key ? "text-white" : "text-ink-400 hover:text-ink-200",
          )}
        >
          {t.label}
          {t.count != null && (
            <span className="ml-1.5 text-xs text-ink-500">({t.count})</span>
          )}
          {active === t.key && (
            <motion.div
              layoutId="tab-underline"
              className="absolute left-2 right-2 -bottom-px h-0.5 bg-brand-gradient rounded-full"
            />
          )}
        </button>
      ))}
    </div>
  );
}
