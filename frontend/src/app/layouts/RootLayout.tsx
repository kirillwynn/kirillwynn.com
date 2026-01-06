// frontend/src/app/layouts/RootLayout.tsx
// App shell layout.
// - Shows a minimal top bar
// - Displays current user email (if authenticated)
// - Provides logout action

import React, { useState } from "react";
import { Link, Outlet, useNavigate } from "react-router-dom";

import { auth } from "@/lib/auth";
import { useAuth } from "@/lib/AuthProvider";

export function RootLayout() {
  const a = useAuth();
  const nav = useNavigate();

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>("");

  async function onLogout() {
    setError("");
    setBusy(true);
    try {
      await auth.logout();
      nav("/", { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Logout failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <header
        style={{
          borderBottom: "1px solid rgba(0,0,0,0.12)",
          padding: "12px 20px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <strong>Secret Room</strong>
          <span style={{ opacity: 0.6, fontSize: 12 }}>admin</span>

          {a.loading ? (
            <span style={{ opacity: 0.6, fontSize: 12 }}>Checking session...</span>
          ) : a.user ? (
            <span style={{ opacity: 0.75, fontSize: 12 }}>{a.user.email}</span>
          ) : null}
        </div>

        <nav style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Link to="/app" style={{ textDecoration: "none" }}>
            Home
          </Link>

          <Link to="/app/posts" style={{ textDecoration: "none" }}>
            Posts
          </Link>

          <button
            type="button"
            onClick={onLogout}
            disabled={busy || a.loading || !a.authenticated}
            style={{
              padding: "8px 10px",
              borderRadius: 10,
              border: "1px solid rgba(0,0,0,0.2)",
              background: "white",
              cursor: busy || a.loading || !a.authenticated ? "default" : "pointer",
              fontWeight: 600,
            }}
          >
            {busy ? "Logging out..." : "Logout"}
          </button>
        </nav>
      </header>

      {error ? (
        <div
          role="alert"
          style={{
            padding: "10px 20px",
            borderBottom: "1px solid rgba(255,0,0,0.25)",
            background: "rgba(255,0,0,0.06)",
            fontFamily: "ui-sans-serif, system-ui",
          }}
        >
          {error}
        </div>
      ) : null}

      <main style={{ flex: 1, padding: 20 }}>
        <Outlet />
      </main>
    </div>
  );
}
