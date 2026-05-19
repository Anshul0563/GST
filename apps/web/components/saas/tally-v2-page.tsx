"use client";

import Link from "next/link";
import type { Route } from "next";
import type { ReactNode } from "react";
import { FormEvent, useEffect, useState } from "react";
import { Building2, CheckCircle2, Download, FileArchive, ReceiptText, UploadCloud } from "lucide-react";
import { AppShell } from "@/components/saas/app-shell";
import { EmptyState, Panel, StatCard, StatusPill } from "@/components/saas/ui";
import { money, useWorkspace } from "@/components/saas/workspace";
import { TallyCompany, TallyExportItem, createTallyCompany, generateTallyXml, getTallyExportUrl, getTallyHistory, getTallyMapping, saveTallyMapping, uploadTallyImport } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

const defaultMapping = {
  sales_ledger: "E-Commerce Sales",
  igst_ledger: "Output IGST",
  cgst_ledger: "Output CGST",
  sgst_ledger: "Output SGST",
  tcs_ledger: "TCS Receivable",
  tds_ledger: "TDS Receivable",
  discount_ledger: "Discount Allowed",
  round_off_ledger: "Round Off",
  shipping_ledger: "Shipping Charges",
  party_ledger: "eCommerce Debtors",
  stock_item: "Marketplace Item",
  uqc: "NOS",
};
const tallyWorkflows: Array<[string, Route]> = [["Company setup", "/modules/tally/company"], ["Import marketplace data", "/modules/tally/import"], ["Ledger mapping", "/modules/tally/mapping"], ["Generate export", "/modules/tally/export"], ["Export history", "/modules/tally/history"]];
const ledgerFields = Object.keys(defaultMapping) as Array<keyof typeof defaultMapping>;

export function TallyDashboardPage() {
  const workspace = useWorkspace();
  const [history, setHistory] = useState<TallyExportItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  useEffect(() => {
    if (!workspace.token) return;
    setLoadingHistory(true);
    getTallyHistory(workspace.token, workspace.profile?.id).then(setHistory).catch(() => setHistory([])).finally(() => setLoadingHistory(false));
  }, [workspace.token, workspace.profile?.id]);
  const latest = history[0];
  const importErrors = workspace.batches.reduce((sum, batch) => sum + batch.error_rows, 0);
  const readyTransactions = workspace.transactions.filter((row) => row.validation_status !== "error").length;
  const generatedVouchers = history.reduce((sum, item) => sum + item.voucher_count, 0);
  const latestValid = latest?.validation?.valid === true;
  return <AppShell title="eCom to Tally" subtitle="Convert normalized marketplace transactions into Tally-compatible XML vouchers." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }} actions={<Link href="/modules/tally/export" className="inline-flex items-center gap-2 rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white"><FileArchive className="size-4" /> Generate XML</Link>}>
    <div className="space-y-6">
      {!workspace.token ? <EmptyState title="Login required" body="Tally companies, imports and XML history are loaded from authenticated backend APIs." /> : null}
      <div className="grid gap-4 md:grid-cols-5">
        <StatCard label="Transactions ready" value={String(readyTransactions)} />
        <StatCard label="Taxable value" value={formatCurrency(money(workspace.summary?.total_taxable_value))} />
        <StatCard label="XML exports" value={String(history.length)} tone="green" />
        <StatCard label="Generated vouchers" value={String(generatedVouchers)} tone="saffron" />
        <StatCard label="Import errors" value={String(importErrors)} tone={importErrors ? "red" : "green"} />
      </div>
      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <Panel title="Tally workflow" subtitle="Every step is backed by real API state.">
          <div className="grid gap-4 md:grid-cols-2">
            {tallyWorkflows.map(([title, href], index) => <Link key={href} href={href} className="group rounded-3xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-1 hover:shadow-xl dark:border-white/10 dark:bg-slate-950">
              <div className="mb-4 flex size-10 items-center justify-center rounded-2xl bg-[#1746A2]/10 text-[#1746A2]">{index + 1}</div>
              <h3 className="text-lg font-black">{title}</h3>
              <p className="mt-2 text-sm text-slate-500">Open {title.toLowerCase()} workflow.</p>
            </Link>)}
          </div>
        </Panel>
        <Panel title="Latest XML status" subtitle="Export health from backend tally_exports.">
          {loadingHistory ? <EmptyState title="Loading exports" body="Fetching XML generation history." /> : latest ? <div className="space-y-4">
            <div className="rounded-3xl bg-slate-50 p-5 dark:bg-white/5">
              <div className="flex items-center justify-between gap-3">
                <div><b>Export #{latest.id}</b><p className="text-sm text-slate-500">{latest.period} / {latest.voucher_count} vouchers</p></div>
                <StatusPill status={latest.status} />
              </div>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-2xl bg-emerald-50 p-4 text-sm text-emerald-700 dark:bg-emerald-950/30"><b>Validation</b><p>{latestValid ? "XML validation passed" : "Review validation warnings"}</p></div>
              <a href={getTallyExportUrl(latest.id)} className="inline-flex items-center justify-center gap-2 rounded-2xl bg-[#10244d] px-4 py-3 text-sm font-bold text-white"><Download className="size-4" /> Download XML</a>
            </div>
          </div> : <EmptyState title="No XML generated" body="Generate your first Tally XML after importing transactions and saving mappings." />}
        </Panel>
      </div>
      <Panel title="Backend readiness" subtitle="Tally module reads real normalized transactions, companies, mappings and export records.">
        <div className="grid gap-3 text-sm md:grid-cols-4">
          <ReadinessItem icon={<Building2 className="size-4" />} label="Companies" value={String(workspace.companies.length)} />
          <ReadinessItem icon={<UploadCloud className="size-4" />} label="Imports" value={String(workspace.batches.length)} />
          <ReadinessItem icon={<ReceiptText className="size-4" />} label="Period" value={workspace.profile?.return_period || "--"} />
          <ReadinessItem icon={<CheckCircle2 className="size-4" />} label="GSTIN" value={workspace.profile?.gstin || "No GST profile"} />
        </div>
      </Panel>
    </div>
  </AppShell>;
}

export function TallyCompanyPage() {
  const workspace = useWorkspace();
  const [form, setForm] = useState({ company_name: "", gstin: "", financial_year: "2026-27", state: "", auto_create_ledger: true });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!workspace.token || !workspace.profile) return;
    setError("");
    setMessage("");
    try {
      await createTallyCompany(workspace.token, { profile_id: workspace.profile.id, ...form });
      await workspace.refresh();
      setForm({ company_name: "", gstin: "", financial_year: "2026-27", state: "", auto_create_ledger: true });
      setMessage("Tally company saved.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Could not save Tally company");
    }
  }
  return <AppShell title="Tally Company" subtitle="Create or select Tally company details used during XML generation." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }}>
    {!workspace.profile ? <EmptyState title="GST profile required" body="A Tally company is linked to a backend GST profile." /> : null}
    <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
      <Panel title="Add company" subtitle="Company is stored in backend tally_companies."><form onSubmit={submit} className="space-y-3">{(["company_name", "gstin", "financial_year", "state"] as const).map((key) => <input key={key} value={form[key]} onChange={(event) => setForm({ ...form, [key]: event.target.value })} className="w-full rounded-2xl border px-4 py-3 dark:border-white/10 dark:bg-slate-900" placeholder={key.replaceAll("_", " ")} required={key === "company_name"} />)}<label className="flex gap-2 text-sm font-bold"><input type="checkbox" checked={form.auto_create_ledger} onChange={(event) => setForm({ ...form, auto_create_ledger: event.target.checked })} /> Auto-create ledgers and stock items</label><button disabled={!workspace.profile} className="rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white disabled:opacity-50">Save company</button>{message && <div className="rounded-2xl bg-emerald-50 p-4 text-sm font-bold text-emerald-700">{message}</div>}{error && <div className="rounded-2xl bg-rose-50 p-4 text-sm font-bold text-rose-700">{error}</div>}</form></Panel>
      <Panel title="Saved companies" subtitle="Loaded from backend."><CompanyList companies={workspace.companies} /></Panel>
    </div>
  </AppShell>;
}

export function TallyImportPage() {
  const workspace = useWorkspace();
  const [platform, setPlatform] = useState("meesho");
  const [files, setFiles] = useState<FileList | null>(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit() {
    if (!workspace.token || !workspace.profile || !files?.length) return;
    setBusy(true);
    setError("");
    setStatus("");
    try {
      const batch = await uploadTallyImport(workspace.token, workspace.profile.id, platform, files);
      setStatus(`Batch #${batch.id} ${batch.status}. ${batch.parsed_rows} rows parsed and ${batch.error_rows} errors found.`);
      await workspace.refresh();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Tally import failed");
    } finally {
      setBusy(false);
    }
  }
  return <AppShell title="Tally Import" subtitle="Upload marketplace files directly into the shared normalized transaction engine." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }}>
    {!workspace.profile ? <EmptyState title="GST profile required" body="Select a GST profile and filing period before uploading marketplace files." /> : null}
    <div className="grid gap-6 xl:grid-cols-[1fr_0.8fr]">
      <Panel title="Marketplace import for Tally" subtitle="Uses backend /tally/import, which reuses the same Meesho/Amazon/Flipkart/Custom parsers.">
        <div className="grid gap-4 md:grid-cols-2">
          <select value={platform} onChange={(event) => setPlatform(event.target.value)} className="rounded-2xl border px-4 py-3 dark:border-white/10 dark:bg-slate-900"><option value="meesho">Meesho</option><option value="amazon">Amazon</option><option value="flipkart">Flipkart</option><option value="custom">Custom Excel</option></select>
          <input type="file" multiple onChange={(event) => setFiles(event.target.files)} className="rounded-2xl border p-4 dark:border-white/10 dark:bg-slate-900" />
        </div>
        <div className="mt-5 grid gap-3 rounded-3xl bg-slate-50 p-4 text-sm dark:bg-white/5 md:grid-cols-3">
          <div><b>GSTIN</b><p>{workspace.profile?.gstin || "--"}</p></div>
          <div><b>Period</b><p>{workspace.profile?.return_period || "--"}</p></div>
          <div><b>Selected files</b><p>{files?.length || 0}</p></div>
        </div>
        <button onClick={submit} disabled={busy || !workspace.profile || !files?.length} className="mt-5 inline-flex items-center gap-2 rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white disabled:opacity-50"><UploadCloud className="size-4" /> {busy ? "Importing..." : "Import for Tally"}</button>
        {status && <div className="mt-5 rounded-2xl bg-emerald-50 p-4 text-sm font-bold text-emerald-700">{status}</div>}
        {error && <div className="mt-5 rounded-2xl bg-rose-50 p-4 text-sm font-bold text-rose-700">{error}</div>}
      </Panel>
      <Panel title="Recent parser batches" subtitle="Backend import status and errors.">
        {workspace.batches.length ? <div className="space-y-3">{workspace.batches.slice(0, 6).map((batch) => <div key={batch.id} className="rounded-2xl bg-slate-50 p-4 text-sm dark:bg-white/5"><b className="capitalize">{batch.platform}</b><p>{batch.parsed_rows} rows / {batch.error_rows} errors / {batch.status}</p></div>)}</div> : <EmptyState title="No imports yet" body="Upload marketplace files to prepare Tally vouchers." />}
      </Panel>
    </div>
  </AppShell>;
}

export function TallyMappingPage() {
  const workspace = useWorkspace();
  const [companyId, setCompanyId] = useState("");
  const [mapping, setMapping] = useState(defaultMapping);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  async function load(company: string) {
    setCompanyId(company);
    if (!workspace.token || !company) return;
    setLoading(true);
    try {
      const result = await getTallyMapping(workspace.token, Number(company));
      setMapping({ ...defaultMapping, ...result.mapping });
    } finally {
      setLoading(false);
    }
  }
  async function save() {
    if (!workspace.token || !companyId) return;
    await saveTallyMapping(workspace.token, Number(companyId), mapping);
    setMessage("Mapping template saved.");
  }
  return <AppShell title="Ledger Mapping" subtitle="Save reusable Tally ledger templates per company." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }}>
    <Panel title="Mapping template" subtitle="Stored in backend tally_ledger_mappings.">
      <select value={companyId} onChange={(event) => load(event.target.value)} className="mb-5 w-full rounded-2xl border px-4 py-3 dark:border-white/10 dark:bg-slate-900"><option value="">Choose company</option>{workspace.companies.map((company) => <option key={company.id} value={company.id}>{company.company_name}</option>)}</select>
      {loading ? <EmptyState title="Loading mapping" body="Fetching saved ledger template from backend." /> : <div className="grid gap-3 md:grid-cols-2">{ledgerFields.map((key) => <label key={key} className="grid gap-2 text-sm font-bold"><span>{key.replaceAll("_", " ")}</span><input value={mapping[key]} onChange={(event) => setMapping({ ...mapping, [key]: event.target.value })} className="rounded-2xl border px-4 py-3 dark:border-white/10 dark:bg-slate-900" /></label>)}</div>}
      <button onClick={save} disabled={!companyId} className="mt-3 rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white disabled:opacity-50">Save mapping</button>
      {message && <div className="mt-4 rounded-2xl bg-emerald-50 p-4 text-sm font-bold text-emerald-700">{message}</div>}
    </Panel>
  </AppShell>;
}

export function TallyExportPage() {
  const workspace = useWorkspace();
  const [companyId, setCompanyId] = useState("");
  const [mapping, setMapping] = useState(defaultMapping);
  const [result, setResult] = useState<{ id: number; voucher_count: number; validation: Record<string, unknown>; download: string; download_excel: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function generate() {
    if (!workspace.token || !workspace.profile || !companyId) return;
    setBusy(true);
    setError("");
    try {
      const response = await generateTallyXml(workspace.token, { profile_id: workspace.profile.id, period: workspace.profile.return_period, company_id: Number(companyId), ledger_mapping: mapping, auto_create_ledgers: true });
      setResult(response);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Could not generate Tally XML");
    } finally {
      setBusy(false);
    }
  }
  const invoiceCount = workspace.transactions.filter((row) => row.doc_type === "INV").length;
  const creditCount = workspace.transactions.filter((row) => row.doc_type === "CRN").length;
  const debitCount = workspace.transactions.filter((row) => row.doc_type === "DBN").length;
  const missingMappings = ledgerFields.filter((key) => !mapping[key]?.trim());
  return <AppShell title="Generate Tally XML" subtitle="Preview mapping, generate XML and download voucher Excel." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }}>
    <div className="grid gap-6 xl:grid-cols-[0.8fr_1.2fr]">
      <Panel title="Export settings" subtitle="Select company and generate from normalized rows.">
        <select value={companyId} onChange={async (event) => { const value = event.target.value; setCompanyId(value); if (workspace.token && value) { const saved = await getTallyMapping(workspace.token, Number(value)); setMapping({ ...defaultMapping, ...saved.mapping }); } }} className="w-full rounded-2xl border px-4 py-3 dark:border-white/10 dark:bg-slate-900"><option value="">Choose company</option>{workspace.companies.map((company) => <option key={company.id} value={company.id}>{company.company_name}</option>)}</select>
        <div className="mt-5 grid gap-3 text-sm md:grid-cols-2">
          <ReadinessItem icon={<ReceiptText className="size-4" />} label="Invoices" value={String(invoiceCount)} />
          <ReadinessItem icon={<ReceiptText className="size-4" />} label="Credit notes" value={String(creditCount)} />
          <ReadinessItem icon={<ReceiptText className="size-4" />} label="Debit notes" value={String(debitCount)} />
          <ReadinessItem icon={<CheckCircle2 className="size-4" />} label="Missing mappings" value={String(missingMappings.length)} />
        </div>
        <button onClick={generate} disabled={busy || !workspace.profile || !companyId || !workspace.transactions.length || Boolean(missingMappings.length)} className="mt-5 inline-flex items-center gap-2 rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white disabled:opacity-50"><FileArchive className="size-4" /> {busy ? "Generating..." : "Generate XML"}</button>
        {result && <div className="mt-5 rounded-3xl bg-emerald-50 p-4 text-sm font-bold text-emerald-700">Generated {result.voucher_count} vouchers. Validation: {String(result.validation.valid)}</div>}
        {error && <div className="mt-5 rounded-3xl bg-rose-50 p-4 text-sm font-bold text-rose-700">{error}</div>}
        {!workspace.transactions.length ? <div className="mt-5 rounded-3xl bg-amber-50 p-4 text-sm font-bold text-amber-800">No normalized transactions found for this GST profile and period.</div> : null}
      </Panel>
      <Panel title="Mapping editor" subtitle="Customize ledgers before generation."><div className="grid gap-3 md:grid-cols-2">{ledgerFields.map((key) => <label key={key} className="grid gap-2 text-sm font-bold"><span>{key.replaceAll("_", " ")}</span><input value={mapping[key]} onChange={(event) => setMapping({ ...mapping, [key]: event.target.value })} className="rounded-2xl border px-4 py-3 dark:border-white/10 dark:bg-slate-900" /></label>)}</div></Panel>
    </div>
    <Panel title="Voucher preview" subtitle="Live preview from backend normalized transactions and dashboard summary.">
      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="Taxable value" value={formatCurrency(money(workspace.summary?.total_taxable_value))} />
        <StatCard label="IGST" value={formatCurrency(money(workspace.summary?.igst))} />
        <StatCard label="CGST" value={formatCurrency(money(workspace.summary?.cgst))} />
        <StatCard label="SGST" value={formatCurrency(money(workspace.summary?.sgst))} />
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-3">{workspace.summary?.platform_wise_sale?.slice(0, 6).map((item) => <div key={item.platform} className="rounded-2xl bg-slate-50 p-4 text-sm dark:bg-white/5"><b className="capitalize">{item.platform}</b><p>{item.rows} rows / {formatCurrency(money(item.taxable_value))}</p></div>)}</div>
    </Panel>
    {result && <div className="mt-6 flex gap-3"><a href={getTallyExportUrl(result.id)} className="inline-flex items-center gap-2 rounded-2xl bg-emerald-600 px-5 py-3 text-sm font-bold text-white"><Download className="size-4" /> Download XML</a><a href={getTallyExportUrl(result.id, "xlsx")} className="inline-flex items-center gap-2 rounded-2xl bg-[#1746A2] px-5 py-3 text-sm font-bold text-white"><Download className="size-4" /> Voucher Excel</a></div>}
  </AppShell>;
}

export function TallyHistoryPage() {
  const workspace = useWorkspace();
  const [history, setHistory] = useState<TallyExportItem[]>([]);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!workspace.token) return;
    setLoading(true);
    getTallyHistory(workspace.token, workspace.profile?.id).then(setHistory).catch(() => setHistory([])).finally(() => setLoading(false));
  }, [workspace.token, workspace.profile?.id]);
  return <AppShell title="Tally Export History" subtitle="Download center for generated XML and voucher Excel files." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }}><Panel title="Exports" subtitle="Loaded from backend tally_exports.">{loading ? <EmptyState title="Loading exports" body="Fetching generated XML files." /> : history.length ? <div className="space-y-3">{history.map((item) => <div key={item.id} className="grid gap-3 rounded-2xl bg-slate-50 p-4 text-sm dark:bg-white/5 md:grid-cols-[1fr_auto_auto_auto]"><div><b>Export #{item.id}</b><p className="text-xs text-slate-500">{item.period} / {item.voucher_count} vouchers</p></div><StatusPill status={item.status} /><a href={getTallyExportUrl(item.id)} className="rounded-xl bg-emerald-600 px-3 py-2 text-xs font-bold text-white">XML</a><a href={getTallyExportUrl(item.id, "xlsx")} className="rounded-xl bg-[#1746A2] px-3 py-2 text-xs font-bold text-white">Excel</a></div>)}</div> : <EmptyState title="No exports" body="Generated XML files will appear here." />}</Panel></AppShell>;
}

function CompanyList({ companies }: { companies: TallyCompany[] }) {
  return companies.length ? <div className="space-y-3">{companies.map((company) => <div key={company.id} className="rounded-2xl bg-slate-50 p-4 text-sm dark:bg-white/5"><div className="flex items-center justify-between gap-3"><b>{company.company_name}</b><StatusPill status={company.auto_create_ledger ? "auto ledger" : "manual ledger"} /></div><p className="mt-2 text-slate-500">{company.gstin || "No GSTIN"} / {company.financial_year || "FY not set"} / {company.state || "State not set"}</p></div>)}</div> : <EmptyState title="No Tally companies" body="Add your first company to generate XML." />;
}

function ReadinessItem({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return <div className="rounded-2xl bg-slate-50 p-4 dark:bg-white/5">
    <div className="mb-2 flex items-center gap-2 text-xs font-black uppercase tracking-wide text-slate-500">{icon}{label}</div>
    <p className="break-words text-base font-black text-slate-900 dark:text-white">{value}</p>
  </div>;
}
