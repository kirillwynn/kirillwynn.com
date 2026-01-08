// frontend/src/pages/editor/EditorPage.tsx

import { useEffect, useMemo, useState } from "react";
import type { MouseEvent as ReactMouseEvent } from "react";
import { useParams } from "react-router-dom";

import { getPost, type PostItem } from "@/api/posts";

import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";

import Link from "@tiptap/extension-link";
import Underline from "@tiptap/extension-underline";
import TextAlign from "@tiptap/extension-text-align";
import Highlight from "@tiptap/extension-highlight";
import TaskList from "@tiptap/extension-task-list";
import TaskItem from "@tiptap/extension-task-item";
import Superscript from "@tiptap/extension-superscript";
import Subscript from "@tiptap/extension-subscript";

import { TextSelection } from "@tiptap/pm/state";

import "./tiptap-prose.css";

import { formatIso, isEnter, stableStringify } from "./editorUtils";
import { SimpleEditorToolbar, type ThemeMode } from "./SimpleEditorToolbar";
import { usePostAutosave } from "./usePostAutosave";

type LoadState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; post: PostItem };

export function EditorPage() {
  const params = useParams();

  const postId = useMemo(() => {
    const raw = (params as any).id ?? (params as any).postId;
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  }, [params]);

  const [state, setState] = useState<LoadState>({ kind: "idle" });

  // TipTap view is created only after the editor is mounted.
  // We must not call commands like `setContent` before that.
  const [isEditorMounted, setIsEditorMounted] = useState(false);

  // UI state
  const [theme, setTheme] = useState<ThemeMode>("dark");

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        codeBlock: false,
        // Disable extensions that we register explicitly below to avoid duplicate names warnings.
        ...({ link: false, underline: false } as Record<string, false>),
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
      },
    },
    onCreate: () => {
      setIsEditorMounted(true);
    },
    onDestroy: () => {
      setIsEditorMounted(false);
    },
  });

  const autosave = usePostAutosave({
    postId,
    editor: editor ?? null,
    enabled: state.kind === "ready",
    onPostUpdated: (post) => setState({ kind: "ready", post }),
  });

  useEffect(() => {
    if (!editor) return;

    const off = editor.on("update", ({ editor: ed }) => {
      autosave.setBodyJsonStrDraft(stableStringify(ed.getJSON()));
    });

    return () => {
      // @ts-ignore
      if (typeof off === "function") off();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editor]);

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

  // Hydrate from server -> drafts + editor content
  useEffect(() => {
    if (state.kind !== "ready") return;
    if (!editor) return;
    if (!isEditorMounted) return;
    autosave.hydrateFromServer(state.post);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.kind, state.kind === "ready" ? state.post.id : null, editor, isEditorMounted]);

  const statusValue = state.kind === "ready" ? state.post.status ?? "—" : "—";

  const saveBadge =
    autosave.saveState.kind === "saving"
      ? "Saving…"
      : autosave.saveState.kind === "saved"
        ? "Saved"
        : autosave.saveState.kind === "error"
          ? "Save error"
          : "";

  const colors =
    theme === "dark"
      ? {
          cardBg: "#0f1115",
          border: "rgba(255,255,255,0.10)",
          text: "rgba(255,255,255,0.92)",
          surfaceBg: "linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01))",
          editorBg: "rgba(255,255,255,0.02)",
        }
      : {
          cardBg: "#f8fafc",
          border: "rgba(0,0,0,0.10)",
          text: "rgba(0,0,0,0.86)",
          surfaceBg: "linear-gradient(180deg, rgba(0,0,0,0.02), rgba(0,0,0,0.01))",
          editorBg: "rgba(0,0,0,0.02)",
        };

  function onEditorShellMouseDown(e: ReactMouseEvent<HTMLDivElement>) {
    if (!editor) return;

    const target = e.target as HTMLElement | null;
    if (target?.closest?.(".ProseMirror")) return;

    e.preventDefault();

    const view = editor.view;
    const coords = view.posAtCoords({ left: e.clientX, top: e.clientY });

    if (coords) {
      const tr = view.state.tr.setSelection(
        TextSelection.near(view.state.doc.resolve(coords.pos)),
      );
      view.dispatch(tr);
    }

    editor.commands.focus();
  }

  return (
    <div style={{ fontFamily: "ui-sans-serif, system-ui", maxWidth: 980, margin: "0 auto" }}>
      <header style={{ marginBottom: 16 }}>
        <h1 style={{ fontSize: 22, marginBottom: 4 }}>Editor</h1>
        <p style={{ opacity: 0.7, margin: 0 }}>Post editor. TipTap rich editor is enabled.</p>
      </header>

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
                background:
                  autosave.saveState.kind === "error"
                    ? "rgba(255,0,0,0.06)"
                    : "rgba(0,0,0,0.03)",
                fontWeight: 600,
              }}
              title={autosave.saveState.kind === "error" ? autosave.saveState.message : ""}
            >
              {saveBadge}
            </span>
          </div>
        )}
      </div>

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

      <div style={{ marginBottom: 12 }}>
        <input
          placeholder="Post title"
          value={autosave.titleDraft}
          onChange={(e) => autosave.setTitleDraft(e.target.value)}
          onBlur={() => autosave.flushSaveNow("blur")}
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

      <div
        style={{
          borderRadius: 22,
          overflow: "hidden",
          border: `1px solid ${colors.border}`,
          boxShadow: "0 10px 30px rgba(0,0,0,0.06)",
          background: colors.cardBg,
        }}
      >
        <SimpleEditorToolbar
          editor={editor ?? null}
          theme={theme}
          onToggleTheme={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
          onSave={() => autosave.flushSaveNow("manual")}
        />

        <div style={{ background: colors.surfaceBg, padding: 18 }}>
          <div
            onMouseDown={onEditorShellMouseDown}
            style={{
              borderRadius: 18,
              background: colors.editorBg,
              border: `1px solid ${colors.border}`,
              color: colors.text,
              // The editor itself owns padding via ProseMirror CSS.
              padding: 0,
              // Make the whole surface feel like one monolithic input.
              boxShadow: "inset 0 1px 0 rgba(255,255,255,0.04)",
            }}
          >
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
