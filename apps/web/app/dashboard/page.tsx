"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertCircle, CheckCircle2, FileJson, IndianRupee, Loader2, ReceiptText, UploadCloud } from "lucide-react";
import { Sidebar } from "@/components/layout/sidebar";
import { JsonPreview } from "@/components/modules/json-preview";
import { ProfileForm } from "@/components/modules/profile-form";
import { TallyRecon } from "@/components/modules/tally-recon";
import { TransactionsTable } from "@/components/modules/transactions-table";
import { UploadZone } from "@/components/modules/upload-zone";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatCurrency } from "@/lib/utils";
import { DashboardSummary, Gstr1Payload, Profile, Transaction, createProfile, ensureDemoWorkspace, generateGstr1, getGstrPreview, getSummary, getTransactions } from "@/lib/api";

export default function DashboardPage() {
  const [token, setToken] = useState("");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [rows, setRows] = useState<Transaction[]>([]);
  const [preview, setPreview] = useState<Gstr1Payload | null>(null);
  const [status, setStatus] = useState("Connecting to GST Bharat API");

  const refresh = useCallback(async (activeToken?: string, activeProfile?: Profile) => {
    const usableToken = activeToken || token;
    const usableProfile = activeProfile || profile;
    if (!usableToken || !usableProfile) return;
    const [nextSummary, nextRows, nextPreview] = await Promise.all([
      getSummary(usableToken, usableProfile),
      getTransactions(usableToken, usableProfile),
      getGstrPreview(usableToken, usableProfile)
    ]);
    setSummary(nextSummary);
    setRows(nextRows);
    setPreview(nextPreview);
    setStatus(`Live workspace loaded: ${nextRows.length} normalized rows`);
  }, [profile, token]);

  useEffect(() => {
    let mounted = true;
    ensureDemoWorkspace()
      .then(async ({ token: nextToken, profile: nextProfile }) => {
        if (!mounted) return;
        setToken(nextToken);
        setProfile(nextProfile);
        await refresh(nextToken, nextProfile);
      })
      .catch((error) => setStatus(`API not ready: ${String(error).slice(0, 120)}`));
    return () => {
      mounted = false;
    };
  }, [refresh]);

  const metrics = useMemo(() => [
    { label: "Total sales", value: formatCurrency(Number(summary?.total_sales || 0)), icon: IndianRupee, tone: "text-primary" },
    { label: "Taxable value", value: formatCurrency(Number(summary?.total_taxable_value || 0)), icon: ReceiptText, tone: "text-success" },
    { label: "Total GST", value: formatCurrency(Number(summary?.total_gst || 0)), icon: FileJson, tone: "text-accent" },
    { label: "Pending errors", value: String(summary?.pending_errors ?? 0), icon: AlertCircle, tone: "text-red-600" }
  ], [summary]);

  async function saveProfile(payload: Omit<Profile, "id" | "state_code">) {
    if (!token) return;
    const nextProfile = await createProfile(token, payload);
    setProfile(nextProfile);
    await refresh(token, nextProfile);
  }

  async function handleGenerate() {
    if (!token || !profile) return;
    setStatus("Generating GSTR-1 JSON and Excel");
    const exportResult = await generateGstr1(token, profile);
    setPreview(exportResult.json);
    await refresh(token, profile);
  }

  return (
    <main className="flex min-h-screen bg-[#F7FAFD]">
      <Sidebar />
      <section className="min-w-0 flex-1">
        <header className="border-b border-slate-200 bg-white px-5 py-4 lg:px-8">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h1 className="text-2xl font-bold tracking-normal text-slate-950">GST Bharat</h1>
              <p className="mt-1 flex items-center gap-2 text-sm text-slate-500">{status.startsWith("Connecting") && <Loader2 className="size-3 animate-spin" />}{status}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline"><UploadCloud className="size-4" />New import</Button>
              <Button onClick={handleGenerate}><CheckCircle2 className="size-4" />Generate GSTR-1</Button>
            </div>
          </div>
        </header>
        <div className="space-y-6 p-5 lg:p-8">
          <section id="dashboard" className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {metrics.map((metric) => <Card key={metric.label}><CardContent className="flex items-center justify-between p-5"><div><p className="text-sm text-slate-500">{metric.label}</p><p className="mt-2 text-2xl font-bold text-slate-950">{metric.value}</p></div><metric.icon className={`size-8 ${metric.tone}`} /></CardContent></Card>)}
          </section>
          <section className="grid gap-4 xl:grid-cols-3">
            <Card><CardContent className="p-5"><p className="text-sm text-slate-500">IGST / CGST / SGST split</p><p className="mt-3 text-xl font-bold">{formatCurrency(Number(summary?.igst || 0))} / {formatCurrency(Number(summary?.cgst || 0))} / {formatCurrency(Number(summary?.sgst || 0))}</p><div className="mt-4 h-2 rounded-full bg-slate-100"><div className="h-2 w-3/4 rounded-full bg-primary" /></div></CardContent></Card>
            <Card><CardContent className="p-5"><p className="text-sm text-slate-500">Platform-wise sale</p><p className="mt-3 text-xl font-bold">{summary?.platform_wise_sale?.[0]?.platform ?? "No"} live rows</p><div className="mt-4 grid grid-cols-3 gap-2 text-xs">{(summary?.platform_wise_sale || []).slice(0, 3).map((item) => <span key={item.platform} className="rounded bg-blue-50 p-2 text-primary">{item.platform}: {item.rows}</span>)}</div></CardContent></Card>
            <Card><CardContent className="p-5"><p className="text-sm text-slate-500">JSON generation status</p><p className="mt-3 text-xl font-bold text-success">{summary?.json_generation_status?.replaceAll("_", " ") || "preview ready"}</p><p className="mt-2 text-sm text-slate-500">B2CS, SUPECO and doc issue sections generated from live rows.</p></CardContent></Card>
          </section>
          <ProfileForm profile={profile} onSave={saveProfile} />
          <UploadZone token={token} profileId={profile?.id} onUploaded={() => setTimeout(() => refresh(), 1200)} />
          <TransactionsTable rows={rows} />
          <JsonPreview payload={preview} onGenerate={handleGenerate} />
          <TallyRecon />
        </div>
      </section>
    </main>
  );
}
