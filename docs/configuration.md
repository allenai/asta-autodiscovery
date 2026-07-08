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

## Authentication (Auth0)

The API validates Auth0-issued JWTs; the UI drives the Auth0 login flow.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `AUTH0_DOMAIN` | Yes | *(none)* | Auth0 tenant domain used to validate tokens and look up user info. `docker-compose.yaml` sets this to `auth0.allenai.org` for local dev. |
| `AUTH0_AUDIENCE` | Yes | *(none)* | Expected audience (API identifier) for incoming access tokens. Compose default: `https://asta-core.allen.ai`. |
| `AUTH0_REQUIRED_PERMISSION` | No | *(unset — any authenticated user)* | If set, users must have this Auth0 permission to access the API. If empty/unset, any authenticated user is allowed. Example: `enroll:autodiscovery_v0`. |
| `DEV_MASQUERADE_USER` | No | *(unset)* | **Development only.** Forces the app to treat all requests as coming from the given user id (e.g. `google-oauth2|111...`). Leave unset outside local dev. |

## Google Cloud & storage

Job data, run metadata, results, and user profiles are stored in Google Cloud Storage.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `GCP_PROJECT` | Yes | *(none)* | Google Cloud project id. Required for GCS and job execution. |
| `GCS_BUCKET` | No | `autodiscovery` | Name of the bucket holding run data/results/metadata. `AUTODISCOVERY_BUCKET` is accepted as an alias if `GCS_BUCKET` is unset. |
| `GCP_REGION` | No | `us-west1` | Region used for job execution. |
| `GOOGLE_APPLICATION_CREDENTIALS` | Yes | *(none)* | Path to the Google service-account key file used by the Google client libraries. In local dev this is bind-mounted into the container. |
| `GOOGLE_ACCESS_KEY_ID` | No | *(none)* | HMAC access key id, used when generating presigned URLs for direct browser uploads to GCS. |
| `GOOGLE_ACCESS_KEY_SECRET` | No | *(none)* | HMAC secret paired with `GOOGLE_ACCESS_KEY_ID`. |
| `GCS_ENDPOINT_URL` | No | `https://storage.googleapis.com` | Storage endpoint the Modal sandbox uses to read dataset files. Override to point at an alternative/compatible endpoint. |

## Job execution (Cloud Run)

AutoDiscovery runs are executed as Google Cloud Run job executions.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `CLOUDRUN_JOB_NAME` | No | `autodiscovery-job` | Name of the Cloud Run job to execute. Compose sets `autodiscovery-job-dev` for local dev. |

## Modal (code-execution sandbox)

AutoDiscovery runs execute generated code inside Modal sandboxes.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `MODAL_TOKEN_ID` | Yes | *(none)* | Modal API token id. |
| `MODAL_TOKEN_SECRET` | Yes | *(none)* | Modal API token secret. |
| `MODAL_ENVIRONMENT` | Yes | *(none)* | Modal environment name to run sandboxes in. |
| `MODAL_IMAGE_BUILDER_VERSION` | No | *(Modal default)* | Pins the Modal image builder version used to build sandbox images. |
| `MODAL_APP_NAME` | No | `asta-autodiscovery` | Modal app name the sandboxes are associated with. |
| `MODAL_BUCKET_SECRET` | No | `example-bucket-secret` | Name of the Modal secret holding the bucket credentials the sandbox uses to mount dataset files. |

## LLM providers

Model access for the discovery agents.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` | Conditional | *(none)* | OpenAI API key. Required when using OpenAI models. |
| `VERTEX_PROJECT_ID` | Conditional | *(none)* | Google Vertex AI project id. Required when using Vertex-backed models. |
| `VERTEX_LOCATION` | No | `global` | Vertex AI location/region. |
| `VERTEX_OPENAI_BASE_URL` | No | *(derived)* | Overrides the base URL for the Vertex OpenAI-compatible endpoint. When unset it is derived from the project/location. |
| `VERTEX_ACCESS_TOKEN` | Conditional | *(none)* | OAuth bearer token for Vertex. `GOOGLE_OAUTH_ACCESS_TOKEN` is accepted as a fallback. |
| `GOOGLE_OAUTH_ACCESS_TOKEN` | No | *(none)* | Fallback OAuth token used for Vertex when `VERTEX_ACCESS_TOKEN` is not set. |
| `ASTA_AGENTS_MODEL` | No | `openai/gpt-5-mini` | Model used by the `agents` package (LiteLLM model string). |

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

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `ASTA_BASE_URL` | No | `https://asta.allen.ai` | Base URL used to build Asta chat links returned to the UI. |
| `ASTA_CONTEXT_SERVICE_URL` | No | *(empty — feature disabled)* | URL of the context service that stores handoff artifacts and metadata. |
| `ASTA_CONTEXT_SERVICE_API_KEY` | No | *(empty)* | API key for the context service. |
| `ASTA_BUCKET` | No | `example-workspaces-project` | Bucket the handoff copies dataset files into for Asta to load. |

## Frontend (UI)

Read by the Next.js frontend. `NEXT_PUBLIC_*` variables are compiled into the browser bundle and
are **not secret**.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `NEXT_PUBLIC_AUTH0_DOMAIN` | No | `auth0.allenai.org` | Auth0 tenant domain for the browser login flow. |
| `NEXT_PUBLIC_AUTH0_CLIENT_ID` | No | *(built-in public client id)* | Public Auth0 application (client) id for the SPA. Public by design. |
| `NEXT_PUBLIC_AUTH0_AUDIENCE` | No | `https://asta-core.allen.ai` | Auth0 API audience requested by the browser. |
| `NEXT_PUBLIC_AUTH0_REQUIRED_PERMISSION` | No | *(unset)* | If set, the UI expects this permission on the logged-in user. |
| `API_ORIGIN` | No | `http://api:8000` | Origin the UI's server-side actions use to reach the API. |
| `NODE_ENV` | No | `development` | Standard Node environment (`development` / `production`); influences build behavior and analytics loading. |

### Testing / CI (UI)

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `E2E_BASE_URL` | No | `http://localhost:8080` | Base URL Playwright end-to-end tests target. |
| `CI` | No | *(unset)* | When set, Playwright enables CI behavior (retries, single worker, `forbidOnly`). |
