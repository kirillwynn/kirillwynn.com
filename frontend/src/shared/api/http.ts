import { env } from "@/shared/config/env";

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export class HttpError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.name = "HttpError";
    this.status = status;
    this.payload = payload;
  }
}

// --- CSRF (SPA) -------------------------------------------------
// We keep cookie+session auth and send CSRF token in a header for unsafe methods.
// Token is fetched from GET /api/csrf and cached in memory.
//
// Important: different Flask CSRF setups expect different header names.
// To maximize compatibility, we set BOTH:
// - X-CSRFToken
// - X-CSRF-Token
// ---------------------------------------------------------------

let csrfToken: string | null = null;
let csrfPromise: Promise<string> | null = null;

async function getCsrfToken(signal?: AbortSignal): Promise<string> {
  if (csrfToken) return csrfToken;
  if (csrfPromise) return csrfPromise;

  const url = `${env.apiBaseUrl}/api/csrf`;

  csrfPromise = fetch(url, {
    method: "GET",
    credentials: "include",
    headers: { Accept: "application/json" },
    signal,
  })
    .then(async (res) => {
      const contentType = res.headers.get("content-type") ?? "";
      const isJson = contentType.includes("application/json");
      const payload = isJson ? await res.json().catch(() => null) : null;

      if (!res.ok) {
        const msg =
          typeof payload === "object" && payload && "error" in (payload as any)
            ? String((payload as any).error)
            : `HTTP ${res.status}`;
        throw new HttpError(msg, res.status, payload);
      }

      const t = (payload as any)?.csrf_token;
      if (!t || typeof t !== "string") {
        throw new Error("CSRF endpoint returned no csrf_token");
      }

      csrfToken = t;
      return t;
    })
    .finally(() => {
      csrfPromise = null;
    });

  return csrfPromise;
}

function isUnsafe(method: HttpMethod) {
  return method === "POST" || method === "PUT" || method === "PATCH" || method === "DELETE";
}

// Minimal, production-grade-ish wrapper:
// - base URL from env
// - JSON by default
// - credentials included (cookie-based auth)
// - CSRF header for unsafe methods
// - consistent error handling
export async function http<TResponse>(
  path: string,
  options: {
    method?: HttpMethod;
    body?: unknown;
    headers?: Record<string, string>;
    signal?: AbortSignal;
    keepalive?: boolean;
  } = {},
): Promise<TResponse> {
  const method: HttpMethod = options.method ?? "GET";
  const url = `${env.apiBaseUrl}${path.startsWith("/") ? path : `/${path}`}`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers ?? {}),
  };

  if (isUnsafe(method)) {
    const token = await getCsrfToken(options.signal);

    // Some Flask CSRF protectors expect "X-CSRF-Token" (with dash),
    // others accept "X-CSRFToken". Send both to be safe.
    headers["X-CSRFToken"] = token;
    headers["X-CSRF-Token"] = token;
  }

  // Prepare body once (also helps keepalive sizing).
  const bodyStr = options.body === undefined ? undefined : JSON.stringify(options.body);

  // Keepalive requests have a payload size limit in browsers.
  // If too large, we disable keepalive and still try a normal fetch.
  let keepalive = !!options.keepalive;
  if (keepalive && bodyStr && bodyStr.length > 60000) {
    keepalive = false;
  }

  const res = await fetch(url, {
    method,
    credentials: "include",
    headers,
    body: bodyStr,
    signal: options.signal,
    keepalive,
  });

  const contentType = res.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  const payload = isJson ? await res.json().catch(() => null) : await res.text().catch(() => null);

  if (!res.ok) {
    const msg =
      typeof payload === "object" && payload && "error" in (payload as any)
        ? String((payload as any).error)
        : `HTTP ${res.status}`;

    throw new HttpError(msg, res.status, payload);
  }

  return payload as TResponse;
}
