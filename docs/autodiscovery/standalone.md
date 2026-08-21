# Standalone CLI

The `autodiscovery` package ships a console script, `auto-discovery`, that runs the
discovery engine end-to-end against a local dataset — no Cloud Run, GCS, or UI
required.

## Install from PyPI

```sh
pip install autodiscovery
```

This pulls in `autodiscovery-modal` (sandboxed code execution) as a transitive
dependency. Requires Python 3.13+.

## Selecting models

Every model flag — `--model`, `--belief_model`, `--vision_model`,
`--embedding_model` — accepts [litellm's](https://docs.litellm.ai/docs/providers)
`<provider>/<model>` naming, with snake_case provider slugs:

```sh
--model vertex_ai/gemini-3.1-pro-preview
--model openai/o4-mini
--model github_copilot/claude-haiku-4.5
```

A bare model name still works and is resolved to a provider by litellm, so
existing configurations keep running unchanged: `gemini-3.1-pro-preview` goes to
Vertex AI, `o4-mini` and `text-embedding-3-large` go to OpenAI. Prefixes matter
where a bare name is ambiguous — bare `claude-haiku-4.5` names Anthropic direct,
which this package cannot call; the Copilot-hosted model is
`github_copilot/claude-haiku-4.5`.

Because the provider travels with each flag, roles can use different providers
in one run — Copilot for chat, Vertex for plot analysis:

```sh
auto-discovery \
   --model github_copilot/claude-haiku-4.5 \
   --vision_model vertex_ai/gemini-3.1-pro-preview \
   ...
```

Each flag is checked against litellm's offline model registry at startup, before
the first model call: the vision model must support image input, the embedding
model must be an embedding model, and Copilot models must exist in Copilot's
catalog. `google/<model>` is still accepted as a legacy alias for
`vertex_ai/<model>`.

`--llm_provider` and `--embedding_provider` are deprecated. They still set the
provider assumed for bare model names in their respective flags, but prefixing
the model flags is preferred.

## Credentials

All model traffic goes through [litellm](https://docs.litellm.ai/), so
credentials follow litellm's conventions per provider.

**Vertex AI** (the default models `gemini-3.1-pro-preview`,
`gemini-3-flash-preview`) uses Application Default Credentials:

```sh
export VERTEX_PROJECT_ID=your-gcp-project
export VERTEX_LOCATION=global            # optional, defaults to global

# Either a service-account key...
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
# ...or local user credentials:
gcloud auth application-default login
```

> **Changed:** `VERTEX_ACCESS_TOKEN` is no longer used. litellm's Vertex client
> authenticates with ADC and refreshes on its own, so a raw access token from
> `gcloud auth print-access-token` has no equivalent. Use
> `gcloud auth application-default login` locally; deployments already using
> `GOOGLE_APPLICATION_CREDENTIALS` need no change.

**OpenAI** uses `OPENAI_API_KEY`. Pass `--model openai/gpt-...`.

### GitHub Copilot

GitHub Copilot needs no extra install — litellm speaks it natively. It reads a
GitHub OAuth token from a file, so no interactive login happens at run time:

```sh
export GITHUB_COPILOT_TOKEN_DIR=/path/to/dir   # default ~/.config/litellm/github_copilot
# the directory must contain a file named `access-token`
```

> **Changed:** Copilot no longer shells out to the `copilot` CLI via
> `github-copilot-sdk`, and the `[copilot]` extra and
> `python -m autodiscovery.copilot doctor` command are gone. The account still
> needs an active Copilot seat.

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

Use unprefixed (or `vertex_ai/`/`openai/`) model names to preserve the existing
Vertex/OpenAI behavior. Copilot honors `--temperature` and
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
[`publish-to-pypi`](../.github/workflows/publish-to-pypi.yml) workflow.

Steps:

1. On your PR branch, set the new version:

   ```sh
   make set-version VERSION=x.y.z
   ```

   This keeps all six sub-packages in sync. Only `autodiscovery` and
   `autodiscovery-modal` are actually published, but we sync the whole workspace
   so versions don't drift.

2. Just before merging to main, push the version tag:

   ```sh
   make push-version-tag
   ```

   This verifies version consistency, creates `v<version>`, and pushes it to
   `origin`.

3. **Trigger the workflow**: in GitHub Actions, run the *Publish to PyPI*
   workflow with the tag (e.g. `v1.1.7`) as the `version` input.
