// frontend/src/pages/editor/EditorPage.tsx
//
// Editor page (v1).
// - Loads post by id from API
// - Shows metadata (status + timestamps)
// - Title is editable AND autosaves on blur/Enter via PATCH /api/posts/:id
// - No body editor / publish logic yet

import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { getPost, type PostItem } from "@/api/posts";
import { http, HttpError } from "@/shared/api/http";

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

type PatchPostResponse = {
  ok: boolean;
  item?: PostItem;
  error?: string;
};

export function EditorPage() {
  const params = useParams();

  const postId = useMemo(() => {
    const raw = (params as any).id ?? (params as any).postId;
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  }, [params]);

  const [state, setState] = useState<LoadState>({ kind: "idle" });

  // Local draft (editable)
  const [titleDraft, setTitleDraft] = useState("");
  // Remember what we last synced from server (to avoid redundant PATCHes)
  const lastServerTitleRef = useRef<string>("");

  const [isSavingTitle, setIsSavingTitle] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      if (!postId) {
        setState({ kind: "error", message: "Missing or invalid post id in URL." });
        return;
      }

      setState({ kind: "loading" });
      setSaveError(null);

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

  // Hydrate draft from server when post is loaded/changed
  useEffect(() => {
    if (state.kind === "ready") {
      const serverTitle = state.post.title ?? "";
      setTitleDraft(serverTitle);
      lastServerTitleRef.current = serverTitle;
      setSaveError(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.kind, state.kind === "ready" ? state.post.id : null]);

  async function saveTitleIfNeeded(nextTitle: string) {
    if (!postId) return;
    if (state.kind !== "ready") return;

    const trimmed = nextTitle; // (не трогаем пробелы — решишь позже)
    if (trimmed === lastServerTitleRef.current) return;

    setIsSavingTitle(true);
    setSaveError(null);

    try {
      const res = await http<PatchPostResponse>(`/api/posts/${postId}`, {
        method: "PATCH",
        body: { title: trimmed },
      });

      if (!res.ok || !res.item) {
        setSaveError(res.error || "Failed to save title.");
        return;
      }

      // Update UI with server-confirmed post
      lastServerTitleRef.current = res.item.title ?? "";

      setState((prev) => {
        if (prev.kind !== "ready") return prev;
        return { kind: "ready", post: res.item! };
      });

      // Keep draft in sync with what server stored
      setTitleDraft(res.item.title ?? "");
    } catch (e: any) {
      if (e instanceof HttpError) {
        setSaveError(e.message || `HTTP ${e.status}`);
      } else {
        setSaveError(e?.message || "Unexpected error while saving title.");
      }
    } finally {
      setIsSavingTitle(false);
    }
  }

  const statusValue = state.kind === "ready" ? state.post.status ?? "—" : "—";

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

        {/* Title save status */}
        <div style={{ marginLeft: "auto" }}>
          {isSavingTitle ? (
            <span style={{ opacity: 0.75 }}>Saving…</span>
          ) : saveError ? (
            <span style={{ color: "crimson" }}>Save failed: {saveError}</span>
          ) : (
            <span style={{ opacity: 0.6 }}> </span>
          )}
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

      {/* Title (autosave on blur/Enter) */}
      <div style={{ marginBottom: 12 }}>
        <input
          placeholder="Post title"
          value={titleDraft}
          onChange={(e) => setTitleDraft(e.target.value)}
          onBlur={() => saveTitleIfNeeded(titleDraft)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              // Enter triggers a save; blur also runs but saveTitleIfNeeded is idempotent.
              (e.currentTarget as HTMLInputElement).blur();
            }
          }}
          disabled={state.kind !== "ready"}
          style={{
            width: "100%",
            fontSize: 18,
            padding: "10px 12px",
            borderRadius: 10,
            border: "1px solid rgba(0,0,0,0.2)",
            opacity: state.kind !== "ready" ? 0.7 : 1,
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
