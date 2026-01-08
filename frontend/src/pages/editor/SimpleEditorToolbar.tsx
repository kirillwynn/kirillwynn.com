// frontend/src/pages/editor/SimpleEditorToolbar.tsx
//
// Toolbar (Simple Editor style).
// - Compact pill controls (closer to template.tiptap.dev)
// - Custom rounded tooltips (no native browser "title" tooltips)
// - Heading dropdown shows current value (P/H1/H2/...)
// - List dropdown is icon-only (tooltip carries meaning)

import { useEffect, useMemo, useRef, useState } from "react";
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

function useOutsideClick<T extends HTMLElement>(
  ref: RefObject<T | null>,
  onOutside: () => void,
  enabled: boolean,
) {
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

function TooltipWrap(props: { label: string; children: ReactNode; disabled?: boolean }) {
  const { label, children, disabled } = props;
  const [open, setOpen] = useState(false);

  return (
    <span
      style={{ position: "relative", display: "inline-flex" }}
      onMouseEnter={() => !disabled && setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      {children}
      <span
        role="tooltip"
        style={{
          position: "absolute",
          top: -40,
          left: "50%",
          transform: open ? "translate(-50%, 0)" : "translate(-50%, 4px)",
          opacity: open ? 1 : 0,
          pointerEvents: "none",
          transition: "opacity 120ms ease, transform 120ms ease",
          padding: "6px 10px",
          borderRadius: 12,
          background: "rgba(255,255,255,0.92)",
          color: "rgba(17,24,39,0.92)",
          border: "1px solid rgba(0,0,0,0.08)",
          boxShadow: "0 10px 25px rgba(0,0,0,0.12)",
          fontSize: 12,
          fontWeight: 700,
          whiteSpace: "nowrap",
          zIndex: 50,
        }}
      >
        {label}
      </span>
    </span>
  );
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

  const BTN = {
    size: 32,
    radius: 10,
    icon: 16,
    pillPaddingX: 8,
    pillGap: 8,
  } as const;

  function ToolButton(p: {
    tooltip: string;
    active?: boolean;
    disabled?: boolean;
    onClick: () => void;
    children: ReactNode;
    width?: number;
  }) {
    const disabled = !!p.disabled;

    return (
      <TooltipWrap label={p.tooltip} disabled={disabled}>
        <button
          type="button"
          aria-label={p.tooltip}
          disabled={disabled}
          onMouseDown={(e) => {
            // Keep focus in editor; prevents blur-triggered autosave when clicking toolbar.
            e.preventDefault();
          }}
          onClick={p.onClick}
          style={{
            width: p.width ?? BTN.size,
            height: BTN.size,
            borderRadius: BTN.radius,
            border: `1px solid ${colors.btnBorder}`,
            background: p.active ? colors.btnActiveBg : "transparent",
            color: colors.text,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: disabled ? "not-allowed" : "pointer",
            opacity: disabled ? 0.5 : 1,
            transition: "background 120ms ease",
          }}
          onMouseEnter={(e) => {
            if (disabled) return;
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
      </TooltipWrap>
    );
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
        }}
      />
    );
  }

  function MenuButton(p: {
    tooltip: string;
    disabled?: boolean;
    active?: boolean;
    onClick: () => void;
    icon: ReactNode;
    valueText?: string; // "P", "H1", ...
    showValue?: boolean;
  }) {
    const disabled = !!p.disabled;

    return (
      <TooltipWrap label={p.tooltip} disabled={disabled}>
        <button
          type="button"
          aria-label={p.tooltip}
          disabled={disabled}
          onMouseDown={(e) => e.preventDefault()}
          onClick={p.onClick}
          style={{
            height: BTN.size,
            padding: `0 ${BTN.pillPaddingX}px`,
            borderRadius: BTN.radius,
            border: `1px solid ${colors.btnBorder}`,
            background: p.active ? colors.btnActiveBg : "transparent",
            color: colors.text,
            display: "inline-flex",
            alignItems: "center",
            gap: BTN.pillGap,
            cursor: disabled ? "not-allowed" : "pointer",
            opacity: disabled ? 0.5 : 1,
            transition: "background 120ms ease",
          }}
          onMouseEnter={(e) => {
            if (disabled) return;
            const el = e.currentTarget;
            if (!p.active) el.style.background = colors.btnHoverBg;
          }}
          onMouseLeave={(e) => {
            const el = e.currentTarget;
            if (!p.active) el.style.background = "transparent";
          }}
        >
          {p.icon}
          {p.showValue && (
            <span style={{ fontWeight: 800, fontSize: 12, letterSpacing: 0.2 }}>
              {p.valueText ?? ""}
            </span>
          )}
          <ChevronDown size={16} />
        </button>
      </TooltipWrap>
    );
  }

  function MenuPanel(p: { items: MenuItem[]; onClose: () => void }) {
    return (
      <div
        style={{
          position: "absolute",
          top: 40,
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
            <span style={{ fontSize: 13, fontWeight: 800 }}>{it.label}</span>
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

  function getHeadingValueText() {
    if (!editor) return "P";
    if (isHeadingActive(1)) return "H1";
    if (isHeadingActive(2)) return "H2";
    if (isHeadingActive(3)) return "H3";
    if (isHeadingActive(4)) return "H4";
    return "P";
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
        padding: 10,
        borderBottom: `1px solid ${colors.border}`,
        background: colors.barBg,
        position: "relative",
      }}
    >
      <ToolButton
        tooltip="Undo"
        disabled={!editor || !editor.can().undo()}
        onClick={() => editor?.chain().focus().undo().run()}
      >
        <Undo2 size={BTN.icon} />
      </ToolButton>

      <ToolButton
        tooltip="Redo"
        disabled={!editor || !editor.can().redo()}
        onClick={() => editor?.chain().focus().redo().run()}
      >
        <Redo2 size={BTN.icon} />
      </ToolButton>

      <Divider />

      <div ref={headingMenuRef} style={{ position: "relative" }}>
        <MenuButton
          tooltip="Heading"
          disabled={!editor}
          active={headingMenuOpen}
          onClick={() => setHeadingMenuOpen((v) => !v)}
          icon={<Heading size={BTN.icon} />}
          valueText={getHeadingValueText()}
          showValue
        />
        {headingMenuOpen && (
          <MenuPanel items={headingMenuItems} onClose={() => setHeadingMenuOpen(false)} />
        )}
      </div>

      <div ref={listMenuRef} style={{ position: "relative" }}>
        <MenuButton
          tooltip="List"
          disabled={!editor}
          active={listMenuOpen}
          onClick={() => setListMenuOpen((v) => !v)}
          icon={<List size={BTN.icon} />}
          showValue={false}
        />
        {listMenuOpen && <MenuPanel items={listMenuItems} onClose={() => setListMenuOpen(false)} />}
      </div>

      <ToolButton
        tooltip="Blockquote"
        active={!!editor?.isActive("blockquote")}
        disabled={!editor}
        onClick={() => editor?.chain().focus().toggleBlockquote().run()}
      >
        <Quote size={BTN.icon} />
      </ToolButton>

      <ToolButton
        tooltip="Code block"
        active={!!editor?.isActive("codeBlock")}
        disabled={!editor}
        onClick={() => editor?.chain().focus().toggleCodeBlock().run()}
      >
        <CodeSquare size={BTN.icon} />
      </ToolButton>

      <Divider />

      <ToolButton
        tooltip="Bold"
        active={!!editor?.isActive("bold")}
        disabled={!editor}
        onClick={() => editor?.chain().focus().toggleBold().run()}
      >
        <Bold size={BTN.icon} />
      </ToolButton>

      <ToolButton
        tooltip="Italic"
        active={!!editor?.isActive("italic")}
        disabled={!editor}
        onClick={() => editor?.chain().focus().toggleItalic().run()}
      >
        <Italic size={BTN.icon} />
      </ToolButton>

      <ToolButton
        tooltip="Strikethrough"
        active={!!editor?.isActive("strike")}
        disabled={!editor}
        onClick={() => editor?.chain().focus().toggleStrike().run()}
      >
        <Strikethrough size={BTN.icon} />
      </ToolButton>

      <ToolButton
        tooltip="Inline code"
        active={!!editor?.isActive("code")}
        disabled={!editor}
        onClick={() => editor?.chain().focus().toggleCode().run()}
      >
        <Code size={BTN.icon} />
      </ToolButton>

      <ToolButton
        tooltip="Underline"
        active={!!editor?.isActive("underline")}
        disabled={!editor}
        onClick={() => editor?.chain().focus().toggleUnderline().run()}
      >
        <UnderlineIcon size={BTN.icon} />
      </ToolButton>

      <ToolButton
        tooltip="Highlight"
        active={!!editor?.isActive("highlight")}
        disabled={!editor}
        onClick={() => editor?.chain().focus().toggleHighlight().run()}
      >
        <Highlighter size={BTN.icon} />
      </ToolButton>

      <ToolButton
        tooltip="Link"
        active={!!editor?.isActive("link")}
        disabled={!editor}
        onClick={toggleLink}
      >
        <Link2 size={BTN.icon} />
      </ToolButton>

      <Divider />

      <ToolButton
        tooltip="Superscript"
        active={!!editor?.isActive("superscript")}
        disabled={!editor}
        onClick={() => editor?.chain().focus().toggleSuperscript().run()}
      >
        <SuperscriptIcon size={BTN.icon} />
      </ToolButton>

      <ToolButton
        tooltip="Subscript"
        active={!!editor?.isActive("subscript")}
        disabled={!editor}
        onClick={() => editor?.chain().focus().toggleSubscript().run()}
      >
        <SubscriptIcon size={BTN.icon} />
      </ToolButton>

      <Divider />

      <ToolButton
        tooltip="Align left"
        active={!!editor?.isActive({ textAlign: "left" })}
        disabled={!editor}
        onClick={() => editor?.chain().focus().setTextAlign("left").run()}
      >
        <AlignLeft size={BTN.icon} />
      </ToolButton>

      <ToolButton
        tooltip="Align center"
        active={!!editor?.isActive({ textAlign: "center" })}
        disabled={!editor}
        onClick={() => editor?.chain().focus().setTextAlign("center").run()}
      >
        <AlignCenter size={BTN.icon} />
      </ToolButton>

      <ToolButton
        tooltip="Align right"
        active={!!editor?.isActive({ textAlign: "right" })}
        disabled={!editor}
        onClick={() => editor?.chain().focus().setTextAlign("right").run()}
      >
        <AlignRight size={BTN.icon} />
      </ToolButton>

      <ToolButton
        tooltip="Justify"
        active={!!editor?.isActive({ textAlign: "justify" })}
        disabled={!editor}
        onClick={() => editor?.chain().focus().setTextAlign("justify").run()}
      >
        <AlignJustify size={BTN.icon} />
      </ToolButton>

      <Divider />

      <div ref={addMenuRef} style={{ position: "relative" }}>
        <ToolButton
          tooltip="Add"
          disabled={!editor}
          active={addMenuOpen}
          onClick={() => setAddMenuOpen((v) => !v)}
        >
          <Plus size={BTN.icon} />
        </ToolButton>

        {addMenuOpen && (
          <div
            style={{
              position: "absolute",
              top: 40,
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
                  height: 34,
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

      <div style={{ flex: 1 }} />

      <ToolButton
        tooltip={theme === "dark" ? "Switch to light" : "Switch to dark"}
        disabled={!editor}
        onClick={onToggleTheme}
      >
        {theme === "dark" ? <Moon size={BTN.icon} /> : <Sun size={BTN.icon} />}
      </ToolButton>

      <TooltipWrap label="Save" disabled={!editor}>
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={onSave}
          disabled={!editor}
          aria-label="Save"
          style={{
            height: BTN.size,
            padding: "0 12px",
            borderRadius: BTN.radius,
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
          <Save size={BTN.icon} />
          Save
        </button>
      </TooltipWrap>
    </div>
  );
}
