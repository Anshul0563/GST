"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { CalendarDays, CheckCircle2, CreditCard, Settings, ShieldCheck } from "lucide-react";
import { AppShell } from "@/components/saas/app-shell";
import { EmptyState, Panel, StatCard } from "@/components/saas/ui";
import { useWorkspace } from "@/components/saas/workspace";
import { BillingPlan, BillingStatus, createBillingOrder, createProfile, getBillingPlans, getBillingStatus, updateProfile, verifyBillingPayment } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

function currentProfileDefaults() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const year = now.getFullYear();
  const financialStart = now.getMonth() >= 3 ? year : year - 1;
  return {
    gstin: "",
    legal_name: "",
    trade_name: "",
    filing_frequency: "Monthly",
    financial_year: `${financialStart}-${String(financialStart + 1).slice(-2)}`,
    return_period: `${month}${year}`
  };
}

export function ProfilePage() {
  const workspace = useWorkspace();
  const [form, setForm] = useState(currentProfileDefaults);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const dynamicDefaults = currentProfileDefaults();
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!workspace.token) return;
    const savedProfile = editingId
      ? await updateProfile(workspace.token, editingId, form)
      : await createProfile(workspace.token, form);
    workspace.setProfile(savedProfile);
    await workspace.refresh(savedProfile);
    if (editingId) {
      setForm({ gstin: savedProfile.gstin, legal_name: savedProfile.legal_name, trade_name: savedProfile.trade_name || "", filing_frequency: savedProfile.filing_frequency, financial_year: savedProfile.financial_year, return_period: savedProfile.return_period });
    } else {
      setForm(currentProfileDefaults());
      setEditingId(savedProfile.id);
    }
    setMessage(editingId ? "GST profile updated." : "GST profile added.");
  }
  return <AppShell title="GST Profile & Filing Period" subtitle="Select the GSTIN, return period and Monthly/Quarterly filing mode before using any GST Bharat tool." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); setEditingId(profile.id); setForm({ gstin: profile.gstin, legal_name: profile.legal_name, trade_name: profile.trade_name || "", filing_frequency: profile.filing_frequency, financial_year: profile.financial_year, return_period: profile.return_period }); }}>
    <div className="space-y-6">
      {!workspace.token ? <EmptyState title="Login required" body="Login to create or update GST profile details." /> : null}
      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="Active GSTIN" value={workspace.profile?.gstin || "Not set"} />
        <StatCard label="Return period" value={workspace.profile?.return_period || dynamicDefaults.return_period} />
        <StatCard label="Filing mode" value={workspace.profile?.filing_frequency || dynamicDefaults.filing_frequency} />
        <StatCard label="Financial year" value={workspace.profile?.financial_year || dynamicDefaults.financial_year} />
      </div>
      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <Panel title="Workspace setup" subtitle="Save this once, then continue with upload, reconcile or Tally export.">
          <form onSubmit={submit} className="space-y-4">
            <label className="grid gap-2 text-sm font-bold">GST number
              <input value={form.gstin} onChange={(event) => setForm({ ...form, gstin: event.target.value.toUpperCase() })} className="rounded-2xl border border-slate-200 px-4 py-3 text-sm font-semibold outline-none dark:border-white/10 dark:bg-slate-900" placeholder="15 digit GSTIN" required maxLength={15} />
            </label>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="grid gap-2 text-sm font-bold">Return period
                <div className="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3 dark:border-white/10 dark:bg-slate-900">
                  <CalendarDays className="size-4 text-[#1746A2]" />
                  <input value={form.return_period} onChange={(event) => setForm({ ...form, return_period: event.target.value })} className="min-w-0 flex-1 bg-transparent text-sm font-semibold outline-none" placeholder="MMYYYY e.g. 052026" required />
                </div>
              </label>
              <label className="grid gap-2 text-sm font-bold">Financial year
                <input value={form.financial_year} onChange={(event) => setForm({ ...form, financial_year: event.target.value })} className="rounded-2xl border border-slate-200 px-4 py-3 text-sm font-semibold outline-none dark:border-white/10 dark:bg-slate-900" placeholder="2026-27" required />
              </label>
            </div>
            <div className="rounded-3xl bg-slate-50 p-4 dark:bg-white/5">
              <p className="text-sm font-black">Filing frequency</p>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                {["Monthly", "Quarterly"].map((item) => <button key={item} type="button" onClick={() => setForm({ ...form, filing_frequency: item })} className={`rounded-2xl border px-4 py-3 text-left text-sm font-bold transition ${form.filing_frequency === item ? "border-[#1746A2] bg-[#1746A2] text-white" : "border-slate-200 bg-white text-slate-600 dark:border-white/10 dark:bg-slate-900 dark:text-slate-300"}`}>
                  <span className="flex items-center gap-2">{form.filing_frequency === item && <CheckCircle2 className="size-4" />}{item}</span>
                </button>)}
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="grid gap-2 text-sm font-bold">Legal name
                <input value={form.legal_name} onChange={(event) => setForm({ ...form, legal_name: event.target.value })} className="rounded-2xl border border-slate-200 px-4 py-3 text-sm font-semibold outline-none dark:border-white/10 dark:bg-slate-900" placeholder="Business / legal name" required />
              </label>
              <label className="grid gap-2 text-sm font-bold">Trade name
                <input value={form.trade_name} onChange={(event) => setForm({ ...form, trade_name: event.target.value })} className="rounded-2xl border border-slate-200 px-4 py-3 text-sm font-semibold outline-none dark:border-white/10 dark:bg-slate-900" placeholder="Brand / trade name" />
              </label>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <button disabled={!workspace.token} className="rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-50">{editingId ? "Update workspace" : "Create workspace"}</button>
              <button type="button" onClick={() => { setEditingId(null); setForm(currentProfileDefaults()); }} className="rounded-2xl border border-slate-200 px-5 py-3 text-sm font-bold text-slate-600 dark:border-white/10 dark:text-slate-300">New GSTIN</button>
            </div>
            {message && <div className="rounded-2xl bg-emerald-50 p-4 text-sm font-bold text-emerald-700">{message}</div>}
          </form>
        </Panel>

        <Panel title="Saved GSTINs" subtitle={`Added ${workspace.profiles.length} / Limit 20`}>
          <div className="space-y-3">
            {workspace.profiles.map((profile) => {
              const active = workspace.profile?.id === profile.id;
              return <button key={profile.id} onClick={() => { workspace.setProfile(profile); workspace.refresh(profile); setEditingId(profile.id); setForm({ gstin: profile.gstin, legal_name: profile.legal_name, trade_name: profile.trade_name || "", filing_frequency: profile.filing_frequency, financial_year: profile.financial_year, return_period: profile.return_period }); }} className={`w-full rounded-3xl border p-4 text-left transition ${active ? "border-[#1746A2] bg-blue-50 dark:bg-blue-500/10" : "border-slate-200 bg-slate-50 hover:bg-white dark:border-white/10 dark:bg-white/5 dark:hover:bg-slate-900"}`}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <b>{profile.gstin}</b>
                    <p className="mt-1 text-sm text-slate-500">{profile.trade_name || profile.legal_name}</p>
                  </div>
                  {active && <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-black text-emerald-700">Active</span>}
                </div>
                <div className="mt-4 grid grid-cols-3 gap-2 text-xs font-bold text-slate-500">
                  <span className="rounded-2xl bg-white px-3 py-2 dark:bg-slate-900">{profile.return_period}</span>
                  <span className="rounded-2xl bg-white px-3 py-2 dark:bg-slate-900">{profile.filing_frequency}</span>
                  <span className="rounded-2xl bg-white px-3 py-2 dark:bg-slate-900">{profile.financial_year}</span>
                </div>
              </button>;
            })}
            {!workspace.profiles.length && <EmptyState title="No GSTIN added" body="Submit GST information to create first backend profile." />}
          </div>
        </Panel>
      </div>
      <Panel title="Works across all modules" subtitle="The same active GST profile controls Online Seller, 2A/2B Reconcile and eCom to Tally.">
        <div className="grid gap-3 text-sm md:grid-cols-3">
          {["GST Online Seller", "2A/2B Reconcile", "eCom to Tally"].map((item) => <div key={item} className="flex items-center gap-3 rounded-2xl bg-slate-50 p-4 font-bold dark:bg-white/5"><ShieldCheck className="size-4 text-emerald-600" /> {item}</div>)}
        </div>
      </Panel>
    </div>
  </AppShell>;
}

export function SettingsPage() {
  const workspace = useWorkspace();
  const [settings, setSettings] = useState({ export_format: "JSON + Excel", import_completed: true, validation_warning: true, filing_reminders: false });
  const [saved, setSaved] = useState("");
  useEffect(() => {
    const raw = typeof window !== "undefined" ? window.localStorage.getItem("gst_bharat_workspace_settings") : null;
    if (raw) setSettings((current) => ({ ...current, ...JSON.parse(raw) }));
  }, []);
  function saveSettings() {
    window.localStorage.setItem("gst_bharat_workspace_settings", JSON.stringify(settings));
    setSaved("Workspace preferences saved in this browser.");
  }
  return <AppShell title="Settings" subtitle="Workspace preferences, account context and export defaults." profile={workspace.profile} profiles={workspace.profiles} onProfileChange={(profile) => { workspace.setProfile(profile); workspace.refresh(profile); }}>
    <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
      <Panel title="Account context" subtitle="Loaded from authenticated backend session and active GST profile.">
        <div className="grid gap-3 text-sm md:grid-cols-2">
          <div className="rounded-2xl bg-slate-50 p-4 dark:bg-white/5"><b>Email</b><p>{workspace.user?.email || "Not logged in"}</p></div>
          <div className="rounded-2xl bg-slate-50 p-4 dark:bg-white/5"><b>Role</b><p>{workspace.user?.role || "user"}</p></div>
          <div className="rounded-2xl bg-slate-50 p-4 dark:bg-white/5"><b>Plan</b><p>{workspace.user?.plan || "free"}</p></div>
          <div className="rounded-2xl bg-slate-50 p-4 dark:bg-white/5"><b>GSTIN</b><p>{workspace.profile?.gstin || "No GST profile"}</p></div>
        </div>
      </Panel>
      <Panel title="Workspace preferences" subtitle="Stored locally until a backend settings table is added.">
        <div className="grid gap-4 md:grid-cols-2">
          <label className="rounded-2xl bg-slate-50 p-4 font-bold dark:bg-white/5"><Settings className="mb-3 size-5 text-[#1746A2]" />Default export format<select value={settings.export_format} onChange={(event) => setSettings({ ...settings, export_format: event.target.value })} className="mt-3 w-full rounded-xl border px-3 py-2 dark:border-white/10 dark:bg-slate-900"><option>JSON + Excel</option><option>JSON only</option><option>Excel only</option></select></label>
          <label className="rounded-2xl bg-slate-50 p-4 font-bold dark:bg-white/5">Notifications<div className="mt-3 space-y-2 text-sm font-medium text-slate-500"><label className="flex gap-2"><input type="checkbox" checked={settings.import_completed} onChange={(event) => setSettings({ ...settings, import_completed: event.target.checked })} /> Import completed</label><label className="flex gap-2"><input type="checkbox" checked={settings.validation_warning} onChange={(event) => setSettings({ ...settings, validation_warning: event.target.checked })} /> Validation warning</label><label className="flex gap-2"><input type="checkbox" checked={settings.filing_reminders} onChange={(event) => setSettings({ ...settings, filing_reminders: event.target.checked })} /> Filing reminders</label></div></label>
        </div>
        <button onClick={saveSettings} className="mt-5 rounded-2xl bg-[#10244d] px-5 py-3 text-sm font-bold text-white">Save settings</button>
        {saved && <div className="mt-4 rounded-2xl bg-emerald-50 p-4 text-sm font-bold text-emerald-700">{saved}</div>}
      </Panel>
    </div>
  </AppShell>;
}

export function BillingPage() {
  const workspace = useWorkspace();
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [status, setStatus] = useState<BillingStatus | null>(null);
  const [cycle, setCycle] = useState("monthly");
  const [message, setMessage] = useState("");

  const loadBilling = useCallback(async () => {
    if (!workspace.token) return;
    const [planResult, statusResult] = await Promise.all([getBillingPlans(workspace.token), getBillingStatus(workspace.token)]);
    setPlans(planResult.plans);
    setStatus(statusResult);
  }, [workspace.token]);

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
  }, [workspace.token, loadBilling]);

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
