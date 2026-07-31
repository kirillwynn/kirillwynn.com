# ADR 0006: Manifest-managed custom reaction catalog

Status: accepted

Date: 2026-07-29

Amended: 2026-07-31 (retired suggested reactions from the public UI while
retaining rollback compatibility)

Supersedes: ADR 0003's public Unicode identity, picker, and storage contract.
ADR 0003 remains the historical contract for preserved legacy rows and the
concurrency, privacy, visibility, pagination, and OAuth safeguards retained
here.

## Context

Stage 16 replaces public Unicode reactions with a site-owned catalog of static
and animated images. A reaction must remain the same identity when its display
name, source filename, CDN URL, ordering, or Wagtail database state changes.
The supplied 228-file corpus has no accompanying attribution or license
material. It is therefore approved only for a controlled staging evaluation;
Internet availability and noncommercial use are not treated as production
rights.

The existing application already has populated `emoji` rows and deployed
migrations `discussions.0001` and `0002`. A single breaking schema/API rollout
would leave either the previous or new application digest unable to operate
safely during migration and rollback.

## Decision

### Stable identity and persistence

`ReactionCatalogItem.catalog_id` is the lowercase ASCII public identity and
primary key. Identity never derives from a URL, filename, label, database
integer, or ordering. Each catalog row records:

- display and accessibility labels, static/animated kind, deterministic
  ordering, enabled/selectable state, and optional quick order;
- source, normalized asset, and poster SHA-256 values;
- `sha256-<normalized-asset-digest>` immutable asset version;
- intrinsic dimensions, output frame count, duration, and minimum frame delay;
- content-addressed asset and poster keys;
- provenance, author, license, rights basis, approval status, exact manifest
  digest, and import time.

`PostReaction` and `CommentReaction` retain the deployed Unicode `emoji`
column and add nullable `catalog_item` foreign keys with `PROTECT`. A database
check requires exactly one identity representation. New custom rows use an
empty legacy value plus a catalog relation. Conditional unique constraints use
`(target, user, catalog_item)` and aggregate indexes use
`(target, catalog_item, created_at, id)`. The legacy aggregation indexes
remain. During activation, the existing named Unicode uniqueness constraints
become partial on non-empty `emoji` values so multiple side-by-side custom
identities can coexist without weakening legacy duplicate protection.

The immutable migration contains an explicit Unicode-to-catalog mapping table.
It is empty because no semantic equivalence has been approved. Thus all legacy
rows remain reversible and are hidden, not silently relabelled. A later cleanup
may archive/remove the legacy public path only after rollback support and
retention policy are separately approved.

### Two-phase rollout

The rollout has two application releases:

1. expansion adds the side-by-side schema, Wagtail controls, prepare/sync
   pipeline, and filters the legacy API to legacy rows;
2. after expansion is live, the catalog objects and rows are verified and
   activated, then migration `0004` makes the retained legacy uniqueness
   conditional on a non-empty legacy value and a second release switches API
   and frontend to catalog IDs.

The expansion digest is the rollback target for activation. It is compatible
with catalog rows and ignores them. No custom row is inserted before expansion
is confirmed. Migrations `0001` and `0002` and existing Git history are never
rewritten.

Migration `0004` has a state-reversing, physical no-op reverse operation. This
is deliberate: recreating the former unconditional `(target, user, emoji)`
constraint would reject valid custom rows that all retain an empty legacy
column. A subsequent forward application explicitly replaces either the old
constraint or the partial index, so `0004 → 0003 → 0004` is safe and preserves
populated legacy and custom rows. Removing the legacy column, legacy index, or
rollback compatibility remains a separate contract/cleanup migration.

### Manifest and preparation

The manifest is the sole allowlist. It names every source path explicitly and
contains the required identity, source digest, labels, kind, order, state,
quick status, provenance/rights, approval, and immutable source version.
Directory discovery cannot publish an item.

`prepare_reaction_catalog` accepts an explicit manifest, source root, and
output directory. It rejects absolute/traversing item paths and every symlink;
checks source SHA-256; identifies PNG, WebP, and GIF by bytes rather than
extension; validates exact container EOF; and fully verifies/decodes every
frame. Limits are:

| Boundary | Limit |
| --- | ---: |
| source and each normalized object | 512 KiB |
| width or height | 512 px |
| source animation frames | 160 |
| normalized duration | 10 seconds |
| cumulative decoded RGBA cost | 64 MiB |
| minimum normalized frame delay | 20 ms |

Static PNG/WebP becomes lossless sRGB WebP. Animated input must be GIF and
becomes a looping, optimized sRGB GIF plus a lossless WebP first-frame poster.
Zero/short delays become 20 ms. ICC, XMP, EXIF, comments, Software, and other
non-rendering metadata are not emitted. Transparency and aspect ratio remain.
The pinned Pillow implementation, explicit parameters, exact output checks,
content hashes, immutable writes, and canonical JSON attestation make repeated
preparation byte-preserving.

A production approval manifest may reuse a reviewed staging attestation and
prepared objects through `--reuse-attestation`; that path verifies the source
and object bytes and does not re-encode them.

### Storage and activation

`sync_reaction_catalog` verifies the exact manifest/attestation and uses the
configured environment-isolated S3 storage. Logical keys are:

```text
reactions/<catalog-id>/<normalized-sha256>/asset.webp
reactions/<catalog-id>/<normalized-sha256>/animation.gif
reactions/<catalog-id>/<normalized-sha256>/poster.webp
```

The configured `staging/media` or `production/media` location is prepended by
storage. Sync fails when the requested environment and prefix disagree.
Objects use exact `Content-Type`,
`Cache-Control: public, max-age=31536000, immutable`, and SHA/catalog/version
metadata. A conditional create prevents overwrite. Existing objects are
byte/header verified and never deleted. All objects are uploaded and read back
before one database transaction activates rows and exactly three quick
reactions.

Production sync fails closed unless the manifest and every item are
`production-approved`. The current 228-item manifest is
`staging-only/unverified`; it cannot be promoted by this command.

### Wagtail boundary

Wagtail exposes catalog listing/search, safe label edits, enabled/selectable
state, and ordering. Add, copy, delete, binary replacement, storage keys,
hashes, versions, and provenance fields are unavailable to normal or superuser
browser actions. Those values come only from the verified importer.

The site setting selects exactly three distinct enabled/selectable catalog
items. Saving it synchronizes quick order transactionally. Disabling a selected
quick item is rejected until another quick set is chosen.

### Public API

Mutations accept exactly:

```json
{"reaction_id": "pepeclap"}
```

Unicode, shortcodes, filenames, URLs, keys, and client objects are rejected.
Groups return a catalog descriptor, count, viewer state, and an exact relative
participant endpoint keyed by catalog ID:

```json
{
  "reaction": {
    "id": "pepeclap",
    "name": "Pepe clap",
    "label": "Clapping",
    "kind": "animated",
    "asset_url": "https://cdn.example/reactions/…/animation.gif",
    "poster_url": "https://cdn.example/reactions/…/poster.webp",
    "width": 128,
    "height": 128,
    "version": "sha256-…"
  },
  "count": 3,
  "viewer_reacted": true,
  "participants": "/api/v1/posts/post/reactions/pepeclap/participants/"
}
```

Catalog and quick config are user-independent and use
`Cache-Control: public, max-age=60, stale-while-revalidate=300` plus a
payload-derived ETag, with no `Cookie` variance. Viewer-dependent aggregates,
toggles, and participants remain `private, no-store` and `Vary: Cookie`. ADR
0003's
anonymous reads, Django session/CSRF mutation boundary, active/non-banned
policy, canonical visibility, hidden/deleted behavior, rate limit,
target-row locking, bounded Feed batch, and participant pagination continue.

### Frontend and browser storage

The public reaction bar exposes no suggested/quick reactions. Post detail,
top-level comments, replies, and thread copies show only existing aggregate
pills plus one compact picker trigger; an empty group shows only the trigger.
Feed remains aggregate-only and does not gain a picker. The new frontend does
not fetch quick config on mount, does not render quick assets, and restores an
unknown valid pending catalog ID through the catalog endpoint.

`GET /api/v1/reactions/config/`, `ReactionSettings`, its three catalog foreign
keys, catalog `quick_order`, and the existing three selected values remain
temporarily byte/schema compatible for rollback to the preceding staging
frontend digest. The Wagtail settings form is removed from owner navigation so
it cannot present an active feature. Physical removal is deferred to a
separate cleanup migration after the rollback window; this amendment performs
no data migration or catalog sync.

The picker is a lazy application chunk and fetches only the enabled catalog.
Search uses names/labels; keyboard, touch, Escape, and focus restoration are
supported. Catalog pages use lazy images, and full-size binaries are not part
of the initial route or browser bundle.

Static assets render directly. Animated reactions render their poster until
visible/active. Picker animation is limited to the focused, hovered, or
selected item. When `prefers-reduced-motion` is active, code never assigns or
preloads the animated URL; offscreen reactions return to posters. Broken
images retain accessible text. Images inside labelled buttons are decorative
(`alt=""`), while the button's `aria-label` carries the reaction label.

Recent reactions and OAuth pending intent use versioned catalog-ID-only
storage. Legacy Unicode entries are removed/ignored without mapping. TTL,
target isolation, explicit confirm/discard, no automatic replay, optimistic
rollback, shared target coordinator, stale settlement defense, duplicate
instances, participant abort/dedupe/focus, Feed explicit activation,
tombstones, and Draft Mode suppression remain.

### Staging activation outcome

The two-phase decision was exercised on staging. Expansion release
`2d3c04faa08835e2b1d8cadb4eb1649870633f17` applied `0003`; attested sync
operation
`catalog-sync-30588326706-staging-2d3c04faa08835e2b1d8cadb4eb1649870633f17`
activated the explicit 228-item allowlist and verified 276 immutable objects;
activation release `9c2f6d4e6e1ae39cd1dbf72e7affc55b9c50dd03` applied `0004`.
The final live-QA fix release is
`43f5a05213f13d7c5129ddebd05955fc3186de82`.

Two historical post Unicode rows and the legacy columns remain intact and are
not exposed through the catalog contract. The allowlist remains
`staging-only/unverified`, so this successful staging activation does not
authorize or imply a production catalog.

## Consequences

The public identity and asset lifecycle are stable and auditable, animations
have a real reduced-motion network boundary, and a previous application digest
can safely operate during rollout. The tradeoff is a deliberately strict
prepare/promote process, two application releases, retained legacy columns,
and a production rights gate that cannot be bypassed through Wagtail or a
directory upload.
