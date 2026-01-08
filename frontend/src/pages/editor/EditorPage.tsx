import React, { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { getPost, patchPost, type PostItem } from "@/api/posts";

import { EditorContent, type JSONContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";

import Link from "@tiptap/extension-link";
import Underline from "@tiptap/extension-underline";
import TextAlign from "@tiptap/extension-text-align";
import Highlight from "@tiptap/extension-highlight";

import {
  Bold,
  Italic,
  Underline as UnderlineIcon,
  Strikethrough,
  Code,
  Quote,
  List,
  ListOrdered,
  Heading1,
  Heading2,
  Undo2,
  Redo2,
  AlignLeft,
  AlignCenter,
  AlignRight,
  AlignJustify,
  Link2,
  Highlighter,
  Save,
  Moon,
} from "lucide-react";

import "./tiptap-prose.css";

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

// Stable stringify so we can compare JSON snapshots reliably.
// (Avoids PATCH spam due to key order differences)
function stableStringify(value: unknown): string {
  const seen = new WeakSet<object>();

  function normalize(v: any): any {
    if (v === null || typeof v !== "object") return v;
    if (seen.has(v)) return null;
    seen.add(v);
    if (Array.isArray(v)) return v.map(normalize);
    const out: Record<string, any> = {};
    for (const k of Object.keys(v).sort()) out[k] = normalize(v[k]);
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

  // Drafts
  const [titleDraft, setTitleDraft] = useState("");
  const [bodyJsonStrDraft, setBodyJsonStrDraft] = useState<string>("");

  // Save status
  const [saveState, setSaveState] = useState<SaveState>({ kind: "idle" });

  // Keep last server snapshot to avoid PATCH spam
  const lastServerTitleRef = useRef<string>("");
  const lastServerBodyJsonStrRef = useRef<string>("");

  // Debounce timer
  const saveTimerRef = useRef<number | null>(null);

  const editor = useEditor({
    extensions: [
      StarterKit,
      Underline,
      Highlight,
      Link.configure({
        openOnClick: false,
        autolink: true,
        linkOnPaste: true,
        HTMLAttributes: {
          rel: "noopener noreferrer nofollow",
          target: "_blank",
        },
      }),
      TextAlign.configure({
        types: ["heading", "paragraph"],
      }),
    ],
    content: "",
    editorProps: {
      attributes: {
        class: "tiptap-prose",
      },
    },

    // IMPORTANT:
    // TipTap calls onUpdate only when docChanged.
    // That means: toolbar clicks that only change selection/storedMarks won't fire this.
    onUpdate: ({ editor }) => {
      setBodyJsonStrDraft(stableStringify(editor.getJSON()));
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

  // Hydrate from server -> local drafts + editor content
  useEffect(() => {
    if (state.kind !== "ready") return;

    const title = state.post.title ?? "";
    setTitleDraft(title);
    lastServerTitleRef.current = title;

    const bodyJsonFromApi = (state.post as any).body_json as JSONContent | null | undefined;
    const bodyHtmlLegacy = (state.post as any).body_md as string | null | undefined;

    if (editor) {
      if (bodyJsonFromApi && typeof bodyJsonFromApi === "object") {
        editor.commands.setContent(bodyJsonFromApi, { emitUpdate: false });
      } else {
        // Fallback: if we have legacy html in body_md
        editor.commands.setContent(bodyHtmlLegacy || "", { emitUpdate: false });
      }

      const hydratedJsonStr = stableStringify(editor.getJSON());
      setBodyJsonStrDraft(hydratedJsonStr);
      lastServerBodyJsonStrRef.current = hydratedJsonStr;
    } else {
      setBodyJsonStrDraft("");
      lastServerBodyJsonStrRef.current = "";
    }

    setSaveState({ kind: "idle" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.kind, state.kind === "ready" ? state.post.id : null, editor]);

  function buildPatch(): Record<string, unknown> | null {
    const patch: Record<string, unknown> = {};

    const nextTitle = normalizeTitle(titleDraft);
    const serverTitle = normalizeTitle(lastServerTitleRef.current);
    if (nextTitle !== serverTitle) {
      // Don’t autosave invalid title
      if (nextTitle.length > 0) patch.title = nextTitle;
    }

    if (bodyJsonStrDraft !== lastServerBodyJsonStrRef.current) {
      patch.body_json = editor ? editor.getJSON() : null;
    }

    return Object.keys(patch).length ? patch : null;
  }

  async function flushSaveNow(reason: "debounce" | "blur" | "manual" = "manual") {
    if (!postId) return;
    if (state.kind !== "ready") return;

    const normalizedTitle = normalizeTitle(titleDraft);

    // Only enforce “title required” on explicit user actions.
    // Clicking toolbar should not suddenly error just because title is temporarily empty.
    if ((reason === "blur" || reason === "manual") && normalizedTitle.length === 0) {
      setSaveState({ kind: "error", message: "Title cannot be empty." });
      return;
    }

    const patch = buildPatch();
    if (!patch) return;

    setSaveState({ kind: "saving" });
    try {
      const res = await patchPost(postId, patch as any);

      if (!res.ok) {
        setSaveState({ kind: "error", message: res.error || "Failed to save." });
        return;
      }

      if (res.item) {
        const newTitle = res.item.title ?? lastServerTitleRef.current;
        lastServerTitleRef.current = newTitle ?? "";
        setTitleDraft(newTitle ?? "");

        const newBodyJsonFromApi = (res.item as any).body_json as JSONContent | null | undefined;

        if (editor) {
          if (newBodyJsonFromApi && typeof newBodyJsonFromApi === "object") {
            editor.commands.setContent(newBodyJsonFromApi, { emitUpdate: false });
          }
          const jsonStr = stableStringify(editor.getJSON());
          setBodyJsonStrDraft(jsonStr);
          lastServerBodyJsonStrRef.current = jsonStr;
        } else {
          // If editor is not ready, still advance snapshot
          lastServerBodyJsonStrRef.current = bodyJsonStrDraft;
        }

        setState({ kind: "ready", post: res.item });
      } else {
        // Fallback: assume patch succeeded
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

  // Debounced autosave on real changes
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

  // --- UI helpers (Simple-editor-ish toolbar) --------------------

  function ToolButton(props: {
    title: string;
    active?: boolean;
    disabled?: boolean;
    onClick: () => void;
    children: React.ReactNode;
  }) {
    return (
      <button
        type="button"
        title={props.title}
        disabled={props.disabled}
        onMouseDown={(e) => {
          // Keep focus in editor; prevents blur-triggered autosave when clicking toolbar.
          e.preventDefault();
        }}
        onClick={props.onClick}
        style={{
          width: 36,
          height: 36,
          borderRadius: 12,
          border: "1px solid rgba(255,255,255,0.10)",
          background: props.active ? "rgba(255,255,255,0.10)" : "transparent",
          color: "rgba(255,255,255,0.92)",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: props.disabled ? "not-allowed" : "pointer",
          opacity: props.disabled ? 0.5 : 1,
        }}
      >
        {props.children}
      </button>
    );
  }

  function Divider() {
    return (
      <div
        style={{
          width: 1,
          height: 22,
          background: "rgba(255,255,255,0.14)",
          margin: "0 8px",
          alignSelf: "center",
        }}
      />
    );
  }

  async function toggleLink() {
    if (!editor) return;

    const current = editor.getAttributes("link").href as string | undefined;
    const url = window.prompt("Enter URL", current || "https://");
    if (!url) {
      editor.chain().focus().unsetLink().run();
      return;
    }
    editor.chain().focus().setLink({ href: url }).run();
  }

  return (
    <div style={{ fontFamily: "ui-sans-serif, system-ui", maxWidth: 980, margin: "0 auto" }}>
      <header style={{ marginBottom: 16 }}>
        <h1 style={{ fontSize: 22, marginBottom: 4 }}>Editor</h1>
        <p style={{ opacity: 0.7, margin: 0 }}>Post editor. TipTap rich editor is enabled.</p>
      </header>

      {/* Status line */}
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
          <strong>Published:</strong> {state.kind === "ready" ? formatIso(state.post.published_at) : "—"}
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

      {/* Simple editor card */}
      <div
        style={{
          borderRadius: 22,
          overflow: "hidden",
          border: "1px solid rgba(0,0,0,0.10)",
          boxShadow: "0 10px 30px rgba(0,0,0,0.06)",
          background: "#0f1115",
        }}
      >
        {/* Toolbar */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            flexWrap: "wrap",
            padding: 12,
            borderBottom: "1px solid rgba(255,255,255,0.10)",
            background: "rgba(255,255,255,0.03)",
          }}
        >
          {/* Group 1: Undo/Redo */}
          <ToolButton
            title="Undo"
            disabled={!editor || !editor.can().undo()}
            onClick={() => editor?.chain().focus().undo().run()}
          >
            <Undo2 size={18} />
          </ToolButton>
          <ToolButton
            title="Redo"
            disabled={!editor || !editor.can().redo()}
            onClick={() => editor?.chain().focus().redo().run()}
          >
            <Redo2 size={18} />
          </ToolButton>

          <Divider />

          {/* Group 2: Headings + Lists */}
          <ToolButton
            title="Heading 1"
            active={!!editor?.isActive("heading", { level: 1 })}
            disabled={!editor}
            onClick={() => editor?.chain().focus().toggleHeading({ level: 1 }).run()}
          >
            <Heading1 size={18} />
          </ToolButton>
          <ToolButton
            title="Heading 2"
            active={!!editor?.isActive("heading", { level: 2 })}
            disabled={!editor}
            onClick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()}
          >
            <Heading2 size={18} />
          </ToolButton>
          <ToolButton
            title="Bullet list"
            active={!!editor?.isActive("bulletList")}
            disabled={!editor}
            onClick={() => editor?.chain().focus().toggleBulletList().run()}
          >
            <List size={18} />
          </ToolButton>
          <ToolButton
            title="Ordered list"
            active={!!editor?.isActive("orderedList")}
            disabled={!editor}
            onClick={() => editor?.chain().focus().toggleOrderedList().run()}
          >
            <ListOrdered size={18} />
          </ToolButton>

          <Divider />

          {/* Group 3: Alignment */}
          <ToolButton
            title="Align left"
            active={!!editor?.isActive({ textAlign: "left" })}
            disabled={!editor}
            onClick={() => editor?.chain().focus().setTextAlign("left").run()}
          >
            <AlignLeft size={18} />
          </ToolButton>
          <ToolButton
            title="Align center"
            active={!!editor?.isActive({ textAlign: "center" })}
            disabled={!editor}
            onClick={() => editor?.chain().focus().setTextAlign("center").run()}
          >
            <AlignCenter size={18} />
          </ToolButton>
          <ToolButton
            title="Align right"
            active={!!editor?.isActive({ textAlign: "right" })}
            disabled={!editor}
            onClick={() => editor?.chain().focus().setTextAlign("right").run()}
          >
            <AlignRight size={18} />
          </ToolButton>
          <ToolButton
            title="Justify"
            active={!!editor?.isActive({ textAlign: "justify" })}
            disabled={!editor}
            onClick={() => editor?.chain().focus().setTextAlign("justify").run()}
          >
            <AlignJustify size={18} />
          </ToolButton>

          <Divider />

          {/* Group 4: Inline formatting */}
          <ToolButton
            title="Bold"
            active={!!editor?.isActive("bold")}
            disabled={!editor}
            onClick={() => editor?.chain().focus().toggleBold().run()}
          >
            <Bold size={18} />
          </ToolButton>
          <ToolButton
            title="Italic"
            active={!!editor?.isActive("italic")}
            disabled={!editor}
            onClick={() => editor?.chain().focus().toggleItalic().run()}
          >
            <Italic size={18} />
          </ToolButton>
          <ToolButton
            title="Underline"
            active={!!editor?.isActive("underline")}
            disabled={!editor}
            onClick={() => editor?.chain().focus().toggleUnderline().run()}
          >
            <UnderlineIcon size={18} />
          </ToolButton>
          <ToolButton
            title="Strikethrough"
            active={!!editor?.isActive("strike")}
            disabled={!editor}
            onClick={() => editor?.chain().focus().toggleStrike().run()}
          >
            <Strikethrough size={18} />
          </ToolButton>
          <ToolButton
            title="Inline code"
            active={!!editor?.isActive("code")}
            disabled={!editor}
            onClick={() => editor?.chain().focus().toggleCode().run()}
          >
            <Code size={18} />
          </ToolButton>

          <Divider />

          {/* Group 5: Quote / Highlight / Link */}
          <ToolButton
            title="Quote"
            active={!!editor?.isActive("blockquote")}
            disabled={!editor}
            onClick={() => editor?.chain().focus().toggleBlockquote().run()}
          >
            <Quote size={18} />
          </ToolButton>
          <ToolButton
            title="Highlight"
            active={!!editor?.isActive("highlight")}
            disabled={!editor}
            onClick={() => editor?.chain().focus().toggleHighlight().run()}
          >
            <Highlighter size={18} />
          </ToolButton>
          <ToolButton
            title="Link"
            active={!!editor?.isActive("link")}
            disabled={!editor}
            onClick={toggleLink}
          >
            <Link2 size={18} />
          </ToolButton>

          <div style={{ flex: 1 }} />

          {/* Theme toggle placeholder (later) */}
          <ToolButton
            title="Theme (later)"
            disabled
            onClick={() => {}}
          >
            <Moon size={18} />
          </ToolButton>

          {/* Save */}
          <button
            type="button"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => flushSaveNow("manual")}
            disabled={!editor}
            title="Save"
            style={{
              height: 36,
              padding: "0 12px",
              borderRadius: 12,
              border: "1px solid rgba(255,255,255,0.14)",
              background: "rgba(255,255,255,0.08)",
              color: "rgba(255,255,255,0.92)",
              fontWeight: 700,
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              cursor: !editor ? "not-allowed" : "pointer",
              opacity: !editor ? 0.6 : 1,
            }}
          >
            <Save size={18} />
            Save
          </button>
        </div>

        {/* Surface */}
        <div
          style={{
            background: "linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01))",
            padding: 18,
          }}
          // NOTE: no onBlur here — toolbar clicks would cause blur spam.
        >
          <div
            style={{
              borderRadius: 18,
              background: "rgba(255,255,255,0.02)",
              border: "1px solid rgba(255,255,255,0.10)",
              padding: 14,
            }}
          >
            <div style={{ color: "rgba(255,255,255,0.92)" }}>
              <EditorContent editor={editor} />
            </div>
          </div>
        </div>
      </div>

      <div style={{ fontSize: 12, opacity: 0.6, marginTop: 8, marginBottom: 16 }}>
        Autosave: edits are saved after a short pause.
      </div>
    </div>
  );
}
