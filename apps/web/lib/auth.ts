const TOKEN_KEY = "gst_bharat_token";

type JwtPayload = {
  exp?: number;
};

function decodeJwtPayload(token: string): JwtPayload | null {
  try {
    const payload = token.split(".")[1];
    if (!payload || typeof window === "undefined") return null;
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
    return JSON.parse(window.atob(padded)) as JwtPayload;
  } catch {
    return null;
  }
}

export function persistAuthToken(token: string) {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearAuthToken() {
  window.localStorage.removeItem(TOKEN_KEY);
}

export function getStoredAuthToken() {
  if (typeof window === "undefined") return "";
  const token = window.localStorage.getItem(TOKEN_KEY) || "";
  if (!token) return "";
  const payload = decodeJwtPayload(token);
  if (payload?.exp && payload.exp * 1000 <= Date.now()) {
    clearAuthToken();
    return "";
  }
  return token;
}
