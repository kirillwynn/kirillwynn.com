# Runtime environment matrix

| Boundary | Staging | Production |
|---|---|---|
| Compose project | `kirillwynn-staging` | `kirillwynn-production` |
| Public origin | `https://staging.kirillwynn.com` | `https://kirillwynn.com` |
| Database network | `kirillwynn-staging-database` (`internal`) | `kirillwynn-production-database` (`internal`) |
| Application network | `kirillwynn-staging-application` (`internal`) | `kirillwynn-production-application` (`internal`) |
| Egress network | `kirillwynn-staging-egress` | `kirillwynn-production-egress` |
| Edge network | `kirillwynn-staging-edge` | `kirillwynn-production-edge` |
| Edge aliases | `staging-django`, `staging-next` | `production-django`, `production-next` |
| PostgreSQL volume | `kirillwynn-staging-postgres` | `kirillwynn-production-postgres` |
| Database | `kirillwynn_staging` | `kirillwynn_production` |
| Media | staging-only bucket + `staging/media` | production-only bucket + `production/media` |
| OAuth/Resend/auth mail | staging-only apps, sender, and idempotency namespace | production-only apps, sender, and idempotency namespace |
| Basic Auth | yes, narrow exceptions | no |
| Images | release-manifest digests | same staging-attested digests |

## Role allowlists

| File | Receives |
|---|---|
| `control.env` | project/environment/SHA/sequence, role-file paths, network/volume/alias names, pinned PostgreSQL/Django/Next images |
| `postgres.env` | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` |
| `django.env` | production Django settings, signing/session values, S3, OAuth, Resend webhook verification, auth credential/rate-key derivation; no Resend send API key |
| `worker.env` | minimal production worker settings, DB via separate PostgreSQL file, S3/revalidation/subscription-and-auth-email send values and worker intervals; no OAuth or webhook secret |
| `next.env` | `PUBLIC_SITE_URL`, internal `DJANGO_API_URL`, `REVALIDATION_SECRET` |

Compose interpolation receives only `control.env`; secrets are loaded through
raw role env files. Docker Compose 2.30.0 is the minimum supported version.
Single-line allowed values are byte-preserved, including `$`, `${...}`, `#`,
quotes, backslashes, and spaces. Missing, extra, multiline, NUL, oversized, and
cross-environment values are rejected.

Committed `infra/env/*.env.example` files use syntactically valid non-zero fake
digests and resolvable paths solely for `docker compose config`; they are never
release evidence.

Stage 17 adds no browser or Next secret. Auth credential and rate-limit HMAC
keys are domain-separated derivations of the environment-specific Django key by
default, so web and worker agree without granting the web role the Resend send
key. Verification/reset TTLs and the 16 KiB JSON boundary use checked defaults;
the only new worker runtime knobs are
`WORKER_AUTH_EMAIL_INTERVAL_SECONDS` and `WORKER_AUTH_EMAIL_BATCH_SIZE`.
