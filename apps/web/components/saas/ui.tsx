"use client";

import { AlertCircle, CheckCircle2, Loader2, RefreshCw, WifiOff } from "lucide-react";

export function StatCard({ label, value, detail, tone = "blue" }: { label: string; value: string; detail?: string; tone?: "blue" | "green" | "saffron" | "red" }) {
  const tones = {
    blue: "bg-blue-600",
    green: "bg-emerald-600",
    saffron: "bg-orange-500",
    red: "bg-rose-600"
  };
  return (
    <div className="surface rounded-2xl p-4 transition hover:-translate-y-0.5 sm:p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <p className="text-xs font-bold uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</p>
        <span className={`h-2.5 w-2.5 rounded-full ${tones[tone]}`} />
      </div>
      <p className="break-words text-xl font-black tracking-tight text-slate-950 dark:text-white sm:text-2xl">{value}</p>
      {detail && <p className="mt-2 text-xs font-medium leading-5 text-slate-500 dark:text-slate-400">{detail}</p>}
    </div>
  );
}

export function Panel({ title, subtitle, action, children }: { title: string; subtitle?: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="surface rounded-2xl p-4 sm:p-5">
      <div className="mb-5 flex flex-col items-stretch gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h2 className="text-base font-black tracking-tight text-slate-950 dark:text-white">{title}</h2>
          {subtitle && <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-500 dark:text-slate-400">{subtitle}</p>}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      {children}
    </section>
  );
}

export function EmptyState({ title, body, action }: { title: string; body: string; action?: React.ReactNode }) {
  return (
    <div className="grid min-h-56 place-items-center rounded-2xl border border-dashed border-slate-300 bg-slate-50/80 p-8 text-center dark:border-white/10 dark:bg-white/5">
      <div>
        <div className="mx-auto grid size-11 place-items-center rounded-xl bg-white shadow-sm ring-1 ring-slate-200 dark:bg-slate-900 dark:ring-white/10"><AlertCircle className="size-5 text-saffron" /></div>
        <h3 className="mt-4 text-base font-black">{title}</h3>
        <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">{body}</p>
        {action && <div className="mt-5">{action}</div>}
      </div>
    </div>
  );
}

export function PageLoader({ title = "Loading workspace", body = "Syncing your GST Bharat data securely." }: { title?: string; body?: string }) {
  return (
    <div className="grid min-h-[70vh] place-items-center px-5">
      <div className="w-full max-w-xl rounded-2xl border border-slate-200/80 bg-white p-6 text-center shadow-[0_18px_44px_rgba(15,23,42,0.08)] dark:border-white/10 dark:bg-slate-950">
        <div className="mx-auto grid size-14 place-items-center rounded-2xl bg-[#12284f] text-white shadow-sm">
          <Loader2 className="size-6 animate-spin" />
        </div>
        <h1 className="mt-5 text-xl font-black tracking-tight text-slate-950 dark:text-white">{title}</h1>
        <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-slate-500 dark:text-slate-400">{body}</p>
        <div className="mt-6 grid gap-3">
          <div className="h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-white/10">
            <div className="h-full w-1/2 animate-[loader-bar_1.25s_ease-in-out_infinite] rounded-full bg-gradient-to-r from-[#1746A2] via-[#3E7DD8] to-[#F58220]" />
          </div>
          <div className="grid gap-2 sm:grid-cols-3">
            <div className="h-14 animate-pulse rounded-xl bg-slate-100 dark:bg-white/10" />
            <div className="h-14 animate-pulse rounded-xl bg-slate-100 dark:bg-white/10 [animation-delay:120ms]" />
            <div className="h-14 animate-pulse rounded-xl bg-slate-100 dark:bg-white/10 [animation-delay:240ms]" />
          </div>
        </div>
      </div>
    </div>
  );
}

export function InlineLoader({ title = "Loading", body = "Fetching the latest data." }: { title?: string; body?: string }) {
  return (
    <div className="grid min-h-56 place-items-center rounded-2xl border border-slate-200/80 bg-white/75 p-8 text-center dark:border-white/10 dark:bg-white/[0.04]">
      <div>
        <div className="mx-auto grid size-11 place-items-center rounded-xl bg-[#12284f] text-white shadow-sm">
          <Loader2 className="size-5 animate-spin" />
        </div>
        <h3 className="mt-4 text-base font-black text-slate-950 dark:text-white">{title}</h3>
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500 dark:text-slate-400">{body}</p>
      </div>
    </div>
  );
}

export function ErrorState({ title = "Could not load data", body, actionLabel = "Retry", onRetry }: { title?: string; body: string; actionLabel?: string; onRetry?: () => void }) {
  return (
    <div className="grid min-h-56 place-items-center rounded-2xl border border-rose-200 bg-rose-50/80 p-8 text-center text-rose-900 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-100">
      <div>
        <div className="mx-auto grid size-11 place-items-center rounded-xl bg-white shadow-sm ring-1 ring-rose-200 dark:bg-slate-950 dark:ring-rose-500/30">
          <WifiOff className="size-5 text-rose-600 dark:text-rose-300" />
        </div>
        <h3 className="mt-4 text-base font-black">{title}</h3>
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-rose-700 dark:text-rose-200">{body}</p>
        {onRetry ? (
          <button onClick={onRetry} className="mt-5 inline-flex items-center justify-center gap-2 rounded-xl bg-rose-600 px-4 py-2.5 text-sm font-bold text-white shadow-sm transition hover:bg-rose-700">
            <RefreshCw className="size-4" />
            {actionLabel}
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function SkeletonGrid() {
  return <div className="grid gap-4 md:grid-cols-4">{Array.from({ length: 4 }).map((_, index) => <div key={index} className="h-32 animate-pulse rounded-2xl bg-slate-200/70 dark:bg-white/10" />)}</div>;
}

export function StatusPill({ status }: { status: string }) {
  const ok = ["completed", "generated", "downloaded", "Active"].includes(status);
  const warn = ["queued", "processing", "Beta"].includes(status);
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-bold ${ok ? "border-emerald-200 bg-emerald-50 text-emerald-700" : warn ? "border-amber-200 bg-amber-50 text-amber-700" : "border-slate-200 bg-slate-100 text-slate-600 dark:border-white/10 dark:bg-white/10 dark:text-slate-300"}`}>
      {warn ? <Loader2 className="size-3 animate-spin" /> : <CheckCircle2 className="size-3" />}
      {status}
    </span>
  );
}
