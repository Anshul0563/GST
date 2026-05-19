"use client";

import Link from "next/link";
import type { Route } from "next";
import { usePathname } from "next/navigation";
import { Bell, Building2, ChevronDown, CreditCard, FileJson, FileSpreadsheet, Home, Menu, Moon, ReceiptText, Repeat2, Search, Settings, ShieldCheck, UploadCloud, UserCircle } from "lucide-react";
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
      { href: "/modules/online-seller/profile", label: "GST Profile", icon: UserCircle },
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
  const activeModule = pathname.startsWith("/modules/online-seller") ? "onlineSeller" : pathname.startsWith("/modules/reconcile") ? "reconcile" : pathname.startsWith("/modules/tally") ? "tally" : "";
  const activeModuleConfig = activeModule ? moduleNav[activeModule] : null;
  const currentItem = activeModuleConfig?.items.find((item) => pathname === item.href || pathname.startsWith(`${item.href}/`));
  const ActiveModuleIcon = activeModuleConfig?.icon;
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

export function ClassicToolShell({ title, crumb, active, profile, children }: {
  title: string;
  crumb: string;
  active: "dashboard" | "profile" | "imports" | "manage" | "gstr1";
  profile: Profile | null;
  children: React.ReactNode;
}) {
  const sideItems: Array<{ key: typeof active; href: Route; label: string; icon: typeof Home }> = [
    { key: "profile", href: "/profile", label: "GST Profile", icon: UserCircle },
    { key: "imports", href: "/marketplaces", label: "Import Data", icon: UploadCloud },
    { key: "manage", href: "/transactions", label: "Manage Data", icon: ReceiptText },
    { key: "gstr1", href: "/gstr1", label: "GSTR1 Report", icon: FileJson }
  ];
  return <div className="min-h-screen bg-[#f3f7fc] text-slate-950">
    <header className="h-14 border-b border-slate-200 bg-white">
      <div className="mx-auto flex h-full max-w-6xl items-center justify-between px-5">
        <Link href="/dashboard" className="flex items-center gap-2">
          <span className="text-2xl font-black tracking-tight text-[#10244d]">GST</span>
          <span className="-ml-1 rounded-sm bg-saffron px-1.5 py-0.5 text-xs font-black text-white">BHARAT</span>
        </Link>
        <nav className="hidden items-center gap-8 text-xs font-bold text-slate-500 md:flex">
          <Link className={active === "dashboard" ? "text-rose-500" : ""} href="/dashboard">Dashboard</Link>
          <Link href="/marketplaces">Our Tools</Link>
          <Link href="/transactions">Screenshot</Link>
          <Link href="/settings">Support</Link>
          <span className="grid size-8 place-items-center rounded-full bg-rose-500 font-black text-white">P</span>
        </nav>
      </div>
    </header>
    <section className="relative bg-[#162d59] text-white">
      <div className="absolute inset-0 opacity-20 [background-image:linear-gradient(135deg,rgba(255,255,255,.2)_1px,transparent_1px)] [background-size:32px_32px]" />
      <div className="relative mx-auto flex min-h-44 max-w-6xl items-start justify-between px-5 py-8">
        <div>
          <h1 className="text-2xl font-black">{title}</h1>
          <p className="mt-3 text-sm font-semibold text-white/85">Home <span className="px-2 text-white/45">/</span> Dashboard <span className="px-2 text-white/45">/</span> <span className="text-blue-300">{crumb}</span></p>
        </div>
        {profile && <div className="hidden rounded bg-white/10 px-5 py-3 text-xs font-bold md:block">
          <div>GSTIN: {profile.gstin}</div>
          <div className="mt-1">Period: {profile.return_period}</div>
        </div>}
      </div>
    </section>
    <main className="mx-auto -mt-9 grid max-w-6xl gap-5 px-5 pb-12 md:grid-cols-[215px_1fr]">
      <aside className="h-fit rounded-md bg-white p-7 shadow-xl shadow-slate-200/80">
        <Link href="/dashboard" className={`mb-5 block border-b border-slate-200 pb-5 text-center text-base font-black ${active === "dashboard" ? "text-[#2f72ff]" : "text-slate-600"}`}>Dashboard</Link>
        <p className="mb-4 text-xs font-black uppercase text-slate-800">GST Online Seller</p>
        <nav className="space-y-1">
          {sideItems.map((item) => {
            const Icon = item.icon;
            const isActive = active === item.key;
            return <Link key={item.key} href={item.href} className={`flex items-center gap-3 border-l-2 px-3 py-2 text-sm font-semibold ${isActive ? "border-[#2f72ff] bg-blue-50 text-[#2f72ff]" : "border-transparent text-slate-700 hover:bg-slate-50"}`}>
              <Icon className="size-4 text-slate-400" /> {item.label}
            </Link>;
          })}
        </nav>
      </aside>
      <div className="space-y-6">{children}</div>
    </main>
  </div>;
}
