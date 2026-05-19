"use client";

import { motion } from "framer-motion";
import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";

export function StatCard({ label, value, detail, tone = "blue" }: { label: string; value: string; detail?: string; tone?: "blue" | "green" | "saffron" | "red" }) {
  const tones = {
    blue: "from-blue-600 to-indigo-600",
    green: "from-emerald-600 to-teal-500",
    saffron: "from-orange-500 to-amber-400",
    red: "from-rose-600 to-red-500"
  };
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="rounded-3xl border border-white/70 bg-white p-5 shadow-xl shadow-slate-200/60 dark:border-white/10 dark:bg-slate-950 dark:shadow-none">
      <div className={`mb-5 h-1.5 w-16 rounded-full bg-gradient-to-r ${tones[tone]}`} />
      <p className="text-sm font-semibold text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-black tracking-tight">{value}</p>
      {detail && <p className="mt-2 text-xs font-medium text-slate-400">{detail}</p>}
    </motion.div>
  );
}

export function Panel({ title, subtitle, action, children }: { title: string; subtitle?: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-3xl border border-white/70 bg-white p-5 shadow-xl shadow-slate-200/60 dark:border-white/10 dark:bg-slate-950 dark:shadow-none">
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-black tracking-tight">{title}</h2>
          {subtitle && <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

export function EmptyState({ title, body, action }: { title: string; body: string; action?: React.ReactNode }) {
  return (
    <div className="grid min-h-56 place-items-center rounded-3xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center dark:border-white/10 dark:bg-white/5">
      <div>
        <div className="mx-auto grid size-12 place-items-center rounded-2xl bg-white shadow-sm dark:bg-slate-900"><AlertCircle className="size-5 text-saffron" /></div>
        <h3 className="mt-4 text-base font-black">{title}</h3>
        <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">{body}</p>
        {action && <div className="mt-5">{action}</div>}
      </div>
    </div>
  );
}

export function SkeletonGrid() {
  return <div className="grid gap-4 md:grid-cols-4">{Array.from({ length: 4 }).map((_, index) => <div key={index} className="h-32 animate-pulse rounded-3xl bg-slate-200/70 dark:bg-white/10" />)}</div>;
}

export function StatusPill({ status }: { status: string }) {
  const ok = ["completed", "generated", "downloaded", "Active"].includes(status);
  const warn = ["queued", "processing", "Beta"].includes(status);
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold ${ok ? "bg-emerald-50 text-emerald-700" : warn ? "bg-amber-50 text-amber-700" : "bg-slate-100 text-slate-600"}`}>
      {warn ? <Loader2 className="size-3 animate-spin" /> : <CheckCircle2 className="size-3" />}
      {status}
    </span>
  );
}
