"use client";

import { FormEvent, useEffect, useState } from "react";
import { CreditCard, Settings } from "lucide-react";
import { AppShell } from "@/components/saas/app-shell";
import { EmptyState, Panel, StatCard } from "@/components/saas/ui";
import { useWorkspace } from "@/components/saas/workspace";
import { BillingPlan, BillingStatus, createBillingOrder, createProfile, getBillingPlans, getBillingStatus, updateProfile, verifyBillingPayment } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

export function ProfilePage() {
  const workspace = useWorkspace();
  const [form, setForm] = useState({ gstin: "", legal_name: "", trade_name: "", filing_frequency: "Monthly", financial_year: "2026-27", return_period: "042026" });
  const [editingId, setEditingId] = useState<number | null>(null);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!workspace.token) return;
    if (editingId) {
      await updateProfile(workspace.token, editingId, form);
    } else {
      await createProfile(workspace.token, form);
    }
    setEditingId(null);
    setForm({ gstin: "", legal_name: "", trade_name: "", filing_frequency: "Monthly", financial_year: "2026-27", return_period: "042026" });
    await workspace.refresh();
  }
  return <AppShell title="GST Profiles" subtitle="Manage GSTIN workspaces, filing frequency and return period." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }}><div className="grid gap-6 xl:grid-cols-[1fr_0.9fr]"><Panel title="Profiles" subtitle="Switch or edit backend GST profiles."><div className="space-y-3">{workspace.profiles.map((profile) => <div key={profile.id} className="flex items-center justify-between gap-4 rounded-2xl bg-slate-50 p-4 dark:bg-white/5"><button onClick={() => { workspace.setProfile(profile); workspace.refresh(profile); }} className="text-left"><b>{profile.gstin}</b><p className="text-sm text-slate-500">{profile.legal_name} / {profile.return_period}</p></button><button onClick={() => { setEditingId(profile.id); setForm({ gstin: profile.gstin, legal_name: profile.legal_name, trade_name: profile.trade_name || "", filing_frequency: profile.filing_frequency, financial_year: profile.financial_year, return_period: profile.return_period }); }} className="rounded-xl bg-white px-3 py-2 text-xs font-bold text-[#1746A2] dark:bg-slate-900">Edit</button></div>)}</div></Panel><Panel title={editingId ? "Update GST profile" : "Add GST profile"} subtitle="State code is detected from GSTIN by backend."><form onSubmit={submit} className="space-y-3">{Object.keys(form).map((key) => <input key={key} value={form[key as keyof typeof form]} onChange={(event) => setForm({ ...form, [key]: event.target.value })} className="w-full rounded-2xl border px-4 py-3 dark:border-white/10 dark:bg-slate-900" placeholder={key.replaceAll("_", " ")} />)}<button className="rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white">{editingId ? "Update profile" : "Create profile"}</button>{editingId && <button type="button" onClick={() => { setEditingId(null); setForm({ gstin: "", legal_name: "", trade_name: "", filing_frequency: "Monthly", financial_year: "2026-27", return_period: "042026" }); }} className="ml-3 rounded-2xl border px-5 py-3 text-sm font-bold">Cancel</button>}</form></Panel></div></AppShell>;
}

export function SettingsPage() {
  const workspace = useWorkspace();
  return <AppShell title="Settings" subtitle="Workspace preferences, security controls, notifications and export defaults." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }}><Panel title="Workspace settings" subtitle="Frontend-ready settings. Persistence can be added to backend later."><div className="grid gap-4 md:grid-cols-2"><label className="rounded-2xl bg-slate-50 p-4 font-bold dark:bg-white/5"><Settings className="mb-3 size-5 text-[#1746A2]" />Default export format<select className="mt-3 w-full rounded-xl border px-3 py-2 dark:border-white/10 dark:bg-slate-900"><option>JSON + Excel</option><option>JSON only</option><option>Excel only</option></select></label><label className="rounded-2xl bg-slate-50 p-4 font-bold dark:bg-white/5">Notifications<div className="mt-3 space-y-2 text-sm font-medium text-slate-500"><label className="flex gap-2"><input type="checkbox" defaultChecked /> Import completed</label><label className="flex gap-2"><input type="checkbox" defaultChecked /> Validation warning</label><label className="flex gap-2"><input type="checkbox" /> Filing reminders</label></div></label></div></Panel></AppShell>;
}

export function BillingPage() {
  const workspace = useWorkspace();
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [status, setStatus] = useState<BillingStatus | null>(null);
  const [cycle, setCycle] = useState("monthly");
  const [message, setMessage] = useState("");

  async function loadBilling() {
    if (!workspace.token) return;
    const [planResult, statusResult] = await Promise.all([getBillingPlans(workspace.token), getBillingStatus(workspace.token)]);
    setPlans(planResult.plans);
    setStatus(statusResult);
  }

  async function startCheckout(planId: string) {
    if (!workspace.token) return;
    const order = await createBillingOrder(workspace.token, { plan_id: planId, billing_cycle: cycle });
    if (order.free_access) {
      setMessage(order.message || "Free access is active.");
      await loadBilling();
      return;
    }
    if (!order.gateway_configured) {
      setMessage(`Payment order #${order.id} created, but Razorpay keys are not configured in backend .env yet.`);
      await loadBilling();
      return;
    }
    const loaded = await loadRazorpay();
    if (!loaded || !order.id || !order.provider_order_id || !order.gateway_key_id || !order.amount_paise) {
      setMessage("Razorpay Checkout could not be loaded. Check internet access and gateway keys.");
      return;
    }
    const Razorpay = window.Razorpay;
    if (!Razorpay) {
      setMessage("Razorpay Checkout is unavailable after script load.");
      return;
    }
    const checkout = new Razorpay({
      key: order.gateway_key_id,
      amount: order.amount_paise,
      currency: order.currency || "INR",
      name: "GST Bharat",
      description: `${order.plan_id} ${order.billing_cycle} subscription`,
      order_id: order.provider_order_id,
      prefill: {
        name: workspace.user?.full_name || "",
        email: workspace.user?.email || "",
      },
      theme: { color: "#10244d" },
      handler: async (response: { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }) => {
        await verifyBillingPayment(workspace.token, {
          order_id: order.id!,
          razorpay_order_id: response.razorpay_order_id,
          razorpay_payment_id: response.razorpay_payment_id,
          razorpay_signature: response.razorpay_signature,
        });
        setMessage("Payment verified. Subscription is active.");
        await loadBilling();
      },
    });
    checkout.open();
    await loadBilling();
  }

  useEffect(() => {
    if (!workspace.token) return;
    loadBilling().catch((exc) => setMessage(exc instanceof Error ? exc.message : "Could not load billing"));
  }, [workspace.token]);

  return <AppShell title="Billing" subtitle="Subscription, free-access admin status and Razorpay checkout." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }}>
    <div className="space-y-6">
      {!workspace.token ? <EmptyState title="Login required" body="Billing is connected to authenticated backend APIs." /> : null}
      <Panel title="Account access" subtitle="Live billing status from backend.">
        <div className="grid gap-4 md:grid-cols-4">
          <StatCard label="Role" value={status?.role || workspace.user?.role || "user"} />
          <StatCard label="Plan" value={status?.plan || workspace.user?.plan || "free"} tone={status?.free_access ? "green" : "blue"} />
          <StatCard label="Status" value={status?.subscription_status || workspace.user?.subscription_status || "inactive"} tone={status?.subscription_status === "active" ? "green" : "saffron"} />
          <StatCard label="Billing cycle" value={cycle} />
        </div>
        {status?.free_access && <div className="mt-5 rounded-3xl bg-emerald-50 p-4 text-sm font-bold text-emerald-700">{status.free_access_reason || "This account has unrestricted free access."}</div>}
        {message && <div className="mt-5 rounded-3xl bg-blue-50 p-4 text-sm font-bold text-blue-700">{message}</div>}
      </Panel>
      <Panel title="Plans" subtitle="Orders are created through backend /billing/create-order. Razorpay key/secret come from .env.">
        <div className="mb-5 inline-flex rounded-2xl bg-slate-100 p-1 text-sm font-bold dark:bg-white/10">
          {["monthly", "yearly"].map((item) => <button key={item} onClick={() => setCycle(item)} className={`rounded-xl px-4 py-2 capitalize ${cycle === item ? "bg-[#10244d] text-white" : "text-slate-600 dark:text-slate-300"}`}>{item}</button>)}
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          {plans.map((plan) => {
            const amount = cycle === "yearly" ? plan.yearly_amount : plan.monthly_amount;
            return <div key={plan.id} className="rounded-3xl border border-slate-200 bg-white p-5 shadow-xl shadow-slate-200/60 dark:border-white/10 dark:bg-slate-900 dark:shadow-none">
              <h3 className="text-xl font-black">{plan.name}</h3>
              <p className="mt-3 text-3xl font-black">{formatCurrency(amount)}</p>
              <p className="text-sm text-slate-500">per {cycle === "yearly" ? "year" : "month"}</p>
              <div className="mt-5 space-y-2 text-sm text-slate-600 dark:text-slate-300">{plan.features.map((feature) => <p key={feature}>- {feature}</p>)}</div>
              <button onClick={() => startCheckout(plan.id)} className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white"><CreditCard className="size-4" /> Create order</button>
            </div>;
          })}
          {!plans.length && <EmptyState title="Plans not loaded" body="Login and retry billing status." />}
        </div>
      </Panel>
    </div>
  </AppShell>;
}

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => { open: () => void };
  }
}

function loadRazorpay() {
  if (typeof window === "undefined") return Promise.resolve(false);
  if (window.Razorpay) return Promise.resolve(true);
  return new Promise<boolean>((resolve) => {
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
}
