# OAuth setup

Status: implemented application configuration; external applications pending

The site uses the classic django-allauth browser OAuth flow with Google and
GitHub. Django owns identities, database-backed sessions, and CSRF. Next.js owns
the login/account presentation and reaches only fixed same-origin paths.
Provider access and refresh tokens are discarded after identification.

There is no Auth.js/NextAuth, JWT, `localStorage` token, `X-Session-Token`, CORS
configuration, or database-managed `SocialApp`. All provider applications use
the settings-based `SOCIALACCOUNT_PROVIDERS[provider].APPS` configuration.

## Environment

Configure exactly these credential variables:

```text
GOOGLE_OAUTH_CLIENT_ID
GOOGLE_OAUTH_CLIENT_SECRET
GITHUB_OAUTH_CLIENT_ID
GITHUB_OAUTH_CLIENT_SECRET
```

Production settings fail during import if any credential is missing. Local
settings allow an omitted provider pair and `/api/me/` reports that provider as
unavailable. Never create a `SocialApp` row for Google or GitHub, because mixing
database and settings applications makes provider selection ambiguous.

Credential values are trimmed before provider applications and the production
required-environment matrix are built. Missing, empty, and whitespace-only
values all fail closed; a successful production import guarantees non-empty
Google and GitHub `APPS`. `SOCIALACCOUNT_REQUESTS_TIMEOUT` defaults to five
seconds and, when configured, must be a finite positive number.

The GitHub Environments for staging and production must each supply the four
names above (client IDs as environment variables or secrets according to the
workflow policy; client secrets as secrets). They are intentionally not added or
changed by application implementation.

## Callback URLs

Register web applications with these exact callbacks:

| Environment | Google | GitHub |
| --- | --- | --- |
| Local | `http://localhost:3000/accounts/google/login/callback/` | `http://localhost:3000/accounts/github/login/callback/` |
| Staging | `https://staging.kirillwynn.com/accounts/google/login/callback/` | `https://staging.kirillwynn.com/accounts/github/login/callback/` |
| Production | `https://kirillwynn.com/accounts/google/login/callback/` | `https://kirillwynn.com/accounts/github/login/callback/` |

Use separate applications and credentials for staging and production. A GitHub
OAuth App accepts only one callback URL, so staging and production necessarily
use different GitHub applications. Keep local credentials separate from both
deployed environments when a live local consent flow is needed.

For local development, begin at `http://localhost:3000/login`. Next.js has
fixed rewrites for `/accounts/*`, `/api/me/`, and `/api/auth/logout/`; it is not
a caller-controlled general proxy. The Django trusted origins must include
`http://localhost:3000`.

## Provider permissions

Google requests only:

- `openid`;
- `profile`;
- `email`.

Google PKCE is enabled and `access_type=online`; no offline access, Gmail, or
Drive permission is requested.

GitHub requests only `user:email`, which is needed to read a private primary
email. It does not request repository, organization, workflow, code, or write
access.

Automatic matching considers only addresses marked verified by the provider.
The project does not set an unconditional `VERIFIED_EMAIL=True`. A new identity
without a verified provider email is rejected. A second provider with the same
verified email connects to the existing user; explicit `process=connect` is
available from `/account`. The `(provider, uid)` database constraint and
allauth connection flow prevent silent reassignment from another user.

## Sessions, cookies, and CSRF

Local HTTP uses ordinary `sessionid` and `csrftoken` names. Production uses
`__Host-sessionid` and `__Host-csrftoken`, both Secure, Path `/`, and without a
Domain attribute. Session cookies are HttpOnly and SameSite=Lax. The CSRF cookie
is also HttpOnly and SameSite=Lax because `/api/me/` returns a masked CSRF token
for POST forms and the logout header.

Django rotates the session key on login. Production trusts exactly one reverse
proxy for allauth client-IP handling and uses
`SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`. Configure
`DJANGO_CSRF_TRUSTED_ORIGINS` explicitly per deployed environment.

## Safe return destinations

Django is the authoritative return-to boundary. A destination is decoded
exactly once with strict UTF-8 percent handling and must begin with exactly one
slash in both its raw and decoded forms. Schemes, authorities, fragments,
backslashes, control characters, malformed percent escapes, double encoding,
and network-path references are rejected before the product allowlist is
evaluated. Django's `url_has_allowed_host_and_scheme` is an additional
defense-in-depth check.

Only `/`, `/bridge`, `/account`, and `/posts/<unicode-slug>` are accepted. A
query string is retained only for one of those paths and cannot contain raw or
encoded control characters. `/login`, arbitrary frontend routes, and the
`/api`, `/accounts`, `/cms`, and `/django-admin` service boundaries are never
valid return destinations. Invalid values are not stored in OAuth state and
fall back to `/`.

## Site owner

Do not infer or hardcode the owner email. After the intended owner has completed
a verified Google or GitHub signup, configure:

```text
SITE_OWNER_EMAIL=owner@example.com
```

Then run deliberately in the intended environment:

```bash
cd backend/django
uv run python manage.py promote_site_owner
```

The command requires an existing matching user, a verified allauth
`EmailAddress`, and a connected Google or GitHub identity. It idempotently
grants Django/Wagtail administrator status and never creates a user. Do not run
it against production as part of automated deployment.

## External setup checklist

- Create separate staging and production Google OAuth web clients.
- Create separate staging and production GitHub OAuth Apps.
- Enter only the callback URL for the matching environment.
- Put the four credential names in the matching GitHub Environment.
- Confirm the public origin, allowed host, and CSRF trusted origin agree.
- Run a staging live-consent smoke test before production.
- Never log authorization codes, access tokens, refresh tokens, client secrets,
  provider payloads, or session keys.
