# Changelog

All notable changes to the published packages — [`asta-autodiscovery`][pypi]
(the `auto-discovery` CLI), `asta-autodiscovery-modal`, and
`asta-code-execution` — are recorded here. This project follows
[Semantic Versioning](https://semver.org/).

[pypi]: https://pypi.org/project/asta-autodiscovery/

## Unreleased

### Fixed: Vertex AI configuration ([#78])

Two 1.0.0 regressions, both on the path a first run takes, since the default
models are Vertex.

- **`VERTEX_LOCATION` unset means `global` again.** 1.0.0 passed the location to
  litellm only when the variable happened to be set, so unset took litellm's own
  default of `us-central1` — which does not serve `vertex_ai/gemini-3.7-flash`.
  The 404 that came back read as if the model did not exist. `global` is now
  passed when nothing is configured, matching what the docs have said all along.
- **A missing `VERTEX_PROJECT_ID` fails at startup again**, with a message naming
  the variable, rather than letting litellm fall back to the Application Default
  Credentials project and 404 on a project you never chose.

litellm's own `VERTEXAI_PROJECT`/`VERTEX_PROJECT` and `VERTEXAI_LOCATION` are
also read, at lower precedence, so a deployment configured litellm's way is
neither rejected by the new check nor overridden by the default location.

A model-flag mistake now exits with a one-line error instead of a traceback.
That covers the `<provider>/<model>` prefix error every 0.2.x command line hits
on upgrade.

[#78]: https://github.com/allenai/asta-autodiscovery/issues/78

## 1.0.0

First release of the litellm-based model layer ([#67], [#68]). Every model call
in the CLI now goes through [litellm](https://docs.litellm.ai/), which owns
provider routing, credentials, request shaping and wire formats. The
user-visible consequence is that **model flags now name their provider**, and
**Vertex AI authenticates through Application Default Credentials only**.

Upgrading requires editing your command line. Start with
**[Standalone CLI → Selecting models](docs/autodiscovery/standalone.md#selecting-models)**;
everything below is the summary.

### Breaking: model flags require a `<provider>/<model>` prefix

`--model`, `--belief_model`, `--vision_model` and `--embedding_model` now take
[litellm's](https://docs.litellm.ai/docs/providers) qualified naming, with
snake_case provider slugs. A bare model name is rejected at startup.

```sh
# 0.2.x
auto-discovery --model gemini-3.1-pro-preview ...

# 1.0.0
auto-discovery --model vertex_ai/gemini-3.7-flash ...
```

The prefix is required rather than inferred. A bare name is genuinely
ambiguous — `claude-haiku-4.5` is Anthropic direct or GitHub Copilot depending
on who you ask — and resolving one means asking litellm, which triggers
device-flow auth for some providers. An unqualified name fails immediately with
the qualified form to use:

```
'gemini-3.7-flash' is missing a provider. Model names are litellm-qualified
as <provider>/<model>, e.g. vertex_ai/gemini-3.7-flash or openai/gemini-3.7-flash.
```

`google/<model>` is also rejected. That was Vertex's OpenAI-compatible wire
prefix, never a litellm provider slug — use `vertex_ai/<model>`.

Any of litellm's ~149 providers may be named; there is no allow-list. The three
this project configures credentials for and tests are `vertex_ai`, `openai` and
`github_copilot`. Naming another means supplying its credentials yourself, per
litellm's env-var conventions.

Because the provider travels with each flag, one run can mix providers:

```sh
auto-discovery \
    --model github_copilot/claude-haiku-4.5 \
    --vision_model vertex_ai/gemini-3.7-flash \
    ...
```

### Breaking: Vertex AI requires Application Default Credentials

Raw bearer tokens are gone. `VERTEX_ACCESS_TOKEN`, `GOOGLE_OAUTH_ACCESS_TOKEN`
and `VERTEX_OPENAI_BASE_URL` are no longer read; litellm's `vertex_ai`
transport authenticates via `google.auth`. Use either a service-account key or
local user credentials:

```sh
export VERTEX_PROJECT_ID=your-gcp-project
export VERTEX_LOCATION=global                          # optional, defaults to global

export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json  # service account
# ...or, for local development:
gcloud auth application-default login
```

`VERTEX_PROJECT_ID` and `VERTEX_LOCATION` keep working — they are mapped onto
litellm's `vertex_project` / `vertex_location` — so existing deployment config
needs no change beyond credentials. `OPENAI_API_KEY` is unchanged.

### Breaking: default models changed

| Flag | 0.2.x default | 1.0.0 default |
| --- | --- | --- |
| `--model` | `gemini-3.1-pro-preview` | `vertex_ai/gemini-3.7-flash` |
| `--belief_model` | `gemini-3-flash-preview` | `vertex_ai/gemini-3.7-flash` |
| `--vision_model` | `gemini-3.1-pro-preview` | `vertex_ai/gemini-3.7-flash` |
| `--embedding_model` | (not a flag; hardcoded `text-embedding-3-large`) | `openai/text-embedding-3-large` |

Runs that relied on the defaults will now use Gemini 3.7 Flash ([#71]).
Expect different cost, latency and output than the 3.1 Pro preview default.

### Added: GitHub Copilot as a provider

Name it with the `github_copilot/` prefix; no extra install, litellm speaks it
natively. On an interactive terminal litellm runs GitHub's device-code login on
first use and caches the token itself. For non-interactive runs, pre-seed it:

```sh
export GITHUB_COPILOT_TOKEN_DIR=/path/to/dir   # default ~/.config/litellm/github_copilot
# the directory must contain a file named `access-token` holding a GitHub OAuth token
```

litellm does no TTY detection, so a headless run with no cached token prints a
device code and blocks for roughly three minutes before failing rather than
erroring immediately.

Copilot currently requires the `process` or `modal` execution backend — the
`local` backend's generated image-analysis code is tied to an OpenAI client.

### Added: `--embedding_model`, `--embedding_dimensions`, `--dedupe`

Deduplication embeddings were previously hardwired to OpenAI
`text-embedding-3-large` through a direct OpenAI client. They are now a normal
model flag, so dedupe can run on any litellm embedding provider:

```sh
auto-discovery --dedupe \
    --embedding_model github_copilot/text-embedding-3-small \
    --embedding_dimensions 1536 \
    ...
```

`--dedupe` was previously hardcoded off in the `auto-discovery` entry point and
is now selectable (`--dedupe` / `--no-dedupe`, default off).

Note that `text-embedding-3-small` at 1536 dimensions is not numerically
identical to the `text-embedding-3-large` default; keep the default when exact
embedding geometry matters.

### Added: model flags are validated before the first model call

Every flag is checked at startup against litellm's offline registry: the vision
model must accept image input, the embedding model must be an embedding model,
and chat flags must be chat models. A model litellm has not mapped yet is a
warning, not an error — providers ship models faster than litellm maps them.

For `github_copilot/` the check queries Copilot's own `/models` endpoint
instead, since litellm's static catalog is inaccurate in both directions for
Copilot: it lists models an account cannot call and omits ones it can. The live
list is read from litellm's cached API key and never triggers a login; with no
usable cached key, validation falls back to the registry with a warning
([#68]).

### Changed: per-model parameter handling

- `temperature` is dropped, with a warning, for models that reject it. This was
  a hardcoded `o4-mini` substring check; it now consults litellm's per-model
  reasoning support.
- `reasoning_effort=minimal` is mapped to `low` only for OpenAI models that
  litellm reports cannot take it, instead of for every non-Gemini model.
- Per-request sample caps (`n`) are applied per provider: 5 for `vertex_ai`, 8
  for `github_copilot`, 8 for OpenAI reasoning models. Requests above the cap
  are batched rather than failing.
- Parameters a model does not support are stripped by litellm
  (`drop_params`) rather than by hand at each call site.

Retry behavior is unchanged: this package's own truncated exponential backoff
still applies, configured by `LLM_RETRY_MAX_RETRIES`,
`LLM_RETRY_INITIAL_DELAY_SECONDS` and `LLM_RETRY_MAX_DELAY_SECONDS`. litellm's
own `num_retries` is pinned to 0 so there is one retry layer, not two nested
ones.

### Fixed

- Local dataset paths are resolved to their real file before symlinking into
  the work directory, and a broken existing symlink no longer silently wins
  over the resolved source.
- Directory datasets skip dotfiles at every level, not just the top.

### Packaging

- Added `litellm>=1.97.0,<2` and `google-auth`.
- Dropped `google-cloud-aiplatform` and the `ag2[openai,gemini]` extras
  (`ag2==0.10` is still required); provider SDKs are litellm's business now.
- `LICENSE` is bundled in each published distribution.

---

## Library-level changes

These affect code that imports these packages as a Python library. If you use
`asta-autodiscovery` only for the `auto-discovery` CLI, nothing below applies.

### Removed modules

- `autodiscovery.vertex_client` and `autodiscovery.vertex_config` — Vertex is
  reached through litellm, so there is no bespoke OpenAI-compatible client,
  base-URL builder or credentials refresher.
- `autodiscovery.log_utils` — dead since it was written.
- From `autodiscovery.utils`: `is_gemini_model`, `is_reasoning_model`,
  `normalize_vertex_model_name`, `max_n_for_model`, `normalize_reasoning_effort`,
  `get_vertex_access_token`, `get_openai_client_for_model`. Their replacements
  live in the new `autodiscovery.llm` module (`provider_of`, `model_info`,
  `accepts_temperature`, `max_n`, `normalize_reasoning_effort`, `validate`,
  `complete`, `embed`).
- `autodiscovery.agents.get_openai_config` is replaced by
  `get_llm_config`, and AG2 now talks to models through a `LiteLLMAG2Client`
  custom client rather than a patched `OpenAIWrapper`.

### Required and keyword-only model arguments

Functions no longer default to a model name, since no default can be
provider-correct. Model arguments are now required, and several are keyword-only:

- `run.run_mcts(...)` — `model_name`, `belief_model_name`, `vision_model` and
  `embedding_model` are required keyword arguments.
- `utils.query_llm(...)` — `model` is required; the `client` parameter is gone.
- `deduplication.dedupe(...)` — `model` and `embedding_model` are required
  keyword arguments.
- `deduplication.get_embedding(...)` — `model` is required; `client` is gone,
  replaced by an optional `dimensions`.
- `deduplication.get_llm_merge_decision(...)` — `model` is a required keyword
  argument.
- `agents.VisionHandler(vision_model=...)` — required.
- `run.save_nodes(...)` — takes `embedding_model` and `embedding_dimensions`.

Passing a bare model name to any of these raises
`autodiscovery.llm.ModelError`.

### `agent_usage_mode="per_response"`

No longer depends on monkey-patching AG2's `OpenAIWrapper`, so it can no longer
fail at startup with *"the patch could not be applied"*. The custom litellm
client records each response as it is produced.

[#67]: https://github.com/allenai/asta-autodiscovery/pull/67
[#68]: https://github.com/allenai/asta-autodiscovery/pull/68
[#71]: https://github.com/allenai/asta-autodiscovery/pull/71

## 0.2.2 and earlier

Not recorded here. See the
[commit history](https://github.com/allenai/asta-autodiscovery/commits/main).
