"use client";

import { AppShell } from "@/components/saas/app-shell";
import { EmptyState, Panel, StatusPill } from "@/components/saas/ui";
import { useWorkspace } from "@/components/saas/workspace";
import {
  BatchStatus,
  ImportErrors,
  deleteImportBatch,
  getImportErrors,
  getImportStatus,
  listProfileImportBatches,
  reprocessImportBatch,
  uploadMarketplaceFiles,
} from "@/lib/api";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  FileSpreadsheet,
  RotateCw,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react";
import Image from "next/image";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

const ACCEPTED_IMPORT_FILES = ".csv,.xls,.xlsx,.xlsm";
const ACCEPTED_EXCEL_FILES = ".xls,.xlsx,.xlsm";
const TERMINAL_IMPORT_STATUSES = new Set([
  "completed",
  "completed_with_errors",
  "failed",
]);
const MAX_IMPORT_POLLS = 20;
const PLATFORM_DISPLAY_ORDER = [
  "meesho",
  "amazon",
  "flipkart",
  "myntra",
  "ajio",
  "tatacliq",
  "nykaa",
  "snapdeal",
  "jiomart",
  "blinkit",
  "shopify",
  "zomato",
  "swiggy",
  "firstcry",
  "paytm",
  "custom",
];
const MARKETPLACE_LOGOS: Record<
  string,
  { src: string; width: number; height: number; imageClassName?: string }
> = {
  amazon: { src: "/marketplaces/amazon.png", width: 107, height: 31 },
  flipkart: { src: "/marketplaces/flipkart.png", width: 573, height: 143 },
  meesho: {
    src: "/marketplaces/meesho.png",
    width: 960,
    height: 960,
    imageClassName: "max-h-14",
  },
  myntra: { src: "/marketplaces/myntra.svg", width: 137, height: 60 },
  ajio: { src: "/marketplaces/ajio.svg", width: 200, height: 58 },
  tatacliq: { src: "/marketplaces/tatacliq.jpg", width: 640, height: 360 },
  nykaa: { src: "/marketplaces/nykaa.svg", width: 2500, height: 622 },
  snapdeal: { src: "/marketplaces/snapdeal.png", width: 860, height: 183 },
  jiomart: {
    src: "/marketplaces/jiomart.svg",
    width: 32,
    height: 32,
    imageClassName: "max-h-14",
  },
  blinkit: {
    src: "/marketplaces/blinkit.svg",
    width: 3500,
    height: 3500,
    imageClassName: "max-h-14",
  },
  shopify: { src: "/marketplaces/shopify.png", width: 700, height: 180 },
  zomato: {
    src: "/marketplaces/zomato.png",
    width: 1200,
    height: 1200,
    imageClassName: "max-h-14",
  },
  swiggy: {
    src: "/marketplaces/swiggy.png",
    width: 259,
    height: 194,
    imageClassName: "max-h-14",
  },
  firstcry: {
    src: "/marketplaces/firstcry.png",
    width: 600,
    height: 600,
    imageClassName: "max-h-14",
  },
  paytm: { src: "/marketplaces/paytm.png", width: 607, height: 199 },
};

function platformShortLabel(key: string) {
  const labels: Record<string, string> = {
    amazon: "B2C",
    flipkart: "B2C Sales Report",
    meesho: "B2C",
    myntra: "B2C",
    snapdeal: "B2C",
    jiomart: "B2C",
    blinkit: "Quick Commerce",
    ajio: "Fashion",
    tatacliq: "B2C",
    nykaa: "Beauty",
    shopify: "D2C Orders",
    zomato: "Food Delivery",
    swiggy: "Food Delivery",
    firstcry: "B2C",
    paytm: "B2C",
    custom: "Mapped Excel/CSV",
  };
  return labels[key] || "B2C";
}

function requiredFilesForPlatform(
  platform?: string,
  requiredFiles: string[] = [],
) {
  if (platform === "flipkart") return ["Sales report Excel"];
  return requiredFiles.length ? requiredFiles : ["Excel/CSV report"];
}

function LogoShell({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`grid h-20 w-full place-items-center rounded-xl bg-white px-4 py-3 shadow-sm ring-1 ring-slate-100 ${className}`}
    >
      {children}
    </div>
  );
}

function PlatformLogo({ platform, name }: { platform: string; name: string }) {
  const normalized = platform?.toLowerCase().trim();
  const logo = MARKETPLACE_LOGOS[normalized];

  if (!logo) {
    return (
      <div className="grid h-20 w-full place-items-center rounded-xl bg-slate-100 text-[#1746A2] shadow-sm dark:bg-slate-900">
        <FileSpreadsheet className="size-10" />
        <span className="sr-only">{name}</span>
      </div>
    );
  }

  return (
    <LogoShell>
      <Image
        src={logo.src}
        alt={name}
        width={logo.width}
        height={logo.height}
        unoptimized
        className={`h-auto max-h-12 max-w-full object-contain ${logo.imageClassName || ""}`}
      />
    </LogoShell>
  );
}

function periodLabel(period?: string | null) {
  if (!period || period.length !== 6) return period || "--";
  const month = Number(period.slice(0, 2));
  const year = period.slice(2);
  const label = new Intl.DateTimeFormat("en-IN", { month: "short" }).format(
    new Date(2026, month - 1, 1),
  );
  return `${label} ${year}`;
}

export function ImportsPage() {
  const params = useSearchParams();
  const workspace = useWorkspace();
  const initial = params.get("platform") || "meesho";
  const [platformKey, setPlatformKey] = useState(initial);
  const [files, setFiles] = useState<File[]>([]);
  const [progress, setProgress] = useState("");
  const [fileUploadStatus, setFileUploadStatus] = useState<
    "idle" | "selected" | "uploading" | "success" | "error"
  >("idle");
  const [activeBatch, setActiveBatch] = useState<BatchStatus | null>(null);
  const [errors, setErrors] = useState<ImportErrors | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [reprocessingId, setReprocessingId] = useState<number | null>(null);
  const [profileBatches, setProfileBatches] = useState<BatchStatus[]>([]);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const activeProfileKey = workspace.profile
    ? `${workspace.profile.id}:${workspace.profile.return_period}`
    : "";
  const marketplaces = workspace.marketplaces;

  const resetUploadState = () => {
    setFiles([]);
    setProgress("");
    setFileUploadStatus("idle");
    setActiveBatch(null);
    setErrors(null);
    setDeletingId(null);
    setReprocessingId(null);
  };

  useEffect(() => {
    resetUploadState();
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
  const selected = useMemo(
    () =>
      marketplaces.find((item) => item.key === platformKey) ||
      marketplaces[0] ||
      null,
    [marketplaces, platformKey],
  );
  const platformCards = useMemo(
    () =>
      [...marketplaces].sort((left, right) => {
        const leftIndex = PLATFORM_DISPLAY_ORDER.indexOf(left.key);
        const rightIndex = PLATFORM_DISPLAY_ORDER.indexOf(right.key);
        return (
          (leftIndex === -1 ? 99 : leftIndex) -
            (rightIndex === -1 ? 99 : rightIndex) ||
          left.name.localeCompare(right.name)
        );
      }),
    [marketplaces],
  );
  const canImport = Boolean(selected && selected.status !== "Coming Soon");
  const canStartImport =
    canImport &&
    Boolean(workspace.profile) &&
    files.length > 0 &&
    fileUploadStatus !== "uploading" &&
    fileUploadStatus !== "success";
  const timelineBatches = workspace.batches.length
    ? workspace.batches
    : profileBatches;
  const activePeriodHasBatches = timelineBatches.some(
    (batch) => batch.period === workspace.profile?.return_period,
  );
  const uploadFields = requiredFilesForPlatform(
    selected?.key,
    selected?.required_files || [],
  );
  const fileAccept =
    selected?.key === "flipkart" ? ACCEPTED_EXCEL_FILES : ACCEPTED_IMPORT_FILES;

  function addFiles(index: number, selectedFiles: File[]) {
    if (!selectedFiles.length) return;
    setFiles((current) => {
      const next = [...current];
      next.splice(index, 1, ...selectedFiles);
      return next.filter(Boolean);
    });
    setFileUploadStatus("selected");
  }

  function removeFile(index: number) {
    setFiles((current) =>
      current.filter((_, currentIndex) => currentIndex !== index),
    );
  }

  async function startImport() {
    if (!canImport) {
      setProgress(
        selected
          ? `${selected.name} parser is not enabled yet.`
          : "Marketplace catalog is still loading.",
      );
      return;
    }
    if (!selected || !workspace.token || !workspace.profile || !files.length) {
      setProgress("Choose files before starting import.");
      return;
    }
    setErrors(null);
    setFileUploadStatus("uploading");
    try {
      setProgress("Uploading files securely...");
      const batch = await uploadMarketplaceFiles(
        workspace.token,
        workspace.profile,
        selected.key,
        files,
      );
      setActiveBatch(batch);
      setProgress(`Batch ${batch.id} queued. Parser is reading files...`);
      let finalStatus = batch;
      for (let index = 0; index < MAX_IMPORT_POLLS; index += 1) {
        await new Promise((resolve) => setTimeout(resolve, 900));
        const status = await getImportStatus(workspace.token, batch.id);
        finalStatus = status;
        setActiveBatch(status);
        setProgress(
          `Status: ${status.status}. Parsed ${status.parsed_rows}, errors ${status.error_rows}.`,
        );
        if (TERMINAL_IMPORT_STATUSES.has(status.status)) break;
      }
      const hasErrors = finalStatus.error_rows > 0;
      if (hasErrors) {
        setErrors(await getImportErrors(workspace.token, batch.id));
        setFileUploadStatus("error");
      } else {
        setFileUploadStatus("success");
        setProgress(`Batch ${batch.id} uploaded successfully.`);
      }
      await workspace.refresh();
      if (workspace.profile)
        setProfileBatches(
          await listProfileImportBatches(workspace.token, workspace.profile.id),
        );
    } catch (exc) {
      setFileUploadStatus("error");
      setProgress(exc instanceof Error ? exc.message : "Import failed.");
    }
  }

  async function openErrors(batchId: number) {
    if (!workspace.token) return;
    setProgress("");
    try {
      setActiveBatch(
        workspace.batches.find((batch) => batch.id === batchId) || null,
      );
      setErrors(await getImportErrors(workspace.token, batchId));
    } catch (exc) {
      setProgress(
        exc instanceof Error ? exc.message : "Could not load import errors.",
      );
    }
  }

  async function removeBatch(batch: BatchStatus) {
    if (!workspace.token) return;
    const confirmed = window.confirm(
      `Delete ${batch.platform} batch #${batch.id}? Imported rows from this batch will also be removed.`,
    );
    if (!confirmed) return;
    setDeletingId(batch.id);
    setProgress("");
    try {
      await deleteImportBatch(workspace.token, batch.id);
      if (activeBatch?.id === batch.id) setActiveBatch(null);
      setErrors(null);
      await workspace.refresh();
      if (workspace.profile)
        setProfileBatches(
          await listProfileImportBatches(workspace.token, workspace.profile.id),
        );
      setProgress(`Batch #${batch.id} deleted.`);
    } catch (exc) {
      setProgress(
        exc instanceof Error ? exc.message : "Could not delete import batch.",
      );
    } finally {
      setDeletingId(null);
    }
  }

  async function reprocessBatch(batch: BatchStatus) {
    if (!workspace.token) return;
    setReprocessingId(batch.id);
    setErrors(null);
    setProgress(
      `Reprocessing ${batch.platform} batch #${batch.id} with current parser...`,
    );
    try {
      const status = await reprocessImportBatch(workspace.token, batch.id);
      setActiveBatch(status);
      if (status.error_rows)
        setErrors(await getImportErrors(workspace.token, batch.id));
      else setErrors(null);
      await workspace.refresh();
      if (workspace.profile)
        setProfileBatches(
          await listProfileImportBatches(workspace.token, workspace.profile.id),
        );
      setProgress(
        `Batch #${batch.id} reprocessed. Parsed ${status.parsed_rows}, errors ${status.error_rows}.`,
      );
    } catch (exc) {
      setProgress(
        exc instanceof Error
          ? exc.message
          : "Could not reprocess import batch.",
      );
    } finally {
      setReprocessingId(null);
    }
  }

  return (
    <AppShell
      requiresSubscription
      requiredPlan="online_seller"
      token={workspace.token}
      user={workspace.user}
      productName="GST Online Seller"
      title="Marketplace Upload"
      subtitle="Select profile, platform, required files and track parser progress from upload to normalized transactions."
      profile={workspace.profile}
      profiles={workspace.profiles}
      loading={workspace.loading}
      error={workspace.error}
      onRetry={() => workspace.refresh()}
      onProfileChange={(profile) => {
        workspace.setProfile(profile);
        workspace.refresh(profile);
      }}
    >
      {!workspace.token ? (
        <EmptyState
          title="Login required"
          body="Imports are connected to secure backend APIs. Login before uploading marketplace files."
        />
      ) : !workspace.profile ? (
        <EmptyState
          title="Create GST profile first"
          body="Uploads require a GST profile and return period so normalized rows are stored against the correct GSTIN."
        />
      ) : null}
      <div className="grid gap-6">
        <Panel
          title="Upload workspace"
          subtitle="Parser catalog, required files and platform status are loaded from the backend."
        >
          <div className="grid gap-4 md:grid-cols-2">
            <label className="text-sm font-bold">
              GST profile
              <select className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 dark:border-white/10 dark:bg-slate-900">
                <option>{workspace.profile?.gstin || "No GSTIN"}</option>
              </select>
            </label>
            <label className="text-sm font-bold">
              Filing period
              <input
                value={workspace.profile?.return_period || ""}
                readOnly
                className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 dark:border-white/10 dark:bg-slate-900"
              />
            </label>
            <div className="md:col-span-2">
              <div className="mb-4 flex items-center gap-3 text-sm font-bold text-slate-500">
                <span className="h-px flex-1 bg-slate-200 dark:bg-white/10" />
                <span>Famous Platforms</span>
                <span className="h-px flex-1 bg-slate-200 dark:bg-white/10" />
              </div>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {platformCards.map((item) => {
                  const active = item.key === selected?.key;
                  return (
                    <button
                      key={item.key}
                      type="button"
                      onClick={() => {
                        setPlatformKey(item.key);
                        setFiles([]);
                        setProgress("");
                        setActiveBatch(null);
                        setErrors(null);
                        setUploadDialogOpen(true);
                      }}
                      className={`platform-card-shadow flex min-h-52 flex-col items-center justify-between rounded-lg border bg-white p-4 text-center transition hover:-translate-y-0.5 hover:shadow-xl dark:bg-slate-950 ${active ? "border-[#1746A2] ring-2 ring-[#1746A2]/20" : "border-slate-200 dark:border-white/10"}`}
                    >
                      <div className="grid justify-items-center">
                        <PlatformLogo platform={item.key} name={item.name} />
                        <h3 className="mt-3 text-lg font-black text-slate-950 dark:text-white">
                          {item.name}
                        </h3>
                        <p className="mt-0.5 text-sm font-semibold text-slate-500">
                          {platformShortLabel(item.key)}
                        </p>
                      </div>
                      <span
                        className={`mt-5 rounded-full px-5 py-2 text-xs font-black uppercase tracking-wide ${active ? "bg-[#1746A2] text-white" : "bg-slate-100 text-slate-900 dark:bg-white/10 dark:text-white"}`}
                      >
                        Import Data
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </Panel>
      </div>
      {uploadDialogOpen && (
        <div
          className="fixed inset-0 z-50 grid place-items-center bg-slate-950/50 p-4"
          onClick={() => setUploadDialogOpen(false)}
        >
          <div
            onClick={(event) => event.stopPropagation()}
            className="max-h-[92vh] w-full max-w-3xl overflow-auto rounded-2xl bg-white p-5 shadow-2xl dark:bg-slate-950 sm:p-6"
          >
            <div className="mb-5 flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="text-xs font-black uppercase tracking-wide text-slate-400">
                  Upload marketplace data
                </p>
                <h2 className="mt-1 text-xl font-black text-slate-950 dark:text-white">
                  {selected?.name || "Marketplace"} import
                </h2>
              </div>
              <button
                type="button"
                onClick={() => {
                  setUploadDialogOpen(false);
                  resetUploadState();
                }}
                className="grid size-10 shrink-0 place-items-center rounded-xl bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-white/10 dark:text-white"
              >
                <X className="size-5" />
              </button>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5 dark:border-white/10 dark:bg-white/5">
              {selected ? (
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex min-w-0 items-start gap-3">
                    <div className="size-20 shrink-0">
                      <PlatformLogo
                        platform={selected.key}
                        name={selected.name}
                      />
                    </div>
                    <div className="min-w-0">
                      <h3 className="font-black">{selected.name}</h3>
                      <p className="text-sm text-slate-500">{selected.guide}</p>
                      <p className="mt-1 break-words text-xs font-bold text-slate-400">
                        Parser: {selected.parser}
                      </p>
                    </div>
                  </div>
                  <StatusPill status={selected.status} />
                </div>
              ) : (
                <EmptyState
                  title="Marketplace catalog not loaded"
                  body="Backend marketplace endpoint did not return parser data yet."
                />
              )}
              {selected && !canImport && (
                <div className="mt-4 rounded-2xl bg-amber-50 p-4 text-sm font-bold text-amber-800">
                  {selected.name} parser is not enabled by the backend yet.
                </div>
              )}
              <div className="mt-4 grid gap-3">
                {uploadFields.map((file, index) => {
                  const uploadedFile = files[index];

                  return (
                    <label
                      key={file}
                      className={`flex min-h-20 flex-col gap-3 rounded-2xl border-2 border-dashed p-4 text-sm transition sm:flex-row sm:items-center ${
                        uploadedFile
                          ? "border-emerald-400 bg-emerald-50/70 dark:border-emerald-500/50 dark:bg-emerald-950/20"
                          : "border-slate-300 bg-white dark:border-white/10 dark:bg-slate-900"
                      } ${
                        canImport
                          ? "cursor-pointer hover:border-[#1746A2]"
                          : "cursor-not-allowed opacity-60"
                      }`}
                    >
                      {uploadedFile ? (
                        <CheckCircle2 className="size-6 shrink-0 text-emerald-600" />
                      ) : (
                        <FileSpreadsheet className="size-6 shrink-0 text-emerald-600" />
                      )}

                      <div className="min-w-0 flex-1">
                        <p className="font-bold">
                          {uploadedFile ? "File uploaded" : file}
                        </p>

                        {uploadedFile ? (
                          <p className="mt-1 truncate text-xs font-semibold text-emerald-700">
                            ✓ {uploadedFile.name}
                          </p>
                        ) : (
                          <p className="mt-1 text-xs text-slate-400">
                            Click to choose your file
                          </p>
                        )}
                      </div>

                      {!uploadedFile && (
                        <span className="rounded-xl bg-[#10244d] px-4 py-2 text-xs font-bold text-white">
                          Choose file
                        </span>
                      )}

                      {uploadedFile && (
                        <span className="rounded-xl bg-emerald-600 px-4 py-2 text-xs font-bold text-white">
                          Selected
                        </span>
                      )}

                      <input
                        type="file"
                        multiple={selected?.key !== "flipkart"}
                        disabled={!canImport}
                        className="hidden"
                        onChange={(event) => {
                          const selectedFiles = Array.from(
                            event.target.files || [],
                          );

                          addFiles(index, selectedFiles);
                          event.currentTarget.value = "";
                        }}
                        accept={fileAccept}
                      />
                    </label>
                  );
                })}
              </div>
              {(fileUploadStatus !== "idle" || files.length > 0) && (
                <div className="mt-3 flex flex-wrap items-center gap-2 text-sm font-semibold">
                  <span
                    className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-black ${fileUploadStatus === "success" ? "bg-emerald-100 text-emerald-800" : fileUploadStatus === "uploading" ? "bg-slate-100 text-slate-900" : fileUploadStatus === "error" ? "bg-rose-100 text-rose-800" : "bg-slate-100 text-slate-900"}`}
                  >
                    {fileUploadStatus === "success" ? (
                      <CheckCircle2 className="size-4 text-emerald-700" />
                    ) : null}
                    {fileUploadStatus === "success"
                      ? "Files uploaded successfully"
                      : fileUploadStatus === "uploading"
                        ? "Uploading files..."
                        : fileUploadStatus === "error"
                          ? "Upload incomplete. Check progress."
                          : files.length
                            ? "Files selected"
                            : "Choose files to upload"}
                  </span>
                </div>
              )}
              {files.length ? (
                <div className="mt-4 space-y-2 rounded-2xl bg-white p-4 text-xs font-semibold text-slate-600 dark:bg-slate-900 dark:text-slate-300">
                  {files.map((file, index) => (
                    <div
                      key={`${file.name}-${file.lastModified}-${index}`}
                      className="flex items-center justify-between gap-3 rounded-xl bg-slate-50 px-3 py-2 dark:bg-white/5"
                    >
                      <span className="min-w-0 truncate">{file.name}</span>
                      <button
                        type="button"
                        onClick={() => removeFile(index)}
                        className="rounded-lg px-2 py-1 text-rose-700 hover:bg-rose-50"
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
              ) : null}
              <button
                onClick={startImport}
                disabled={!canStartImport}
                className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
              >
                <UploadCloud className="size-4" />{" "}
                {canImport ? "Start import" : "Coming soon"}{" "}
                <ArrowRight className="size-4" />
              </button>
              {progress && (
                <div className="mt-4 rounded-2xl bg-emerald-50 p-4 text-sm font-semibold text-emerald-700">
                  {progress}
                </div>
              )}
              {activeBatch && (
                <div className="mt-4 grid gap-3 rounded-2xl bg-white p-4 text-sm dark:bg-slate-900 md:grid-cols-3">
                  <b>Batch #{activeBatch.id}</b>
                  <span>{activeBatch.parsed_rows} parsed</span>
                  <span>{activeBatch.error_rows} errors</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
      <div className="mt-6">
        <Panel
          title="Import status timeline"
          subtitle="Recent parser jobs and error counts."
        >
          {workspace.profile &&
          !workspace.batches.length &&
          !activePeriodHasBatches &&
          timelineBatches.length ? (
            <div className="mb-4 rounded-2xl bg-amber-50 p-4 text-sm font-bold text-amber-800">
              No imports found for active return period{" "}
              {periodLabel(workspace.profile.return_period)}. Showing imports
              from other periods.
            </div>
          ) : null}
          {timelineBatches.length ? (
            <div className="space-y-3">
              {timelineBatches.map((batch) => {
                const busy = deletingId === batch.id;
                const locked = ["queued", "processing"].includes(batch.status);
                return (
                  <div
                    key={batch.id}
                    className="grid gap-3 rounded-2xl bg-slate-50 p-4 text-sm dark:bg-white/5 md:grid-cols-[1fr_auto_auto_auto] xl:grid-cols-[1fr_auto_auto_auto_auto_auto_auto]"
                  >
                    <b className="capitalize">{batch.platform}</b>
                    <span>
                      {periodLabel(
                        batch.period || workspace.profile?.return_period,
                      )}
                    </span>
                    <span>{batch.parsed_rows} parsed</span>
                    <span>{batch.error_rows} errors</span>
                    <StatusPill status={batch.status} />
                    {batch.error_rows ? (
                      <button
                        onClick={() => openErrors(batch.id)}
                        className="inline-flex items-center gap-1 rounded-xl bg-rose-50 px-3 py-2 text-xs font-bold text-rose-700"
                      >
                        <AlertTriangle className="size-3" /> Errors
                      </button>
                    ) : (
                      <span />
                    )}
                    <button
                      onClick={() => reprocessBatch(batch)}
                      disabled={reprocessingId === batch.id || locked}
                      className="inline-flex items-center gap-1 rounded-xl bg-white px-3 py-2 text-xs font-bold text-blue-700 shadow-sm ring-1 ring-blue-100 disabled:cursor-not-allowed disabled:opacity-45 dark:bg-slate-900 dark:ring-white/10"
                    >
                      <RotateCw
                        className={`size-3 ${reprocessingId === batch.id ? "animate-spin" : ""}`}
                      />{" "}
                      {reprocessingId === batch.id
                        ? "Reprocessing"
                        : "Reprocess"}
                    </button>
                    <button
                      onClick={() => removeBatch(batch)}
                      disabled={busy || locked}
                      className="inline-flex items-center gap-1 rounded-xl bg-white px-3 py-2 text-xs font-bold text-rose-700 shadow-sm ring-1 ring-rose-100 disabled:cursor-not-allowed disabled:opacity-45 dark:bg-slate-900 dark:ring-white/10"
                    >
                      <Trash2 className="size-3" />{" "}
                      {busy ? "Deleting" : "Delete"}
                    </button>
                  </div>
                );
              })}
            </div>
          ) : (
            <EmptyState
              title="No import batches"
              body="Start your first guided import to see progress here."
            />
          )}
        </Panel>
      </div>
      {errors && (
        <div
          className="fixed inset-0 z-50 flex justify-end bg-slate-950/40"
          onClick={() => setErrors(null)}
        >
          <aside
            onClick={(event) => event.stopPropagation()}
            className="h-full w-full max-w-2xl overflow-auto bg-white p-6 shadow-2xl dark:bg-slate-950"
          >
            <h2 className="text-2xl font-black">Import error report</h2>
            <p className="mt-1 text-sm text-slate-500">
              Batch #{activeBatch?.id}
            </p>
            <pre className="mt-6 whitespace-pre-wrap rounded-3xl bg-slate-950 p-5 text-xs text-slate-100">
              {JSON.stringify(errors, null, 2)}
            </pre>
          </aside>
        </div>
      )}
    </AppShell>
  );
}
