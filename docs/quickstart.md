# Quick start

Run the whole AutoDiscovery stack -- API, UI, and a container per run -- on one
machine with nothing but Docker and an account with a model provider.
Persistence and authentication default to vendor-free local settings, so the
one thing you must configure is **which model to use**. There is no default
model: `make dev` refuses to start until you choose one.

## 1. Prerequisites

- [Docker](https://www.docker.com/get-started) (Docker Desktop or Engine with Compose v2)
- An API key or account with one of the providers below

## 2. Create `.env` with your model

Create a file named `.env` at the repository root. It needs
`AUTODISCOVERY_MODEL` -- the model every run uses, as litellm's
`<provider>/<model>` -- plus that provider's own variables. Copy one of the
examples below; nothing else is required.

### OpenAI

```sh
AUTODISCOVERY_MODEL=openai/gpt-5.4-mini
OPENAI_API_KEY=sk-...
```

### Anthropic

```sh
AUTODISCOVERY_MODEL=anthropic/claude-sonnet-5
ANTHROPIC_API_KEY=sk-ant-...
```

Anthropic offers no embedding models. The stack never needs one; only the
standalone CLI's `--dedupe` does, and for that set
`AUTODISCOVERY_EMBEDDING_MODEL` to another provider's embedding model along
with its key.

### Azure OpenAI

```sh
AUTODISCOVERY_MODEL=azure/gpt-5.4-mini
AZURE_API_KEY=...
AZURE_API_BASE=https://<your-resource>.openai.azure.com
# Optional. litellm uses a current API version when unset.
# AZURE_API_VERSION=2025-04-01-preview
```

The part after `azure/` is your **deployment name**, not the model name. Name
deployments after the model they serve (a deployment called `gpt-5.4-mini`
serving `gpt-5.4-mini`) so the startup checks can tell reasoning models -- which
reject a temperature -- from the rest.

### Google (Vertex AI)

```sh
AUTODISCOVERY_MODEL=vertex_ai/gemini-3.7-flash
VERTEXAI_PROJECT=your-gcp-project
VERTEXAI_LOCATION=global
# A service-account key with Vertex AI access. Use an ABSOLUTE path: the key
# is bind-mounted into each job container.
GOOGLE_APPLICATION_CREDENTIALS=/Users/you/secrets/gcp-key.json
```

`VERTEXAI_LOCATION=global` serves current Gemini models; litellm's own fallback
region does not.

### GitHub Copilot

Copilot authenticates with a GitHub OAuth token that litellm obtains through a
device-code login and caches on disk. Log in once, on the host, from an
interactive terminal:

```sh
uv run --all-packages python -c "import litellm; litellm.completion(model='github_copilot/gpt-4.1', messages=[{'role': 'user', 'content': 'hi'}])"
```

Enter the printed code at github.com when prompted. The token lands in
`~/.config/litellm/github_copilot`; point the stack at that directory:

```sh
AUTODISCOVERY_MODEL=github_copilot/claude-haiku-4.5
# The directory litellm cached the token in. Use an ABSOLUTE path (no ~): it
# is bind-mounted into each job container.
GITHUB_COPILOT_TOKEN_DIR=/Users/you/.config/litellm/github_copilot
```

Which models an account can call depends on its Copilot plan; the job checks
the chosen one against your account's catalog at startup.

## 3. Start the stack

```sh
make dev
```

The first start builds the images, which takes a few minutes. Then open
<http://localhost:8080>, upload a dataset, and start a run.

If `make dev` stops with `no model chosen`, `.env` is missing
`AUTODISCOVERY_MODEL`. If the `api` container exits right after starting, its
log names the variable that is missing for your provider:

```sh
docker compose logs api | tail -20
```

## What you are running

With only the lines above, the stack is:

- **Persistence** in `./data` on your machine (`STORAGE_BACKEND=local`).
- **Jobs** as local Docker containers (`JOB_BACKEND=docker`), one per run. The
  API forwards your provider's variables -- and bind-mounts the Google key or
  Copilot token directory -- into each job container.
- **Generated code** in an isolated subprocess inside the job container
  (`CODE_EXECUTION_BACKEND=process`).
- **No authentication** (`AUTH_PROVIDER=none`): every request is one fixed
  local user. This is a single-user setup; see
  [Authentication](authentication.md) before exposing it to others.

Every other variable in [`.env.example`](https://github.com/allenai/asta-autodiscovery/blob/main/.env.example)
is optional or belongs to an alternative backend. See
[Configuration](configuration.md) for the full reference.

## Optional: different models per role

The engine uses a model in four roles. All default to `AUTODISCOVERY_MODEL`
except embeddings, which are only used by `--dedupe`:

| Variable | Role |
| --- | --- |
| `AUTODISCOVERY_BELIEF_MODEL` | Belief elicitation (prior/posterior sampling). |
| `AUTODISCOVERY_VISION_MODEL` | Interpreting plots the generated code produces. Must accept image input. |
| `AUTODISCOVERY_EMBEDDING_MODEL` | Hypothesis deduplication (standalone CLI `--dedupe` only). |

Roles may use different providers; set each provider's variables.

## Other providers and deployments

Any [litellm provider](https://docs.litellm.ai/docs/providers) can be named in
`AUTODISCOVERY_MODEL`. The five above are the ones this project documents and
checks at startup, and whose variables the docker job backend forwards into
job containers. For another provider, add its variables to the forwarding list
in `packages/autodiscovery_jobs/src/autodiscovery_jobs/backends/docker.py`, or
run jobs on Cloud Run (`JOB_BACKEND=gcp`), where the job carries its own
secrets.

Deployed services set `AUTODISCOVERY_MODEL` on the API the same way; the API
passes the choice to every job as explicit `--model` flags, so the job image
needs no model configuration of its own.
