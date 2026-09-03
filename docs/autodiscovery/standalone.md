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

Every model flag — `--model`, `--belief_model`, `--vision_model`,
`--embedding_model` — accepts [litellm's](https://docs.litellm.ai/docs/providers)
`<provider>/<model>` naming, with snake_case provider slugs:

```sh
--model vertex_ai/gemini-3.7-flash
--model openai/o4-mini
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
named — there is no allow-list. The three documented below (`vertex_ai`,
`openai`, `github_copilot`) are the ones this project configures credentials for
and tests; using another means supplying its credentials yourself, per litellm's
env-var conventions.

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

**Vertex AI** (the default model `vertex_ai/gemini-3.7-flash`) uses Application
Default Credentials:

```sh
export VERTEX_PROJECT_ID=your-gcp-project
export VERTEX_LOCATION=global            # optional, defaults to global

# Either a service-account key...
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
# ...or local user credentials:
gcloud auth application-default login
```

The project is required and is not inferred from your credentials — a run
naming a `vertex_ai/` model without `VERTEX_PROJECT_ID` stops at startup naming
the variable. Application Default Credentials carry a project of their own, but
it is frequently not the one you meant, and using it silently would turn a
missing setting into a 404 about an unrelated project. The location is optional
because `global` serves the Gemini models this package defaults to; litellm's
own default, `us-central1`, does not.

litellm's own `VERTEXAI_PROJECT`/`VERTEX_PROJECT` and `VERTEXAI_LOCATION` work
too, and take lower precedence than the names above.

**OpenAI** uses `OPENAI_API_KEY`. Pass `--model openai/gpt-...`.

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
identical to the OpenAI `text-embedding-3-large` default, so keep the OpenAI
embedding model when exact embedding geometry must be preserved. Copilot
currently requires the `process` or `modal` execution backend; the `local`
backend's generated image analysis code is tied to an OpenAI client.

## Run

```sh
auto-discovery \
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
