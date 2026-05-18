"use client";

import Link from "next/link";
import type { Route } from "next";
import { usePathname } from "next/navigation";
import { Bell, Building2, ChevronDown, CreditCard, FileJson, Home, Menu, Moon, PackageSearch, ReceiptText, Repeat2, Search, Settings, ShieldCheck, UploadCloud, UserCircle } from "lucide-react";
import { Profile } from "@/lib/api";

const nav: Array<{ href: Route; label: string; icon: typeof Home }> = [
  { href: "/dashboard", label: "Dashboard", icon: Home },
  { href: "/marketplaces", label: "Marketplaces", icon: PackageSearch },
  { href: "/imports", label: "Imports", icon: UploadCloud },
  { href: "/transactions", label: "Transactions", icon: ReceiptText },
  { href: "/gstr1", label: "GSTR-1", icon: FileJson },
  { href: "/reconcile", label: "2A/2B Reconcile", icon: Repeat2 },
  { href: "/tally", label: "eCom to Tally", icon: Building2 },
  { href: "/profile", label: "GST Profiles", icon: UserCircle },
  { href: "/settings", label: "Settings", icon: Settings },
  { href: "/billing", label: "Billing", icon: CreditCard }
];

export function LogoMark() {
  return (
    <div className="flex items-center gap-3">
      <div className="grid size-10 place-items-center rounded-2xl bg-gradient-to-br from-[#10244d] via-[#1746A2] to-[#0F9F6E] font-black text-white shadow-lg shadow-blue-950/20">GB</div>
      <div>
        <p className="text-lg font-black tracking-tight text-slate-950 dark:text-white">GST Bharat</p>
        <p className="-mt-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-saffron">eCom GST OS</p>
      </div>
    </div>
  );
}

export function AppShell({ title, subtitle, profile, profiles, onProfileChange, actions, children }: {
  title: string;
  subtitle?: string;
  profile: Profile | null;
  profiles: Profile[];
  onProfileChange?: (profile: Profile) => void;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  return (
    <div className="min-h-screen bg-[#f6f8fb] text-slate-950 dark:bg-[#07111f] dark:text-white">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-72 border-r border-white/70 bg-white/90 p-5 shadow-2xl shadow-slate-200/60 backdrop-blur-xl dark:border-white/10 dark:bg-slate-950/80 dark:shadow-none lg:block">
        <LogoMark />
        <div className="mt-7 rounded-3xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-4 dark:border-white/10 dark:from-slate-900 dark:to-slate-950">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-500"><ShieldCheck className="size-4 text-emerald-600" /> Workspace</div>
          <select
            value={profile?.id || ""}
            onChange={(event) => {
              const next = profiles.find((item) => item.id === Number(event.target.value));
              if (next) onProfileChange?.(next);
            }}
            className="mt-3 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm font-bold text-slate-900 outline-none dark:border-white/10 dark:bg-slate-900 dark:text-white"
          >
            {profiles.map((item) => <option key={item.id} value={item.id}>{item.trade_name || item.legal_name}</option>)}
          </select>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-500">
            <span className="rounded-xl bg-white px-3 py-2 dark:bg-slate-900">{profile?.gstin || "No GSTIN"}</span>
            <span className="rounded-xl bg-white px-3 py-2 dark:bg-slate-900">FP {profile?.return_period || "--"}</span>
          </div>
        </div>
        <nav className="mt-6 space-y-1">
          {nav.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href;
            return (
              <Link key={item.href} href={item.href} className={`group flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-semibold transition ${active ? "bg-[#10244d] text-white shadow-lg shadow-blue-950/20" : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-white/10"}`}>
                <Icon className={`size-4 ${active ? "text-saffron" : "text-slate-400 group-hover:text-[#1746A2]"}`} />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <div className="lg:pl-72">
        <header className="sticky top-0 z-20 border-b border-white/70 bg-white/75 backdrop-blur-xl dark:border-white/10 dark:bg-slate-950/70">
          <div className="flex h-20 items-center justify-between px-5 lg:px-8">
            <div className="flex items-center gap-4">
              <button className="grid size-10 place-items-center rounded-2xl border border-slate-200 bg-white lg:hidden"><Menu className="size-5" /></button>
              <div className="hidden items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm text-slate-500 shadow-sm dark:border-white/10 dark:bg-slate-900 md:flex">
                <Search className="size-4" />
                Search invoices, GSTIN, imports
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button className="hidden items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-600 shadow-sm dark:border-white/10 dark:bg-slate-900 md:flex">
                {profile?.return_period || "Period"} <ChevronDown className="size-4" />
              </button>
              <button className="grid size-10 place-items-center rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-white/10 dark:bg-slate-900"><Moon className="size-4" /></button>
              <button className="relative grid size-10 place-items-center rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-white/10 dark:bg-slate-900"><Bell className="size-4" /><span className="absolute right-2 top-2 size-2 rounded-full bg-saffron" /></button>
              <div className="grid size-10 place-items-center rounded-2xl bg-gradient-to-br from-saffron to-rose-500 font-black text-white">P</div>
            </div>
          </div>
        </header>
        <main className="px-5 py-7 lg:px-8">
          <div className="mb-7 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[#1746A2] dark:text-sky-300">GST Bharat Workspace</p>
              <h1 className="mt-2 text-3xl font-black tracking-tight md:text-4xl">{title}</h1>
              {subtitle && <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500 dark:text-slate-400">{subtitle}</p>}
            </div>
            {actions}
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}
