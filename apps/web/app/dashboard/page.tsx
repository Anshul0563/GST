"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Building2,
  ChevronDown,
  Database,
  FileArchive,
  FileJson,
  FileSpreadsheet,
  Layers3,
  LockKeyhole,
  Menu,
  Package,
  ReceiptText,
  RotateCw,
  Settings,
  Upload,
  X
} from "lucide-react";
import { DashboardSummary, Gstr1Payload, Profile, Transaction, ensureDemoWorkspace, generateGstr1, getGstrPreview, getSummary, getTransactions } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

type Tool = "home" | "gos" | "e2t" | "recon";
type View = "dashboard" | "profile" | "upload" | "manage" | "report" | "company" | "customize" | "xml" | "reconUpload" | "reconReport";

const platformCards = [
  { key: "meesho", name: "Meesho", sub: "B2C", logo: "m", color: "bg-[#f72585] text-white", badge: "" },
  { key: "amazon", name: "Amazon", sub: "B2C", logo: "a", color: "bg-white text-black", badge: "" },
  { key: "amazon-b2b", name: "Amazon B2B", sub: "B2B", logo: "a", color: "bg-white text-black", badge: "" },
  { key: "flipkart", name: "Flipkart", sub: "B2C & B2B Sales Report", logo: "F", color: "bg-[#ffd52e] text-[#1769d2]", badge: "" },
  { key: "myntra", name: "Myntra", sub: "B2C", logo: "M", color: "bg-gradient-to-tr from-pink-500 via-orange-400 to-purple-600 text-white", badge: "" },
  { key: "snapdeal", name: "Snapdeal", sub: "B2C", logo: "S", color: "bg-[#e51b35] text-white", badge: "" },
  { key: "glowroad", name: "Glowroad", sub: "B2C", logo: "g", color: "bg-[#005b66] text-white", badge: "" },
  { key: "limeroad", name: "Limeroad", sub: "B2C", logo: "LR", color: "bg-[#e00046] text-white", badge: "" },
  { key: "jiomart", name: "JioMart", sub: "B2C", logo: "Jio", color: "bg-[#d51224] text-white", badge: "" },
  { key: "json", name: "GSTR1 JSON", sub: "B2C/B2B/B2CL/CDNR", logo: "JSON", color: "bg-slate-100 text-green-600", badge: "Beta" },
  { key: "excel", name: "GSTR1 Excel", sub: "B2C/B2B/B2CL/Exempt/Exp", logo: "X", color: "bg-green-600 text-white", badge: "" },
  { key: "custom", name: "Custom Excel", sub: "B2C/B2B/Exempt", logo: "X", color: "bg-green-600 text-white", badge: "" }
];

function TopNav() {
  return (
    <header className="sticky top-0 z-40 h-[58px] border-b border-slate-100 bg-white">
      <div className="mx-auto flex h-full max-w-[1280px] items-center justify-between px-6">
        <div className="flex items-center gap-2">
          <div className="text-[26px] font-black leading-none text-[#10244d]">
            GST<span className="block -mt-1 text-[15px] font-extrabold text-[#f59e0b]">BHARAT</span>
          </div>
        </div>
        <nav className="hidden items-center gap-8 text-sm md:flex">
          <button className="font-semibold text-[#ef4d82]">Dashboard</button>
          <button className="flex items-center gap-1 text-slate-600">Our Tools <ChevronDown className="size-3" /></button>
          <button className="text-slate-600">Screenshot</button>
          <button className="text-slate-600">Support</button>
          <span className="grid size-9 place-items-center rounded-full bg-[#ef4d82] font-bold text-white">P</span>
        </nav>
        <Menu className="size-5 text-slate-500 md:hidden" />
      </div>
    </header>
  );
}

function Hero({ tool, view, profile }: { tool: Tool; view: View; profile: Profile | null }) {
  const title = tool === "e2t" ? "eCom to Tally" : tool === "recon" ? "2B/2A Reconcile" : tool === "home" ? "Dashboard" : "GST Online Seller Tool";
  const crumbs = tool === "home" ? "Home / Dashboard" : `Home / Dashboard / ${title} / ${labelForView(view)}`;
  return (
    <section className="gst-pattern h-[190px] text-white">
      <div className="mx-auto flex max-w-[1280px] justify-between px-6 pt-11">
        <div>
          <h1 className="text-2xl font-bold">{title}</h1>
          <p className="mt-3 text-sm font-medium">
            <span>Home</span>
            <span className="mx-2 text-white/70">/</span>
            <span className="text-[#3b82f6]">{crumbs.split("/").slice(1).join(" / ")}</span>
          </p>
        </div>
        {profile && tool !== "home" && (
          <div className="mt-1 hidden h-fit rounded bg-white/10 px-4 py-3 text-[11px] leading-5 lg:block">
            <p>GSTIN: {profile.gstin}</p>
            <p>Period: April-2026</p>
          </div>
        )}
      </div>
    </section>
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
    reconReport: "Online Seller Tool"
  }[view];
}

function Sidebar({ tool, view, setView }: { tool: Tool; view: View; setView: (view: View) => void }) {
  const gos = [
    ["profile", "GST Profile", Building2],
    ["upload", "Import Data", Upload],
    ["manage", "Manage Data", Database],
    ["report", "GSTR1 Report", FileJson]
  ] as const;
  const e2t = [
    ["company", "Tally Company", Building2],
    ["upload", "Import Data", Upload],
    ["manage", "Manage Data", Database],
    ["customize", "Customize Master", Settings],
    ["xml", "Generate XML", FileArchive]
  ] as const;
  const recon = [
    ["reconUpload", "2B/2A Reconcile", RotateCw],
    ["reconReport", "Online Seller Tool", ReceiptText]
  ] as const;
  const items = tool === "e2t" ? e2t : tool === "recon" ? recon : gos;
  return (
    <aside className="gst-shadow min-h-[250px] w-[230px] shrink-0 rounded-md bg-white px-8 py-6">
      <button onClick={() => setView("dashboard")} className="mb-5 w-full border-b border-slate-200 pb-5 text-center text-lg font-bold text-[#3478ff]">Dashboard</button>
      <p className="mb-5 text-[11px] font-black uppercase text-slate-900">{tool === "e2t" ? "eCom to Tally" : tool === "recon" ? "Reconcile" : "GST Online Seller"}</p>
      <div className="space-y-1">
        {items.map(([key, text, Icon]) => (
          <button
            key={key}
            onClick={() => setView(key)}
            className={`relative flex w-full items-center gap-4 rounded py-2.5 pl-1 text-left text-sm ${view === key ? "font-bold text-[#3478ff]" : "text-[#1f335c]"}`}
          >
            {view === key && <span className="absolute -left-8 top-1/2 h-9 w-1 -translate-y-1/2 bg-[#3478ff]" />}
            <Icon className="size-4 text-slate-500" />
            {text}
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
        <div className="mx-auto -mt-8 flex max-w-[1080px] gap-6 px-6">
          {tool !== "home" && <Sidebar tool={tool} view={view} setView={setView} />}
          <section className={tool === "home" ? "mx-auto w-full max-w-[900px]" : "min-w-0 flex-1"}>{children}</section>
        </div>
      </main>
    </>
  );
}

function WhitePanel({ title, subtitle, children, className = "" }: { title: string; subtitle?: string; children?: React.ReactNode; className?: string }) {
  return (
    <div className={`gst-shadow rounded-md bg-white ${className}`}>
      <div className="px-8 py-7 text-center">
        <h2 className="text-xl font-bold text-slate-950">{title}</h2>
        {subtitle && <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-500">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

function HomeTools({ setTool, setView }: { setTool: (tool: Tool) => void; setView: (view: View) => void }) {
  const cards = [
    { tool: "gos" as Tool, title: "GST Online Seller", text: "Convert e-Commerce excel into GSTR1 excel & json.", red: true },
    { tool: "recon" as Tool, title: "2B/2A Reconcile v2.0", text: "Reconcile 2B/2A purchase data and download query report.", red: false },
    { tool: "e2t" as Tool, title: "eCom to Tally", text: "Convert e-Commerce excel into Tally import XML.", red: true }
  ];
  return (
    <WhitePanel title="Our Tools" subtitle="Here is all tool click access now to use our tool.">
      <div className="grid gap-5 px-7 pb-7 md:grid-cols-3">
        {cards.map((card) => (
          <div key={card.title} className={`rounded-sm border ${card.red ? "border-red-500" : "border-slate-200"} bg-[#10244d] p-3 text-white`}>
            <div className="mb-3 flex h-28 items-center justify-center rounded bg-[#3b78ff] text-3xl font-bold">
              {card.tool === "recon" ? <FileSpreadsheet className="size-16 text-white" /> : <span>a → GST → XML</span>}
            </div>
            <p className="text-xs uppercase text-slate-300">{card.tool === "e2t" ? "Account" : "GST"}</p>
            <h3 className="mt-1 text-base font-bold">{card.title}</h3>
            <p className="mt-2 min-h-12 text-xs leading-5 text-slate-300">{card.text}</p>
            <div className="mt-3 flex items-center justify-between border-t border-white/10 pt-3">
              <span className="text-sm text-[#05d7c5]">Active</span>
              <button onClick={() => { setTool(card.tool); setView(card.tool === "recon" ? "reconUpload" : card.tool === "e2t" ? "company" : "profile"); }} className="rounded bg-[#3b78ff] px-3 py-2 text-xs font-semibold">Access Now</button>
            </div>
          </div>
        ))}
      </div>
    </WhitePanel>
  );
}

function PlatformLogo({ card }: { card: typeof platformCards[number] }) {
  return (
    <div className={`mx-auto grid size-14 place-items-center rounded-lg text-2xl font-black ${card.color}`}>
      {card.logo}
    </div>
  );
}

function UploadGrid({ openModal, e2t = false }: { openModal: (card: typeof platformCards[number]) => void; e2t?: boolean }) {
  const cards = e2t ? platformCards.slice(1, 9) : platformCards;
  return (
    <WhitePanel title="Import Platform Data" subtitle={e2t ? "Upload platform data to convert into Tally XML." : "Upload platform data then check view statement & generate GSTR1."}>
      <div className="mx-auto max-w-[680px] px-7 pb-8">
        {!e2t && (
          <>
            <div className="mx-auto mb-4 flex max-w-[470px] rounded-md border border-slate-200 bg-white p-2">
              <input className="flex-1 px-4 text-sm outline-none" placeholder="Search for platform" />
              <button className="grid size-10 place-items-center rounded bg-[#3478ff] text-white">→</button>
            </div>
            <p className="mb-7 text-center text-sm text-[#ff4d7d]">Caution: Avoid importing the edited file to prevent potential errors.</p>
            <div className="mb-5 flex items-center gap-3 text-xs text-slate-500">
              <span className="h-px flex-1 bg-slate-200" />
              Famous Platforms
              <span className="h-px flex-1 bg-slate-200" />
            </div>
          </>
        )}
        {e2t && (
          <div className="mb-5 flex items-center gap-3 text-xs text-slate-500">
            <span className="h-px flex-1 bg-slate-200" />
            Order Data
            <span className="h-px flex-1 bg-slate-200" />
          </div>
        )}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
          {cards.map((card) => (
            <button key={card.key} onClick={() => openModal(card)} className="platform-card-shadow relative min-h-[132px] rounded-md border border-slate-200 bg-white p-4 text-center transition hover:-translate-y-0.5">
              {card.badge && <span className="absolute right-0 top-0 rounded-bl bg-[#12264f] px-2 py-1 text-[10px] font-bold text-white">{card.badge}</span>}
              <PlatformLogo card={card} />
              <h3 className="mt-2 text-sm font-black text-black">{card.name}</h3>
              <p className="text-xs text-slate-500">{card.sub}</p>
              <span className="mt-4 inline-flex rounded-full bg-slate-100 px-4 py-2 text-[11px] font-bold text-black">IMPORT DATA</span>
            </button>
          ))}
        </div>
      </div>
    </WhitePanel>
  );
}

function UploadModal({ card, onClose }: { card: typeof platformCards[number] | null; onClose: () => void }) {
  if (!card) return null;
  const files = card.key === "meesho" ? ["tcs_sales.xlsx", "tcs_sales_return.xlsx", "Tax_invoice_details.xlsx"] : card.key === "amazon" ? ["MTR_B2C File"] : card.key === "flipkart" ? ["Sales Report"] : ["Upload File"];
  return (
    <div className="fixed inset-0 z-50 grid place-items-start bg-[#b7c1d1]/80 pt-12">
      <div className="w-[455px] rounded-md bg-white shadow-2xl">
        <div className="flex items-start justify-between border-b border-slate-200 px-6 py-4">
          <div className="flex items-center gap-3">
            <PlatformLogo card={card} />
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold">{card.name}</h3>
                <span className="rounded bg-[#3478ff] px-2 py-0.5 text-[10px] font-bold text-white">{card.sub.split(" ")[0]}</span>
              </div>
              <p className="text-xs text-slate-500">{card.name.toLowerCase()}.com</p>
            </div>
          </div>
          <button onClick={onClose}><X className="size-5 text-slate-500" /></button>
        </div>
        <div className="space-y-4 px-6 py-6">
          <div className="rounded-md border border-slate-200 py-2 text-center text-sm">April Data</div>
          <div>
            <p className="mb-2 text-xs font-bold">Download Path</p>
            <p className="text-sm leading-5 text-slate-500">
              {card.key === "meesho" ? "Meesho Panel → Payments → Download GST Reports" : card.key === "flipkart" ? "Flipkart Portal → Report → Reports Center → Request New Report → Tax Reports → Sales report" : "Reports → Manage Taxes → GST Monthly Reports → Download Report"}
            </p>
          </div>
          <div className="flex rounded border border-slate-200">
            <span className="w-40 border-r border-slate-200 px-3 py-2 text-sm text-slate-500">GSTIN of {card.name}</span>
            <span className="flex-1 px-3 py-2 text-sm">{card.key === "meesho" ? "07AARCM9332R1CQ" : card.key === "flipkart" ? "07AACCF0683K1CU" : card.key === "amazon" ? "07AAICA3918J1CV" : "Auto Detect"}</span>
          </div>
          <div>
            <p className="mb-2 text-xs font-bold">Upload Files: <span className="text-[#ff4d7d]">(April-2026)</span></p>
            <div className="space-y-2">
              {files.map((file) => (
                <div key={file} className="flex rounded border border-slate-200">
                  <span className="w-36 bg-slate-50 px-3 py-2 text-sm">{file}</span>
                  <span className="flex-1 px-3 py-2 text-sm">No file selected.</span>
                </div>
              ))}
            </div>
          </div>
          <button className="rounded bg-[#3478ff] px-5 py-2 text-sm font-bold text-white">Upload</button>
          <div className="rounded-md bg-[#06c7a8] px-4 py-3 text-sm text-white">File uploaded successfully</div>
        </div>
        <div className="flex justify-end border-t border-slate-200 bg-slate-50 px-4 py-4">
          <button onClick={onClose} className="rounded bg-slate-600 px-4 py-2 text-sm text-white">Close</button>
        </div>
      </div>
    </div>
  );
}

function ProfileView({ profile }: { profile: Profile | null }) {
  return (
    <div className="space-y-6">
      <WhitePanel title="GST Information" subtitle="Provide GST Number, month and year of filing.">
        <div className="mx-auto max-w-[620px] px-8 pb-8">
          <div className="grid grid-cols-[1fr_190px_110px] overflow-hidden rounded-md border border-slate-200 text-sm">
            <div className="px-4 py-3 text-slate-500">GST Number</div>
            <div className="border-l border-slate-200 px-4 py-3">April 2026</div>
            <button className="bg-[#3478ff] font-bold text-white">Submit</button>
            <div className="border-t border-slate-200 px-4 py-3">{profile?.gstin || "07TCRPS8655B1ZK"}</div>
            <div className="border-l border-t border-slate-200 px-4 py-3">Monthly</div>
            <div className="border-t border-slate-200" />
          </div>
          <p className="mt-4 text-right text-xs text-[#3478ff]">Need Help ? Read the Guide</p>
        </div>
      </WhitePanel>
      <WhitePanel title="GSTIN List" subtitle="Added GSTIN List">
        <div className="grid gap-4 px-8 pb-8 md:grid-cols-2">
          {[profile?.gstin || "07TCRPS8655B1ZK", "24JFPPKJ7874H1ZM", "24BOPSC9797Q1ZL", "07TCRPS8655B1ZK"].map((gstin) => (
            <div key={gstin} className="rounded border border-slate-200 bg-white p-4 text-center text-xs">
              <p className="font-bold">{gstin}</p>
              <p className="mt-1 text-slate-500">Added: 22-07-2023 / Used: 23-04-2026</p>
              <button className="mt-2 rounded bg-[#3478ff] px-4 py-1 text-white">Select</button>
            </div>
          ))}
        </div>
      </WhitePanel>
    </div>
  );
}

function ManageView({ tool, setView, summary }: { tool: Tool; setView: (view: View) => void; summary: DashboardSummary | null }) {
  if (tool === "e2t") {
    return (
      <WhitePanel title="Manage of Imported Data" subtitle="View, edit, and delete your imported data as needed before converting them into Tally XML.">
        <div className="mx-auto max-w-[760px] px-8 pb-10">
          {[
            ["Manage Invoices", "You can view, edit and delete individual invoices.", ReceiptText],
            ["Update Stock SKU", "You can view, edit Stock SKU's.", Layers3],
            ["Update Stock Name", "You can view, edit Stock Name's.", Layers3],
            ["Update Stock Unit (UQC)", "You can view, edit Stock Unit (UQC).", Package]
          ].map(([title, desc, Icon]) => (
            <div key={String(title)} className="flex items-center justify-between border border-slate-200 px-5 py-5 first:rounded-t-md last:rounded-b-md">
              <div className="flex items-center gap-5"><Icon className="size-9 text-black" /><div><h3 className="text-lg font-semibold">{String(title)}</h3><p className="text-slate-500">{String(desc)}</p></div></div>
              <button className="rounded bg-[#3478ff] px-5 py-2 font-semibold text-white">Actions</button>
            </div>
          ))}
          <div className="mt-8 flex justify-center gap-4"><button onClick={() => setView("customize")} className="rounded border px-8 py-3 font-semibold text-slate-500">Customize Master</button><button onClick={() => setView("xml")} className="rounded bg-[#3478ff] px-8 py-3 font-semibold text-white">Generate Tally XML</button></div>
        </div>
      </WhitePanel>
    );
  }
  return (
    <WhitePanel title="Manage of Imported Data" subtitle="You can view, edit, and delete invoice and platform data.">
      <div className="px-8 pb-8">
        <table className="mx-auto w-full max-w-[640px] border border-slate-200 text-center text-sm">
          <thead className="bg-slate-50"><tr><th className="p-3">Platform</th><th>B2C Sales</th><th>B2C Returns</th><th>CDNR</th><th>HSN</th><th /></tr></thead>
          <tbody>
            <tr className="border-t"><td className="p-3 font-bold text-[#f72585]">Meesho</td><td>0.00</td><td>5,210.46</td><td>0.00</td><td>10,988.86</td><td><X className="mx-auto size-4 text-[#ff4d7d]" /></td></tr>
            <tr className="border-t"><td className="p-3 font-bold text-slate-600">Live Summary</td><td>{summary ? formatCurrency(Number(summary.total_taxable_value)) : "-"}</td><td colSpan={4}>Official calculator ready</td></tr>
          </tbody>
        </table>
        <div className="mt-5 text-center"><button onClick={() => setView("report")} className="rounded bg-[#3478ff] px-5 py-2 text-xs font-bold text-white">Generate GSTR1</button></div>
      </div>
    </WhitePanel>
  );
}

function ReportView({ preview, onGenerate }: { preview: Gstr1Payload | null; onGenerate: () => void }) {
  return (
    <WhitePanel title="GSTR1 Report" subtitle="Here is your GSTR1 report generated download excel and json provided.">
      <div className="mx-auto max-w-[650px] px-8 pb-8">
        <table className="w-full border border-slate-200 text-center text-xs">
          <thead className="bg-slate-50"><tr><th className="p-3">No. of records</th><th>Taxable Value</th><th>Integrated tax</th><th>Central tax</th><th>State/UT tax</th><th>Invoice</th><th>Option</th></tr></thead>
          <tbody><tr className="border-t"><td className="p-3">24</td><td>21,565.87</td><td>628.95</td><td>9.01</td><td>9.01</td><td>22,212.83</td><td><button className="text-[#3478ff]">Edit</button></td></tr></tbody>
        </table>
        <div className="mt-5 space-y-2 text-xs text-slate-500">
          <label className="flex items-center gap-2"><input type="checkbox" /> B2CS HSN</label>
          <label className="flex items-center gap-2"><input type="checkbox" /> Documents Issued</label>
        </div>
        <p className="mt-5 text-center text-sm text-[#3478ff]">Return of April - 2026</p>
        <div className="mt-4 flex justify-center gap-4">
          <button className="flex items-center gap-2 rounded bg-[#3478ff] px-5 py-3 text-sm font-bold text-white"><FileSpreadsheet className="size-5" /> GSTR1 Excel Download</button>
          <button onClick={onGenerate} className="flex items-center gap-2 rounded bg-[#3478ff] px-5 py-3 text-sm font-bold text-white"><FileJson className="size-5" /> GSTR1 Json Download</button>
        </div>
      </div>
    </WhitePanel>
  );
}

function CompanyView() {
  return (
    <WhitePanel title="Tally Company" subtitle="Select or add company from list.">
      <div className="px-8 pb-10 text-right">
        <button className="rounded bg-[#3478ff] px-5 py-2 text-sm font-bold text-white">Add Company</button>
      </div>
      <div className="fixed left-1/2 top-20 z-20 w-[360px] -translate-x-1/2 rounded-md bg-white p-5 shadow-2xl">
        <p className="mb-3 text-xs text-slate-500">Add Tally Company</p>
        <div className="flex overflow-hidden rounded border border-slate-200">
          <div className="flex-1 space-y-2 p-2"><input className="w-full rounded border px-3 py-2 text-xs" placeholder="Tally Company Name" /><input className="w-full rounded border px-3 py-2 text-xs" placeholder="Company GSTIN" /></div>
          <button className="bg-[#3478ff] px-4 text-white">→</button>
        </div>
        <p className="mt-2 text-[11px] text-slate-500">* GSTIN leave blank to support all GSTIN.</p>
      </div>
    </WhitePanel>
  );
}

function CustomizeView({ setView }: { setView: (view: View) => void }) {
  return (
    <WhitePanel title="Customize Master" subtitle="Change and update your ledger, voucher and party names.">
      <div className="mx-auto max-w-[620px] px-8 pb-8">
        <p className="rounded-t border border-slate-200 bg-slate-50 py-3 text-center text-sm text-[#3478ff]">Sales Ledger Customization</p>
        {["Party Name", "Voucher Type", "Sales Ledger", "Tax Ledger", "Stock Name", "Other Ledger"].map((item) => <div key={item} className="border-x border-b border-slate-200 px-4 py-3 text-sm">+ {item}</div>)}
        <div className="mt-5 flex justify-end gap-2"><button className="rounded bg-[#3478ff] px-4 py-2 text-xs text-white">Save changes</button><button className="rounded border px-4 py-2 text-xs">Reset</button></div>
        <div className="mt-5 text-center"><button onClick={() => setView("xml")} className="rounded bg-[#3478ff] px-5 py-2 text-xs font-bold text-white">Generate Tally XML</button></div>
      </div>
    </WhitePanel>
  );
}

function XmlView() {
  return (
    <WhitePanel title="Download Tally XML" subtitle="Select your Tally version and download Tally XML.">
      <div className="mx-auto mb-10 w-[230px] rounded bg-white p-6 shadow-lg">
        <p className="mb-3 text-center text-sm font-bold">Tally XML</p>
        <label className="text-xs text-slate-500">Select Tally Version</label>
        <select className="mt-1 w-full rounded border px-3 py-2 text-xs"><option>Choose ...</option></select>
        <label className="mt-3 flex items-center gap-2 text-xs"><input type="checkbox" defaultChecked /> Auto Create Ledger</label>
        <button className="mx-auto mt-4 flex items-center gap-2 rounded bg-[#3478ff] px-4 py-3 text-xs font-bold text-white"><FileArchive className="size-5" /> Tally XML Download</button>
      </div>
    </WhitePanel>
  );
}

function ReconcileView({ report = false }: { report?: boolean }) {
  return (
    <div className="space-y-5">
      <WhitePanel title="2B/2A Reconcile" subtitle="2B/2A Reconcile with Purchase data and provide query report.">
        <div className="px-8 pb-8 text-center text-sm text-slate-500">
          <p className="mx-auto max-w-xl">Please download the sample file for 2B & 2A verification sheet by clicking the button below.</p>
          <button className="mt-4 inline-flex items-center gap-2 rounded bg-[#3478ff] px-5 py-3 text-sm font-bold text-white"><FileSpreadsheet className="size-6" /> Sample File Download</button>
        </div>
      </WhitePanel>
      <WhitePanel title="Upload File">
        <div className="px-8 pb-8">
          <div className="grid gap-5 md:grid-cols-[1fr_120px]">
            <div><label className="text-xs">2B/2A Data Sheet</label><input type="file" className="mt-2 w-full rounded border px-3 py-2 text-sm" /></div>
            <div><label className="text-xs">Difference Ignore</label><input defaultValue="5" className="mt-2 w-full rounded border px-3 py-2 text-sm" /></div>
          </div>
          <button className="mt-4 rounded bg-[#3478ff] px-5 py-2 text-sm font-bold text-white">Submit</button>
          {report && (
            <>
              <div className="mt-5 grid grid-cols-6 text-center text-xs font-bold text-white">
                {["Total 2B", "Total Purchase", "Matched", "Amount Mismatched", "Invoice Mismatched", "Pending"].map((x, i) => <div key={x} className={`p-3 ${i < 3 ? "bg-cyan-500" : i < 5 ? "bg-orange-400" : "bg-pink-500"}`}>{x}<br />{[10, 64, 61, 2, 1, 0][i]}</div>)}
              </div>
              <div className="mt-5 text-center"><button className="inline-flex items-center gap-2 rounded bg-[#3478ff] px-5 py-3 text-sm font-bold text-white"><FileSpreadsheet className="size-6" /> Query Report Download</button></div>
            </>
          )}
        </div>
      </WhitePanel>
    </div>
  );
}

export default function DashboardPage() {
  const [tool, setTool] = useState<Tool>("home");
  const [view, setView] = useState<View>("dashboard");
  const [modal, setModal] = useState<typeof platformCards[number] | null>(null);
  const [token, setToken] = useState("");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [preview, setPreview] = useState<Gstr1Payload | null>(null);

  useEffect(() => {
    ensureDemoWorkspace().then(async ({ token, profile }) => {
      setToken(token);
      setProfile(profile);
      const [summary, preview] = await Promise.all([getSummary(token, profile), getGstrPreview(token, profile)]);
      setSummary(summary);
      setPreview(preview);
      await getTransactions(token, profile);
    }).catch(() => undefined);
  }, []);

  async function handleGenerate() {
    if (!token || !profile) return;
    const result = await generateGstr1(token, profile);
    setPreview(result.json);
  }

  const content = useMemo(() => {
    if (tool === "home") return <HomeTools setTool={setTool} setView={setView} />;
    if (tool === "recon") return view === "reconReport" ? <ReconcileView report /> : <ReconcileView />;
    if (view === "profile") return <ProfileView profile={profile} />;
    if (view === "upload") return <UploadGrid openModal={setModal} e2t={tool === "e2t"} />;
    if (view === "manage") return <ManageView tool={tool} setView={setView} summary={summary} />;
    if (view === "report") return <ReportView preview={preview} onGenerate={handleGenerate} />;
    if (view === "company") return <CompanyView />;
    if (view === "customize") return <CustomizeView setView={setView} />;
    if (view === "xml") return <XmlView />;
    return <HomeTools setTool={setTool} setView={setView} />;
  }, [tool, view, profile, summary, preview]);

  return (
    <>
      <TopNav />
      <PageShell tool={tool} view={view} setView={setView} profile={profile}>
        {content}
      </PageShell>
      <footer className="bg-[#1b335f] py-7 text-white">
        <div className="mx-auto flex max-w-[1080px] items-center justify-between px-6 text-xs">
          <div className="text-xl font-black">GST<span className="text-[#f59e0b]">BHARAT</span></div>
          <div className="hidden gap-12 md:flex"><span>Company</span><span>Our Tools</span><span>Documentation</span><span>Resources</span></div>
        </div>
      </footer>
      <button className="fixed bottom-6 right-6 grid size-11 place-items-center rounded-full bg-sky-400 text-white shadow-lg"><LockKeyhole className="size-5" /></button>
      <UploadModal card={modal} onClose={() => setModal(null)} />
    </>
  );
}
