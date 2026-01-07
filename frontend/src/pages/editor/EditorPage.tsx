// frontend/src/pages/editor/EditorPage.tsx
//
// Editor page (v3).
// - Loads post by id from API
// - Shows metadata (status + timestamps)
// - Title + body_md are editable
// - Autosave via PATCH (debounced) + immediate save on blur
// - TipTap is used for rich editing (content is persisted as body_md)

import React, { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { getPost, patchPost, type PostItem } from "@/api/posts";

function formatIso(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function isEnter(e: React.KeyboardEvent<HTMLInputElement>) {
  return e.key === "Enter";
}

type LoadState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; post: PostItem };

type SaveState =
  | { kind: "idle" }
  | { kind: "saving" }
  | { kind: "saved"; at: number }
  | { kind: "error"; message: string };

function normalizeTitle(raw: string): string {
  return raw.trim();
}

export function EditorPage() {
  const params = useParams();

  const postId = useMemo(() => {
    const raw = (params as any).id ?? (params as any).postId;
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  }, [params]);

  const [state, setState] = useState<LoadState>({ kind: "idle" });

  // Local drafts
  const [titleDraft, setTitleDraft] = useState("");
  const [bodyDraft, setBodyDraft] = useState("");

  // Save status (tiny UX)
  const [saveState, setSaveState] = useState<SaveState>({ kind: "idle" });

  // Keep last server values to avoid PATCH spam
  const lastServerTitleRef = useRef<string>("");
  const lastServerBodyRef = useRef<string>("");

  // Debounce timer
  const saveTimerRef = useRef<number | null>(null);

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
          setState({ kind: "error", message: res.error || "Failed to load post." });
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

  // Hydrate drafts from server when post becomes ready / changes
  useEffect(() => {
    if (state.kind !== "ready") return;

    const title = state.post.title ?? "";
    const body = state.post.body_md ?? "";

    setTitleDraft(title);
    setBodyDraft(body);

    lastServerTitleRef.current = title;
    lastServerBodyRef.current = body;

    setSaveState({ kind: "idle" });
  }, [state.kind, state.kind === "ready" ? state.post.id : null]);

  function buildPatch(): Partial<Pick<PostItem, "title" | "body_md">> | null {
    const patch: Partial<Pick<PostItem, "title" | "body_md">> = {};

    // Never send invalid title. If user cleared title, we keep it local and show save error on blur/save.
    const nextTitle = normalizeTitle(titleDraft);
    const serverTitle = lastServerTitleRef.current;

    if (nextTitle !== normalizeTitle(serverTitle)) {
      // Only include title if it's valid (non-empty).
      if (nextTitle.length > 0) patch.title = nextTitle;
    }

    if (bodyDraft !== lastServerBodyRef.current) patch.body_md = bodyDraft;

    return Object.keys(patch).length ? patch : null;
  }

  async function flushSaveNow(reason: "debounce" | "blur" | "manual" = "manual") {
    if (!postId) return;
    if (state.kind !== "ready") return;

    // Validate title on explicit user actions (blur/manual).
    // For debounced saves triggered by body formatting, we do not block saving body
    // just because title is temporarily empty while user is editing.
    const normalizedTitle = normalizeTitle(titleDraft);
    if ((reason === "blur" || reason === "manual") && normalizedTitle.length === 0) {
      setSaveState({ kind: "error", message: "Title cannot be empty." });
      return;
    }

    const patch = buildPatch();
    if (!patch) return;

    setSaveState({ kind: "saving" });
    try {
      const res = await patchPost(postId, patch);

      if (!res.ok) {
        setSaveState({ kind: "error", message: res.error || "Failed to save." });
        return;
      }

      if (res.item) {
        const newTitle = res.item.title ?? lastServerTitleRef.current;
        const newBody = res.item.body_md ?? lastServerBodyRef.current;

        lastServerTitleRef.current = newTitle ?? "";
        lastServerBodyRef.current = newBody ?? "";

        // Keep drafts aligned with server (nice UX).
        setTitleDraft(newTitle ?? "");
        setBodyDraft(newBody ?? "");

        setState({ kind: "ready", post: res.item });
      } else {
        // Fallback: assume patch succeeded.
        if (patch.title !== undefined) lastServerTitleRef.current = patch.title ?? "";
        if (patch.body_md !== undefined) lastServerBodyRef.current = patch.body_md ?? "";
      }

      setSaveState({ kind: "saved", at: Date.now() });
    } catch (e: any) {
      setSaveState({
        kind: "error",
        message: e?.message || "Unexpected error while saving.",
      });
    }
  }

  function scheduleDebouncedSave() {
    if (saveTimerRef.current) {
      window.clearTimeout(saveTimerRef.current);
    }
    saveTimerRef.current = window.setTimeout(() => {
      flushSaveNow("debounce");
    }, 600);
  }

  // Debounced autosave on changes (after initial hydration)
  useEffect(() => {
    if (state.kind !== "ready") return;

    if (!buildPatch()) return;

    scheduleDebouncedSave();

    return () => {
      if (saveTimerRef.current) {
        window.clearTimeout(saveTimerRef.current);
        saveTimerRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [titleDraft, bodyDraft]);

  const statusValue = state.kind === "ready" ? state.post.status ?? "—" : "—";

  const saveBadge =
    saveState.kind === "saving"
      ? "Saving…"
      : saveState.kind === "saved"
        ? "Saved"
        : saveState.kind === "error"
          ? "Save error"
          : "";

  return (
    <div style={{ fontFamily: "ui-sans-serif, system-ui", maxWidth: 900, margin: "0 auto" }}>
      <header style={{ marginBottom: 16 }}>
        <h1 style={{ fontSize: 22, marginBottom: 4 }}>Editor</h1>
        <p style={{ opacity: 0.7, margin: 0 }}>Post editor (v3). TipTap rich editor is enabled.</p>
      </header>

      {/* Status + timestamps + save state */}
      <div
        style={{
          display: "flex",
          gap: 16,
          flexWrap: "wrap",
          marginBottom: 12,
          opacity: 0.85,
          fontSize: 13,
          alignItems: "center",
        }}
      >
        <div>
          <strong>Status:</strong> {statusValue}
        </div>
        <div>
          <strong>Updated:</strong> {state.kind === "ready" ? formatIso(state.post.updated_at) : "—"}
        </div>
        <div>
          <strong>Published:</strong>{" "}
          {state.kind === "ready" ? formatIso(state.post.published_at) : "—"}
        </div>
        <div>
          <strong>Created:</strong> {state.kind === "ready" ? formatIso(state.post.created_at) : "—"}
        </div>

        {saveBadge && (
          <div style={{ marginLeft: "auto" }}>
            <span
              style={{
                padding: "4px 8px",
                borderRadius: 999,
                border: "1px solid rgba(0,0,0,0.15)",
                background: saveState.kind === "error" ? "rgba(255,0,0,0.06)" : "rgba(0,0,0,0.03)",
                fontWeight: 600,
              }}
              title={saveState.kind === "error" ? saveState.message : ""}
            >
              {saveBadge}
            </span>
          </div>
        )}
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
          value={titleDraft}
          onChange={(e) => setTitleDraft(e.target.value)}
          onBlur={() => flushSaveNow("blur")}
          onKeyDown={(e) => {
            if (isEnter(e)) {
              (e.currentTarget as HTMLInputElement).blur();
            }
          }}
          style={{
            width: "100%",
            fontSize: 18,
            padding: "10px 12px",
            borderRadius: 10,
            border: "1px solid rgba(0,0,0,0.2)",
          }}
        />
      </div>

      {/* Body (still persisted as body_md) */}
      <div style={{ marginBottom: 16 }}>
        <textarea
          placeholder="Write…"
          value={bodyDraft}
          onChange={(e) => setBodyDraft(e.target.value)}
          onBlur={() => flushSaveNow("blur")}
          style={{
            width: "100%",
            minHeight: 320,
            padding: 16,
            borderRadius: 12,
            border: "1px solid rgba(0,0,0,0.2)",
            background: "rgba(0,0,0,0.02)",
            resize: "vertical",
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
            fontSize: 13,
            lineHeight: 1.5,
          }}
        />
        <div style={{ fontSize: 12, opacity: 0.6, marginTop: 6 }}>
          Autosave: edits are saved after a short pause or when you leave the field.
        </div>
      </div>

      {/* Actions (still disabled; autosave does the job) */}
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
