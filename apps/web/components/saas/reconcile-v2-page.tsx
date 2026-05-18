"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Download, FileSearch, UploadCloud } from "lucide-react";
import { AppShell } from "@/components/saas/app-shell";
import { EmptyState, Panel, StatCard, StatusPill } from "@/components/saas/ui";
import { money, useWorkspace } from "@/components/saas/workspace";
import { ReconcileHistoryItem, ReconcileReport, getReconcileDownloadUrl, getReconcileHistory, getReconcileResults, uploadReconcileFilesV2 } from "@/lib/api";
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
  return <AppShell title="Reconcile Upload" subtitle="Upload GST portal 2A/2B and purchase register, then run the matching engine." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }}>
    {!workspace.profile ? <EmptyState title="GST profile required" body="Create or select a GST profile before uploading 2A/2B reconciliation files." /> : null}
    <div className="grid gap-6 xl:grid-cols-[0.8fr_1.2fr]">
      <Panel title="Workflow" subtitle="Real parser + matching pipeline.">
        {["Select GST profile and period", "Upload 2A/2B Excel or JSON", "Upload purchase register", "Normalize supplier invoices", "Run exact/fuzzy/tolerance matching", "Download Excel reports"].map((item, index) => <div key={item} className="mb-3 rounded-2xl bg-slate-50 p-4 text-sm font-bold dark:bg-white/5">{index + 1}. {item}</div>)}
      </Panel>
      <Panel title="Upload files" subtitle="Supports GST 2A/2B Excel/JSON and purchase register Excel/CSV templates.">
        <div className="grid gap-4 md:grid-cols-2">
          <label className="text-sm font-bold">GSTIN<input readOnly value={workspace.profile?.gstin || ""} className="mt-2 w-full rounded-2xl border px-4 py-3 dark:border-white/10 dark:bg-slate-900" /></label>
          <label className="text-sm font-bold">Period<input readOnly value={workspace.profile?.return_period || ""} className="mt-2 w-full rounded-2xl border px-4 py-3 dark:border-white/10 dark:bg-slate-900" /></label>
          <label className="text-sm font-bold">2A/2B portal file<input type="file" onChange={(event) => setPortal(event.target.files?.[0] || null)} className="mt-2 w-full rounded-2xl border p-4 dark:border-white/10 dark:bg-slate-900" /></label>
          <label className="text-sm font-bold">Purchase register<input type="file" onChange={(event) => setBooks(event.target.files?.[0] || null)} className="mt-2 w-full rounded-2xl border p-4 dark:border-white/10 dark:bg-slate-900" /></label>
          <label className="text-sm font-bold">Tax tolerance<input value={taxTolerance} onChange={(event) => setTaxTolerance(event.target.value)} className="mt-2 w-full rounded-2xl border px-4 py-3 dark:border-white/10 dark:bg-slate-900" /></label>
          <label className="text-sm font-bold">Date tolerance days<input type="number" value={dateTolerance} onChange={(event) => setDateTolerance(Number(event.target.value))} className="mt-2 w-full rounded-2xl border px-4 py-3 dark:border-white/10 dark:bg-slate-900" /></label>
        </div>
        <button onClick={submit} disabled={busy || !workspace.profile} className="mt-5 inline-flex items-center gap-2 rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white disabled:opacity-50"><FileSearch className="size-4" /> {busy ? "Reconciling..." : "Run reconciliation"}</button>
        {error && <div className="mt-4 rounded-2xl bg-rose-50 p-4 text-sm font-bold text-rose-700">{error}</div>}
        {result && <div className="mt-5 rounded-3xl bg-emerald-50 p-5 text-sm font-bold text-emerald-700"><div>Batch #{result.id} completed.</div><div className="mt-2 grid gap-2 md:grid-cols-3"><span>Matched: {result.summary?.matched || 0}</span><span>Tax mismatch: {result.summary?.tax_mismatch || 0}</span><span>Missing: {Number(result.summary?.missing_in_portal || 0) + Number(result.summary?.missing_in_books || 0)}</span></div><Link className="mt-3 inline-flex underline" href={`/reconcile/results/${result.id}`}>Open results</Link></div>}
      </Panel>
    </div>
  </AppShell>;
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
