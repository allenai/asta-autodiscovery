# Scripts

This directory contains scripts that run as scheduled Cloud Run Jobs.

## send_completion_emails.py

Sends email notifications when AutoDiscovery runs complete successfully. Failed and cancelled runs do not trigger notifications. Tracks sent emails in GCS to avoid duplicates.

**Features:**
- Scans for successful runs completed within the last 24 hours (configurable)
- Only sends notifications for SUCCEEDED status (not FAILED or CANCELLED)
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

**Development environment:**
```bash
gcloud run jobs create autodiscovery-send-emails-dev \
  --image us-west1-docker.pkg.dev/example-legacy-project/autodiscovery/autodiscovery-scripts:dev \
  --region us-west1 \
  --service-account example-gcp-project-dev@example-legacy-project.iam.gserviceaccount.com \
  --set-env-vars "AUTH0_MGMT_CLIENT_ID=${AUTH0_MGMT_CLIENT_ID},AUTH0_MGMT_CLIENT_SECRET=${AUTH0_MGMT_CLIENT_SECRET}" \
  --update-secrets=SMTP_USERNAME=smtp-username:latest,SMTP_PASSWORD=smtp-password:latest \
  --task-timeout 29m \
  --max-retries 0 \
  --command "uv" \
  --args "run,python,scripts/send_completion_emails.py,--acquire-lock,--userid,auth0|EXAMPLE_USER_ID"
```

**Note:** The dev job includes `--userid` to limit emails to a single test user, preventing accidental spam to all users during development.

**Production environment:**
```bash
gcloud run jobs create autodiscovery-send-emails-prod \
  --image us-west1-docker.pkg.dev/example-legacy-project/autodiscovery/autodiscovery-scripts:prod \
  --region us-west1 \
  --service-account example-gcp-project-dev@example-legacy-project.iam.gserviceaccount.com \
  --set-env-vars "AUTH0_MGMT_CLIENT_ID=${AUTH0_MGMT_CLIENT_ID},AUTH0_MGMT_CLIENT_SECRET=${AUTH0_MGMT_CLIENT_SECRET}" \
  --update-secrets=SMTP_USERNAME=smtp-username:latest,SMTP_PASSWORD=smtp-password:latest \
  --task-timeout 29m \
  --max-retries 0 \
  --command "uv" \
  --args "run,python,scripts/send_completion_emails.py,--acquire-lock"
```

**SMTP Configuration:**
The jobs use Gmail SMTP relay for sending emails. Credentials are stored in GCP Secrets Manager:
- `smtp-username`: Gmail/Google Workspace email address
- `smtp-password`: App password for authentication

To grant the service account access to these secrets:
```bash
gcloud secrets add-iam-policy-binding smtp-username \
  --member="serviceAccount:example-gcp-project-dev@example-legacy-project.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=example-legacy-project

gcloud secrets add-iam-policy-binding smtp-password \
  --member="serviceAccount:example-gcp-project-dev@example-legacy-project.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=example-legacy-project
```

### Schedule (every 30 minutes)

**Development environment:**
```bash
gcloud scheduler jobs create http autodiscovery-send-emails-schedule-dev \
  --location us-west1 \
  --schedule "*/30 * * * *" \
  --uri "https://us-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/example-legacy-project/jobs/autodiscovery-send-emails-dev:run" \
  --http-method POST \
  --oauth-service-account-email example-gcp-project-dev@example-legacy-project.iam.gserviceaccount.com \
  --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform"
```

**Production environment:**
```bash
gcloud scheduler jobs create http autodiscovery-send-emails-schedule-prod \
  --location us-west1 \
  --schedule "*/30 * * * *" \
  --uri "https://us-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/example-legacy-project/jobs/autodiscovery-send-emails-prod:run" \
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

## Docker Images

All scripts are packaged into a single container image: `us-west1-docker.pkg.dev/example-legacy-project/autodiscovery/autodiscovery-scripts`

### Image Tagging Strategy

Images are tagged based on the branch they're built from:
- **Dev environment** (`main` branch): `:dev`, `:dev-${commit_sha}`
- **Prod environment** (`env/prod` branch): `:prod`, `:prod-${commit_sha}`

**Note:** We do not use `:latest` tags. All deployments must explicitly specify `:dev` or `:prod` to prevent accidental environment mixing.

### Automated Builds

The image is automatically built and pushed to Artifact Registry by GitHub Actions when changes are merged to `main` or `env/prod` that affect:
- `scripts/**`
- `packages/autodiscovery_jobs/**`

See `.github/workflows/scripts-build.yml`

### Manual Build (if needed)

Using Makefile:
```bash
# Build and push with dev tag (default)
make push-scripts-image

# Build and push with prod tag
IMAGE_TAG=prod make push-scripts-image

# Build and push with custom tag
IMAGE_TAG=my-tag make push-scripts-image
```

Using Docker directly:
```bash
docker build --platform linux/amd64 -t us-west1-docker.pkg.dev/example-legacy-project/autodiscovery/autodiscovery-scripts:dev -f scripts/Dockerfile .
docker push us-west1-docker.pkg.dev/example-legacy-project/autodiscovery/autodiscovery-scripts:dev
```

Note: `--platform linux/amd64` is required for Cloud Run compatibility (especially when building on Apple Silicon).

## Cloud Run Job Setup

**Setup your environment:**
```bash
export CLOUDSDK_CORE_PROJECT=example-legacy-project
```

### Create Cloud Run Job

**Development environment:**
```bash
gcloud run jobs create autodiscovery-dataset-cleanup-dev \
  --image us-west1-docker.pkg.dev/example-legacy-project/autodiscovery/autodiscovery-scripts:dev \
  --region us-west1 \
  --service-account example-gcp-project-dev@example-legacy-project.iam.gserviceaccount.com \
  --command "uv" \
  --args "run,python,scripts/cleanup_old_datasets.py"
```

**Production environment:**
```bash
gcloud run jobs create autodiscovery-dataset-cleanup-prod \
  --image us-west1-docker.pkg.dev/example-legacy-project/autodiscovery/autodiscovery-scripts:prod \
  --region us-west1 \
  --service-account example-gcp-project-dev@example-legacy-project.iam.gserviceaccount.com \
  --command "uv" \
  --args "run,python,scripts/cleanup_old_datasets.py"
```

### Schedule with Cloud Scheduler

**Development environment:**
```bash
gcloud scheduler jobs create http autodiscovery-dataset-cleanup-schedule-dev \
  --location us-west1 \
  --schedule "0 2 * * *" \
  --uri "https://us-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/example-legacy-project/jobs/autodiscovery-dataset-cleanup-dev:run" \
  --http-method POST \
  --oauth-service-account-email example-gcp-project-dev@example-legacy-project.iam.gserviceaccount.com \
  --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform"
```

**Production environment:**
```bash
gcloud scheduler jobs create http autodiscovery-dataset-cleanup-schedule-prod \
  --location us-west1 \
  --schedule "0 2 * * *" \
  --uri "https://us-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/example-legacy-project/jobs/autodiscovery-dataset-cleanup-prod:run" \
  --http-method POST \
  --oauth-service-account-email example-gcp-project-dev@example-legacy-project.iam.gserviceaccount.com \
  --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform"
```

This runs daily at 2 AM.

### Updating Jobs to Use New Images

The GitHub Action automatically pushes new images when changes merge to `main` (`:dev` tag) or `env/prod` (`:prod` tag).

After a new image is pushed, update the Cloud Run Job to force it to pull the latest image with that tag:

**Development environment:**
```bash
gcloud run jobs update autodiscovery-send-emails-dev \
  --image us-west1-docker.pkg.dev/example-legacy-project/autodiscovery/autodiscovery-scripts:dev \
  --region us-west1

gcloud run jobs update autodiscovery-dataset-cleanup-dev \
  --image us-west1-docker.pkg.dev/example-legacy-project/autodiscovery/autodiscovery-scripts:dev \
  --region us-west1
```

**Production environment:**
```bash
gcloud run jobs update autodiscovery-send-emails-prod \
  --image us-west1-docker.pkg.dev/example-legacy-project/autodiscovery/autodiscovery-scripts:prod \
  --region us-west1

gcloud run jobs update autodiscovery-dataset-cleanup-prod \
  --image us-west1-docker.pkg.dev/example-legacy-project/autodiscovery/autodiscovery-scripts:prod \
  --region us-west1
```

## Required Permissions

**`example-gcp-project-dev@example-legacy-project.iam.gserviceaccount.com`** is used for:
- Running scheduled Cloud Run Jobs (job runtime identity)
- Pushing images to Artifact Registry (via GitHub Actions)
- Invoking Cloud Run Jobs (via Cloud Scheduler)
- Updating Cloud Run Jobs (via GitHub Actions, optional)

It needs:
- `roles/storage.objectAdmin` - for GCS operations (list/delete)
- `roles/artifactregistry.writer` - for pushing images to Artifact Registry
- `roles/run.invoker` - for Cloud Scheduler to invoke the job
- `roles/run.developer` - (optional) for GitHub Actions to auto-update jobs after pushing new images
