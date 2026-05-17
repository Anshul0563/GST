"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Building2,
  ChevronDown,
  Database,
  Download,
  FileArchive,
  FileJson,
  FileSpreadsheet,
  Layers3,
  LockKeyhole,
  Menu,
  Package,
  ReceiptText,
  RotateCw,
  Search,
  Settings,
  Trash2,
  Upload,
  X
} from "lucide-react";
import {
  BatchStatus,
  DashboardSummary,
  Gstr1Payload,
  Profile,
  ReconcileReport,
  TallyCompany,
  Transaction,
  createProfile,
  createTallyCompany,
  deleteTransaction,
  downloadUrl,
  ensureDemoWorkspace,
  generateGstr1,
  generateTallyXml,
  getGstrPreview,
  getImportStatus,
  getReconcileReport,
  getSummary,
  getTransactions,
  listImportBatches,
  listProfiles,
  listTallyCompanies,
  updateProfile,
  updateTransaction,
  uploadMarketplaceFiles,
  uploadReconcileFiles
} from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

type Tool = "home" | "gos" | "e2t" | "recon";
type View = "dashboard" | "profile" | "upload" | "manage" | "report" | "company" | "customize" | "xml" | "reconUpload" | "reconReport";
type PlatformCard = { key: string; name: string; sub: string; logo: string; color: string; badge?: string; files: string[]; guide: string; etin?: string };

const platformCards: PlatformCard[] = [
  { key: "meesho", name: "Meesho", sub: "B2C", logo: "m", color: "bg-[#f72585] text-white", files: ["tcs_sales.xlsx", "tcs_sales_return.xlsx", "Tax_invoice_details.xlsx"], guide: "Meesho Panel -> Payments -> Download GST Reports", etin: "07AARCM9332R1CQ" },
  { key: "amazon", name: "Amazon", sub: "B2C", logo: "a", color: "bg-white text-black", files: ["MTR_B2C CSV"], guide: "Reports -> Manage Taxes -> GST Monthly Reports -> Download Report", etin: "07AAICA3918J1CV" },
  { key: "amazon-b2b", name: "Amazon B2B", sub: "B2B", logo: "a", color: "bg-white text-black", files: ["MTR_B2B CSV"], guide: "Amazon tax reports B2B download" },
  { key: "flipkart", name: "Flipkart", sub: "B2C & B2B Sales Report", logo: "F", color: "bg-[#ffd52e] text-[#1769d2]", files: ["Sales Report Excel"], guide: "Flipkart Portal -> Reports Center -> Tax Reports -> Sales report", etin: "07AACCF0683K1CU" },
  { key: "myntra", name: "Myntra", sub: "B2C", logo: "M", color: "bg-gradient-to-tr from-pink-500 via-orange-400 to-purple-600 text-white", files: ["Sales report"], guide: "Upload Myntra GST report" },
  { key: "snapdeal", name: "Snapdeal", sub: "B2C", logo: "S", color: "bg-[#e51b35] text-white", files: ["Sales report"], guide: "Upload Snapdeal GST report" },
  { key: "glowroad", name: "Glowroad", sub: "B2C", logo: "g", color: "bg-[#005b66] text-white", files: ["Sales report"], guide: "Upload Glowroad GST report" },
  { key: "limeroad", name: "Limeroad", sub: "B2C", logo: "LR", color: "bg-[#e00046] text-white", files: ["Sales report"], guide: "Upload Limeroad GST report" },
  { key: "jiomart", name: "JioMart", sub: "B2C", logo: "Jio", color: "bg-[#d51224] text-white", files: ["Sales report"], guide: "Upload JioMart GST report" },
  { key: "custom", name: "Custom Excel", sub: "B2C/B2B/Exempt", logo: "X", color: "bg-green-600 text-white", files: ["Custom Excel"], guide: "Upload a mapped custom Excel file" }
];

const ledgerDefaults = {
  sales_ledger: "E-Commerce Sales",
  igst_ledger: "Output IGST",
  cgst_ledger: "Output CGST",
  sgst_ledger: "Output SGST",
  tcs_ledger: "TCS Receivable",
  tds_ledger: "TDS Receivable",
  discount_ledger: "Marketplace Discount",
  roundoff_ledger: "Round Off",
  party_ledger: "Marketplace Customer",
  stock_item: "E-Commerce Item",
  uqc: "PCS"
};

function amount(value: number | string | undefined | null) {
  return Number(value || 0);
}

function TopNav({ setTool, setView }: { setTool: (tool: Tool) => void; setView: (view: View) => void }) {
  function go(tool: Tool, view: View) {
    setTool(tool);
    setView(view);
  }
  return (
    <header className="sticky top-0 z-40 h-[58px] border-b border-slate-100 bg-white">
      <div className="mx-auto flex h-full max-w-[1280px] items-center justify-between px-6">
        <button onClick={() => go("home", "dashboard")} className="text-left text-[26px] font-black leading-none text-[#10244d]">
          GST<span className="block -mt-1 text-[15px] font-extrabold text-[#f59e0b]">BHARAT</span>
        </button>
        <nav className="hidden items-center gap-8 text-sm md:flex">
          <button onClick={() => go("home", "dashboard")} className="font-semibold text-[#ef4d82]">Dashboard</button>
          <button onClick={() => go("gos", "upload")} className="flex items-center gap-1 text-slate-600">Our Tools <ChevronDown className="size-3" /></button>
          <button onClick={() => go("gos", "report")} className="text-slate-600">Screenshot</button>
          <button onClick={() => go("recon", "reconUpload")} className="text-slate-600">Support</button>
          <span className="grid size-9 place-items-center rounded-full bg-[#ef4d82] font-bold text-white">P</span>
        </nav>
        <Menu className="size-5 text-slate-500 md:hidden" />
      </div>
    </header>
  );
}

function labelForView(view: View) {
  return {
    dashboard: "Dashboard",
    profile: "GST Profile",
    upload: "Import Data",
    manage: "Manage Data",
    report: "GSTR1 Report",
    company: "Tally Company",
    customize: "Customize Master",
    xml: "Generate XML",
    reconUpload: "2B/2A Reconcile",
    reconReport: "Report"
  }[view];
}

function Hero({ tool, view, profile }: { tool: Tool; view: View; profile: Profile | null }) {
  const title = tool === "e2t" ? "eCom to Tally" : tool === "recon" ? "2B/2A Reconcile" : tool === "home" ? "Dashboard" : "GST Online Seller Tool";
  return (
    <section className="gst-pattern h-[190px] text-white">
      <div className="mx-auto flex max-w-[1280px] justify-between px-6 pt-11">
        <div>
          <h1 className="text-2xl font-bold">{title}</h1>
          <p className="mt-3 text-sm font-medium"><span>Home</span><span className="mx-2 text-white/70">/</span><span className="text-[#3b82f6]">Dashboard / {title} / {labelForView(view)}</span></p>
        </div>
        {profile && tool !== "home" && <div className="mt-1 hidden h-fit rounded bg-white/10 px-4 py-3 text-[11px] leading-5 lg:block"><p>GSTIN: {profile.gstin}</p><p>Period: {profile.return_period}</p></div>}
      </div>
    </section>
  );
}

function Sidebar({ tool, view, setView }: { tool: Tool; view: View; setView: (view: View) => void }) {
  const gos = [["profile", "GST Profile", Building2], ["upload", "Import Data", Upload], ["manage", "Manage Data", Database], ["report", "GSTR1 Report", FileJson]] as const;
  const e2t = [["company", "Tally Company", Building2], ["upload", "Import Data", Upload], ["manage", "Manage Data", Database], ["customize", "Customize Master", Settings], ["xml", "Generate XML", FileArchive]] as const;
  const recon = [["reconUpload", "2B/2A Reconcile", RotateCw], ["reconReport", "Reconcile Report", ReceiptText]] as const;
  const items = tool === "e2t" ? e2t : tool === "recon" ? recon : gos;
  return (
    <aside className="gst-shadow min-h-[250px] w-[230px] shrink-0 rounded-md bg-white px-8 py-6">
      <button onClick={() => setView("dashboard")} className="mb-5 w-full border-b border-slate-200 pb-5 text-center text-lg font-bold text-[#3478ff]">Dashboard</button>
      <p className="mb-5 text-[11px] font-black uppercase text-slate-900">{tool === "e2t" ? "eCom to Tally" : tool === "recon" ? "Reconcile" : "GST Online Seller"}</p>
      <div className="space-y-1">
        {items.map(([key, text, Icon]) => (
          <button key={key} onClick={() => setView(key)} className={`relative flex w-full items-center gap-4 rounded py-2.5 pl-1 text-left text-sm ${view === key ? "font-bold text-[#3478ff]" : "text-[#1f335c]"}`}>
            {view === key && <span className="absolute -left-8 top-1/2 h-9 w-1 -translate-y-1/2 bg-[#3478ff]" />}
            <Icon className="size-4 text-slate-500" />{text}
          </button>
        ))}
      </div>
    </aside>
  );
}

function PageShell({ tool, view, setView, profile, children }: { tool: Tool; view: View; setView: (view: View) => void; profile: Profile | null; children: React.ReactNode }) {
  return (
    <>
      <Hero tool={tool} view={view} profile={profile} />
      <main className="min-h-[calc(100vh-248px)] bg-[#f5f8fc] pb-20">
        <div className="mx-auto -mt-8 flex max-w-[1120px] gap-6 px-6">
          {tool !== "home" && <Sidebar tool={tool} view={view} setView={setView} />}
          <section className={tool === "home" ? "mx-auto w-full max-w-[900px]" : "min-w-0 flex-1"}>{children}</section>
        </div>
      </main>
    </>
  );
}

function WhitePanel({ title, subtitle, children, className = "" }: { title: string; subtitle?: string; children?: React.ReactNode; className?: string }) {
  return <div className={`gst-shadow rounded-md bg-white ${className}`}><div className="px-8 py-7 text-center"><h2 className="text-xl font-bold text-slate-950">{title}</h2>{subtitle && <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-500">{subtitle}</p>}</div>{children}</div>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded border border-slate-200 bg-white p-4"><p className="text-xs font-bold uppercase text-slate-500">{label}</p><p className="mt-2 text-xl font-black text-[#10244d]">{value}</p></div>;
}

function HomeTools({ setTool, setView, summary }: { setTool: (tool: Tool) => void; setView: (view: View) => void; summary: DashboardSummary | null }) {
  const cards = [
    { tool: "gos" as Tool, title: "GST Online Seller", text: "Convert e-Commerce excel into GSTR1 excel & json.", red: true, view: "profile" as View },
    { tool: "recon" as Tool, title: "2B/2A Reconcile v2.0", text: "Reconcile 2B/2A purchase data and download query report.", red: false, view: "reconUpload" as View },
    { tool: "e2t" as Tool, title: "eCom to Tally", text: "Convert e-Commerce excel into Tally import XML.", red: true, view: "company" as View }
  ];
  return (
    <div className="space-y-6">
      <WhitePanel title="Live Dashboard" subtitle="Connected to GST Bharat API and current selected GST profile.">
        <div className="grid gap-4 px-7 pb-7 md:grid-cols-4">
          <Metric label="Taxable" value={formatCurrency(amount(summary?.total_taxable_value))} />
          <Metric label="Total GST" value={formatCurrency(amount(summary?.total_gst))} />
          <Metric label="Files" value={String(summary?.uploaded_files ?? 0)} />
          <Metric label="Errors" value={String(summary?.pending_errors ?? 0)} />
        </div>
      </WhitePanel>
      <WhitePanel title="Our Tools" subtitle="Here is all tool click access now to use our tool.">
        <div className="grid gap-5 px-7 pb-7 md:grid-cols-3">
          {cards.map((card) => (
            <div key={card.title} className={`rounded-sm border ${card.red ? "border-red-500" : "border-slate-200"} bg-[#10244d] p-3 text-white`}>
              <div className="mb-3 flex h-28 items-center justify-center rounded bg-[#3b78ff] text-2xl font-bold">{card.tool === "recon" ? <FileSpreadsheet className="size-16" /> : "GST -> JSON"}</div>
              <p className="text-xs uppercase text-slate-300">{card.tool === "e2t" ? "Account" : "GST"}</p>
              <h3 className="mt-1 text-base font-bold">{card.title}</h3>
              <p className="mt-2 min-h-12 text-xs leading-5 text-slate-300">{card.text}</p>
              <div className="mt-3 flex items-center justify-between border-t border-white/10 pt-3"><span className="text-sm text-[#05d7c5]">Active</span><button onClick={() => { setTool(card.tool); setView(card.view); }} className="rounded bg-[#3b78ff] px-3 py-2 text-xs font-semibold">Access Now</button></div>
            </div>
          ))}
        </div>
      </WhitePanel>
    </div>
  );
}

function PlatformLogo({ card }: { card: PlatformCard }) {
  return <div className={`mx-auto grid size-14 place-items-center rounded-lg text-2xl font-black ${card.color}`}>{card.logo}</div>;
}

function UploadGrid({ batches, openModal, e2t = false }: { batches: BatchStatus[]; openModal: (card: PlatformCard) => void; e2t?: boolean }) {
  const cards = e2t ? platformCards.slice(1, 9) : platformCards;
  const latestByPlatform = new Map(batches.map((batch) => [batch.platform, batch]));
  return (
    <WhitePanel title="Import Platform Data" subtitle={e2t ? "Upload platform data to convert into Tally XML." : "Upload platform data then check view statement & generate GSTR1."}>
      <div className="mx-auto max-w-[680px] px-7 pb-8">
        {!e2t && <><div className="mx-auto mb-4 flex max-w-[470px] rounded-md border border-slate-200 bg-white p-2"><Search className="ml-2 mt-2 size-4 text-slate-400" /><input className="flex-1 px-4 text-sm outline-none" placeholder="Search for platform" /><button className="grid size-10 place-items-center rounded bg-[#3478ff] text-white">{"->"}</button></div><p className="mb-7 text-center text-sm text-[#ff4d7d]">Caution: Avoid importing the edited file to prevent potential errors.</p></>}
        <div className="mb-5 flex items-center gap-3 text-xs text-slate-500"><span className="h-px flex-1 bg-slate-200" />{e2t ? "Order Data" : "Famous Platforms"}<span className="h-px flex-1 bg-slate-200" /></div>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
          {cards.map((card) => {
            const batch = latestByPlatform.get(card.key);
            return (
              <button key={card.key} onClick={() => openModal(card)} className="platform-card-shadow relative min-h-[142px] rounded-md border border-slate-200 bg-white p-4 text-center transition hover:-translate-y-0.5">
                {card.badge && <span className="absolute right-0 top-0 rounded-bl bg-[#12264f] px-2 py-1 text-[10px] font-bold text-white">{card.badge}</span>}
                <PlatformLogo card={card} /><h3 className="mt-2 text-sm font-black text-black">{card.name}</h3><p className="text-xs text-slate-500">{card.sub}</p>
                <span className={`mt-4 inline-flex rounded-full px-4 py-2 text-[11px] font-bold ${batch ? "bg-[#06c7a8] text-white" : "bg-slate-100 text-black"}`}>{batch ? `${batch.status} (${batch.parsed_rows})` : "IMPORT DATA"}</span>
              </button>
            );
          })}
        </div>
      </div>
    </WhitePanel>
  );
}

function UploadModal({ card, token, profile, onClose, onRefresh }: { card: PlatformCard | null; token: string; profile: Profile | null; onClose: () => void; onRefresh: () => Promise<void> }) {
  const [files, setFiles] = useState<FileList | null>(null);
  const [batch, setBatch] = useState<BatchStatus | null>(null);
  const [message, setMessage] = useState("");
  if (!card) return null;
  async function startUpload() {
    if (!token || !profile || !files?.length) {
      setMessage("Select files after workspace is ready.");
      return;
    }
    setMessage("Uploading and parsing...");
    const nextBatch = await uploadMarketplaceFiles(token, profile.id, card.key, files);
    setBatch(nextBatch);
    for (let attempt = 0; attempt < 8; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 900));
      const status = await getImportStatus(token, nextBatch.id);
      setBatch(status);
      if (!["queued", "processing"].includes(status.status)) break;
    }
    setMessage("Import status updated from backend.");
    await onRefresh();
  }
  return (
    <div className="fixed inset-0 z-50 grid place-items-start bg-[#b7c1d1]/80 pt-12">
      <div className="w-[455px] rounded-md bg-white shadow-2xl">
        <div className="flex items-start justify-between border-b border-slate-200 px-6 py-4"><div className="flex items-center gap-3"><PlatformLogo card={card} /><div><div className="flex items-center gap-2"><h3 className="font-bold">{card.name}</h3><span className="rounded bg-[#3478ff] px-2 py-0.5 text-[10px] font-bold text-white">{card.sub.split(" ")[0]}</span></div><p className="text-xs text-slate-500">{card.name.toLowerCase()}.com</p></div></div><button onClick={onClose}><X className="size-5 text-slate-500" /></button></div>
        <div className="space-y-4 px-6 py-6">
          <div className="rounded-md border border-slate-200 py-2 text-center text-sm">{profile?.return_period || "Period"} Data</div>
          <div><p className="mb-2 text-xs font-bold">Download Path</p><p className="text-sm leading-5 text-slate-500">{card.guide}</p></div>
          <div className="flex rounded border border-slate-200"><span className="w-40 border-r border-slate-200 px-3 py-2 text-sm text-slate-500">GSTIN / ETIN</span><span className="flex-1 px-3 py-2 text-sm">{card.etin || profile?.gstin || "Auto Detect"}</span></div>
          <div><p className="mb-2 text-xs font-bold">Upload Files: <span className="text-[#ff4d7d]">({profile?.return_period || "selected period"})</span></p><input multiple type="file" accept=".xlsx,.xls,.xlsm,.csv" onChange={(event) => setFiles(event.target.files)} className="w-full rounded border border-slate-200 px-3 py-2 text-sm" /><p className="mt-2 text-xs text-slate-500">Required: {card.files.join(", ")}</p></div>
          <button onClick={startUpload} className="rounded bg-[#3478ff] px-5 py-2 text-sm font-bold text-white">Upload</button>
          {(message || batch) && <div className="rounded-md bg-[#06c7a8] px-4 py-3 text-sm text-white">{message || batch?.status} {batch ? `Rows: ${batch.parsed_rows}, Errors: ${batch.error_rows}` : ""}</div>}
        </div>
        <div className="flex justify-end border-t border-slate-200 bg-slate-50 px-4 py-4"><button onClick={onClose} className="rounded bg-slate-600 px-4 py-2 text-sm text-white">Close</button></div>
      </div>
    </div>
  );
}

function ProfileView({ token, profiles, profile, setProfile, onRefresh }: { token: string; profiles: Profile[]; profile: Profile | null; setProfile: (profile: Profile) => void; onRefresh: () => Promise<void> }) {
  const [form, setForm] = useState({ gstin: profile?.gstin || "", legal_name: profile?.legal_name || "", trade_name: profile?.trade_name || "", filing_frequency: profile?.filing_frequency || "Monthly", financial_year: profile?.financial_year || "2026-27", return_period: profile?.return_period || "042026" });
  useEffect(() => { if (profile) setForm({ gstin: profile.gstin, legal_name: profile.legal_name, trade_name: profile.trade_name || "", filing_frequency: profile.filing_frequency, financial_year: profile.financial_year, return_period: profile.return_period }); }, [profile]);
  async function save(event: FormEvent) {
    event.preventDefault();
    const saved = profile ? await updateProfile(token, profile.id, form) : await createProfile(token, form);
    setProfile(saved);
    await onRefresh();
  }
  return (
    <div className="space-y-6">
      <WhitePanel title="GST Information" subtitle="Provide GST Number, month and year of filing.">
        <form onSubmit={save} className="mx-auto grid max-w-[680px] gap-3 px-8 pb-8 md:grid-cols-3">
          {(["gstin", "legal_name", "trade_name", "financial_year", "return_period"] as const).map((key) => <input key={key} value={form[key] || ""} onChange={(event) => setForm({ ...form, [key]: event.target.value })} className="rounded border border-slate-200 px-3 py-2 text-sm" placeholder={key.replace("_", " ").toUpperCase()} />)}
          <select value={form.filing_frequency} onChange={(event) => setForm({ ...form, filing_frequency: event.target.value })} className="rounded border border-slate-200 px-3 py-2 text-sm"><option>Monthly</option><option>Quarterly</option></select>
          <button className="rounded bg-[#3478ff] px-5 py-2 text-sm font-bold text-white md:col-span-3">Save profile</button>
          <p className="text-xs text-slate-500 md:col-span-3">State code auto-detected: {form.gstin.slice(0, 2) || "--"}</p>
        </form>
      </WhitePanel>
      <WhitePanel title="GSTIN List" subtitle="Live profiles available in your account.">
        <div className="grid gap-4 px-8 pb-8 md:grid-cols-2">
          {profiles.map((item) => <button key={item.id} onClick={() => setProfile(item)} className={`rounded border p-4 text-center text-xs ${item.id === profile?.id ? "border-[#3478ff] bg-blue-50" : "border-slate-200 bg-white"}`}><p className="font-bold">{item.gstin}</p><p className="mt-1 text-slate-500">{item.legal_name} / {item.return_period}</p><span className="mt-2 inline-flex rounded bg-[#3478ff] px-4 py-1 text-white">Select</span></button>)}
        </div>
      </WhitePanel>
    </div>
  );
}

function ManageView({ token, rows, summary, onRefresh }: { token: string; rows: Transaction[]; summary: DashboardSummary | null; onRefresh: () => Promise<void> }) {
  const [query, setQuery] = useState("");
  const [platform, setPlatform] = useState("all");
  const [editing, setEditing] = useState<Transaction | null>(null);
  const filtered = rows.filter((row) => (platform === "all" || row.platform === platform) && JSON.stringify(row).toLowerCase().includes(query.toLowerCase()));
  const platforms = Array.from(new Set(rows.map((row) => row.platform))).sort();
  async function remove(id: number) {
    await deleteTransaction(token, id);
    await onRefresh();
  }
  async function saveEdit(event: FormEvent) {
    event.preventDefault();
    if (!editing) return;
    await updateTransaction(token, editing.id, editing);
    setEditing(null);
    await onRefresh();
  }
  return (
    <WhitePanel title="Manage of Imported Data" subtitle="Live merged platform transactions. Search, edit, delete and validate before generating GSTR1.">
      <div className="px-8 pb-8">
        <div className="mb-5 grid gap-3 md:grid-cols-4"><Metric label="Rows" value={String(rows.length)} /><Metric label="Taxable" value={formatCurrency(amount(summary?.total_taxable_value))} /><Metric label="GST" value={formatCurrency(amount(summary?.total_gst))} /><Metric label="Errors" value={String(summary?.pending_errors ?? 0)} /></div>
        <div className="mb-4 flex flex-wrap gap-2"><input value={query} onChange={(event) => setQuery(event.target.value)} className="rounded border px-3 py-2 text-sm" placeholder="Search invoices, orders, states" /><select value={platform} onChange={(event) => setPlatform(event.target.value)} className="rounded border px-3 py-2 text-sm"><option value="all">All platforms</option>{platforms.map((item) => <option key={item}>{item}</option>)}</select><button onClick={onRefresh} className="rounded bg-[#3478ff] px-4 py-2 text-sm font-bold text-white">Recalculate GST</button></div>
        <div className="table-scroll max-h-[520px] overflow-auto rounded border border-slate-200">
          <table className="min-w-[1180px] text-left text-xs"><thead className="sticky top-0 bg-slate-50 text-slate-500"><tr>{["Platform", "Invoice", "Order", "Date", "POS", "HSN", "Taxable", "Rate", "IGST", "CGST", "SGST", "TCS", "TDS", "Doc", "Source", ""].map((head) => <th key={head} className="p-3">{head}</th>)}</tr></thead><tbody className="divide-y">
            {filtered.map((row) => <tr key={row.id} className={row.validation_status === "error" ? "bg-red-50" : "bg-white"}><td className="p-3 font-bold">{row.platform}</td><td>{row.invoice_no}</td><td>{row.order_id}</td><td>{row.invoice_date}</td><td>{row.buyer_state_code}</td><td>{row.hsn}</td><td>{formatCurrency(amount(row.taxable_value))}</td><td>{row.gst_rate}%</td><td>{row.igst}</td><td>{row.cgst}</td><td>{row.sgst}</td><td>{row.tcs}</td><td>{row.tds}</td><td>{row.doc_type}</td><td>{row.source_file}</td><td className="p-2"><button onClick={() => setEditing(row)} className="mr-2 text-[#3478ff]">Edit</button><button onClick={() => remove(row.id)} className="text-[#ff4d7d]"><Trash2 className="size-4" /></button></td></tr>)}
          </tbody></table>
        </div>
      </div>
      {editing && <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/40"><form onSubmit={saveEdit} className="w-[420px] rounded bg-white p-6 shadow-2xl"><h3 className="mb-4 font-bold">Edit row {editing.invoice_no}</h3>{(["buyer_state_code", "hsn", "taxable_value", "gst_rate", "igst", "cgst", "sgst", "doc_type"] as const).map((key) => <input key={key} value={String(editing[key] ?? "")} onChange={(event) => setEditing({ ...editing, [key]: event.target.value })} className="mb-2 w-full rounded border px-3 py-2 text-sm" placeholder={key} />)}<div className="mt-3 flex justify-end gap-2"><button type="button" onClick={() => setEditing(null)} className="rounded border px-4 py-2">Cancel</button><button className="rounded bg-[#3478ff] px-4 py-2 text-white">Save</button></div></form></div>}
    </WhitePanel>
  );
}

function ReportView({ profile, preview, summary, generated, onGenerate }: { profile: Profile | null; preview: Gstr1Payload | null; summary: DashboardSummary | null; generated: { download_json: string; download_excel: string } | null; onGenerate: () => Promise<void> }) {
  const b2csTaxable = preview?.b2cs.reduce((sum, row) => sum + row.txval, 0) || amount(summary?.total_taxable_value);
  const docGroups = preview?.doc_issue?.doc_det?.length || 0;
  return (
    <WhitePanel title="GSTR1 Report" subtitle="Live GSTR1 preview generated from normalized transactions.">
      <div className="mx-auto max-w-[760px] px-8 pb-8">
        <table className="w-full border border-slate-200 text-center text-xs"><thead className="bg-slate-50"><tr><th className="p-3">B2CS records</th><th>Taxable Value</th><th>Integrated tax</th><th>Central tax</th><th>State/UT tax</th><th>Invoice value</th><th>Doc groups</th></tr></thead><tbody><tr className="border-t"><td className="p-3">{preview?.b2cs.length ?? 0}</td><td>{formatCurrency(b2csTaxable)}</td><td>{formatCurrency(amount(summary?.igst))}</td><td>{formatCurrency(amount(summary?.cgst))}</td><td>{formatCurrency(amount(summary?.sgst))}</td><td>{formatCurrency(amount(summary?.total_sales))}</td><td>{docGroups}</td></tr></tbody></table>
        <div className="mt-5 grid gap-3 md:grid-cols-2">
          <div className="rounded border p-3 text-sm"><p className="font-bold">SUPECO</p><p className="text-slate-500">{preview?.supeco?.supeco_det?.length ?? 0} ecommerce operator groups</p></div>
          <div className="rounded border p-3 text-sm"><p className="font-bold">GSTIN / Period</p><p className="text-slate-500">{profile?.gstin} / {profile?.return_period}</p></div>
        </div>
        <div className="mt-5 max-h-64 overflow-auto rounded border"><table className="w-full text-xs"><thead className="bg-slate-50"><tr><th className="p-2">Supply</th><th>Rate</th><th>POS</th><th>Taxable</th><th>IGST</th><th>CGST</th><th>SGST</th></tr></thead><tbody>{preview?.b2cs.map((row) => <tr key={`${row.sply_ty}-${row.rt}-${row.pos}`} className="border-t"><td className="p-2">{row.sply_ty}</td><td>{row.rt}</td><td>{row.pos}</td><td>{row.txval}</td><td>{row.iamt}</td><td>{row.camt}</td><td>{row.samt}</td></tr>)}</tbody></table></div>
        <div className="mt-4 flex justify-center gap-4"><button onClick={onGenerate} className="flex items-center gap-2 rounded bg-[#3478ff] px-5 py-3 text-sm font-bold text-white"><FileJson className="size-5" />Generate Final Files</button>{generated && <><a className="flex items-center gap-2 rounded bg-[#3478ff] px-5 py-3 text-sm font-bold text-white" href={downloadUrl(generated.download_excel)}><FileSpreadsheet className="size-5" />Excel</a><a className="flex items-center gap-2 rounded bg-[#3478ff] px-5 py-3 text-sm font-bold text-white" href={downloadUrl(generated.download_json)}><Download className="size-5" />JSON</a></>}</div>
      </div>
    </WhitePanel>
  );
}

function CompanyView({ token, profile, companies, onRefresh }: { token: string; profile: Profile | null; companies: TallyCompany[]; onRefresh: () => Promise<void> }) {
  const [companyName, setCompanyName] = useState("");
  async function add(event: FormEvent) {
    event.preventDefault();
    if (!profile || !companyName.trim()) return;
    await createTallyCompany(token, { profile_id: profile.id, company_name: companyName.trim() });
    setCompanyName("");
    await onRefresh();
  }
  return <WhitePanel title="Tally Company" subtitle="Select or add company from live backend data."><form onSubmit={add} className="mx-auto max-w-[520px] px-8 pb-8"><div className="flex overflow-hidden rounded border"><input value={companyName} onChange={(event) => setCompanyName(event.target.value)} className="flex-1 px-3 py-2 text-sm" placeholder="Tally Company Name" /><button className="bg-[#3478ff] px-5 text-white">Add</button></div><div className="mt-5 space-y-2">{companies.map((company) => <div key={company.id} className="rounded border p-3 text-sm"><b>{company.company_name}</b><span className="ml-2 text-slate-500">#{company.id}</span></div>)}</div></form></WhitePanel>;
}

function CustomizeView({ mapping, setMapping, setView }: { mapping: Record<string, string>; setMapping: (mapping: Record<string, string>) => void; setView: (view: View) => void }) {
  return <WhitePanel title="Customize Master" subtitle="Change and update ledger, voucher and party names before XML generation."><div className="mx-auto max-w-[620px] px-8 pb-8">{Object.keys(mapping).map((key) => <label key={key} className="mb-2 grid grid-cols-[160px_1fr] items-center gap-3 text-sm"><span className="font-semibold capitalize">{key.replaceAll("_", " ")}</span><input value={mapping[key]} onChange={(event) => setMapping({ ...mapping, [key]: event.target.value })} className="rounded border px-3 py-2" /></label>)}<div className="mt-5 text-center"><button onClick={() => setView("xml")} className="rounded bg-[#3478ff] px-5 py-2 text-xs font-bold text-white">Generate Tally XML</button></div></div></WhitePanel>;
}

function XmlView({ token, profile, companies, mapping }: { token: string; profile: Profile | null; companies: TallyCompany[]; mapping: Record<string, string> }) {
  const [companyId, setCompanyId] = useState("");
  const [download, setDownload] = useState("");
  async function generate() {
    if (!profile || !companyId) return;
    const result = await generateTallyXml(token, { profile_id: profile.id, period: profile.return_period, company_id: Number(companyId), ledger_mapping: mapping });
    setDownload(result.download);
  }
  return <WhitePanel title="Download Tally XML" subtitle="Select your Tally company and generate Tally XML from live normalized rows."><div className="mx-auto mb-10 w-[280px] rounded bg-white p-6 shadow-lg"><p className="mb-3 text-center text-sm font-bold">Tally XML</p><select value={companyId} onChange={(event) => setCompanyId(event.target.value)} className="mt-1 w-full rounded border px-3 py-2 text-xs"><option value="">Choose company...</option>{companies.map((company) => <option key={company.id} value={company.id}>{company.company_name}</option>)}</select><label className="mt-3 flex items-center gap-2 text-xs"><input type="checkbox" defaultChecked /> Auto Create Ledger</label><button onClick={generate} className="mx-auto mt-4 flex items-center gap-2 rounded bg-[#3478ff] px-4 py-3 text-xs font-bold text-white"><FileArchive className="size-5" />Generate XML</button>{download && <a className="mt-3 block text-center text-sm text-[#3478ff]" href={downloadUrl(download)}>Download XML</a>}</div></WhitePanel>;
}

function ReconcileView({ token, profile, report, currentReport, setReport }: { token: string; profile: Profile | null; report?: boolean; currentReport: ReconcileReport | null; setReport: (report: ReconcileReport | null) => void }) {
  const [portal, setPortal] = useState<File | null>(null);
  const [books, setBooks] = useState<File | null>(null);
  async function uploadFiles() {
    if (!profile || !portal || !books) return;
    const uploaded = await uploadReconcileFiles(token, profile.id, portal, books);
    const full = await getReconcileReport(token, uploaded.id);
    setReport({ ...uploaded, ...full });
  }
  const categories = currentReport?.categories || ["Matched", "Amount mismatch", "Invoice mismatch", "Missing in 2B", "Missing in books", "Pending"];
  return <div className="space-y-5"><WhitePanel title="2B/2A Reconcile" subtitle="Upload portal and purchase register files, then generate query report."><div className="px-8 pb-8 text-center text-sm text-slate-500"><p className="mx-auto max-w-xl">The backend currently stores the reconciliation batch and exposes report status. Matching engine can be expanded here without changing the UI flow.</p><button className="mt-4 inline-flex items-center gap-2 rounded bg-[#3478ff] px-5 py-3 text-sm font-bold text-white"><FileSpreadsheet className="size-6" />Sample File Download</button></div></WhitePanel><WhitePanel title="Upload File"><div className="px-8 pb-8"><div className="grid gap-5 md:grid-cols-2"><input type="file" onChange={(event) => setPortal(event.target.files?.[0] || null)} className="rounded border px-3 py-2 text-sm" /><input type="file" onChange={(event) => setBooks(event.target.files?.[0] || null)} className="rounded border px-3 py-2 text-sm" /></div><button onClick={uploadFiles} className="mt-4 rounded bg-[#3478ff] px-5 py-2 text-sm font-bold text-white">Submit</button>{(report || currentReport) && <><div className="mt-5 grid grid-cols-3 text-center text-xs font-bold text-white md:grid-cols-6">{categories.map((x, i) => <div key={x} className={`p-3 ${i < 2 ? "bg-cyan-500" : i < 4 ? "bg-orange-400" : "bg-pink-500"}`}>{x}<br />{currentReport?.summary?.[x.toLowerCase().replaceAll(" ", "_")] ?? 0}</div>)}</div><div className="mt-4 flex gap-2 rounded bg-amber-50 p-3 text-sm text-amber-800"><AlertTriangle className="size-4" />Report batch: {currentReport?.id || "not uploaded yet"} / {currentReport?.status || "pending"}</div></>}</div></WhitePanel></div>;
}

export default function DashboardPage() {
  const [tool, setTool] = useState<Tool>("home");
  const [view, setView] = useState<View>("dashboard");
  const [modal, setModal] = useState<PlatformCard | null>(null);
  const [token, setToken] = useState("");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [preview, setPreview] = useState<Gstr1Payload | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [batches, setBatches] = useState<BatchStatus[]>([]);
  const [companies, setCompanies] = useState<TallyCompany[]>([]);
  const [generated, setGenerated] = useState<{ download_json: string; download_excel: string } | null>(null);
  const [reconcileReport, setReconcileReport] = useState<ReconcileReport | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>(ledgerDefaults);
  const [error, setError] = useState("");

  async function refresh(activeToken = token, activeProfile = profile) {
    if (!activeToken || !activeProfile) return;
    const [nextProfiles, nextSummary, nextPreview, nextTransactions, nextBatches, nextCompanies] = await Promise.all([
      listProfiles(activeToken),
      getSummary(activeToken, activeProfile),
      getGstrPreview(activeToken, activeProfile),
      getTransactions(activeToken, activeProfile),
      listImportBatches(activeToken, activeProfile.id),
      listTallyCompanies(activeToken, activeProfile.id)
    ]);
    setProfiles(nextProfiles);
    setSummary(nextSummary);
    setPreview(nextPreview);
    setTransactions(nextTransactions);
    setBatches(nextBatches);
    setCompanies(nextCompanies);
  }

  useEffect(() => {
    ensureDemoWorkspace().then(async ({ token, profile }) => {
      setToken(token);
      setProfile(profile);
      await refresh(token, profile);
    }).catch((exc) => setError(exc instanceof Error ? exc.message : "Could not initialize workspace"));
  }, []);

  async function handleGenerate() {
    if (!token || !profile) return;
    const result = await generateGstr1(token, profile);
    setPreview(result.json);
    setGenerated({ download_json: result.download_json, download_excel: result.download_excel });
    await refresh();
  }

  const content = useMemo(() => {
    if (tool === "home") return <HomeTools setTool={setTool} setView={setView} summary={summary} />;
    if (tool === "recon") return <ReconcileView token={token} profile={profile} report={view === "reconReport"} currentReport={reconcileReport} setReport={setReconcileReport} />;
    if (view === "profile") return <ProfileView token={token} profiles={profiles} profile={profile} setProfile={setProfile} onRefresh={refresh} />;
    if (view === "upload") return <UploadGrid batches={batches} openModal={setModal} e2t={tool === "e2t"} />;
    if (view === "manage") return <ManageView token={token} rows={transactions} summary={summary} onRefresh={refresh} />;
    if (view === "report") return <ReportView profile={profile} preview={preview} summary={summary} generated={generated} onGenerate={handleGenerate} />;
    if (view === "company") return <CompanyView token={token} profile={profile} companies={companies} onRefresh={refresh} />;
    if (view === "customize") return <CustomizeView mapping={mapping} setMapping={setMapping} setView={setView} />;
    if (view === "xml") return <XmlView token={token} profile={profile} companies={companies} mapping={mapping} />;
    return <HomeTools setTool={setTool} setView={setView} summary={summary} />;
  }, [tool, view, token, profile, profiles, summary, preview, transactions, batches, companies, generated, reconcileReport, mapping]);

  return (
    <>
      <TopNav setTool={setTool} setView={setView} />
      <PageShell tool={tool} view={view} setView={setView} profile={profile}>
        {error && <div className="mb-4 rounded bg-red-50 p-3 text-sm text-red-700">{error}</div>}
        {content}
      </PageShell>
      <footer className="bg-[#1b335f] py-7 text-white"><div className="mx-auto flex max-w-[1080px] items-center justify-between px-6 text-xs"><div className="text-xl font-black">GST<span className="text-[#f59e0b]">BHARAT</span></div><div className="hidden gap-12 md:flex"><span>Company</span><span>Our Tools</span><span>Documentation</span><span>Resources</span></div></div></footer>
      <button className="fixed bottom-6 right-6 grid size-11 place-items-center rounded-full bg-sky-400 text-white shadow-lg"><LockKeyhole className="size-5" /></button>
      <UploadModal card={modal} token={token} profile={profile} onClose={() => setModal(null)} onRefresh={refresh} />
    </>
  );
}
