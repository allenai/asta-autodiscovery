# Docker Image Build and Deployment Strategy

This document describes the unified build and tagging strategy for all Cloud Run Job images in the asta-autodiscovery project.

## Overview

We maintain three Cloud Run Job images:
1. **autodiscovery** - Main AutoDiscovery job
2. **autodiscovery-scripts** - Maintenance scripts (email notifications, dataset cleanup)
3. **autodiscovery-replay** - Replay/simulation tool for testing

All three images follow the same build, tagging, and deployment pattern to isolate development from production environments.

## Image Tagging Strategy

Images are tagged based on the branch they're built from:

- **Development environment** (`main` branch):
  - `:dev` - Latest dev build
  - `:dev-${commit_sha}` - Specific dev build

- **Production environment** (`env/prod` branch):
  - `:prod` - Latest prod build
  - `:prod-${commit_sha}` - Specific prod build

**Note:** We do not use `:latest` tags. All deployments must explicitly specify `:dev` or `:prod` to prevent accidental environment mixing.

## Automated Builds

GitHub Actions automatically build and push images when changes merge to `main` or `env/prod`:

| Image | Workflow | Triggers |
|-------|----------|----------|
| autodiscovery-scripts | `.github/workflows/scripts-build.yml` | `scripts/**`, `packages/autodiscovery_jobs/**` |
| autodiscovery-replay | `.github/workflows/replay-build.yml` | `packages/devtools/**` |
| autodiscovery | `.github/workflows/autodiscovery-build.yml` | `packages/autodiscovery/**`, `pyproject.toml`, `uv.lock` |

## Local Development

### Building Images

From the repository root, use the Makefile:

```bash
# Build and push scripts image with dev tag (default)
make push-scripts-image

# Build and push replay image with prod tag
IMAGE_TAG=prod make push-replay-image

# Build autodiscovery image (requires GITHUB_TOKEN)
GITHUB_TOKEN=your_token make build-autodiscovery-image
```

Available Makefile targets:
- `build-scripts-image` / `push-scripts-image`
- `build-replay-image` / `push-replay-image`
- `build-autodiscovery-image` / `push-autodiscovery-image`

All targets support the `IMAGE_TAG` variable (defaults to `dev`).

### Deploying Cloud Run Jobs

#### AutoDiscovery Job

```bash
# Deploy to dev environment (uses :dev tag)
make deploy-autodiscovery

# Deploy to prod environment (uses :prod tag)
ENV_TAG=prod SKIP_BUILD=true make deploy-autodiscovery
```

The `SKIP_BUILD=true` flag skips building the image locally and uses the image already built by GitHub Actions.

#### Scripts Jobs (email, cleanup)

See `scripts/README.md` for detailed commands. Example:

```bash
# Update email job in dev
gcloud run jobs update autodiscovery-send-emails \
  --image us-west1-docker.pkg.dev/ai2-aristo/autodiscovery/autodiscovery-scripts:dev \
  --region us-west1

# Update email job in prod
gcloud run jobs update autodiscovery-send-emails \
  --image us-west1-docker.pkg.dev/ai2-aristo/autodiscovery/autodiscovery-scripts:prod \
  --region us-west1
```

#### Replay Job

See `packages/devtools/DEPLOYMENT.md` for detailed commands.

## Environment Isolation

### Cloud Run Job Naming

Since Cloud Run doesn't allow overriding the image at execution time, we use separate job definitions for dev and prod with explicit `-dev` and `-prod` suffixes:

| Environment | Job Name | Image Tag |
|-------------|----------|-----------|
| **Dev** | `autodiscovery-job-dev` | `:dev` |
| **Dev** | `autodiscovery-send-emails-dev` | `:dev` |
| **Dev** | `autodiscovery-dataset-cleanup-dev` | `:dev` |
| **Dev** | `autodiscovery-replay-dev` | `:dev` |
| **Prod** | `autodiscovery-job-prod` | `:prod` |
| **Prod** | `autodiscovery-send-emails-prod` | `:prod` |
| **Prod** | `autodiscovery-dataset-cleanup-prod` | `:prod` |
| **Prod** | `autodiscovery-replay-prod` | `:prod` |

The webapp/API automatically uses the correct job name based on the `ENV` environment variable:
- Dev environment: `CLOUDRUN_JOB_NAME=autodiscovery-job-dev`
- Prod environment: `CLOUDRUN_JOB_NAME=autodiscovery-job-prod`

### Development Environment
- Deployed from `main` branch
- Uses `:dev` tagged images
- Cloud Run jobs without `-prod` suffix
- URL: https://asta-autodiscovery-dev.allen.ai/
- GCS bucket: `ai2-autodiscovery` (shared, but dev jobs write to dev runs)

### Production Environment
- Deployed from `env/prod` branch
- Uses `:prod` tagged images
- Cloud Run jobs with `-prod` suffix
- URL: https://autodiscovery.allen.ai/
- GCS bucket: `ai2-autodiscovery` (shared, but prod jobs write to prod runs)

## Deployment Workflow

1. **Development:**
   - Merge changes to `main`
   - GitHub Actions builds and pushes images with `:dev` tag
   - Skiff deploys webapp/api to dev environment
   - Cloud Run jobs in dev use `:dev` tagged images

2. **Production:**
   - Point `env/prod` branch at a stable commit from `main`
   - GitHub Actions builds and pushes images with `:prod` tag
   - Skiff deploys webapp/api to prod environment
   - Cloud Run jobs in prod use `:prod` tagged images

## Image Registry

All images are stored in Google Artifact Registry:

```
us-west1-docker.pkg.dev/ai2-aristo/autodiscovery/
├── autodiscovery
├── autodiscovery-scripts
└── autodiscovery-replay
```

## Security Notes

- The `autodiscovery` image requires a GitHub token during build (for private repo access)
- GitHub Actions uses the `GCP_SA_KEY` secret for Artifact Registry authentication
- Cloud Run jobs use service accounts for GCS and Secret Manager access

### GitHub Actions Service Account Permissions

The `GCP_SA_KEY` secret contains a key for `ai2-autodiscovery-dev@ai2-aristo.iam.gserviceaccount.com`.

**Required permissions:**
- `roles/artifactregistry.writer` - Push images ✅
- `roles/storage.objectAdmin` - GCS operations ✅
- `roles/run.invoker` - Invoke jobs via Cloud Scheduler ✅
- `roles/run.developer` - Update Cloud Run Jobs after pushing new images ⚠️

**To enable automated job updates, grant the missing permission:**

```bash
gcloud projects add-iam-policy-binding ai2-aristo \
  --member="serviceAccount:ai2-autodiscovery-dev@ai2-aristo.iam.gserviceaccount.com" \
  --role="roles/run.developer"
```

Once granted, GitHub Actions will automatically update Cloud Run Jobs after pushing new images. The workflows are already configured to do this.

## See Also

- `scripts/README.md` - Scripts image details and job configuration
- `packages/autodiscovery/README.md` - AutoDiscovery job deployment
- `packages/devtools/DEPLOYMENT.md` - Replay job deployment
- `Makefile` - Build targets and commands
