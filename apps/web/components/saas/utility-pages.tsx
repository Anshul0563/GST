"use client";

import { FormEvent, useEffect, useState } from "react";
import { CalendarDays, CreditCard, Settings } from "lucide-react";
import { AppShell, ClassicToolShell } from "@/components/saas/app-shell";
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
    if (editingId) {
      await updateProfile(workspace.token, editingId, form);
    } else {
      await createProfile(workspace.token, form);
    }
    setEditingId(null);
    setForm(currentProfileDefaults());
    await workspace.refresh();
    setMessage(editingId ? "GST profile updated." : "GST profile added.");
  }
  return <ClassicToolShell title="GST Online Seller Tool" crumb="GST Online Seller" active="profile" profile={workspace.profile}>
    <section className="rounded-md bg-white p-7 shadow-xl shadow-slate-200/80">
      <div className="text-center">
        <h2 className="text-xl font-black">GST Information</h2>
        <p className="mt-2 text-xs text-slate-500">Provide GST Number, month and year of filing.</p>
      </div>
      <div className="mx-auto mt-6 grid max-w-2xl gap-3 rounded-md border border-slate-200 bg-slate-50 p-4 text-xs md:grid-cols-3">
        <div><b className="text-slate-800">Active GSTIN</b><p className="mt-1 text-slate-500">{workspace.profile?.gstin || "No active profile"}</p></div>
        <div><b className="text-slate-800">Current period</b><p className="mt-1 text-slate-500">{workspace.profile?.return_period || dynamicDefaults.return_period}</p></div>
        <div><b className="text-slate-800">Financial year</b><p className="mt-1 text-slate-500">{workspace.profile?.financial_year || dynamicDefaults.financial_year}</p></div>
      </div>
      <form onSubmit={submit} className="mx-auto mt-8 max-w-2xl rounded-md border border-slate-200 bg-white shadow-sm">
        <div className="grid border-b border-slate-200 md:grid-cols-[1fr_220px]">
          <label className="flex items-center gap-3 px-4 py-3 text-xs text-slate-500">
            <span className="text-slate-400">▣</span>
            <input value={form.gstin} onChange={(event) => setForm({ ...form, gstin: event.target.value.toUpperCase() })} className="w-full bg-transparent text-sm font-semibold text-slate-800 outline-none" placeholder="GST Number" required maxLength={15} />
          </label>
          <div className="flex items-center justify-center gap-5 border-t border-slate-200 px-4 py-3 text-xs font-semibold md:border-l md:border-t-0">
            {["Monthly", "Quarterly"].map((item) => <label key={item} className="flex items-center gap-2"><input type="radio" checked={form.filing_frequency === item} onChange={() => setForm({ ...form, filing_frequency: item })} /> {item}</label>)}
          </div>
        </div>
        <div className="grid border-b border-slate-200 md:grid-cols-2">
          <label className="flex items-center gap-3 px-4 py-3 text-xs text-slate-500"><CalendarDays className="size-4 text-slate-400" /><input value={form.return_period} onChange={(event) => setForm({ ...form, return_period: event.target.value })} className="w-full bg-transparent text-sm font-semibold text-slate-800 outline-none" placeholder="Month e.g. 042026" required /></label>
          <label className="flex items-center gap-3 border-t border-slate-200 px-4 py-3 text-xs text-slate-500 md:border-l md:border-t-0"><CalendarDays className="size-4 text-slate-400" /><input value={form.financial_year} onChange={(event) => setForm({ ...form, financial_year: event.target.value })} className="w-full bg-transparent text-sm font-semibold text-slate-800 outline-none" placeholder="2026-27" required /></label>
        </div>
        <div className="grid border-b border-slate-200 md:grid-cols-2">
          <input value={form.legal_name} onChange={(event) => setForm({ ...form, legal_name: event.target.value })} className="px-4 py-3 text-sm font-semibold outline-none" placeholder="Business / legal name" required />
          <input value={form.trade_name} onChange={(event) => setForm({ ...form, trade_name: event.target.value })} className="border-t border-slate-200 px-4 py-3 text-sm font-semibold outline-none md:border-l md:border-t-0" placeholder="Trade name" />
        </div>
        <div className="flex items-center justify-between px-4 py-4">
          <button className="rounded bg-[#2f72ff] px-5 py-2.5 text-xs font-bold text-white">{editingId ? "Update" : "Submit"}</button>
          <button type="button" className="text-xs font-semibold text-[#2f72ff]">Need Help ? Read the Guide ⓘ</button>
        </div>
      </form>
      {message && <div className="mx-auto mt-4 max-w-2xl rounded bg-emerald-50 p-3 text-sm font-bold text-emerald-700">{message}</div>}
    </section>

    <section className="rounded-md bg-white p-7 shadow-xl shadow-slate-200/80">
      <div className="text-center">
        <h2 className="text-lg font-black">GSTIN List</h2>
        <p className="mt-1 text-xs text-slate-500">( Added: {workspace.profiles.length} / Limit: 20 )</p>
      </div>
      <div className="mt-6 grid gap-4 md:grid-cols-2">
        {workspace.profiles.map((profile) => <div key={profile.id} className="rounded border border-slate-200 bg-slate-50 p-4 text-center text-xs shadow-sm">
          <b className="text-slate-800">{profile.gstin}</b>
          <p className="mt-1 text-slate-500">Added: {profile.financial_year} / Used: {profile.return_period}</p>
          <p className="mt-1 font-semibold text-slate-700">{profile.trade_name || profile.legal_name}</p>
          <button onClick={() => { workspace.setProfile(profile); workspace.refresh(profile); setEditingId(profile.id); setForm({ gstin: profile.gstin, legal_name: profile.legal_name, trade_name: profile.trade_name || "", filing_frequency: profile.filing_frequency, financial_year: profile.financial_year, return_period: profile.return_period }); }} className="mt-3 rounded bg-[#2f72ff] px-4 py-1.5 text-xs font-bold text-white">Select</button>
        </div>)}
        {!workspace.profiles.length && <EmptyState title="No GSTIN added" body="Submit GST information to create first backend profile." />}
      </div>
    </section>
  </ClassicToolShell>;
}

export function SettingsPage() {
  const workspace = useWorkspace();
  const [settings, setSettings] = useState({ export_format: "JSON + Excel", import_completed: true, validation_warning: true, filing_reminders: false });
  const [saved, setSaved] = useState("");
  useEffect(() => {
    const raw = typeof window !== "undefined" ? window.localStorage.getItem("gst_bharat_workspace_settings") : null;
    if (raw) setSettings({ ...settings, ...JSON.parse(raw) });
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
