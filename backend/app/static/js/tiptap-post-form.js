import { Editor } from "https://esm.sh/@tiptap/core@2.6.6";
import StarterKit from "https://esm.sh/@tiptap/starter-kit@2.6.6";

const initEditor = () => {
  const editorElement = document.getElementById("tiptap-editor");
  const toolbarElement = document.getElementById("tiptap-toolbar");
  const errorBox = document.getElementById("tiptap-error");
  const loadingElement = document.getElementById("tiptap-loading");
  const bodyField = document.getElementById("body-field");
  const form = editorElement?.closest("form");

  if (!(editorElement && toolbarElement && errorBox && loadingElement && bodyField && form)) {
    return;
  }

  const toolbarButtonClass =
    "px-3 py-1 rounded border border-gruvbox-bg2 bg-gruvbox-bg text-white text-sm hover:bg-gruvbox-bg1 transition-colors";
  const activeButtonClass = "bg-gruvbox-yellow text-gruvbox-bg font-semibold border-gruvbox-yellow";

  const removeLoading = () => {
    if (loadingElement?.parentNode) {
      loadingElement.remove();
    }
  };

  const showError = (error) => {
    const message = error?.message || String(error);
    const stack = error?.stack ? `\n\n${error.stack}` : "";

    removeLoading();
    errorBox.classList.remove("hidden");
    errorBox.textContent = `${message}${stack}`;
  };

  const toolbarActions = [
    {
      name: "bold",
      label: "Bold",
      command: (editor) => editor.chain().focus().toggleBold().run(),
      isActive: (editor) => editor.isActive("bold"),
    },
    {
      name: "italic",
      label: "Italic",
      command: (editor) => editor.chain().focus().toggleItalic().run(),
      isActive: (editor) => editor.isActive("italic"),
    },
    {
      name: "heading1",
      label: "H1",
      command: (editor) => editor.chain().focus().toggleHeading({ level: 1 }).run(),
      isActive: (editor) => editor.isActive("heading", { level: 1 }),
    },
    {
      name: "heading2",
      label: "H2",
      command: (editor) => editor.chain().focus().toggleHeading({ level: 2 }).run(),
      isActive: (editor) => editor.isActive("heading", { level: 2 }),
    },
    {
      name: "bulletList",
      label: "Bullet List",
      command: (editor) => editor.chain().focus().toggleBulletList().run(),
      isActive: (editor) => editor.isActive("bulletList"),
    },
    {
      name: "orderedList",
      label: "Ordered List",
      command: (editor) => editor.chain().focus().toggleOrderedList().run(),
      isActive: (editor) => editor.isActive("orderedList"),
    },
    {
      name: "codeBlock",
      label: "Code Block",
      command: (editor) => editor.chain().focus().toggleCodeBlock().run(),
      isActive: (editor) => editor.isActive("codeBlock"),
    },
    {
      name: "blockquote",
      label: "Blockquote",
      command: (editor) => editor.chain().focus().toggleBlockquote().run(),
      isActive: (editor) => editor.isActive("blockquote"),
    },
  ];

  const buildToolbar = (editor) => {
    toolbarElement.innerHTML = "";

    toolbarActions.forEach((action) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.action = action.name;
      button.textContent = action.label;
      button.className = toolbarButtonClass;
      toolbarElement.appendChild(button);
    });

    toolbarElement.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-action]");
      if (!button) return;

      event.preventDefault();
      const action = toolbarActions.find((item) => item.name === button.dataset.action);
      if (!action) return;

      action.command(editor);
      updateToolbarState(editor);
      bodyField.value = editor.getHTML();
    });
  };

  const updateToolbarState = (editor) => {
    toolbarElement.querySelectorAll("button[data-action]").forEach((button) => {
      const action = toolbarActions.find((item) => item.name === button.dataset.action);
      if (!action) return;

      const isActive = action.isActive(editor);
      button.className = `${toolbarButtonClass} ${isActive ? activeButtonClass : ""}`.trim();
    });
  };

  try {
    const editor = new Editor({
      element: editorElement,
      extensions: [StarterKit],
      content: bodyField.value?.trim() || "<p>Start writing your post...</p>",
      onCreate: ({ editor }) => {
        bodyField.value = editor.getHTML();
        updateToolbarState(editor);
      },
      onUpdate: ({ editor }) => {
        bodyField.value = editor.getHTML();
        updateToolbarState(editor);
      },
      onSelectionUpdate: ({ editor }) => {
        bodyField.value = editor.getHTML();
        updateToolbarState(editor);
      },
    });

    buildToolbar(editor);
    removeLoading();
    editorElement.classList.add("tiptap-ready");
    window.__tiptapPostForm = editor;

    form.addEventListener("submit", () => {
      bodyField.value = editor.getHTML();
    });
  } catch (error) {
    showError(error);
  }
};

document.addEventListener("DOMContentLoaded", initEditor);
