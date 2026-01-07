// frontend/src/pages/editor/EditorPage.tsx
//
// Editor page (v3 -> v4 internal behavior).
// - Loads post by id from API
// - Shows metadata (status + timestamps)
// - Title is editable (saved via PATCH)
// - Body uses TipTap rich editor
// - Autosave via PATCH (debounced) + safe flush on blur/manual
//
// v4 change:
// - Compare and persist TipTap JSON as the canonical authoring format (body_json)
// - Do NOT send PATCH on toolbar clicks/blur unless the document actually changed

import React, { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { getPost, patchPost, type PostItem } from "@/api/posts";

import { EditorContent, type JSONContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";

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

function stableStringify(value: unknown): string {
  // Deterministic JSON stringify (sort keys recursively).
  // This avoids "different string, same meaning" issues when comparing objects.
  const seen = new WeakSet<object>();

  function normalize(v: any): any {
    if (v === null || typeof v !== "object") return v;

    if (seen.has(v)) return null;
    seen.add(v);

    if (Array.isArray(v)) return v.map(normalize);

    const out: Record<string, any> = {};
    for (const k of Object.keys(v).sort()) {
      out[k] = normalize(v[k]);
    }
    return out;
  }

  return JSON.stringify(normalize(value));
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
  const [bodyJsonStrDraft, setBodyJsonStrDraft] = useState<string>("");

  // Save status (tiny UX)
  const [saveState, setSaveState] = useState<SaveState>({ kind: "idle" });

  // Keep last server values to avoid PATCH spam
  const lastServerTitleRef = useRef<string>("");
  const lastServerBodyJsonStrRef = useRef<string>("");

  // Debounce timer
  const saveTimerRef = useRef<number | null>(null);

  // TipTap editor
  const editor = useEditor({
    extensions: [StarterKit],
    content: "",
    editorProps: {
      attributes: {
        style: [
          "min-height: 320px",
          "padding: 16px",
          "outline: none",
          "font-family: ui-sans-serif, system-ui",
          "font-size: 14px",
          "line-height: 1.6",
        ].join("; "),
      },
    },
    onUpdate: ({ editor }) => {
      // Canonical authoring format: TipTap JSON.
      // onUpdate only fires when docChanged === true, so selection/toolbar focus
      // won't cause drafts to change.
      const json = editor.getJSON();
      setBodyJsonStrDraft(stableStringify(json));
    },
  });

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
    setTitleDraft(title);
    lastServerTitleRef.current = title;

    // Prefer v2 canonical body_json (object) if present, fallback to legacy body_md (HTML).
    const bodyJsonFromApi = (state.post as any).body_json as JSONContent | null | undefined;
    const bodyHtmlLegacy = (state.post as any).body_md as string | null | undefined;

    if (editor) {
      if (bodyJsonFromApi && typeof bodyJsonFromApi === "object") {
        // Set JSON content without emitting update.
        editor.commands.setContent(bodyJsonFromApi, { emitUpdate: false });
      } else {
        // Fallback: we still support HTML for existing posts.
        editor.commands.setContent(bodyHtmlLegacy || "", { emitUpdate: false });
      }

      // After hydration, compute canonical JSON string from the editor state.
      const hydratedJsonStr = stableStringify(editor.getJSON());
      setBodyJsonStrDraft(hydratedJsonStr);
      lastServerBodyJsonStrRef.current = hydratedJsonStr;
    } else {
      // If editor isn't ready yet, keep drafts empty until it is.
      setBodyJsonStrDraft("");
      lastServerBodyJsonStrRef.current = "";
    }

    setSaveState({ kind: "idle" });
  }, [state.kind, state.kind === "ready" ? state.post.id : null, editor]);

  function buildPatch(): Record<string, unknown> | null {
    const patch: Record<string, unknown> = {};

    // Never send invalid title in autosave.
    // If user clears title temporarily, we do not include it in PATCH.
    const nextTitle = normalizeTitle(titleDraft);
    const serverTitle = normalizeTitle(lastServerTitleRef.current);

    if (nextTitle !== serverTitle) {
      if (nextTitle.length > 0) patch.title = nextTitle;
    }

    // Canonical: body_json
    if (bodyJsonStrDraft !== lastServerBodyJsonStrRef.current) {
      // Send object to backend (it will json.dumps to TEXT).
      // We re-read from editor to avoid any stringify/parse drift.
      patch.body_json = editor ? editor.getJSON() : null;
    }

    return Object.keys(patch).length ? patch : null;
  }

  async function flushSaveNow(reason: "debounce" | "blur" | "manual" = "manual") {
    if (!postId) return;
    if (state.kind !== "ready") return;

    // Validate title only on explicit user actions.
    const normalizedTitle = normalizeTitle(titleDraft);
    if ((reason === "blur" || reason === "manual") && normalizedTitle.length === 0) {
      setSaveState({ kind: "error", message: "Title cannot be empty." });
      return;
    }

    const patch = buildPatch();
    if (!patch) return;

    setSaveState({ kind: "saving" });
    try {
      // api client typing currently may not include body_json yet.
      // We keep this change local to the page and rely on backend support.
      const res = await patchPost(postId, patch as any);

      if (!res.ok) {
        setSaveState({ kind: "error", message: res.error || "Failed to save." });
        return;
      }

      if (res.item) {
        const newTitle = res.item.title ?? lastServerTitleRef.current;
        lastServerTitleRef.current = newTitle ?? "";
        setTitleDraft(newTitle ?? "");

        // Re-sync canonical JSON string.
        // Prefer server body_json if returned; otherwise use current editor state.
        const newBodyJsonFromApi = (res.item as any).body_json as JSONContent | null | undefined;

        if (editor) {
          if (newBodyJsonFromApi && typeof newBodyJsonFromApi === "object") {
            editor.commands.setContent(newBodyJsonFromApi, { emitUpdate: false });
          }

          const jsonStr = stableStringify(editor.getJSON());
          setBodyJsonStrDraft(jsonStr);
          lastServerBodyJsonStrRef.current = jsonStr;
        } else {
          // If editor is missing, at least stop spam.
          lastServerBodyJsonStrRef.current = bodyJsonStrDraft;
        }

        setState({ kind: "ready", post: res.item });
      } else {
        // Fallback: assume patch succeeded.
        if (patch.title !== undefined) lastServerTitleRef.current = String(patch.title ?? "");
        if (editor) {
          const jsonStr = stableStringify(editor.getJSON());
          lastServerBodyJsonStrRef.current = jsonStr;
          setBodyJsonStrDraft(jsonStr);
        }
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
    if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
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
  }, [titleDraft, bodyJsonStrDraft]);

  const statusValue = state.kind === "ready" ? state.post.status ?? "—" : "—";

  const saveBadge =
    saveState.kind === "saving"
      ? "Saving…"
      : saveState.kind === "saved"
        ? "Saved"
        : saveState.kind === "error"
          ? "Save error"
          : "";

  const btnStyle: React.CSSProperties = {
    padding: "6px 10px",
    borderRadius: 10,
    border: "1px solid rgba(0,0,0,0.18)",
    background: "white",
    cursor: "pointer",
    fontWeight: 700,
    fontSize: 12,
  };

  const btnOnStyle: React.CSSProperties = {
    ...btnStyle,
    background: "rgba(0,0,0,0.05)",
  };

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
            if (isEnter(e)) (e.currentTarget as HTMLInputElement).blur();
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

      {/* TipTap toolbar */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
        <button
          type="button"
          style={editor?.isActive("bold") ? btnOnStyle : btnStyle}
          onClick={() => editor?.chain().focus().toggleBold().run()}
          disabled={!editor}
        >
          B
        </button>
        <button
          type="button"
          style={editor?.isActive("italic") ? btnOnStyle : btnStyle}
          onClick={() => editor?.chain().focus().toggleItalic().run()}
          disabled={!editor}
        >
          I
        </button>
        <button
          type="button"
          style={editor?.isActive("heading", { level: 1 }) ? btnOnStyle : btnStyle}
          onClick={() => editor?.chain().focus().toggleHeading({ level: 1 }).run()}
          disabled={!editor}
        >
          H1
        </button>
        <button
          type="button"
          style={editor?.isActive("heading", { level: 2 }) ? btnOnStyle : btnStyle}
          onClick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()}
          disabled={!editor}
        >
          H2
        </button>
        <button
          type="button"
          style={editor?.isActive("bulletList") ? btnOnStyle : btnStyle}
          onClick={() => editor?.chain().focus().toggleBulletList().run()}
          disabled={!editor}
        >
          • List
        </button>
        <button
          type="button"
          style={editor?.isActive("orderedList") ? btnOnStyle : btnStyle}
          onClick={() => editor?.chain().focus().toggleOrderedList().run()}
          disabled={!editor}
        >
          1. List
        </button>
        <button
          type="button"
          style={editor?.isActive("blockquote") ? btnOnStyle : btnStyle}
          onClick={() => editor?.chain().focus().toggleBlockquote().run()}
          disabled={!editor}
        >
          “
        </button>
        <button
          type="button"
          style={editor?.isActive("codeBlock") ? btnOnStyle : btnStyle}
          onClick={() => editor?.chain().focus().toggleCodeBlock().run()}
          disabled={!editor}
        >
          Code
        </button>

        <button
          type="button"
          style={{ ...btnStyle, marginLeft: "auto" }}
          onClick={() => flushSaveNow("manual")}
          disabled={!editor}
          title="Manual save"
        >
          Save
        </button>
      </div>

      {/* TipTap editor surface */}
      <div
        style={{
          borderRadius: 12,
          border: "1px solid rgba(0,0,0,0.2)",
          background: "white",
          overflow: "hidden",
        }}
        // Important: toolbar clicks cause blur on this container.
        // flushSaveNow will only PATCH if canonical JSON actually changed.
        onBlur={() => flushSaveNow("blur")}
      >
        <EditorContent editor={editor} />
      </div>

      <div style={{ fontSize: 12, opacity: 0.6, marginTop: 6, marginBottom: 16 }}>
        Autosave: edits are saved after a short pause or when you leave the editor.
      </div>

      {/* Actions placeholder */}
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
