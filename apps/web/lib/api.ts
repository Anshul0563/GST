const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";
const DEMO_EMAIL = "demo@gstbharat.example.com";
const DEMO_PASSWORD = "Password123";

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

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
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

async function auth(path: "/auth/register" | "/auth/login") {
  return request<{ access_token: string }>(path, {
    method: "POST",
    body: JSON.stringify({ email: DEMO_EMAIL, password: DEMO_PASSWORD, full_name: "Demo Seller" })
  });
}

export async function ensureDemoWorkspace() {
  let token = typeof window !== "undefined" ? window.localStorage.getItem("gst_bharat_token") : null;
  if (!token) {
    try {
      token = (await auth("/auth/register")).access_token;
    } catch {
      token = (await auth("/auth/login")).access_token;
    }
    window.localStorage.setItem("gst_bharat_token", token);
  }
  try {
    await request("/auth/me", {}, token);
  } catch {
    try {
      token = (await auth("/auth/login")).access_token;
    } catch {
      token = (await auth("/auth/register")).access_token;
    }
    window.localStorage.setItem("gst_bharat_token", token);
  }
  await request("/demo/seed", { method: "POST" }, token);
  const profiles = await request<Profile[]>("/gst-profile", {}, token);
  return { token, profile: profiles[0] };
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

export function uploadMarketplaceFiles(token: string, profileId: number, platform: string, files: FileList) {
  const form = new FormData();
  Array.from(files).forEach((file) => form.append("files", file));
  return request(`/imports/${platform}/upload?profile_id=${profileId}`, { method: "POST", body: form }, token);
}

export function generateGstr1(token: string, profile: Profile) {
  return request<{ status: string; json: Gstr1Payload; download_json: string; download_excel: string }>("/gstr1/generate", {
    method: "POST",
    body: JSON.stringify({ profile_id: profile.id, period: profile.return_period })
  }, token);
}
