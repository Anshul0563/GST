"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AlertTriangle, ArrowRight, FileSpreadsheet, Trash2, UploadCloud } from "lucide-react";
import { AppShell } from "@/components/saas/app-shell";
import { EmptyState, Panel, StatusPill } from "@/components/saas/ui";
import { useWorkspace } from "@/components/saas/workspace";
import { marketplaces } from "@/lib/marketplaces";
import { BatchStatus, ImportErrors, deleteImportBatch, getImportErrors, getImportStatus, uploadMarketplaceFiles } from "@/lib/api";

export function ImportsPage() {
  const params = useSearchParams();
  const workspace = useWorkspace();
  const initial = params.get("platform") || "meesho";
  const [platformKey, setPlatformKey] = useState(initial);
  const [files, setFiles] = useState<File[]>([]);
  const [progress, setProgress] = useState("");
  const [activeBatch, setActiveBatch] = useState<BatchStatus | null>(null);
  const [errors, setErrors] = useState<ImportErrors | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const activeProfileKey = workspace.profile ? `${workspace.profile.id}:${workspace.profile.return_period}` : "";
  useEffect(() => {
    setFiles([]);
    setProgress("");
    setActiveBatch(null);
    setErrors(null);
    setDeletingId(null);
  }, [activeProfileKey]);
  const selected = useMemo(() => marketplaces.find((item) => item.key === platformKey) || marketplaces[0], [platformKey]);
  const canImport = selected.status !== "Coming Soon";

  async function startImport() {
    if (!canImport) {
      setProgress(`${selected.name} parser is not enabled yet.`);
      return;
    }
    if (!workspace.token || !workspace.profile || !files.length) {
      setProgress("Choose files before starting import.");
      return;
    }
    setProgress("Uploading files securely...");
    const batch = await uploadMarketplaceFiles(workspace.token, workspace.profile.id, selected.key, files);
    setActiveBatch(batch);
    setProgress(`Batch ${batch.id} queued. Parser is reading files...`);
    for (let index = 0; index < 8; index += 1) {
      await new Promise((resolve) => setTimeout(resolve, 900));
      const status = await getImportStatus(workspace.token, batch.id);
      setActiveBatch(status);
      setProgress(`Status: ${status.status}. Parsed ${status.parsed_rows}, errors ${status.error_rows}.`);
      if (!["queued", "processing"].includes(status.status)) break;
    }
    const finalStatus = await getImportStatus(workspace.token, batch.id);
    if (finalStatus.error_rows) {
      setErrors(await getImportErrors(workspace.token, batch.id));
    }
    await workspace.refresh();
  }

  async function openErrors(batchId: number) {
    if (!workspace.token) return;
    setActiveBatch(workspace.batches.find((batch) => batch.id === batchId) || null);
    setErrors(await getImportErrors(workspace.token, batchId));
  }

  async function removeBatch(batch: BatchStatus) {
    if (!workspace.token) return;
    const confirmed = window.confirm(`Delete ${batch.platform} batch #${batch.id}? Imported rows from this batch will also be removed.`);
    if (!confirmed) return;
    setDeletingId(batch.id);
    setProgress("");
    try {
      await deleteImportBatch(workspace.token, batch.id);
      if (activeBatch?.id === batch.id) setActiveBatch(null);
      setErrors(null);
      await workspace.refresh();
      setProgress(`Batch #${batch.id} deleted.`);
    } catch (exc) {
      setProgress(exc instanceof Error ? exc.message : "Could not delete import batch.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <AppShell requiresSubscription requiredPlan="online_seller" token={workspace.token} user={workspace.user} productName="GST Online Seller" title="Marketplace Upload" subtitle="Select profile, platform, required files and track parser progress from upload to normalized transactions." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }}>
      {!workspace.token ? <EmptyState title="Login required" body="Imports are connected to secure backend APIs. Login before uploading marketplace files." /> : !workspace.profile ? <EmptyState title="Create GST profile first" body="Uploads require a GST profile and return period so normalized rows are stored against the correct GSTIN." /> : null}
      <div className="grid gap-6 xl:grid-cols-[0.8fr_1.2fr]">
        <Panel title="Import steps" subtitle="A production upload flow with profile, period and parser feedback.">
          <div className="space-y-3">
            {["Select GST profile + filing period", "Choose marketplace platform", "Review required files", "Drag/drop upload", "Parse progress", "Success/error report", "View imported transactions"].map((step, index) => <div key={step} className={`flex items-center gap-3 rounded-2xl p-3 text-sm font-semibold ${index < 3 ? "bg-blue-50 text-blue-700" : "bg-slate-50 text-slate-600 dark:bg-white/5"}`}><span className="grid size-7 place-items-center rounded-full bg-white text-xs shadow-sm">{index + 1}</span>{step}</div>)}
          </div>
        </Panel>
        <Panel title="Upload workspace" subtitle="Active and beta parsers connect to backend import APIs. Coming-soon platforms are locked until parser support is added.">
          <div className="grid gap-4 md:grid-cols-2">
            <label className="text-sm font-bold">GST profile<select className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 dark:border-white/10 dark:bg-slate-900"><option>{workspace.profile?.gstin || "No GSTIN"}</option></select></label>
            <label className="text-sm font-bold">Filing period<input value={workspace.profile?.return_period || ""} readOnly className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 dark:border-white/10 dark:bg-slate-900" /></label>
            <label className="text-sm font-bold md:col-span-2">Platform<select value={platformKey} onChange={(event) => { setPlatformKey(event.target.value); setFiles([]); setProgress(""); }} className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 dark:border-white/10 dark:bg-slate-900">{marketplaces.map((item) => <option key={item.key} value={item.key}>{item.name} - {item.status}</option>)}</select></label>
          </div>
          <div className="mt-5 rounded-3xl border border-slate-200 bg-slate-50 p-5 dark:border-white/10 dark:bg-white/5">
            <div className="flex items-center justify-between"><div><h3 className="font-black">{selected.name}</h3><p className="text-sm text-slate-500">{selected.guide}</p></div><StatusPill status={selected.status} /></div>
            {!canImport && <div className="mt-4 rounded-2xl bg-amber-50 p-4 text-sm font-bold text-amber-800">{selected.name} upload is coming soon. Choose Amazon, Flipkart, Meesho, Custom Excel, or a beta parser.</div>}
            <div className="mt-4 grid gap-3">
              {selected.requiredFiles.map((file, index) => <label key={file} className={`flex min-h-16 items-center gap-3 rounded-2xl border border-dashed border-slate-300 bg-white p-4 text-sm dark:border-white/10 dark:bg-slate-900 ${canImport ? "cursor-pointer" : "cursor-not-allowed opacity-60"}`}><FileSpreadsheet className="size-5 text-emerald-600" /><span className="w-44 font-bold">{file}</span><input type="file" disabled={!canImport} className="flex-1 text-xs" onChange={(event) => {
                const selectedFile = event.target.files?.[0];
                if (!selectedFile) return;
                setFiles((current) => {
                  const next = [...current];
                  next[index] = selectedFile;
                  return next.filter(Boolean);
                });
              }} /></label>)}
            </div>
            <button onClick={startImport} disabled={!canImport || !workspace.profile} className="mt-5 inline-flex items-center gap-2 rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-50"><UploadCloud className="size-4" /> {canImport ? "Start import" : "Coming soon"} <ArrowRight className="size-4" /></button>
            {progress && <div className="mt-4 rounded-2xl bg-emerald-50 p-4 text-sm font-semibold text-emerald-700">{progress}</div>}
            {activeBatch && <div className="mt-4 grid gap-3 rounded-2xl bg-white p-4 text-sm dark:bg-slate-900 md:grid-cols-3"><b>Batch #{activeBatch.id}</b><span>{activeBatch.parsed_rows} parsed</span><span>{activeBatch.error_rows} errors</span></div>}
          </div>
        </Panel>
      </div>
      <div className="mt-6">
        <Panel title="Import status timeline" subtitle="Recent parser jobs and error counts.">
          {workspace.batches.length ? <div className="space-y-3">{workspace.batches.map((batch) => {
            const busy = deletingId === batch.id;
            const locked = ["queued", "processing"].includes(batch.status);
            return <div key={batch.id} className="grid gap-3 rounded-2xl bg-slate-50 p-4 text-sm dark:bg-white/5 md:grid-cols-[1fr_auto_auto_auto_auto_auto]">
              <b className="capitalize">{batch.platform}</b>
              <span>{batch.parsed_rows} parsed</span>
              <span>{batch.error_rows} errors</span>
              <StatusPill status={batch.status} />
              {batch.error_rows ? <button onClick={() => openErrors(batch.id)} className="inline-flex items-center gap-1 rounded-xl bg-rose-50 px-3 py-2 text-xs font-bold text-rose-700"><AlertTriangle className="size-3" /> Errors</button> : <span />}
              <button onClick={() => removeBatch(batch)} disabled={busy || locked} className="inline-flex items-center gap-1 rounded-xl bg-white px-3 py-2 text-xs font-bold text-rose-700 shadow-sm ring-1 ring-rose-100 disabled:cursor-not-allowed disabled:opacity-45 dark:bg-slate-900 dark:ring-white/10">
                <Trash2 className="size-3" /> {busy ? "Deleting" : "Delete"}
              </button>
            </div>;
          })}</div> : <EmptyState title="No import batches" body="Start your first guided import to see progress here." /> }
        </Panel>
      </div>
      {errors && <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/40" onClick={() => setErrors(null)}><aside onClick={(event) => event.stopPropagation()} className="h-full w-full max-w-2xl overflow-auto bg-white p-6 shadow-2xl dark:bg-slate-950"><h2 className="text-2xl font-black">Import error report</h2><p className="mt-1 text-sm text-slate-500">Batch #{activeBatch?.id}</p><pre className="mt-6 whitespace-pre-wrap rounded-3xl bg-slate-950 p-5 text-xs text-slate-100">{JSON.stringify(errors, null, 2)}</pre></aside></div>}
    </AppShell>
  );
}
