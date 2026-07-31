# ADR 0007: Editorial dates and first-publication email decision

Status: accepted

Date: 2026-07-30

Complements ADR 0002's content API, preview, and revalidation boundaries and
ADR 0004's email outbox/provider boundary.

## Context

The site needs a low-friction single-author workflow in Wagtail and a safe way
to import writing that was originally published elsewhere. Wagtail's
`first_published_at`, `last_published_at`, `go_live_at`, and `expire_at` already
have precise lifecycle meanings and must not be rewritten to simulate an
archive date.

The previous publication-email trigger created one outbox event when a post
first matched the public visibility policy. A revision-aware boolean by itself
cannot safely suppress an archive forever: republishing or restoring an older
revision could re-arm it unless the first public decision is recorded outside
revision content.

## Decision

### Wagtail remains the editor and lifecycle owner

`BlogPostPage` uses Wagtail 7.4's supported extension points:

- a custom `TabbedInterface`, `ObjectList`, field panels, title panel, and
  page form;
- `register_admin_urls`, `register_admin_menu_item`, and
  `construct_homepage_panels` hooks for the permission-aware `New post`
  shortcut;
- `insert_global_admin_css` for scoped, semantic-variable-based editor CSS;
- StreamField block `label`, `description`, and `group` metadata.

There is no separate Next.js editor, duplicated publishing state, or DOM
monkey-patching against Wagtail's private selectors. The shortcut resolves the
single valid root-level `BlogIndexPage` at request time, checks Wagtail's
add-child permission, and redirects to Wagtail's ordinary add-page view. A
missing, duplicated, or misplaced Blog index fails closed with an explanatory
dashboard state.

The editor has **Write**, **Publish**, and **SEO & sharing** tabs. Wagtail
continues to own drafts, revisions, preview modes, immediate/scheduled
publication, scheduled unpublication, rollback, permissions, images,
StreamField content, and page status controls.

All 13 existing body block names and stored JSON shapes remain unchanged.
Chooser-only descriptions and the Text, Media, Lists, Code / Data, and
Structure groups are migration-recorded metadata, not content conversion.

### Editorial and actual publication dates are separate

`BlogPostPage.original_published_at` is a nullable, revision-aware
`DateTimeField`. It means “first published outside this site.” It must be
timezone-aware, cannot be in the future, and—once a post has actually been
published here—cannot be later than the persisted Wagtail
`first_published_at`.

The effective display value is:

```text
display_published_at = original_published_at or first_published_at
```

The API change is additive:

- `published_at` remains Wagtail `first_published_at`;
- `updated_at` remains Wagtail `last_published_at`;
- `original_published_at` is nullable;
- `display_published_at` is the effective display value.

Feed cards, post metadata, HTML `<time datetime>`, previews, and Open Graph
`article:published_time` use the display value. Actual timestamps remain
available. The original date never affects live visibility, scheduling,
expiry, audience cutoff, email availability, revalidation event time, or the
test for first public publication.

Without search, the public queryset orders by SQL
`COALESCE(original_published_at, first_published_at) DESC, page_id DESC`.
The descending page ID is the deterministic pagination tie-break. PostgreSQL
must join the Wagtail base page table to the BlogPostPage child table to
evaluate that expression, so a conventional single-table expression index
cannot satisfy the complete ordering. We deliberately avoid a denormalized
second lifecycle timestamp and verify the PostgreSQL SQL/plan and ordering
directly. At this single-author data size PostgreSQL uses a bounded explicit
sort over the already-filtered public set. Existing visibility indexes and the
page primary key still support filtering and ties.

Search keeps Wagtail's supported PostgreSQL relevance compiler as the primary
order and its deterministic descending page-ID tie-break. Adding the
cross-table display expression as another search ordering would require
replacing or reaching inside that compiler, so it is not treated as a safe
secondary extension.

### Notification intent and durable decision are different state

`notify_subscribers_on_first_publication` is a revision-aware checkbox with a
default of true. It expresses the author's pending intent. A separate
`PostPublicationEmailDecision` one-to-one row records the durable state:

```text
pending --first actually public, checkbox on--> queued + one EmailOutbox
pending --first actually public, checkbox off-> suppressed + no EmailOutbox
```

Draft save and preview create neither a decision nor outbox work. A logical
pending state may therefore have no decision row for a never-published new
draft. Future-scheduled and restricted live revisions remain pending until
the canonical public policy accepts them.

Decision processing is one database transaction. It locks the
`BlogPostPage`, then locks or creates its decision row, reconciles any
pre-existing publication outbox event, rechecks public visibility, and either
creates the unique publication event or records suppression. Database
constraints enforce valid state/outbox/timestamp combinations, while the
existing conditional unique outbox constraint remains the final
one-publication-event boundary.

For a queued decision, `audience_cutoff`, `available_at`, and `decided_at` use
the actual decision time. They never use the archive date. Existing immutable
outbox snapshots, delivery fingerprints, provider contract IDs, idempotency
keys, and message semantics are unchanged. Suppression performs no provider
I/O and creates no `EmailDelivery`.

Once queued or suppressed, the CMS forces the checkbox to the accepted value,
makes it read-only, and shows the durable status. An older revision cannot
re-arm the post. Direct removal of a page restriction rechecks descendants,
revalidates their public caches, and makes any still-pending decision.
Restriction deletion caused by deleting a page is explicitly not a public
transition.

### Existing-data migration is non-mailing and reversible

The forward data migration creates decision rows only:

- an existing publication outbox event becomes `queued` and points to that
  unchanged event;
- any ever-published post without such an event becomes `suppressed`;
- a never-published draft, including a not-yet-public scheduled revision,
  remains `pending`.

It creates no outbox event or delivery and performs no provider call. The
reverse migration removes only decision rows; historical outbox, delivery,
recipient, snapshot, fingerprint, and provider identifiers are untouched.

## Consequences

- Archive dates can change through ordinary revisions and revalidation without
  corrupting Wagtail lifecycle history.
- Feed order can move after a republished archive-date change, while an
  unpublished draft cannot move the public Feed.
- First-publication email intent is explicit and defaults safely for ordinary
  new writing; archive suppression is durable.
- Queued posts retain existing protected email history. Suppressed decisions
  are deleted with an intentionally deleted page, while unpublish preserves
  both the post and decision.
- The editor uses stable Wagtail APIs and a small scoped theme, so Wagtail and
  Django Admin remain independently maintainable.
