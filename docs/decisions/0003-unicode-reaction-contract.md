# ADR 0003: Concrete Unicode reaction contract

Status: accepted

Date: 2026-07-26

## Context

Posts, top-level comments, and thread replies need Slack-style Unicode emoji
reactions. The feature must preserve relational integrity, accept modern
multi-code-point emoji, serialize concurrent toggles, expose viewer state
without N+1 queries, and remain inside the existing Django session/CSRF and
public-content boundaries.

Emoji are not individual Unicode code points. Valid sequences include ZWJ
compositions, modifiers, flags, keycaps, gender variants, and variation
selectors. A browser-only check, `len(value) == 1`, a generic relation, or an
in-process rate limiter cannot enforce the required contract.

## Decision

### Persistence

Use two concrete Django models:

- `PostReaction(post, user, emoji, created_at)`;
- `CommentReaction(comment, user, emoji, created_at)`.

All target and user foreign keys use `PROTECT`, preserving reaction history and
preventing identity or target deletion from silently destroying it. Each model
has a database unique constraint on `(target, user, emoji)` and an aggregation /
participant index on `(target, emoji, created_at, id)`.

Deleted or hidden comments retain existing reaction rows for moderation
history, but public serialization returns no reaction groups, participant reads
return 404, and new toggles return 403.

### Unicode boundary

Django is authoritative. It:

1. requires a string;
2. rejects empty input, whitespace, controls, surrogate code points, and
   dangerous bidirectional formatting controls;
3. enforces 32 Unicode code points and 128 UTF-8 bytes;
4. normalizes to NFC;
5. uses `emoji` 2.15.0 `is_emoji` / `EMOJI_DATA` to require exactly one
   recommended-for-general-interchange Unicode emoji sequence;
6. rejects standalone Unicode emoji components such as skin-tone modifiers.

Meaningful ZWJ, modifier, keycap, flag, gender, and variation code points are
preserved. The normalized value is stored and returned as the canonical key.
The frontend picker uses the local `@emoji-mart/data` 1.2.1 Unicode 15 dataset,
but the backend repeats validation and can accept supported sequences sent by
newer clients.

### API and privacy

Versioned concrete endpoints exist separately for post and comment aggregates,
toggles, and reaction participants. Participant pages use stable
`(created_at, id)` cursor pagination and relative links. Public participant
objects contain only `id`, `display_name`, and `is_site_author`.

All reaction responses are `private, no-store` and `Vary: Cookie`. Reads are
anonymous. Mutations require the existing Django authenticated session, normal
CSRF, and an active non-banned user. Post and comment lookups reuse the one
canonical public visibility policy; Draft Mode never renders the client
reaction components.

Comment pages compute all reaction counts in one grouped query and viewer state
in at most one additional query for the whole 20-item page. Deterministic Python
string ordering is applied to groups after aggregation.

### Toggle concurrency and abuse protection

Each toggle runs inside `transaction.atomic`. The concrete post or comment row
is selected with `select_for_update`, serializing all conflicting toggles for
one target. The unique constraint remains the final duplicate boundary, and an
`IntegrityError` caused by a writer that ignored the target lock is handled
inside a savepoint.

A separate `ReactionRateLimitBucket` stores one fixed-window row per user. The
row is locked transactionally. Defaults are 60 toggles per 60 seconds and are
validated positive integer settings. Limit responses use 429 and
`Retry-After`.

### Wagtail and frontend

`ReactionSettings` is a Wagtail Site Setting with exactly three emoji fields.
The same backend validator normalizes them and enforces post-normalization
uniqueness. The public config endpoint emits only the three values.

The client uses accessible pills with `aria-pressed`, separate participant
triggers, touch-sized controls, quick reactions, a lazy local picker with search
and keyboard navigation, and a bounded emoji-only recent list in
`localStorage`. A synchronous in-flight guard prevents double-click and
out-of-order toggles; optimistic state rolls back on failure and is replaced by
the complete server aggregate on success.

Anonymous intent is stored for ten minutes in `sessionStorage`, scoped by
Unicode slug, target type, target ID, and emoji. OAuth return restores a
confirmation prompt. It never automatically replays a toggle; if authoritative
state already shows the reaction, confirmation clears the intent without
removing it.

## Consequences

Positive:

- normal foreign keys and unique constraints preserve integrity;
- multi-code-point emoji validation follows the Unicode dataset rather than
  heuristics;
- toggles have clear PostgreSQL serialization semantics;
- participant privacy and cursor boundaries are explicit;
- comment aggregation remains bounded as page size grows;
- picker data never leaves the site or inflates the initial post bundle.

Negative:

- post and comment reaction code has deliberate concrete duplication;
- the backend and picker datasets may temporarily support different Unicode
  versions, so the backend remains the final authority;
- target-row locking serializes different emoji toggles on the same object,
  trading peak per-target throughput for simple correct semantics;
- reaction and rate-bucket rows require a future operational retention policy
  if volume grows materially.

## Alternatives considered

### GenericForeignKey

Rejected because it removes concrete target foreign keys, complicates query
planning, and weakens deletion integrity.

### Regex-only or grapheme-only validation

Rejected because grapheme clusters are broader than standardized emoji and
home-grown regexes routinely mishandle ZWJ, modifiers, tags, and qualification
status.

### Optimistic automatic OAuth replay

Rejected because toggles are not idempotent: a repeated page load could remove
an already-added reaction.

### Redis or in-process throttling

Rejected for the first version. Redis is outside the accepted architecture, and
in-process counters are neither durable nor consistent across workers.

## Revisit conditions

Revisit this decision if reaction traffic makes target-level serialization a
measurable bottleneck, Unicode policy must distinguish qualification statuses,
or custom emoji are accepted through a separate ADR.
