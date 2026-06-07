"use client";

import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type TrendPoint = {
  name: string;
  matched: number;
  mismatch: number;
};

type RiskPoint = {
  name: string;
  value: number;
};

export function ChartSkeleton({ heightClass = "h-80" }: { heightClass?: string }) {
  return (
    <div className={`${heightClass} animate-pulse rounded-2xl bg-slate-100 dark:bg-white/10`} />
  );
}

export function ReconcileTrendChart({ data }: { data: TrendPoint[] }) {
  return (
    <div className="h-80">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Bar dataKey="matched" fill="#0F9F6E" radius={[10, 10, 0, 0]} />
          <Bar dataKey="mismatch" fill="#F58220" radius={[10, 10, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ReconcileRiskChart({ data }: { data: RiskPoint[] }) {
  return (
    <div className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="name" hide />
          <YAxis allowDecimals={false} />
          <Tooltip />
          <Area type="monotone" dataKey="value" stroke="#1746A2" fill="#1746A240" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
