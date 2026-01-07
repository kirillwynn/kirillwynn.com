// frontend/src/shared/config/env.ts
// Centralized environment access.
// - In production we default to same-origin API ("/api") if VITE_API_BASE_URL is not set.

function normalizeBaseUrl(raw: unknown): string {
  const v = typeof raw === "string" ? raw.trim() : "";
  if (!v) return ""; // same-origin
  // remove trailing slash to avoid double slashes when joining
  return v.endsWith("/") ? v.slice(0, -1) : v;
}

export const env = {
  apiBaseUrl: normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL),
} as const;
