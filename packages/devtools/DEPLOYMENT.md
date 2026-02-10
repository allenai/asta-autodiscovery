# Devtools Replay Job Deployment

This document describes how to deploy the replay job as a Cloud Run service.

## Image Tagging Strategy

The replay Docker image follows an environment-based tagging strategy:
- **Dev environment** (`main` branch): `:dev`, `:dev-${commit_sha}`, `:latest`
- **Prod environment** (`env/prod` branch): `:prod`, `:prod-${commit_sha}`, `:latest`

Images are automatically built and pushed by GitHub Actions when changes merge to `main` or `env/prod`. See `.github/workflows/replay-build.yml`.

## Build and Push Docker Image

### Using Makefile (from repo root)

```bash
# Build and push with dev tag (default)
make push-replay-image

# Build and push with prod tag
IMAGE_TAG=prod make push-replay-image
```

### Using Docker directly

```bash
# Build for linux/amd64 (required for Cloud Run)
docker build --platform linux/amd64 \
  -t us-west1-docker.pkg.dev/example-legacy-project/autodiscovery/autodiscovery-replay:dev \
  -f packages/devtools/Dockerfile .

# Push to Artifact Registry
docker push us-west1-docker.pkg.dev/example-legacy-project/autodiscovery/autodiscovery-replay:dev
```

## Create Cloud Run Job

```bash
# Set project
export CLOUDSDK_CORE_PROJECT=example-legacy-project
```

**Development environment:**
```bash
gcloud run jobs create autodiscovery-replay-dev \
  --image us-west1-docker.pkg.dev/example-legacy-project/autodiscovery/autodiscovery-replay:dev \
  --region us-west1 \
  --service-account example-gcp-project@example-legacy-project.iam.gserviceaccount.com \
  --max-retries 0 \
  --task-timeout 30m
```

**Production environment:**
```bash
gcloud run jobs create autodiscovery-replay-prod \
  --image us-west1-docker.pkg.dev/example-legacy-project/autodiscovery/autodiscovery-replay:prod \
  --region us-west1 \
  --service-account example-gcp-project@example-legacy-project.iam.gserviceaccount.com \
  --max-retries 0 \
  --task-timeout 30m
```

## Execute the Replay Job

**Development environment:**
```bash
gcloud run jobs execute autodiscovery-replay-dev \
  --region us-west1 \
  --args="--source=gs://example-gcp-project/users/test/jobs/melanoma/output" \
  --args="--target=gs://example-gcp-project/users/alice/jobs/test-123/output" \
  --args="--time-scale=0.1"
```

**Production environment:**
```bash
gcloud run jobs execute autodiscovery-replay-prod \
  --region us-west1 \
  --args="--source=gs://example-gcp-project/users/test/jobs/melanoma/output" \
  --args="--target=gs://example-gcp-project/users/alice/jobs/test-123/output" \
  --args="--time-scale=0.1"
```

## Update Job to Use New Image

After a new image is pushed, update the Cloud Run Job to force it to pull the latest image with that tag:

**Development environment:**
```bash
gcloud run jobs update autodiscovery-replay-dev \
  --image us-west1-docker.pkg.dev/example-legacy-project/autodiscovery/autodiscovery-replay:dev \
  --region us-west1
```

**Production environment:**
```bash
gcloud run jobs update autodiscovery-replay-prod \
  --image us-west1-docker.pkg.dev/example-legacy-project/autodiscovery/autodiscovery-replay:prod \
  --region us-west1
```

## Parameters

- `--source` (required): Source GCS path containing the template run files
- `--target` (required): Target GCS path where files will be copied
- `--time-scale` (optional, default=1.0): Time multiplier (0.1 = 10x faster)
- `--project-id` (optional): GCP project ID (auto-detected if not provided)

## Integration with API

The API will detect `"asta.simulate_outputs"` in the run intent and execute this job instead of the actual AutoDiscovery job.

See `api/runs/runs_api.py` for implementation details.
