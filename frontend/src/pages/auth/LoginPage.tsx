// frontend/src/pages/auth/LoginPage.tsx
// Minimal login page for cookie-session auth.
// - Shows backend error messages
// - Disables form while submitting
// - Door lives at / (no /login route)
// - If already authenticated: shows a friendly "Already signed in" screen

import { useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { auth } from "@/lib/auth";
import { useAuth } from "@/lib/AuthProvider";

function getRedirectTarget(search: string): string {
  const params = new URLSearchParams(search);
  const next = params.get("next");
  // Keep it safe: only allow internal absolute paths
  if (next && next.startsWith("/")) return next;
  // Default landing after login
  return "/app";
}

export function LoginPage() {
  const a = useAuth();
  const nav = useNavigate();
  const loc = useLocation();

  const nextPath = useMemo(() => getRedirectTarget(loc.search), [loc.search]);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string>("");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      await auth.login(email, password);
      nav(nextPath, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function onLogout() {
    setError("");
    setSubmitting(true);
    try {
      await auth.logout();
      // Door is /
      nav("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Logout failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (a.loading) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "grid",
          placeItems: "center",
          padding: 24,
          fontFamily: "ui-sans-serif, system-ui",
        }}
      >
        <div style={{ opacity: 0.75 }}>Checking session...</div>
      </div>
    );
  }

  if (a.authenticated && a.user) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "grid",
          placeItems: "center",
          padding: 24,
          fontFamily: "ui-sans-serif, system-ui",
        }}
      >
        <div style={{ width: "100%", maxWidth: 420 }}>
          <h1 style={{ fontSize: 22, marginBottom: 6 }}>Already signed in</h1>
          <p style={{ opacity: 0.75, marginTop: 0, marginBottom: 16 }}>
            {a.user.email}
          </p>

          {error ? (
            <div
              role="alert"
              style={{
                marginBottom: 12,
                padding: 10,
                borderRadius: 10,
                background: "rgba(255,0,0,0.08)",
                border: "1px solid rgba(255,0,0,0.25)",
              }}
            >
              {error}
            </div>
          ) : null}

          <div style={{ display: "flex", gap: 10 }}>
            <button
              type="button"
              onClick={() => nav(nextPath, { replace: true })}
              disabled={submitting}
              style={{
                flex: 1,
                padding: "10px 12px",
                borderRadius: 10,
                border: "1px solid rgba(0,0,0,0.2)",
                background: "white",
                cursor: submitting ? "default" : "pointer",
                fontWeight: 600,
              }}
            >
              Enter
            </button>

            <button
              type="button"
              onClick={onLogout}
              disabled={submitting}
              style={{
                padding: "10px 12px",
                borderRadius: 10,
                border: "1px solid rgba(0,0,0,0.2)",
                background: submitting ? "rgba(0,0,0,0.05)" : "white",
                cursor: submitting ? "default" : "pointer",
                fontWeight: 600,
              }}
            >
              Logout
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        padding: 24,
        fontFamily: "ui-sans-serif, system-ui",
      }}
    >
      <div style={{ width: "100%", maxWidth: 420 }}>
        <h1 style={{ fontSize: 22, marginBottom: 6 }}>Secret Room</h1>
        <p style={{ opacity: 0.75, marginTop: 0, marginBottom: 16 }}>
          Sign in to enter.
        </p>

        <form
          onSubmit={onSubmit}
          style={{
            display: "grid",
            gap: 10,
            padding: 16,
            border: "1px solid rgba(0,0,0,0.12)",
            borderRadius: 12,
          }}
        >
          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 12, opacity: 0.7 }}>Email</span>
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              inputMode="email"
              placeholder="you@example.com"
              disabled={submitting}
              style={{
                padding: "10px 12px",
                borderRadius: 10,
                border: "1px solid rgba(0,0,0,0.2)",
              }}
            />
          </label>

          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 12, opacity: 0.7 }}>Password</span>
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              autoComplete="current-password"
              placeholder="••••••••"
              disabled={submitting}
              style={{
                padding: "10px 12px",
                borderRadius: 10,
                border: "1px solid rgba(0,0,0,0.2)",
              }}
            />
          </label>

          {error ? (
            <div
              role="alert"
              style={{
                marginTop: 6,
                padding: 10,
                borderRadius: 10,
                background: "rgba(255,0,0,0.08)",
                border: "1px solid rgba(255,0,0,0.25)",
              }}
            >
              {error}
            </div>
          ) : null}

          <button
            type="submit"
            disabled={submitting || !email || !password}
            style={{
              marginTop: 6,
              padding: "10px 12px",
              borderRadius: 10,
              border: "1px solid rgba(0,0,0,0.2)",
              background: submitting ? "rgba(0,0,0,0.05)" : "white",
              cursor: submitting ? "default" : "pointer",
              fontWeight: 600,
            }}
          >
            {submitting ? "Signing in..." : "Enter"}
          </button>
        </form>
      </div>
    </div>
  );
}
