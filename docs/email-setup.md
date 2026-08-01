# Email setup

Subscription and account mail use separate durable application records while
sharing the same deterministic provider transport. Do not put real values in
Git, `.env.example`, a browser bundle, or command output. Provider, GitHub
Environment, DNS, scheduler, and monitoring changes are external setup.

## Environment separation

Create separate Resend configuration and GitHub Environment values for
`staging` and `production`. Never reuse signing secrets, API keys, webhook
endpoints, databases, or sender subdomains between them.

Required secret names:

- `RESEND_API_KEY`;
- `RESEND_WEBHOOK_SECRET`;
- `SUBSCRIPTION_SIGNING_SECRET` (at least 32 UTF-8 bytes);
- the existing `DJANGO_SECRET_KEY`, database, OAuth, and
  `REVALIDATION_SECRET` values.

Required non-secret runtime values:

- `EMAIL_PROVIDER_ADAPTER=apps.subscriptions.providers.resend.ResendEmailProvider`;
- `EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE`, a stable non-secret label for the
  exact provider account and environment, for example
  `resend/production/account-main`;
- `EMAIL_FROM_ADDRESS` using an address on the verified environment-specific
  sending domain;
- `PUBLIC_SITE_URL` for the corresponding public origin.

`EMAIL_FROM_ADDRESS` is required for every production adapter, not just
Resend. It is normalized by trimming outer whitespace and rejected before
Django starts if it is empty, contains CR/LF, exceeds 512 code points, or does
not contain a valid mailbox; a display name is allowed. `RESEND_API_KEY` and
`RESEND_WEBHOOK_SECRET` remain conditional on the Resend adapter.
The namespace is trimmed and lowercased, limited to 128 ASCII characters, and
accepts only letters, digits, `.`, `_`, `:`, `/`, and `-`. Never put an API key,
webhook secret, credential, or raw account token in it.

Optional tuning values are documented in `.env.example`. In particular,
`EMAIL_PROVIDER_IDEMPOTENCY_WINDOW_SECONDS` defaults to 82,800 seconds, below
Resend's 24-hour idempotency retention. Provider success/error bodies are read
only up to their separate 65,536-byte limits. Webhook correlation defaults to
seven days and applied/ignored event retention to 30 days.

## Local-account mail boundary

Email verification and password reset use `AuthEmailOutbox` and
`AuthEmailDelivery`, not `Subscriber`, `EmailOutbox`, publication decisions, or
newsletter constraints. The web role has the Django signing/session key and
provider-independent serializer configuration but never receives
`RESEND_API_KEY`; its transaction creates one bounded event and records only
the SHA-256 fingerprint of the exact provider request. The worker role receives
the send key, reconstructs the same bytes, verifies contract/version/namespace
and fingerprint, and only then performs provider I/O.

`ACCOUNT_EMAIL_VERIFICATION="none"` and
`ACCOUNT_EMAIL_NOTIFICATIONS=False` are deliberate: allauth still owns account
and social flows, while Stage 17 exclusively owns verification/reset delivery.
Do not enable an allauth SMTP/notification fallback in the web role.

The account transport namespace is the configured environment-specific
`EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE` with a fixed `/auth` suffix. The
provider-visible idempotency key is that namespace plus the delivery UUID;
retries reuse it byte-for-byte and stop before
`EMAIL_PROVIDER_IDEMPOTENCY_WINDOW_SECONDS`; an ambiguous delivery that reaches
the boundary moves to `manual_review` without another provider call. Terminal
errors are bounded and raw provider bodies are never stored or logged.

Verification credentials default to 86,400 seconds and password-reset
credentials to 3,600 seconds. Their per-purpose HMAC keys are domain-separated
from each other and from rate-limit keys; deployed web and worker roles derive the same
keys from their shared environment-specific `DJANGO_SECRET_KEY`. Optional
local overrides are `AUTH_CREDENTIAL_SIGNING_SECRET` and
`AUTH_RATE_LIMIT_SIGNING_SECRET`, each at least 32 UTF-8 bytes. Other bounded
defaults are `AUTH_API_MAX_BODY_BYTES=16384`,
`WORKER_AUTH_EMAIL_INTERVAL_SECONDS=10`, and
`WORKER_AUTH_EMAIL_BATCH_SIZE=25`.

Credential consumption locks the user before credential/allauth-address rows.
Reset succeeds only while the bound canonical address remains the unique
verified primary address; case and NFKC variants are resolved with the same
normalizer used by signup, login, and provider linking.

Wagtail keeps staff password login and authenticated password change, but its
separate public password-reset flow is disabled: that flow would place a
credential in the query string and send synchronously outside
`AuthEmailOutbox`. Wagtail self-service email editing is disabled as well;
email change is intentionally outside Stage 17.

Only a digest and a purpose/user/email/version/expiry lifecycle row are stored;
the raw credential is reconstructed for the immutable message and appears only
after a URL fragment marker:

```text
/account/verify-email#credential=...
/account/password/reset/confirm#credential=...
```

Fragments are not sent in HTTP requests. The Next entry removes the fragment
immediately and posts the credential only in a CSRF-protected JSON body. Plain
text and HTML templates use generic subjects and contain no account metadata
beyond the destination link.

## Resend domain and DNS checklist

1. Add an environment-specific sending domain in Resend. A dedicated subdomain
   is recommended to isolate reputation.
2. Copy the exact SPF and DKIM records shown by Resend into the DNS provider.
   Do not invent, merge, or copy example record values from this document.
3. Wait for both SPF and DKIM to show verified in Resend.
4. Add DMARC only after SPF and DKIM pass. Start with a monitored `p=none`
   policy and a controlled aggregate-report mailbox, verify every legitimate
   sender, then move deliberately to `quarantine` or `reject`.
5. Send test mail for each environment and inspect headers for SPF, DKIM, and
   DMARC pass before enabling a worker schedule.

Official references:

- [Resend domain verification, SPF, and DKIM](https://resend.com/docs/dashboard/domains/introduction)
- [Resend DMARC implementation guide](https://resend.com/docs/dashboard/domains/dmarc)
- [Resend deliverability insights](https://resend.com/docs/dashboard/emails/deliverability-insights)

## Webhook

Register this exact HTTPS endpoint per environment:

```text
https://<public-origin>/api/v1/email/webhooks/resend/
```

Enable:

- `email.delivered`;
- `email.bounced`;
- `email.complained`.

Copy that endpoint's Svix signing secret to its matching
`RESEND_WEBHOOK_SECRET`. The application verifies the exact raw body plus
`svix-id`, `svix-timestamp`, and `svix-signature`, enforces a replay window,
and deduplicates `svix-id`. Do not place a proxy in front of it that rewrites
the body. Recognized events that beat provider-ID persistence are durably
pending rather than rejected; genuinely foreign IDs therefore still receive
200 and age out instead of creating a retry storm.

Official references:

- [Resend webhook verification](https://resend.com/docs/webhooks/verify-webhooks-requests)
- [Resend webhook event types](https://resend.com/docs/webhooks/event-types)
- [Resend retries and replays](https://resend.com/docs/webhooks/retries-and-replays)

## Sending and unsubscribe

Resend sends multipart HTML/plain-text content through `POST /emails` with a
per-delivery `Idempotency-Key`. Publication messages include
`List-Unsubscribe` and RFC 8058 `List-Unsubscribe-Post` headers and an in-body
unsubscribe link. One immutable outbox snapshot pins schema version, sender,
public origin, subject, and publication inputs. A delivery pins recipient,
credential version/issue time, and the SHA-256 fingerprint of the exact bytes
selected during one adapter preparation call. It also pins the adapter contract
identifier, serializer contract version, and idempotency namespace. The worker
checks all four values and passes the already verified immutable bytes directly
to transport; the Resend adapter does not serialize again. A retry is sent only
while every value still matches and before the absolute local safety deadline
from the first possible provider call. The bundled external production adapter
is Resend contract `resend.emails`, serializer version `1`; a replacement
adapter must define and test its own stable contract/version, namespace, exact
request bytes, and safe error classifications. The memory adapter is
local/test-only.

Official references:

- [Resend send-email API](https://resend.com/docs/api-reference/emails/send-email)
- [Resend idempotency keys](https://resend.com/docs/dashboard/emails/idempotency-keys)
- [Resend one-click unsubscribe headers](https://resend.com/docs/dashboard/emails/add-unsubscribe-to-transactional-emails)

## Rotation

API key rotation inside the same Resend account/environment:

1. create a replacement key in the correct Resend environment;
2. keep `EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE` unchanged;
3. update only the `RESEND_API_KEY` GitHub Environment secret and restart the
   email worker/runtime;
4. verify a controlled send and webhook;
5. revoke the old key.

This is safe because credential rotation does not change the provider's
idempotency ledger. Never derive the namespace from either key.

Provider, account, environment, or idempotency-scope change:

1. pause worker scheduling and allow active provider calls to settle;
2. finish retryable deliveries with the old adapter/namespace where safe, or
   explicitly leave them for manual review;
3. configure the new adapter/account and a new non-secret
   `EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE`;
4. restart the runtime and verify a new controlled delivery;
5. resume scheduling. Existing deliveries created under the old identity do
   not cross the boundary: a mismatch becomes `manual_review` before I/O.

Changing request serialization also requires an explicit serializer contract
version bump. Keep the old adapter/version available to finish old deliveries,
or review them manually; do not claim a version change is a safe retry.

Webhook signing secret:

1. pause email worker scheduling;
2. create or rotate the environment-specific webhook in Resend;
3. update `RESEND_WEBHOOK_SECRET` and restart Django;
4. replay a controlled event and confirm a 200;
5. resume the worker. Keep the pause shorter than the documented Resend retry
   period.

Subscription signing secret:

1. pause the email worker;
2. update `SUBSCRIPTION_SIGNING_SECRET` and restart Django and the worker;
3. resume processing.

Rotating the subscription signing secret intentionally invalidates outstanding
confirmation and unsubscribe credentials. Readers can request a new
confirmation; administrators must account for already-sent unsubscribe links
before choosing this rotation.

## Worker scheduling

The repository-owned `worker` service runs one scheduler per environment. Its
defaults are:

- `process_email_outbox` every 10 seconds with outbox/delivery limits 25/100;
- `process_auth_email_outbox` every 10 seconds with limit 25;
- `reconcile_email_webhooks` every 60 seconds with limit 100;
- `process_revalidation_outbox` every 15 seconds with limit 100;
- `publish_scheduled_pages` every 60 seconds.

Every task fails and backs off independently, and Docker monitors the atomic
heartbeat. The management commands remain available for controlled bounded
invocations:

```bash
cd backend/django
uv run python manage.py process_email_outbox --limit 25 --delivery-limit 100
```

Run account mail independently:

```bash
cd backend/django
uv run python manage.py process_auth_email_outbox --limit 25
```

Schedule it independently and much more frequently than the 23-hour
idempotency safety window. Monitor terminal `failed` outbox/delivery rows,
`manual_review` deliveries, bounce/complaint volume, queue age, and command
exit status. Lease reclaim never moves the first-provider-attempt timestamp.
Once the absolute deadline is reached, neither pending nor stale-processing
work can call Resend.

Also run the bounded correlation/retention backstop:

```bash
cd backend/django
uv run python manage.py reconcile_email_webhooks --limit 100
```

It applies pending events whose provider message ID has appeared, expires
unmatched events, and deletes retained history only after the configured
retention period. Enabling the service and external queue-age/manual-review
alerts belongs to staging activation.

Wagtail search indexing is separate work. Run:

```bash
uv run python manage.py update_index
```

as an explicit deploy/search operation, never chained to
`process_email_outbox`; a slow index rebuild must not delay email retries.
