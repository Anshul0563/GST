const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

export type Profile = {
  id: number;
  gstin: string;
  legal_name: string;
  trade_name?: string | null;
  state_code: string;
  filing_frequency: string;
  financial_year: string;
  return_period: string;
};

export type Transaction = {
  id: number;
  platform: string;
  gstin: string;
  etin: string | null;
  filing_period: string;
  order_id: string | null;
  order_item_id: string | null;
  invoice_no: string | null;
  invoice_date: string | null;
  doc_type: string;
  buyer_state_code: string | null;
  buyer_state_name: string | null;
  hsn: string | null;
  product_name: string | null;
  sku: string | null;
  qty: number | string;
  taxable_value: number | string;
  gst_rate: number | string;
  igst: number | string;
  cgst: number | string;
  sgst: number | string;
  cess: number | string;
  tcs: number | string;
  tds: number | string;
  gross_amount: number | string;
  discount_seller: number | string;
  discount_platform: number | string;
  settlement_amount: number | string;
  source_file: string | null;
  validation_status: string;
  validation_errors: string | null;
};

export type DashboardSummary = {
  total_sales: number | string;
  total_taxable_value: number | string;
  total_gst: number | string;
  igst: number | string;
  cgst: number | string;
  sgst: number | string;
  platform_wise_sale: Array<{ platform: string; taxable_value: number | string; gst: number | string; rows: number }>;
  state_wise_sale: Array<{ state_code: string; taxable_value: number | string; gst: number | string; rows: number }>;
  uploaded_files: number;
  pending_errors: number;
  json_generation_status: string;
};

export type Gstr1Payload = {
  gstin: string;
  fp: string;
  version: string;
  hash: string;
  b2cs: Array<{ sply_ty: string; rt: number; typ: string; pos: string; txval: number; iamt: number; camt: number; samt: number; csamt: number }>;
  supeco: { supeco_det: Array<Record<string, string | number>> };
  doc_issue: { doc_det: Array<Record<string, unknown>> };
};

export type BatchStatus = {
  id: number;
  platform: string;
  status: string;
  parsed_rows: number;
  error_rows: number;
  errors?: Array<Record<string, unknown>>;
};

export type ImportErrors = {
  parser_errors: Array<Record<string, unknown>>;
  row_errors: Transaction[];
};

export type TallyCompany = {
  id: number;
  company_name: string;
  gstin?: string | null;
  financial_year?: string | null;
  state?: string | null;
  auto_create_ledger?: boolean;
  tally_guid?: string | null;
};

export type ReconcileReport = {
  id: number;
  status: string;
  categories?: string[];
  summary?: Record<string, number | string | unknown[]>;
  rows?: ReconcileRow[];
};

export type ReconcileRow = {
  id: number;
  supplier_gstin: string | null;
  invoice_no: string | null;
  invoice_date: string | null;
  taxable_value: number | string;
  igst: number | string;
  cgst: number | string;
  sgst: number | string;
  total_tax: number | string;
  tax_difference: number | string;
  match_score: number | string;
  category: string;
  mismatch_reason: string | null;
};

export type ReconcileHistoryItem = {
  id: number;
  profile_id: number;
  status: string;
  portal_rows: number;
  book_rows: number;
  matched_rows: number;
  mismatch_rows: number;
  tax_difference: number | string;
  itc_risk_amount: number | string;
  summary: Record<string, number | string | unknown[]>;
  created_at: string;
};

export type TallyExportItem = {
  id: number;
  profile_id: number;
  company_id: number;
  period: string;
  voucher_count: number;
  status: string;
  validation: Record<string, unknown>;
  created_at: string;
};

export type BillingPlan = {
  id: string;
  name: string;
  monthly_amount: number;
  yearly_amount: number;
  currency: string;
  features: string[];
};

export type BillingStatus = {
  role: string;
  plan: string;
  subscription_status: string;
  free_access: boolean;
  free_access_reason?: string | null;
  latest_order?: {
    id: number;
    plan_id: string;
    billing_cycle: string;
    amount: number;
    status: string;
    provider_order_id?: string | null;
  } | null;
};

export type PaymentOrder = {
  id?: number;
  free_access?: boolean;
  message?: string;
  provider?: string;
  provider_order_id?: string;
  amount?: number;
  amount_paise?: number;
  currency?: string;
  plan_id?: string;
  billing_cycle?: string;
  gateway_key_id?: string | null;
  gateway_configured?: boolean;
};

export async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers
    }
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export function loginUser(payload: { email: string; password: string }) {
  return request<{ access_token: string; token_type: string }>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function registerUser(payload: { email: string; password: string; full_name?: string }) {
  return request<{ access_token: string; token_type: string }>("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getCurrentUser(token: string) {
  return request<{ id: number; email: string; full_name?: string | null; role?: string; plan?: string; subscription_status?: string; free_access_reason?: string | null }>("/auth/me", {}, token);
}

export async function loadWorkspace(token: string) {
  const user = await getCurrentUser(token);
  const profiles = await listProfiles(token);
  return { user, profiles, profile: profiles[0] ?? null };
}

export function listProfiles(token: string) {
  return request<Profile[]>("/gst-profile", {}, token);
}

export function getSummary(token: string, profile: Profile) {
  return request<DashboardSummary>(`/dashboard/summary?profile_id=${profile.id}&period=${profile.return_period}`, {}, token);
}

export function getTransactions(token: string, profile: Profile) {
  return request<Transaction[]>(`/transactions?profile_id=${profile.id}&period=${profile.return_period}`, {}, token);
}

export function getGstrPreview(token: string, profile: Profile) {
  return request<Gstr1Payload>(`/gstr1/preview/${profile.return_period}?profile_id=${profile.id}`, {}, token);
}

export function createProfile(token: string, payload: Omit<Profile, "id" | "state_code">) {
  return request<Profile>("/gst-profile", { method: "POST", body: JSON.stringify(payload) }, token);
}

export function updateProfile(token: string, profileId: number, payload: Omit<Profile, "id" | "state_code">) {
  return request<Profile>(`/gst-profile/${profileId}`, { method: "PUT", body: JSON.stringify(payload) }, token);
}

export function uploadMarketplaceFiles(token: string, profileId: number, platform: string, files: FileList | File[]) {
  const form = new FormData();
  Array.from(files).forEach((file) => form.append("files", file));
  return request<BatchStatus>(`/imports/${platform}/upload?profile_id=${profileId}`, { method: "POST", body: form }, token);
}

export function listImportBatches(token: string, profileId?: number) {
  return request<BatchStatus[]>(`/imports${profileId ? `?profile_id=${profileId}` : ""}`, {}, token);
}

export function getImportStatus(token: string, batchId: number) {
  return request<BatchStatus>(`/imports/${batchId}/status`, {}, token);
}

export function getImportErrors(token: string, batchId: number) {
  return request<ImportErrors>(`/imports/${batchId}/errors`, {}, token);
}

export function updateTransaction(token: string, transactionId: number, payload: Partial<Transaction>) {
  return request<Transaction>(`/transactions/${transactionId}`, { method: "PUT", body: JSON.stringify(payload) }, token);
}

export function deleteTransaction(token: string, transactionId: number) {
  return request<{ ok: boolean }>(`/transactions/${transactionId}`, { method: "DELETE" }, token);
}

export function generateGstr1(token: string, profile: Profile) {
  return request<{ status: string; json: Gstr1Payload; download_json: string; download_excel: string }>("/gstr1/generate", {
    method: "POST",
    body: JSON.stringify({ profile_id: profile.id, period: profile.return_period })
  }, token);
}

export function downloadUrl(path: string) {
  return `${API_BASE}${path}`;
}

export function createTallyCompany(token: string, payload: { profile_id: number; company_name: string; gstin?: string; financial_year?: string; state?: string; auto_create_ledger?: boolean; tally_guid?: string }) {
  return request<TallyCompany>("/tally/company", { method: "POST", body: JSON.stringify(payload) }, token);
}

export function listTallyCompanies(token: string, profileId?: number) {
  return request<TallyCompany[]>(`/tally/companies${profileId ? `?profile_id=${profileId}` : ""}`, {}, token);
}

export function generateTallyXml(token: string, payload: { profile_id: number; period: string; company_id: number; ledger_mapping: Record<string, string>; auto_create_ledgers?: boolean }) {
  return request<{ id: number; voucher_count: number; validation: Record<string, unknown>; download: string; download_excel: string }>("/tally/generate", { method: "POST", body: JSON.stringify(payload) }, token);
}

export function uploadReconcileFiles(token: string, profileId: number, portalFile: File, booksFile: File) {
  const form = new FormData();
  form.append("portal_file", portalFile);
  form.append("books_file", booksFile);
  return request<ReconcileReport>(`/reconcile/upload?profile_id=${profileId}`, { method: "POST", body: form }, token);
}

export function uploadReconcileFilesV2(token: string, profileId: number, portalFile: File, booksFile: File, settings: { tax_tolerance: string; date_tolerance_days: number; enable_date_tolerance: boolean; enable_fuzzy_invoice: boolean }) {
  const form = new FormData();
  form.append("portal_file", portalFile);
  form.append("books_file", booksFile);
  const params = new URLSearchParams({
    profile_id: String(profileId),
    tax_tolerance: settings.tax_tolerance,
    date_tolerance_days: String(settings.date_tolerance_days),
    enable_date_tolerance: String(settings.enable_date_tolerance),
    enable_fuzzy_invoice: String(settings.enable_fuzzy_invoice)
  });
  return request<ReconcileReport>(`/reconcile/upload?${params.toString()}`, { method: "POST", body: form }, token);
}

export function getReconcileReport(token: string, batchId: number) {
  return request<ReconcileReport>(`/reconcile/report/${batchId}`, {}, token);
}

export function getReconcileResults(token: string, batchId: number, category?: string) {
  return request<ReconcileReport>(`/reconcile/results/${batchId}${category ? `?category=${category}` : ""}`, {}, token);
}

export function getReconcileHistory(token: string, profileId?: number) {
  return request<ReconcileHistoryItem[]>(`/reconcile/history${profileId ? `?profile_id=${profileId}` : ""}`, {}, token);
}

export function getReconcileDownloadUrl(batchId: number) {
  return downloadUrl(`/reconcile/download/${batchId}`);
}

export function getBillingPlans(token: string) {
  return request<{ plans: BillingPlan[]; gateway: string; free_access: boolean }>("/billing/plans", {}, token);
}

export function getBillingStatus(token: string) {
  return request<BillingStatus>("/billing/status", {}, token);
}

export function createBillingOrder(token: string, payload: { plan_id: string; billing_cycle: string }) {
  return request<PaymentOrder>("/billing/create-order", { method: "POST", body: JSON.stringify(payload) }, token);
}

export function verifyBillingPayment(token: string, payload: { order_id: number; razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }) {
  return request<{ status: string; plan: string; subscription_status: string }>("/billing/verify", { method: "POST", body: JSON.stringify(payload) }, token);
}

export function getTallyHistory(token: string, profileId?: number) {
  return request<TallyExportItem[]>(`/tally/history${profileId ? `?profile_id=${profileId}` : ""}`, {}, token);
}

export function getTallyExportUrl(exportId: number, format: "xml" | "xlsx" = "xml") {
  return downloadUrl(`/tally/export/${exportId}${format === "xlsx" ? "?format=xlsx" : ""}`);
}
