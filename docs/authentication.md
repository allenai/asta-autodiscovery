# Authentication

Authentication is a **swappable backend** chosen with the `AUTH_PROVIDER` environment
variable. The API validates the caller on every request; the UI discovers which provider
is active at runtime via `GET /api/auth/config`, so a single build works in all modes.

This page is the setup guide. For the full description of each variable see
[Configuration → Authentication](configuration.md#authentication); for the rationale and
architecture see the [design doc](design/auth-providers.md).

## Choosing a provider

| Provider | Use when | Login UX | Needs |
| --- | --- | --- | --- |
| `none` (default) | Local runs / single-user dev — zero config. | None — always signed in. | Nothing. |
| `auth0` | Hosted, multi-user deployments (SSO). | Redirect to Auth0. | An Auth0 tenant + application. |
| `password_file` | Self-hosted / small teams without Auth0. | Username + password form. | A mounted store dir + a session secret. |
| `trusted_header` | Behind an authenticating proxy or API gateway, alongside one of the above. | None — the upstream signs users in. | A secret shared with the upstream. |

The default is **`none`** so the app runs out of the box with no auth configuration.
**Any real or multi-user deployment must set `AUTH_PROVIDER` explicitly** to `auth0` or
`password_file` — `none` grants everyone full access as a single shared local user.

## `auth0`

Validates Auth0-issued JWTs and drives the Auth0 login redirect.

```bash
AUTH_PROVIDER=auth0
AUTH0_DOMAIN=your-tenant.auth0.com
AUTH0_AUDIENCE=https://your-api-identifier
AUTH0_CLIENT_ID=your-spa-client-id   # served to the UI via /api/auth/config
```

`AUTH0_CLIENT_ID` is a public SPA client id (safe to expose). See
[Configuration](configuration.md#authentication) for details and the `VITE_AUTH0_*`
build-time fallbacks.

## `password_file`

Users live in a JSON file mounted into the API. `POST /api/auth/login` verifies the
password against the file and issues a short-lived signed session token; the file is
**re-read on every request**, so adding, changing, disabling, or deleting a user takes
effect immediately — no restart.

```bash
AUTH_PROVIDER=password_file
AUTH_PASSWORD_DIR=./secrets       # dir holding passwddb.json (fixed filename)
AUTH_SESSION_SECRET="$(openssl rand -hex 32)"   # ≥ 32 random bytes
# AUTH_SESSION_TTL=43200                          # optional, seconds (default 12h)
```

`docker-compose.yaml` bind-mounts `AUTH_PASSWORD_DIR` as a directory into the API
container (read-only). Mounting the directory — rather than the file — means edits
(which write the store atomically) are picked up live without restarting the container.

### Managing users

Administer the store with `api/scripts/auth_admin.py` (directory from `--dir` or
`$AUTH_PASSWORD_DIR`; the file inside is always `passwddb.json`). It shares the
store/hashing code with the running API, so formats never drift, and changes are live
immediately.

```bash
# create a user (prompts for password if --password is omitted)
uv run api/scripts/auth_admin.py useradd alice --email alice@example.org --name Alice \
    --permission enroll:autodiscovery_admin

uv run api/scripts/auth_admin.py passwd alice
uv run api/scripts/auth_admin.py usermod alice --add-permission enroll:higher_upload_limit
uv run api/scripts/auth_admin.py disable alice        # / enable / userdel
uv run api/scripts/auth_admin.py list
```

In a deployed environment, `kubectl exec` into the API container (which has the store
mounted) and run the same command.

## `trusted_header`

Accepts requests relayed by an upstream you trust (an authenticating proxy or an API
gateway) that has already signed the user in. The upstream sends a shared secret as its
bearer token and names the user in a header:

```bash
AUTH_PROVIDER=trusted_header,auth0          # ahead of the provider people sign in with
AUTH_TRUSTED_HEADER_SECRET=<the bearer the upstream sends>
# AUTH_TRUSTED_HEADER_USER=X-Forwarded-User  # the default
```

The header is trusted only on a request bearing the secret, so the upstream must drop
any copy of it that its own callers send. Anyone holding the secret can act as any user:
guard it like a signing key. The value becomes the user id; to share runs
with users who also sign in directly, the upstream names them by the same id the other
provider gives them (for `auth0`, the Auth0 subject).

`AUTH_TRUSTED_HEADER_USER` may list several headers, each optionally `header=prefix`, for
an upstream that names different kinds of caller in different headers. A request must
carry exactly one of them, and the prefix keeps the kinds apart:

```bash
AUTH_TRUSTED_HEADER_USER=X-Forwarded-User,X-Forwarded-Service=service:
```

Callers authenticated this way hold no permissions: they get the default upload limit and
no admin access.

## `none` (desktop mode) — default

The default provider. Every request is a fixed `local` user with all permissions; there
is no login UI. Zero configuration, so the app runs out of the box — but **do not use in
a shared or production deployment**, as it grants everyone full access.

```bash
AUTH_PROVIDER=none            # the default; no other configuration
```

## Several providers

`AUTH_PROVIDER` may list several providers, separated by commas. Each request goes to the
first provider, in order, that recognizes its credentials. A provider that accepts every
request (`auth0`, `password_file`, `none`) recognizes them all, so it must come last; one
that recognizes only its own kind of credential (`trusted_header`) goes before it. The UI's login is the
first provider people sign in with.

A single name behaves exactly as before.

## Referring to yourself as `me`

Any `<userid>` in an API path may be `me`, meaning the signed-in caller, so a client
needn't know which id the API keys it on (`GET /api/runs/me/list`). An anonymous request
that uses `me` gets a 401.
