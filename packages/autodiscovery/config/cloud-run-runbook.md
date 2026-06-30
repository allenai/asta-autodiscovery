# Autodiscovery — Cloud Run Job Runbook

How to build, deploy, and run `packages/autodiscovery` as a Cloud Run **job**
(`autodiscovery.run`, the MCTS hypothesis-search pipeline) on GCP. Every command
here was verified end-to-end against the first working run (`test-adv`).

> All commands assume you run from the **repo root** unless noted, and that
> `gcloud` is authenticated (`gcloud auth login`) and pointed at the project.

---

## 0. Settings used by this runbook

| Thing | Value |
|---|---|
| GCP project | `autodiscovery-research` |
| Region | `us-central1` |
| Artifact Registry repo | `autodiscovery` (format: docker) |
| Image | `us-central1-docker.pkg.dev/autodiscovery-research/autodiscovery/asta-autodiscovery:latest` |
| GCS bucket (data + output) | `sijia-adv-exp` (US multi-region), mounted at `/mnt/gcs` |
| Job name | `test-adv` |
| Job service account | `1045379309345-compute@developer.gserviceaccount.com` (has project `roles/editor` → can read/write buckets + secrets without extra IAM) |

```bash
gcloud config set project autodiscovery-research
```

One-time API enablement (idempotent):

```bash
gcloud services enable cloudbuild.googleapis.com artifactregistry.googleapis.com run.googleapis.com \
  --project=autodiscovery-research
```

---

## 1. Build & push the image (only when code/deps change)

The Dockerfile lives in `packages/autodiscovery/Dockerfile` but **copies from the
repo root** (`pyproject.toml`, `uv.lock`, `packages/`), so the build **context
must be the repo root**. `gcloud builds submit --tag` can't express this (no
`-f`), so we use `config/cloudbuild.yaml`:

```bash
# from repo root
gcloud builds submit --config packages/autodiscovery/config/cloudbuild.yaml \
  --project=autodiscovery-research .
```

This builds and pushes to Artifact Registry. Note the resulting digest from the
output if you want to pin the job to an immutable image.

---

## 2. Prepare the dataset

`autodiscovery.run` consumes a **JSON metadata file** plus the **data file(s)**
it references — NOT a HuggingFace dataset directory.

`metadata.json` (asta format):

```json
{
  "description": "what this dataset is",
  "datasets": [
    {
      "name": "data.csv",
      "description": "what this table is",
      "columns": { "raw": [
        { "name": "col1", "description": "..." },
        { "name": "col2", "description": "..." }
      ]}
    }
  ]
}
```

- `datasets[].name` must be a **data file (CSV) sitting in the same directory**
  as `metadata.json` (loaded as `os.path.join(dirname(metadata), name)`).
- The table just needs analyzable columns (categorical / numeric) for the agents
  to form and test hypotheses on.

Upload metadata + data side by side into the bucket:

```bash
JOB=my-new-run    # pick a name per dataset
gcloud storage cp metadata.json data.csv \
  gs://sijia-adv-exp/jobs/${JOB}/ --project=autodiscovery-research
```

These land at `/mnt/gcs/jobs/${JOB}/...` inside the container.

---

## 3. Create / update the job (one-time, or when config changes)

The `test-adv` job already exists. To recreate from the exported snapshot:

```bash
gcloud run jobs replace packages/autodiscovery/config/test.yaml \
  --region=us-central1 --project=autodiscovery-research
```

Or create fresh with the volume mount + resources:

```bash
gcloud run jobs create test-adv \
  --image=us-central1-docker.pkg.dev/autodiscovery-research/autodiscovery/asta-autodiscovery:latest \
  --region=us-central1 --project=autodiscovery-research \
  --task-timeout=1h \
  --memory=4Gi --cpu=2 \
  --add-volume=name=job-storage,type=cloud-storage,bucket=sijia-adv-exp \
  --add-volume-mount=volume=job-storage,mount-path=/mnt/gcs
```

> ⚠️ **Memory must be ≥ 4Gi.** The default 512Mi OOMs (exit 137) — heavy deps
> (scikit-learn / scipy / statsmodels / matplotlib) plus runtime `uv` sync.

### OpenAI key (env var, no Secret Manager)

The key is set as a literal env var on the job (extracted from `~/.zshrc`):

```bash
val=$(grep -E '^[[:space:]]*export[[:space:]]+OPENAI_API_KEY=' ~/.zshrc | tail -1)
val=${val#*=}; val=${val%\"}; val=${val#\"}; val=${val%\'}; val=${val#\'}
gcloud run jobs update test-adv --region=us-central1 --project=autodiscovery-research \
  --update-env-vars="OPENAI_API_KEY=${val}"
```

> If a stale Secret Manager reference blocks this with *"already set with a
> different type"*, clear it first:
> `gcloud run jobs update test-adv --region=us-central1 --remove-secrets=OPENAI_API_KEY`

---

## 4. Run the job

```bash
JOB=my-new-run
gcloud run jobs execute test-adv \
  --region=us-central1 --project=autodiscovery-research --async \
  --args="--dataset_metadata=/mnt/gcs/jobs/${JOB}/metadata.json,\
--out_dir=/mnt/gcs/jobs/${JOB}/output,\
--work_dir=work,\
--n_experiments=4,\
--model=gpt-5.4-mini,--belief_model=gpt-5.4-mini,--vision_model=gpt-5.4-mini,\
--no-timestamp_dir"
```

> **Set all three models** (`--model --belief_model --vision_model`). The
> defaults are Gemini/Vertex and would need Vertex credentials.

Required args: `--dataset_metadata`, `--out_dir`, `--work_dir`, `--n_experiments`.
`--out_dir` should point under `/mnt/gcs/...` so results persist to the bucket.

---

## 5. Monitor

```bash
EXEC=<execution-name-from-step-4>   # e.g. test-adv-xr8zp

# status (Completed True = success, False = failed)
gcloud run jobs executions describe $EXEC --region=us-central1 \
  --project=autodiscovery-research \
  --format="value(status.runningCount,status.succeededCount,status.failedCount,status.conditions[0].message)"

# logs
gcloud logging read \
  "resource.type=cloud_run_job AND resource.labels.job_name=test-adv" \
  --project=autodiscovery-research --limit=50 --freshness=30m \
  --format="value(textPayload)"
```

A reference run took ~11 min for `n_experiments=4` on gpt-5.4-mini.

---

## 6. Get results

```bash
JOB=my-new-run
gcloud storage ls -r gs://sijia-adv-exp/jobs/${JOB}/output/          # list
gcloud storage cp -r "gs://sijia-adv-exp/jobs/${JOB}/output/*" ./local_out/   # download
```

Key outputs: `mcts_nodes.csv` / `mcts_nodes.json` (summary), `mcts_nodes_all.json`
(all nodes), `node_*.json` + `rich_outputs/` (per-node detail),
`llm_usage_summary.json` (tokens), `args.json` (run params).

---

## 7. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `exit code 137` / "Out-of-memory" | Bump `--memory` (≥4Gi). |
| `Cannot update env var ... different type` | Stale secret ref → `--remove-secrets=OPENAI_API_KEY`, then set env var. |
| `Permission denied on secret` at deploy | Job SA lacks `secretmanager.secretAccessor` — or just use the env-var path (this runbook). |
| `open()` fails on metadata / 0 datasets loaded | `--dataset_metadata` must be the **JSON manifest**, not a data dir; data files must sit next to it. |
| Agent code `SyntaxError` in logs | Harmless — LLM-generated code error; MCTS retries. Not a job failure. |
| `Model ... not found ... cost will be 0` | Cosmetic pricing warning, ignore. |

---

## 8. Cleanup (optional)

```bash
# delete a job execution's outputs
gcloud storage rm -r gs://sijia-adv-exp/jobs/<job>/

# delete the job
gcloud run jobs delete test-adv --region=us-central1 --project=autodiscovery-research

# delete the image / repo
gcloud artifacts docker images delete \
  us-central1-docker.pkg.dev/autodiscovery-research/autodiscovery/asta-autodiscovery
```
