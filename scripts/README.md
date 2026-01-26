# Maintenance Scripts

This directory contains maintenance scripts that run as scheduled Cloud Run Jobs.

## cleanup_old_datasets.py

Deletes user-uploaded dataset files older than 7 days from GCS to comply with data retention policies.

**What it deletes:**
- Files matching: `gs://example-gcp-project/users/*/jobs/*/data/*`
- Older than 7 days (based on GCS creation time)

### Local Usage

**Test with dry run:**
```bash
uv run python scripts/cleanup_old_datasets.py --dry-run
```

**Run cleanup:**
```bash
uv run python scripts/cleanup_old_datasets.py
```

**Custom age:**
```bash
uv run python scripts/cleanup_old_datasets.py --max-age-days 3
```

## Docker Image

All maintenance scripts are packaged into a single container image: `gcr.io/example-legacy-project/autodiscovery-maintenance`

### Automated Builds

The image is automatically built and pushed to GCR by GitHub Actions when changes are merged to `main` that affect:
- `scripts/**`
- `packages/autodiscovery_jobs/**`

See `.github/workflows/maintenance-build.yml`

### Manual Build (if needed)

```bash
docker build --platform linux/amd64 -t gcr.io/example-legacy-project/autodiscovery-maintenance -f scripts/Dockerfile .
docker push gcr.io/example-legacy-project/autodiscovery-maintenance
```

Note: `--platform linux/amd64` is required for Cloud Run compatibility (especially when building on Apple Silicon).

## Cloud Run Job Setup

**Setup your environment:**
```bash
export CLOUDSDK_CORE_PROJECT=example-legacy-project
```

### Create Cloud Run Job

```bash
gcloud run jobs create autodiscovery-dataset-cleanup \
  --image gcr.io/example-legacy-project/autodiscovery-maintenance \
  --region us-west1 \
  --service-account example-gcp-project-dev@example-legacy-project.iam.gserviceaccount.com \
  --command "uv" \
  --args "run,python,scripts/cleanup_old_datasets.py,--dry-run"
```
Note: Currently configured with `--dry-run` for safety. Remove `--dry-run` from args once validated.

### Schedule with Cloud Scheduler

```bash
project_number=$(gcloud projects describe example-legacy-project --format="value(projectNumber)")

gcloud scheduler jobs create http autodiscovery-dataset-cleanup-schedule \
  --location us-west1 \
  --schedule "0 2 * * *" \
  --uri "https://us-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/example-legacy-project/jobs/autodiscovery-dataset-cleanup:run" \
  --http-method POST \
  --oidc-service-account-email ${project_number}-compute@developer.gserviceaccount.com
```

This runs daily at 2 AM.

### Updating

The GitHub Action automatically pushes new images when changes merge to main. To manually trigger an update:

```bash
gcloud run jobs update autodiscovery-dataset-cleanup \
  --image gcr.io/example-legacy-project/autodiscovery-maintenance \
  --region us-west1
```

## Required Permissions

**`example-gcp-project-dev@example-legacy-project.iam.gserviceaccount.com`** is used for:
- Running maintenance Cloud Run Jobs (job runtime identity)
- Pushing images to GCR (via GitHub Actions)

It needs:
- `roles/storage.objectAdmin` - for GCS operations (list/delete)
- `roles/artifactregistry.writer` - for pushing images to Artifact Registry/GCR

**Default compute service account** is used by Cloud Scheduler to invoke the job (needs `roles/run.invoker`).
