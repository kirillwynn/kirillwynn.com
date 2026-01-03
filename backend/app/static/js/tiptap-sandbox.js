const status = document.getElementById("status");
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

const init = async () => {
  if (!editorElement) {
    showError(new Error("Editor container missing"));
    return;
  }

  try {
    const [{ Editor }, { default: StarterKit }] = await Promise.all([
      import("https://esm.sh/@tiptap/core@2.6.6"),
      import("https://esm.sh/@tiptap/starter-kit@2.6.6"),
    ]);

    const editor = new Editor({
      element: editorElement,
      extensions: [StarterKit],
      content: "<p>Hello from TipTap sandbox. Click and type here.</p>",
    });

    window.__tiptap = editor;
    editor.commands.focus("end");

    showReady("TipTap loaded. Click inside the box to edit.");
  } catch (error) {
    showError(error);
  }
};

init();
