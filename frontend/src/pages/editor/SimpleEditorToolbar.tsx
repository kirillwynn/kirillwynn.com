// frontend/src/pages/editor/SimpleEditorToolbar.tsx
//
// Toolbar (Simple Editor style).
// - Compact icon buttons (closer to the official demo)
// - Custom tooltip (rounded, light surface)
// - Heading/List dropdown buttons are icon-only (no "Heading"/"List" labels)
// - Horizontal scroll instead of wrapping

import { useCallback, useMemo, useRef, useState } from "react";
import type { ReactNode, RefObject } from "react";
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
  icon?: ReactNode;
  active?: boolean;
  onSelect: () => void;
};

type TooltipState = {
  text: string;
  x: number;
  y: number;
};

function useOutsideClick<T extends HTMLElement>(
  ref: RefObject<T | null>,
  onOutside: () => void,
  enabled: boolean,
) {
  const onOutsideStable = useCallback(onOutside, [onOutside]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useMemo(() => {
    if (!enabled) return;

    function onDocMouseDown(e: MouseEvent) {
      const el = ref.current;
      if (!el) return;
      if (e.target instanceof Node && el.contains(e.target)) return;
      onOutsideStable();
    }

    document.addEventListener("mousedown", onDocMouseDown);
    return () => document.removeEventListener("mousedown", onDocMouseDown);
  }, [ref, enabled, onOutsideStable]);
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

  // Compact sizing closer to the reference UI
  const BTN = 28;
  const ICON = 16;

  const colors =
    theme === "dark"
      ? {
          barBg: "rgba(255,255,255,0.02)",
          border: "rgba(255,255,255,0.10)",
          divider: "rgba(255,255,255,0.14)",
          btnActiveBg: "rgba(255,255,255,0.10)",
          btnHoverBg: "rgba(255,255,255,0.06)",
          text: "rgba(255,255,255,0.92)",
          textDim: "rgba(255,255,255,0.72)",
          panelBg: "rgba(20,22,28,0.98)",
        }
      : {
          barBg: "rgba(0,0,0,0.02)",
          border: "rgba(0,0,0,0.10)",
          divider: "rgba(0,0,0,0.14)",
          btnActiveBg: "rgba(0,0,0,0.08)",
          btnHoverBg: "rgba(0,0,0,0.05)",
          text: "rgba(0,0,0,0.86)",
          textDim: "rgba(0,0,0,0.62)",
          panelBg: "rgba(255,255,255,0.98)",
        };

  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

  function showTooltip(text: string, el: HTMLElement) {
    const r = el.getBoundingClientRect();
    setTooltip({
      text,
      x: r.left + r.width / 2,
      y: r.top - 10,
    });
  }

  function hideTooltip() {
    setTooltip(null);
  }

  function Divider() {
    return (
      <div
        style={{
          width: 1,
          height: 18,
          background: colors.divider,
          margin: "0 8px",
          alignSelf: "center",
          flex: "0 0 auto",
        }}
      />
    );
  }

  function ToolButton(p: {
    title: string;
    active?: boolean;
    disabled?: boolean;
    onClick: () => void;
    children: ReactNode;
    width?: number;
  }) {
    return (
      <button
        type="button"
        aria-label={p.title}
        disabled={p.disabled}
        onMouseDown={(e) => {
          // Keep focus in editor; prevents blur-triggered autosave when clicking toolbar.
          e.preventDefault();
        }}
        onMouseEnter={(e) => {
          if (p.disabled) return;
          showTooltip(p.title, e.currentTarget);
        }}
        onMouseLeave={() => hideTooltip()}
        onFocus={(e) => {
          if (p.disabled) return;
          showTooltip(p.title, e.currentTarget);
        }}
        onBlur={() => hideTooltip()}
        onClick={() => {
          hideTooltip();
          p.onClick();
        }}
        style={{
          width: p.width ?? BTN,
          height: BTN,
          borderRadius: 10,
          border: "none",
          background: p.active ? colors.btnActiveBg : "transparent",
          color: colors.text,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: p.disabled ? "not-allowed" : "pointer",
          opacity: p.disabled ? 0.5 : 1,
          transition: "background 120ms ease",
          flex: "0 0 auto",
        }}
        onMouseMove={(e) => {
          // Keep tooltip anchored even when moving between buttons quickly.
          if (!tooltip) return;
          showTooltip(p.title, e.currentTarget);
        }}
      >
        {p.children}
      </button>
    );
  }

  function MenuButton(p: {
    title: string;
    disabled?: boolean;
    active?: boolean;
    onClick: () => void;
    icon: ReactNode;
    showLabel?: boolean;
    label?: string;
  }) {
    return (
      <button
        type="button"
        aria-label={p.title}
        disabled={p.disabled}
        onMouseDown={(e) => e.preventDefault()}
        onMouseEnter={(e) => {
          if (p.disabled) return;
          showTooltip(p.title, e.currentTarget);
        }}
        onMouseLeave={() => hideTooltip()}
        onFocus={(e) => {
          if (p.disabled) return;
          showTooltip(p.title, e.currentTarget);
        }}
        onBlur={() => hideTooltip()}
        onClick={() => {
          hideTooltip();
          p.onClick();
        }}
        style={{
          height: BTN,
          padding: p.showLabel ? "0 10px" : "0 8px",
          borderRadius: 10,
          border: "none",
          background: p.active ? colors.btnActiveBg : "transparent",
          color: colors.text,
          display: "inline-flex",
          alignItems: "center",
          gap: p.showLabel ? 8 : 6,
          cursor: p.disabled ? "not-allowed" : "pointer",
          opacity: p.disabled ? 0.5 : 1,
          transition: "background 120ms ease",
          flex: "0 0 auto",
        }}
      >
        {p.icon}
        {p.showLabel && p.label ? (
          <span style={{ fontWeight: 700, fontSize: 12 }}>{p.label}</span>
        ) : null}
        <ChevronDown size={14} />
      </button>
    );
  }

  function MenuPanel(p: { items: MenuItem[]; onClose: () => void }) {
    return (
      <div
        style={{
          position: "absolute",
          top: 36,
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
              {it.active ? <Check size={14} /> : it.icon ?? null}
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
        icon: <Heading size={ICON} />,
        active: isParagraphActive(),
        onSelect: () => editor?.chain().focus().setParagraph().run(),
      },
      {
        id: "h1",
        label: "Heading 1",
        icon: <Heading1 size={ICON} />,
        active: isHeadingActive(1),
        onSelect: () => editor?.chain().focus().toggleHeading({ level: 1 }).run(),
      },
      {
        id: "h2",
        label: "Heading 2",
        icon: <Heading2 size={ICON} />,
        active: isHeadingActive(2),
        onSelect: () => editor?.chain().focus().toggleHeading({ level: 2 }).run(),
      },
      {
        id: "h3",
        label: "Heading 3",
        icon: <Heading3 size={ICON} />,
        active: isHeadingActive(3),
        onSelect: () => editor?.chain().focus().toggleHeading({ level: 3 }).run(),
      },
      {
        id: "h4",
        label: "Heading 4",
        icon: <Heading4 size={ICON} />,
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
        icon: <List size={ICON} />,
        active: isListActive("bullet"),
        onSelect: () => editor?.chain().focus().toggleBulletList().run(),
      },
      {
        id: "ordered",
        label: "Ordered list",
        icon: <ListOrdered size={ICON} />,
        active: isListActive("ordered"),
        onSelect: () => editor?.chain().focus().toggleOrderedList().run(),
      },
      {
        id: "task",
        label: "Task list",
        icon: <ListChecks size={ICON} />,
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
        position: "relative",
      }}
    >
      {/* Tooltip (rounded, light surface like reference UI) */}
      {tooltip && (
        <div
          style={{
            position: "fixed",
            left: tooltip.x,
            top: tooltip.y,
            transform: "translate(-50%, -100%)",
            padding: "6px 10px",
            borderRadius: 10,
            border: "1px solid rgba(0,0,0,0.10)",
            background: "rgba(255,255,255,0.96)",
            color: "rgba(0,0,0,0.88)",
            fontSize: 12,
            fontWeight: 700,
            boxShadow: "0 10px 30px rgba(0,0,0,0.18)",
            pointerEvents: "none",
            zIndex: 9999,
            whiteSpace: "nowrap",
          }}
        >
          {tooltip.text}
        </div>
      )}

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: 10,
          borderBottom: `1px solid ${colors.border}`,
          background: colors.barBg,
          overflowX: "auto",
          flexWrap: "nowrap",
          WebkitOverflowScrolling: "touch",
        }}
      >
        {/* Group 1: Undo/Redo */}
        <ToolButton
          title="Undo"
          disabled={!editor || !editor.can().undo()}
          onClick={() => editor?.chain().focus().undo().run()}
        >
          <Undo2 size={ICON} />
        </ToolButton>
        <ToolButton
          title="Redo"
          disabled={!editor || !editor.can().redo()}
          onClick={() => editor?.chain().focus().redo().run()}
        >
          <Redo2 size={ICON} />
        </ToolButton>

        <Divider />

        {/* Group 2: Heading + List dropdowns + Quote + Code block */}
        <div ref={headingMenuRef} style={{ position: "relative", flex: "0 0 auto" }}>
          <MenuButton
            title="Heading"
            disabled={!editor}
            active={headingMenuOpen}
            onClick={() => setHeadingMenuOpen((v) => !v)}
            icon={<Heading size={ICON} />}
          />
          {headingMenuOpen && (
            <MenuPanel items={headingMenuItems} onClose={() => setHeadingMenuOpen(false)} />
          )}
        </div>

        <div ref={listMenuRef} style={{ position: "relative", flex: "0 0 auto" }}>
          <MenuButton
            title="List"
            disabled={!editor}
            active={listMenuOpen}
            onClick={() => setListMenuOpen((v) => !v)}
            icon={<List size={ICON} />}
          />
          {listMenuOpen && <MenuPanel items={listMenuItems} onClose={() => setListMenuOpen(false)} />}
        </div>

        <ToolButton
          title="Blockquote"
          active={!!editor?.isActive("blockquote")}
          disabled={!editor}
          onClick={() => editor?.chain().focus().toggleBlockquote().run()}
        >
          <Quote size={ICON} />
        </ToolButton>

        <ToolButton
          title="Code block"
          active={!!editor?.isActive("codeBlock")}
          disabled={!editor}
          onClick={() => editor?.chain().focus().toggleCodeBlock().run()}
        >
          <CodeSquare size={ICON} />
        </ToolButton>

        <Divider />

        {/* Group 3: Bold/Italic/Strike/Code/Underline/Highlight/Link */}
        <ToolButton
          title="Bold"
          active={!!editor?.isActive("bold")}
          disabled={!editor}
          onClick={() => editor?.chain().focus().toggleBold().run()}
        >
          <Bold size={ICON} />
        </ToolButton>

        <ToolButton
          title="Italic"
          active={!!editor?.isActive("italic")}
          disabled={!editor}
          onClick={() => editor?.chain().focus().toggleItalic().run()}
        >
          <Italic size={ICON} />
        </ToolButton>

        <ToolButton
          title="Strikethrough"
          active={!!editor?.isActive("strike")}
          disabled={!editor}
          onClick={() => editor?.chain().focus().toggleStrike().run()}
        >
          <Strikethrough size={ICON} />
        </ToolButton>

        <ToolButton
          title="Inline code"
          active={!!editor?.isActive("code")}
          disabled={!editor}
          onClick={() => editor?.chain().focus().toggleCode().run()}
        >
          <Code size={ICON} />
        </ToolButton>

        <ToolButton
          title="Underline"
          active={!!editor?.isActive("underline")}
          disabled={!editor}
          onClick={() => editor?.chain().focus().toggleUnderline().run()}
        >
          <UnderlineIcon size={ICON} />
        </ToolButton>

        <ToolButton
          title="Highlight"
          active={!!editor?.isActive("highlight")}
          disabled={!editor}
          onClick={() => editor?.chain().focus().toggleHighlight().run()}
        >
          <Highlighter size={ICON} />
        </ToolButton>

        <ToolButton
          title="Link"
          active={!!editor?.isActive("link")}
          disabled={!editor}
          onClick={toggleLink}
        >
          <Link2 size={ICON} />
        </ToolButton>

        <Divider />

        {/* Group 4: Superscript/Subscript */}
        <ToolButton
          title="Superscript"
          active={!!editor?.isActive("superscript")}
          disabled={!editor}
          onClick={() => editor?.chain().focus().toggleSuperscript().run()}
        >
          <SuperscriptIcon size={ICON} />
        </ToolButton>

        <ToolButton
          title="Subscript"
          active={!!editor?.isActive("subscript")}
          disabled={!editor}
          onClick={() => editor?.chain().focus().toggleSubscript().run()}
        >
          <SubscriptIcon size={ICON} />
        </ToolButton>

        <Divider />

        {/* Group 5: Align */}
        <ToolButton
          title="Align left"
          active={!!editor?.isActive({ textAlign: "left" })}
          disabled={!editor}
          onClick={() => editor?.chain().focus().setTextAlign("left").run()}
        >
          <AlignLeft size={ICON} />
        </ToolButton>

        <ToolButton
          title="Align center"
          active={!!editor?.isActive({ textAlign: "center" })}
          disabled={!editor}
          onClick={() => editor?.chain().focus().setTextAlign("center").run()}
        >
          <AlignCenter size={ICON} />
        </ToolButton>

        <ToolButton
          title="Align right"
          active={!!editor?.isActive({ textAlign: "right" })}
          disabled={!editor}
          onClick={() => editor?.chain().focus().setTextAlign("right").run()}
        >
          <AlignRight size={ICON} />
        </ToolButton>

        <ToolButton
          title="Justify"
          active={!!editor?.isActive({ textAlign: "justify" })}
          disabled={!editor}
          onClick={() => editor?.chain().focus().setTextAlign("justify").run()}
        >
          <AlignJustify size={ICON} />
        </ToolButton>

        <Divider />

        {/* Group 6: Add */}
        <div ref={addMenuRef} style={{ position: "relative", flex: "0 0 auto" }}>
          <ToolButton
            title="Add"
            disabled={!editor}
            active={addMenuOpen}
            onClick={() => setAddMenuOpen((v) => !v)}
          >
            <Plus size={ICON} />
          </ToolButton>

          {addMenuOpen && (
            <div
              style={{
                position: "absolute",
                top: 36,
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
                    background: theme === "dark" ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.04)",
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
                    height: 34,
                    padding: "0 12px",
                    borderRadius: 12,
                    border: "none",
                    background: theme === "dark" ? "rgba(255,255,255,0.10)" : "rgba(0,0,0,0.06)",
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

        {/* Right side */}
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8, flex: "0 0 auto" }}>
          <ToolButton
            title={theme === "dark" ? "Switch to light" : "Switch to dark"}
            disabled={!editor}
            onClick={onToggleTheme}
          >
            {theme === "dark" ? <Moon size={ICON} /> : <Sun size={ICON} />}
          </ToolButton>

          <button
            type="button"
            aria-label="Save"
            onMouseDown={(e) => e.preventDefault()}
            onMouseEnter={(e) => {
              if (!editor) return;
              showTooltip("Save", e.currentTarget);
            }}
            onMouseLeave={() => hideTooltip()}
            onFocus={(e) => {
              if (!editor) return;
              showTooltip("Save", e.currentTarget);
            }}
            onBlur={() => hideTooltip()}
            onClick={() => {
              hideTooltip();
              onSave();
            }}
            disabled={!editor}
            style={{
              height: BTN,
              padding: "0 10px",
              borderRadius: 10,
              border: "none",
              background: theme === "dark" ? "rgba(255,255,255,0.10)" : "rgba(0,0,0,0.06)",
              color: colors.text,
              fontWeight: 800,
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              cursor: !editor ? "not-allowed" : "pointer",
              opacity: !editor ? 0.6 : 1,
              flex: "0 0 auto",
            }}
          >
            <Save size={ICON} />
            <span style={{ fontSize: 12 }}>Save</span>
          </button>
        </div>
      </div>
    </div>
  );
}
