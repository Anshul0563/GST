"use client";

import Link from "next/link";
import type { Route } from "next";
import { ArrowRight, FileJson, GitCompareArrows, ReceiptText, UploadCloud } from "lucide-react";
import { ClassicToolShell } from "@/components/saas/app-shell";
import { EmptyState, StatCard, StatusPill } from "@/components/saas/ui";
import { money, useWorkspace } from "@/components/saas/workspace";
import { formatCurrency } from "@/lib/utils";

const tools = [
  {
    title: "GST Online Seller",
    type: "GST",
    href: "/marketplaces",
    icon: UploadCloud,
    accent: "from-[#12396f] to-[#0e5fd8]",
    points: ["Import marketplace data", "Generate GSTR1", "Excel and JSON export"]
  },
  {
    title: "2B/2A Reconcile v2.0",
    type: "GST",
    href: "/reconcile",
    icon: GitCompareArrows,
    accent: "from-[#3b66ff] to-[#6dd5ff]",
    points: ["2A/2B upload", "Purchase matching", "Query report"]
  },
  {
    title: "eCom to Tally",
    type: "ACCOUNT",
    href: "/tally",
    icon: ReceiptText,
    accent: "from-[#10244d] to-[#1746A2]",
    points: ["Marketplace to XML", "Ledger mapping", "Voucher export"]
  }
] satisfies Array<{
  title: string;
  type: string;
  href: Route;
  icon: typeof UploadCloud;
  accent: string;
  points: string[];
}>;

export function DashboardSaasPage() {
  const workspace = useWorkspace();
  const summary = workspace.summary;
  const warnings = workspace.transactions.filter((row) => row.validation_status === "error");
  const activePlatforms = summary?.platform_wise_sale.length || 0;

  return <ClassicToolShell title="Dashboard" crumb="Dashboard" active="dashboard" profile={workspace.profile}>
    {!workspace.token ? <EmptyState title="Login required" body="Login karke backend se real dashboard data load hoga." action={<Link className="rounded bg-[#2f72ff] px-4 py-2 text-sm font-bold text-white" href="/login">Login</Link>} /> : null}
    <section className="rounded-md bg-white p-7 text-center shadow-xl shadow-slate-200/80">
      <h2 className="text-xl font-black">Our Tools</h2>
      <p className="mt-2 text-xs text-slate-500">Here is all tool click access now to use our tool.</p>
      <div className="mt-7 grid gap-5 lg:grid-cols-3">
        {tools.map((tool, index) => {
          const Icon = tool.icon;
          return <div key={tool.title} className={`overflow-hidden rounded-sm border bg-white text-left shadow-md ${index === 0 ? "border-2 border-red-500" : "border-slate-200"}`}>
            <div className={`relative h-28 bg-gradient-to-br ${tool.accent} p-4 text-white`}>
              <div className="absolute inset-0 opacity-20 [background-image:radial-gradient(circle_at_20%_30%,white_0_7px,transparent_8px)] [background-size:42px_42px]" />
              {index === 2 && <span className="absolute right-0 top-0 rounded-bl bg-rose-500 px-2 py-1 text-[10px] font-black">v2.0</span>}
              <div className="relative flex h-full items-center justify-center gap-4">
                <div className="grid size-14 place-items-center rounded bg-white text-2xl font-black text-[#10244d]">a</div>
                <div className="grid size-12 place-items-center rounded-full bg-red-600 text-white">GST</div>
                <div className="grid size-14 place-items-center rounded bg-white text-[#1746A2]"><Icon className="size-8" /></div>
              </div>
            </div>
            <div className="p-4">
              <p className="text-[10px] font-black uppercase text-slate-400">{tool.type}</p>
              <h3 className="mt-1 text-base font-black">{tool.title}</h3>
              <p className="mt-1 text-xs text-slate-500">Convert eCommerce excel into GST-ready reports.</p>
              <div className="mt-4 space-y-1.5 text-xs text-slate-600">
                {tool.points.map((point) => <p key={point}>› {point}</p>)}
              </div>
            </div>
            <div className="flex items-center justify-between bg-[#10244d] px-4 py-3">
              <span className="text-sm font-bold text-emerald-300">Active</span>
              <Link href={tool.href} className="inline-flex items-center gap-1 rounded bg-[#2f72ff] px-3 py-1.5 text-xs font-bold text-white">Access Now <ArrowRight className="size-3" /></Link>
            </div>
          </div>;
        })}
      </div>
    </section>

    {workspace.profile && <section className="grid gap-4 md:grid-cols-4">
      <StatCard label="Taxable value" value={formatCurrency(money(summary?.total_taxable_value))} detail={`${activePlatforms} platforms`} />
      <StatCard label="Total GST" value={formatCurrency(money(summary?.total_gst))} />
      <StatCard label="Uploaded files" value={String(summary?.uploaded_files || workspace.batches.length)} />
      <StatCard label="Warnings" value={String(warnings.length)} tone={warnings.length ? "red" : "green"} />
    </section>}

    <section className="grid gap-5 lg:grid-cols-2">
      <div className="rounded-md bg-white p-6 shadow-xl shadow-slate-200/80">
        <h3 className="text-center text-lg font-black">Recent Imports</h3>
        <div className="mt-5 space-y-3">
          {workspace.batches.slice(0, 4).map((batch) => <div key={batch.id} className="flex items-center justify-between rounded border border-slate-200 p-3 text-sm"><div><b className="capitalize">{batch.platform}</b><p className="text-xs text-slate-500">{batch.parsed_rows} parsed / {batch.error_rows} errors</p></div><StatusPill status={batch.status} /></div>)}
          {!workspace.batches.length && <EmptyState title="No imports yet" body="Marketplace uploads yahan appear honge." />}
        </div>
      </div>
      <div className="rounded-md bg-white p-6 shadow-xl shadow-slate-200/80">
        <h3 className="text-center text-lg font-black">GSTR1 Readiness</h3>
        <div className="mt-5 space-y-3 text-sm">
          <div className="flex items-center justify-between rounded border border-slate-200 p-3"><span>JSON status</span><StatusPill status={summary?.json_generation_status || "not_generated"} /></div>
          <div className="flex items-center justify-between rounded border border-slate-200 p-3"><span>B2CS groups</span><b>{workspace.preview?.b2cs.length || 0}</b></div>
          <div className="flex items-center justify-between rounded border border-slate-200 p-3"><span>Errors</span><b>{summary?.pending_errors || 0}</b></div>
          <Link href="/gstr1" className="inline-flex w-full items-center justify-center gap-2 rounded bg-[#2f72ff] px-4 py-2.5 text-sm font-bold text-white"><FileJson className="size-4" /> Open GSTR1</Link>
        </div>
      </div>
    </section>
  </ClassicToolShell>;
}
