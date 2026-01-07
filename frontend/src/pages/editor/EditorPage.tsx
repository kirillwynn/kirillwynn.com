// frontend/src/pages/editor/EditorPage.tsx
//
// Editor page (v1, read-only).
// - Loads post by id from API
// - Displays basic fields read-only
// - No editor/save/publish logic yet

import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { getPost, type PostItem } from "@/api/posts";

type LoadState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; post: PostItem };

function formatIso(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export function EditorPage() {
  const params = useParams();

  // Accept both :id and :postId to be resilient to router changes.
  const postId = useMemo(() => {
    const raw = (params as any).id ?? (params as any).postId;
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  }, [params]);

  const [state, setState] = useState<LoadState>({ kind: "idle" });

  useEffect(() => {
    let cancelled = false;

    async function run() {
      if (!postId) {
        setState({ kind: "error", message: "Missing or invalid post id in URL." });
        return;
      }

      setState({ kind: "loading" });

      try {
        const res = await getPost(postId);

        if (cancelled) return;

        if (!res.ok) {
          setState({
            kind: "error",
            message: res.error || "Failed to load post.",
          });
          return;
        }

        if (!res.item) {
          setState({ kind: "error", message: "API returned ok=true but no item." });
          return;
        }

        setState({ kind: "ready", post: res.item });
      } catch (e: any) {
        if (cancelled) return;
        setState({
          kind: "error",
          message: e?.message || "Unexpected error while loading post.",
        });
      }
    }

    run();

    return () => {
      cancelled = true;
    };
  }, [postId]);

  const titleValue =
    state.kind === "ready" ? state.post.title ?? "" : "";
  const statusValue =
    state.kind === "ready" ? state.post.status ?? "—" : "—";

  return (
    <div
      style={{
        fontFamily: "ui-sans-serif, system-ui",
        maxWidth: 900,
        margin: "0 auto",
      }}
    >
      <header style={{ marginBottom: 16 }}>
        <h1 style={{ fontSize: 22, marginBottom: 4 }}>Editor</h1>
        <p style={{ opacity: 0.7, margin: 0 }}>
          Post viewer (v1). Editor will come later.
        </p>
      </header>

      {/* Status + timestamps */}
      <div
        style={{
          display: "flex",
          gap: 16,
          flexWrap: "wrap",
          marginBottom: 12,
          opacity: 0.85,
          fontSize: 13,
        }}
      >
        <div>
          <strong>Status:</strong> {statusValue}
        </div>
        <div>
          <strong>Updated:</strong>{" "}
          {state.kind === "ready" ? formatIso(state.post.updated_at) : "—"}
        </div>
        <div>
          <strong>Published:</strong>{" "}
          {state.kind === "ready" ? formatIso(state.post.published_at) : "—"}
        </div>
        <div>
          <strong>Created:</strong>{" "}
          {state.kind === "ready" ? formatIso(state.post.created_at) : "—"}
        </div>
      </div>

      {/* Loading / error */}
      {state.kind === "loading" && (
        <div
          style={{
            padding: 12,
            borderRadius: 10,
            border: "1px solid rgba(0,0,0,0.15)",
            background: "rgba(0,0,0,0.02)",
            marginBottom: 12,
          }}
        >
          Loading…
        </div>
      )}

      {state.kind === "error" && (
        <div
          style={{
            padding: 12,
            borderRadius: 10,
            border: "1px solid rgba(0,0,0,0.15)",
            background: "rgba(255,0,0,0.06)",
            marginBottom: 12,
          }}
        >
          <strong>Failed to load post.</strong>
          <div style={{ opacity: 0.85, marginTop: 6 }}>{state.message}</div>
        </div>
      )}

      {/* Title */}
      <div style={{ marginBottom: 12 }}>
        <input
          placeholder="Post title"
          value={titleValue}
          readOnly
          style={{
            width: "100%",
            fontSize: 18,
            padding: "10px 12px",
            borderRadius: 10,
            border: "1px solid rgba(0,0,0,0.2)",
            background: "rgba(0,0,0,0.02)",
          }}
        />
      </div>

      {/* Body placeholder */}
      <div
        style={{
          minHeight: 300,
          padding: 16,
          borderRadius: 12,
          border: "1px solid rgba(0,0,0,0.2)",
          background: "rgba(0,0,0,0.02)",
          marginBottom: 16,
        }}
      >
        {state.kind === "ready" ? (
          <div style={{ opacity: 0.75 }}>
            Body will be shown here in the next step (when backend returns body fields).
          </div>
        ) : (
          <div style={{ opacity: 0.6 }}>Editor will live here (TipTap / Markdown).</div>
        )}
      </div>

      {/* Actions (disabled for v1) */}
      <div style={{ display: "flex", gap: 10 }}>
        <button
          disabled
          style={{
            padding: "8px 12px",
            borderRadius: 10,
            border: "1px solid rgba(0,0,0,0.2)",
            background: "white",
            fontWeight: 600,
            opacity: 0.6,
            cursor: "not-allowed",
          }}
        >
          Save draft
        </button>

        <button
          disabled
          style={{
            padding: "8px 12px",
            borderRadius: 10,
            border: "1px solid rgba(0,0,0,0.2)",
            background: "white",
            fontWeight: 600,
            opacity: 0.6,
            cursor: "not-allowed",
          }}
        >
          Publish
        </button>
      </div>
    </div>
  );
}
