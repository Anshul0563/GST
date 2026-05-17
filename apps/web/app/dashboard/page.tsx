import { AlertCircle, CheckCircle2, FileJson, IndianRupee, ReceiptText, UploadCloud } from "lucide-react";
import { Sidebar } from "@/components/layout/sidebar";
import { JsonPreview } from "@/components/modules/json-preview";
import { ProfileForm } from "@/components/modules/profile-form";
import { TallyRecon } from "@/components/modules/tally-recon";
import { TransactionsTable } from "@/components/modules/transactions-table";
import { UploadZone } from "@/components/modules/upload-zone";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatCurrency } from "@/lib/utils";

const metrics = [
  { label: "Total sales", value: formatCurrency(2794280), icon: IndianRupee, tone: "text-primary" },
  { label: "Taxable value", value: formatCurrency(2421110), icon: ReceiptText, tone: "text-success" },
  { label: "Total GST", value: formatCurrency(373170), icon: FileJson, tone: "text-accent" },
  { label: "Pending errors", value: "18", icon: AlertCircle, tone: "text-red-600" }
];

export default function DashboardPage() {
  return (
    <main className="flex min-h-screen bg-[#F7FAFD]">
      <Sidebar />
      <section className="min-w-0 flex-1">
        <header className="border-b border-slate-200 bg-white px-5 py-4 lg:px-8">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h1 className="text-2xl font-bold tracking-normal text-slate-950">GST Bharat</h1>
              <p className="mt-1 text-sm text-slate-500">Consolidated marketplace GST filing for April 2026</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline"><UploadCloud className="size-4" />New import</Button>
              <Button><CheckCircle2 className="size-4" />Generate GSTR-1</Button>
            </div>
          </div>
        </header>
        <div className="space-y-6 p-5 lg:p-8">
          <section id="dashboard" className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {metrics.map((metric) => <Card key={metric.label}><CardContent className="flex items-center justify-between p-5"><div><p className="text-sm text-slate-500">{metric.label}</p><p className="mt-2 text-2xl font-bold text-slate-950">{metric.value}</p></div><metric.icon className={`size-8 ${metric.tone}`} /></CardContent></Card>)}
          </section>
          <section className="grid gap-4 xl:grid-cols-3">
            <Card><CardContent className="p-5"><p className="text-sm text-slate-500">IGST / CGST / SGST split</p><p className="mt-3 text-xl font-bold">₹2.84L / ₹44.5K / ₹44.5K</p><div className="mt-4 h-2 rounded-full bg-slate-100"><div className="h-2 w-3/4 rounded-full bg-primary" /></div></CardContent></Card>
            <Card><CardContent className="p-5"><p className="text-sm text-slate-500">Platform-wise sale</p><p className="mt-3 text-xl font-bold">Flipkart leads at 49%</p><div className="mt-4 grid grid-cols-3 gap-2 text-xs"><span className="rounded bg-blue-50 p-2 text-primary">Flipkart</span><span className="rounded bg-orange-50 p-2 text-orange-700">Amazon</span><span className="rounded bg-pink-50 p-2 text-pink-700">Meesho</span></div></CardContent></Card>
            <Card><CardContent className="p-5"><p className="text-sm text-slate-500">JSON generation status</p><p className="mt-3 text-xl font-bold text-success">Preview ready</p><p className="mt-2 text-sm text-slate-500">B2CS, SUPECO and doc issue sections generated.</p></CardContent></Card>
          </section>
          <ProfileForm />
          <UploadZone />
          <TransactionsTable />
          <JsonPreview />
          <TallyRecon />
        </div>
      </section>
    </main>
  );
}

