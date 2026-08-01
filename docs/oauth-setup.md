# OAuth setup

Status: implemented; staging applications configured; production applications absent

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

The rendered runtime must supply the four names above. GitHub Actions reserves
the `GITHUB_` prefix for secret names, so each GitHub Environment stores the
GitHub provider credentials as `OAUTH_GITHUB_CLIENT_ID` and
`OAUTH_GITHUB_CLIENT_SECRET`; the deployment workflows map those source secrets
to the runtime names Django expects. Google credentials use
`GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` directly. They are
intentionally not added or changed by application implementation.

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
fixed rewrites for `/accounts/*`, `/api/me/`, logout, and each documented local
account mutation. Nginx has the same explicit location list. Neither layer has
a general `/api/*` or `/api/auth/*` proxy. The Django trusted origins must
include `http://localhost:3000`.

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
An already linked provider must continue to return that Django user's canonical
email as verified on every login. A different newly verified provider address
does not silently change or bypass the local identity; email change is outside
Stage 17 and the login fails closed.

Only the selected authoritative verified address is normalized and passed to
allauth persistence. Extra provider-profile addresses are not persisted as
secondary identity candidates. A takeover of an unverified preregistration
always rotates the Django password hash, including an already-unusable hash,
so every pre-existing session is invalidated.

The installed django-allauth 65.18.0 extension contract is explicit:
`ACCOUNT_LOGIN_METHODS={"email"}`, `ACCOUNT_USER_MODEL_USERNAME_FIELD=None`,
settings-backed provider `APPS`, provider `EMAIL_AUTHENTICATION=True`, custom
account/social adapters, and `SOCIALACCOUNT_STORE_TOKENS=False`. Provider
scopes and Google PKCE remain unchanged. Public local forms are project-owned
JSON/Next surfaces; duplicate allauth HTML account/password/social-management
routes return 404, while allauth continues to own the exact Google/GitHub
provider initiation, callback, state, and connection processing routes.

The public JSON login consumes its transactional PostgreSQL IP/email limits
before invoking allauth's `LoginForm`. Only allauth's duplicate cache-based
`login_failed` action is disabled, preventing process-local early rejection;
other installed-version allauth rate-limit defaults remain unchanged.

## Local/provider linking matrix

- A verified local account followed by Google or GitHub with the same verified
  canonical email stays one `User`; its password is preserved.
- A verified Google account may set a local password and later connect GitHub,
  still on the same `User`.
- A provider-verified identity may reclaim an unverified local
  preregistration of that exact canonical address. The preregistration's
  password, sessions, and outstanding credentials are invalidated before the
  provider is connected and the primary address becomes verified. Its
  untrusted nickname is marked incomplete until the verified owner explicitly
  accepts or replaces it on `/account/profile`.
- An unverified provider address never signs up, authenticates by email, or
  connects.
- Explicit connection requires the current account to have the same verified
  primary email. A `SocialAccount` already owned by another user cannot move.
- Repeated callbacks are idempotent and no `SocialToken` is persisted.
- Inactive and banned users cannot enter through local or social login.

A newly created OAuth user receives an opaque provisional public key and a
provider-name suggestion only. The suggestion is not trusted or automatically
confirmed. `/account/profile` requires a valid unique nickname before
`can_interact` becomes true and then returns to the backend-approved original
destination. Reading, logout, password setup, and account management remain
available during completion.

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

The command requires an existing matching user, the matching verified primary
allauth `EmailAddress`, and a connected Google or GitHub identity. It
idempotently grants Django/Wagtail administrator status and the unique public
site-author marker, refuses to replace a different marked author, and never
creates a user. Do not run it against production as part of automated
deployment.

## External setup checklist

- Create separate staging and production Google OAuth web clients.
- Create separate staging and production GitHub OAuth Apps.
- Enter only the callback URL for the matching environment.
- Put `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`,
  `OAUTH_GITHUB_CLIENT_ID`, and `OAUTH_GITHUB_CLIENT_SECRET` in the matching
  GitHub Environment; deployment maps the GitHub pair to the runtime names.
- Confirm the public origin, allowed host, and CSRF trusted origin agree.
- Run a staging live-consent smoke test before production.
- Never log authorization codes, access tokens, refresh tokens, client secrets,
  provider payloads, or session keys.
