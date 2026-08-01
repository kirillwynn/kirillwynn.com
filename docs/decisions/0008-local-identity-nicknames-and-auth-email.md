# ADR 0008: Local identity, public nicknames, profile completion, and auth email

- Status: Accepted for phased Stage 17 rollout
- Date: 2026-07-31

## Context

The site already uses Django users, database sessions, Django CSRF, and django-allauth 65.18.0 for Google and GitHub. Public author names were derived independently from `get_full_name()` or the internal `username`. Local password login, account email delivery, and a durable public-name identity did not exist.

Stage 17 adds local accounts without moving identity or session authority into Next.js. Existing user IDs, password hashes, sessions, social identities, content foreign keys, page ownership, and moderation/staff state must survive the rollout. The active Stage 16 application must also remain compatible while the schema expands.

## Decision

### Identity boundary

Django remains the user authority and django-allauth remains the account/social flow authority. The browser receives only an HttpOnly Django database-session cookie and an HttpOnly CSRF cookie. There are no JWTs, Auth.js sessions, browser-stored access tokens, or persisted `SocialToken` rows. `ModelBackend` remains enabled for username/password access to Django Admin and Wagtail, while public login accepts only canonical email plus password.

Every user has a nullable rollout key, `email_normalized`. Activated public account creation always supplies it. Its contract is trim, validate, IDNA-normalize and lowercase the domain, then NFKC plus full casefold the local part. A database unique constraint is the final concurrency boundary. Legacy case-colliding rows are preserved, not merged or renumbered: the lowest stable user ID receives the key and the other rows remain quarantined with a null key for manual review. No verification flag is changed by backfill.

OAuth email authentication is allowed only when allauth/provider processing marks the provider email verified and the matching local user owns the same canonical primary, verified `EmailAddress`. An unverified local address is not linkable. Explicit provider connection still requires an authenticated session, an unowned provider identity, and a provider-verified email. These rules preserve local passwords, prevent an unverified-account takeover, and keep repeated callbacks idempotent.

### Nickname contract

`User.nickname` is the NFC display value. `User.nickname_normalized` is the NFKC plus full-casefold database uniqueness key. Normalization first rejects Unicode controls, format/invisible characters, bidi overrides and isolates, surrogates, private-use code points, noncharacters, and line/paragraph separators. It trims outer Unicode space separators and collapses internal runs to one ASCII space.

The display value contains 2–40 Unicode code points and at most 160 UTF-8 bytes. Letters, combining marks after a base, numbers, internal spaces, and `- _ . · ' ’` are allowed. It must begin and end with a letter or number; repeated separators and HTML/URL-like punctuation are rejected. The backend contract is authoritative and the frontend performs equivalent defensive validation only for faster feedback.

Service-name impersonation is rejected for `admin`, `administrator`, `moderator`, `staff`, `system`, `support`, and the current site-owner nickname. A deliberately narrow skeleton maps common Greek/Cyrillic lookalikes and removes diacritics/separators only when comparing these privileged names. It is identified as `stage17-v1/unicodedata-15.0.0`; it is not a general cross-script restriction and ordinary multilingual names remain allowed.

Internal `username` stays for `AbstractUser`, Admin, and rollback compatibility. It is never a public login or display field. New public accounts receive opaque `usr_<random>` usernames, and nickname changes never mutate them.

### Confirmation, changes, and history

Local signup is an explicit initial nickname selection and has no cooldown. A new OAuth user receives only a provider-name suggestion, with `nickname_confirmed=false`, and must complete `/account/profile`. Existing staff/site-owner users and users with existing comments or reactions are confirmed by migration. Other existing users keep the deterministic backfill suggestion but must confirm it after login. Inactive and banned rows retain a historical display value without gaining interaction rights.

After initial confirmation, user-initiated changes are allowed once every 30 days. Each claim is written transactionally to `NicknameHistory`; its unique normalized key is retained permanently. This deliberately stronger anti-impersonation policy means an old public name is never recycled. Concurrent signup and rename rely on both the current-user unique constraint and the permanent-claim unique constraint. Staff overrides are available only through Django Admin and require an actor plus a non-empty reason. The API returns the next allowed change timestamp.

Historical comments, replies, reactions, and Wagtail-owned posts continue to reference stable user IDs and resolve the current nickname at read time. There is no display-name snapshot in those content rows.

### Interaction and public author contract

The one interaction predicate is authenticated, active, not banned, nickname confirmed, and primary email verified. Reading, logout, and safe account management remain available while profile or email verification is incomplete.

One backend helper returns the authoritative public display name. Activated `/api/me/`, comments, replies, reply targets, reaction participants, moderation views, and post authors use `nickname` without a runtime `full_name`/`username` fallback. Post list, detail, and preview responses add only `{id, display_name, is_site_author}` from Wagtail `Page.owner`; they do not expose email, username, provider, permissions, or moderation state.

A nickname change creates existing durable post revalidation events for all posts owned by that user. Delivery starts after commit and never performs network I/O inside the nickname transaction. Feed and post cache tags are invalidated while preview credentials remain isolated.

### Auth credentials and email delivery

Verification and password-reset credentials are purpose-, user-, canonical-email-, account-state-version-, and expiry-bound. A random UUID plus a server-secret HMAC deterministically reconstructs the credential for worker delivery; only its SHA-256 digest and lifecycle row are stored. Credentials are revocable and one-time, and validation distinguishes generic invalid, expired, used, and unavailable states without exposing account existence. Password and relevant account-state changes invalidate outstanding credentials.

Email links use fragments:

- `/account/verify-email#credential=...`
- `/account/password/reset/confirm#credential=...`

The Next.js entry reads the fragment once, immediately calls `history.replaceState`, and submits it only in a bounded, same-origin, CSRF-protected POST body. Credentials therefore do not enter Nginx/Django access logs, Referer headers, browser history after consumption, persistent React state, `localStorage`, or `sessionStorage`.

Account mail has dedicated `AuthEmailOutbox` and `AuthEmailDelivery` tables, message types, templates, lifecycle constraints, and idempotency keys. It shares only the existing deterministic provider serializer/adapter. The web transaction creates a bounded event and never has the Resend send key; the worker reconstructs exact request bytes, performs provider I/O, retries within the provider idempotency window, and moves ambiguous/terminal cases to bounded failure or manual review. No `Subscriber`, newsletter outbox, or publication decision is created or changed.

### Migration and rollback

Rollout is expand, verify, then activate:

1. Add nullable user fields and independent audit/credential/outbox/rate-limit tables.
2. Backfill deterministic nicknames and email keys, create nickname claims, and report collisions/quarantines/owner exceptions. The previous Django and Next digests remain valid and local signup stays disabled.
3. Verify staging data and the previous application against the expanded schema.
4. Apply an activation catch-up backfill for users created during the expansion window, then enable authoritative nickname display, local account APIs, profile completion, exact edge routes, and Next account pages.
5. Keep fields nullable and retain legacy identity columns during the rollback window. Contract cleanup is a later migration.

Backfill candidates are the first valid value in this order: full name, non-synthetic username, primary email local part, `user-<id>`. A collision adds a bounded stable-ID suffix. The site owner is allocated first to protect that public identity; all other allocation and duplicate-email quarantine is stable-ID deterministic. Reversing the data migration clears only Stage 17-derived identity fields/history and never deletes users, sessions, email/social rows, comments, reactions, ownership, or content. A proven repair of a missing page owner is intentionally not undone.

Every staging rollout uses its normal verified PostgreSQL backup before migrations. Expansion and activation have separate commits, image manifests, attestations, operations, and acceptance evidence. Production, `main`, reaction catalog synchronization/assets, Stage 15 editorial state, and real publications are outside this rollout.

## Consequences

The schema remains temporarily nullable and must be audited before activation. Legacy canonical-email collisions cannot authenticate locally or link providers until an operator resolves them without merging IDs. Permanent nickname claims consume a small append-only audit table but remove name-recycling ambiguity. The worker gains a second outbox workload while the Resend secret boundary and deterministic transport contract remain unchanged.
