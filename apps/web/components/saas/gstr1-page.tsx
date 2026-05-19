"use client";

import { useCallback, useEffect, useState } from "react";
import { Download, FileJson, FileSpreadsheet } from "lucide-react";
import { AppShell } from "@/components/saas/app-shell";
import { EmptyState, Panel, StatCard, StatusPill } from "@/components/saas/ui";
import { money, useWorkspace } from "@/components/saas/workspace";
import { Gstr1ExportItem, downloadUrl, generateGstr1, getGstr1History } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

export function Gstr1Page() {
  const workspace = useWorkspace();
  const [downloads, setDownloads] = useState<{ download_json: string; download_excel: string } | null>(null);
  const [history, setHistory] = useState<Gstr1ExportItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const loadHistory = useCallback(async () => {
    if (!workspace.token) return;
    setLoadingHistory(true);
    try {
      const items = await getGstr1History(workspace.token, workspace.profile?.id);
      setHistory(items);
    } catch {
      setHistory([]);
    } finally {
      setLoadingHistory(false);
    }
  }, [workspace.token, workspace.profile?.id]);
  useEffect(() => {
    loadHistory();
  }, [loadHistory]);
  async function generate() {
    if (!workspace.token || !workspace.profile) return;
    setBusy(true);
    setError("");
    try {
      const result = await generateGstr1(workspace.token, workspace.profile);
      setDownloads({ download_json: result.download_json, download_excel: result.download_excel });
      await workspace.refresh();
      await loadHistory();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Could not generate GSTR-1 files");
    } finally {
      setBusy(false);
    }
  }
  async function exportFile(format: "json" | "excel") {
    if (!workspace.token || !workspace.profile) return;
    setBusy(true);
    setError("");
    try {
      const result = await generateGstr1(workspace.token, workspace.profile);
      setDownloads({ download_json: result.download_json, download_excel: result.download_excel });
      await workspace.refresh();
      await loadHistory();
      window.location.href = downloadUrl(format === "json" ? result.download_json : result.download_excel);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : `Could not export GSTR-1 ${format.toUpperCase()}`);
    } finally {
      setBusy(false);
    }
  }
  const summary = workspace.summary;
  const previewTotals = (workspace.preview?.b2cs || []).reduce((total, row) => ({
    taxable: total.taxable + money(row.txval),
    igst: total.igst + money(row.iamt),
    cgst: total.cgst + money(row.camt),
    sgst: total.sgst + money(row.samt),
    cess: total.cess + money(row.csamt)
  }), { taxable: 0, igst: 0, cgst: 0, sgst: 0, cess: 0 });
  const previewGst = previewTotals.igst + previewTotals.cgst + previewTotals.sgst + previewTotals.cess;
  const checks = [
    ["GST profile selected", Boolean(workspace.profile)],
    ["Transactions imported", workspace.transactions.length > 0],
    ["No validation blockers", !summary?.pending_errors],
    ["B2CS preview generated", Boolean(workspace.preview?.b2cs.length)],
    ["SUPECO preview generated", Boolean(workspace.preview?.supeco?.supeco_det?.length)]
  ];

  return (
    <AppShell title="GSTR-1 Preview" subtitle="Preview B2CS, SUPECO and document issue summaries, then export GST portal-compatible JSON or Excel from the same workspace." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }} actions={<div className="flex flex-wrap gap-3"><button onClick={() => exportFile("json")} disabled={busy || !workspace.profile || Boolean(summary?.pending_errors)} className="inline-flex items-center gap-2 rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-50"><FileJson className="size-4" /> {busy ? "Preparing..." : "JSON Export"}</button><button onClick={() => exportFile("excel")} disabled={busy || !workspace.profile || Boolean(summary?.pending_errors)} className="inline-flex items-center gap-2 rounded-2xl bg-[#1746A2] px-5 py-3 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-50"><FileSpreadsheet className="size-4" /> {busy ? "Preparing..." : "Excel Export"}</button></div>}>
      <div className="space-y-6">
        {!workspace.token ? <EmptyState title="Login required" body="GSTR-1 preview and generation use authenticated backend APIs." /> : !workspace.profile ? <EmptyState title="Create GST profile first" body="GSTR-1 generation needs GSTIN, filing frequency and return period." /> : null}
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          <StatCard label="Taxable value" value={formatCurrency(money(summary?.total_taxable_value))} tone="blue" />
          <StatCard label="IGST" value={formatCurrency(money(summary?.igst))} tone="green" />
          <StatCard label="CGST" value={formatCurrency(money(summary?.cgst))} tone="saffron" />
          <StatCard label="SGST" value={formatCurrency(money(summary?.sgst))} tone="saffron" />
          <StatCard label="Total GST" value={formatCurrency(money(summary?.total_gst))} tone="green" />
        </div>
        <div className="grid gap-6 xl:grid-cols-[1fr_0.8fr]">
          <Panel title="B2CS preview" subtitle="Grouped by supply type, rate, POS and OE type.">
            {workspace.preview?.b2cs.length ? <div className="overflow-auto rounded-3xl border border-slate-200 dark:border-white/10"><table className="min-w-[760px] text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500 dark:bg-slate-900"><tr>{["Supply", "Rate", "POS", "Taxable", "IGST", "CGST", "SGST"].map((head) => <th key={head} className="px-4 py-3 text-left">{head}</th>)}</tr></thead><tbody>{workspace.preview.b2cs.map((row) => <tr key={`${row.sply_ty}-${row.rt}-${row.pos}`} className="border-t border-slate-100 dark:border-white/10"><td className="px-4 py-3">{row.sply_ty}</td><td>{row.rt}%</td><td>{row.pos}</td><td>{formatCurrency(row.txval)}</td><td>{formatCurrency(row.iamt)}</td><td>{formatCurrency(row.camt)}</td><td>{formatCurrency(row.samt)}</td></tr>)}</tbody></table></div> : <EmptyState title="No B2CS rows" body="Import transactions to generate preview." />}
          </Panel>
          <Panel title="Validation checklist" subtitle="Generation readiness.">
            <div className="space-y-3">{checks.map(([label, ok]) => <div key={String(label)} className="flex items-center justify-between rounded-2xl bg-slate-50 p-3 text-sm dark:bg-white/5"><span>{label}</span><StatusPill status={ok ? "completed" : "pending"} /></div>)}</div>
            <div className="mt-5 rounded-3xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
              <b>Backend preview reconciliation</b>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                <span>B2CS taxable</span><b>{formatCurrency(previewTotals.taxable)}</b>
                <span>B2CS GST</span><b>{formatCurrency(previewGst)}</b>
                <span>Dashboard taxable delta</span><b>{formatCurrency(money(summary?.total_taxable_value) - previewTotals.taxable)}</b>
                <span>Dashboard GST delta</span><b>{formatCurrency(money(summary?.total_gst) - previewGst)}</b>
              </div>
            </div>
            <div className="mt-5 flex flex-wrap gap-3">
              <button onClick={generate} disabled={busy || !workspace.profile || Boolean(summary?.pending_errors)} className="rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-50">{busy ? "Generating files..." : "Save to history"}</button>
              {downloads && <><a href={downloadUrl(downloads.download_json)} className="inline-flex items-center gap-2 rounded-2xl bg-emerald-600 px-5 py-3 text-sm font-bold text-white"><Download className="size-4" /> JSON</a><a href={downloadUrl(downloads.download_excel)} className="inline-flex items-center gap-2 rounded-2xl bg-[#1746A2] px-5 py-3 text-sm font-bold text-white"><FileSpreadsheet className="size-4" /> Excel</a></>}
            </div>
            {error && <div className="mt-5 rounded-2xl bg-rose-50 p-4 text-sm font-bold text-rose-700">{error}</div>}
          </Panel>
        </div>
        <div className="grid gap-6 xl:grid-cols-2">
          <Panel title="SUPECO preview" subtitle="Ecommerce operator level summary."><pre className="max-h-80 overflow-auto rounded-3xl bg-slate-950 p-5 text-xs text-slate-100">{JSON.stringify(workspace.preview?.supeco || {}, null, 2)}</pre></Panel>
          <Panel title="Document issue preview" subtitle="Invoice, credit note and debit note ranges."><pre className="max-h-80 overflow-auto rounded-3xl bg-slate-950 p-5 text-xs text-slate-100">{JSON.stringify(workspace.preview?.doc_issue || {}, null, 2)}</pre></Panel>
        </div>
        <Panel title="Generated file history" subtitle="JSON and Excel exports are saved by backend export ID.">
          {loadingHistory ? <EmptyState title="Loading exports" body="Fetching generated GSTR-1 files." /> : history.length ? <div className="space-y-3">{history.map((item) => <div key={item.id} className="grid gap-3 rounded-2xl bg-slate-50 p-4 text-sm dark:bg-white/5 md:grid-cols-[1fr_auto_auto_auto]">
            <div><b>Export #{item.id}</b><p className="text-xs text-slate-500">{item.period} / {new Date(item.created_at).toLocaleString()}</p></div>
            <StatusPill status={item.status} />
            <a href={downloadUrl(item.download_json)} className="rounded-xl bg-emerald-600 px-3 py-2 text-center text-xs font-bold text-white">JSON</a>
            <a href={downloadUrl(item.download_excel)} className="rounded-xl bg-[#1746A2] px-3 py-2 text-center text-xs font-bold text-white">Excel</a>
          </div>)}</div> : <EmptyState title="No generated files" body="Generated JSON and Excel files will appear here." />}
        </Panel>
      </div>
    </AppShell>
  );
}
