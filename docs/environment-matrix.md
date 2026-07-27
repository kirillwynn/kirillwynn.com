# Runtime environment matrix

| Boundary | Local | Staging | Production |
|---|---|---|---|
| Compose project | root dev stack | `kirillwynn-staging` | `kirillwynn-production` |
| Public origin | `http://localhost:3000` | `https://staging.kirillwynn.com` | `https://kirillwynn.com` |
| Edge network | none | `kirillwynn-staging-edge` | `kirillwynn-production-edge` |
| Django alias | `django` | `staging-django` | `production-django` |
| Next alias | `next` | `staging-next` | `production-next` |
| Database | local `kirillwynn` | `kirillwynn_staging` | `kirillwynn_production` |
| Media | filesystem | staging-only bucket + `staging/media` | production-only bucket + `production/media` |
| OAuth | optional local apps | staging Google/GitHub apps | production Google/GitHub apps |
| Email | memory adapter | staging Resend namespace/domain | production Resend namespace/domain |
| Basic Auth | no | yes, except ACME and exact webhook | no |
| Images | local build | release-manifest digests | same staging-attested digests |

`DJANGO_SECRET_KEY`, revalidation/subscription keys, PostgreSQL password, S3,
OAuth, Resend, and webhook credentials must be unique. Provider namespace,
bucket/prefix, sender domain, media origin, database/user, Compose project,
edge network, and aliases are non-secret but must also differ.

Committed `infra/env/*.env.example` files define names and placeholders only.
GitHub Actions generates the real file, validates a fixed allowlist, transfers
it as mode 0600, and atomically installs it under
`/srv/kirillwynn/runtime/`.
