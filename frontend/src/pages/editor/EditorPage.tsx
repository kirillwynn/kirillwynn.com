// frontend/src/pages/editor/EditorPage.tsx
//
// Editor page (v3).
// - Loads post by id from API
// - Shows metadata (status + timestamps)
// - Title is editable + autosaved via PATCH (debounced) + immediate save on blur
// - Body uses TipTap editor (rich UI), stored in body_md as plain text for now
// - Still no media integration yet

import React, { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { getPost, patchPost, type PostItem } from "@/api/posts";

import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Link from "@tiptap/extension-link";
import Placeholder from "@tiptap/extension-placeholder";

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

function isEnter(e: React.KeyboardEvent<HTMLInputElement>) {
  return e.key === "Enter";
}

type SaveState =
  | { kind: "idle" }
  | { kind: "saving" }
  | { kind: "saved"; at: number }
  | { kind: "error"; message: string };

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

  // Save status
  const [saveState, setSaveState] = useState<SaveState>({ kind: "idle" });

  // Keep last server values to avoid PATCH spam
  const lastServerTitleRef = useRef<string>("");
  const lastServerBodyRef = useRef<string>("");

  // Debounce timer
  const saveTimerRef = useRef<number | null>(null);

  // TipTap editor
  const editor = useEditor({
    extensions: [
      StarterKit,
      Link.configure({
        openOnClick: false,
        autolink: true,
        linkOnPaste: true,
      }),
      Placeholder.configure({
        placeholder: "Write something…",
      }),
    ],
    content: "",
    editorProps: {
      attributes: {
        style: [
          "min-height: 320px",
          "padding: 16px",
          "border-radius: 12px",
          "border: 1px solid rgba(0,0,0,0.2)",
          "background: rgba(0,0,0,0.02)",
          "outline: none",
          "font-family: ui-sans-serif, system-ui",
          "font-size: 14px",
          "line-height: 1.6",
        ].join("; "),
      },
    },
  });

  // Load post
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

  // Hydrate drafts when post becomes ready / changes
  useEffect(() => {
    if (state.kind !== "ready") return;

    const title = state.post.title ?? "";
    const body = state.post.body_md ?? "";

    setTitleDraft(title);

    lastServerTitleRef.current = title;
    lastServerBodyRef.current = body;

    // Set TipTap content once per post load
    if (editor) {
      // For now we treat body_md as plain text and put it into a paragraph
      // (next step will implement real Markdown import/export).
      const safeText = body ?? "";
      editor.commands.setContent(
        safeText ? `<p>${escapeHtml(safeText).replace(/\n/g, "<br>")}</p>` : "",
        { emitUpdate: false },
      );
    }

    setSaveState({ kind: "idle" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.kind, state.kind === "ready" ? state.post.id : null, editor]);

  function currentBodyDraft(): string {
    // For now store as plain text. Rich markdown export comes next.
    const txt = editor?.getText({ blockSeparator: "\n" }) ?? "";
    return txt;
  }

  function buildPatch(): Partial<Pick<PostItem, "title" | "body_md">> | null {
    const patch: Partial<Pick<PostItem, "title" | "body_md">> = {};

    const bodyNow = currentBodyDraft();

    if (titleDraft !== lastServerTitleRef.current) patch.title = titleDraft;
    if (bodyNow !== lastServerBodyRef.current) patch.body_md = bodyNow;

    return Object.keys(patch).length ? patch : null;
  }

  async function flushSaveNow() {
    if (!postId) return;
    if (state.kind !== "ready") return;

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
        const newTitle = res.item.title ?? titleDraft;
        const newBody = res.item.body_md ?? currentBodyDraft();

        lastServerTitleRef.current = newTitle;
        lastServerBodyRef.current = newBody;

        setTitleDraft(newTitle);
        setState({ kind: "ready", post: res.item });
      } else {
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
    if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
    saveTimerRef.current = window.setTimeout(() => {
      flushSaveNow();
    }, 700);
  }

  // Debounced autosave on title changes
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
  }, [titleDraft]);

  // Debounced autosave on editor changes
  useEffect(() => {
    if (!editor) return;
    if (state.kind !== "ready") return;

    const handler = () => {
      if (!buildPatch()) return;
      scheduleDebouncedSave();
    };

    editor.on("update", handler);
    return () => {
      editor.off("update", handler);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editor, state.kind]);

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
        <p style={{ opacity: 0.7, margin: 0 }}>
          Post editor (v3). TipTap rich editor is enabled.
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
          onBlur={() => flushSaveNow()}
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

      {/* Editor toolbar */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 10 }}>
        <ToolbarButton
          label="B"
          title="Bold"
          active={!!editor?.isActive("bold")}
          onClick={() => editor?.chain().focus().toggleBold().run()}
        />
        <ToolbarButton
          label="I"
          title="Italic"
          active={!!editor?.isActive("italic")}
          onClick={() => editor?.chain().focus().toggleItalic().run()}
        />
        <ToolbarButton
          label="H1"
          title="Heading 1"
          active={!!editor?.isActive("heading", { level: 1 })}
          onClick={() => editor?.chain().focus().toggleHeading({ level: 1 }).run()}
        />
        <ToolbarButton
          label="H2"
          title="Heading 2"
          active={!!editor?.isActive("heading", { level: 2 })}
          onClick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()}
        />
        <ToolbarButton
          label="• List"
          title="Bullet list"
          active={!!editor?.isActive("bulletList")}
          onClick={() => editor?.chain().focus().toggleBulletList().run()}
        />
        <ToolbarButton
          label="1. List"
          title="Ordered list"
          active={!!editor?.isActive("orderedList")}
          onClick={() => editor?.chain().focus().toggleOrderedList().run()}
        />
        <ToolbarButton
          label="❝"
          title="Blockquote"
          active={!!editor?.isActive("blockquote")}
          onClick={() => editor?.chain().focus().toggleBlockquote().run()}
        />
        <ToolbarButton
          label="Code"
          title="Code block"
          active={!!editor?.isActive("codeBlock")}
          onClick={() => editor?.chain().focus().toggleCodeBlock().run()}
        />
        <ToolbarButton
          label="Save"
          title="Save now"
          active={false}
          onClick={() => flushSaveNow()}
        />
      </div>

      {/* TipTap editor */}
      <div onBlurCapture={() => flushSaveNow()} style={{ marginBottom: 10 }}>
        <EditorContent editor={editor} />
      </div>

      <div style={{ fontSize: 12, opacity: 0.6, marginTop: 6 }}>
        Autosave: changes are saved after a short pause or when you leave the field.
      </div>
    </div>
  );
}

function ToolbarButton(props: {
  label: string;
  title: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      title={props.title}
      onClick={props.onClick}
      style={{
        padding: "6px 10px",
        borderRadius: 10,
        border: "1px solid rgba(0,0,0,0.18)",
        background: props.active ? "rgba(0,0,0,0.06)" : "white",
        fontWeight: 700,
        cursor: "pointer",
      }}
    >
      {props.label}
    </button>
  );
}

function escapeHtml(s: string): string {
  return s
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
