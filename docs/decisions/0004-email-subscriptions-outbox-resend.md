# ADR 0004: Double-opt-in subscriptions, durable email outbox, and Resend

Status: accepted

Date: 2026-07-27

## Context

Anonymous readers need publication email subscriptions without an application
account. A successful Wagtail publication must not depend on provider
availability, one publication must not produce duplicate mail to a reader, and
bounces or complaints must stop later sends. The first provider is Resend, but
provider state must not become the domain model.

Resend accepts an `Idempotency-Key` on `POST /emails` and retains it for 24
hours. A retry is safe only with the same request payload. Reusing the key with
a different payload returns terminal `409 invalid_idempotent_request`; a
simultaneous matching request returns retryable
`409 concurrent_idempotent_requests`. These contracts are documented in
[Resend idempotency keys](https://resend.com/docs/dashboard/emails/idempotency-keys)
and the [Resend error reference](https://resend.com/docs/api-reference/errors).

Resend webhooks use the Svix `svix-id`, `svix-timestamp`, and
`svix-signature` contract over the exact raw body, provide at-least-once
delivery, may arrive out of order, and retry after an unsuccessful HTTP
response. See [Managing Webhooks](https://resend.com/docs/webhooks/introduction)
and [Retries and Replays](https://resend.com/docs/webhooks/retries-and-replays).

## Decision

### Subscriber identity and lifecycle

The `subscriptions` Django application owns `Subscriber`, `EmailOutbox`,
`EmailDelivery`, `EmailWebhookEvent`, and anonymous rate-limit buckets.

Email input is trimmed and validated with a maximum of 320 Unicode code points.
The source form is retained for delivery. The canonical key case-folds the
complete local part and converts the domain through IDNA to lowercase ASCII.
All model, API, and worker paths use this one function. A functional
`LOWER(canonical_email)` database constraint is the final case-insensitive
uniqueness boundary.

Subscriber states are `pending`, `active`, `unsubscribed`, and `suppressed`.
Database checks tie each state to its allowed confirmation, unsubscribe, and
suppression timestamps. A suppressed address cannot self-resubscribe. Removing
suppression administratively leaves it unsubscribed and requires a new
double-opt-in. Subscriber, post, outbox, delivery, and webhook history uses
concrete `PROTECT` foreign keys.

### Credentials

Confirmation and unsubscribe credentials are Django `TimestampSigner`
credentials keyed by a dedicated secret of at least 32 UTF-8 bytes. Their
payload contains only schema version, purpose, subscriber UUID, and the
appropriate token version. Raw credentials are never persisted.

Confirmation credentials expire after 48 hours by default. Invalid, expired,
wrong-purpose, tampered, unknown, and superseded credentials share one public
error. A repeated valid confirmation is idempotent. Human email links carry
the credential in the URL fragment; the client removes the fragment with
`history.replaceState` before rendering the action and mutates only after an
explicit CSRF-protected POST. This prevents GET-only scanners from confirming
or unsubscribing and keeps the credential out of HTTP request logs and
referrers.

Unsubscribe credentials are version-revocable and deliberately do not expire.
A new successful opt-in increments the version, while a repeated unsubscribe
with the current credential remains idempotent. Publication messages also
carry RFC 8058 `List-Unsubscribe` and `List-Unsubscribe-Post` headers. The
one-click URL is a separate CSRF-exempt POST boundary that accepts only the
exact form body `List-Unsubscribe=One-Click`; normal browser actions retain
same-origin CSRF.

### Outbox and publication boundary

A confirmation request and the first actual public publication create
`EmailOutbox` rows transactionally. No network request occurs in request,
confirmation, or Wagtail publication transactions. Publication creation
reuses the canonical public visibility policy and has a conditional unique
constraint on post, so drafts, future schedules, restricted posts, and normal
republishes cannot create duplicate events. Wagtail's scheduled publication
signal creates the event when the schedule becomes due.

The publication row stores an immutable `audience_cutoff`. The worker creates
`EmailDelivery` rows in bounded batches for subscribers whose `confirmed_at`
is at or before that cutoff. Current inactive members receive terminal
`skipped` deliveries. A later confirmation cannot enter the old audience, and
later unsuppression cannot revive an old skipped delivery. A unique
`(outbox, subscriber)` constraint is the final per-recipient duplicate
boundary.

Workers claim rows with `select_for_update(skip_locked=True)` on PostgreSQL,
reclaim stale processing rows, and send outside the claim transaction.
Delivery failures use capped exponential backoff and become terminal after the
configured attempt limit. One delivery failure does not stop the rest of a
batch. Provider idempotency keys are `email/<immutable delivery UUID>`.

The processing lease and provider ambiguity clock are separate. The lease uses
mutable `processing_at`; `first_provider_attempt_at` is written once immediately
before the first possible network call, and `last_provider_attempt_at` records
later calls. Timeout, connection reset, retryable provider failure, or a
concurrent-idempotency response preserves that metadata when the delivery
returns to pending.

Because Resend retains idempotency keys for only 24 hours, the default local
safety window is 23 hours measured absolutely from
`first_provider_attempt_at`. Pending work and reclaimed stale processing work
both become terminal `manual_review` at the deadline without calling the
provider. Reclaim, backoff, worker downtime, or a sparse schedule cannot move
the deadline. The attempt cap is an additional limit, not a replacement for
the absolute window.

### Provider and messages

The provider interface is `send(message, idempotency_key)`. Production uses
the Resend `POST /emails` adapter; tests use a deterministic in-memory adapter
or explicit fakes and perform no network I/O. Safe error classifications, not
provider response bodies, are persisted.

Every outbox event captures message schema version, FROM address, public
origin, subject, and—when applicable—publication title, excerpt, and canonical
URL. Every delivery captures recipient address, credential token version, and
one immutable credential issue time. Confirmation and unsubscribe credentials
are regenerated deterministically from those inputs and the signing secret;
the raw signed value is never stored.

The delivery also stores SHA-256 of the exact compact UTF-8 JSON body sent to
Resend. This fingerprint is created with the delivery and checked before every
provider call. Thus the same `email/<delivery UUID>` key can reach Resend only
with a byte-equivalent body. A post edit/republish, template deployment,
`RESEND_FROM_EMAIL` change, or public-origin change does not silently mutate an
existing request. Unsupported schema or fingerprint mismatch becomes terminal
`manual_review` without provider I/O. A new template shape requires a new
message schema version while older renderers remain available until their
deliveries are terminal.

Templates render explicit HTML and plain text parts. Publication messages
contain only the snapshotted title, excerpt, canonical public URL, and
unsubscribe links; the StreamField body is not included. Django template
autoescaping protects HTML values.

The Resend adapter bounds both success and error response reads before parsing.
It stores only safe classifications. `invalid_idempotent_request` is terminal,
`concurrent_idempotent_requests` is retryable, and an unknown 409 is
conservatively terminal because its idempotency semantics are not known.
Provider bodies, API keys, and authorization headers never enter
`last_error`.

Immediately before a publication delivery's first provider call, the worker
reapplies the canonical public visibility policy. Unpublished, expired,
restricted, future-scheduled, or no-longer-public-section posts become
`skipped` without provider I/O. Normal edit/republish leaves the immutable
snapshot unchanged. After the first possible call, visibility changes do not
rewrite or cancel an ambiguous retry because the provider may already have
accepted the snapshotted request.

### Webhooks and abuse boundary

The Resend endpoint reads a bounded raw body, validates the timestamp replay
window, and delegates exact Svix signature verification to the official Python
SDK before JSON/business processing. `EmailWebhookEvent` stores the provider
event ID under a unique constraint, event type, timestamps, and optional
delivery relation. It does not store a raw payload or an unbounded JSON ID
list.

Only the stored provider message ID can select a delivery. Recognized delivery,
permanent-bounce, and complaint events store only bounded provider message ID,
event type, occurrence time, normalized bounce classification, and processing
state. If the webhook arrives before the worker commits the message ID, the
event remains durably `pending` and still returns 200. Provider settlement
immediately reconciles matching pending events; the bounded
`reconcile_email_webhooks` command is the crash/restart backstop.

Pending events apply deterministically by provider occurrence time, receipt
time, and local ID. Bounces and complaints suppress the subscriber, and
complaint/bounce terminal state wins over a late delivered event. Duplicate
`svix-id` remains idempotent. Unknown event types are immediately ignored.
Authenticated recognized events with genuinely foreign IDs remain pending for
seven days and then become ignored; applied/ignored ledger rows are retained
for 30 days and deleted only by the bounded reconciliation command. This
durable-200 approach avoids a retry storm while bounding unmatched history.
Raw webhook payloads are not stored.

### Concurrent unsubscribe

Unsubscribe locks the subscriber and skips only deliveries that have not been
claimed. It immediately prevents future claims and causes later publication
deliveries to be created as skipped. A processing delivery is left processing
because an already-started provider call cannot be cancelled reliably.
Settlement uses a row lock and state comparison: accepted provider mail becomes
`sent` even if unsubscribe happened in flight, while the subscriber remains
unsubscribed. Retryable ambiguous failure after that concurrent unsubscribe
becomes `manual_review`, not a misleading guaranteed cancellation. Webhook and
other terminal states are never overwritten unconditionally.

Anonymous subscribe and confirm use database-backed fixed windows. Keys are
HMAC digests scoped to canonical email or client IP; raw IPs and rate-limit
emails are not stored. Client IP selection uses the existing rightmost
`ALLAUTH_TRUSTED_PROXY_COUNT` contract. Subscribe responses are the same generic
202 for new, pending, active, unsubscribed, and suppressed identities.

## Consequences

Positive:

- publication and confirmation survive provider downtime without coupling
  provider failure to the user transaction;
- audience cutoff, concrete delivery uniqueness, and provider idempotency
  provide bounded, inspectable duplicate protection;
- GET scanners cannot mutate subscription state;
- bounce, complaint, and unsubscribe state immediately prevents pending work;
- provider replacement does not require changing subscriber or outbox models.

Negative:

- a crashed ambiguous send beyond the local safety deadline requires manual
  review rather than retry;
- applied/ignored webhook rows require the bounded retention command; outbox,
  delivery, and rate-limit retention remains future policy;
- actual periodic scheduling, alerting, DNS, and provider configuration remain
  infrastructure work.

## Revisit conditions

Revisit this decision if the audience no longer fits bounded relational batch
generation, multiple subscription topics are introduced, a provider offers a
longer queryable idempotency ledger, or infrastructure adopts a dedicated
queue while preserving the database outbox as the source of truth.
