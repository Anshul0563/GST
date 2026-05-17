"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BatchStatus,
  DashboardSummary,
  Gstr1Payload,
  Profile,
  TallyCompany,
  Transaction,
  ensureDemoWorkspace,
  getCurrentUser,
  getGstrPreview,
  getSummary,
  getTransactions,
  listImportBatches,
  listProfiles,
  listTallyCompanies
} from "@/lib/api";

export type Workspace = {
  token: string;
  user: { id: number; email: string; full_name?: string | null } | null;
  profile: Profile | null;
  profiles: Profile[];
  summary: DashboardSummary | null;
  transactions: Transaction[];
  batches: BatchStatus[];
  preview: Gstr1Payload | null;
  companies: TallyCompany[];
  loading: boolean;
  error: string;
  setProfile: (profile: Profile) => void;
  refresh: (profileOverride?: Profile) => Promise<void>;
};

export function useWorkspace(): Workspace {
  const [token, setToken] = useState("");
  const [user, setUser] = useState<Workspace["user"]>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [batches, setBatches] = useState<BatchStatus[]>([]);
  const [preview, setPreview] = useState<Gstr1Payload | null>(null);
  const [companies, setCompanies] = useState<TallyCompany[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = useCallback(async (profileOverride?: Profile) => {
    const activeToken = token || (typeof window !== "undefined" ? window.localStorage.getItem("gst_bharat_token") || "" : "");
    const activeProfile = profileOverride || profile;
    if (!activeToken || !activeProfile) return;
    setLoading(true);
    try {
      const [nextUser, nextProfiles, nextSummary, nextRows, nextBatches, nextPreview, nextCompanies] = await Promise.all([
        getCurrentUser(activeToken),
        listProfiles(activeToken),
        getSummary(activeToken, activeProfile),
        getTransactions(activeToken, activeProfile),
        listImportBatches(activeToken, activeProfile.id),
        getGstrPreview(activeToken, activeProfile),
        listTallyCompanies(activeToken, activeProfile.id)
      ]);
      setUser(nextUser);
      setProfiles(nextProfiles);
      setSummary(nextSummary);
      setTransactions(nextRows);
      setBatches(nextBatches);
      setPreview(nextPreview);
      setCompanies(nextCompanies);
      setError("");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Could not refresh workspace");
    } finally {
      setLoading(false);
    }
  }, [profile, token]);

  useEffect(() => {
    ensureDemoWorkspace()
      .then(async ({ token, profile }) => {
        setToken(token);
        setProfile(profile);
        await refresh(profile);
      })
      .catch((exc) => {
        setError(exc instanceof Error ? exc.message : "Could not initialize workspace");
        setLoading(false);
      });
  }, []);

  return useMemo(() => ({
    token,
    user,
    profile,
    profiles,
    summary,
    transactions,
    batches,
    preview,
    companies,
    loading,
    error,
    setProfile,
    refresh
  }), [token, user, profile, profiles, summary, transactions, batches, preview, companies, loading, error, refresh]);
}

export function money(value: number | string | null | undefined) {
  return Number(value || 0);
}
