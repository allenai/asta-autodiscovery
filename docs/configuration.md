# Configuration

AutoDiscovery is configured through **environment variables**. This page documents every
variable the application reads, grouped by the concern it configures, along with whether it is
required and its default.

## How configuration is supplied

- **Local development** (`docker compose`): variables are read from a `.env` file at the repo
  root. Copy [`.env.example`](https://github.com/allenai/asta-autodiscovery/blob/main/.env.example)
  to `.env` and fill in the values. The `api` service loads the whole `.env` file; a curated
  subset is also passed explicitly in `docker-compose.yaml`.
- **Deployed services**: variables (and secrets) are injected into the container environment by
  the deployment platform.
- **The frontend** (`ui`, Next.js) reads its own set of variables at build/run time. Variables
  prefixed with `NEXT_PUBLIC_` are embedded in the browser bundle and are therefore **not
  secret**.

Unless noted otherwise, "Default" is the value used by the code when the variable is unset. A
value of *(required)* means the relevant feature fails or is disabled when the variable is
missing.

---

## Core service

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `LOG_LEVEL` | No | `INFO` | Python logging level for the API (e.g. `DEBUG`, `INFO`, `WARNING`). |
| `LOG_FORMAT` | No | *(plain)* | When set to `google:json`, logs are emitted as structured JSON that Google Cloud can parse. Any other value (or unset) uses plain logging. |

The API is served by gunicorn bound to `0.0.0.0:8000`; the port is fixed in the entrypoint
scripts (`api/start.sh`, `api/dev.sh`) and is not configurable via environment.

## Authentication

The backend is selected with `AUTH_PROVIDER` (`none` default, or `auth0` /
`password_file`). See [Authentication](authentication.md) for how to set up and operate
each provider; the table below is the variable reference.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `AUTH_PROVIDER` | No | `none` | Active auth backend: `none` (zero-config, unauthenticated local user), `auth0`, or `password_file`. Set explicitly for any real deployment. |
| `AUTH0_DOMAIN` | auth0 | *(none)* | Auth0 tenant domain used to validate tokens and look up user info. Compose default: `auth0.allenai.org`. |
| `AUTH0_AUDIENCE` | auth0 | *(none)* | Expected audience (API identifier) for incoming access tokens. Compose default: `https://asta-core.allen.ai`. |
| `AUTH0_CLIENT_ID` | No | *(none)* | Public SPA client id, served to the UI via `/api/auth/config`. |
| `AUTH_PASSWORD_DIR` | password_file | *(none)* | Directory holding the user store (fixed filename `passwddb.json`), managed with `api/scripts/auth_admin.py`. Mounted as a directory so edits are picked up live. |
| `AUTH_SESSION_SECRET` | password_file | *(none)* | Secret used to sign HS256 session tokens (use ≥ 32 random bytes). |
| `AUTH_SESSION_TTL` | No | `43200` | `password_file` session lifetime in seconds (default 12h). |

## Google Cloud & storage

Job data, run metadata, results, and user profiles are stored in Google Cloud Storage.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `GCP_PROJECT` | Yes | *(none)* | Google Cloud project id. Required for GCS and job execution. |
| `GCS_BUCKET` | No | `autodiscovery` | Name of the bucket holding run data/results/metadata. `AUTODISCOVERY_BUCKET` is accepted as an alias if `GCS_BUCKET` is unset. |
| `GCP_REGION` | No | `us-west1` | Region used for job execution. |
| `GOOGLE_APPLICATION_CREDENTIALS` | Yes | *(none)* | Path to the Google service-account key file used by the Google client libraries. In local dev this is bind-mounted into the container. Use an **absolute** path when running the docker job backend (the default): the backend re-mounts this file into each job container and the host daemon needs an absolute bind source. |
| `GOOGLE_ACCESS_KEY_ID` | No | *(none)* | HMAC access key id, used when generating presigned URLs for direct browser uploads to GCS. |
| `GOOGLE_ACCESS_KEY_SECRET` | No | *(none)* | HMAC secret paired with `GOOGLE_ACCESS_KEY_ID`. |
| `GCS_ENDPOINT_URL` | No | `https://storage.googleapis.com` | Storage endpoint the Modal sandbox uses to read dataset files. Override to point at an alternative/compatible endpoint. |

## Job execution

Each AutoDiscovery run is launched by a swappable **job backend**, selected with `JOB_BACKEND`:

- `docker` (default) — runs the job as a local Docker container on the host daemon. Keeps the
  out-of-the-box experience infra-agnostic; intended for local development and
  single-user/on-prem deployments.
- `gcp` — runs the job as a Google Cloud Run job execution. Deployments that run jobs on Cloud
  Run must set `JOB_BACKEND=gcp` explicitly.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `JOB_BACKEND` | No | `docker` | Job backend: `docker` (local containers) or `gcp` (Cloud Run). |
| `AUTODISCOVERY_IMAGE` | docker | `autodiscovery:dev` | **docker backend.** Image the backend launches per job. Build it locally with `docker compose build autodiscovery`. |
| `CLOUDRUN_JOB_NAME` | No | `autodiscovery-job` | **gcp backend.** Name of the Cloud Run job to execute. Compose sets `autodiscovery-job-dev` for local dev. |

The docker backend bind-mounts the GCP key into each job container using the **host** path of
`GOOGLE_APPLICATION_CREDENTIALS` (compose forwards it internally as `GCP_KEY_HOST_PATH`), which is
why that variable must be an absolute path for the docker backend.

### Docker backend (default)

With the default backend, `docker compose up` launches each run as a local container. The compose
stack mounts the host Docker socket into the API so it can start those containers
(docker-out-of-docker). Build the job image once first:

```sh
docker compose build autodiscovery
docker compose up
```

The job container mounts its GCS data at `/mnt/gcs` itself via gcsfuse (triggered by
`GCSFUSE_BUCKET`, which the backend sets from `GCS_BUCKET`); on Cloud Run the platform provides
that mount instead. The docker backend scopes the mount to the run's own prefix
(`users/<uid>/jobs/<jid>`), so a job container never sees other users' data — see
[Code-execution backend](#code-execution-backend) for why that matters.

To run jobs on Cloud Run instead, set `JOB_BACKEND=gcp` (the Docker socket mount is then unused).

> **Security note.** The docker backend gives the API access to the host Docker socket, which is
> effectively root on the host. This is fine for local/single-user use, but for a shared,
> multi-user deployment (e.g. `AUTH_PROVIDER=password_file`) prefer `JOB_BACKEND=gcp`, where the
> API only holds scoped cloud credentials.

## Code-execution backend

The AD job runs the LLM-generated experiment code through a configurable executor, selected with
`CODE_EXECUTION_BACKEND` and forwarded to the job's `--backend` flag:

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `CODE_EXECUTION_BACKEND` | No | `process` | `process` (isolated subprocess in the job container), `local` (in-process, no isolation), or `modal` (remote sandbox). |

- `process` (default) — runs code in an isolated subprocess inside the job container, in a separate
  sandbox venv; per-cell package installs are discarded, and no state carries across cells. No cloud
  dependency (Modal is not required). Reads the dataset from the job's `/mnt/gcs` mount.
- `local` — runs code in-process with no isolation. Lowest overhead, least safe.
- `modal` — runs code in a remote Modal sandbox that mounts **only** the per-job data prefix,
  read-only. Requires the [Modal](#modal-code-execution-sandbox-backend) variables.

### Choosing a safe combination

`process`/`local` execute untrusted, generated code **inside the job container**, so that code can
read whatever GCS data the container mounts. `modal` instead runs it on a separate machine with only
the per-job data mounted read-only. Whether in-process execution is safe therefore depends on the
job backend (how the mount is scoped) and on whether the deployment is multi-user:

| Job backend | Code backend | Single user (`AUTH_PROVIDER=none`) | Multi-user (`auth0` / `password_file`) |
| --- | --- | --- | --- |
| `docker` | `process` / `local` | ✅ safe | ✅ safe — mount is scoped to the job's own prefix |
| `gcp` | `process` / `local` | ✅ safe | ⚠️ **unsafe** — Cloud Run mounts the whole bucket; executed code can read every user's data |
| `docker` / `gcp` | `modal` | ✅ safe | ✅ safe — scoped, read-only per-job data mount |

The unsafe combination arises because Cloud Run's GCS mount is fixed per job (it cannot be scoped
per execution), while the docker backend re-mounts only the current job's prefix each run. The API
logs a loud warning at startup for the unsafe combination; set `CODE_EXECUTION_BACKEND=modal` for
multi-user Cloud Run deployments.

> Within a single job, `process`/`local` mount the job's own data read-write (the run also writes its
> output there), so generated code could overwrite that job's own inputs. This is within-tenant only;
> `modal` mounts the data read-only.

## Modal (code-execution sandbox backend)

Used only when `CODE_EXECUTION_BACKEND=modal`. With the default `process` (or `local`) backend the
`MODAL_*` variables are unused.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `MODAL_TOKEN_ID` | modal | *(none)* | Modal API token id. |
| `MODAL_TOKEN_SECRET` | modal | *(none)* | Modal API token secret. |
| `MODAL_ENVIRONMENT` | modal | *(none)* | Modal environment name to run sandboxes in. |
| `MODAL_IMAGE_BUILDER_VERSION` | No | *(Modal default)* | Pins the Modal image builder version used to build sandbox images. |
| `MODAL_APP_NAME` | No | `asta-autodiscovery` | Modal app name the sandboxes are associated with. Created on demand if it doesn't exist. |
| `MODAL_BUCKET_SECRET` | modal | `example-bucket-secret` | Name of the Modal [secret](https://modal.com/docs/guide/secrets) holding the GCS credentials the sandbox uses to mount dataset files. The default is a **placeholder that does not exist** — you must set this to the name of a real secret in your `MODAL_ENVIRONMENT`, or every run fails at sandbox creation with `Secret '…' not found`. |

## LLM providers

Model access for the discovery agents.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` | Conditional | *(none)* | OpenAI API key. Required when using OpenAI models. |
| `VERTEX_PROJECT_ID` | Conditional | *(none)* | Google Vertex AI project id. Required when using Vertex-backed models. |
| `VERTEX_LOCATION` | No | `global` | Vertex AI location/region. |
| `GOOGLE_APPLICATION_CREDENTIALS` | Conditional | *(none)* | Service-account key for Vertex. Vertex uses Application Default Credentials; run `gcloud auth application-default login` instead for local development. |
| `GITHUB_COPILOT_TOKEN_DIR` | No | `~/.config/litellm/github_copilot` | Directory holding an `access-token` file with a GitHub OAuth token. Interactive runs obtain and cache this via device-code login; pre-seed it for non-interactive runs, which otherwise block on a device prompt. |
| `ASTA_AGENTS_MODEL` | No | `openai/gpt-5-mini` | Model used by the `agents` package (LiteLLM model string). |

`VERTEX_ACCESS_TOKEN`, `GOOGLE_OAUTH_ACCESS_TOKEN` and `VERTEX_OPENAI_BASE_URL`
are no longer read. Vertex traffic goes through litellm's Vertex client, which
authenticates with ADC and refreshes tokens itself, so a raw bearer token and a
hand-set OpenAI-compatible base URL no longer have a place.

### LLM retry / backoff

Controls the client-side retry behavior when LLM calls fail.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `LLM_RETRY_MAX_RETRIES` | No | `5` | Maximum number of retries per LLM call. |
| `LLM_RETRY_INITIAL_DELAY_SECONDS` | No | `1.0` | Initial backoff delay before the first retry. |
| `LLM_RETRY_MAX_DELAY_SECONDS` | No | `20.0` | Maximum backoff delay between retries. |

## Maintenance jobs (email & user lookup)

Used by the completion-email maintenance job to notify users when runs finish.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `SMTP_SERVER` | Yes* | *(none)* | Mail server hostname. Required to send completion emails. |
| `SENDER_EMAIL` | Yes* | *(none)* | From-address for outgoing email. Required to send completion emails. |
| `SMTP_PORT` | No | `25` | Mail server port. |
| `AUTH0_MGMT_DOMAIN` | Yes* | *(none)* | Auth0 tenant domain for the Management API, used to look up user email addresses. |
| `AUTH0_MGMT_CLIENT_ID` | Yes* | *(none)* | Auth0 Management API client id. |
| `AUTH0_MGMT_CLIENT_SECRET` | Yes* | *(none)* | Auth0 Management API client secret. |

<small>\* Required only for the email maintenance job; not needed to run the API or jobs.</small>

## Asta integration

Configures the "dig deeper" handoff that sends an experiment's context to Asta.

Both `ASTA_CONTEXT_SERVICE_URL` and `ASTA_CONTEXT_SERVICE_API_KEY` must be set to enable it. With
either missing the feature is off: the UI hides the "Continue exploring with Asta" entry points and
the API returns `503` from the handoff endpoint. The rest of the app is unaffected.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `AUTODISCOVERY_BASE_URL` | No | `https://autodiscovery.allen.ai` | Base URL of this app, used to build the AutoDiscovery run link included in the Asta handoff. |
| `ASTA_BASE_URL` | No | `https://asta.allen.ai` | Base URL used to build Asta chat links returned to the UI. |
| `ASTA_CONTEXT_SERVICE_URL` | No | *(empty — feature disabled)* | URL of the context service that stores handoff artifacts and metadata. |
| `ASTA_CONTEXT_SERVICE_API_KEY` | No | *(empty — feature disabled)* | API key for the context service. |
| `ASTA_BUCKET` | No | `example-workspaces-project` | Bucket the handoff copies dataset files into for Asta to load. |

## Frontend (UI)

Read by the Next.js frontend. `NEXT_PUBLIC_*` variables are compiled into the browser bundle and
are **not secret**.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `NEXT_PUBLIC_AUTH_PROVIDER` | No | `auth0` | Build-time fallback for the active auth provider (`auth0` / `password_file` / `none`) if `/api/auth/config` is unreachable. |
| `NEXT_PUBLIC_AUTH0_DOMAIN` | No | `auth0.allenai.org` | Auth0 tenant domain for the browser login flow. |
| `NEXT_PUBLIC_AUTH0_CLIENT_ID` | No | *(built-in public client id)* | Public Auth0 application (client) id for the SPA. Public by design. |
| `NEXT_PUBLIC_AUTH0_AUDIENCE` | No | `https://asta-core.allen.ai` | Auth0 API audience requested by the browser. |
| `API_ORIGIN` | No | `http://api:8000` | Origin the UI's server-side actions use to reach the API. |
| `NODE_ENV` | No | `development` | Standard Node environment (`development` / `production`); influences build behavior and analytics loading. |

The `NEXT_PUBLIC_AUTH*` values are build-time fallbacks; at runtime the UI prefers the
provider and settings served by `GET /api/auth/config`.

### Testing / CI (UI)

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `E2E_BASE_URL` | No | `http://localhost:8080` | Base URL Playwright end-to-end tests target. |
| `CI` | No | *(unset)* | When set, Playwright enables CI behavior (retries, single worker, `forbidOnly`). |
