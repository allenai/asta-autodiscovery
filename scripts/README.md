# Scripts

## cleanup_old_datasets.py

Deletes user-uploaded dataset files older than 7 days from GCS to comply with data retention policies.

**What it deletes:**
- Files matching: `gs://example-gcp-project/users/*/jobs/*/data/*`
- Older than 7 days (based on GCS creation time)

**What it preserves:**
- Job results: `users/*/jobs/*/output/*`
- Metadata: `users/*/jobs/*/metadata.json`
- Run details: `users/*/jobs/*/run_details.json`

### Usage

**Test with dry run:**
```bash
uv run python scripts/cleanup_old_datasets.py --dry-run
```

**Run cleanup:**
```bash
uv run python scripts/cleanup_old_datasets.py
```

**Custom bucket or age:**
```bash
uv run python scripts/cleanup_old_datasets.py --bucket my-bucket --max-age-days 3
```

### Deployment Options

#### Option 1: Cloud Scheduler + Cloud Run Job (Recommended)

1. **Build and push container:**
   ```bash
   gcloud builds submit --tag gcr.io/PROJECT_ID/dataset-cleanup
   ```

2. **Create Cloud Run Job:**
   ```bash
   gcloud run jobs create dataset-cleanup \
     --image gcr.io/PROJECT_ID/dataset-cleanup \
     --region us-west1 \
     --service-account autodiscovery-sa@PROJECT_ID.iam.gserviceaccount.com \
     --command "python" \
     --args "scripts/cleanup_old_datasets.py"
   ```

3. **Schedule with Cloud Scheduler:**
   ```bash
   gcloud scheduler jobs create http dataset-cleanup-schedule \
     --location us-west1 \
     --schedule "0 2 * * *" \
     --uri "https://us-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/PROJECT_ID/jobs/dataset-cleanup:run" \
     --http-method POST \
     --oauth-service-account-email autodiscovery-sa@PROJECT_ID.iam.gserviceaccount.com
   ```

   This runs daily at 2 AM.

#### Option 2: Cloud Function

Deploy as a Cloud Function triggered by Cloud Scheduler (simpler but less flexible).

#### Option 3: Manual/Cron

Run manually or via cron on a VM:
```bash
0 2 * * * cd /path/to/repo && uv run python scripts/cleanup_old_datasets.py
```

### Required Permissions

The service account running this script needs:
- `storage.objects.list` on the bucket
- `storage.objects.delete` on the bucket

Or simply the `roles/storage.objectAdmin` role.
