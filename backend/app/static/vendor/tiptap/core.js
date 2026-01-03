// Minimal locally vendored TipTap-like shim for environments without external ESM access.
// This is not the full TipTap implementation but matches the surface API used by the admin post form.

export class Editor {
  constructor(options = {}) {
    const {
      element,
      content = "",
      onCreate,
      onUpdate,
      onSelectionUpdate,
    } = options;

    if (!element) {
      throw new Error("Editor requires a target element");
    }

    this.element = element;
    this.options = options;

    this.element.contentEditable = "true";
    this.element.classList.add("ProseMirror");
    this.element.innerHTML = content;

    // Bind listeners
    this._onInput = () => {
      onUpdate?.({ editor: this });
    };
    this._onSelection = () => {
      if (document.activeElement === this.element) {
        onSelectionUpdate?.({ editor: this });
      }
    };

    this.element.addEventListener("input", this._onInput);
    document.addEventListener("selectionchange", this._onSelection);

    // Run onCreate callback
    onCreate?.({ editor: this });
  }

  getHTML() {
    return this.element.innerHTML;
  }

  chain() {
    const editor = this;
    const commands = [];

    const runCommands = () => {
      commands.forEach((fn) => fn());
      return true;
    };

    const api = {
      focus() {
        commands.push(() => editor.element.focus());
        return api;
      },
      toggleBold() {
        commands.push(() => document.execCommand("bold", false));
        return api;
      },
      toggleItalic() {
        commands.push(() => document.execCommand("italic", false));
        return api;
      },
      toggleHeading({ level }) {
        commands.push(() => {
          const tag = `h${level}`;
          document.execCommand("formatBlock", false, tag);
        });
        return api;
      },
      toggleBulletList() {
        commands.push(() => document.execCommand("insertUnorderedList", false));
        return api;
      },
      toggleOrderedList() {
        commands.push(() => document.execCommand("insertOrderedList", false));
        return api;
      },
      toggleCodeBlock() {
        commands.push(() => {
          const selection = window.getSelection();
          if (!selection || selection.rangeCount === 0) return;
          const range = selection.getRangeAt(0);
          const wrapper = document.createElement("pre");
          const code = document.createElement("code");
          code.appendChild(range.extractContents());
          wrapper.appendChild(code);
          range.insertNode(wrapper);
          selection.collapse(wrapper, 1);
        });
        return api;
      },
      run: runCommands,
    };

    return api;
  }

  isActive(name, attrs = {}) {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return false;
    let node = selection.anchorNode;
    if (!node) return false;
    if (node.nodeType === Node.TEXT_NODE) {
      node = node.parentElement;
    }
    if (!(node instanceof Element)) return false;

    const matchesTag = (tagName) => node.closest(tagName);

    switch (name) {
      case "bold":
        return document.queryCommandState("bold");
      case "italic":
        return document.queryCommandState("italic");
      case "heading":
        return matchesTag(`h${attrs.level || 1}`) != null;
      case "bulletList":
        return matchesTag("ul") != null;
      case "orderedList":
        return matchesTag("ol") != null;
      case "codeBlock":
        return matchesTag("pre") != null;
      default:
        return false;
    }
  }
}

export default { Editor };
