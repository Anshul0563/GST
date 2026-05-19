"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BatchStatus,
  DashboardSummary,
  Gstr1Payload,
  Profile,
  TallyCompany,
  Transaction,
  getCurrentUser,
  getGstrPreview,
  getSummary,
  getTransactions,
  listImportBatches,
  listProfiles,
  listTallyCompanies,
  loadWorkspace
} from "@/lib/api";

export type Workspace = {
  token: string;
  user: { id: number; email: string; full_name?: string | null; role?: string; plan?: string; subscription_status?: string; free_access_reason?: string | null } | null;
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

  const refreshWorkspace = useCallback(async (activeToken: string, activeProfile: Profile | null | undefined) => {
    if (!activeToken) return;
    setLoading(true);
    try {
      if (!activeProfile) {
        const [nextUser, nextProfiles] = await Promise.all([getCurrentUser(activeToken), listProfiles(activeToken)]);
        setUser(nextUser);
        setProfiles(nextProfiles);
        setProfile(nextProfiles[0] ?? null);
        setSummary(null);
        setTransactions([]);
        setBatches([]);
        setPreview(null);
        setCompanies([]);
        setError("");
        return;
      }
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
  }, []);

  const refresh = useCallback(async (profileOverride?: Profile) => {
    const activeToken = token || (typeof window !== "undefined" ? window.localStorage.getItem("gst_bharat_token") || "" : "");
    const activeProfile = profileOverride || profile;
    await refreshWorkspace(activeToken, activeProfile);
  }, [profile, refreshWorkspace, token]);

  useEffect(() => {
    const storedToken = typeof window !== "undefined" ? window.localStorage.getItem("gst_bharat_token") : null;
    if (!storedToken) {
      setLoading(false);
      return;
    }
    const initializer = loadWorkspace(storedToken).then(({ user, profiles, profile }) => ({ token: storedToken, user, profiles, profile }));
    initializer
      .then(async ({ token, user, profiles, profile }) => {
        setToken(token);
        setUser(user);
        setProfiles(profiles);
        setProfile(profile);
        await refreshWorkspace(token, profile);
      })
      .catch((exc) => {
        setError(exc instanceof Error ? exc.message : "Could not initialize workspace");
        setLoading(false);
      });
  }, [refreshWorkspace]);

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
