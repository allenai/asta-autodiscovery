# Standalone CLI

The `asta-autodiscovery` package ships a console script, `auto-discovery`, that runs the
discovery engine end-to-end against a local dataset — no Cloud Run, GCS, or UI
required.

## Install from PyPI

```sh
pip install asta-autodiscovery
```

This pulls in `asta-autodiscovery-modal` (sandboxed code execution) and
`asta-code-execution` as transitive dependencies. Requires Python 3.13+.

## Selecting models

There is **no default model**. Choose one with `--model`, or set
`AUTODISCOVERY_MODEL` in the environment; a run with neither stops at startup
with `No model chosen`. `--belief_model` and `--vision_model` default to
`--model` (environment: `AUTODISCOVERY_BELIEF_MODEL`, `AUTODISCOVERY_VISION_MODEL`).
`--embedding_model` (`AUTODISCOVERY_EMBEDDING_MODEL`) has no fallback and is
required only with `--dedupe`.

Every model flag accepts [litellm's](https://docs.litellm.ai/docs/providers)
`<provider>/<model>` naming, with snake_case provider slugs:

```sh
--model openai/gpt-5.4-mini
--model anthropic/claude-sonnet-5
--model azure/gpt-5.4-mini            # your Azure OpenAI deployment name
--model vertex_ai/gemini-3.7-flash
--model github_copilot/claude-haiku-4.5
```

The prefix is **required**. A bare name is ambiguous — `claude-haiku-4.5` is
Anthropic direct or Copilot depending on who you ask — and resolving one means
asking litellm, which authenticates for some providers. Unqualified names are
rejected at startup with the qualified form to use:

```
'gemini-3.7-flash' is missing a provider. Model names are litellm-qualified
as <provider>/<model>, e.g. vertex_ai/gemini-3.7-flash or openai/gemini-3.7-flash.
```

`google/<model>` is also rejected: it was Vertex's OpenAI-compatible wire prefix,
never a litellm provider. Use `vertex_ai/<model>`.

Any of litellm's [~149 providers](https://docs.litellm.ai/docs/providers) can be
named — there is no allow-list. The five documented below (`openai`,
`anthropic`, `azure`, `vertex_ai`, `github_copilot`) are the ones this project
checks credentials for at startup and tests; using another means supplying its
credentials yourself, per litellm's env-var conventions.

Because the provider travels with each flag, roles can use different providers
in one run — Copilot for chat, Vertex for plot analysis:

```sh
auto-discovery \
   --model github_copilot/claude-haiku-4.5 \
   --vision_model vertex_ai/gemini-3.7-flash \
   ...
```

Each flag is checked at startup, before the first model call: the vision model
must support image input, the embedding model must be an embedding model, and
chat flags must be chat models. A model litellm has not mapped yet is a warning,
not an error — providers ship models faster than litellm maps them.

For `github_copilot/` the check uses Copilot's own `/models` endpoint instead of
litellm's static catalog, which is inaccurate in both directions: it lists models
an account cannot call (`gpt-5` → *"The requested model is not supported"*) and
omits ones it can (`gpt-5.4`, `claude-opus-5`). The live list is read from
litellm's cached API key and never triggers a login; with no usable cached key,
validation falls back to the registry with a warning.

## Credentials

All model traffic goes through [litellm](https://docs.litellm.ai/), so
credentials follow litellm's conventions per provider.

**OpenAI** uses `OPENAI_API_KEY`, checked at startup. Pass `--model openai/gpt-...`.

**Anthropic** uses `ANTHROPIC_API_KEY`, checked at startup. Pass
`--model anthropic/claude-...`. Anthropic's API has no `n` parameter, so
multi-sample calls (belief elicitation) are issued one sample per request; and
it has no embedding models, so `--dedupe` needs `--embedding_model` from another
provider (with that provider's key).

**Azure OpenAI** uses `AZURE_API_KEY` and `AZURE_API_BASE`
(`https://<resource>.openai.azure.com`), both checked at startup, plus litellm's
optional `AZURE_API_VERSION`. The model is `azure/<deployment name>`; name
deployments after the model they serve so the reasoning-model handling
(temperature, per-request sample cap) resolves from litellm's registry.

**Vertex AI** uses Application Default Credentials:

```sh
export VERTEXAI_PROJECT=your-gcp-project
export VERTEXAI_LOCATION=global          # `global` serves current Gemini models

# Either a service-account key...
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
# ...or local user credentials:
gcloud auth application-default login
```

Both variables are litellm's own — this package defines no Vertex settings of
its own and maps nothing. Both are required: a run naming a `vertex_ai/` model
without them stops at startup naming the ones that are missing, because
litellm's fallback for each is worse than an error. An unset project takes
whatever project your Application Default Credentials carry, which is
frequently not the one you meant; an unset location takes `us-central1`, which
does not serve current Gemini models. Either way the first model call 404s
mid-run, and the 404 reads as if the model does not exist. Set
`VERTEXAI_LOCATION=global` unless you have a specific region in mind.

### GitHub Copilot

GitHub Copilot needs no extra install — litellm speaks it natively.

On an interactive terminal, litellm runs GitHub's device-code login on first
use — it prints a code to enter at github.com and caches the token itself. No
setup needed.

For **non-interactive** runs (deployed jobs, CI), pre-seed the token instead:

```sh
export GITHUB_COPILOT_TOKEN_DIR=/path/to/dir   # default ~/.config/litellm/github_copilot
# the directory must contain a file named `access-token` holding a GitHub OAuth token
```

litellm does no TTY detection, so without a cached token a headless run prints
a device code and blocks for roughly three minutes before failing, rather than
erroring immediately.

Select Copilot per role with the `github_copilot/` prefix:

```sh
auto-discovery \
   --model github_copilot/claude-haiku-4.5 \
   --belief_model github_copilot/claude-haiku-4.5 \
   --vision_model github_copilot/claude-haiku-4.5 \
   --embedding_model github_copilot/text-embedding-3-small \
   --embedding_dimensions 1536 \
   --backend process \
   --dedupe \
   data/measurements.csv
```

Copilot honors `--temperature` and
`--belief_temperature` when the selected model permits that value. Some reasoning
modes constrain temperature at the provider.

`github_copilot/text-embedding-3-small` at 1536 dimensions is not numerically
identical to OpenAI's `text-embedding-3-large`, so use the OpenAI embedding model
when exact embedding geometry must be preserved. Copilot works
with every execution backend, including `local`: figures are interpreted in the
CLI's own process, so `--vision_model` is never resolved inside the sandbox.

## Run

```sh
auto-discovery \
    --model openai/gpt-5.4-mini \
    --name "Plant growth study" \
    --description "Field trial measurements of plant height under varying fertilizer" \
    --intent "Focus on dose-response relationships" \
    --n_experiments 20 \
    --out_dir ./results \
    data/measurements.csv data/treatments.csv
```

Datasets are positional file or directory paths (CSV, TSV, JSON, etc.). The CLI
generates a metadata file, runs the MCTS loop, writes results to `--out_dir`,
and emits a static HTML report.

See `auto-discovery --help` for the full option list (model selection, MCTS
parameters, belief mode, execution backend, etc.).

## Publishing to PyPI

Releases are cut from a git tag and published via the
[`publish-to-pypi`](https://github.com/allenai/asta-autodiscovery/blob/main/.github/workflows/publish-to-pypi.yml)
workflow.

Steps:

1. On your PR branch, set the new version:

   ```sh
   make set-version VERSION=x.y.z
   ```

   This keeps all six sub-packages in sync. Only `asta-autodiscovery`,
   `asta-autodiscovery-modal` and `asta-code-execution` are actually published,
   but we sync the whole workspace so versions don't drift.

2. Just before merging to main, push the version tag:

   ```sh
   make push-version-tag
   ```

   This verifies version consistency, creates `v<version>`, and pushes it to
   `origin`.

3. **Trigger the workflow**: in GitHub Actions, run the *Publish to PyPI*
   workflow with the tag (e.g. `v1.1.7`) as the `version` input.

   The workflow publishes the three packages and then creates the matching
   GitHub release, pointing at the tag's `CHANGELOG.md`. Add the version's
   changelog entry before releasing — that link is the only per-version notes
   PyPI consumers get, since PyPI renders only the current long description.
