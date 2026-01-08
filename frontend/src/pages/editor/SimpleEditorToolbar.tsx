// frontend/src/pages/editor/SimpleEditorToolbar.tsx
//
// Toolbar (Simple Editor style).
// - Renders 6 groups
// - Heading/List dropdowns
// - Theme toggle
// - Add menu UI-only
// - Accepts: editor, theme, onToggleTheme, onSave

import React, { useEffect, useMemo, useRef, useState } from "react";
import type { Editor } from "@tiptap/react";

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

export type ThemeMode = "dark" | "light";

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

export function SimpleEditorToolbar(props: {
  editor: Editor | null;
  theme: ThemeMode;
  onToggleTheme: () => void;
  onSave: () => void;
}) {
  const { editor, theme, onToggleTheme, onSave } = props;

  const [headingMenuOpen, setHeadingMenuOpen] = useState(false);
  const [listMenuOpen, setListMenuOpen] = useState(false);
  const [addMenuOpen, setAddMenuOpen] = useState(false);

  const headingMenuRef = useRef<HTMLDivElement>(null);
  const listMenuRef = useRef<HTMLDivElement>(null);
  const addMenuRef = useRef<HTMLDivElement>(null);

  useOutsideClick(headingMenuRef, () => setHeadingMenuOpen(false), headingMenuOpen);
  useOutsideClick(listMenuRef, () => setListMenuOpen(false), listMenuOpen);
  useOutsideClick(addMenuRef, () => setAddMenuOpen(false), addMenuOpen);

  const colors =
    theme === "dark"
      ? {
          barBg: "rgba(255,255,255,0.03)",
          border: "rgba(255,255,255,0.10)",
          divider: "rgba(255,255,255,0.14)",
          btnBorder: "rgba(255,255,255,0.10)",
          btnActiveBg: "rgba(255,255,255,0.10)",
          btnHoverBg: "rgba(255,255,255,0.06)",
          text: "rgba(255,255,255,0.92)",
          textDim: "rgba(255,255,255,0.72)",
          panelBg: "rgba(20,22,28,0.98)",
        }
      : {
          barBg: "rgba(0,0,0,0.03)",
          border: "rgba(0,0,0,0.10)",
          divider: "rgba(0,0,0,0.14)",
          btnBorder: "rgba(0,0,0,0.10)",
          btnActiveBg: "rgba(0,0,0,0.08)",
          btnHoverBg: "rgba(0,0,0,0.05)",
          text: "rgba(0,0,0,0.86)",
          textDim: "rgba(0,0,0,0.62)",
          panelBg: "rgba(255,255,255,0.98)",
        };

  function ToolButton(p: {
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
        title={p.title}
        disabled={p.disabled}
        onMouseDown={(e) => {
          // Keep focus in editor; prevents blur-triggered autosave when clicking toolbar.
          e.preventDefault();
        }}
        onClick={p.onClick}
        style={{
          width: p.width ?? 36,
          height: 36,
          borderRadius: 12,
          border: `1px solid ${colors.btnBorder}`,
          background: p.active ? colors.btnActiveBg : "transparent",
          color: colors.text,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: p.disabled ? "not-allowed" : "pointer",
          opacity: p.disabled ? 0.5 : 1,
          transition: "background 120ms ease",
        }}
        onMouseEnter={(e) => {
          if (p.disabled) return;
          const el = e.currentTarget;
          if (!p.active) el.style.background = colors.btnHoverBg;
        }}
        onMouseLeave={(e) => {
          const el = e.currentTarget;
          if (!p.active) el.style.background = "transparent";
        }}
      >
        {p.children}
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

  function MenuButton(p: {
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
        title={p.title}
        disabled={p.disabled}
        onMouseDown={(e) => e.preventDefault()}
        onClick={p.onClick}
        style={{
          height: 36,
          padding: "0 10px",
          borderRadius: 12,
          border: `1px solid ${colors.btnBorder}`,
          background: p.active ? colors.btnActiveBg : "transparent",
          color: colors.text,
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          cursor: p.disabled ? "not-allowed" : "pointer",
          opacity: p.disabled ? 0.5 : 1,
          transition: "background 120ms ease",
        }}
        onMouseEnter={(e) => {
          if (p.disabled) return;
          const el = e.currentTarget;
          if (!p.active) el.style.background = colors.btnHoverBg;
        }}
        onMouseLeave={(e) => {
          const el = e.currentTarget;
          if (!p.active) el.style.background = "transparent";
        }}
      >
        {p.icon}
        <span style={{ fontWeight: 700, fontSize: 12 }}>{p.label}</span>
        <ChevronDown size={16} />
      </button>
    );
  }

  function MenuPanel(p: { items: MenuItem[]; onClose: () => void }) {
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
        {p.items.map((it) => (
          <button
            key={it.id}
            type="button"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => {
              it.onSelect();
              p.onClose();
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

  const headingMenuItems: MenuItem[] = useMemo(
    () => [
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
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [editor, theme, headingMenuOpen],
  );

  const listMenuItems: MenuItem[] = useMemo(
    () => [
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
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [editor, theme, listMenuOpen],
  );

  return (
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
        {headingMenuOpen && <MenuPanel items={headingMenuItems} onClose={() => setHeadingMenuOpen(false)} />}
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

      <ToolButton title="Link" active={!!editor?.isActive("link")} disabled={!editor} onClick={toggleLink}>
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
                border: `1px dashed ${
                  theme === "dark" ? "rgba(255,255,255,0.18)" : "rgba(0,0,0,0.18)"
                }`,
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
                onClick={() => window.alert("Upload will be implemented in the next step.")}
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
        onClick={onToggleTheme}
      >
        {theme === "dark" ? <Moon size={18} /> : <Sun size={18} />}
      </ToolButton>

      <button
        type="button"
        onMouseDown={(e) => e.preventDefault()}
        onClick={onSave}
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
  );
}
