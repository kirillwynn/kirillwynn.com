// frontend/src/pages/editor/EditorPage.tsx
//
// Editor page (v3).
// - Loads post by id from API
// - Shows metadata (status + timestamps)
// - Title + body_md are editable
// - Autosave via PATCH (debounced) + immediate save on blur
// - Adds "dirty-state" UX: Unsaved / Saving / Saved / Error
// - Still no rich editor yet (textarea for body_md)

import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { getPost, patchPost, type PostItem } from "@/api/posts";

type LoadState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; post: PostItem };

type SaveState =
  | { kind: "idle" }
  | { kind: "dirty" }
  | { kind: "saving" }
  | { kind: "saved"; at: number }
  | { kind: "error"; message: string };

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

  // Save state badge
  const [saveState, setSaveState] = useState<SaveState>({ kind: "idle" });

  // Keep last server values to avoid PATCH spam + compute "dirty"
  const lastServerTitleRef = useRef<string>("");
  const lastServerBodyRef = useRef<string>("");

  // Debounce timer
  const saveTimerRef = useRef<number | null>(null);

  // Prevent showing "dirty" while hydrating initial data
  const isHydratingRef = useRef<boolean>(true);

  // Avoid out-of-order PATCH responses winning
  const saveSeqRef = useRef<number>(0);

  function getNormalizedDrafts() {
    // Normalize the same way backend validates (trim + no nulls).
    // NOTE: backend forbids empty title; here we still allow typing, but we won't PATCH invalid payloads.
    const title = titleDraft;
    const body = bodyDraft;
    return { title, body };
  }

  function computeDirty(): boolean {
    const { title, body } = getNormalizedDrafts();
    return title !== lastServerTitleRef.current || body !== lastServerBodyRef.current;
  }

  function buildPatch(): Partial<Pick<PostItem, "title" | "body_md">> | null {
    const patch: Partial<Pick<PostItem, "title" | "body_md">> = {};
    const { title, body } = getNormalizedDrafts();

    if (title !== lastServerTitleRef.current) patch.title = title;
    if (body !== lastServerBodyRef.current) patch.body_md = body;

    return Object.keys(patch).length ? patch : null;
  }

  useEffect(() => {
    let cancelled = false;

    async function run() {
      if (!postId) {
        setState({ kind: "error", message: "Missing or invalid post id in URL." });
        return;
      }

      setState({ kind: "loading" });
      isHydratingRef.current = true;

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

    // Reset save UX
    setSaveState({ kind: "idle" });

    // Hydration done
    isHydratingRef.current = false;
  }, [state.kind, state.kind === "ready" ? state.post.id : null]);

  // Dirty-state tracking: whenever drafts diverge from server, show "Unsaved changes"
  useEffect(() => {
    if (state.kind !== "ready") return;
    if (isHydratingRef.current) return;

    const dirty = computeDirty();

    setSaveState((prev) => {
      // Do not override "saving" (it has priority).
      if (prev.kind === "saving") return prev;

      // If not dirty, keep "saved" if we have it; otherwise idle.
      if (!dirty) {
        if (prev.kind === "saved") return prev;
        return { kind: "idle" };
      }

      // Dirty: show unsaved unless already error (error can stay until next edit).
      if (prev.kind === "error") return { kind: "dirty" };
      if (prev.kind === "dirty") return prev;
      return { kind: "dirty" };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [titleDraft, bodyDraft, state.kind]);

  async function flushSaveNow() {
    if (!postId) return;
    if (state.kind !== "ready") return;

    // Cancel pending debounce if any
    if (saveTimerRef.current) {
      window.clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }

    const patch = buildPatch();
    if (!patch) return;

    // Basic client-side guard: avoid PATCH that backend will reject.
    if (patch.title !== undefined) {
      const t = String(patch.title ?? "").trim();
      if (t.length === 0) {
        setSaveState({ kind: "error", message: "Title cannot be empty." });
        return;
      }
      if (t.length > 200) {
        setSaveState({ kind: "error", message: "Title too long (max 200)." });
        return;
      }
      patch.title = t;
    }

    const seq = ++saveSeqRef.current;

    setSaveState({ kind: "saving" });
    try {
      const res = await patchPost(postId, patch);

      // Ignore stale responses
      if (seq !== saveSeqRef.current) return;

      if (!res.ok) {
        setSaveState({ kind: "error", message: res.error || "Failed to save." });
        return;
      }

      if (res.item) {
        const newTitle = res.item.title ?? titleDraft;
        const newBody = res.item.body_md ?? bodyDraft;

        lastServerTitleRef.current = newTitle;
        lastServerBodyRef.current = newBody;

        // Keep drafts aligned with server after save
        setTitleDraft(newTitle);
        setBodyDraft(newBody);

        setState({ kind: "ready", post: res.item });
      } else {
        // Fallback: assume patch succeeded
        if (patch.title !== undefined) lastServerTitleRef.current = String(patch.title ?? "");
        if (patch.body_md !== undefined) lastServerBodyRef.current = String(patch.body_md ?? "");
      }

      setSaveState({ kind: "saved", at: Date.now() });
    } catch (e: any) {
      if (seq !== saveSeqRef.current) return;
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
      flushSaveNow();
    }, 600);
  }

  // Debounced autosave on changes
  useEffect(() => {
    if (state.kind !== "ready") return;
    if (isHydratingRef.current) return;

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

  const badgeText =
    saveState.kind === "dirty"
      ? "Unsaved changes"
      : saveState.kind === "saving"
        ? "Saving…"
        : saveState.kind === "saved"
          ? "Saved"
          : saveState.kind === "error"
            ? "Save error"
            : "";

  const badgeBg =
    saveState.kind === "error"
      ? "rgba(255,0,0,0.06)"
      : saveState.kind === "dirty"
        ? "rgba(255,165,0,0.12)"
        : "rgba(0,0,0,0.03)";

  return (
    <div style={{ fontFamily: "ui-sans-serif, system-ui", maxWidth: 900, margin: "0 auto" }}>
      <header style={{ marginBottom: 16 }}>
        <h1 style={{ fontSize: 22, marginBottom: 4 }}>Editor</h1>
        <p style={{ opacity: 0.7, margin: 0 }}>
          Post editor (v3). Dirty-state + autosave.
        </p>
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

        {badgeText && (
          <div style={{ marginLeft: "auto" }}>
            <span
              style={{
                padding: "4px 10px",
                borderRadius: 999,
                border: "1px solid rgba(0,0,0,0.15)",
                background: badgeBg,
                fontWeight: 700,
              }}
              title={saveState.kind === "error" ? saveState.message : ""}
            >
              {badgeText}
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
          onBlur={() => flushSaveNow()}
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

      {/* Body (markdown textarea for now) */}
      <div style={{ marginBottom: 16 }}>
        <textarea
          placeholder="Write markdown…"
          value={bodyDraft}
          onChange={(e) => setBodyDraft(e.target.value)}
          onBlur={() => flushSaveNow()}
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
