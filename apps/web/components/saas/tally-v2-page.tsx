"use client";

import Link from "next/link";
import type { Route } from "next";
import type { ReactNode } from "react";
import { FormEvent, useEffect, useState } from "react";
import { Download, FileArchive, UploadCloud } from "lucide-react";
import { AppShell } from "@/components/saas/app-shell";
import { EmptyState, Panel, StatCard } from "@/components/saas/ui";
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
const tallyWorkflows: Array<[string, Route]> = [["Company setup", "/tally/company"], ["Import marketplace data", "/tally/import"], ["Ledger mapping", "/tally/mapping"], ["Generate export", "/tally/export"], ["Export history", "/tally/history"]];

export function TallyDashboardPage() {
  const workspace = useWorkspace();
  const [history, setHistory] = useState<TallyExportItem[]>([]);
  useEffect(() => {
    if (!workspace.token) return;
    getTallyHistory(workspace.token, workspace.profile?.id).then(setHistory).catch(() => setHistory([]));
  }, [workspace.token, workspace.profile?.id]);
  const latest = history[0];
  return <AppShell title="eCom to Tally" subtitle="Convert normalized marketplace transactions into Tally-compatible XML vouchers." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }} actions={<Link href="/tally/export" className="inline-flex items-center gap-2 rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white"><FileArchive className="size-4" /> Generate XML</Link>}>
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="Transactions ready" value={String(workspace.transactions.length)} />
        <StatCard label="Taxable value" value={formatCurrency(money(workspace.summary?.total_taxable_value))} />
        <StatCard label="XML exports" value={String(history.length)} tone="green" />
        <StatCard label="Last vouchers" value={String(latest?.voucher_count || 0)} tone="saffron" />
      </div>
      <div className="grid gap-6 xl:grid-cols-3">
        {tallyWorkflows.map(([title, href]) => <Link key={href} href={href} className="rounded-3xl border border-white/70 bg-white p-6 shadow-xl shadow-slate-200/60 transition hover:-translate-y-1 dark:border-white/10 dark:bg-slate-950"><h3 className="text-xl font-black">{title}</h3><p className="mt-3 text-sm text-slate-500">Open {title.toLowerCase()} workflow.</p></Link>)}
      </div>
    </div>
  </AppShell>;
}

export function TallyCompanyPage() {
  const workspace = useWorkspace();
  const [form, setForm] = useState({ company_name: "", gstin: "", financial_year: "2026-27", state: "", auto_create_ledger: true });
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!workspace.token || !workspace.profile) return;
    await createTallyCompany(workspace.token, { profile_id: workspace.profile.id, ...form });
    await workspace.refresh();
    setForm({ company_name: "", gstin: "", financial_year: "2026-27", state: "", auto_create_ledger: true });
  }
  return <AppShell title="Tally Company" subtitle="Create or select Tally company details used during XML generation." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }}>
    <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
      <Panel title="Add company" subtitle="Company is stored in backend tally_companies."><form onSubmit={submit} className="space-y-3">{(["company_name", "gstin", "financial_year", "state"] as const).map((key) => <input key={key} value={form[key]} onChange={(event) => setForm({ ...form, [key]: event.target.value })} className="w-full rounded-2xl border px-4 py-3 dark:border-white/10 dark:bg-slate-900" placeholder={key.replaceAll("_", " ")} />)}<label className="flex gap-2 text-sm font-bold"><input type="checkbox" checked={form.auto_create_ledger} onChange={(event) => setForm({ ...form, auto_create_ledger: event.target.checked })} /> Auto-create ledgers and stock items</label><button className="rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white">Save company</button></form></Panel>
      <Panel title="Saved companies" subtitle="Loaded from backend."><CompanyList companies={workspace.companies} /></Panel>
    </div>
  </AppShell>;
}

export function TallyImportPage() {
  const workspace = useWorkspace();
  const [platform, setPlatform] = useState("meesho");
  const [files, setFiles] = useState<FileList | null>(null);
  const [status, setStatus] = useState("");
  async function submit() {
    if (!workspace.token || !workspace.profile || !files?.length) return;
    const batch = await uploadTallyImport(workspace.token, workspace.profile.id, platform, files);
    setStatus(`Batch #${batch.id} ${batch.status}. Parsed rows will update in Imports timeline.`);
    await workspace.refresh();
  }
  return <AppShell title="Tally Import" subtitle="Upload marketplace files directly into the shared normalized transaction engine." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }}>
    <Panel title="Marketplace import for Tally" subtitle="Uses backend /tally/import, which reuses the same Meesho/Amazon/Flipkart/Custom parsers.">
      <div className="grid gap-4 md:grid-cols-2">
        <select value={platform} onChange={(event) => setPlatform(event.target.value)} className="rounded-2xl border px-4 py-3 dark:border-white/10 dark:bg-slate-900"><option value="meesho">Meesho</option><option value="amazon">Amazon</option><option value="flipkart">Flipkart</option><option value="custom">Custom Excel</option></select>
        <input type="file" multiple onChange={(event) => setFiles(event.target.files)} className="rounded-2xl border p-4 dark:border-white/10 dark:bg-slate-900" />
      </div>
      <button onClick={submit} className="mt-5 inline-flex items-center gap-2 rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white"><UploadCloud className="size-4" /> Import for Tally</button>
      {status && <div className="mt-5 rounded-2xl bg-emerald-50 p-4 text-sm font-bold text-emerald-700">{status}</div>}
    </Panel>
  </AppShell>;
}

export function TallyMappingPage() {
  const workspace = useWorkspace();
  const [companyId, setCompanyId] = useState("");
  const [mapping, setMapping] = useState(defaultMapping);
  const [message, setMessage] = useState("");
  async function load(company: string) {
    setCompanyId(company);
    if (!workspace.token || !company) return;
    const result = await getTallyMapping(workspace.token, Number(company));
    setMapping({ ...defaultMapping, ...result.mapping });
  }
  async function save() {
    if (!workspace.token || !companyId) return;
    await saveTallyMapping(workspace.token, Number(companyId), mapping);
    setMessage("Mapping template saved.");
  }
  return <AppShell title="Ledger Mapping" subtitle="Save reusable Tally ledger templates per company." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }}>
    <Panel title="Mapping template" subtitle="Stored in backend tally_ledger_mappings.">
      <select value={companyId} onChange={(event) => load(event.target.value)} className="mb-5 w-full rounded-2xl border px-4 py-3 dark:border-white/10 dark:bg-slate-900"><option value="">Choose company</option>{workspace.companies.map((company) => <option key={company.id} value={company.id}>{company.company_name}</option>)}</select>
      {Object.entries(mapping).map(([key, value]) => <label key={key} className="mb-3 grid gap-2 text-sm font-bold"><span>{key.replaceAll("_", " ")}</span><input value={value} onChange={(event) => setMapping({ ...mapping, [key]: event.target.value })} className="rounded-2xl border px-4 py-3 dark:border-white/10 dark:bg-slate-900" /></label>)}
      <button onClick={save} className="mt-3 rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white">Save mapping</button>
      {message && <div className="mt-4 rounded-2xl bg-emerald-50 p-4 text-sm font-bold text-emerald-700">{message}</div>}
    </Panel>
  </AppShell>;
}

export function TallyExportPage() {
  const workspace = useWorkspace();
  const [companyId, setCompanyId] = useState("");
  const [mapping, setMapping] = useState(defaultMapping);
  const [result, setResult] = useState<{ id: number; voucher_count: number; validation: Record<string, unknown>; download: string; download_excel: string } | null>(null);
  async function generate() {
    if (!workspace.token || !workspace.profile || !companyId) return;
    const response = await generateTallyXml(workspace.token, { profile_id: workspace.profile.id, period: workspace.profile.return_period, company_id: Number(companyId), ledger_mapping: mapping, auto_create_ledgers: true });
    setResult(response);
  }
  return <AppShell title="Generate Tally XML" subtitle="Preview mapping, generate XML and download voucher Excel." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }}>
    <div className="grid gap-6 xl:grid-cols-[0.8fr_1.2fr]">
      <Panel title="Export settings" subtitle="Select company and generate from normalized rows."><select value={companyId} onChange={async (event) => { const value = event.target.value; setCompanyId(value); if (workspace.token && value) { const saved = await getTallyMapping(workspace.token, Number(value)); setMapping({ ...defaultMapping, ...saved.mapping }); } }} className="w-full rounded-2xl border px-4 py-3 dark:border-white/10 dark:bg-slate-900"><option value="">Choose company</option>{workspace.companies.map((company) => <option key={company.id} value={company.id}>{company.company_name}</option>)}</select><button onClick={generate} className="mt-5 inline-flex items-center gap-2 rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white"><FileArchive className="size-4" /> Generate XML</button>{result && <div className="mt-5 rounded-3xl bg-emerald-50 p-4 text-sm font-bold text-emerald-700">Generated {result.voucher_count} vouchers. Validation: {String(result.validation.valid)}</div>}</Panel>
      <Panel title="Mapping editor" subtitle="Customize ledgers before generation.">{Object.entries(mapping).map(([key, value]) => <label key={key} className="mb-3 grid gap-2 text-sm font-bold"><span>{key.replaceAll("_", " ")}</span><input value={value} onChange={(event) => setMapping({ ...mapping, [key]: event.target.value })} className="rounded-2xl border px-4 py-3 dark:border-white/10 dark:bg-slate-900" /></label>)}</Panel>
    </div>
    {result && <div className="mt-6 flex gap-3"><a href={getTallyExportUrl(result.id)} className="inline-flex items-center gap-2 rounded-2xl bg-emerald-600 px-5 py-3 text-sm font-bold text-white"><Download className="size-4" /> Download XML</a><a href={getTallyExportUrl(result.id, "xlsx")} className="inline-flex items-center gap-2 rounded-2xl bg-[#1746A2] px-5 py-3 text-sm font-bold text-white"><Download className="size-4" /> Voucher Excel</a></div>}
  </AppShell>;
}

export function TallyHistoryPage() {
  const workspace = useWorkspace();
  const [history, setHistory] = useState<TallyExportItem[]>([]);
  useEffect(() => {
    if (!workspace.token) return;
    getTallyHistory(workspace.token, workspace.profile?.id).then(setHistory).catch(() => setHistory([]));
  }, [workspace.token, workspace.profile?.id]);
  return <AppShell title="Tally Export History" subtitle="Download center for generated XML and voucher Excel files." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }}><Panel title="Exports" subtitle="Loaded from backend tally_exports.">{history.length ? <div className="space-y-3">{history.map((item) => <div key={item.id} className="grid gap-3 rounded-2xl bg-slate-50 p-4 text-sm dark:bg-white/5 md:grid-cols-[1fr_auto_auto_auto]"><div><b>Export #{item.id}</b><p className="text-xs text-slate-500">{item.period} / {item.voucher_count} vouchers</p></div><span>{item.status}</span><a href={getTallyExportUrl(item.id)} className="rounded-xl bg-emerald-600 px-3 py-2 text-xs font-bold text-white">XML</a><a href={getTallyExportUrl(item.id, "xlsx")} className="rounded-xl bg-[#1746A2] px-3 py-2 text-xs font-bold text-white">Excel</a></div>)}</div> : <EmptyState title="No exports" body="Generated XML files will appear here." />}</Panel></AppShell>;
}

function CompanyList({ companies }: { companies: TallyCompany[] }) {
  return companies.length ? <div className="space-y-3">{companies.map((company) => <div key={company.id} className="rounded-2xl bg-slate-50 p-4 text-sm dark:bg-white/5"><b>{company.company_name}</b><p className="text-slate-500">{company.gstin || "No GSTIN"} / {company.financial_year || "FY not set"}</p></div>)}</div> : <EmptyState title="No Tally companies" body="Add your first company to generate XML." />;
}

function TallyDashboardFrame({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  const workspace = useWorkspace();
  return <AppShell title={title} subtitle={subtitle} profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }}>{children}</AppShell>;
}
