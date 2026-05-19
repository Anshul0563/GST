"use client";

import Link from "next/link";
import type { Route } from "next";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Building2, CreditCard, FileJson, FileSpreadsheet, Home, LockKeyhole, Menu, Moon, ReceiptText, Repeat2, Settings, ShieldCheck, Sun, UploadCloud } from "lucide-react";
import { BillingPlan, Profile, getBillingPlans } from "@/lib/api";

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
      { href: "/modules/online-seller/marketplaces", label: "Upload History", icon: UploadCloud }
    ]
  },
  reconcile: {
    title: "2A/2B Reconcile",
    icon: Repeat2,
    items: [
      { href: "/modules/reconcile", label: "Mini Dashboard", icon: Home },
      { href: "/modules/reconcile/upload", label: "Upload & Reconcile", icon: UploadCloud },
      { href: "/modules/reconcile/results", label: "Match Results", icon: ReceiptText },
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
      { href: "/modules/tally/export", label: "Voucher Preview & XML", icon: FileSpreadsheet },
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

type AppShellUser = {
  id: number;
  email: string;
  full_name?: string | null;
  role?: string;
  plan?: string;
  subscription_status?: string;
  subscription_expires_at?: string | null;
  free_access_reason?: string | null;
} | null;

function hasPaidAccess(user: AppShellUser, requiredPlan?: string) {
  if (!user) return false;
  if (user.role === "admin" || user.role === "super_admin" || user.plan === "admin_free") return true;
  if (user.subscription_status !== "active") return false;
  if (!requiredPlan) return true;
  return user.plan === requiredPlan;
}

export function AppShell({ title, subtitle, profile, profiles, onProfileChange, actions, token, user, requiresSubscription = false, requiredPlan, productName, children }: {
  title: string;
  subtitle?: string;
  profile: Profile | null;
  profiles: Profile[];
  onProfileChange?: (profile: Profile) => void;
  actions?: React.ReactNode;
  token?: string;
  user?: AppShellUser;
  requiresSubscription?: boolean;
  requiredPlan?: string;
  productName?: string;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const activeModule = pathname.startsWith("/modules/online-seller") ? "onlineSeller" : pathname.startsWith("/modules/reconcile") ? "reconcile" : pathname.startsWith("/modules/tally") ? "tally" : "";
  const activeModuleConfig = activeModule ? moduleNav[activeModule] : null;
  const currentItem = pathname === "/modules/online-seller/profile"
    ? { href: "/modules/online-seller/profile" as Route, label: "GST Profile", icon: ShieldCheck }
    : activeModuleConfig?.items.find((item) => pathname === item.href || pathname.startsWith(`${item.href}/`));
  const ActiveModuleIcon = activeModuleConfig?.icon;
  const pageContext = currentItem?.label || activeModuleConfig?.title || "Product Suite";
  const workspaceName = profile?.trade_name || profile?.legal_name || "Workspace";
  const workspaceInitial = workspaceName.trim().charAt(0).toUpperCase() || "G";
  const locked = requiresSubscription && !hasPaidAccess(user ?? null, requiredPlan);
  function logout() {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem("gst_bharat_token");
    }
    setProfileMenuOpen(false);
    router.push("/login");
  }
  useEffect(() => {
    const stored = typeof window !== "undefined" ? window.localStorage.getItem("gst_bharat_theme") : null;
    const nextTheme = stored === "dark" ? "dark" : "light";
    setTheme(nextTheme);
    document.documentElement.classList.toggle("dark", nextTheme === "dark");
  }, []);

  function toggleTheme() {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    document.documentElement.classList.toggle("dark", nextTheme === "dark");
    window.localStorage.setItem("gst_bharat_theme", nextTheme);
  }
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
              <button onClick={toggleTheme} aria-label="Toggle color theme" className="grid size-10 place-items-center rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-white/10 dark:bg-slate-900">{theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}</button>
              <div className="relative hidden sm:block">
                <button onClick={() => setProfileMenuOpen((open) => !open)} className="flex max-w-64 items-center gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-2 shadow-sm transition hover:border-[#1746A2]/40 dark:border-white/10 dark:bg-slate-900">
                  <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-saffron to-rose-500 font-black text-white">{workspaceInitial}</span>
                  <span className="min-w-0 text-left">
                    <span className="block truncate text-sm font-black">{workspaceName}</span>
                    <span className="block truncate text-xs font-semibold text-slate-500">{profile?.gstin || user?.email || "GSTIN not set"}</span>
                  </span>
                </button>
                {profileMenuOpen && <div className="absolute right-0 mt-2 w-56 overflow-hidden rounded-2xl border border-slate-200 bg-white p-2 shadow-2xl shadow-slate-200/70 dark:border-white/10 dark:bg-slate-950 dark:shadow-none">
                  <Link onClick={() => setProfileMenuOpen(false)} href="/modules/online-seller/profile" className="block rounded-xl px-3 py-2 text-sm font-bold text-slate-700 hover:bg-slate-50 dark:text-slate-200 dark:hover:bg-white/10">GST Profile</Link>
                  <Link onClick={() => setProfileMenuOpen(false)} href="/billing" className="block rounded-xl px-3 py-2 text-sm font-bold text-slate-700 hover:bg-slate-50 dark:text-slate-200 dark:hover:bg-white/10">Billing</Link>
                  <button onClick={logout} className="block w-full rounded-xl px-3 py-2 text-left text-sm font-bold text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-500/10">Logout</button>
                </div>}
              </div>
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
            {!locked && actions}
          </div>
          {locked ? <SubscriptionGate token={token || ""} user={user ?? null} productName={productName || activeModuleConfig?.title || title} requiredPlan={requiredPlan} /> : children}
        </main>
      </div>
    </div>
  );
}

function CalendarMini() {
  return <span className="grid size-7 shrink-0 place-items-center rounded-xl bg-[#1746A2]/10 text-[10px] font-black text-[#1746A2]">FP</span>;
}

function SubscriptionGate({ token, user, productName, requiredPlan }: { token: string; user: AppShellUser; productName: string; requiredPlan?: string }) {
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!token) return;
    setLoading(true);
    getBillingPlans(token)
      .then((result) => setPlans(requiredPlan ? result.plans.filter((plan) => plan.id === requiredPlan) : result.plans))
      .catch(() => setPlans([]))
      .finally(() => setLoading(false));
  }, [token, requiredPlan]);

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-xl shadow-slate-200/60 dark:border-white/10 dark:bg-slate-950 dark:shadow-none">
        <div className="grid gap-6 p-6 lg:grid-cols-[1fr_0.8fr] lg:p-8">
          <div>
            <div className="mb-5 inline-flex items-center gap-2 rounded-full bg-amber-50 px-3 py-1 text-xs font-black uppercase tracking-wide text-amber-700">
              <LockKeyhole className="size-3.5" /> Subscription required
            </div>
            <h2 className="text-2xl font-black tracking-tight md:text-3xl">{productName} is a paid GST Bharat module</h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-500 dark:text-slate-400">
              2A/2B Reconcile remains available. Subscribe to unlock marketplace GST filing tools and Tally XML workflows.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link href="/billing" className="inline-flex items-center gap-2 rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white"><CreditCard className="size-4" /> View pricing</Link>
              <Link href="/modules/reconcile" className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-5 py-3 text-sm font-bold text-slate-700 dark:border-white/10 dark:bg-slate-900 dark:text-slate-200">Open 2A/2B Reconcile</Link>
            </div>
          </div>
          <div className="rounded-3xl bg-slate-50 p-5 dark:bg-white/5">
            <div className="text-xs font-black uppercase tracking-[0.18em] text-slate-500">Account status</div>
            <div className="mt-4 grid gap-3 text-sm">
              <AccessRow label="Email" value={user?.email || "Login required"} />
              <AccessRow label="Plan" value={user?.plan || "free"} />
              <AccessRow label="Status" value={user?.subscription_status || "inactive"} />
              <AccessRow label="Renews/Expires" value={user?.subscription_expires_at ? new Date(user.subscription_expires_at).toLocaleDateString() : "--"} />
            </div>
          </div>
        </div>
      </section>
      <section className="grid gap-4 lg:grid-cols-3">
        {loading ? <div className="rounded-3xl border border-slate-200 bg-white p-5 text-sm font-bold text-slate-500 dark:border-white/10 dark:bg-slate-950">Loading pricing...</div> : plans.map((plan) => (
          <div key={plan.id} className="rounded-3xl border border-slate-200 bg-white p-5 shadow-xl shadow-slate-200/60 dark:border-white/10 dark:bg-slate-950 dark:shadow-none">
            <h3 className="text-xl font-black">{plan.name}</h3>
            <div className="mt-4 grid gap-3 text-sm">
              <div className="rounded-2xl bg-slate-50 p-4 dark:bg-white/5"><b>Monthly</b><p className="mt-1 text-2xl font-black">₹{plan.monthly_amount.toLocaleString("en-IN")}</p></div>
              <div className="rounded-2xl bg-slate-50 p-4 dark:bg-white/5"><b>Yearly</b><p className="mt-1 text-2xl font-black">₹{plan.yearly_amount.toLocaleString("en-IN")}</p></div>
            </div>
            <div className="mt-4 space-y-2 text-sm text-slate-500">{plan.features.slice(0, 4).map((feature) => <p key={feature}>- {feature}</p>)}</div>
          </div>
        ))}
        {!loading && !plans.length ? <div className="rounded-3xl border border-slate-200 bg-white p-5 text-sm font-bold text-slate-500 dark:border-white/10 dark:bg-slate-950">Pricing will load after login.</div> : null}
      </section>
    </div>
  );
}

function AccessRow({ label, value }: { label: string; value: string }) {
  return <div className="flex items-center justify-between gap-3 rounded-2xl bg-white px-4 py-3 dark:bg-slate-900"><span className="text-slate-500">{label}</span><b className="break-all text-right">{value}</b></div>;
}
