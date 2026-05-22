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

## Credentials

The default models (`gemini-3.1-pro-preview`, `gemini-3-flash-preview`) run on
Vertex AI. Set:

```sh
export VERTEX_PROJECT_ID=your-gcp-project
export VERTEX_LOCATION=global            # optional, defaults to global
export VERTEX_ACCESS_TOKEN=$(gcloud auth print-access-token)
```

To use OpenAI models instead, pass `--model gpt-...` and export `OPENAI_API_KEY`.

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
