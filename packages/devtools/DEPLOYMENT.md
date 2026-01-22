# Devtools Replay Job Deployment

This document describes how to deploy the replay job as a Cloud Run service.

## Build and Push Docker Image

```bash
# Build for linux/amd64 (required for Cloud Run)
docker build --platform linux/amd64 \
  -t gcr.io/ai2-aristo/autodiscovery-replay \
  -f packages/devtools/Dockerfile .

# Push to Google Container Registry
docker push gcr.io/ai2-aristo/autodiscovery-replay
```

## Create Cloud Run Job

```bash
# Set project
export CLOUDSDK_CORE_PROJECT=ai2-aristo

# Create the Cloud Run job
gcloud run jobs create autodiscovery-replay \
  --image gcr.io/ai2-aristo/autodiscovery-replay \
  --region us-west1 \
  --service-account ai2-autodiscovery@ai2-aristo.iam.gserviceaccount.com \
  --max-retries 0 \
  --task-timeout 30m
```

## Execute the Replay Job

```bash
# Execute with parameters
gcloud run jobs execute autodiscovery-replay \
  --region us-west1 \
  --args="--source=gs://ai2-autodiscovery/users/test/jobs/melanoma/output" \
  --args="--target=gs://ai2-autodiscovery/users/alice/jobs/test-123/output" \
  --args="--time-scale=0.1"
```

## Update Existing Job

```bash
# Update the image
gcloud run jobs update autodiscovery-replay \
  --image gcr.io/ai2-aristo/autodiscovery-replay \
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
