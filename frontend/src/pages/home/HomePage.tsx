import { useState } from "react";
import { http } from "@/shared/api/http";

export function HomePage() {
  const [status, setStatus] = useState<string>("idle");

  async function ping() {
    setStatus("loading");
    try {
      // Expecting backend /api/health later
      await http<{ status: string }>("/health");
      setStatus("ok");
    } catch (e) {
      setStatus("error");
    }
  }

  return (
    <div>
      <h1 style={{ margin: 0 }}>Secret Room</h1>
      <p style={{ opacity: 0.7 }}>
        Next: cookie auth + editor page.
      </p>

      <div style={{ marginTop: 16, display: "flex", gap: 12, alignItems: "center" }}>
        <button onClick={ping} style={{ padding: "8px 12px" }}>
          Ping API
        </button>
        <span style={{ opacity: 0.7 }}>status: {status}</span>
      </div>
    </div>
  );
}