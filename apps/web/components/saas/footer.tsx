import Link from "next/link";
import type { Route } from "next";
import { FileJson, ReceiptText, Repeat2, ShieldCheck } from "lucide-react";

type FooterUser = {
  role?: string;
  plan?: string;
  subscription_status?: string;
} | null;

const productLinks: Array<{ href: Route; label: string; requiredPlan?: string }> = [
  { href: "/modules/online-seller/marketplaces", label: "Marketplace Upload", requiredPlan: "online_seller" },
  { href: "/modules/online-seller/gstr1", label: "GSTR-1 Preview", requiredPlan: "online_seller" },
  { href: "/modules/reconcile", label: "2A/2B Reconcile" },
  { href: "/modules/tally", label: "Tally Export", requiredPlan: "ecom_tally" },
];

const publicLinks: Array<{ href: string; label: string }> = [
  { href: "/#features", label: "Features" },
  { href: "/#pricing", label: "Pricing" },
  { href: "/#security", label: "Security" },
];

const workspaceLinks: Array<{ href: Route; label: string }> = [
  { href: "/settings", label: "Settings" },
  { href: "/billing", label: "Billing" },
  { href: "/modules/online-seller/profile", label: "GST Profile" },
];

function hasPlanAccess(user: FooterUser, requiredPlan?: string) {
  if (!requiredPlan) return true;
  if (!user) return false;
  if (user.role === "admin" || user.role === "super_admin" || user.plan === "admin_free") return true;
  return user.subscription_status === "active" && user.plan === requiredPlan;
}

function guardedHref({ href, requiredPlan, token, user, isPublic }: { href: Route; requiredPlan?: string; token?: string; user?: FooterUser; isPublic: boolean }) {
  if (isPublic || !token) return "/login" as Route;
  if (!hasPlanAccess(user ?? null, requiredPlan)) return `/billing?plan=${requiredPlan}` as Route;
  return href;
}

export function AppFooter({ variant = "app", token, user }: { variant?: "app" | "public"; token?: string; user?: FooterUser }) {
  const year = new Date().getFullYear();
  const isPublic = variant === "public";

  return (
    <footer className={`${isPublic ? "border-t border-slate-200 bg-white" : "mt-8 border-t border-slate-200/80 dark:border-white/10"} px-5 py-8 text-sm text-slate-500 dark:text-slate-400 lg:px-8`}>
      <div className={`${isPublic ? "mx-auto max-w-7xl" : ""} flex flex-col gap-6 md:flex-row md:items-start md:justify-between`}>
        <div className="max-w-xl">
          <div className="flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-xl bg-[#12284f] font-black text-white shadow-sm">GB</span>
            <div>
              <p className="font-black text-slate-950 dark:text-white">GST Bharat</p>
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-400">eCom GST OS</p>
            </div>
          </div>
          <p className="mt-4 max-w-lg leading-6">
            Marketplace imports, GST filing exports, reconciliation and Tally workflows for Indian eCommerce sellers.
          </p>
        </div>

        <div className="grid gap-6 sm:grid-cols-2 md:min-w-[24rem]">
          <div>
            <p className="mb-3 flex items-center gap-2 text-xs font-black uppercase tracking-[0.16em] text-slate-400">
              <ReceiptText className="size-4 text-[#1746A2]" /> Product
            </p>
            <nav className="grid gap-2">
              {productLinks.map((item) => (
                <Link
                  key={item.href}
                  href={guardedHref({ href: item.href, requiredPlan: item.requiredPlan, token, user, isPublic })}
                  className="font-semibold text-slate-600 transition hover:text-[#1746A2] dark:text-slate-300"
                  title={!token || isPublic ? "Login required" : item.requiredPlan && !hasPlanAccess(user ?? null, item.requiredPlan) ? "Subscription required" : undefined}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
          <div>
            <p className="mb-3 flex items-center gap-2 text-xs font-black uppercase tracking-[0.16em] text-slate-400">
              {isPublic ? <ShieldCheck className="size-4 text-emerald-600" /> : <FileJson className="size-4 text-emerald-600" />}
              {isPublic ? "Company" : "Workspace"}
            </p>
            <nav className="grid gap-2">
              {(isPublic ? publicLinks : workspaceLinks).map((item) => (
                <Link key={item.href} href={(isPublic ? item.href : token ? item.href : "/login") as Route} className="font-semibold text-slate-600 transition hover:text-[#1746A2] dark:text-slate-300">
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
        </div>
      </div>

      <div className={`${isPublic ? "mx-auto max-w-7xl" : ""} mt-8 flex flex-col gap-3 border-t border-slate-200/80 pt-5 text-xs font-semibold text-slate-400 dark:border-white/10 sm:flex-row sm:items-center sm:justify-between`}>
        <p>© {year} GST Bharat. All rights reserved.</p>
        <p className="flex items-center gap-2">
          <Repeat2 className="size-3.5" /> Built for GST, reconciliation and accounting workflows.
        </p>
      </div>
    </footer>
  );
}
