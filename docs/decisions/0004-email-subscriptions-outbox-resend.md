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
hours. Its webhooks use the Svix `svix-id`, `svix-timestamp`, and
`svix-signature` contract over the exact raw body, provide at-least-once
delivery, and do not guarantee event ordering.

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

Because Resend retains idempotency keys for only 24 hours, the default local
safety window is 23 hours. An ambiguous processing attempt older than that is
failed without another provider call, preferring a visible terminal failure
over a possible duplicate. The worker must therefore run much more frequently
than this window.

### Provider and messages

The provider interface is `send(message, idempotency_key)`. Production uses
the Resend `POST /emails` adapter; tests use a deterministic in-memory adapter
or explicit fakes and perform no network I/O. Safe error classifications, not
provider response bodies, are persisted.

Templates render explicit HTML and plain text parts. Publication messages
contain only title, excerpt, canonical public URL, and unsubscribe links; the
StreamField body is not included. Django template autoescaping protects HTML
values. All application-owned URLs start from the validated
`PUBLIC_SITE_URL`.

### Webhooks and abuse boundary

The Resend endpoint reads a bounded raw body, validates the timestamp replay
window, and delegates exact Svix signature verification to the official Python
SDK before JSON/business processing. `EmailWebhookEvent` stores the provider
event ID under a unique constraint, event type, timestamps, and optional
delivery relation. It does not store a raw payload or an unbounded JSON ID
list.

Only the stored provider message ID can select a delivery. Delivered, permanent
bounce, and complaint events update delivery state. Bounces and complaints
suppress the subscriber. Terminal bounce/complaint state wins over a late
delivered event. Unknown types and message IDs are authenticated, deduplicated,
and safely ignored.

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

- a crashed ambiguous send beyond Resend's 24-hour key retention is failed for
  manual review rather than retried;
- outbox, delivery, webhook-event, and rate-limit rows need a future retention
  policy;
- actual periodic scheduling, alerting, DNS, and provider configuration remain
  infrastructure work.

## Revisit conditions

Revisit this decision if the audience no longer fits bounded relational batch
generation, multiple subscription topics are introduced, a provider offers a
longer queryable idempotency ledger, or infrastructure adopts a dedicated
queue while preserving the database outbox as the source of truth.
