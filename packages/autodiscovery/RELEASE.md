# Open-ended Scientific Discovery via Bayesian Surprise

Asta Autodiscovery is an autonomous agent that performs data exploration on arbitrary datasets.
The agent will generate hypotheses and run experiments to test each one. Surprising outcomes
generate follow-up hypotheses in a recursive exploration.

> Link to our NeurIPS 2025 paper: [AutoDiscovery: Open-ended Scientific Discovery via Bayesian Surprise](https://openreview.net/pdf?id=kJqTkj2HhF)

## Installation

Requires Python 3.13 or newer.

```sh
pip install asta-autodiscovery
```

This installs the `auto-discovery` command-line tool.

## Quick start

Point `auto-discovery` at one or more dataset files and describe what you want explored:

```sh
auto-discovery \
    --name "Plant growth study" \
    --description "Field trial measurements of plant height under varying fertilizer dosage" \
    --intent "Focus on dose-response relationships" \
    --n_experiments 20 \
    --out_dir ./results \
    data/measurements.csv data/treatments.csv
```

CSV/TSV column headers are detected automatically. Datasets can also be directories — every
file under them will be included.

Dataset files/directories can have different descriptions for each one listed. Use a repeated `--dataset_description`
parameter in place of the overall `--description`.

When the run finishes, a static HTML report is written to `<out_dir>/report`.

## Common options

| Flag | Description |
| --- | --- |
| `--n_experiments` | Number of experiments to run (required). |
| `--out_dir` | Output directory for results and the HTML report (required). |
| `--name` | Short title for the run. |
| `--description` | Context about the dataset: provenance, collection method, known gaps. |
| `--domain` | Research domain (e.g. `Genomics`). |
| `--intent` | High-level exploration guidance for the agent. |
| `--dataset_description` | Per-dataset description; repeat once per dataset, in order. |
| `--exploration_weight` | Higher = broader exploration (default `2.0`). |
| `--surprisal_width` | Surprise threshold; lower = more sensitive (default `0.2`). |

Run `auto-discovery --help` to see the full set of options.

## Authentication

All model traffic goes through [litellm](https://docs.litellm.ai/), and every model flag names
its provider explicitly as `<provider>/<model>` — for example
`vertex_ai/gemini-3.1-pro-preview`, `openai/o4-mini`, `github_copilot/claude-haiku-4.5`. You only
need to configure the providers you actually name in `--model`, `--belief_model`,
`--vision_model` and `--embedding_model`.

### Vertex AI

Used when a model flag names `vertex_ai/...`. The defaults are Vertex models, so this is required
unless you override them all.

Pick one of the following. In all cases, set the project (and optionally location) so the agent
knows which Vertex endpoint to call:

```sh
export VERTEX_PROJECT_ID=your-gcp-project-id
export VERTEX_LOCATION=global   # optional; defaults to "global"
```

**Service account key file (recommended for non-interactive use):**

Create a service account in your GCP project, grant it the `Vertex AI User` role, download a
JSON key, and point Google's standard ADC env var at it:

```sh
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

**User credentials via gcloud (recommended for local development):**

```sh
gcloud auth application-default login
```

Vertex authenticates via Application Default Credentials, so either
`GOOGLE_APPLICATION_CREDENTIALS` or `gcloud auth application-default login` is
required. Raw bearer tokens (`VERTEX_ACCESS_TOKEN`) are no longer accepted.

### OpenAI

Used when a model flag names `openai/...` (e.g. `openai/gpt-4o`).

```sh
export OPENAI_API_KEY=sk-...
```

### GitHub Copilot

Used when a model flag names `github_copilot/...`. litellm reads a GitHub OAuth token from a
file, so no interactive login happens at run time:

```sh
export GITHUB_COPILOT_TOKEN_DIR=/path/to/dir   # must contain a file named `access-token`
```

### Selecting models

| Flag | What it controls | Default |
| --- | --- | --- |
| `--model` | Primary reasoning model used for hypothesis generation and analysis. | `vertex_ai/gemini-3.1-pro-preview` |
| `--belief_model` | Model used for belief updates over experimental outcomes. | `vertex_ai/gemini-3-flash-preview` |
| `--vision_model` | Model used to interpret plots and figures emitted by experiments. | `vertex_ai/gemini-3.1-pro-preview` |
| `--embedding_model` | Model used for deduplication embeddings. | `openai/text-embedding-3-large` |

Because the provider travels with each flag, mixing providers is supported — for example,
`--model openai/gpt-4o --belief_model vertex_ai/gemini-3-flash-preview` uses OpenAI for the main
loop and Vertex AI for belief updates, with both `OPENAI_API_KEY` and the Vertex variables set.

Each flag is validated against litellm's offline model registry at startup, before the first
model call.

## Citation

If you find this work useful, please cite:

```
@inproceedings{
agarwal2025autodiscovery,
title={AutoDiscovery: Open-ended Scientific Discovery via Bayesian Surprise},
author={Dhruv Agarwal and Bodhisattwa Prasad Majumder and Reece Adamson and Megha Chakravorty and Satvika Reddy Gavireddy and Aditya Parashar and Harshit Surana and Bhavana Dalvi Mishra and Andrew McCallum and Ashish Sabharwal and Peter Clark},
booktitle={The Thirty-ninth Annual Conference on Neural Information Processing Systems},
year={2025},
url={https://openreview.net/forum?id=kJqTkj2HhF}
}
```