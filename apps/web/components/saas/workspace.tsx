"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import {
  BatchStatus,
  ApiError,
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

type WorkspaceUser = {
  id: number;
  email: string;
  full_name?: string | null;
  role?: string;
  plan?: string;
  subscription_status?: string;
  subscription_expires_at?: string | null;
  free_access_reason?: string | null;
} | null;

function activeProfileKey(user: WorkspaceUser) {
  return user?.id ? `${ACTIVE_PROFILE_KEY}:${user.id}` : ACTIVE_PROFILE_KEY;
}

function rememberActiveProfile(user: WorkspaceUser, profile: Profile | null) {
  if (typeof window === "undefined") return;
  const key = activeProfileKey(user);
  if (profile) {
    window.localStorage.setItem(key, String(profile.id));
    window.localStorage.setItem(ACTIVE_PROFILE_KEY, String(profile.id));
  } else {
    window.localStorage.removeItem(key);
    window.localStorage.removeItem(ACTIVE_PROFILE_KEY);
  }
}

function selectStoredProfile(user: WorkspaceUser, profiles: Profile[]) {
  const storedProfileId = typeof window !== "undefined"
    ? Number(window.localStorage.getItem(activeProfileKey(user)) || window.localStorage.getItem(ACTIVE_PROFILE_KEY) || 0)
    : 0;
  const profile = profiles.find((item) => item.id === storedProfileId) ?? profiles[0] ?? null;
  rememberActiveProfile(user, profile);
  return profile;
}

export type Workspace = {
  token: string;
  user: WorkspaceUser;
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
    rememberActiveProfile(user, nextProfile);
    setActiveProfile(nextProfile);
    clearPeriodScopedState();
    setLoading(true);
  }, [clearPeriodScopedState, user]);

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
        const nextProfile = selectStoredProfile(nextUser, nextProfiles);
        setUser(nextUser);
        setProfiles(nextProfiles);
        setActiveProfile(nextProfile);
        clearPeriodScopedState();
        setError("");
        return;
      }
      const [nextUser, nextProfiles] = await Promise.all([
        base ? Promise.resolve(base.user) : getCurrentUser(activeToken),
        base ? Promise.resolve(base.profiles) : listProfiles(activeToken),
      ]);
      if (!isCurrent()) return;
      const refreshedProfile = nextProfiles.find((item) => item.id === activeProfile.id) ?? nextProfiles[0] ?? null;
      if (!refreshedProfile) {
        setUser(nextUser);
        setProfiles(nextProfiles);
        setActiveProfile(null);
        rememberActiveProfile(nextUser, null);
        clearPeriodScopedState();
        setError("");
        return;
      }
      const [nextSummary, nextRows, nextBatches, nextPreview, nextCompanies] = await Promise.all([
        needs.summary ? getSummary(activeToken, refreshedProfile) : Promise.resolve(null),
        needs.transactions ? getTransactions(activeToken, refreshedProfile) : Promise.resolve([]),
        needs.batches ? listImportBatches(activeToken, refreshedProfile) : Promise.resolve([]),
        needs.preview ? getGstrPreview(activeToken, refreshedProfile) : Promise.resolve(null),
        needs.companies ? listTallyCompanies(activeToken, refreshedProfile.id) : Promise.resolve([])
      ]);
      if (!isCurrent()) return;
      setUser(nextUser);
      setProfiles(nextProfiles);
      setActiveProfile(refreshedProfile);
      rememberActiveProfile(nextUser, refreshedProfile);
      setSummary(nextSummary);
      setTransactions(nextRows);
      setBatches(nextBatches);
      setPreview(nextPreview);
      setCompanies(nextCompanies);
      setError("");
    } catch (exc) {
      if (!isCurrent()) return;
      if (exc instanceof ApiError && exc.status === 401) {
        clearAuthToken();
        setToken("");
        setUser(null);
        clearPeriodScopedState();
      }
      setError(exc instanceof Error ? exc.message : "Could not refresh workspace");
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
        const profile = selectStoredProfile(user, profiles);
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
        if (exc instanceof ApiError && exc.status === 401) {
          clearAuthToken();
          setToken("");
          setUser(null);
        } else {
          setToken(storedToken);
        }
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
