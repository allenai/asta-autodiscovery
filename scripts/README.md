# Scripts

## cleanup_old_datasets.py

Deletes user-uploaded dataset files older than 7 days from GCS to comply with data retention policies.

**What it deletes:**
- Files matching: `gs://example-gcp-project/users/*/jobs/*/data/*`
- Older than 7 days (based on GCS creation time)

### Usage

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

### Deployment

This script is deployed as a Cloud Run Job triggered by Cloud Scheduler.

#### Setup

1. **Build and push container:**
   ```bash
   gcloud builds submit --tag gcr.io/example-legacy-project/autodiscovery-dataset-cleanup --file scripts/Dockerfile .
   ```

   This builds from the repo root using the Dockerfile in scripts/.

2. **Create Cloud Run Job:**
   ```bash
   gcloud run jobs create autodiscovery-dataset-cleanup \
     --image gcr.io/example-legacy-project/autodiscovery-dataset-cleanup \
     --region us-west1 \
     --command "uv" \
     --args "run,python,scripts/cleanup_old_datasets.py,--dry-run"
   ```

   Note: Currently configured with `--dry-run` for safety. Remove `--dry-run` from args once validated. Uses the default compute service account. Add `--service-account <email>` if you need a specific service account.

3. **Schedule with Cloud Scheduler:**
   ```bash
   project_number=$(gcloud projects describe example-legacy-project --format="value(projectNumber)")
   gcloud scheduler jobs create http autodiscovery-dataset-cleanup-schedule \
     --location us-west1 \
     --schedule "0 2 * * *" \
     --uri "https://us-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/example-legacy-project/jobs/autodiscovery-dataset-cleanup:run" \
     --http-method POST \
     --oidc-service-account-email ${project_number}-compute@developer.gserviceaccount.com
   ```

   This runs daily at 2 AM. Replace `<PROJECT_NUMBER>` with your GCP project number (find with ``).

#### Updating

To update the script:
```bash
# Rebuild and push
gcloud builds submit --tag gcr.io/example-legacy-project/autodiscovery-dataset-cleanup --file scripts/Dockerfile .

# Update the job to use the new image
gcloud run jobs update autodiscovery-dataset-cleanup \
  --image gcr.io/example-legacy-project/autodiscovery-dataset-cleanup \
  --region us-west1
```

### Required Permissions

The service account running this script needs:
- `storage.objects.list` on the bucket
- `storage.objects.delete` on the bucket

Or simply the `roles/storage.objectAdmin` role.
