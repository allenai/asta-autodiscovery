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
| `auth0` (default) | Hosted, multi-user deployments (SSO). | Redirect to Auth0. | An Auth0 tenant + application. |
| `password_file` | Self-hosted / small teams without Auth0. | Username + password form. | A mounted user file + a session secret. |
| `none` | Local "desktop" mode / single-user dev. | None — always signed in. | Nothing. |

## `auth0` (default)

Validates Auth0-issued JWTs and drives the Auth0 login redirect.

```bash
AUTH_PROVIDER=auth0            # (default; may be omitted)
AUTH0_DOMAIN=your-tenant.auth0.com
AUTH0_AUDIENCE=https://your-api-identifier
AUTH0_CLIENT_ID=your-spa-client-id   # served to the UI via /api/auth/config
```

`AUTH0_CLIENT_ID` is a public SPA client id (safe to expose). See
[Configuration](configuration.md#authentication) for details and the `NEXT_PUBLIC_AUTH0_*`
build-time fallbacks.

## `password_file`

Users live in a JSON file mounted into the API. `POST /api/auth/login` verifies the
password against the file and issues a short-lived signed session token; the file is
**re-read on every request**, so adding, changing, disabling, or deleting a user takes
effect immediately — no restart.

```bash
AUTH_PROVIDER=password_file
AUTH_PASSWORD_FILE=/secrets/users.json
AUTH_SESSION_SECRET="$(openssl rand -hex 32)"   # ≥ 32 random bytes
# AUTH_SESSION_TTL=43200                          # optional, seconds (default 12h)
```

Mount the store read-only into the API container (see the commented bind mount in
`docker-compose.yaml`).

### Managing users

Administer the file with `api/scripts/auth_admin.py` (path from `--file` or
`$AUTH_PASSWORD_FILE`). It shares the store/hashing code with the running API, so formats
never drift, and changes are live immediately.

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

## `none` (desktop mode)

Every request is a fixed `local` user with all permissions; there is no login UI.
Intended for single-user local runs and development — **do not use in a shared or
production deployment**, as it grants everyone full access.

```bash
AUTH_PROVIDER=none            # no other configuration
```
