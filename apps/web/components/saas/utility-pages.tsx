"use client";

import { FormEvent, useState } from "react";
import { CreditCard, FileArchive, FileSpreadsheet, Settings } from "lucide-react";
import { AppShell } from "@/components/saas/app-shell";
import { EmptyState, Panel, StatCard } from "@/components/saas/ui";
import { money, useWorkspace } from "@/components/saas/workspace";
import { createProfile, createTallyCompany, downloadUrl, generateTallyXml, uploadReconcileFiles } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

export function ReconciliationPage() {
  const workspace = useWorkspace();
  const [portal, setPortal] = useState<File | null>(null);
  const [books, setBooks] = useState<File | null>(null);
  const [result, setResult] = useState<string>("");
  async function submit() {
    if (!workspace.token || !workspace.profile || !portal || !books) return;
    const upload = await uploadReconcileFiles(workspace.token, workspace.profile.id, portal, books);
    setResult(`Batch ${upload.id} ${upload.status}. Matching summary will populate as reconciliation engine is expanded.`);
  }
  return <AppShell title="2A/2B Reconciliation" subtitle="Upload GST portal 2A/2B and purchase register files for matching and query report generation." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }}><div className="grid gap-6 xl:grid-cols-[0.8fr_1.2fr]"><Panel title="Reconcile workflow" subtitle="Designed for supplier GSTIN, invoice number, date and tax amount matching."><div className="space-y-3">{["Upload portal 2A/2B", "Upload purchase register", "Run match engine", "Review mismatch buckets", "Download query report"].map((item, index) => <div key={item} className="rounded-2xl bg-slate-50 p-4 text-sm font-bold dark:bg-white/5">{index + 1}. {item}</div>)}</div></Panel><Panel title="Upload files" subtitle="Current backend stores batch/report status; deeper matching remains a backend roadmap item."><div className="grid gap-4 md:grid-cols-2"><input type="file" onChange={(event) => setPortal(event.target.files?.[0] || null)} className="rounded-2xl border p-4 dark:border-white/10 dark:bg-slate-900" /><input type="file" onChange={(event) => setBooks(event.target.files?.[0] || null)} className="rounded-2xl border p-4 dark:border-white/10 dark:bg-slate-900" /></div><button onClick={submit} className="mt-5 rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white">Run reconciliation</button>{result ? <div className="mt-4 rounded-2xl bg-emerald-50 p-4 text-sm font-bold text-emerald-700">{result}</div> : <EmptyState title="No reconciliation run yet" body="Upload both files to begin." />}</Panel></div></AppShell>;
}

export function TallyPage() {
  const workspace = useWorkspace();
  const [companyName, setCompanyName] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [download, setDownload] = useState("");
  async function addCompany(event: FormEvent) {
    event.preventDefault();
    if (!workspace.token || !workspace.profile || !companyName) return;
    await createTallyCompany(workspace.token, { profile_id: workspace.profile.id, company_name: companyName });
    setCompanyName("");
    await workspace.refresh();
  }
  async function generate() {
    if (!workspace.token || !workspace.profile || !companyId) return;
    const result = await generateTallyXml(workspace.token, { profile_id: workspace.profile.id, period: workspace.profile.return_period, company_id: Number(companyId), ledger_mapping: { sales_ledger: "E-Commerce Sales", igst_ledger: "Output IGST", cgst_ledger: "Output CGST", sgst_ledger: "Output SGST" } });
    setDownload(result.download);
  }
  return <AppShell title="eCom to Tally" subtitle="Convert normalized marketplace transactions into Tally XML with ledger mapping." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }}><div className="grid gap-6 xl:grid-cols-3"><StatCard label="Transactions ready" value={String(workspace.transactions.length)} detail="Rows available for XML" /><StatCard label="Taxable value" value={formatCurrency(money(workspace.summary?.total_taxable_value))} /><StatCard label="Companies" value={String(workspace.companies.length)} /></div><div className="mt-6 grid gap-6 xl:grid-cols-2"><Panel title="Tally company" subtitle="Add or select Tally company."><form onSubmit={addCompany} className="flex gap-3"><input value={companyName} onChange={(event) => setCompanyName(event.target.value)} className="flex-1 rounded-2xl border px-4 py-3 dark:border-white/10 dark:bg-slate-900" placeholder="Company name" /><button className="rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white">Add</button></form><select value={companyId} onChange={(event) => setCompanyId(event.target.value)} className="mt-4 w-full rounded-2xl border px-4 py-3 dark:border-white/10 dark:bg-slate-900"><option value="">Choose company</option>{workspace.companies.map((company) => <option key={company.id} value={company.id}>{company.company_name}</option>)}</select></Panel><Panel title="Generate XML" subtitle="Uses backend Tally XML generator."><button onClick={generate} className="inline-flex items-center gap-2 rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white"><FileArchive className="size-4" /> Generate Tally XML</button>{download && <a href={downloadUrl(download)} className="ml-3 inline-flex rounded-2xl bg-emerald-600 px-5 py-3 text-sm font-bold text-white">Download XML</a>}</Panel></div></AppShell>;
}

export function ProfilePage() {
  const workspace = useWorkspace();
  const [form, setForm] = useState({ gstin: "", legal_name: "", trade_name: "", filing_frequency: "Monthly", financial_year: "2026-27", return_period: "042026" });
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!workspace.token) return;
    await createProfile(workspace.token, form);
    await workspace.refresh();
  }
  return <AppShell title="GST Profiles" subtitle="Manage GSTIN workspaces, filing frequency and return period." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }}><div className="grid gap-6 xl:grid-cols-[1fr_0.9fr]"><Panel title="Profiles" subtitle="Switch workspace from sidebar anytime."><div className="space-y-3">{workspace.profiles.map((profile) => <div key={profile.id} className="rounded-2xl bg-slate-50 p-4 dark:bg-white/5"><b>{profile.gstin}</b><p className="text-sm text-slate-500">{profile.legal_name} / {profile.return_period}</p></div>)}</div></Panel><Panel title="Add GST profile" subtitle="State code is detected from GSTIN by backend."><form onSubmit={submit} className="space-y-3">{Object.keys(form).map((key) => <input key={key} value={form[key as keyof typeof form]} onChange={(event) => setForm({ ...form, [key]: event.target.value })} className="w-full rounded-2xl border px-4 py-3 dark:border-white/10 dark:bg-slate-900" placeholder={key.replaceAll("_", " ")} />)}<button className="rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white">Create profile</button></form></Panel></div></AppShell>;
}

export function SettingsPage() {
  const workspace = useWorkspace();
  return <AppShell title="Settings" subtitle="Workspace preferences, security controls, notifications and export defaults." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }}><Panel title="Workspace settings" subtitle="Frontend-ready settings. Persistence can be added to backend later."><div className="grid gap-4 md:grid-cols-2"><label className="rounded-2xl bg-slate-50 p-4 font-bold dark:bg-white/5"><Settings className="mb-3 size-5 text-[#1746A2]" />Default export format<select className="mt-3 w-full rounded-xl border px-3 py-2 dark:border-white/10 dark:bg-slate-900"><option>JSON + Excel</option><option>JSON only</option><option>Excel only</option></select></label><label className="rounded-2xl bg-slate-50 p-4 font-bold dark:bg-white/5">Notifications<div className="mt-3 space-y-2 text-sm font-medium text-slate-500"><label className="flex gap-2"><input type="checkbox" defaultChecked /> Import completed</label><label className="flex gap-2"><input type="checkbox" defaultChecked /> Validation warning</label><label className="flex gap-2"><input type="checkbox" /> Filing reminders</label></div></label></div></Panel></AppShell>;
}

export function BillingPage() {
  const workspace = useWorkspace();
  return <AppShell title="Billing" subtitle="Subscription and usage management placeholder for GST Bharat plans." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }}><Panel title="Plan management" subtitle="Placeholder only. No payment integration is implemented yet."><EmptyState title="Billing is not connected" body="Add pricing plans, invoices and payment gateway integration in the next product phase." action={<button className="inline-flex items-center gap-2 rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white"><CreditCard className="size-4" /> Coming soon</button>} /></Panel></AppShell>;
}
