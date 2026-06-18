"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AlertTriangle, ArrowRight, FileSpreadsheet, RotateCw, Trash2, UploadCloud } from "lucide-react";
import { AppShell } from "@/components/saas/app-shell";
import { EmptyState, Panel, StatusPill } from "@/components/saas/ui";
import { useWorkspace } from "@/components/saas/workspace";
import { marketplaceIconFor } from "@/lib/marketplaces";
import { BatchStatus, ImportErrors, deleteImportBatch, getImportErrors, getImportStatus, listProfileImportBatches, reprocessImportBatch, uploadMarketplaceFiles } from "@/lib/api";

const ACCEPTED_IMPORT_FILES = ".csv,.xls,.xlsx,.xlsm";
const TERMINAL_IMPORT_STATUSES = new Set(["completed", "completed_with_errors", "failed"]);
const MAX_IMPORT_POLLS = 20;

function periodLabel(period?: string | null) {
  if (!period || period.length !== 6) return period || "--";
  const month = Number(period.slice(0, 2));
  const year = period.slice(2);
  const label = new Intl.DateTimeFormat("en-IN", { month: "short" }).format(new Date(2026, month - 1, 1));
  return `${label} ${year}`;
}

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
  const [reprocessingId, setReprocessingId] = useState<number | null>(null);
  const [profileBatches, setProfileBatches] = useState<BatchStatus[]>([]);
  const activeProfileKey = workspace.profile ? `${workspace.profile.id}:${workspace.profile.return_period}` : "";
  const marketplaces = workspace.marketplaces;
  useEffect(() => {
    setFiles([]);
    setProgress("");
    setActiveBatch(null);
    setErrors(null);
    setDeletingId(null);
    setReprocessingId(null);
  }, [activeProfileKey]);
  useEffect(() => {
    let cancelled = false;
    if (!workspace.token || !workspace.profile) {
      setProfileBatches([]);
      return;
    }
    listProfileImportBatches(workspace.token, workspace.profile.id)
      .then((batches) => {
        if (!cancelled) setProfileBatches(batches);
      })
      .catch(() => {
        if (!cancelled) setProfileBatches([]);
      });
    return () => {
      cancelled = true;
    };
  }, [workspace.token, workspace.profile]);
  useEffect(() => {
    if (!marketplaces.length) return;
    if (!marketplaces.some((item) => item.key === platformKey)) {
      setPlatformKey(marketplaces[0].key);
    }
  }, [marketplaces, platformKey]);
  const selected = useMemo(() => marketplaces.find((item) => item.key === platformKey) || marketplaces[0] || null, [marketplaces, platformKey]);
  const SelectedIcon = selected ? marketplaceIconFor(selected.key) : FileSpreadsheet;
  const canImport = Boolean(selected && selected.status !== "Coming Soon");
  const canStartImport = canImport && Boolean(workspace.profile) && files.length > 0;
  const timelineBatches = workspace.batches.length ? workspace.batches : profileBatches;
  const activePeriodHasBatches = timelineBatches.some((batch) => batch.period === workspace.profile?.return_period);
  const importSteps = [
    { label: workspace.profile ? `Profile ${workspace.profile.gstin}` : "GST profile missing", done: Boolean(workspace.profile) },
    { label: selected ? `${selected.name} parser ${selected.status}` : "Parser catalog loading", done: Boolean(selected) },
    { label: `${files.length} files selected`, done: files.length > 0 },
    { label: activeBatch ? `Batch #${activeBatch.id} ${activeBatch.status}` : "No active batch", done: Boolean(activeBatch) },
    { label: activeBatch ? `${activeBatch.parsed_rows} parsed rows` : "Parser not started", done: Boolean(activeBatch?.parsed_rows) },
    { label: activeBatch ? `${activeBatch.error_rows} parser errors` : "Error report pending", done: Boolean(activeBatch && activeBatch.status !== "queued" && activeBatch.status !== "processing") },
  ];

  function addFiles(index: number, selectedFiles: File[]) {
    if (!selectedFiles.length) return;
    setFiles((current) => {
      const next = [...current];
      next.splice(index, 1, ...selectedFiles);
      return next.filter(Boolean);
    });
  }

  function removeFile(index: number) {
    setFiles((current) => current.filter((_, currentIndex) => currentIndex !== index));
  }

  async function startImport() {
    if (!canImport) {
      setProgress(selected ? `${selected.name} parser is not enabled yet.` : "Marketplace catalog is still loading.");
      return;
    }
    if (!selected || !workspace.token || !workspace.profile || !files.length) {
      setProgress("Choose files before starting import.");
      return;
    }
    setErrors(null);
    try {
      setProgress("Uploading files securely...");
      const batch = await uploadMarketplaceFiles(workspace.token, workspace.profile, selected.key, files);
      setActiveBatch(batch);
      setProgress(`Batch ${batch.id} queued. Parser is reading files...`);
      let finalStatus = batch;
      for (let index = 0; index < MAX_IMPORT_POLLS; index += 1) {
        await new Promise((resolve) => setTimeout(resolve, 900));
        const status = await getImportStatus(workspace.token, batch.id);
        finalStatus = status;
        setActiveBatch(status);
        setProgress(`Status: ${status.status}. Parsed ${status.parsed_rows}, errors ${status.error_rows}.`);
        if (TERMINAL_IMPORT_STATUSES.has(status.status)) break;
      }
      if (finalStatus.error_rows) {
        setErrors(await getImportErrors(workspace.token, batch.id));
      }
      await workspace.refresh();
      if (workspace.profile) setProfileBatches(await listProfileImportBatches(workspace.token, workspace.profile.id));
    } catch (exc) {
      setProgress(exc instanceof Error ? exc.message : "Import failed.");
    }
  }

  async function openErrors(batchId: number) {
    if (!workspace.token) return;
    setProgress("");
    try {
      setActiveBatch(workspace.batches.find((batch) => batch.id === batchId) || null);
      setErrors(await getImportErrors(workspace.token, batchId));
    } catch (exc) {
      setProgress(exc instanceof Error ? exc.message : "Could not load import errors.");
    }
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
      if (workspace.profile) setProfileBatches(await listProfileImportBatches(workspace.token, workspace.profile.id));
      setProgress(`Batch #${batch.id} deleted.`);
    } catch (exc) {
      setProgress(exc instanceof Error ? exc.message : "Could not delete import batch.");
    } finally {
      setDeletingId(null);
    }
  }

  async function reprocessBatch(batch: BatchStatus) {
    if (!workspace.token) return;
    setReprocessingId(batch.id);
    setErrors(null);
    setProgress(`Reprocessing ${batch.platform} batch #${batch.id} with current parser...`);
    try {
      const status = await reprocessImportBatch(workspace.token, batch.id);
      setActiveBatch(status);
      if (status.error_rows) setErrors(await getImportErrors(workspace.token, batch.id));
      else setErrors(null);
      await workspace.refresh();
      if (workspace.profile) setProfileBatches(await listProfileImportBatches(workspace.token, workspace.profile.id));
      setProgress(`Batch #${batch.id} reprocessed. Parsed ${status.parsed_rows}, errors ${status.error_rows}.`);
    } catch (exc) {
      setProgress(exc instanceof Error ? exc.message : "Could not reprocess import batch.");
    } finally {
      setReprocessingId(null);
    }
  }

  return (
    <AppShell requiresSubscription requiredPlan="online_seller" token={workspace.token} user={workspace.user} productName="GST Online Seller" title="Marketplace Upload" subtitle="Select profile, platform, required files and track parser progress from upload to normalized transactions." profile={workspace.profile} profiles={workspace.profiles} loading={workspace.loading} error={workspace.error} onRetry={() => workspace.refresh()} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }}>
      {!workspace.token ? <EmptyState title="Login required" body="Imports are connected to secure backend APIs. Login before uploading marketplace files." /> : !workspace.profile ? <EmptyState title="Create GST profile first" body="Uploads require a GST profile and return period so normalized rows are stored against the correct GSTIN." /> : null}
      <div className="grid gap-6 xl:grid-cols-[0.8fr_1.2fr]">
        <Panel title="Import steps" subtitle="A production upload flow with profile, period and parser feedback.">
          <div className="space-y-3">
            {importSteps.map((step, index) => <div key={step.label} className={`flex items-center gap-3 rounded-2xl p-3 text-sm font-semibold ${step.done ? "bg-blue-50 text-blue-700" : "bg-slate-50 text-slate-600 dark:bg-white/5"}`}><span className="grid size-7 place-items-center rounded-full bg-white text-xs shadow-sm">{index + 1}</span>{step.label}</div>)}
          </div>
        </Panel>
        <Panel title="Upload workspace" subtitle="Parser catalog, required files and platform status are loaded from the backend.">
          <div className="grid gap-4 md:grid-cols-2">
            <label className="text-sm font-bold">GST profile<select className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 dark:border-white/10 dark:bg-slate-900"><option>{workspace.profile?.gstin || "No GSTIN"}</option></select></label>
            <label className="text-sm font-bold">Filing period<input value={workspace.profile?.return_period || ""} readOnly className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 dark:border-white/10 dark:bg-slate-900" /></label>
            <label className="text-sm font-bold md:col-span-2">Platform<select value={selected?.key || ""} disabled={!marketplaces.length} onChange={(event) => { setPlatformKey(event.target.value); setFiles([]); setProgress(""); }} className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 dark:border-white/10 dark:bg-slate-900">{marketplaces.map((item) => <option key={item.key} value={item.key}>{item.name} - {item.status}</option>)}</select></label>
          </div>
          <div className="mt-5 rounded-3xl border border-slate-200 bg-slate-50 p-5 dark:border-white/10 dark:bg-white/5">
            {selected ? <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"><div className="flex min-w-0 items-start gap-3"><div className="grid size-11 shrink-0 place-items-center rounded-xl bg-white text-[#1746A2] shadow-sm dark:bg-slate-900"><SelectedIcon className="size-5" /></div><div className="min-w-0"><h3 className="font-black">{selected.name}</h3><p className="text-sm text-slate-500">{selected.guide}</p><p className="mt-1 break-words text-xs font-bold text-slate-400">Parser: {selected.parser}</p></div></div><StatusPill status={selected.status} /></div> : <EmptyState title="Marketplace catalog not loaded" body="Backend marketplace endpoint did not return parser data yet." />}
            {selected && !canImport && <div className="mt-4 rounded-2xl bg-amber-50 p-4 text-sm font-bold text-amber-800">{selected.name} parser is not enabled by the backend yet.</div>}
            <div className="mt-4 grid gap-3">
              {(selected?.required_files || []).map((file, index) => <label key={file} className={`flex min-h-16 flex-col gap-3 rounded-2xl border border-dashed border-slate-300 bg-white p-4 text-sm dark:border-white/10 dark:bg-slate-900 sm:flex-row sm:items-center ${canImport ? "cursor-pointer" : "cursor-not-allowed opacity-60"}`}><FileSpreadsheet className="size-5 shrink-0 text-emerald-600" /><span className="font-bold sm:w-44">{file}</span><input type="file" multiple disabled={!canImport} className="w-full min-w-0 text-xs sm:flex-1" onChange={(event) => {
                const selectedFiles = Array.from(event.target.files || []);
                addFiles(index, selectedFiles);
                event.currentTarget.value = "";
              }} accept={ACCEPTED_IMPORT_FILES} /></label>)}
            </div>
            {files.length ? <div className="mt-4 space-y-2 rounded-2xl bg-white p-4 text-xs font-semibold text-slate-600 dark:bg-slate-900 dark:text-slate-300">{files.map((file, index) => <div key={`${file.name}-${file.lastModified}-${index}`} className="flex items-center justify-between gap-3 rounded-xl bg-slate-50 px-3 py-2 dark:bg-white/5"><span className="min-w-0 truncate">{file.name}</span><button type="button" onClick={() => removeFile(index)} className="rounded-lg px-2 py-1 text-rose-700 hover:bg-rose-50">Remove</button></div>)}</div> : null}
            <button onClick={startImport} disabled={!canStartImport} className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"><UploadCloud className="size-4" /> {canImport ? "Start import" : "Coming soon"} <ArrowRight className="size-4" /></button>
            {progress && <div className="mt-4 rounded-2xl bg-emerald-50 p-4 text-sm font-semibold text-emerald-700">{progress}</div>}
            {activeBatch && <div className="mt-4 grid gap-3 rounded-2xl bg-white p-4 text-sm dark:bg-slate-900 md:grid-cols-3"><b>Batch #{activeBatch.id}</b><span>{activeBatch.parsed_rows} parsed</span><span>{activeBatch.error_rows} errors</span></div>}
          </div>
        </Panel>
      </div>
      <div className="mt-6">
        <Panel title="Import status timeline" subtitle="Recent parser jobs and error counts.">
          {workspace.profile && !workspace.batches.length && !activePeriodHasBatches && timelineBatches.length ? <div className="mb-4 rounded-2xl bg-amber-50 p-4 text-sm font-bold text-amber-800">No imports found for active return period {periodLabel(workspace.profile.return_period)}. Showing imports from other periods.</div> : null}
          {timelineBatches.length ? <div className="space-y-3">{timelineBatches.map((batch) => {
            const busy = deletingId === batch.id;
            const locked = ["queued", "processing"].includes(batch.status);
            return <div key={batch.id} className="grid gap-3 rounded-2xl bg-slate-50 p-4 text-sm dark:bg-white/5 md:grid-cols-[1fr_auto_auto_auto] xl:grid-cols-[1fr_auto_auto_auto_auto_auto_auto]">
              <b className="capitalize">{batch.platform}</b>
              <span>{periodLabel(batch.period || workspace.profile?.return_period)}</span>
              <span>{batch.parsed_rows} parsed</span>
              <span>{batch.error_rows} errors</span>
              <StatusPill status={batch.status} />
              {batch.error_rows ? <button onClick={() => openErrors(batch.id)} className="inline-flex items-center gap-1 rounded-xl bg-rose-50 px-3 py-2 text-xs font-bold text-rose-700"><AlertTriangle className="size-3" /> Errors</button> : <span />}
              <button onClick={() => reprocessBatch(batch)} disabled={reprocessingId === batch.id || locked} className="inline-flex items-center gap-1 rounded-xl bg-white px-3 py-2 text-xs font-bold text-blue-700 shadow-sm ring-1 ring-blue-100 disabled:cursor-not-allowed disabled:opacity-45 dark:bg-slate-900 dark:ring-white/10">
                <RotateCw className={`size-3 ${reprocessingId === batch.id ? "animate-spin" : ""}`} /> {reprocessingId === batch.id ? "Reprocessing" : "Reprocess"}
              </button>
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
