"use client";

import { useMemo, useState } from "react";
import { Download, Eye, Trash2 } from "lucide-react";
import { AppShell } from "@/components/saas/app-shell";
import { EmptyState, Panel, StatusPill } from "@/components/saas/ui";
import { money, useWorkspace } from "@/components/saas/workspace";
import { deleteTransaction, updateTransaction, Transaction } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

export function TransactionsPage() {
  const workspace = useWorkspace();
  const [query, setQuery] = useState("");
  const [platform, setPlatform] = useState("all");
  const [docType, setDocType] = useState("all");
  const [rate, setRate] = useState("all");
  const [state, setState] = useState("all");
  const [errorOnly, setErrorOnly] = useState(false);
  const [detail, setDetail] = useState<Transaction | null>(null);
  const platforms = Array.from(new Set(workspace.transactions.map((row) => row.platform))).sort();
  const states = Array.from(new Set(workspace.transactions.map((row) => row.buyer_state_code).filter(Boolean))).sort();
  const rates = Array.from(new Set(workspace.transactions.map((row) => String(row.gst_rate)))).sort();
  const rows = useMemo(() => workspace.transactions.filter((row) =>
    JSON.stringify(row).toLowerCase().includes(query.toLowerCase()) &&
    (platform === "all" || row.platform === platform) &&
    (docType === "all" || row.doc_type === docType) &&
    (rate === "all" || String(row.gst_rate) === rate) &&
    (state === "all" || row.buyer_state_code === state) &&
    (!errorOnly || row.validation_status === "error")
  ), [workspace.transactions, query, platform, docType, rate, state, errorOnly]);

  async function remove(row: Transaction) {
    if (!workspace.token) return;
    await deleteTransaction(workspace.token, row.id);
    await workspace.refresh();
  }

  async function inlineUpdate(row: Transaction, field: keyof Transaction, value: string) {
    if (!workspace.token) return;
    await updateTransaction(workspace.token, row.id, { [field]: value });
    await workspace.refresh();
  }

  function exportCsv() {
    const header = ["platform", "invoice_no", "order_id", "invoice_date", "buyer_state_code", "hsn", "taxable_value", "gst_rate", "igst", "cgst", "sgst", "doc_type"];
    const csv = [header.join(","), ...rows.map((row) => header.map((key) => JSON.stringify((row as unknown as Record<string, unknown>)[key] || "")).join(","))].join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "gst-bharat-transactions.csv";
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <AppShell requiresSubscription token={workspace.token} user={workspace.user} productName="GST Online Seller" title="Transactions" subtitle="Normalized transaction database with professional filters, inline correction and detail drawer." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }} actions={<button onClick={exportCsv} className="inline-flex items-center gap-2 rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white"><Download className="size-4" /> Export CSV</button>}>
      {!workspace.token ? <EmptyState title="Login required" body="Transactions are loaded from the backend for your authenticated workspace." /> : !workspace.profile ? <EmptyState title="No GST profile selected" body="Create a GST profile before importing and managing transactions." /> : null}
      <Panel title="Merged transaction table" subtitle={`${rows.length} of ${workspace.transactions.length} rows visible`}>
        <div className="mb-5 grid gap-3 md:grid-cols-6">
          <input value={query} onChange={(event) => setQuery(event.target.value)} className="rounded-2xl border border-slate-200 px-4 py-3 text-sm md:col-span-2 dark:border-white/10 dark:bg-slate-900" placeholder="Search invoices, orders, SKU" />
          <select value={platform} onChange={(event) => setPlatform(event.target.value)} className="rounded-2xl border border-slate-200 px-3 py-3 text-sm dark:border-white/10 dark:bg-slate-900"><option value="all">All platforms</option>{platforms.map((item) => <option key={item}>{item}</option>)}</select>
          <select value={state} onChange={(event) => setState(event.target.value)} className="rounded-2xl border border-slate-200 px-3 py-3 text-sm dark:border-white/10 dark:bg-slate-900"><option value="all">All POS</option>{states.map((item) => <option key={item || ""}>{item}</option>)}</select>
          <select value={rate} onChange={(event) => setRate(event.target.value)} className="rounded-2xl border border-slate-200 px-3 py-3 text-sm dark:border-white/10 dark:bg-slate-900"><option value="all">All rates</option>{rates.map((item) => <option key={item}>{item}%</option>)}</select>
          <select value={docType} onChange={(event) => setDocType(event.target.value)} className="rounded-2xl border border-slate-200 px-3 py-3 text-sm dark:border-white/10 dark:bg-slate-900"><option value="all">All docs</option><option value="invoice">Invoice</option><option value="credit_note">Credit note</option><option value="debit_note">Debit note</option></select>
        </div>
        <label className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-600"><input type="checkbox" checked={errorOnly} onChange={(event) => setErrorOnly(event.target.checked)} /> Show errors only</label>
        {rows.length ? <div className="max-h-[620px] overflow-auto rounded-3xl border border-slate-200 dark:border-white/10"><table className="min-w-[1280px] text-left text-sm"><thead className="sticky top-0 bg-slate-50 text-xs uppercase text-slate-500 dark:bg-slate-900"><tr>{["Platform", "Invoice", "Order", "Date", "POS", "HSN", "Taxable", "Rate", "IGST", "CGST", "SGST", "Doc", "Status", ""].map((head) => <th key={head} className="px-4 py-3">{head}</th>)}</tr></thead><tbody className="divide-y divide-slate-100 dark:divide-white/10">{rows.map((row) => <tr key={row.id} className="bg-white hover:bg-slate-50 dark:bg-slate-950 dark:hover:bg-white/5"><td className="px-4 py-3 font-bold capitalize">{row.platform}</td><td>{row.invoice_no}</td><td>{row.order_id}</td><td>{row.invoice_date}</td><td><input defaultValue={row.buyer_state_code || ""} onBlur={(event) => inlineUpdate(row, "buyer_state_code", event.target.value)} className="w-14 rounded-lg border px-2 py-1 dark:border-white/10 dark:bg-slate-900" /></td><td>{row.hsn}</td><td>{formatCurrency(money(row.taxable_value))}</td><td>{row.gst_rate}%</td><td>{row.igst}</td><td>{row.cgst}</td><td>{row.sgst}</td><td>{row.doc_type}</td><td><StatusPill status={row.validation_status} /></td><td className="flex gap-2 px-4 py-3"><button onClick={() => setDetail(row)} className="rounded-xl bg-slate-100 p-2 dark:bg-white/10"><Eye className="size-4" /></button><button onClick={() => remove(row)} className="rounded-xl bg-rose-50 p-2 text-rose-600"><Trash2 className="size-4" /></button></td></tr>)}</tbody></table></div> : <EmptyState title="No transactions found" body="Upload marketplace files or clear filters to see normalized rows." />}
      </Panel>
      {detail && <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/40" onClick={() => setDetail(null)}><aside onClick={(event) => event.stopPropagation()} className="h-full w-full max-w-xl overflow-auto bg-white p-6 shadow-2xl dark:bg-slate-950"><h2 className="text-2xl font-black">Row details</h2><p className="mt-1 text-sm text-slate-500">{detail.invoice_no || detail.order_id}</p><pre className="mt-6 whitespace-pre-wrap rounded-3xl bg-slate-950 p-5 text-xs text-slate-100">{JSON.stringify(detail, null, 2)}</pre></aside></div>}
    </AppShell>
  );
}
