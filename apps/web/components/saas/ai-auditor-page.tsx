"use client";

import { useEffect, useState } from "react";
import { ShieldCheck, Sparkles, Wrench, Loader2, Triangle } from "lucide-react";
import Link from "next/link";
import { AppShell } from "./app-shell";
import { EmptyState, Panel, StatCard, StatusPill } from "./ui";
import { useWorkspace } from "./workspace";
import { AuditIssue, AuditSummaryData, fixAuditIssues, getAuditIssues, getAuditSummary } from "@/lib/api";

export function AiAuditorPage() {
  const workspace = useWorkspace();
  const [summary, setSummary] = useState<AuditSummaryData | null>(null);
  const [issues, setIssues] = useState<AuditIssue[]>([]);
  const [loading, setLoading] = useState(true);
  const [fixing, setFixing] = useState(false);
  const [notification, setNotification] = useState<string | null>(null);

  const token = workspace.token;
  const profile = workspace.profile;

  useEffect(() => {
    async function loadAudit() {
      if (!token || !profile) {
        setLoading(false);
        return;
      }
      setLoading(true);
      try {
        const [auditSummary, auditIssues] = await Promise.all([
          getAuditSummary(token, profile),
          getAuditIssues(token, profile),
        ]);
        setSummary(auditSummary);
        setIssues(auditIssues);
        setNotification(null);
      } catch (exc) {
        setNotification(exc instanceof Error ? exc.message : "Unable to load AI Auditor data");
      } finally {
        setLoading(false);
      }
    }
    loadAudit();
  }, [profile, token]);

  const issueCount = issues.length;
  const warnings = summary?.warnings ?? [];
  const canFix = Boolean(profile && token && issueCount > 0 && !fixing);

  async function handleFixIssues() {
    if (!token || !profile) return;
    setFixing(true);
    setNotification(null);
    try {
      const result = await fixAuditIssues(token, profile);
      if (result.fixed_count > 0) {
        setNotification(`Fixed ${result.fixed_count} issue${result.fixed_count === 1 ? "" : "s"}.`);
      } else {
        setNotification("No auto-fixable issues were detected.");
      }
      const [auditSummary, auditIssues] = await Promise.all([
        getAuditSummary(token, profile),
        getAuditIssues(token, profile),
      ]);
      setSummary(auditSummary);
      setIssues(auditIssues);
    } catch (exc) {
      setNotification(exc instanceof Error ? exc.message : "Unable to apply fixes");
    } finally {
      setFixing(false);
    }
  }

  if (!token) {
    return (
      <AppShell
        title="AI Auditor"
        subtitle="Inspect marketplace sales and prepare GST filings with smart audit insights."
        profile={workspace.profile}
        profiles={workspace.profiles}
        loading={workspace.loading}
        error={workspace.error}
        onRetry={() => workspace.refresh()}
        onProfileChange={(selected) => {
          workspace.setProfile(selected);
          workspace.refresh(selected);
        }}
        token={workspace.token}
        user={workspace.user}
        requiresSubscription={true}
        requiredPlan="online_seller"
      >
        <EmptyState
          title="Login required"
          body="Login to access AI-guided GST audit insights and automated issue remediation."
          action={
            <Link className="rounded bg-[#2f72ff] px-4 py-2 text-sm font-bold text-white" href="/login">
              Login
            </Link>
          }
        />
      </AppShell>
    );
  }

  return (
    <AppShell
      title="AI Auditor"
      subtitle="Inspect marketplace sales and prepare GST filings with smart audit insights."
      profile={workspace.profile}
      profiles={workspace.profiles}
      loading={workspace.loading}
      error={workspace.error}
      onRetry={() => workspace.refresh()}
      onProfileChange={(selected) => {
        workspace.setProfile(selected);
        workspace.refresh(selected);
      }}
      token={workspace.token}
      user={workspace.user}
      requiresSubscription={true}
      requiredPlan="online_seller"
    >
      <section className="grid gap-6 lg:grid-cols-[minmax(28rem,1fr)_minmax(22rem,1fr)]">
        <div className="space-y-6">
          <Panel
            title="Audit overview"
            subtitle="AI detects GST issues, marketplace reconciliation risks, and filing readiness for your current profile and period."
            action={
              <button
                type="button"
                onClick={handleFixIssues}
                disabled={!canFix}
                className="inline-flex items-center gap-2 rounded-full bg-[#12284f] px-4 py-2 text-sm font-bold text-white transition hover:bg-[#0f1e3d] disabled:cursor-not-allowed disabled:bg-slate-300"
              >
                {fixing ? <Loader2 className="size-4 animate-spin" /> : <Wrench className="size-4" />}
                Fix Issues
              </button>
            }
          >
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard
                label="Health Score"
                value={summary ? String(summary.auditor_health_score) : "--"}
                detail="Higher is better"
                tone={summary && summary.auditor_health_score && summary.auditor_health_score >= 80 ? "green" : summary && summary.auditor_health_score && summary.auditor_health_score >= 50 ? "saffron" : "red"}
              />
              <StatCard
                label="Readiness"
                value={summary?.readiness_status ?? "--"}
                detail={`${summary?.issue_counts ? Object.values(summary.issue_counts).reduce((sum, value) => sum + value, 0) : 0} issues detected`}
                tone={summary?.readiness_status === "Ready To File" ? "green" : summary?.readiness_status === "Almost Ready" ? "saffron" : "red"}
              />
              <StatCard
                label="Pending validation issues"
                value={String(workspace.summary?.pending_errors ?? 0)}
                detail="Rows requiring cleanup"
                tone={workspace.summary?.pending_errors ? "red" : "green"}
              />
              <StatCard
                label="Marketplace warnings"
                value={String(warnings.length)}
                detail="Top issue categories"
                tone={warnings.length ? "saffron" : "green"}
              />
            </div>
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              {notification ? (
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700 dark:border-white/10 dark:bg-slate-900 dark:text-slate-200">
                  <strong>Notice:</strong> {notification}
                </div>
              ) : null}
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm dark:border-white/10 dark:bg-slate-900">
                <p className="font-bold text-slate-900 dark:text-white">Summary</p>
                <p className="mt-2 text-slate-600 dark:text-slate-400">{loading ? "Loading audit details…" : summary ? "AI Auditor has scanned your current batch and found actionable issues." : "No audit data available."}</p>
              </div>
            </div>
          </Panel>
          <Panel title="Top findings" subtitle="Review the most important issues the AI Auditor found." action={null}>
            {loading ? (
              <div className="space-y-3">
                {Array.from({ length: 4 }).map((_, index) => (
                  <div key={index} className="h-14 rounded-2xl bg-slate-200/70 dark:bg-white/10" />
                ))}
              </div>
            ) : issueCount === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-500 dark:border-white/10 dark:bg-white/5 dark:text-slate-300">
                <Sparkles className="mx-auto mb-3 inline-block size-6 text-emerald-500" />
                <p className="font-bold">No critical audit issues detected.</p>
                <p className="mt-2">Your financials look consistent for the selected profile and period.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {issues.slice(0, 6).map((issue) => (
                  <div key={`${issue.transaction_id}-${issue.issue_type}-${issue.field}`} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-white/10 dark:bg-slate-900">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-black text-slate-900 dark:text-white">{issue.issue_type.replace(/_/g, " ")}</p>
                        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{issue.description}</p>
                      </div>
                      <StatusPill status={issue.severity === "error" ? "Needs Attention" : "Warning"} />
                    </div>
                    <div className="mt-3 grid gap-2 sm:grid-cols-2">
                      <p className="text-xs text-slate-500"><strong>Platform:</strong> {issue.platform || "unknown"}</p>
                      <p className="text-xs text-slate-500"><strong>Invoice:</strong> {issue.invoice_no || "N/A"}</p>
                      <p className="text-xs text-slate-500"><strong>Field:</strong> {issue.field || "—"}</p>
                      <p className="text-xs text-slate-500"><strong>Invoice Date:</strong> {issue.invoice_date || "—"}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </div>
        <div className="space-y-6">
          <Panel title="Audit details" subtitle="Breakdown of issue categories and expected next steps." action={null}>
            <div className="grid gap-3">
              <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-white/10 dark:bg-slate-900">
                <p className="text-sm font-black text-slate-900 dark:text-white">Issue categories</p>
                <div className="mt-4 grid gap-3">
                  {(summary?.issue_counts ? Object.entries(summary.issue_counts) : []).map(([category, count]) => (
                    <div key={category} className="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm dark:border-white/10 dark:bg-white/5">
                      <span className="font-semibold text-slate-700 dark:text-slate-200">{category.replace(/_/g, " ")}</span>
                      <span className="text-slate-500 dark:text-slate-400">{count}</span>
                    </div>
                  ))}
                  {!summary?.issue_counts && <p className="text-sm text-slate-500 dark:text-slate-400">No issue categories available.</p>}
                </div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-white/10 dark:bg-slate-900">
                <p className="text-sm font-black text-slate-900 dark:text-white">AI recommendations</p>
                <div className="mt-4 space-y-3 text-sm text-slate-600 dark:text-slate-300">
                  <p className="flex items-center gap-2"><Sparkles className="size-4 text-emerald-500" /> Use the Fix Issues action to auto-correct missing POS and invoice number issues.</p>
                  <p className="flex items-center gap-2"><Triangle className="size-4 text-saffron-500" /> Review non-auto-fix validation errors manually in Manage Data.</p>
                  <p className="flex items-center gap-2"><ShieldCheck className="size-4 text-blue-600" /> Release your final filing only when readiness status indicates the file is ready.</p>
                </div>
              </div>
            </div>
          </Panel>
          <Panel title="Issue log" subtitle="Audit fix logs are stored for your review." action={null}>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700 dark:border-white/10 dark:bg-slate-900 dark:text-slate-200">
              <p>Audit logs are created whenever the AI Auditor applies automated corrections to your transaction data.</p>
              <p className="mt-2">You can view the transaction history in the Manage Data module after fixes are applied.</p>
            </div>
          </Panel>
        </div>
      </section>
    </AppShell>
  );
}
