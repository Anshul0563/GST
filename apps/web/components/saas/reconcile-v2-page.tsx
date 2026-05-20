"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Download, FileSpreadsheet, ReceiptText, SlidersHorizontal, UploadCloud } from "lucide-react";
import { AppShell } from "@/components/saas/app-shell";
import { EmptyState, Panel, StatCard, StatusPill } from "@/components/saas/ui";
import { money, useWorkspace } from "@/components/saas/workspace";
import { ReconcileHistoryItem, ReconcileReport, getReconcileDownloadUrl, getReconcileHistory, getReconcileResults, uploadReconcileFilesV2 } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

const categories = ["matched", "partially_matched", "tax_mismatch", "invoice_mismatch", "missing_in_portal", "missing_in_books", "duplicate_invoice", "invalid_gstin"];

export function ReconcileDashboardPage() {
  const workspace = useWorkspace();
  const activeProfileId = workspace.profile?.id;
  const activeProfilePeriod = workspace.profile?.return_period;
  const [history, setHistory] = useState<ReconcileHistoryItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  useEffect(() => {
    if (!workspace.token || !activeProfileId) {
      setHistory([]);
      return;
    }
    setHistory([]);
    setLoadingHistory(true);
    getReconcileHistory(workspace.token, activeProfileId).then(setHistory).catch(() => setHistory([])).finally(() => setLoadingHistory(false));
  }, [workspace.token, activeProfileId, activeProfilePeriod]);
  const latest = history[0];
  const chart = history.slice(0, 8).reverse().map((item) => ({ name: `#${item.id}`, matched: item.matched_rows, mismatch: item.mismatch_rows }));
  const totalRuns = history.length;
  const totalMismatches = history.reduce((sum, item) => sum + item.mismatch_rows, 0);
  return <AppShell title="2A/2B Reconcile" subtitle="Professional ITC reconciliation across GST portal 2A/2B and purchase books." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }} actions={<Link href="/modules/reconcile/upload" className="inline-flex items-center gap-2 rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white"><UploadCloud className="size-4" /> New reconcile</Link>}>
    <div className="space-y-6">
      {!workspace.token ? <EmptyState title="Login required" body="Reconciliation history is loaded from authenticated backend APIs." /> : null}
      <div className="grid gap-4 md:grid-cols-5">
        <StatCard label="Runs" value={String(totalRuns)} />
        <StatCard label="Portal invoices" value={String(latest?.portal_rows || 0)} />
        <StatCard label="Book invoices" value={String(latest?.book_rows || 0)} />
        <StatCard label="Matched" value={`${latest?.summary?.matched_percent || 0}%`} tone="green" />
        <StatCard label="Open mismatches" value={String(totalMismatches)} tone={totalMismatches ? "red" : "green"} />
      </div>
      <Panel title="Active reconcile workspace" subtitle="The dashboard follows the selected GST profile and return period.">
        <div className="grid gap-3 text-sm md:grid-cols-4">
          <Readiness label="GSTIN" ready={Boolean(workspace.profile?.gstin)} value={workspace.profile?.gstin || "No GST profile"} />
          <Readiness label="Return period" ready={Boolean(workspace.profile?.return_period)} value={workspace.profile?.return_period || "--"} />
          <Readiness label="Frequency" ready={Boolean(workspace.profile?.filing_frequency)} value={workspace.profile?.filing_frequency || "--"} />
          <Link href="/modules/online-seller/profile" className="rounded-2xl bg-[#10244d] px-4 py-3 text-center text-sm font-bold text-white">Change period</Link>
        </div>
      </Panel>
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
  const activeProfileKey = workspace.profile ? `${workspace.profile.id}:${workspace.profile.return_period}` : "";
  useEffect(() => {
    setPortal(null);
    setBooks(null);
    setResult(null);
    setBusy(false);
    setError("");
  }, [activeProfileKey]);
  async function submit() {
    if (!workspace.token || !workspace.profile || !portal || !books) return;
    setBusy(true);
    setError("");
    try {
      const upload = await uploadReconcileFilesV2(workspace.token, workspace.profile.id, portal, books, { tax_tolerance: taxTolerance, date_tolerance_days: dateTolerance, enable_date_tolerance: true, enable_fuzzy_invoice: true });
      setResult(upload);
      await workspace.refresh();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Reconciliation failed");
    } finally {
      setBusy(false);
    }
  }
  const summary = result?.summary || {};
  const summaryNumber = (key: string) => Number(summary[key] || 0);
  const unmatched = summaryNumber("missing_in_books") + summaryNumber("invalid_gstin");
  return <AppShell title="Upload & Reconcile" subtitle="Upload GST portal 2A/2B and purchase register files, tune tolerances, then generate match results." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }} actions={<a href="data:text/csv;charset=utf-8,Supplier GSTIN,Invoice Number,Invoice Date,Taxable Value,IGST,CGST,SGST%0A" download="gst-bharat-2a-2b-sample.csv" className="inline-flex items-center gap-2 rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white"><FileSpreadsheet className="size-4" /> Sample CSV</a>}>
    <div className="space-y-6">
      {!workspace.token ? <EmptyState title="Login required" body="Login to upload 2A/2B and purchase register files." /> : !workspace.profile ? <EmptyState title="GST profile required" body="Create or select GST profile before uploading reconciliation files." /> : null}
      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="GSTIN" value={workspace.profile?.gstin || "Not set"} />
        <StatCard label="Return period" value={workspace.profile?.return_period || "--"} />
        <StatCard label="2A/2B file" value={portal ? "Selected" : "Pending"} tone={portal ? "green" : "saffron"} />
        <StatCard label="Purchase file" value={books ? "Selected" : "Pending"} tone={books ? "green" : "saffron"} />
      </div>
      <div className="grid gap-6 xl:grid-cols-[1fr_1fr_0.8fr]">
        <Panel title="Upload 2A/2B" subtitle="GST portal file with supplier invoice and tax data.">
          <UploadBox title="GST portal 2A/2B file" file={portal} onFile={setPortal} />
        </Panel>
        <Panel title="Upload Purchase Register" subtitle="Books purchase register used for ITC matching.">
          <UploadBox title="Purchase register file" file={books} onFile={setBooks} />
        </Panel>
        <Panel title="Reconcile settings" subtitle="Tolerance and fuzzy matching controls.">
          <div className="space-y-4">
            <label className="grid gap-2 text-sm font-bold">Tax difference ignore
              <div className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 dark:border-white/10 dark:bg-slate-900">
                <span className="text-slate-400">INR</span>
                <input value={taxTolerance} onChange={(event) => setTaxTolerance(event.target.value)} className="min-w-0 flex-1 bg-transparent text-sm font-semibold outline-none" />
              </div>
            </label>
            <label className="grid gap-2 text-sm font-bold">Date tolerance days
              <input type="number" min={0} value={dateTolerance} onChange={(event) => setDateTolerance(Number(event.target.value))} className="rounded-2xl border border-slate-200 px-4 py-3 text-sm font-semibold outline-none dark:border-white/10 dark:bg-slate-900" />
            </label>
            <div className="rounded-2xl bg-slate-50 p-4 text-sm text-slate-600 dark:bg-white/5 dark:text-slate-300">
              <div className="mb-2 flex items-center gap-2 font-black text-slate-900 dark:text-white"><SlidersHorizontal className="size-4 text-[#1746A2]" /> Enabled checks</div>
              <p>Date tolerance and fuzzy invoice matching are applied during backend reconciliation.</p>
            </div>
          </div>
        </Panel>
      </div>
      <Panel title="Run reconcile" subtitle="Both files are required. Results are saved as a reconciliation batch with downloadable Excel.">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="grid gap-3 text-sm md:grid-cols-3">
            <Readiness label="GST profile" ready={Boolean(workspace.profile)} />
            <Readiness label="2A/2B upload" ready={Boolean(portal)} />
            <Readiness label="Purchase register" ready={Boolean(books)} />
          </div>
          <button onClick={submit} disabled={busy || !workspace.profile || !portal || !books} className="inline-flex items-center justify-center gap-2 rounded-2xl bg-[#10244d] px-6 py-4 text-sm font-bold text-white shadow-xl shadow-blue-950/20 disabled:cursor-not-allowed disabled:opacity-45">
            <UploadCloud className="size-4" /> {busy ? "Reconciling..." : "Reconcile now"}
          </button>
        </div>
        {error && <div className="mt-5 rounded-2xl bg-rose-50 p-4 text-sm font-bold text-rose-700">{error}</div>}
      </Panel>
      {result && <Panel title={`Match results batch #${result.id}`} subtitle="Open explorer for row-level mismatch reasons or download Excel report.">
        <div className="grid gap-4 md:grid-cols-4 xl:grid-cols-6">
          <StatCard label="Portal rows" value={String(summaryNumber("portal_rows"))} />
          <StatCard label="Matched" value={String(summaryNumber("matched"))} tone="green" />
          <StatCard label="Tax mismatch" value={String(summaryNumber("tax_mismatch"))} tone="saffron" />
          <StatCard label="Invoice mismatch" value={String(summaryNumber("invoice_mismatch"))} tone="saffron" />
          <StatCard label="Unmatched" value={String(unmatched)} tone={unmatched ? "red" : "green"} />
          <StatCard label="ITC risk" value={formatCurrency(summaryNumber("itc_risk_amount"))} tone={summaryNumber("itc_risk_amount") ? "red" : "green"} />
        </div>
        <div className="mt-5 flex flex-wrap gap-3">
          <Link href={`/modules/reconcile/results/${result.id}`} className="inline-flex items-center gap-2 rounded-2xl bg-[#1746A2] px-5 py-3 text-sm font-bold text-white"><ReceiptText className="size-4" /> Match Results</Link>
          <a href={getReconcileDownloadUrl(result.id)} className="inline-flex items-center gap-2 rounded-2xl bg-emerald-600 px-5 py-3 text-sm font-bold text-white"><Download className="size-4" /> Download Excel</a>
        </div>
      </Panel>}
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
  const activeProfileId = workspace.profile?.id;
  const activeProfilePeriod = workspace.profile?.return_period;
  const [history, setHistory] = useState<ReconcileHistoryItem[]>([]);
  useEffect(() => {
    if (!workspace.token || !activeProfileId) {
      setHistory([]);
      return;
    }
    setHistory([]);
    getReconcileHistory(workspace.token, activeProfileId).then(setHistory).catch(() => setHistory([]));
  }, [workspace.token, activeProfileId, activeProfilePeriod]);
  return <AppShell title="Reconciliation History" subtitle="Download center for previous 2A/2B matching runs." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }}>
    <Panel title="History" subtitle="All batches are loaded from backend."><HistoryList history={history} /></Panel>
  </AppShell>;
}

function HistoryList({ history }: { history: ReconcileHistoryItem[] }) {
  return history.length ? <div className="space-y-3">{history.map((item) => <div key={item.id} className="grid gap-3 rounded-2xl bg-slate-50 p-4 text-sm dark:bg-white/5 md:grid-cols-[1fr_auto_auto_auto]"><div><b>Batch #{item.id}</b><p className="text-xs text-slate-500">{item.portal_rows} portal / {item.book_rows} books</p></div><StatusPill status={item.status} /><Link href={`/modules/reconcile/results/${item.id}`} className="rounded-xl bg-[#1746A2] px-3 py-2 text-xs font-bold text-white">Open</Link><a href={getReconcileDownloadUrl(item.id)} className="rounded-xl bg-emerald-600 px-3 py-2 text-xs font-bold text-white">Download</a></div>)}</div> : <EmptyState title="No history" body="Completed reconciliation batches will appear here." />;
}

function UploadBox({ title, file, onFile }: { title: string; file: File | null; onFile: (file: File | null) => void }) {
  return <label className="group flex min-h-48 cursor-pointer flex-col items-center justify-center rounded-3xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center transition hover:border-[#1746A2] hover:bg-blue-50/60 dark:border-white/10 dark:bg-white/5 dark:hover:bg-white/10">
    <div className="grid size-14 place-items-center rounded-2xl bg-white text-[#1746A2] shadow-sm transition group-hover:scale-105 dark:bg-slate-900">
      <FileSpreadsheet className="size-6" />
    </div>
    <h3 className="mt-4 text-base font-black">{title}</h3>
    <p className="mt-2 max-w-xs text-sm text-slate-500">{file ? file.name : "Choose CSV, XLS or XLSX file"}</p>
    <span className="mt-4 rounded-2xl bg-[#10244d] px-4 py-2 text-xs font-bold text-white">{file ? "Replace file" : "Select file"}</span>
    <input type="file" accept=".csv,.xls,.xlsx" className="sr-only" onChange={(event) => onFile(event.target.files?.[0] || null)} />
  </label>;
}

function Readiness({ label, ready, value }: { label: string; ready: boolean; value?: string }) {
  return <div className={`rounded-2xl px-4 py-3 font-bold ${ready ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300" : "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300"}`}>
    <span className="text-xs uppercase tracking-wide">{label}</span>
    <p className="mt-1 break-words text-sm">{value || (ready ? "Ready" : "Pending")}</p>
  </div>;
}
