"use client";

import Link from "next/link";
import type { Route } from "next";
import { usePathname, useRouter } from "next/navigation";
import { Building2, CreditCard, FileJson, FileSpreadsheet, Home, Menu, Moon, ReceiptText, Repeat2, Search, Settings, ShieldCheck, UploadCloud } from "lucide-react";
import { Profile } from "@/lib/api";

const nav: Array<{ href: Route; label: string; icon: typeof Home }> = [
  { href: "/dashboard", label: "Dashboard", icon: Home },
  { href: "/settings", label: "Settings", icon: Settings },
  { href: "/billing", label: "Billing", icon: CreditCard }
];

const moduleNav: Record<string, { title: string; icon: typeof Home; items: Array<{ href: Route; label: string; icon: typeof Home }> }> = {
  onlineSeller: {
    title: "GST Online Seller",
    icon: ReceiptText,
    items: [
      { href: "/modules/online-seller", label: "Mini Dashboard", icon: Home },
      { href: "/modules/online-seller/marketplaces", label: "Marketplace Upload", icon: UploadCloud },
      { href: "/modules/online-seller/manage-data", label: "Manage Data", icon: ReceiptText },
      { href: "/modules/online-seller/gstr1", label: "GSTR-1 Preview", icon: FileJson },
      { href: "/modules/online-seller/gstr1", label: "JSON Export", icon: FileJson },
      { href: "/modules/online-seller/gstr1", label: "Excel Export", icon: FileSpreadsheet },
      { href: "/modules/online-seller/reports", label: "Reports", icon: FileSpreadsheet },
      { href: "/modules/online-seller/marketplaces", label: "Upload History", icon: UploadCloud }
    ]
  },
  reconcile: {
    title: "2A/2B Reconcile",
    icon: Repeat2,
    items: [
      { href: "/modules/reconcile", label: "Mini Dashboard", icon: Home },
      { href: "/modules/reconcile/upload", label: "Upload 2A/2B", icon: UploadCloud },
      { href: "/modules/reconcile/upload", label: "Upload Purchase Register", icon: FileSpreadsheet },
      { href: "/modules/reconcile/upload", label: "Reconcile", icon: Repeat2 },
      { href: "/modules/reconcile/results", label: "Match Results", icon: ReceiptText },
      { href: "/modules/reconcile/results", label: "Mismatch Explorer", icon: Search },
      { href: "/modules/reconcile/reports", label: "ITC Risk Report", icon: ShieldCheck },
      { href: "/modules/reconcile/reports", label: "Download Excel", icon: FileSpreadsheet },
      { href: "/modules/reconcile/reports", label: "Reconciliation History", icon: ReceiptText }
    ]
  },
  tally: {
    title: "eCom to Tally",
    icon: Building2,
    items: [
      { href: "/modules/tally", label: "Mini Dashboard", icon: Home },
      { href: "/modules/tally/company", label: "Tally Company", icon: Building2 },
      { href: "/modules/tally/import", label: "Marketplace Import", icon: UploadCloud },
      { href: "/modules/tally/mapping", label: "Ledger Mapping", icon: ReceiptText },
      { href: "/modules/tally/export", label: "Voucher Preview", icon: FileSpreadsheet },
      { href: "/modules/tally/export", label: "XML Generate", icon: FileJson },
      { href: "/modules/tally/export", label: "XML Download", icon: FileSpreadsheet },
      { href: "/modules/tally/history", label: "Export History", icon: ReceiptText }
    ]
  }
};

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
  const router = useRouter();
  const activeModule = pathname.startsWith("/modules/online-seller") ? "onlineSeller" : pathname.startsWith("/modules/reconcile") ? "reconcile" : pathname.startsWith("/modules/tally") ? "tally" : "";
  const activeModuleConfig = activeModule ? moduleNav[activeModule] : null;
  const currentItem = pathname === "/modules/online-seller/profile"
    ? { href: "/modules/online-seller/profile" as Route, label: "GST Profile", icon: ShieldCheck }
    : activeModuleConfig?.items.find((item) => pathname === item.href || pathname.startsWith(`${item.href}/`));
  const ActiveModuleIcon = activeModuleConfig?.icon;
  const pageContext = currentItem?.label || activeModuleConfig?.title || "Product Suite";
  const workspaceName = profile?.trade_name || profile?.legal_name || "Workspace";
  const workspaceInitial = workspaceName.trim().charAt(0).toUpperCase() || "G";
  return (
    <div className="min-h-screen bg-[#f6f8fb] text-slate-950 dark:bg-[#07111f] dark:text-white">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-72 border-r border-white/70 bg-white/90 p-5 shadow-2xl shadow-slate-200/60 backdrop-blur-xl dark:border-white/10 dark:bg-slate-950/80 dark:shadow-none lg:block">
        <LogoMark />
        <div
          role="button"
          tabIndex={0}
          onClick={() => router.push("/modules/online-seller/profile")}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") router.push("/modules/online-seller/profile");
          }}
          className="mt-7 cursor-pointer rounded-3xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-4 transition hover:-translate-y-0.5 hover:border-[#1746A2]/40 hover:shadow-xl hover:shadow-slate-200/70 dark:border-white/10 dark:from-slate-900 dark:to-slate-950 dark:hover:shadow-none"
        >
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-500"><ShieldCheck className="size-4 text-emerald-600" /> Workspace</div>
            <span className="rounded-full bg-[#1746A2]/10 px-2.5 py-1 text-[10px] font-black uppercase tracking-wide text-[#1746A2]">Edit</span>
          </div>
          <select
            value={profile?.id || ""}
            onClick={(event) => event.stopPropagation()}
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
          <p className="mt-3 text-[11px] font-semibold text-slate-500">Click to set GSTIN, filing period and Monthly/Quarterly.</p>
        </div>
        <nav className="mt-6 space-y-1">
          {nav.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(`${item.href}/`));
            return (
              <Link key={item.href} href={item.href} className={`group flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-semibold transition ${active ? "bg-[#10244d] text-white shadow-lg shadow-blue-950/20" : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-white/10"}`}>
                <Icon className={`size-4 ${active ? "text-saffron" : "text-slate-400 group-hover:text-[#1746A2]"}`} />
                {item.label}
              </Link>
            );
          })}
        </nav>
        {activeModuleConfig && <div className="mt-7 rounded-3xl border border-slate-200 bg-slate-50 p-4 dark:border-white/10 dark:bg-white/5">
          <div className="mb-3 flex items-center gap-2 text-xs font-black uppercase tracking-[0.18em] text-slate-500">
            {ActiveModuleIcon && <ActiveModuleIcon className="size-4 text-[#1746A2]" />}
            {activeModuleConfig.title}
          </div>
          <nav className="space-y-1">
            {activeModuleConfig.items.map((item) => {
              const Icon = item.icon;
              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
              return <Link key={`${item.href}-${item.label}`} href={item.href} className={`group flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm font-semibold transition ${active ? "bg-white text-[#10244d] shadow-sm dark:bg-slate-900 dark:text-white" : "text-slate-600 hover:bg-white dark:text-slate-300 dark:hover:bg-slate-900"}`}>
                <Icon className={`size-4 ${active ? "text-saffron" : "text-slate-400 group-hover:text-[#1746A2]"}`} />
                {item.label}
              </Link>;
            })}
          </nav>
        </div>}
      </aside>
      <div className="lg:pl-72">
        <header className="sticky top-0 z-20 border-b border-white/70 bg-white/75 backdrop-blur-xl dark:border-white/10 dark:bg-slate-950/70">
          <div className="flex h-20 items-center justify-between px-5 lg:px-8">
            <div className="flex min-w-0 items-center gap-4">
              <button className="grid size-10 place-items-center rounded-2xl border border-slate-200 bg-white lg:hidden"><Menu className="size-5" /></button>
              <div className="hidden min-w-0 md:block">
                <p className="text-xs font-black uppercase tracking-[0.18em] text-slate-400">Current View</p>
                <div className="mt-1 flex min-w-0 items-center gap-2 text-sm font-black text-slate-800 dark:text-white">
                  {ActiveModuleIcon && <ActiveModuleIcon className="size-4 shrink-0 text-[#1746A2]" />}
                  <span className="truncate">{activeModuleConfig ? `${activeModuleConfig.title} / ${pageContext}` : pageContext}</span>
                </div>
              </div>
            </div>
            <div className="flex min-w-0 items-center gap-3">
              <Link href="/modules/online-seller/profile" className="hidden items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-600 shadow-sm transition hover:border-[#1746A2]/40 hover:text-[#1746A2] dark:border-white/10 dark:bg-slate-900 dark:text-slate-300 md:flex">
                <CalendarMini />
                <span>{profile?.return_period || "Set period"}</span>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-black uppercase text-slate-500 dark:bg-white/10">{profile?.filing_frequency || "Mode"}</span>
              </Link>
              <button className="grid size-10 place-items-center rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-white/10 dark:bg-slate-900"><Moon className="size-4" /></button>
              <Link href="/modules/online-seller/profile" className="hidden max-w-64 items-center gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-2 shadow-sm transition hover:border-[#1746A2]/40 dark:border-white/10 dark:bg-slate-900 sm:flex">
                <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-saffron to-rose-500 font-black text-white">{workspaceInitial}</span>
                <span className="min-w-0 text-left">
                  <span className="block truncate text-sm font-black">{workspaceName}</span>
                  <span className="block truncate text-xs font-semibold text-slate-500">{profile?.gstin || "GSTIN not set"}</span>
                </span>
              </Link>
            </div>
          </div>
        </header>
        <main className="px-5 py-7 lg:px-8">
          <div className="mb-5 flex flex-wrap items-center gap-2 text-sm font-bold text-slate-500">
            <Link href="/dashboard" className="text-[#1746A2]">Dashboard</Link>
            {activeModuleConfig && <><span>/</span><Link href={activeModuleConfig.items[0].href} className="text-[#1746A2]">{activeModuleConfig.title}</Link></>}
            {activeModuleConfig && currentItem && currentItem.href !== activeModuleConfig.items[0].href && <><span>/</span><span>{currentItem.label}</span></>}
          </div>
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

function CalendarMini() {
  return <span className="grid size-7 shrink-0 place-items-center rounded-xl bg-[#1746A2]/10 text-[10px] font-black text-[#1746A2]">FP</span>;
}
