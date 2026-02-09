# Scripts

This directory contains scripts that run as scheduled Cloud Run Jobs.

## send_completion_emails.py

Sends email notifications when AutoDiscovery runs complete. Tracks sent emails in GCS to avoid duplicates.

**Features:**
- Scans for runs completed within the last 24 hours (configurable)
- Looks up user emails from Auth0
- Uses GCS-based distributed lock to prevent concurrent executions
- Supports dry-run mode for testing

### Local Usage

```bash
# Dry run (no emails sent)
uv run python scripts/send_completion_emails.py --dry-run

# Test with specific user
uv run python scripts/send_completion_emails.py --userid "google-oauth2|123" --dry-run
```

### Cloud Run Job Setup

```bash
gcloud run jobs create autodiscovery-send-emails \
  --image us-west1-docker.pkg.dev/example-legacy-project/autodiscovery/autodiscovery-scripts \
  --region us-west1 \
  --service-account example-gcp-project-dev@example-legacy-project.iam.gserviceaccount.com \
  --set-env-vars "AUTH0_MGMT_CLIENT_ID=${AUTH0_MGMT_CLIENT_ID},AUTH0_MGMT_CLIENT_SECRET=${AUTH0_MGMT_CLIENT_SECRET}" \
  --command "uv" \
  --args "run,python,scripts/send_completion_emails.py,--acquire-lock,--dry-run"
```

Note: Remove `--dry-run` from args once validated.

### Schedule (every 15 minutes)

```bash
gcloud scheduler jobs create http autodiscovery-send-emails-schedule \
  --location us-west1 \
  --schedule "*/15 * * * *" \
  --uri "https://us-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/example-legacy-project/jobs/autodiscovery-send-emails:run" \
  --http-method POST \
  --oauth-service-account-email example-gcp-project-dev@example-legacy-project.iam.gserviceaccount.com \
  --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform"
```

The `--acquire-lock` flag uses a GCS-based lock so overlapping scheduled runs exit cleanly.

---

## cleanup_old_datasets.py

Deletes user-uploaded dataset files older than 7 days from GCS to comply with data retention policies.

**What it deletes:**
- Files matching: `gs://example-gcp-project/users/*/jobs/*/data/*`
- Older than 7 days (based on GCS creation time)

### Local Usage

```bash
# Dry run
uv run python scripts/cleanup_old_datasets.py --dry-run

# Run cleanup
uv run python scripts/cleanup_old_datasets.py

# Custom age
uv run python scripts/cleanup_old_datasets.py --max-age-days 3
```

## Docker Image

All scripts are packaged into a single container image: `us-west1-docker.pkg.dev/example-legacy-project/autodiscovery/autodiscovery-scripts`

### Automated Builds

The image is automatically built and pushed to Artifact Registry by GitHub Actions when changes are merged to `main` that affect:
- `scripts/**`
- `packages/autodiscovery_jobs/**`

See `.github/workflows/maintenance-build.yml`

### Manual Build (if needed)

```bash
docker build --platform linux/amd64 -t us-west1-docker.pkg.dev/example-legacy-project/autodiscovery/autodiscovery-scripts -f scripts/Dockerfile .
docker push us-west1-docker.pkg.dev/example-legacy-project/autodiscovery/autodiscovery-scripts
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
  --image us-west1-docker.pkg.dev/example-legacy-project/autodiscovery/autodiscovery-scripts \
  --region us-west1 \
  --service-account example-gcp-project-dev@example-legacy-project.iam.gserviceaccount.com \
  --command "uv" \
  --args "run,python,scripts/cleanup_old_datasets.py,--dry-run"
```
Note: Currently configured with `--dry-run` for safety. Remove `--dry-run` from args once validated.

### Schedule with Cloud Scheduler

```bash
gcloud scheduler jobs create http autodiscovery-dataset-cleanup-schedule \
  --location us-west1 \
  --schedule "0 2 * * *" \
  --uri "https://us-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/example-legacy-project/jobs/autodiscovery-dataset-cleanup:run" \
  --http-method POST \
  --oauth-service-account-email example-gcp-project-dev@example-legacy-project.iam.gserviceaccount.com \
  --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform"
```

This runs daily at 2 AM.

### Updating

The GitHub Action automatically pushes new images when changes merge to main. To manually trigger an update:

```bash
gcloud run jobs update autodiscovery-dataset-cleanup \
  --image us-west1-docker.pkg.dev/example-legacy-project/autodiscovery/autodiscovery-scripts \
  --region us-west1
```

## Required Permissions

**`example-gcp-project-dev@example-legacy-project.iam.gserviceaccount.com`** is used for:
- Running scheduled Cloud Run Jobs (job runtime identity)
- Pushing images to Artifact Registry (via GitHub Actions)
- Invoking Cloud Run Jobs (via Cloud Scheduler)

It needs:
- `roles/storage.objectAdmin` - for GCS operations (list/delete)
- `roles/artifactregistry.writer` - for pushing images to Artifact Registry
- `roles/run.invoker` - for Cloud Scheduler to invoke the job
