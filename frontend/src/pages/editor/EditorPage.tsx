// frontend/src/pages/editor/EditorPage.tsx
//
// Editor page (v3).
// - Loads post by id from API
// - Shows metadata (status + timestamps)
// - Title is editable (saved via PATCH)
// - Body uses TipTap rich editor (saved via PATCH as body_json)
// - Autosave via PATCH (debounced) when doc реально изменился
//
// Notes:
// - Toolbar is structured to match TipTap Simple Editor template (6 groups).
// - Some UI parts are implemented as lightweight dropdown/popovers (no extra deps).
// - "Add" panel is UI-only for now (upload handling in later step).

import React, { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { getPost, patchPost, type PostItem } from "@/api/posts";

import { EditorContent, type JSONContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";

import Link from "@tiptap/extension-link";
import Underline from "@tiptap/extension-underline";
import TextAlign from "@tiptap/extension-text-align";
import Highlight from "@tiptap/extension-highlight";
import TaskList from "@tiptap/extension-task-list";
import TaskItem from "@tiptap/extension-task-item";
import Superscript from "@tiptap/extension-superscript";
import Subscript from "@tiptap/extension-subscript";

import {
  Bold,
  Italic,
  Underline as UnderlineIcon,
  Strikethrough,
  Code,
  Quote,
  List,
  ListOrdered,
  ListChecks,
  Heading,
  Heading1,
  Heading2,
  Heading3,
  Heading4,
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
  Sun,
  Plus,
  FileUp,
  CodeSquare,
  Superscript as SuperscriptIcon,
  Subscript as SubscriptIcon,
  ChevronDown,
  Check,
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

type ThemeMode = "dark" | "light";

type MenuItem = {
  id: string;
  label: string;
  icon?: React.ReactNode;
  active?: boolean;
  onSelect: () => void;
};

function useOutsideClick(ref: React.RefObject<HTMLElement>, onOutside: () => void, enabled: boolean) {
  useEffect(() => {
    if (!enabled) return;

    function onDocMouseDown(e: MouseEvent) {
      const el = ref.current;
      if (!el) return;
      if (e.target instanceof Node && el.contains(e.target)) return;
      onOutside();
    }

    document.addEventListener("mousedown", onDocMouseDown);
    return () => document.removeEventListener("mousedown", onDocMouseDown);
  }, [ref, onOutside, enabled]);
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

  // UI state
  const [theme, setTheme] = useState<ThemeMode>("dark");
  const [headingMenuOpen, setHeadingMenuOpen] = useState(false);
  const [listMenuOpen, setListMenuOpen] = useState(false);
  const [addMenuOpen, setAddMenuOpen] = useState(false);

  const headingMenuRef = useRef<HTMLDivElement>(null);
  const listMenuRef = useRef<HTMLDivElement>(null);
  const addMenuRef = useRef<HTMLDivElement>(null);

  useOutsideClick(headingMenuRef, () => setHeadingMenuOpen(false), headingMenuOpen);
  useOutsideClick(listMenuRef, () => setListMenuOpen(false), listMenuOpen);
  useOutsideClick(addMenuRef, () => setAddMenuOpen(false), addMenuOpen);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        codeBlock: false,
      }),
      Underline,
      Highlight.configure({
        multicolor: false,
      }),
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
      TaskList,
      TaskItem.configure({
        nested: true,
      }),
      Superscript,
      Subscript,
    ],
    content: "",
    editorProps: {
      attributes: {
        class: "tiptap-prose",
        "data-theme": theme,
      },
    },

    // IMPORTANT:
    // TipTap calls onUpdate only when docChanged.
    // That means: toolbar clicks that only change selection/storedMarks won't fire this.
    onUpdate: ({ editor }) => {
      setBodyJsonStrDraft(stableStringify(editor.getJSON()));
    },
  });

  // Keep editor theme in sync with state (without recreating editor)
  useEffect(() => {
    if (!editor) return;
    const el = editor.view.dom as HTMLElement;
    el.setAttribute("data-theme", theme);
  }, [editor, theme]);

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

  const colors =
    theme === "dark"
      ? {
          cardBg: "#0f1115",
          barBg: "rgba(255,255,255,0.03)",
          border: "rgba(255,255,255,0.10)",
          divider: "rgba(255,255,255,0.14)",
          btnBorder: "rgba(255,255,255,0.10)",
          btnActiveBg: "rgba(255,255,255,0.10)",
          btnHoverBg: "rgba(255,255,255,0.06)",
          text: "rgba(255,255,255,0.92)",
          textDim: "rgba(255,255,255,0.72)",
          surfaceBg:
            "linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01))",
          panelBg: "rgba(20,22,28,0.98)",
        }
      : {
          cardBg: "#f8fafc",
          barBg: "rgba(0,0,0,0.03)",
          border: "rgba(0,0,0,0.10)",
          divider: "rgba(0,0,0,0.14)",
          btnBorder: "rgba(0,0,0,0.10)",
          btnActiveBg: "rgba(0,0,0,0.08)",
          btnHoverBg: "rgba(0,0,0,0.05)",
          text: "rgba(0,0,0,0.86)",
          textDim: "rgba(0,0,0,0.62)",
          surfaceBg: "linear-gradient(180deg, rgba(0,0,0,0.02), rgba(0,0,0,0.01))",
          panelBg: "rgba(255,255,255,0.98)",
        };

  function ToolButton(props: {
    title: string;
    active?: boolean;
    disabled?: boolean;
    onClick: () => void;
    children: React.ReactNode;
    width?: number;
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
          width: props.width ?? 36,
          height: 36,
          borderRadius: 12,
          border: `1px solid ${colors.btnBorder}`,
          background: props.active ? colors.btnActiveBg : "transparent",
          color: colors.text,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: props.disabled ? "not-allowed" : "pointer",
          opacity: props.disabled ? 0.5 : 1,
          transition: "background 120ms ease",
        }}
        onMouseEnter={(e) => {
          if (props.disabled) return;
          const el = e.currentTarget;
          if (!props.active) el.style.background = colors.btnHoverBg;
        }}
        onMouseLeave={(e) => {
          const el = e.currentTarget;
          if (!props.active) el.style.background = "transparent";
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
          background: colors.divider,
          margin: "0 8px",
          alignSelf: "center",
        }}
      />
    );
  }

  function MenuButton(props: {
    title: string;
    disabled?: boolean;
    active?: boolean;
    onClick: () => void;
    icon: React.ReactNode;
    label: string;
  }) {
    return (
      <button
        type="button"
        title={props.title}
        disabled={props.disabled}
        onMouseDown={(e) => e.preventDefault()}
        onClick={props.onClick}
        style={{
          height: 36,
          padding: "0 10px",
          borderRadius: 12,
          border: `1px solid ${colors.btnBorder}`,
          background: props.active ? colors.btnActiveBg : "transparent",
          color: colors.text,
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          cursor: props.disabled ? "not-allowed" : "pointer",
          opacity: props.disabled ? 0.5 : 1,
          transition: "background 120ms ease",
        }}
        onMouseEnter={(e) => {
          if (props.disabled) return;
          const el = e.currentTarget;
          if (!props.active) el.style.background = colors.btnHoverBg;
        }}
        onMouseLeave={(e) => {
          const el = e.currentTarget;
          if (!props.active) el.style.background = "transparent";
        }}
      >
        {props.icon}
        <span style={{ fontWeight: 700, fontSize: 12 }}>{props.label}</span>
        <ChevronDown size={16} />
      </button>
    );
  }

  function MenuPanel(props: { items: MenuItem[]; onClose: () => void }) {
    return (
      <div
        style={{
          position: "absolute",
          top: 44,
          left: 0,
          minWidth: 220,
          padding: 8,
          borderRadius: 14,
          border: `1px solid ${colors.border}`,
          background: colors.panelBg,
          boxShadow:
            theme === "dark"
              ? "0 18px 50px rgba(0,0,0,0.50)"
              : "0 18px 50px rgba(0,0,0,0.16)",
          zIndex: 20,
        }}
      >
        {props.items.map((it) => (
          <button
            key={it.id}
            type="button"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => {
              it.onSelect();
              props.onClose();
            }}
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "10px 10px",
              borderRadius: 12,
              border: "none",
              background: it.active ? colors.btnActiveBg : "transparent",
              color: colors.text,
              cursor: "pointer",
              textAlign: "left",
            }}
            onMouseEnter={(e) => {
              if (!it.active) e.currentTarget.style.background = colors.btnHoverBg;
            }}
            onMouseLeave={(e) => {
              if (!it.active) e.currentTarget.style.background = "transparent";
            }}
          >
            <span style={{ width: 18, display: "inline-flex", justifyContent: "center" }}>
              {it.active ? <Check size={16} /> : it.icon ?? null}
            </span>
            <span style={{ fontSize: 13, fontWeight: 700 }}>{it.label}</span>
          </button>
        ))}
      </div>
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

  function toggleTheme() {
    setTheme((t) => (t === "dark" ? "light" : "dark"));
  }

  function isHeadingActive(level: number) {
    return !!editor?.isActive("heading", { level });
  }

  function isParagraphActive() {
    return !!editor?.isActive("paragraph");
  }

  function isListActive(kind: "bullet" | "ordered" | "task") {
    if (!editor) return false;
    if (kind === "bullet") return editor.isActive("bulletList");
    if (kind === "ordered") return editor.isActive("orderedList");
    return editor.isActive("taskList");
  }

  const headingMenuItems: MenuItem[] = [
    {
      id: "p",
      label: "Paragraph",
      icon: <Heading size={16} />,
      active: isParagraphActive(),
      onSelect: () => editor?.chain().focus().setParagraph().run(),
    },
    {
      id: "h1",
      label: "Heading 1",
      icon: <Heading1 size={16} />,
      active: isHeadingActive(1),
      onSelect: () => editor?.chain().focus().toggleHeading({ level: 1 }).run(),
    },
    {
      id: "h2",
      label: "Heading 2",
      icon: <Heading2 size={16} />,
      active: isHeadingActive(2),
      onSelect: () => editor?.chain().focus().toggleHeading({ level: 2 }).run(),
    },
    {
      id: "h3",
      label: "Heading 3",
      icon: <Heading3 size={16} />,
      active: isHeadingActive(3),
      onSelect: () => editor?.chain().focus().toggleHeading({ level: 3 }).run(),
    },
    {
      id: "h4",
      label: "Heading 4",
      icon: <Heading4 size={16} />,
      active: isHeadingActive(4),
      onSelect: () => editor?.chain().focus().toggleHeading({ level: 4 }).run(),
    },
  ];

  const listMenuItems: MenuItem[] = [
    {
      id: "bullet",
      label: "Bullet list",
      icon: <List size={16} />,
      active: isListActive("bullet"),
      onSelect: () => editor?.chain().focus().toggleBulletList().run(),
    },
    {
      id: "ordered",
      label: "Ordered list",
      icon: <ListOrdered size={16} />,
      active: isListActive("ordered"),
      onSelect: () => editor?.chain().focus().toggleOrderedList().run(),
    },
    {
      id: "task",
      label: "Task list",
      icon: <ListChecks size={16} />,
      active: isListActive("task"),
      onSelect: () => editor?.chain().focus().toggleTaskList().run(),
    },
  ];

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
          border: `1px solid ${theme === "dark" ? "rgba(0,0,0,0.10)" : "rgba(0,0,0,0.10)"}`,
          boxShadow: "0 10px 30px rgba(0,0,0,0.06)",
          background: colors.cardBg,
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
            borderBottom: `1px solid ${colors.border}`,
            background: colors.barBg,
            position: "relative",
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

          {/* Group 2: Heading + List dropdowns + Quote + Code block */}
          <div ref={headingMenuRef} style={{ position: "relative" }}>
            <MenuButton
              title="Heading"
              disabled={!editor}
              active={headingMenuOpen}
              onClick={() => setHeadingMenuOpen((v) => !v)}
              icon={<Heading size={18} />}
              label="Heading"
            />
            {headingMenuOpen && (
              <MenuPanel items={headingMenuItems} onClose={() => setHeadingMenuOpen(false)} />
            )}
          </div>

          <div ref={listMenuRef} style={{ position: "relative" }}>
            <MenuButton
              title="List"
              disabled={!editor}
              active={listMenuOpen}
              onClick={() => setListMenuOpen((v) => !v)}
              icon={<List size={18} />}
              label="List"
            />
            {listMenuOpen && <MenuPanel items={listMenuItems} onClose={() => setListMenuOpen(false)} />}
          </div>

          <ToolButton
            title="Blockquote"
            active={!!editor?.isActive("blockquote")}
            disabled={!editor}
            onClick={() => editor?.chain().focus().toggleBlockquote().run()}
          >
            <Quote size={18} />
          </ToolButton>

          <ToolButton
            title="Code block"
            active={!!editor?.isActive("codeBlock")}
            disabled={!editor}
            onClick={() => editor?.chain().focus().toggleCodeBlock().run()}
          >
            <CodeSquare size={18} />
          </ToolButton>

          <Divider />

          {/* Group 3: Bold/Italic/Strike/Code/Underline/Highlight/Link */}
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

          <ToolButton
            title="Underline"
            active={!!editor?.isActive("underline")}
            disabled={!editor}
            onClick={() => editor?.chain().focus().toggleUnderline().run()}
          >
            <UnderlineIcon size={18} />
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

          <Divider />

          {/* Group 4: Superscript/Subscript */}
          <ToolButton
            title="Superscript"
            active={!!editor?.isActive("superscript")}
            disabled={!editor}
            onClick={() => editor?.chain().focus().toggleSuperscript().run()}
          >
            <SuperscriptIcon size={18} />
          </ToolButton>

          <ToolButton
            title="Subscript"
            active={!!editor?.isActive("subscript")}
            disabled={!editor}
            onClick={() => editor?.chain().focus().toggleSubscript().run()}
          >
            <SubscriptIcon size={18} />
          </ToolButton>

          <Divider />

          {/* Group 5: Align */}
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

          {/* Group 6: Add */}
          <div ref={addMenuRef} style={{ position: "relative" }}>
            <ToolButton
              title="Add"
              disabled={!editor}
              active={addMenuOpen}
              onClick={() => setAddMenuOpen((v) => !v)}
            >
              <Plus size={18} />
            </ToolButton>

            {addMenuOpen && (
              <div
                style={{
                  position: "absolute",
                  top: 44,
                  right: 0,
                  width: 320,
                  borderRadius: 16,
                  border: `1px solid ${colors.border}`,
                  background: colors.panelBg,
                  boxShadow:
                    theme === "dark"
                      ? "0 18px 50px rgba(0,0,0,0.50)"
                      : "0 18px 50px rgba(0,0,0,0.16)",
                  padding: 12,
                  zIndex: 30,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                  <div
                    style={{
                      width: 34,
                      height: 34,
                      borderRadius: 12,
                      border: `1px solid ${colors.btnBorder}`,
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: colors.text,
                    }}
                  >
                    <FileUp size={18} />
                  </div>
                  <div>
                    <div style={{ fontWeight: 800, fontSize: 13, color: colors.text }}>Add</div>
                    <div style={{ fontSize: 12, color: colors.textDim }}>
                      Drop a file or pick from disk (next step: real upload).
                    </div>
                  </div>
                </div>

                <div
                  style={{
                    borderRadius: 16,
                    border: `1px dashed ${theme === "dark" ? "rgba(255,255,255,0.18)" : "rgba(0,0,0,0.18)"}`,
                    background: theme === "dark" ? "rgba(255,255,255,0.03)" : "rgba(0,0,0,0.02)",
                    padding: 14,
                    color: colors.text,
                    textAlign: "center",
                  }}
                >
                  <div style={{ fontWeight: 800, marginBottom: 6 }}>Drag & drop</div>
                  <div style={{ fontSize: 12, color: colors.textDim, marginBottom: 10 }}>
                    Or click to choose a file
                  </div>
                  <button
                    type="button"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => {
                      window.alert("Upload will be implemented in the next step.");
                    }}
                    style={{
                      height: 36,
                      padding: "0 12px",
                      borderRadius: 12,
                      border: `1px solid ${colors.btnBorder}`,
                      background: theme === "dark" ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)",
                      color: colors.text,
                      fontWeight: 800,
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 8,
                    }}
                  >
                    <FileUp size={18} />
                    Choose file
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Right side: theme toggle + save */}
          <div style={{ flex: 1 }} />

          <ToolButton
            title={theme === "dark" ? "Switch to light" : "Switch to dark"}
            disabled={!editor}
            onClick={toggleTheme}
          >
            {theme === "dark" ? <Moon size={18} /> : <Sun size={18} />}
          </ToolButton>

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
              border: `1px solid ${colors.btnBorder}`,
              background: theme === "dark" ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)",
              color: colors.text,
              fontWeight: 800,
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
            background: colors.surfaceBg,
            padding: 18,
          }}
        >
          <div
            style={{
              borderRadius: 18,
              background: theme === "dark" ? "rgba(255,255,255,0.02)" : "rgba(0,0,0,0.02)",
              border: `1px solid ${colors.border}`,
              padding: 14,
              color: colors.text,
            }}
          >
            {/* NOTE: we keep editor focus stable; no blur handler here */}
            <EditorContent editor={editor} />
          </div>
        </div>
      </div>

      <div style={{ fontSize: 12, opacity: 0.6, marginTop: 8, marginBottom: 16 }}>
        Autosave: edits are saved after a short pause.
      </div>
    </div>
  );
}
