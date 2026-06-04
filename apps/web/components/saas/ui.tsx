"use client";

import { motion } from "framer-motion";
import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";

export function StatCard({ label, value, detail, tone = "blue" }: { label: string; value: string; detail?: string; tone?: "blue" | "green" | "saffron" | "red" }) {
  const tones = {
    blue: "bg-blue-600",
    green: "bg-emerald-600",
    saffron: "bg-orange-500",
    red: "bg-rose-600"
  };
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="surface rounded-2xl p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <p className="text-xs font-bold uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</p>
        <span className={`h-2.5 w-2.5 rounded-full ${tones[tone]}`} />
      </div>
      <p className="text-2xl font-black tracking-tight text-slate-950 dark:text-white">{value}</p>
      {detail && <p className="mt-2 text-xs font-medium leading-5 text-slate-500 dark:text-slate-400">{detail}</p>}
    </motion.div>
  );
}

export function Panel({ title, subtitle, action, children }: { title: string; subtitle?: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="surface rounded-2xl p-5">
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-black tracking-tight text-slate-950 dark:text-white">{title}</h2>
          {subtitle && <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-500 dark:text-slate-400">{subtitle}</p>}
        </div>
        {action}
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
