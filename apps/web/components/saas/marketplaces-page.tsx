"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, BookOpen, CheckCircle2, Search, UploadCloud } from "lucide-react";
import { AppShell } from "@/components/saas/app-shell";
import { Panel, StatusPill } from "@/components/saas/ui";
import { useWorkspace } from "@/components/saas/workspace";
import { marketplaceCategories, marketplaces } from "@/lib/marketplaces";

export function MarketplacesPage() {
  const workspace = useWorkspace();
  const [category, setCategory] = useState<(typeof marketplaceCategories)[number] | "All">("All");
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => marketplaces.filter((item) => (category === "All" || item.category === category) && item.name.toLowerCase().includes(query.toLowerCase())), [category, query]);
  const latest = new Map(workspace.batches.map((batch) => [batch.platform, batch]));

  return (
    <AppShell title="Marketplace Hub" subtitle="Premium import cockpit for Indian eCommerce, quick commerce, B2B and accounting platforms." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }} actions={<Link href="/imports" className="rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white">Open import flow</Link>}>
      <div className="space-y-6">
        <Panel title="Discover integrations" subtitle="Search, filter and start guided imports. Active platforms are connected to backend parsers.">
          <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-wrap gap-2">
              {(["All", ...marketplaceCategories] as const).map((item) => <button key={item} onClick={() => setCategory(item)} className={`rounded-2xl px-4 py-2 text-sm font-bold ${category === item ? "bg-[#10244d] text-white" : "bg-slate-100 text-slate-600 dark:bg-white/10 dark:text-slate-300"}`}>{item}</button>)}
            </div>
            <div className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm dark:border-white/10 dark:bg-slate-900"><Search className="size-4 text-slate-400" /><input value={query} onChange={(event) => setQuery(event.target.value)} className="bg-transparent outline-none" placeholder="Search marketplace" /></div>
          </div>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {filtered.map((item) => {
              const Icon = item.icon;
              const batch = latest.get(item.key);
              const canImport = item.status !== "Coming Soon";
              return (
                <div key={item.key} className={`group rounded-3xl border border-slate-200 bg-white p-5 transition dark:border-white/10 dark:bg-slate-900 ${canImport ? "hover:-translate-y-1 hover:shadow-2xl hover:shadow-slate-200/80 dark:hover:shadow-none" : "opacity-75"}`}>
                  <div className="flex items-start justify-between">
                    <div className={`grid size-14 place-items-center rounded-3xl bg-gradient-to-br ${item.accent} text-white shadow-lg`}><Icon className="size-6" /></div>
                    <StatusPill status={item.status} />
                  </div>
                  <h3 className="mt-5 text-xl font-black">{item.name}</h3>
                  <p className="mt-1 text-sm font-semibold text-slate-500">{item.category}</p>
                  <div className="mt-4 space-y-2 text-sm text-slate-500">
                    <p className="flex gap-2"><BookOpen className="mt-0.5 size-4 text-[#1746A2]" />{item.guide}</p>
                    <p className="flex gap-2"><CheckCircle2 className="mt-0.5 size-4 text-emerald-600" />{item.requiredFiles.join(", ")}</p>
                  </div>
                  <div className="mt-5 rounded-2xl bg-slate-50 p-3 text-xs text-slate-500 dark:bg-white/5">
                    {batch ? <>Last import: <b>{batch.parsed_rows}</b> parsed, <b>{batch.error_rows}</b> errors</> : "No uploads yet"}
                  </div>
                  {canImport ? <Link href={`/imports?platform=${item.key}`} className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-[#10244d] px-4 py-3 text-sm font-bold text-white">
                    <UploadCloud className="size-4" /> Start guided upload <ArrowRight className="size-4" />
                  </Link> : <button disabled className="mt-4 inline-flex w-full cursor-not-allowed items-center justify-center gap-2 rounded-2xl bg-slate-200 px-4 py-3 text-sm font-bold text-slate-500 dark:bg-white/10">
                    Coming soon
                  </button>}
                </div>
              );
            })}
          </div>
        </Panel>
      </div>
    </AppShell>
  );
}
