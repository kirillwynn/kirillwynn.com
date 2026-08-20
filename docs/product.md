# Product

## Purpose

kirillwynn.com is the owner's personal authoring and publishing site under the owner's control. It is not an aggregator of social-network content.

## Roles

- **Anonymous reader:** reads published content and public discussion.
- **Registered member:** maintains a verified identity, reacts, comments, blocks users, and manages subscriptions.
- **Author/admin:** writes, previews, publishes, moderates, and operates the site through first-party administration.
- **Moderator capability:** initially belongs to the admin role and may become a separate role later.

## Production v1: non-finance scope

### Reading and presentation

- The Feed at `/` server-renders page 1, orders published posts newest first, and continues with infinite loading plus a manual fallback. It provides live search; loading, empty, error, and terminal states; and state and scroll restoration. Draft, future, unpublished, and no-longer-published content stays hidden.
- A full post has a stable slug, structured content, publication and update dates, responsive images, reactions, and comments.
- Public experiences support light, dark, and system themes; desktop and mobile layouts; keyboard and touch input; visible focus; and accessible semantics.
- Pages provide SEO metadata, Open Graph metadata, and canonical URLs.

### Authoring and publication

- Administration is first-party. Long-form writing is desktop-first and uses Tiptap.
- The lifecycle supports autosave, drafts, preview, revisions, revision restore, publication dates, immediate publication, scheduled publication, and manual or scheduled unpublish.
- The v1 content baseline includes rich text, headings, quotes, bullet and numbered lists, checklists, inline code, code blocks with language and highlighting, tables, dividers, links, images, and galleries. Embeds are post-v1.

### Identity and access

- Email-and-password authentication requires email verification.
- Google and GitHub OAuth request only minimal scopes.
- A required public nickname is separate from the login credential, Unicode-safe, and unique under case-insensitive comparison.

### Discussion, reactions, and emoji

- Comments have one thread level: a root comment with flat replies. Members can edit and soft-delete their content. Administration supports moderation, and members can block users.
- Posts, comments, and replies support custom reactions. A user may have at most one reaction of a given type for each `(user, target)` pair; selecting it toggles the reaction. The UI exposes aggregates and explicit participant lists.
- The site owns a searchable custom emoji catalog. The existing 228-item legacy corpus is unverified and must not be imported. Production population fails closed until a separate provenance and license decision approves a corpus.

### Subscriptions and delivery

- A separate `/subscriptions/` experience supports double opt-in, publication email, and unsubscribe.
- Email delivery uses a durable outbox and delivery deduplication.

### Data and release requirements

- PostgreSQL is the planned system of record; media uses object storage and a CDN.
- Releases go to an isolated staging environment first and promote immutable artifacts.
- Production requires backups and a verified restore procedure.

## Bridge contract

The Bridge contains exactly these profiles, in this order:

1. GitHub — https://github.com/kirillwynn
2. LeetCode — https://leetcode.com/u/kirillwynn/
3. Reddit — https://reddit.com/user/kirillwynn
4. Telegram — https://t.me/kirillwynn
5. Instagram — https://instagram.com/kirillwynn
6. X — https://x.com/kirillwynn
7. Steam — https://steamcommunity.com/id/kirillwynn
8. Pulse — https://www.tbank.ru/invest/social/profile/kirillwynn/

The Bridge is an icon-only grid. Social names remain accessible names, and no visible `Bridge` heading or descriptive paragraph appears above the grid. Keyboard, touch, and focus behavior never depends on hover. Links, icons, and labels come from one configuration-backed source rather than duplicated UI values.

The shared public footer contains only two centered rows:

`Current Team: Yandex`

`Previous Team: Deeplay`

It contains no copyright or tagline.

## Non-goals

- Migrating old users or data, or reusing old Wagtail, Next.js, or Lexical code or data formats without a new ADR.
- Aggregating content from social media.
- Finance or T-Invest functionality before the complete non-finance production release is accepted.
- Native applications or mobile long-form authoring.
- A notification center or user-uploaded emoji.
- Elasticsearch or OpenSearch unless a future ADR changes scope.
- Multi-author workflows, embeds, or complex animation in v1.
