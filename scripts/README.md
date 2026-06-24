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
- Files matching: `gs://example-bucket/users/*/jobs/*/data/*`
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

