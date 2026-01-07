// frontend/src/lib/api.ts
// Centralized HTTP client for the frontend.
// - Uses cookie-based session auth
// - Always sends credentials (cookies)
// - Designed to mirror production behavior via Nginx proxy

export type ApiUser = {
  id: number;
  email: string;
  name: string | null;
  is_admin: boolean;
};

export type ApiMeResponse =
  | { authenticated: true; user: ApiUser }
  | { authenticated: false; user: null };

export type ApiLoginResponse =
  | { ok: true; user: ApiUser }
  | { ok: false; error: string };

export type ApiPostStatus = "draft" | "published" | string;

export type ApiPostListItem = {
  id: number;
  title: string;
  slug: string;
  status: ApiPostStatus;
  updated_at: string | null;
  published_at: string | null;
};

export type ApiPostsListResponse =
  | { ok: true; items: ApiPostListItem[] }
  | { ok: false; error: string };

export type ApiPostCreateResponse =
  | { ok: true; post: { id: number; title: string; slug: string; status: ApiPostStatus } }
  | { ok: false; error: string };

// Low-level request helper.
// - Always includes cookies
// - Gracefully handles non-JSON error responses from Flask
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    ...init,
    credentials: "include", // REQUIRED: send session cookies
    headers: {
      ...(init.headers || {}),
    },
  });

  const contentType = res.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");

  if (!res.ok) {
    const body = isJson
      ? await res.json().catch(() => null)
      : await res.text().catch(() => "");

    const message =
      typeof body === "string"
        ? body
        : body?.error || body?.message || `HTTP ${res.status}`;

    throw new Error(message);
  }

  return (isJson ? await res.json() : await res.text()) as T;
}

// Public API surface used by the app
export const api = {
  // Session check: "who am I?"
  me: () => request<ApiMeResponse>("/api/auth/me"),

  // Login using email + password (cookie session)
  login: (email: string, password: string) =>
    request<ApiLoginResponse>("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }),

  // Logout and destroy session
  logout: () =>
    request<{ ok: true }>("/api/auth/logout", {
      method: "POST",
    }),

  // Posts
  postsList: () => request<ApiPostsListResponse>("/api/posts"),

  postsCreateDraft: () =>
    request<ApiPostCreateResponse>("/api/posts", {
      method: "POST",
    }),
};
