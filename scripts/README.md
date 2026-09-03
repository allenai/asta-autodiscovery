# Scripts

This directory contains scripts that run as scheduled Cloud Run Jobs, plus
`purge_user_data.py`, which is run by hand by a system maintainer.

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

---

## purge_user_data.py

Permanently erases one user's data to satisfy a GDPR "right to be forgotten"
request. **Maintainer-only and interactive** — it is not scheduled, and the
purge helpers it calls are deliberately not reachable from any HTTP route or
from `JobManager`.

Unlike `soft_delete_job` (which keeps results and metadata) and
`cleanup_old_datasets.py` (which only expires uploads past the retention
window), this preserves nothing and cannot be undone.

**What it erases:**

| Surface | Location |
|---|---|
| Uploaded datasets, results, run metadata | `gs://{bucket}/users/{sub}/**` |
| Credits profile | `gs://{bucket}/users/{sub}/user.json` |
| Shared-run index entries naming the user | `gs://{bucket}/index/shared-runs/*` |
| The user's rows in the derived metrics cache | `gs://{bucket}/_metrics/jobs_cache.json` |
| Dataset copies in the Asta workspaces bucket (with `--asta-user-uuid`) | `gs://{ASTA_BUCKET}/owners/{uuid}/**` |

**What it does not erase** — each needs its own request, and the script prints
this list on every run: asta-context-service artifacts under
`/owners/{uuid}/artifacts`, the Asta user record and threads, the Auth0 profile,
and application logs.

AutoDiscovery never persists the Auth0 `sub` → Asta user UUID mapping (it is
resolved per-request through Asta's login endpoint), so the Asta workspace UUID
has to be looked up in Asta and passed in explicitly.

### Usage

```bash
# 1. Inventory the subject's data. Deletes nothing, prompts for nothing.
uv run python scripts/purge_user_data.py --sub 'google-oauth2|123' --dry-run

# ...with every object path, not just the counts
uv run python scripts/purge_user_data.py --sub 'google-oauth2|123' --dry-run --show-paths

# 2. Purge. Prints the same inventory, then requires the sub to be retyped.
uv run python scripts/purge_user_data.py --sub 'google-oauth2|123' \
    --asta-user-uuid 00000000-0000-0000-0000-000000000000
```

The confirmation step needs a TTY, so run it attached (`docker run -it ...`) —
without one the script refuses rather than proceeding unattended. It also
refuses when the subject has jobs in a non-terminal state, since a still-running
job would write new data after the purge; cancel those first.

