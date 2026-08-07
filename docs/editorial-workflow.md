# Editorial workflow

The staging editor lives at
[`https://staging.kirillwynn.com/cms/`](https://staging.kirillwynn.com/cms/).
Use it from a desktop browser for normal post work. `/django-admin/` is an
operational administration surface; it is not the primary post editor.

## The two page types

Wagtail **Pages** are a website tree, not filesystem directories:

```text
Root
└── Blog index (the Feed container)
    └── Blog post (one public post)
```

`BlogIndexPage` is the single container for the Feed.
Each `BlogPostPage` is one post beneath it. The editor resolves this container
dynamically; no deployed page ID is built into the `New post` shortcut.

## Write a new post

1. Sign in to `/cms/`.
2. Select the prominent **New post** action on the dashboard or in the main
   navigation.
3. In **Write**, enter the title, excerpt, and body. The body chooser groups
   the existing blocks as Text, Media, Lists, Code / Data, and Structure.
4. In **Publish**, add optional tags. Leave **Original publication date**
   empty for new work.
5. Leave **Notify subscribers on first publication** selected for an ordinary
   new post, or deliberately clear it when no publication email should be
   created.
6. Use Wagtail's normal actions:
   - **Save draft** stores a revision without changing the public site or
     creating email work.
   - **Preview** opens the immutable headless preview; the backend fallback is
     also available from Wagtail's preview modes.
   - **Set schedule** sets a future go-live or expiry time in Wagtail's status
     panel.
   - **Publish** makes the accepted revision live immediately.
7. Use **SEO & sharing** only when the default title, excerpt, canonical URL,
   and Open Graph fallbacks need to be overridden.

If `New post` is unavailable, do not guess a page ID or create a post
elsewhere in the tree. The dashboard explains whether the Blog index is
missing, ambiguous, misplaced, or unavailable under the current permissions.
Repair the tree or permissions first.

## The writing surface

The **Write** tab is a centred, quiet writing column. Title, excerpt, and body
are still ordinary Wagtail fields in one Django form: browser length counters
and backend validation remain authoritative. Block borders and controls become
more prominent on hover or keyboard focus; they remain visible on touch-sized
layouts. Nothing is automatically collapsed when focus moves elsewhere.

Rich Text is the normal Wagtail Draftail editor. Its compact toolbar contains
Bold, Italic, Link, line break, revision comment, and Wagtail's toolbar pin
control. Use `Cmd/Ctrl+B`, `Cmd/Ctrl+I`, and `Cmd/Ctrl+K`; normal undo/redo and
Escape behavior are unchanged. Pinning is an explicit Wagtail user preference,
not a project-side simulated click. Each Rich Text block owns exactly one
toolbar, so duplicate, reorder, and delete remain normal StreamField actions.

The Add block control uses Wagtail's searchable keyboard-accessible chooser and
the existing groups. The complete stored block contract is unchanged:

- **Text:** Rich text, Heading, Quote;
- **Media:** Image, Gallery;
- **Lists:** Bulleted list, Numbered list, Checklist;
- **Code / Data:** Inline code, Code block, Table;
- **Structure:** Horizontal divider, Link.

Images and internal links continue to use Wagtail choosers. Pasted Rich Text is
sanitized by Wagtail's converter; do not paste or hand-author database HTML.
Move, duplicate, delete, preview, comments, history, and restore remain Wagtail
operations rather than editor-specific shortcuts.

## Drafts, schedules, and unpublishing

Drafts and previews do not affect the Feed. A future-scheduled revision stays
non-public until Wagtail's scheduled-publication worker makes it live. An
expiry time is Wagtail's scheduled unpublish control.

To remove a live post from public view, open it in Wagtail and choose the
normal **Unpublish** action. This preserves its page and revision history.
Changing **Original publication date** in a draft does not reorder the public
Feed until that revision is published.

The original-date field never schedules, publishes, expires, restricts, or
unpublishes a page. Those lifecycle controls remain entirely Wagtail-owned.

Tags remain optional backend metadata for internal classification, search
relevance, and metadata. They are not promised as visible Feed filters.

## Restore an earlier revision

1. Open the post and select **History**.
2. Open the revision to inspect it.
3. Choose Wagtail's restore action. Restoration creates a new draft revision;
   it does not rewrite history.
4. Preview the restored draft, then publish or schedule it normally.

The archived content fields, including the original date, are revision-aware.
The newsletter decision is durable and separate from revisions. Restoring an
old revision cannot re-enable a notification after the first public decision.

## Import an archived post

1. Select **New post** and enter the archived title, excerpt, and body.
2. In **Publish**, set **Original publication date** to the date and time the
   material first appeared elsewhere.
3. Clear **Notify subscribers on first publication**.
4. Save and preview the draft.
5. Publish immediately or use Wagtail scheduling.

The public Feed, visible post date, HTML `<time datetime>`, and Open Graph
`article:published_time` use the original date. The API still retains the
actual site publication and update timestamps:

- `original_published_at`: the optional archive date;
- `published_at`: Wagtail's actual first publication on this site;
- `updated_at`: Wagtail's actual last publication/update timestamp;
- `display_published_at`: original date when present, otherwise actual site
  publication date.

Do not edit Wagtail's `first_published_at` or `last_published_at` values.

## Newsletter safety

The checkbox is intent stored with the draft revision. No decision and no
publication outbox event are created by draft save or preview.

At the first moment the post is actually public, the backend atomically locks
one durable result:

- **Queued**: one publication outbox event exists, with an audience cutoff
  taken from the actual public-publication time.
- **Suppressed**: no publication outbox event or delivery is created.

A scheduled or restricted post remains pending until it really becomes
public. After either result, the checkbox becomes read-only. Republish, edits,
slug changes, and restored revisions cannot change the result automatically.
This irreversibility prevents an archived or intentionally quiet post from
mailing subscribers later by accident.

To verify a post without sending a publication email:

1. use preview whenever public visibility is not required;
2. if live verification is required, use a controlled QA post and clear the
   notification checkbox before its first publication;
3. confirm the post shows **Suppressed** after publication;
4. unpublish or delete only that controlled QA post through Wagtail when the
   check is complete.

Never use a real user post for staging QA, and never enable notifications on a
live QA post.
