"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import {
  BatchStatus,
  DashboardSummary,
  Gstr1Payload,
  MarketplaceCatalogItem,
  Profile,
  TallyCompany,
  Transaction,
  getCurrentUser,
  getGstrPreview,
  getMarketplaces,
  getSummary,
  getTransactions,
  listImportBatches,
  listProfiles,
  listTallyCompanies
} from "@/lib/api";
import { clearAuthToken, getStoredAuthToken } from "@/lib/auth";

const ACTIVE_PROFILE_KEY = "gst_bharat_active_profile_id";

export type Workspace = {
  token: string;
  user: { id: number; email: string; full_name?: string | null; role?: string; plan?: string; subscription_status?: string; subscription_expires_at?: string | null; free_access_reason?: string | null } | null;
  profile: Profile | null;
  profiles: Profile[];
  summary: DashboardSummary | null;
  transactions: Transaction[];
  batches: BatchStatus[];
  preview: Gstr1Payload | null;
  companies: TallyCompany[];
  marketplaces: MarketplaceCatalogItem[];
  loading: boolean;
  error: string;
  setProfile: (profile: Profile) => void;
  refresh: (profileOverride?: Profile) => Promise<void>;
};

export function useWorkspace(): Workspace {
  const pathname = usePathname();
  const [token, setToken] = useState("");
  const [user, setUser] = useState<Workspace["user"]>(null);
  const [profile, setActiveProfile] = useState<Profile | null>(null);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [batches, setBatches] = useState<BatchStatus[]>([]);
  const [preview, setPreview] = useState<Gstr1Payload | null>(null);
  const [companies, setCompanies] = useState<TallyCompany[]>([]);
  const [marketplaces, setMarketplaces] = useState<MarketplaceCatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const refreshSeq = useRef(0);

  const clearPeriodScopedState = useCallback(() => {
    setSummary(null);
    setTransactions([]);
    setBatches([]);
    setPreview(null);
    setCompanies([]);
    setError("");
  }, []);

  const selectProfile = useCallback((nextProfile: Profile) => {
    refreshSeq.current += 1;
    if (typeof window !== "undefined") {
      window.localStorage.setItem(ACTIVE_PROFILE_KEY, String(nextProfile.id));
    }
    setActiveProfile(nextProfile);
    clearPeriodScopedState();
    setLoading(true);
  }, [clearPeriodScopedState]);

  const needs = useMemo(() => {
    const path = pathname || "";
    const isDashboard = path === "/dashboard";
    const isOnlineSeller = path.startsWith("/modules/online-seller");
    const isTally = path.startsWith("/modules/tally");
    const isImport = path.includes("/marketplaces") || path.includes("/import") || isDashboard || path === "/modules/online-seller" || path === "/modules/tally";
    const isGstr = path.includes("/gstr1") || path === "/modules/online-seller" || isDashboard;
    const isTransactions = isOnlineSeller || isTally || isDashboard;
    return {
      summary: isOnlineSeller || isTally || isDashboard,
      transactions: isTransactions,
      batches: isImport || isOnlineSeller || isTally || isDashboard,
      preview: isGstr,
      companies: isTally || isDashboard,
    };
  }, [pathname]);

  const refreshWorkspace = useCallback(async (activeToken: string, activeProfile: Profile | null | undefined, base?: { user: Workspace["user"]; profiles: Profile[] }) => {
    if (!activeToken) return;
    const requestId = ++refreshSeq.current;
    const isCurrent = () => requestId === refreshSeq.current;
    setLoading(true);
    try {
      if (!activeProfile) {
        const [nextUser, nextProfiles] = await Promise.all([getCurrentUser(activeToken), listProfiles(activeToken)]);
        if (!isCurrent()) return;
        const storedProfileId = typeof window !== "undefined" ? Number(window.localStorage.getItem(ACTIVE_PROFILE_KEY) || 0) : 0;
        const nextProfile = nextProfiles.find((item) => item.id === storedProfileId) ?? nextProfiles[0] ?? null;
        setUser(nextUser);
        setProfiles(nextProfiles);
        setActiveProfile(nextProfile);
        clearPeriodScopedState();
        setError("");
        return;
      }
      const [nextUser, nextProfiles, nextSummary, nextRows, nextBatches, nextPreview, nextCompanies] = await Promise.all([
        base ? Promise.resolve(base.user) : getCurrentUser(activeToken),
        base ? Promise.resolve(base.profiles) : listProfiles(activeToken),
        needs.summary ? getSummary(activeToken, activeProfile) : Promise.resolve(null),
        needs.transactions ? getTransactions(activeToken, activeProfile) : Promise.resolve([]),
        needs.batches ? listImportBatches(activeToken, activeProfile) : Promise.resolve([]),
        needs.preview ? getGstrPreview(activeToken, activeProfile) : Promise.resolve(null),
        needs.companies ? listTallyCompanies(activeToken, activeProfile.id) : Promise.resolve([])
      ]);
      if (!isCurrent()) return;
      const refreshedProfile = nextProfiles.find((item) => item.id === activeProfile.id) ?? activeProfile;
      setUser(nextUser);
      setProfiles(nextProfiles);
      setActiveProfile(refreshedProfile);
      if (typeof window !== "undefined") {
        window.localStorage.setItem(ACTIVE_PROFILE_KEY, String(refreshedProfile.id));
      }
      setSummary(nextSummary);
      setTransactions(nextRows);
      setBatches(nextBatches);
      setPreview(nextPreview);
      setCompanies(nextCompanies);
      setError("");
    } catch (exc) {
      if (isCurrent()) setError(exc instanceof Error ? exc.message : "Could not refresh workspace");
    } finally {
      if (isCurrent()) setLoading(false);
    }
  }, [clearPeriodScopedState, needs]);

  const refresh = useCallback(async (profileOverride?: Profile) => {
    const activeToken = token || getStoredAuthToken();
    const activeProfile = profileOverride || profile;
    await refreshWorkspace(activeToken, activeProfile);
  }, [profile, refreshWorkspace, token]);

  useEffect(() => {
    const storedToken = getStoredAuthToken();
    if (!storedToken) {
      getMarketplaces()
        .then((result) => setMarketplaces(result.marketplaces))
        .catch(() => setMarketplaces([]));
      setLoading(false);
      return;
    }
    setToken(storedToken);
    getMarketplaces()
      .then((result) => setMarketplaces(result.marketplaces))
      .catch(() => setMarketplaces([]));
    const initializer = Promise.all([getCurrentUser(storedToken), listProfiles(storedToken)])
      .then(([user, profiles]) => {
        const storedProfileId = typeof window !== "undefined" ? Number(window.localStorage.getItem(ACTIVE_PROFILE_KEY) || 0) : 0;
        const profile = profiles.find((item) => item.id === storedProfileId) ?? profiles[0] ?? null;
        return { token: storedToken, user, profiles, profile };
      });
    initializer
      .then(async ({ token, user, profiles, profile }) => {
        setToken(token);
        setUser(user);
        setProfiles(profiles);
        setActiveProfile(profile);
        if (profile) {
          await refreshWorkspace(token, profile, { user, profiles });
        } else {
          setLoading(false);
        }
      })
      .catch((exc) => {
        clearAuthToken();
        setToken("");
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
    marketplaces,
    loading,
    error,
    setProfile: selectProfile,
    refresh
  }), [token, user, profile, profiles, summary, transactions, batches, preview, companies, marketplaces, loading, error, selectProfile, refresh]);
}

export function money(value: number | string | null | undefined) {
  return Number(value || 0);
}
