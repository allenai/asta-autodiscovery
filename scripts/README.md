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

### Cloud Run Setup

See [INFRASTRUCTURE.md](../INFRASTRUCTURE.md) for Cloud Run job and scheduler creation commands.

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

### Cloud Run Setup

See [INFRASTRUCTURE.md](../INFRASTRUCTURE.md) for Cloud Run job and scheduler creation commands.

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

