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

OAuth email authentication is allowed only when allauth/provider processing marks the provider email verified. A matching verified local account keeps its password and receives the provider on the same `User`. A provider-verified identity may also reclaim an unverified local preregistration of that exact canonical address, but the unverified password, old sessions, and outstanding credentials are invalidated before the address is verified and the provider is connected. The unusable-password salt is rotated too, so even an anomalous pre-existing session cannot survive. The verified-email path locks the target user and performs the state transition, canonical `EmailAddress` update, and `SocialAccount` connection in one database transaction; a uniqueness race fails closed. Only the selected authoritative verified provider address reaches allauth persistence, so secondary profile addresses cannot create a second identity boundary. This prevents an attacker from preregistering a victim's address and retaining access. Explicit provider connection still requires an authenticated session with a matching verified primary email and an unowned provider identity. Unverified provider email never links. These rules prevent account takeover and keep repeated callbacks idempotent.

### Nickname contract

`User.nickname` is the NFC display value. `User.nickname_normalized` is the NFKC plus full-casefold database uniqueness key. Normalization first rejects Unicode controls, Unicode 15.0 default-ignorable ranges (including variation selectors and Hangul fillers), other format/invisible characters, bidi overrides and isolates, surrogates, private-use code points, noncharacters, and line/paragraph separators. It trims outer Unicode space separators and collapses internal runs to one ASCII space.

The display value contains 2–40 Unicode code points and at most 160 UTF-8 bytes. Letters, combining marks after a base, numbers, internal spaces, and `- _ . · ' ’` are allowed. It must begin and end with a letter or number; repeated separators and HTML/URL-like punctuation are rejected. The backend contract is authoritative and the frontend performs equivalent defensive validation only for faster feedback.

Service-name impersonation is rejected for `admin`, `administrator`, `moderator`, `staff`, `system`, `support`, and the current site-owner nickname. A deliberately narrow skeleton maps common Greek/Cyrillic lookalikes and removes diacritics/separators only when comparing these privileged names. It is identified as `stage17-v1/unicodedata-15.0.0`; the authoritative backend and activation migration refuse to run with a different Python Unicode database. It is not a general cross-script restriction and ordinary multilingual names remain allowed.

Internal `username` stays for `AbstractUser`, Admin, and rollback compatibility. It is never a public login or display field. New public accounts receive opaque `usr_<random>` usernames, and nickname changes never mutate them.

### Confirmation, changes, and history

Local signup is an explicit initial nickname selection and has no cooldown. A new OAuth user receives only a provider-name suggestion, with `nickname_confirmed=false`, and must complete `/account/profile`. Existing staff/site-owner users and users with existing comments or reactions are confirmed by migration. Other existing users keep the deterministic backfill suggestion but must confirm it after login. Inactive and banned rows retain a historical display value without gaining interaction rights.

Local login reports profile completion as a trusted response flag rather than returning an auth route through the public `next` contract. The frontend opens the fixed completion route from that flag and carries only the independently allowlisted product destination; account/auth/service routes therefore never become attacker-selected return targets.

If a verified provider claims a preregistered but still unverified local email identity, the transition atomically destroys the untrusted local password and sessions, revokes outstanding credentials, and marks the preregistration nickname unconfirmed. The verified owner must explicitly accept or replace that nickname through profile completion. Linking to an already verified local identity preserves its password and confirmed nickname.

For an already connected `SocialAccount`, the provider UID and a currently provider-verified match for the Django user's canonical email are both required. A different verified provider address is treated as an unsupported email change and fails closed; it never rewrites the local identity implicitly.

After initial confirmation, user-initiated changes are allowed once every 30 days. Each claim is written transactionally to `NicknameHistory`; its unique normalized key is retained permanently. This deliberately stronger anti-impersonation policy means an old public name is never recycled. Concurrent signup and rename rely on both the current-user unique constraint and the permanent-claim unique constraint. Staff overrides are available only through Django Admin, require an active staff actor plus a non-empty reason, and may bypass cooldown/reserved-name policy but never the inactive/banned boundary. The API returns the next allowed change timestamp.

Historical comments, replies, reactions, and Wagtail-owned posts continue to reference stable user IDs and resolve the current nickname at read time. There is no display-name snapshot in those content rows.

### Interaction and public author contract

The one interaction predicate is authenticated, active, not banned, nickname confirmed, and primary email verified. Reading, logout, and safe account management remain available while profile or email verification is incomplete.

One backend helper returns the authoritative public display name. Activated `/api/me/`, comments, replies, reply targets, reaction participants, moderation views, and post authors use `nickname` without a runtime `full_name`/`username` fallback. Post list, detail, and preview responses add only `{id, display_name, is_site_author}` from Wagtail `Page.owner`; they do not expose email, username, provider, permissions, or moderation state.

The custom user also returns the nickname to Django/Wagtail display-name helpers, so locks, workflow labels, choosers, and moderation surfaces cannot revive legacy names. Wagtail's user index exposes nickname rather than internal username/full name. Its create form establishes canonical email, confirmed nickname, and permanent history atomically; its edit form keeps email and nickname immutable and directs audited nickname overrides to Django Admin.

Wagtail password login and its authenticated password-change view remain available to staff. Its built-in public password-reset flow is disabled because it uses a query-string credential and synchronous email delivery outside the durable auth-email boundary. Wagtail self-service email editing is also disabled because email change is outside this stage. The bootstrap owner command requires the matching verified primary address plus Google/GitHub identity, refuses to replace a different site-author marker, and grants that marker together with staff/superuser state.

A nickname change creates existing durable post revalidation events for every
live/cacheable post owned by that user. Draft-only pages have no public cache
entry to invalidate. Delivery starts after commit and never performs network
I/O inside the nickname transaction. Feed and live post cache tags are
invalidated while preview credentials remain isolated.

### Auth credentials and email delivery

Verification and password-reset credentials are purpose-, user-, canonical-email-, account-state-version-, and expiry-bound. Each purpose uses a domain-separated HMAC key. A random UUID plus that key deterministically reconstructs the credential for worker delivery; only its SHA-256 digest and lifecycle row are stored. Credentials are revocable and one-time, and validation distinguishes generic invalid, expired, used, and unavailable states without exposing account existence. Password and relevant account-state changes invalidate outstanding credentials.

Consumption locks `User` before credential and canonical-matching
`EmailAddress` rows. Password reset additionally requires that the bound
address is still the unique verified primary identity at consumption time;
case/NFKC-equivalent allauth values use the same canonicalizer as signup,
login, and OAuth linking.

Email links use fragments:

- `/account/verify-email#credential=...`
- `/account/password/reset/confirm#credential=...`

The Next.js entry reads the fragment once, immediately calls `history.replaceState`, and submits it only in a bounded, same-origin, CSRF-protected POST body. Credentials therefore do not enter Nginx/Django access logs, Referer headers, browser history after consumption, persistent React state, `localStorage`, or `sessionStorage`.

Account mail has dedicated `AuthEmailOutbox` and `AuthEmailDelivery` tables, message types, templates, lifecycle constraints, and environment-plus-delivery idempotency keys. It shares only the existing deterministic provider serializer/adapter. Allauth's built-in email verification and account notifications are explicitly disabled, so the web transaction only creates a bounded event and never performs synchronous delivery or receives the Resend send key. The worker reconstructs exact request bytes, performs provider I/O, retries only inside the provider idempotency safety window, and moves ambiguous/terminal cases to bounded failure or manual review. A stale worker cannot downgrade a terminal or sent delivery. No `Subscriber`, newsletter outbox, or publication decision is created or changed.

The exact Nginx routes and Django parser independently enforce the same 16 KiB
JSON body ceiling; the edge emits a stable private/no-store JSON 413 before
proxying an oversized body. HMAC-keyed rate-limit buckets are shared through
the database and opportunistically prune a bounded batch older than two full
windows so fixed-window history does not grow forever. Anonymous sensitive
form fields remain disabled until `/api/me/` supplies the masked CSRF token,
preventing pre-hydration input loss without persisting form values.

### Migration and rollback

Rollout is expand, verify, then activate:

1. Add nullable user fields and independent audit/credential/outbox/rate-limit tables.
2. Backfill deterministic nicknames and email keys, create nickname claims, and report collisions/quarantines/owner exceptions. The previous Django and Next digests remain valid and local signup stays disabled.
3. Verify staging data and the previous application against the expanded schema. A dedicated compatibility migration persists database defaults for the two new non-null user columns (`auth_state_version=1` and `nickname_confirmed=false`). This matters because Django's ordinary Python `default=` is temporary during `AddField`; the persistent defaults let a Stage 16 ORM `INSERT`, which omits both columns, continue to succeed during overlap or rollback.
4. Apply an activation catch-up backfill for users created during the expansion window. The new `is_site_author` column likewise has a persistent `false` database default before the candidate application starts.
5. Quiesce only the active Django write container for the bounded final catch-up, invariant audit, and candidate-start window. Restore the exact stopped container ID if catch-up/audit fails, eliminating a final legacy OAuth `INSERT` race without changing edge, Next, or PostgreSQL.
6. Enable authoritative nickname display, local account APIs, profile completion, exact edge routes, and Next account pages only in the activation release.
7. Keep fields nullable and retain legacy identity columns during the rollback window. Check constraints accept the old digest's `NULL/false` insert shape while rejecting incoherent nickname state, empty canonical keys, and multiple site authors. Contract cleanup is a later migration.

Backfill candidates are the first valid value in this order: full name, non-synthetic username, primary email local part, `user-<id>`. A collision adds a bounded stable-ID suffix. The site owner is allocated first to protect that public identity; all other allocation and duplicate-email quarantine is stable-ID deterministic. Reversing the data migration clears only an unchanged activation catch-up identity and its migration claim. If that user has renamed after activation, rollback retains the current identity and both permanent claims. It never deletes users, sessions, email/social rows, comments, reactions, ownership, or content. A proven repair of a missing page owner is intentionally not undone.

Every staging rollout uses its normal verified PostgreSQL backup before migrations. Expansion and activation have separate commits, image manifests, attestations, operations, and acceptance evidence. Production, `main`, reaction catalog synchronization/assets, Stage 15 editorial state, and real publications are outside this rollout.

## Consequences

The schema remains temporarily nullable and must be audited before activation. Legacy canonical-email collisions cannot authenticate locally or link providers until an operator resolves them without merging IDs. Permanent nickname claims consume a small append-only audit table but remove name-recycling ambiguity. The worker gains a second outbox workload while the Resend secret boundary and deterministic transport contract remain unchanged.
