"use client";

import Link from "next/link";
import type { Route } from "next";
import {
  ArrowRight,
  Building2,
  CreditCard,
  FileJson,
  FileSpreadsheet,
  GitCompareArrows,
  ReceiptText,
  ShieldCheck,
  UploadCloud,
} from "lucide-react";
import { AppShell } from "@/components/saas/app-shell";
import { EmptyState, StatCard, StatusPill } from "@/components/saas/ui";
import { money, useWorkspace } from "@/components/saas/workspace";
import { formatCurrency } from "@/lib/utils";

const tools = [
  {
    title: "GST Online Seller",
    type: "Seller GST",
    href: "/modules/online-seller",
    planId: "online_seller",
    price: "₹79/mo",
    icon: UploadCloud,
    accent: "border-blue-200 bg-blue-50 text-blue-700",
    description:
      "Marketplace sales imports, data cleanup, GSTR-1 preview, JSON/Excel export and filing reports.",
  },
  {
    title: "2A/2B Reconcile",
    type: "ITC Control",
    href: "/modules/reconcile",
    planId: null,
    price: "Free",
    icon: GitCompareArrows,
    accent: "border-emerald-200 bg-emerald-50 text-emerald-700",
    description:
      "Upload portal 2A/2B and purchase books, reconcile invoices, inspect mismatches and download Excel.",
  },
  {
    title: "eCom to Tally",
    type: "Accounting",
    href: "/modules/tally",
    planId: "ecom_tally",
    price: "₹199/mo",
    icon: Building2,
    accent: "border-orange-200 bg-orange-50 text-orange-700",
    description:
      "Turn eCommerce transactions into mapped Tally vouchers and XML downloads.",
  },
] satisfies Array<{
  title: string;
  type: string;
  href: Route;
  planId: string | null;
  price: string;
  icon: typeof UploadCloud;
  accent: string;
  description: string;
}>;

export function DashboardSaasPage() {
  const workspace = useWorkspace();
  const summary = workspace.summary;
  const user = workspace.user;

  return (
    <AppShell
      title="GST Bharat Dashboard"
      subtitle="A focused product-suite cockpit. Open one GST Bharat tool at a time and keep workflows separated."
      profile={workspace.profile}
      profiles={workspace.profiles}
      token={workspace.token}
      user={workspace.user}
      loading={workspace.loading}
      error={workspace.error}
      onRetry={() => workspace.refresh()}
      onProfileChange={(profile) => {
        workspace.setProfile(profile);
        workspace.refresh(profile);
      }}
    >
      {!workspace.token ? (
        <EmptyState
          title="Login required"
          body="Login karke backend se real dashboard data load hoga."
          action={
            <Link
              className="rounded bg-[#2f72ff] px-4 py-2 text-sm font-bold text-white"
              href="/login"
            >
              Login
            </Link>
          }
        />
      ) : null}
      <section className="surface rounded-2xl p-6">
        <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <h2 className="text-xl font-black tracking-tight">
              GST Bharat product suite
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
              Exactly three independent tools. Each module opens into its own
              workflow, menu and dashboard.
            </p>
          </div>
          <span className={`w-fit rounded-full border px-4 py-2 text-xs font-black uppercase tracking-wide ${workspace.token ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-amber-200 bg-amber-50 text-amber-700"}`}>
            {workspace.token ? `${workspace.profiles.length} profiles loaded` : "Login required"}
          </span>
        </div>
        <div className="mt-7 grid gap-5 xl:grid-cols-3">
          {tools.map((tool, index) => {
            const Icon = tool.icon;
            const canOpen = !tool.planId || hasModuleAccess(user, tool.planId);
            const ctaHref = !workspace.token
              ? "/login"
              : canOpen
                ? tool.href
                : (`/billing?plan=${tool.planId}` as Route);
            const stats =
              index === 0
                ? [
                    {
                      label: "Imports",
                      value: String(
                        summary?.uploaded_files ||
                          workspace.batches.length ||
                          0,
                      ),
                    },
                    {
                      label: "Rows",
                      value: String(workspace.transactions.length || 0),
                    },
                  ]
                : index === 1
                  ? [
                      {
                        label: "Profile",
                        value: workspace.profile?.gstin ? "Ready" : "Not set",
                      },
                      {
                        label: "Period",
                        value: workspace.profile?.return_period || "--",
                      },
                    ]
                  : [
                      {
                        label: "Companies",
                        value: String(workspace.companies.length || 0),
                      },
                      {
                        label: "Ready rows",
                        value: String(
                          workspace.transactions.filter(
                            (row) => row.validation_status === "valid",
                          ).length || 0,
                        ),
                      },
                    ];
            const signals =
              index === 0
                ? [
                    `${workspace.marketplaces.length} backend parsers`,
                    `${workspace.batches.length} import batches`,
                    `${warningsText(workspace.transactions.filter((row) => ["error", "invalid", "warning"].includes(row.validation_status)).length)} validation rows`,
                    `${workspace.preview?.b2cs?.length ?? 0} B2CS groups`,
                  ]
                : index === 1
                  ? [
                      workspace.profile?.gstin ? `GSTIN ${workspace.profile.gstin}` : "No GST profile selected",
                      workspace.profile?.return_period ? `Period ${workspace.profile.return_period}` : "No return period",
                      `${workspace.transactions.length} book rows available`,
                      `${workspace.summary?.pending_errors || 0} blockers in active data`,
                    ]
                  : [
                      `${workspace.companies.length} Tally companies`,
                      `${workspace.transactions.filter((row) => row.validation_status === "valid").length} valid rows`,
                      `${workspace.batches.filter((batch) => batch.status === "completed").length} completed imports`,
                      workspace.profile?.financial_year ? `FY ${workspace.profile.financial_year}` : "Financial year not set",
                    ];
            return (
              <article
                key={tool.title}
                className="group overflow-hidden rounded-2xl border border-slate-200 bg-white text-left shadow-sm transition hover:-translate-y-0.5 hover:border-[#1746A2]/35 hover:shadow-xl hover:shadow-slate-200/70 dark:border-white/10 dark:bg-slate-900 dark:shadow-none"
              >
                <div className="border-b border-slate-100 p-5 dark:border-white/10">
                  <div className="flex items-start justify-between gap-4">
                    <div className={`grid size-12 place-items-center rounded-xl border ${tool.accent}`}>
                      <Icon className="size-7" />
                    </div>
                    <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-black uppercase tracking-wide text-slate-500 dark:border-white/10 dark:bg-white/5">
                      {tool.price}
                    </span>
                  </div>
                  <h3 className="mt-6 text-2xl font-black tracking-tight">
                    {tool.title}
                  </h3>
                  <p className="mt-2 text-sm leading-6 text-slate-500 dark:text-slate-400">
                    {tool.description}
                  </p>
                </div>
                <div className="p-5">
                  <div className="grid grid-cols-2 gap-3">
                    {stats.map((stat) => (
                      <div
                        key={stat.label}
                        className="surface-muted rounded-xl p-3"
                      >
                        <p className="text-xs font-semibold text-slate-500">
                          {stat.label}
                        </p>
                        <p className="mt-1 truncate text-lg font-black">
                          {stat.value}
                        </p>
                      </div>
                    ))}
                  </div>
                  <div className="mt-5 grid gap-2 text-sm text-slate-600 dark:text-slate-300">
                    {signals.map((point) => (
                      <p key={point} className="flex items-center gap-2">
                        <ShieldCheck className="size-4 text-emerald-600" />{" "}
                        {point}
                      </p>
                    ))}
                  </div>
                  <div className="mt-5 flex items-center justify-between gap-3">
                    <StatusPill
                      status={!workspace.token ? "Login required" : canOpen ? "Active" : "Subscription required"}
                    />
                    <Link
                      href={ctaHref}
                      className={canOpen || !workspace.token ? "btn-primary" : "btn-secondary"}
                    >
                      {!workspace.token ? (
                        <>Login <ArrowRight className="size-4" /></>
                      ) : canOpen ? (
                        <>Open Module <ArrowRight className="size-4" /></>
                      ) : (
                        <>Pricing <CreditCard className="size-4" /></>
                      )}
                    </Link>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </AppShell>
  );
}

function warningsText(count: number) {
  return count ? String(count) : "0";
}

function hasModuleAccess(
  user: { role?: string; plan?: string; subscription_status?: string } | null,
  planId: string,
) {
  if (!user) return false;
  if (user.role === "admin" || user.role === "super_admin" || user.plan === "admin_free") return true;
  return user.subscription_status === "active" && user.plan === planId;
}

export function OnlineSellerDashboardPage() {
  const workspace = useWorkspace();
  const summary = workspace.summary;
  const warnings = workspace.transactions.filter((row) =>
    ["error", "invalid", "warning"].includes(row.validation_status),
  );
  const gstrPreview = workspace.preview;
  const activePlatforms = summary?.platform_wise_sale.length || 0;
  const workflows: Array<{
    title: string;
    href: Route;
    icon: typeof UploadCloud;
    body: () => string;
  }> = [
    {
      title: "GST Profile",
      href: "/modules/online-seller/profile",
      icon: ReceiptText,
      body: () => workspace.profile ? `${workspace.profile.gstin} / ${workspace.profile.return_period}` : "No backend GST profile selected.",
    },
    {
      title: "Marketplace Upload",
      href: "/modules/online-seller/marketplaces",
      icon: UploadCloud,
      body: () => `${workspace.marketplaces.length} parsers / ${workspace.batches.length} batches`,
    },
    {
      title: "Manage Data",
      href: "/modules/online-seller/manage-data",
      icon: FileSpreadsheet,
      body: () => `${workspace.transactions.length} normalized rows loaded`,
    },
    {
      title: "GSTR-1 Preview",
      href: "/modules/online-seller/gstr1",
      icon: FileJson,
      body: () => `${workspace.preview?.b2cs?.length ?? 0} B2CS groups / ${summary?.json_generation_status || "not_generated"}`,
    },
  ];
  return (
    <AppShell
      requiresSubscription
      requiredPlan="online_seller"
      token={workspace.token}
      user={workspace.user}
      productName="GST Online Seller"
      title="GST Online Seller"
      subtitle="Seller GST workflow for marketplace uploads, normalized data, GSTR-1 files and reports."
      profile={workspace.profile}
      profiles={workspace.profiles}
      loading={workspace.loading}
      error={workspace.error}
      onRetry={() => workspace.refresh()}
      onProfileChange={(profile) => {
        workspace.setProfile(profile);
        workspace.refresh(profile);
      }}
      actions={
        <Link
          href="/modules/online-seller/marketplaces"
          className="inline-flex items-center gap-2 rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white"
        >
          <UploadCloud className="size-4" /> Marketplace Upload
        </Link>
      }
    >
      <div className="space-y-6">
        {!workspace.token ? (
          <EmptyState
            title="Login required"
            body="Login to load GST profile, uploads and GSTR-1 readiness from backend APIs."
          />
        ) : null}
        <div className="grid gap-4 md:grid-cols-4">
          <StatCard
            label="Taxable value"
            value={formatCurrency(money(summary?.total_taxable_value))}
            detail={`${activePlatforms} platforms`}
          />
          <StatCard
            label="Total GST"
            value={formatCurrency(money(summary?.total_gst))}
          />
          <StatCard
            label="Uploaded files"
            value={String(
              summary?.uploaded_files || workspace.batches.length || 0,
            )}
          />
          <StatCard
            label="Warnings"
            value={String(warnings.length)}
            tone={warnings.length ? "red" : "green"}
          />
        </div>
        <section className="grid gap-5 lg:grid-cols-4">
          {workflows.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className="rounded-3xl border border-white/70 bg-white p-5 shadow-xl shadow-slate-200/60 transition hover:-translate-y-1 hover:shadow-2xl dark:border-white/10 dark:bg-slate-950 dark:shadow-none"
              >
                <div className="grid size-12 place-items-center rounded-2xl bg-[#1746A2]/10 text-[#1746A2]">
                  <Icon className="size-5" />
                </div>
                <h3 className="mt-5 text-lg font-black">{item.title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  {item.body()}
                </p>
              </Link>
            );
          })}
        </section>
        <section className="grid gap-5 lg:grid-cols-2">
          <div className="rounded-3xl border border-white/70 bg-white p-6 shadow-xl shadow-slate-200/60 dark:border-white/10 dark:bg-slate-950 dark:shadow-none">
            <h3 className="text-lg font-black">Upload History</h3>
            <div className="mt-5 space-y-3">
              {workspace.batches.slice(0, 4).map((batch) => (
                <div
                  key={batch.id}
                  className="flex items-center justify-between rounded-2xl bg-slate-50 p-3 text-sm dark:bg-white/5"
                >
                  <div>
                    <b className="capitalize">{batch.platform}</b>
                    <p className="text-xs text-slate-500">
                      {batch.parsed_rows} parsed / {batch.error_rows} errors
                    </p>
                  </div>
                  <StatusPill status={batch.status} />
                </div>
              ))}
              {!workspace.batches.length && (
                <EmptyState
                  title="No uploads yet"
                  body="Marketplace upload history will appear here."
                />
              )}
            </div>
          </div>
          <div className="rounded-3xl border border-white/70 bg-white p-6 shadow-xl shadow-slate-200/60 dark:border-white/10 dark:bg-slate-950 dark:shadow-none">
            <h3 className="text-lg font-black">GSTR-1 Readiness</h3>
            <div className="mt-5 space-y-3 text-sm">
              <div className="flex items-center justify-between rounded-2xl bg-slate-50 p-3 dark:bg-white/5">
                <span>JSON status</span>
                <StatusPill
                  status={summary?.json_generation_status || "not_generated"}
                />
              </div>
              <div className="flex items-center justify-between rounded-2xl bg-slate-50 p-3 dark:bg-white/5">
                <span>B2CS groups</span>
                <b>{gstrPreview?.b2cs?.length ?? 0}</b>
              </div>
              <div className="flex items-center justify-between rounded-2xl bg-slate-50 p-3 dark:bg-white/5">
                <span>Errors</span>
                <b>{summary?.pending_errors || 0}</b>
              </div>
              <Link
                href="/modules/online-seller/gstr1"
                className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-[#10244d] px-4 py-3 text-sm font-bold text-white"
              >
                <FileJson className="size-4" /> Open GSTR-1
              </Link>
            </div>
          </div>
        </section>
      </div>
    </AppShell>
  );
}
