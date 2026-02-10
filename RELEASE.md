# Release Process

This document describes how to release changes from development to production.

**Note:** For initial infrastructure setup (creating Cloud Run Jobs and Schedulers), see [INFRASTRUCTURE.md](INFRASTRUCTURE.md).

## Overview

The release process is simple: point the `env/prod` branch at a stable commit from `main`.

## Steps

### 1. Identify the Commit

Find the commit SHA you want to release. This should be a tested, stable commit from `main`.

```bash
# View recent commits on main
git log main --oneline -10

# Or use GitHub to find the commit
```

### 2. Update the env/prod Branch

```bash
# Fetch latest changes
git fetch origin

# Point env/prod at the desired commit
git push origin <commit-sha>:refs/heads/env/prod

# Example:
git push origin a1b2c3d4:refs/heads/env/prod
```

### 3. Verify the Build

GitHub Actions will automatically:
- Build and push Docker images with `:prod` tag
- Deploy the webapp/API to production (via Skiff)

Monitor the builds:
- **Workflows:** https://github.com/allenai/asta-autodiscovery/actions
- **Skiff/Marina:** https://marina.apps.allenai.org/a/asta-autodiscovery

### 4. Cloud Run Jobs Updated Automatically ✅

GitHub Actions automatically updates Cloud Run Jobs after pushing new images. When the workflows detect changes to:
- `packages/autodiscovery/**` → Updates `autodiscovery-job-{dev|prod}`
- `scripts/**` or `packages/autodiscovery_jobs/**` → Updates email and cleanup jobs
- `packages/devtools/**` → Updates `autodiscovery-replay-{dev|prod}`

No manual intervention needed! The jobs are automatically updated to use the latest `:dev` or `:prod` image.

**Note:** If the automated update fails (e.g., jobs don't exist yet), you can manually update:

```bash
# Example: manually update autodiscovery job in prod
gcloud run jobs update autodiscovery-job-prod \
  --image us-west1-docker.pkg.dev/ai2-aristo/autodiscovery/autodiscovery:prod \
  --region us-west1
```

### 5. Verify Production

- **Webapp:** https://autodiscovery.allen.ai/
- **Test a run:** Create a small test job and verify it completes successfully
- **Check logs:** Monitor Cloud Logging for any errors

## Rollback

If you need to rollback to a previous version:

```bash
# Find the previous commit
git log env/prod --oneline -10

# Point env/prod back to the previous commit
git push origin <previous-commit-sha>:refs/heads/env/prod
```

Then update Cloud Run jobs as needed (step 4 above).

## What Gets Deployed

### Automatically Deployed by Skiff
- Webapp (Next.js frontend)
- API (FastAPI backend)
- Supporting services (proxy, sonar, etc.)

### Manually Updated
- Cloud Run jobs (autodiscovery, scripts, replay)
- These require explicit `gcloud` commands to update

## Important Notes

- The `env/prod` branch is a deployment branch, not a development branch
- Never commit directly to `env/prod`
- Always point it at tested commits from `main`
- The same GCS bucket (`ai2-autodiscovery`) is used for both dev and prod, but runs are isolated by user/job paths

## Monitoring

- **Cloud Run Jobs:** GCP Console → Cloud Run → Jobs
- **Cloud Scheduler:** GCP Console → Cloud Scheduler
- **Logs:** GCP Console → Logging
- **Marina (Skiff):** https://marina.apps.allenai.org/a/asta-autodiscovery
