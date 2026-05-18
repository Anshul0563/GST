"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Download, FileJson, FileSpreadsheet, ReceiptText, UploadCloud } from "lucide-react";
import { AppShell } from "@/components/saas/app-shell";
import { EmptyState, Panel, StatCard, StatusPill } from "@/components/saas/ui";
import { money, useWorkspace } from "@/components/saas/workspace";
import { Profile, ReconcileHistoryItem, ReconcileReport, getReconcileDownloadUrl, getReconcileHistory, getReconcileResults, uploadReconcileFilesV2 } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

const categories = ["matched", "partially_matched", "tax_mismatch", "invoice_mismatch", "missing_in_portal", "missing_in_books", "duplicate_invoice", "invalid_gstin"];

export function ReconcileDashboardPage() {
  const workspace = useWorkspace();
  const [history, setHistory] = useState<ReconcileHistoryItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  useEffect(() => {
    if (!workspace.token) return;
    setLoadingHistory(true);
    getReconcileHistory(workspace.token, workspace.profile?.id).then(setHistory).catch(() => setHistory([])).finally(() => setLoadingHistory(false));
  }, [workspace.token, workspace.profile?.id]);
  const latest = history[0];
  const chart = history.slice(0, 8).reverse().map((item) => ({ name: `#${item.id}`, matched: item.matched_rows, mismatch: item.mismatch_rows }));
  const totalRuns = history.length;
  const totalMismatches = history.reduce((sum, item) => sum + item.mismatch_rows, 0);
  return <AppShell title="2B/2A Reconcile v2.0" subtitle="Professional ITC reconciliation across GST portal 2A/2B and purchase books." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }} actions={<Link href="/reconcile/upload" className="inline-flex items-center gap-2 rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white"><UploadCloud className="size-4" /> New reconcile</Link>}>
    <div className="space-y-6">
      {!workspace.token ? <EmptyState title="Login required" body="Reconciliation history is loaded from authenticated backend APIs." /> : null}
      <div className="grid gap-4 md:grid-cols-5">
        <StatCard label="Runs" value={String(totalRuns)} />
        <StatCard label="Portal invoices" value={String(latest?.portal_rows || 0)} />
        <StatCard label="Book invoices" value={String(latest?.book_rows || 0)} />
        <StatCard label="Matched" value={`${latest?.summary?.matched_percent || 0}%`} tone="green" />
        <StatCard label="Open mismatches" value={String(totalMismatches)} tone={totalMismatches ? "red" : "green"} />
      </div>
      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <Panel title="Reconcile trend" subtitle="Matched vs mismatch rows by batch.">
          {chart.length ? <div className="h-80"><ResponsiveContainer width="100%" height="100%"><BarChart data={chart}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="name" /><YAxis /><Tooltip /><Bar dataKey="matched" fill="#0F9F6E" radius={[10, 10, 0, 0]} /><Bar dataKey="mismatch" fill="#F58220" radius={[10, 10, 0, 0]} /></BarChart></ResponsiveContainer></div> : <EmptyState title="No reconciliation yet" body="Upload portal and books files to create your first result." />}
        </Panel>
        <Panel title="Recent batches" subtitle="Open result explorer or download Excel report.">
          {loadingHistory ? <EmptyState title="Loading history" body="Fetching reconciliation batches from backend." /> : <HistoryList history={history} />}
        </Panel>
      </div>
      {latest && <Panel title="Latest ITC risk snapshot" subtitle="Backend calculated tax difference and risk amount from the newest batch.">
        <div className="grid gap-4 md:grid-cols-3">
          <StatCard label="Tax difference" value={formatCurrency(money(latest.tax_difference))} tone="saffron" />
          <StatCard label="ITC risk amount" value={formatCurrency(money(latest.itc_risk_amount))} tone="red" />
          <StatCard label="Status" value={latest.status} tone={latest.status.includes("error") ? "red" : "green"} />
        </div>
      </Panel>}
    </div>
  </AppShell>;
}

export function ReconcileUploadPage() {
  const workspace = useWorkspace();
  const [portal, setPortal] = useState<File | null>(null);
  const [books, setBooks] = useState<File | null>(null);
  const [taxTolerance, setTaxTolerance] = useState("1.00");
  const [dateTolerance, setDateTolerance] = useState(3);
  const [result, setResult] = useState<ReconcileReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit() {
    if (!workspace.token || !workspace.profile || !portal || !books) return;
    setBusy(true);
    setError("");
    try {
      const upload = await uploadReconcileFilesV2(workspace.token, workspace.profile.id, portal, books, { tax_tolerance: taxTolerance, date_tolerance_days: dateTolerance, enable_date_tolerance: true, enable_fuzzy_invoice: true });
      setResult(upload);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Reconciliation failed");
    } finally {
      setBusy(false);
    }
  }
  const summary = result?.summary || {};
  const tiles = [
    ["Total 2B (In ₹)", summary.portal_rows || 0, "bg-cyan-500"],
    ["Total Matched Entry", summary.matched || 0, "bg-sky-500"],
    ["Matched", summary.matched || 0, "bg-emerald-500"],
    ["Amount Mismatched", summary.tax_mismatch || 0, "bg-orange-300"],
    ["Invoice Mismatched", summary.invoice_mismatch || 0, "bg-orange-400"],
    ["Entry Missing", summary.missing_in_portal || 0, "bg-pink-500"],
    ["Return Pending", summary.partially_matched || 0, "bg-rose-500"],
    ["UnMatched", Number(summary.missing_in_books || 0) + Number(summary.invalid_gstin || 0), "bg-pink-600"],
  ] as const;
  return <ReconcileClassicShell profile={workspace.profile}>
    <section className="rounded-md bg-white p-8 text-center shadow-xl shadow-slate-200/80">
      <h2 className="text-xl font-black">2B/2A Reconcile</h2>
      <p className="mt-1 text-xs text-slate-500">2A/2B Reconcile with Purchase data and provide query report.</p>
      <p className="mx-auto mt-6 max-w-xl text-xs leading-5 text-slate-500">Please download the sample file for 2A & 2B verification sheet by clicking the button below, and fill in the GST portal 2A/2B data and the client purchase data in the client data sheet.</p>
      <a href="data:text/csv;charset=utf-8,Supplier GSTIN,Invoice Number,Invoice Date,Taxable Value,IGST,CGST,SGST%0A" download="gst-bharat-2b-2a-sample.csv" className="mt-5 inline-flex items-center gap-2 rounded bg-[#2f72ff] px-5 py-3 text-xs font-bold text-white shadow-md">
        <span className="grid size-8 place-items-center rounded bg-emerald-600"><FileSpreadsheet className="size-5" /></span> Sample File Download
      </a>
    </section>

    <section className="rounded-md bg-white p-7 shadow-xl shadow-slate-200/80">
      <h3 className="border-b border-slate-200 pb-4 text-base font-black">Upload File</h3>
      {!workspace.profile ? <div className="mt-5"><EmptyState title="GST profile required" body="Create or select GST profile before uploading reconciliation files." /></div> : null}
      <div className="mt-6 grid gap-5 md:grid-cols-[1fr_150px]">
        <label className="text-xs font-bold text-slate-700">2A/2B Data Sheet
          <input type="file" onChange={(event) => setPortal(event.target.files?.[0] || null)} className="mt-2 w-full rounded border border-slate-300 bg-white px-3 py-2 text-xs file:mr-3 file:rounded file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-xs file:font-bold" />
        </label>
        <label className="text-xs font-bold text-slate-700">Difference Ignore (₹)
          <input value={taxTolerance} onChange={(event) => setTaxTolerance(event.target.value)} className="mt-2 w-full rounded border border-slate-300 px-3 py-2 text-sm outline-none" />
        </label>
        <label className="text-xs font-bold text-slate-700 md:col-span-2">Purchase Register / Client Data Sheet
          <input type="file" onChange={(event) => setBooks(event.target.files?.[0] || null)} className="mt-2 w-full rounded border border-slate-300 bg-white px-3 py-2 text-xs file:mr-3 file:rounded file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-xs file:font-bold" />
        </label>
        <label className="text-xs font-bold text-slate-700">Date tolerance days
          <input type="number" value={dateTolerance} onChange={(event) => setDateTolerance(Number(event.target.value))} className="mt-2 w-full rounded border border-slate-300 px-3 py-2 text-sm outline-none" />
        </label>
      </div>
      <button onClick={submit} disabled={busy || !workspace.profile || !portal || !books} className="mt-5 rounded bg-[#2f72ff] px-4 py-2 text-xs font-bold text-white disabled:opacity-50">{busy ? "Processing..." : "Submit"}</button>
      {error && <div className="mt-4 rounded bg-rose-50 p-3 text-sm font-bold text-rose-700">{error}</div>}

      {result && <div className="mt-6">
        <div className="grid grid-cols-2 text-center text-[11px] font-black text-white md:grid-cols-4 lg:grid-cols-8">
          {tiles.map(([label, value, color]) => <div key={label} className={`${color} min-h-20 p-3`}>
            <p>{label}</p>
            <p className="mt-2 text-lg">{String(value)}</p>
          </div>)}
        </div>
        <div className="mt-6 text-center">
          <a href={getReconcileDownloadUrl(result.id)} className="inline-flex items-center gap-2 rounded bg-[#2f72ff] px-5 py-3 text-xs font-bold text-white shadow-md">
            <span className="grid size-8 place-items-center rounded bg-emerald-600"><FileSpreadsheet className="size-5" /></span> Query Report Download
          </a>
          <Link href={`/reconcile/results/${result.id}`} className="ml-3 inline-flex rounded border border-[#2f72ff] px-5 py-3 text-xs font-bold text-[#2f72ff]">View Details</Link>
        </div>
      </div>}
    </section>
  </ReconcileClassicShell>;
}

export function ReconcileResultsPage({ id }: { id: number }) {
  const workspace = useWorkspace();
  const [report, setReport] = useState<ReconcileReport | null>(null);
  const [category, setCategory] = useState("");
  useEffect(() => {
    if (!workspace.token || !id) return;
    getReconcileResults(workspace.token, id, category || undefined).then(setReport).catch(() => setReport(null));
  }, [workspace.token, id, category]);
  const rows = report?.rows || [];
  const summary = report?.summary || {};
  const summaryNumber = (key: string) => Number(summary[key] || 0);
  const riskData = categories.map((item) => ({ name: item.replaceAll("_", " "), value: summaryNumber(item) }));
  return <AppShell title={`Reconcile Result #${id}`} subtitle="Mismatch explorer with exact reason, tax difference and download actions." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }} actions={<a href={getReconcileDownloadUrl(id)} className="inline-flex items-center gap-2 rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white"><Download className="size-4" /> Excel report</a>}>
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="Matched" value={String(summaryNumber("matched"))} tone="green" />
        <StatCard label="Mismatch %" value={`${summaryNumber("mismatch_percent")}%`} tone="saffron" />
        <StatCard label="Tax difference" value={formatCurrency(summaryNumber("tax_difference"))} tone="red" />
        <StatCard label="ITC risk" value={formatCurrency(summaryNumber("itc_risk_amount"))} tone="red" />
      </div>
      <Panel title="Mismatch buckets" subtitle="Filter explorer by status.">
        <div className="mb-5 flex flex-wrap gap-2">{["", ...categories].map((item) => <button key={item || "all"} onClick={() => setCategory(item)} className={`rounded-2xl px-4 py-2 text-sm font-bold ${category === item ? "bg-[#10244d] text-white" : "bg-slate-100 text-slate-600 dark:bg-white/10 dark:text-slate-300"}`}>{item || "all"}</button>)}</div>
        <div className="h-56"><ResponsiveContainer width="100%" height="100%"><AreaChart data={riskData}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="name" hide /><YAxis allowDecimals={false} /><Tooltip /><Area type="monotone" dataKey="value" stroke="#1746A2" fill="#1746A240" /></AreaChart></ResponsiveContainer></div>
      </Panel>
      <Panel title="Query explorer" subtitle={`${rows.length} rows visible`}>
        {rows.length ? <div className="max-h-[620px] overflow-auto rounded-3xl border dark:border-white/10"><table className="min-w-[1120px] text-sm"><thead className="bg-slate-50 text-left text-xs uppercase text-slate-500 dark:bg-slate-900"><tr>{["Supplier GSTIN", "Invoice", "Date", "Taxable", "GST", "Diff", "Score", "Status", "Reason"].map((head) => <th key={head} className="px-4 py-3">{head}</th>)}</tr></thead><tbody>{rows.map((row) => <tr key={row.id} className="border-t dark:border-white/10"><td className="px-4 py-3">{row.supplier_gstin}</td><td>{row.invoice_no}</td><td>{row.invoice_date}</td><td>{formatCurrency(money(row.taxable_value))}</td><td>{formatCurrency(money(row.total_tax))}</td><td>{formatCurrency(money(row.tax_difference))}</td><td>{row.match_score}</td><td><StatusPill status={row.category} /></td><td>{row.mismatch_reason}</td></tr>)}</tbody></table></div> : <EmptyState title="No rows" body="No reconciliation rows for this filter." />}
      </Panel>
    </div>
  </AppShell>;
}

export function ReconcileHistoryPage() {
  const workspace = useWorkspace();
  const [history, setHistory] = useState<ReconcileHistoryItem[]>([]);
  useEffect(() => {
    if (!workspace.token) return;
    getReconcileHistory(workspace.token, workspace.profile?.id).then(setHistory).catch(() => setHistory([]));
  }, [workspace.token, workspace.profile?.id]);
  return <AppShell title="Reconciliation History" subtitle="Download center for previous 2A/2B matching runs." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }}>
    <Panel title="History" subtitle="All batches are loaded from backend."><HistoryList history={history} /></Panel>
  </AppShell>;
}

function HistoryList({ history }: { history: ReconcileHistoryItem[] }) {
  return history.length ? <div className="space-y-3">{history.map((item) => <div key={item.id} className="grid gap-3 rounded-2xl bg-slate-50 p-4 text-sm dark:bg-white/5 md:grid-cols-[1fr_auto_auto_auto]"><div><b>Batch #{item.id}</b><p className="text-xs text-slate-500">{item.portal_rows} portal / {item.book_rows} books</p></div><StatusPill status={item.status} /><Link href={`/reconcile/results/${item.id}`} className="rounded-xl bg-[#1746A2] px-3 py-2 text-xs font-bold text-white">Open</Link><a href={getReconcileDownloadUrl(item.id)} className="rounded-xl bg-emerald-600 px-3 py-2 text-xs font-bold text-white">Download</a></div>)}</div> : <EmptyState title="No history" body="Completed reconciliation batches will appear here." />;
}

function ReconcileClassicShell({ profile, children }: { profile: Profile | null; children: ReactNode }) {
  return <div className="min-h-screen bg-[#f3f7fc] text-slate-950">
    <header className="h-14 border-b border-slate-200 bg-white">
      <div className="mx-auto flex h-full max-w-6xl items-center justify-between px-5">
        <Link href="/dashboard" className="flex items-center gap-2">
          <span className="text-2xl font-black tracking-tight text-[#10244d]">GST</span>
          <span className="-ml-1 rounded-sm bg-saffron px-1.5 py-0.5 text-xs font-black text-white">BHARAT</span>
        </Link>
        <nav className="hidden items-center gap-8 text-xs font-bold text-slate-500 md:flex">
          <Link className="text-rose-500" href="/dashboard">Dashboard</Link>
          <Link href="/marketplaces">Our Tools</Link>
          <Link href="/billing">Pricing</Link>
          <Link href="/settings">Support</Link>
          <span className="grid size-8 place-items-center rounded-full bg-rose-500 font-black text-white">P</span>
        </nav>
      </div>
    </header>
    <section className="relative bg-[#162d59] text-white">
      <div className="absolute inset-0 opacity-20 [background-image:linear-gradient(135deg,rgba(255,255,255,.2)_1px,transparent_1px)] [background-size:32px_32px]" />
      <div className="relative mx-auto min-h-44 max-w-6xl px-5 py-8">
        <h1 className="text-2xl font-black">2B/2A Reconcile</h1>
        <p className="mt-3 text-sm font-semibold text-white/85">Home <span className="px-2 text-white/45">/</span> Dashboard <span className="px-2 text-white/45">/</span> <span className="text-blue-300">2B/2A Reconcile</span></p>
      </div>
    </section>
    <main className="mx-auto -mt-9 grid max-w-6xl gap-5 px-5 pb-12 md:grid-cols-[215px_1fr]">
      <aside className="h-fit rounded-md bg-white p-7 shadow-xl shadow-slate-200/80">
        <Link href="/dashboard" className="mb-5 block border-b border-slate-200 pb-5 text-center text-base font-black text-[#2f72ff]">Dashboard</Link>
        <nav className="space-y-1 text-sm font-semibold">
          <Link href="/reconcile/upload" className="flex items-center gap-3 border-l-2 border-[#2f72ff] bg-blue-50 px-3 py-2 text-[#2f72ff]"><FileSpreadsheet className="size-4" /> 2B/2A Reconcile</Link>
          <Link href="/dashboard" className="flex items-center gap-3 border-l-2 border-transparent px-3 py-2 text-slate-700 hover:bg-slate-50"><ReceiptText className="size-4 text-slate-400" /> Online Seller Tool</Link>
          <Link href="/gstr1" className="flex items-center gap-3 border-l-2 border-transparent px-3 py-2 text-slate-700 hover:bg-slate-50"><FileJson className="size-4 text-slate-400" /> GSTR1</Link>
        </nav>
        {profile && <div className="mt-5 rounded bg-slate-50 p-3 text-[11px] font-bold text-slate-600">
          <p>{profile.gstin}</p>
          <p className="mt-1">Period: {profile.return_period}</p>
        </div>}
      </aside>
      <div className="space-y-5">{children}</div>
    </main>
  </div>;
}
