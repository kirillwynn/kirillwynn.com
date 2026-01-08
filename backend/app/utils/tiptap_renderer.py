from __future__ import annotations

import json
from html import escape
from typing import Any
from urllib.parse import urlparse


_ALLOWED_ALIGN = {"left", "center", "right", "justify"}
_ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}


def render_tiptap_json(payload: Any) -> str:
    """
    Render TipTap/ProseMirror JSON into HTML.

    This renderer intentionally supports a limited, explicit subset of nodes/marks.
    Unknown nodes are rendered by recursively rendering their children.
    """

    if payload is None:
        return ""

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            return ""

    if isinstance(payload, list):
        nodes = payload
    elif isinstance(payload, dict):
        if payload.get("type") == "doc":
            nodes = payload.get("content", [])
        else:
            nodes = [payload]
    else:
        return ""

    return _render_nodes(nodes)


def _render_nodes(nodes: Any) -> str:
    if not isinstance(nodes, list):
        return ""
    return "".join(_render_node(node) for node in nodes if isinstance(node, dict))


def _render_node(node: dict[str, Any]) -> str:
    node_type = node.get("type")
    content = node.get("content", [])
    attrs = node.get("attrs", {}) or {}

    if node_type == "text":
        return _render_text(node)

    if node_type == "paragraph":
        return _wrap("p", _render_nodes(content), attrs=attrs)

    if node_type == "heading":
        level = int(attrs.get("level", 1) or 1)
        level = min(max(level, 1), 6)
        return _wrap(f"h{level}", _render_nodes(content), attrs=attrs)

    if node_type == "blockquote":
        return _wrap("blockquote", _render_nodes(content))

    if node_type == "bulletList":
        return _wrap("ul", _render_nodes(content))

    if node_type == "orderedList":
        return _wrap("ol", _render_nodes(content))

    if node_type == "listItem":
        return _wrap("li", _render_nodes(content))

    if node_type == "taskList":
        return _wrap("ul", _render_nodes(content), extra_class="task-list")

    if node_type == "taskItem":
        checked = bool(attrs.get("checked"))
        prefix = "[x] " if checked else "[ ] "
        return _wrap("li", prefix + _render_nodes(content), extra_class="task-item")

    if node_type == "codeBlock":
        return _wrap("pre", _wrap("code", escape(_extract_text(node))))

    if node_type == "hardBreak":
        return "<br>"

    if node_type == "horizontalRule":
        return "<hr>"

    # Fallback: render children for unknown nodes.
    return _render_nodes(content)


def _render_text(node: dict[str, Any]) -> str:
    text = escape(node.get("text", "") or "")
    marks = node.get("marks") or []

    for mark in marks:
        if not isinstance(mark, dict):
            continue
        mark_type = mark.get("type")
        attrs = mark.get("attrs", {}) or {}

        if mark_type == "bold":
            text = _wrap("strong", text)
        elif mark_type == "italic":
            text = _wrap("em", text)
        elif mark_type == "strike":
            text = _wrap("s", text)
        elif mark_type == "code":
            text = _wrap("code", text)
        elif mark_type == "underline":
            text = _wrap("u", text)
        elif mark_type == "highlight":
            text = _wrap("mark", text)
        elif mark_type == "superscript":
            text = _wrap("sup", text)
        elif mark_type == "subscript":
            text = _wrap("sub", text)
        elif mark_type == "link":
            href = _safe_href(attrs.get("href"))
            if href:
                title = attrs.get("title")
                text = _wrap_link(text, href=href, title=title)

    return text


def _wrap(tag: str, inner: str, attrs: dict[str, Any] | None = None, extra_class: str | None = None) -> str:
    class_name = _alignment_class(attrs)
    if extra_class:
        class_name = f"{class_name} {extra_class}".strip()
    if class_name:
        return f'<{tag} class="{escape(class_name)}">{inner}</{tag}>'
    return f"<{tag}>{inner}</{tag}>"


def _wrap_link(text: str, href: str, title: str | None = None) -> str:
    title_attr = f' title="{escape(title)}"' if title else ""
    return (
        f'<a href="{escape(href)}"{title_attr} '
        'target="_blank" rel="noopener noreferrer">'
        f"{text}</a>"
    )


def _alignment_class(attrs: dict[str, Any] | None) -> str:
    if not attrs:
        return ""
    align = attrs.get("textAlign")
    if align in _ALLOWED_ALIGN:
        return f"align-{align}"
    return ""


def _extract_text(node: dict[str, Any]) -> str:
    parts: list[str] = []
    content = node.get("content", []) or []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text":
            parts.append(item.get("text", "") or "")
        elif item.get("type") == "hardBreak":
            parts.append("\n")
        else:
            parts.append(_extract_text(item))
    return "".join(parts)


def _safe_href(href: str | None) -> str | None:
    if not href or not isinstance(href, str):
        return None
    if href.startswith(("/", "#")):
        return href
    parsed = urlparse(href)
    if parsed.scheme in _ALLOWED_URL_SCHEMES:
        return href
    return None
