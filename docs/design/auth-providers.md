# Swappable Auth Providers — Design

Status: **Implemented** · Branch: `swappable-auth-providers`

> See [As built](#as-built) at the end for the concrete file layout, operator
> commands, and where the implementation differs from the original proposal.

## Goal

Make authentication pluggable across the Flask API backend and the Next.js UI,
with three interchangeable providers selected by configuration:

1. **`auth0`** — the current Auth0 OIDC/JWT implementation (default; unchanged behavior).
2. **`password_file`** — a `user:password` file administered by a Python CLI, mounted
   into the API container and **re-read on every auth check** so new/changed users take
   effect without restarting the web stack.
3. **`none`** — "desktop mode". Authentication is faux: every request is the fixed
   user `local`. All user-aware business logic keeps working unchanged.

The provider is chosen by a single config value and activated at process start; the UI
discovers the active provider at runtime so a single build serves all three modes.

---

## Current state (what we're abstracting)

### Backend (`api/`, Flask)
- `api/utils/auth.py` exposes three decorators used across ~23 endpoints:
  - `requires_auth(required_permission=None, check_permissions=[...])`
  - `requires_enrollment` — `requires_auth` with `AUTH0_REQUIRED_PERMISSION`
  - `optional_enrollment` — authenticate-if-present, else anonymous (`request.user = {}`)
- Each decorator validates a `Bearer` JWT against Auth0 JWKS (`verify_token`) and sets
  `request.user = <payload dict>` plus `set_userid(payload["sub"])` for logging.
- Handlers read `request.user.get("sub")` and `request.user.get("permissions", [])`.
  `check_permissions` flags are stashed via `setattr(request, perm.value, bool)`.
- `PermissionType` enum: `enroll:autodiscovery_admin`, `enroll:higher_upload_limit`,
  `enroll:ai1_datasets`, `enroll:asta_integration`.
- `/api/user/me` fetches the full profile from Auth0 `/userinfo`.
- `packages/autodiscovery_jobs/src/.../auth0.py` does Management-API lookups (email by id)
  for offline scripts (`send_completion_emails.py`, `export_users_csv.py`).
- Config is plain `os.environ.get(...)`: `AUTH0_DOMAIN`, `AUTH0_AUDIENCE`,
  `AUTH0_REQUIRED_PERMISSION`, `AUTH0_MGMT_*`, `DEV_MASQUERADE_USER`.

### Frontend (`ui/`, Next.js App Router)
- `ui/src/app/auth/Auth0Client.ts` — `@auth0/auth0-spa-js` client from `NEXT_PUBLIC_AUTH0_*`.
- `ui/src/app/contexts/Auth0Context.tsx` — `useAuth0()` context: `isAuthenticated`,
  `isLoading`, `user`, `loginWithRedirect`, `logout`, `getAccessToken`,
  `hasRequiredPermission`, `canExploreWithAsta`, `authError`.
- `ui/src/app/api/BaseApi.ts` — imports `auth0Client` directly; attaches
  `Authorization: Bearer <token>`; redirects to login on 401.
- Permissions are decoded client-side from the JWT in two places (`Auth0Context.tsx`,
  `metrics/layout.tsx`).
- Route gating is client-side via `isAuthenticated` / permission flags.

---

## Backend design

### 1. Normalized identity

```python
# api/utils/auth/models.py
@dataclass(frozen=True)
class AuthenticatedUser:
    sub: str                      # stable id, namespaced per provider
    permissions: list[str]        # e.g. ["enroll:autodiscovery_admin"]
    email: str | None = None
    name: str | None = None
    picture: str | None = None
    email_verified: bool | None = None

    def to_request_user(self) -> dict:
        """Back-compat dict shape that handlers already read via request.user.get(...)."""
        return {
            "sub": self.sub, "permissions": self.permissions, "email": self.email,
            "name": self.name, "picture": self.picture,
            "email_verified": self.email_verified,
        }
```

`request.user` stays a **dict with the same keys**, so none of the ~23 handler call
sites change. `sub` is namespaced per provider to keep GCS paths (`users/{sub}/...`)
collision-free and recognizable:
- auth0: `auth0|...`, `google-oauth2|...` (unchanged)
- password_file: `file|<username>`
- none: `local`

### 2. Provider interface

```python
# api/utils/auth/base.py
class NoCredentialsError(Exception): ...      # nothing presented
class InvalidCredentialsError(Exception): ... # presented but bad -> 401 w/ message

class AuthProvider(ABC):
    name: str

    @abstractmethod
    def authenticate(self, request) -> AuthenticatedUser:
        """Validate the request's credentials. Raise NoCredentialsError if none,
        InvalidCredentialsError if present-but-invalid."""

    def user_profile(self, request, user: AuthenticatedUser) -> dict:
        """Full profile for /api/user/me. Default: derive from `user`."""
        return user.to_request_user()

    def public_config(self) -> dict:
        """Non-secret descriptor the UI fetches to pick its UI mode."""
        return {"provider": self.name}
```

The three decorators stay as the **public API** and become thin wrappers that delegate to
the active provider. Their required-vs-optional semantics are preserved:

| Decorator | NoCredentials | Invalid | Authenticated |
|---|---|---|---|
| `requires_auth` / `requires_enrollment` | 401 | 401 | check perms, set `request.user` |
| `optional_enrollment` | `request.user = {}` | `request.user = {}` | set `request.user` |

`set_userid(...)` moves into the shared decorator path so it applies to every provider.
(The old Auth0-only `DEV_MASQUERADE_USER` debug override was dropped — it had fallen out of
use, and the `none` provider covers the "run as a fixed user" case.)

### 3. Activation / config

```python
# api/utils/auth/factory.py
def get_auth_provider() -> AuthProvider:   # cached singleton
    kind = os.environ.get("AUTH_PROVIDER", "auth0")
    return {
        "auth0": Auth0Provider,
        "password_file": PasswordFileProvider,
        "none": NoneProvider,
    }[kind].from_env()
```

New env var **`AUTH_PROVIDER`** (`auth0` default → no behavior change on existing deploys).
Each provider reads only its own settings via `from_env()`.

### 4. The three providers

**`Auth0Provider`** — lifts `verify_token` / JWKS / `/userinfo` out of `auth.py` verbatim.
`authenticate()` parses the `Bearer` header (NoCredentials if missing, Invalid on bad
token) and returns `AuthenticatedUser` from the JWT claims. `user_profile()` calls
`/userinfo`. No functional change.

**`NoneProvider`** — `authenticate()` *always* returns the fixed user and never raises, so
both required and optional decorators just work:

```python
AuthenticatedUser(
    sub="local",   # hardcoded fixed identity
    name="Local User", email="local@localhost", email_verified=True,
    permissions=ALL_PERMISSIONS,   # every PermissionType value -> all features unlocked
)
```

**`PasswordFileProvider`** — the substantive one.

- **Store**: a JSON file (atomic write, structured so we can carry email/name/permissions),
  schema versioned:
  ```json
  {
    "version": 1,
    "users": {
      "alice": {
        "password_hash": "<bcrypt>",
        "email": "alice@example.org",
        "name": "Alice",
        "permissions": ["enroll:autodiscovery_admin"],
        "disabled": false
      }
    }
  }
  ```
- **Login**: new endpoint `POST /api/auth/login {username, password}`. Validates against
  the file (password verified **only here**), then issues a short-lived **HS256 JWT**
  signed with `AUTH_SESSION_SECRET` containing `{sub:"file|alice", name, email}`.
  Returns `{token, expires_at}`. PyJWT is already a dependency.
- **Per-request**: `authenticate()` verifies the token signature, then **re-reads the
  file** to confirm the user still exists and is not `disabled`, and loads *current*
  `permissions` from the file (not from the token). This is what satisfies "consult the
  file on every check": new users can log in immediately, permission/enable changes take
  effect on the next request, deleted users are locked out on their next request — all
  with no web-stack restart. (The file read is cheap; we can add an mtime-guarded cache
  later if needed, but default to reading each request for correctness.)
- **Hashing**: `bcrypt` (recommended; robust, salted). Stdlib `hashlib.scrypt` is a
  zero-new-dependency fallback. Decision flagged below.
- Shared store/hashing logic lives in `api/utils/auth/password_store.py`, imported by both
  the provider and the CLI so the format/hash never drift.

### 5. Admin CLI (`password_file` administration)

A console entry point (added to `api/pyproject.toml`), e.g. `autodiscovery-auth`:

```
autodiscovery-auth --file $AUTH_PASSWORD_FILE useradd alice --email a@x.org --name Alice \
                   --permission enroll:autodiscovery_admin   # prompts for password
autodiscovery-auth passwd alice
autodiscovery-auth usermod alice --add-permission enroll:higher_upload_limit
autodiscovery-auth disable alice            # / enable
autodiscovery-auth userdel alice
autodiscovery-auth list
```

Writes are atomic (temp file + `os.replace`) with an advisory file lock to avoid clobbering
concurrent edits. Because the backend re-reads on every check, CLI changes are live
immediately. The CLI ships in the same image so an operator can `kubectl exec` and run it
against the mounted file.

### 6. Auth0 Management-API usage in offline scripts

`packages/.../auth0.py` (email-by-id for completion emails / CSV export) is Auth0-specific
and runs **offline**, not in the request path. Out of scope for swapping; left as-is. If a
`password_file` deployment needs those scripts, they can read the same file via
`password_store`. Noted, not built now.

### 7. New / changed env

| Var | Provider | Notes |
|---|---|---|
| `AUTH_PROVIDER` | all | `auth0` (default) \| `password_file` \| `none` |
| `AUTH_PASSWORD_FILE` | password_file | path to mounted JSON |
| `AUTH_SESSION_SECRET` | password_file | HS256 signing secret |
| `AUTH_SESSION_TTL` | password_file | token lifetime (default e.g. 12h) |
| `AUTH0_*` | auth0 | unchanged |

(The `none` provider needs no configuration — its `local` identity is hardcoded.)

---

## Frontend design

### 1. Provider-agnostic context

Replace the Auth0-specific context with a generic `useAuth()` keeping the **same shape**
(so `AuthButton`, route layouts, `BaseApi`, `ViewerRunsContext`, Heap loader, etc. barely
change). `useAuth0` is kept as a thin alias during migration.

```ts
interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: AuthUser | undefined;           // {sub, name, email, picture}
  permissions: string[];                // NEW: centralized
  hasPermission: (p: string) => boolean;// NEW: replaces ad-hoc JWT decodes
  login: (creds?: {username: string; password: string}) => Promise<void>;
  logout: () => void;
  getAccessToken: () => Promise<string | null>;
  hasRequiredPermission: boolean;
  canExploreWithAsta: boolean;          // = hasPermission('enroll:asta_integration')
  authError: string | null;
}
```

The two client-side JWT-decode sites (`Auth0Context`, `metrics/layout`) are refactored to
read `permissions` / `hasPermission(...)` from context, so they work identically for any
provider.

### 2. Runtime provider selection

A top-level `<AuthProvider>` fetches **`GET /api/auth/config`** on boot and renders the
matching implementation:

- `Auth0AuthProvider` — current `@auth0/auth0-spa-js` logic; `login()` = redirect;
  `getAccessToken()` = `getTokenSilently()`; `permissions` from decoded JWT.
- `PasswordFileAuthProvider` — renders a username/password **login form**; `login(creds)`
  → `POST /api/auth/login`, stores token (localStorage); `getAccessToken()` returns the
  stored token; `permissions` decoded from our HS256 JWT; logout clears storage.
- `NoneAuthProvider` — immediately `isAuthenticated=true` as the local user; `login`/
  `logout` are no-ops; `getAccessToken()` returns `null`; `permissions` = all. No login UI.

This makes the active mode a **runtime** decision — one build serves all three. (Auth0's
`NEXT_PUBLIC_AUTH0_*` values can be served from `/api/auth/config` too, so they no longer
have to be baked at build time. Decision flagged below.)

### 3. Decoupling `BaseApi` from Auth0

`BaseApi` no longer imports `auth0Client`. Introduce a tiny module-level bridge the active
provider populates:

```ts
// ui/src/app/auth/authBridge.ts
export const authBridge = {
  getToken: async (): Promise<string | null> => null,  // set by active provider
  getUserId: async (): Promise<string | null> => null,
  onUnauthorized: () => {},                              // 401 handler (redirect / clear)
};
```

`createDefaultHeaders()` calls `authBridge.getToken()`; the 401 path calls
`authBridge.onUnauthorized()`. For `none`, `getToken` returns `null` → no `Authorization`
header, and the backend `NoneProvider` ignores it anyway.

### 4. UI behavior per provider

| Concern | auth0 | password_file | none |
|---|---|---|---|
| Login affordance | "Sign in" → redirect | login form (modal/page) | none (always in) |
| `AuthButton` | Sign in/out | Sign in/out (form) | hidden |
| Token transport | bearer (silent) | bearer (stored) | none |
| Permissions source | JWT claims | JWT claims (file-derived at login) | all |

---

## Rollout

1. Backend: extract `auth.py` into `auth/` (models, base, factory, providers) with the
   three decorators delegating — `auth0` path behavior-identical. Add `/api/auth/config`.
2. Backend: `password_store` + `PasswordFileProvider` + `/api/auth/login` + CLI.
3. Backend: `NoneProvider`.
4. Frontend: generic `useAuth()` + `authBridge`, refactor `BaseApi` and the two decode
   sites; `Auth0AuthProvider` parity.
5. Frontend: `PasswordFileAuthProvider` (+ login form) and `NoneAuthProvider`.
6. Docs + `.env.example`; k8s manifests for mounting the password file.

Each step keeps `auth0` working, so we can land incrementally.

## Decisions (locked)
- **Password-file session**: signed **HS256 token** issued at login (mirrors the existing
  Bearer flow); file re-read every request to validate user + load permissions.
- **Password hashing**: **bcrypt**.
- **UI config**: Auth0 settings served from runtime **`GET /api/auth/config`** — true
  single-build swap.
- **CLI home**: a script at `api/scripts/auth_admin.py` (the API runs from `/api` via
  gunicorn and is not an installed package), run with `uv run api/scripts/auth_admin.py ...`.
- **Scope**: implement all steps (backend + frontend), keeping `auth0` working at each step.

---

## As built

### Backend file layout
```
api/utils/auth/                 # package (replaces the old auth.py module)
  __init__.py                   # re-exports: requires_auth, requires_enrollment,
                                #   optional_enrollment, PermissionType, get_auth_provider, ...
  models.py                     # AuthenticatedUser
  base.py                       # AuthProvider ABC + AuthError/NoCredentials/Invalid/Config
  permissions.py                # PermissionType, ALL_PERMISSIONS
  decorators.py                 # the three decorators, delegating to the active provider
  factory.py                    # get_auth_provider() (cached) / reset_auth_provider()
  password_store.py             # bcrypt + atomic JSON store (shared with the CLI)
  providers/
    _bearer.py                  # shared Authorization-header parsing
    auth0.py                    # Auth0Provider (verify_token/JWKS/userinfo lifted over)
    password_file.py            # PasswordFileProvider (HS256 session, re-reads file/request)
    none.py                     # NoneProvider (fixed "local" user, all permissions)
api/auth/auth_api.py            # blueprint: GET /api/auth/config, POST /api/auth/login
api/scripts/auth_admin.py       # password_file admin CLI
```
`request.user` remains the same dict; `request.auth_user` additionally carries the
typed `AuthenticatedUser` (used by `/api/user/me` → `provider.user_profile`).

### Frontend file layout
```
ui/src/app/auth/authBridge.ts   # singleton so BaseApi has no Auth0 dependency
ui/src/app/auth/authConfig.ts   # fetchAuthConfig() + decodeJwtPayload() + fallbacks
ui/src/app/auth/Auth0Client.ts  # createAuth0Client(config) factory (was a module singleton)
ui/src/app/contexts/Auth0Context.tsx  # generic context + runtime selector + 3 impls
ui/src/app/components/LoginDialog.tsx  # username/password modal (password_file)
```
The consumer hook stays `useAuth0()` (alias `useAuth`) and the provider export stays
`Auth0Provider`, so the ~20 existing consumers and `ClientProviders` are unchanged. The
context gained `permissions`, `hasPermission()`, `login(creds?)`, and `provider`. The
interactive trigger `loginWithRedirect` is now generic (Auth0 redirect / open the
password form / no-op for `none`), so `AuthButton` and `IntroBox` did not change their
call. `AuthButton` hides itself under the `none` provider.

### Operating the password_file provider
```bash
# Configure
AUTH_PROVIDER=password_file
AUTH_PASSWORD_FILE=/secrets/users.json
AUTH_SESSION_SECRET=<random, >= 32 bytes>   # openssl rand -hex 32

# Administer (changes are live; no web-stack restart)
uv run api/scripts/auth_admin.py useradd alice --email a@x.org --name Alice \
    --permission enroll:autodiscovery_admin
uv run api/scripts/auth_admin.py passwd alice
uv run api/scripts/auth_admin.py usermod alice --add-permission enroll:higher_upload_limit
uv run api/scripts/auth_admin.py disable alice   # / enable / userdel
uv run api/scripts/auth_admin.py list
```
The file is mounted read-only into the API container (see the commented bind mount in
`docker-compose.yaml`); the CLI runs wherever it can write the file (e.g. `kubectl exec`).

### Deltas from the proposal
- The consumer-facing hook kept the name `useAuth0` (alias `useAuth`) instead of being
  renamed, to avoid churning ~20 files; the implementation underneath is provider-agnostic.
- `loginWithRedirect` was repurposed as the generic interactive-login trigger rather than
  adding a new `promptLogin`, so existing call sites needed no change.
- The password-file session token also carries `permissions` (for client-side UI gating
  only); the backend still re-reads the file for every authoritative check.
- No k8s manifests exist in-repo (deploy is via Skiff/Cloud Run), so wiring is limited to
  `.env.example` and `docker-compose.yaml`; mount the store file the same way as the GCP key.
