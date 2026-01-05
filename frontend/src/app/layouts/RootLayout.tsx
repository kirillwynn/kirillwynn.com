import { Outlet, Link } from "react-router-dom";

export function RootLayout() {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <header
        style={{
          borderBottom: "1px solid rgba(255,255,255,0.08)",
          padding: "12px 20px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <strong>Secret Room</strong>
          <span style={{ opacity: 0.6, fontSize: 12 }}>admin</span>
        </div>

        <nav style={{ display: "flex", gap: 12 }}>
          <Link to="/" style={{ textDecoration: "none" }}>Home</Link>
          <Link to="/login" style={{ textDecoration: "none" }}>Login</Link>
        </nav>
      </header>

      <main style={{ flex: 1, padding: 20 }}>
        <Outlet />
      </main>
    </div>
  );
}