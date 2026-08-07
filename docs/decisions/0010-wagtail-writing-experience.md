# ADR 0010: Wagtail writing experience

- Status: Accepted
- Date: 2026-08-07
- Scope: Stage 19B CMS authoring experience

## Context

The existing `BlogPostPage` editor already had the correct ownership model:
Wagtail managed drafts, revisions, comments, preview, publication, scheduling,
expiry, permissions, images, choosers, and the 13-block `StreamField`. Its
default presentation was nevertheless too wide and visually read like a
technical block constructor. Panel chrome, block actions, and the floating
Draftail toolbar competed with the post itself, while title, excerpt, and body
did not read as one writing surface.

Replacing Wagtail, Draftail, `StreamField`, Django forms, the rich-text database
format, or the content API would create a second content lifecycle and break
the established revision and publication boundary. Copying Wagtail templates
or patching its DOM would also make an otherwise presentation-only change
dependent on private implementation details.

## Decision

Wagtail 7.4 remains the sole owner of the entire editorial lifecycle and
Draftail remains the rich-text editor. Stage 19B is a supported-extension-point
layer around those components:

- `TabbedInterface`, `ObjectList`, `FieldPanel`, `classname`, and panel `attrs`
  define the unchanged **Write**, **Publish**, and **SEO & sharing** information
  architecture and expose page-specific styling scopes;
- `WAGTAILADMIN_RICH_TEXT_EDITORS` selects a small
  `DraftailRichTextArea` subclass whose only behavior change is the stable
  `Rich text editor` accessible name;
- `register_rich_text_features` keeps Wagtail's page-link handler and the
  existing `bold`, `italic`, and `link` feature set;
- `insert_global_admin_css` loads one Wagtail-admin stylesheet, with all editor
  rules scoped beneath supported panel attributes and `BlogPostPage` classes;
- `insert_editor_js` loads a small script on Wagtail editor views. It exits
  unless the writing-surface attribute is present and only announces existing
  validation errors and focuses Wagtail's first invalid control;
- block `form_attrs` annotate the existing block definitions for content-shaped
  presentation. No custom block form template or Telepath adapter is required.

The writing surface is centred at a maximum of 56 rem (896 px). Title, excerpt,
and body remain ordinary Wagtail form fields. StreamField move, drag,
duplicate, delete, block labels, comments, validation, and the native Add block
autocomplete all remain present and keyboard reachable; their visual emphasis
increases on hover and `focus-within`, while touch layouts keep controls
visible.

## Toolbar architecture

The toolbar is Draftail's own toolbar for each `RichTextBlock`, not a shared
project toolbar or a second editor state. Bold, Italic, Link, line break,
revision comment, and Wagtail's native pin control retain their Draftail
commands, accessible labels, tooltips, shortcuts, selection handling, and
chooser integration. Styling only makes floating and pinned forms compact and
keeps them within the active block and writing column. Pinned inactive toolbars
are quieter; the focused editor's toolbar is fully prominent.

`Cmd/Ctrl+B`, `Cmd/Ctrl+I`, `Cmd/Ctrl+K`, undo/redo, Escape, and native focus
restoration therefore remain Draftail/Wagtail behavior. The pin preference is
intentionally user-controlled: Wagtail exposes a supported Pin toolbar action,
but no documented project setting to force every editor permanently pinned.
Stage 19B does not simulate a pin click or inspect private Draftail state.

## Rich-text and StreamField storage boundary

The widget inherits Wagtail's normal `DraftailRichTextArea` value conversion.
It accepts and returns Wagtail database HTML, including external `href` values
and internal `<a linktype="page" id="…">` entities. Paste sanitization and
chooser conversion remain Wagtail-owned. Loading and saving without a content
change does not introduce a new serializer or rewrite the supported HTML
semantics.

The following stable block names, order, IDs, values, validation, and JSON
representation remain unchanged:

1. `rich_text`
2. `heading`
3. `image`
4. `gallery`
5. `quote`
6. `bulleted_list`
7. `numbered_list`
8. `checklist`
9. `inline_code`
10. `code_block`
11. `table`
12. `horizontal_divider`
13. `link`

No schema migration, API change, public-renderer change, publication timestamp
change, or newsletter-decision change is part of this decision.

## Accessibility contract

All native controls remain semantic buttons or form controls. Formatting
actions have accessible names independent of tooltips; Add block, move,
duplicate, and delete remain keyboard reachable; focus is visible in both
themes; validation messages are live alerts; the first invalid field receives
logical focus; and no outline is removed without an equivalent
`:focus-visible` state. Layout coverage includes 768×1024, 1024×768,
1440×900, 1920×1080, 200% zoom, light/dark themes, reduced motion, and no
horizontal overflow.

## Rejected alternatives

- A Markdown-only editor, Tiptap, Lexical, ProseMirror, Editor.js, or React SPA
  would duplicate or replace Wagtail-owned storage and lifecycle behavior.
- A custom toolbar driven by a global observer, DOM polling, simulated clicks,
  visible translated labels, or Draftail internal state would be brittle and
  inaccessible.
- Forking Wagtail edit or block templates would couple this presentation layer
  to private markup and make Wagtail upgrades unsafe.
- Adding underline would change the agreed rich-text feature/storage contract
  and conflict visually with links.

## Consequences and rollback

The experience can be rolled back without data work: remove the custom widget
setting, hook-loaded assets, panel attributes/classes, and block `form_attrs`.
Stored StreamField JSON, database HTML, revisions, publication state, and the
public API remain valid because Stage 19B never owns them. A Wagtail upgrade
must rerun the editor browser contract against the documented Draftail and
StreamField interfaces before changing selectors or behavior.

The trade-off is deliberate: toolbar pinning and chooser behavior stay within
what Wagtail publicly supports, even when a fully custom editor could make
those interactions more opinionated.

## References

- [Wagtail settings](https://docs.wagtail.org/en/stable/reference/settings.html)
- [Rich text internals](https://docs.wagtail.org/en/v7.4/extending/rich_text_internals.html)
- [Page editing interface](https://docs.wagtail.org/en/stable-7.4.x/advanced_topics/customization/page_editing_interface.html)
- [Admin templates and hooks](https://docs.wagtail.org/en/v7.4/advanced_topics/customization/admin_templates.html)
- [Client-side components](https://docs.wagtail.org/en/stable-7.4.x/extending/extending_client_side.html)
- [StreamField block customisation](https://docs.wagtail.org/en/v7.4/advanced_topics/customization/streamfield_blocks.html)
- [Extending Draftail](https://docs.wagtail.org/en/stable/extending/extending_draftail.html)
