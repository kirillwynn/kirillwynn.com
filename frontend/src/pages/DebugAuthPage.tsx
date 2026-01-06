// frontend/src/pages/DebugAuthPage.tsx
// Debug page for verifying cookie-session auth through Vite proxy.
// - Shows current auth state
// - Lets you call /api/auth/me, /api/auth/login, /api/auth/logout from the browser

import { useState } from "react";
import { auth } from "@/lib/auth";
import { useAuth } from "@/lib/AuthProvider";

export function DebugAuthPage() {
  const a = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState<string>("");

  async function onMe() {
    setMsg("loading...");
    try {
      await auth.init();
      setMsg("ok");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "error");
    }
  }

  async function onLogin() {
    setMsg("loading...");
    try {
      await auth.login(email, password);
      setMsg("ok");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "error");
    }
  }

  async function onLogout() {
    setMsg("loading...");
    try {
      await auth.logout();
      setMsg("ok");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "error");
    }
  }

  return (
    <div style={{ padding: 24, fontFamily: "ui-sans-serif, system-ui" }}>
      <h1 style={{ fontSize: 20, marginBottom: 12 }}>Debug Auth</h1>

      <pre style={{ background: "#111", color: "#eee", padding: 12, borderRadius: 8 }}>
{JSON.stringify(a, null, 2)}
      </pre>

      <div style={{ marginTop: 16, display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button onClick={onMe}>Refresh /me</button>
        <button onClick={onLogout}>Logout</button>
      </div>

      <div style={{ marginTop: 16, display: "grid", gap: 8, maxWidth: 420 }}>
        <input
          placeholder="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <input
          placeholder="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <button onClick={onLogin}>Login</button>
      </div>

      <div style={{ marginTop: 12 }}>
        <b>Status:</b> {msg}
      </div>
    </div>
  );
}
