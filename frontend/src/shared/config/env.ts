// Centralized environment access.
// Keeps config typed and easy to audit.
export const env = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL as string,
} as const;
