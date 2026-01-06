// frontend/src/lib/RequireAuth.tsx
// Route guard for pages that require authentication.
// - Waits for auth.init() to finish (loading state)
// - Redirects to / with ?next=... if not authenticated

import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/lib/AuthProvider";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const a = useAuth();
  const loc = useLocation();

  if (a.loading) {
    return (
      <div style={{ padding: 24, fontFamily: "ui-sans-serif, system-ui" }}>
        Checking session...
      </div>
    );
  }

  if (!a.authenticated) {
    const next = encodeURIComponent(loc.pathname + loc.search);
    return <Navigate to={`/?next=${next}`} replace />;
  }

  return <>{children}</>;
}
