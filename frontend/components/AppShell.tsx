"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  CreditCard, Dumbbell, LogOut, type LucideIcon, Menu, X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { clearToken, getProfile, getToken } from "@/lib/api";
import { Avatar } from "@/components/ui";
import { cn } from "@/lib/utils";

export type NavItem = { href: string; label: string; icon: LucideIcon };

/**
 * Shared chrome for the three portals. `role` decides which token guards the
 * route and where a logged-out visitor is sent.
 */
export function AppShell({
  role,
  nav,
  loginPath,
  brandLabel,
  children,
}: {
  role: "user" | "gym_owner" | "admin";
  nav: NavItem[];
  loginPath: string;
  brandLabel?: string;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [profile, setProfileState] = useState<any>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const token = getToken(role);
    if (!token) {
      router.replace(loginPath);
      return;
    }
    setProfileState(getProfile(role));
    setChecked(true);
  }, [role, loginPath, router]);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  function logout() {
    clearToken(role);
    router.replace(loginPath);
  }

  if (!checked) {
    return (
      <div className="min-h-screen grid place-items-center">
        <div className="w-10 h-10 rounded-xl bg-brand-gradient animate-pulse" />
      </div>
    );
  }

  const displayName =
    profile?.full_name ?? profile?.business_name ?? "Account";

  return (
    <div className="min-h-screen flex flex-col">
      {/* ------------------------------------------------------------ top */}
      <header className="sticky top-0 z-40 glass border-b border-ink-800/70">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center gap-4">
          <button
            onClick={() => setOpen((o) => !o)}
            className="lg:hidden btn-ghost btn-sm -ml-2"
            aria-label="Menu"
          >
            {open ? <Menu className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>

          <Link href={nav[0]?.href ?? "/"} className="flex items-center gap-2 shrink-0">
            <div className="w-8 h-8 rounded-xl bg-brand-gradient grid place-items-center">
              <Dumbbell className="w-4 h-4 text-white" />
            </div>
            <div className="leading-tight">
              <span className="block text-base font-bold">Fitora</span>
              {brandLabel && (
                <span className="block text-[10px] text-ink-500 -mt-0.5">
                  {brandLabel}
                </span>
              )}
            </div>
          </Link>

          {/* desktop nav */}
          <nav className="hidden lg:flex items-center gap-1 ml-6">
            {nav.map((item) => {
              const active =
                pathname === item.href || pathname.startsWith(item.href + "/");
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "relative px-3.5 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2",
                    active
                      ? "text-white bg-ink-800/80"
                      : "text-ink-400 hover:text-ink-100 hover:bg-ink-800/50",
                  )}
                >
                  <item.icon className="w-4 h-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>

          <div className="ml-auto flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2.5">
              <Avatar name={displayName} src={profile?.photo_url} size={32} />
              <div className="leading-tight">
                <p className="text-sm font-medium truncate max-w-[140px]">
                  {displayName}
                </p>
                <p className="text-[10px] text-ink-500 truncate max-w-[140px]">
                  {profile?.email}
                </p>
              </div>
            </div>
            <button
              onClick={logout}
              className="btn-ghost btn-sm"
              title="Log out"
              aria-label="Log out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* mobile nav */}
        <AnimatePresence>
          {open && (
            <motion.nav
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
              className="lg:hidden overflow-hidden border-t border-ink-800"
            >
              <div className="px-3 py-3 space-y-1">
                {nav.map((item) => {
                  const active =
                    pathname === item.href || pathname.startsWith(item.href + "/");
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={cn(
                        "flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium",
                        active
                          ? "text-white bg-ink-800"
                          : "text-ink-300 hover:bg-ink-800/60",
                      )}
                    >
                      <item.icon className="w-4 h-4" />
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </motion.nav>
          )}
        </AnimatePresence>
      </header>

      <main className="flex-1">{children}</main>
    </div>
  );
}

/** Small helper used across dashboards for section titles. */
export function PageHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {subtitle && <p className="text-sm text-ink-400 mt-1">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
