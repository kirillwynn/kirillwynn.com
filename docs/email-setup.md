# Email subscription setup

Milestone 9 implements the application boundary only. Do not put real values in
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
- `RESEND_FROM_EMAIL` using an address on the verified environment-specific
  sending domain;
- `PUBLIC_SITE_URL` for the corresponding public origin.

Optional tuning values are documented in `.env.example`. In particular,
`EMAIL_PROVIDER_IDEMPOTENCY_WINDOW_SECONDS` defaults to 82,800 seconds, below
Resend's 24-hour idempotency retention.

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
the body.

Official references:

- [Resend webhook verification](https://resend.com/docs/webhooks/verify-webhooks-requests)
- [Resend webhook event types](https://resend.com/docs/webhooks/event-types)
- [Resend retries and replays](https://resend.com/docs/webhooks/retries-and-replays)

## Sending and unsubscribe

Resend sends multipart HTML/plain-text content through `POST /emails` with a
per-delivery `Idempotency-Key`. Publication messages include
`List-Unsubscribe` and RFC 8058 `List-Unsubscribe-Post` headers and an in-body
unsubscribe link.

Official references:

- [Resend send-email API](https://resend.com/docs/api-reference/emails/send-email)
- [Resend idempotency keys](https://resend.com/docs/dashboard/emails/idempotency-keys)
- [Resend one-click unsubscribe headers](https://resend.com/docs/dashboard/emails/add-unsubscribe-to-transactional-emails)

## Rotation

API key:

1. create a replacement key in the correct Resend environment;
2. update only that GitHub Environment secret;
3. restart the email worker/runtime;
4. verify a controlled send and webhook;
5. revoke the old key.

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

Run a bounded invocation:

```bash
cd backend/django
uv run python manage.py process_email_outbox --limit 25 --delivery-limit 100
```

Schedule it independently and much more frequently than the 23-hour
idempotency safety window. Monitor terminal `failed` outbox/delivery rows,
bounce/complaint volume, queue age, and command exit status. Adding the actual
service/timer and alerts belongs to the infrastructure milestone.

Wagtail search indexing is separate work. Run:

```bash
uv run python manage.py update_index
```

as an explicit deploy/search operation, never chained to
`process_email_outbox`; a slow index rebuild must not delay email retries.
