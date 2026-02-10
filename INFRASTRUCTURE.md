# Infrastructure Setup

This document provides commands for creating all Cloud Run Jobs and Cloud Scheduler jobs for both development and production environments.

**Note:** These are one-time setup commands. Once created, jobs can be updated as needed (see individual deployment docs).

## Prerequisites

```bash
# Set project
export CLOUDSDK_CORE_PROJECT=ai2-aristo

# Set Auth0 credentials (for email jobs)
export AUTH0_MGMT_CLIENT_ID="your-client-id"
export AUTH0_MGMT_CLIENT_SECRET="your-client-secret"
```

## AutoDiscovery Job

The main AutoDiscovery job that runs hypothesis search and verification.

**Development environment:**
```bash
gcloud run jobs create autodiscovery-job-dev \
  --image us-west1-docker.pkg.dev/ai2-aristo/autodiscovery/autodiscovery:dev \
  --region us-west1 \
  --service-account ai2-autodiscovery-dev@ai2-aristo.iam.gserviceaccount.com \
  --max-retries 0 \
  --task-timeout 12h \
  --memory 8Gi \
  --cpu 4 \
  --set-secrets "OPENAI_API_KEY=autodiscovery-openai-key:latest,MODAL_TOKEN_ID=autodiscovery-modal-token-id:latest,MODAL_TOKEN_SECRET=autodiscovery-modal-token-secret:latest,MODAL_ENVIRONMENT=autodiscovery-modal-environment:latest,MODAL_IMAGE_BUILDER_VERSION=autodiscovery-modal-image-builder:latest" \
  --set-env-vars "VERTEX_PROJECT_ID=ai2-aristo,VERTEX_LOCATION=us-west1" \
  --add-volume name=job-storage,type=cloud-storage,bucket=ai2-autodiscovery \
  --add-volume-mount volume=job-storage,mount-path=/mnt/gcs
```

**Production environment:**
```bash
gcloud run jobs create autodiscovery-job-prod \
  --image us-west1-docker.pkg.dev/ai2-aristo/autodiscovery/autodiscovery:prod \
  --region us-west1 \
  --service-account ai2-autodiscovery-dev@ai2-aristo.iam.gserviceaccount.com \
  --max-retries 0 \
  --task-timeout 12h \
  --memory 8Gi \
  --cpu 4 \
  --set-secrets "OPENAI_API_KEY=autodiscovery-openai-key:latest,MODAL_TOKEN_ID=autodiscovery-modal-token-id:latest,MODAL_TOKEN_SECRET=autodiscovery-modal-token-secret:latest,MODAL_ENVIRONMENT=autodiscovery-modal-environment:latest,MODAL_IMAGE_BUILDER_VERSION=autodiscovery-modal-image-builder:latest" \
  --set-env-vars "VERTEX_PROJECT_ID=ai2-aristo,VERTEX_LOCATION=us-west1" \
  --add-volume name=job-storage,type=cloud-storage,bucket=ai2-autodiscovery \
  --add-volume-mount volume=job-storage,mount-path=/mnt/gcs
```

## Email Notification Job

Sends completion emails when AutoDiscovery runs finish.

**Development environment:**
```bash
gcloud run jobs create autodiscovery-send-emails-dev \
  --image us-west1-docker.pkg.dev/ai2-aristo/autodiscovery/autodiscovery-scripts:dev \
  --region us-west1 \
  --service-account ai2-autodiscovery-dev@ai2-aristo.iam.gserviceaccount.com \
  --set-env-vars "AUTH0_MGMT_CLIENT_ID=${AUTH0_MGMT_CLIENT_ID},AUTH0_MGMT_CLIENT_SECRET=${AUTH0_MGMT_CLIENT_SECRET}" \
  --task-timeout 29m \
  --command "uv" \
  --args "run,python,scripts/send_completion_emails.py,--acquire-lock"

gcloud scheduler jobs create http autodiscovery-send-emails-schedule-dev \
  --location us-west1 \
  --schedule "*/30 * * * *" \
  --uri "https://us-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/ai2-aristo/jobs/autodiscovery-send-emails-dev:run" \
  --http-method POST \
  --oauth-service-account-email ai2-autodiscovery-dev@ai2-aristo.iam.gserviceaccount.com \
  --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform"
```

**Production environment:**
```bash
gcloud run jobs create autodiscovery-send-emails-prod \
  --image us-west1-docker.pkg.dev/ai2-aristo/autodiscovery/autodiscovery-scripts:prod \
  --region us-west1 \
  --service-account ai2-autodiscovery-dev@ai2-aristo.iam.gserviceaccount.com \
  --set-env-vars "AUTH0_MGMT_CLIENT_ID=${AUTH0_MGMT_CLIENT_ID},AUTH0_MGMT_CLIENT_SECRET=${AUTH0_MGMT_CLIENT_SECRET}" \
  --task-timeout 29m \
  --command "uv" \
  --args "run,python,scripts/send_completion_emails.py,--acquire-lock"

gcloud scheduler jobs create http autodiscovery-send-emails-schedule-prod \
  --location us-west1 \
  --schedule "*/30 * * * *" \
  --uri "https://us-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/ai2-aristo/jobs/autodiscovery-send-emails-prod:run" \
  --http-method POST \
  --oauth-service-account-email ai2-autodiscovery-dev@ai2-aristo.iam.gserviceaccount.com \
  --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform"
```

## Dataset Cleanup Job

Deletes user-uploaded datasets older than 7 days.

**Development environment:**
```bash
gcloud run jobs create autodiscovery-dataset-cleanup-dev \
  --image us-west1-docker.pkg.dev/ai2-aristo/autodiscovery/autodiscovery-scripts:dev \
  --region us-west1 \
  --service-account ai2-autodiscovery-dev@ai2-aristo.iam.gserviceaccount.com \
  --command "uv" \
  --args "run,python,scripts/cleanup_old_datasets.py"

gcloud scheduler jobs create http autodiscovery-dataset-cleanup-schedule-dev \
  --location us-west1 \
  --schedule "0 2 * * *" \
  --uri "https://us-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/ai2-aristo/jobs/autodiscovery-dataset-cleanup-dev:run" \
  --http-method POST \
  --oauth-service-account-email ai2-autodiscovery-dev@ai2-aristo.iam.gserviceaccount.com \
  --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform"
```

**Production environment:**
```bash
gcloud run jobs create autodiscovery-dataset-cleanup-prod \
  --image us-west1-docker.pkg.dev/ai2-aristo/autodiscovery/autodiscovery-scripts:prod \
  --region us-west1 \
  --service-account ai2-autodiscovery-dev@ai2-aristo.iam.gserviceaccount.com \
  --command "uv" \
  --args "run,python,scripts/cleanup_old_datasets.py"

gcloud scheduler jobs create http autodiscovery-dataset-cleanup-schedule-prod \
  --location us-west1 \
  --schedule "0 2 * * *" \
  --uri "https://us-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/ai2-aristo/jobs/autodiscovery-dataset-cleanup-prod:run" \
  --http-method POST \
  --oauth-service-account-email ai2-autodiscovery-dev@ai2-aristo.iam.gserviceaccount.com \
  --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform"
```

## Replay Job

Simulates AutoDiscovery runs by copying and replaying existing run outputs.

**Development environment:**
```bash
gcloud run jobs create autodiscovery-replay-dev \
  --image us-west1-docker.pkg.dev/ai2-aristo/autodiscovery/autodiscovery-replay:dev \
  --region us-west1 \
  --service-account ai2-autodiscovery@ai2-aristo.iam.gserviceaccount.com \
  --max-retries 0 \
  --task-timeout 30m
```

**Production environment:**
```bash
gcloud run jobs create autodiscovery-replay-prod \
  --image us-west1-docker.pkg.dev/ai2-aristo/autodiscovery/autodiscovery-replay:prod \
  --region us-west1 \
  --service-account ai2-autodiscovery@ai2-aristo.iam.gserviceaccount.com \
  --max-retries 0 \
  --task-timeout 30m
```

## Verification

After creating the jobs, verify they exist:

```bash
# List all Cloud Run Jobs
gcloud run jobs list --region us-west1

# List all Cloud Scheduler jobs
gcloud scheduler jobs list --location us-west1
```

You should see:
- `autodiscovery-job-dev` and `autodiscovery-job-prod`
- `autodiscovery-send-emails-dev` and `autodiscovery-send-emails-prod`
- `autodiscovery-dataset-cleanup-dev` and `autodiscovery-dataset-cleanup-prod`
- `autodiscovery-replay-dev` and `autodiscovery-replay-prod`
- Corresponding scheduler jobs with `-schedule-dev` and `-schedule-prod` suffixes
