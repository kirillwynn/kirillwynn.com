import { Editor } from "https://esm.sh/@tiptap/core@2.6.6";
import StarterKit from "https://esm.sh/@tiptap/starter-kit@2.6.6";

const status = document.getElementById("status");
const toolbarElement = document.getElementById("tiptap-toolbar");
const editorElement = document.getElementById("tiptap-editor");
const loadingElement = document.getElementById("tiptap-loading");
const errorBox = document.getElementById("tiptap-error");

const removeLoading = () => {
  if (loadingElement?.parentNode) {
    loadingElement.remove();
  }
};

const showError = (error) => {
  const message = error?.message || String(error);
  const stack = error?.stack ? `\n\n${error.stack}` : "";

  if (errorBox) {
    errorBox.style.display = "block";
    errorBox.textContent = `${message}${stack}`;
  }

  if (status) {
    status.textContent = "Failed to load TipTap";
    status.style.color = "#b00020";
  }

  removeLoading();
};

const showReady = (message) => {
  if (status) {
    status.textContent = message;
    status.style.color = "#0a7b1f";
  }

  removeLoading();
};

const baseButtonStyles = (button) => {
  button.style.padding = "6px 10px";
  button.style.border = "1px solid #ccc";
  button.style.borderRadius = "4px";
  button.style.background = "#f5f5f5";
  button.style.cursor = "pointer";
};

const setActiveState = (button, active) => {
  button.style.backgroundColor = active ? "#d3e4ff" : "#f5f5f5";
  button.style.borderColor = active ? "#2b70f7" : "#ccc";
  button.style.color = active ? "#0a2d6b" : "#000";
};

const createToolbar = (editor) => {
  if (!toolbarElement) {
    return () => {};
  }

  const buttonsConfig = [
    {
      label: "Bold",
      command: () => editor.chain().focus().toggleBold().run(),
      isActive: () => editor.isActive("bold"),
    },
    {
      label: "Italic",
      command: () => editor.chain().focus().toggleItalic().run(),
      isActive: () => editor.isActive("italic"),
    },
    {
      label: "H1",
      command: () =>
        editor.chain().focus().toggleHeading({ level: 1 }).run(),
      isActive: () => editor.isActive("heading", { level: 1 }),
    },
    {
      label: "H2",
      command: () =>
        editor.chain().focus().toggleHeading({ level: 2 }).run(),
      isActive: () => editor.isActive("heading", { level: 2 }),
    },
    {
      label: "Bullet List",
      command: () => editor.chain().focus().toggleBulletList().run(),
      isActive: () => editor.isActive("bulletList"),
    },
    {
      label: "Ordered List",
      command: () => editor.chain().focus().toggleOrderedList().run(),
      isActive: () => editor.isActive("orderedList"),
    },
    {
      label: "Code Block",
      command: () => editor.chain().focus().toggleCodeBlock().run(),
      isActive: () => editor.isActive("codeBlock"),
    },
    {
      label: "Blockquote",
      command: () => editor.chain().focus().toggleBlockquote().run(),
      isActive: () => editor.isActive("blockquote"),
    },
  ];

  toolbarElement.innerHTML = "";

  const buttonStates = buttonsConfig.map((config) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = config.label;
    baseButtonStyles(button);
    setActiveState(button, false);

    button.addEventListener("click", (event) => {
      event.preventDefault();
      config.command();
    });

    toolbarElement.appendChild(button);

    return { button, isActive: config.isActive };
  });

  const updateActiveStates = () => {
    buttonStates.forEach(({ button, isActive }) => {
      setActiveState(button, Boolean(isActive()));
    });
  };

  updateActiveStates();

  return updateActiveStates;
};

const init = () => {
  if (!editorElement) {
    showError(new Error("Editor container missing"));
    return;
  }

  if (!toolbarElement) {
    showError(new Error("Toolbar container missing"));
    return;
  }

  try {
    let updateActiveStates = () => {};

    const editor = new Editor({
      element: editorElement,
      extensions: [StarterKit],
      content: "<p>Hello from TipTap sandbox. Click and type here.</p>",
      onCreate: () => updateActiveStates(),
      onUpdate: () => updateActiveStates(),
      onSelectionUpdate: () => updateActiveStates(),
    });

    updateActiveStates = createToolbar(editor);

    window.__tiptap = editor;
    editor.commands.focus("end");
    updateActiveStates();

    showReady("TipTap loaded. Click inside the box to edit.");
  } catch (error) {
    showError(error);
  }
};

init();
