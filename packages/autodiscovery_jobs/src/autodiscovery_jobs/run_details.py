"""Service for managing run_details.json files in GCS.

This module provides functions for creating, reading, and updating run details
stored in GCS. Each run has a run_details.json file that tracks execution state.

Schema:
    {
        "execution_id": str | None,      # Cloud Run execution ID
        "created_at": str,                # ISO timestamp when run was created
        "status": str,                    # CREATED, PENDING, RUNNING, SUCCEEDED, FAILED, CANCELLED
        "status_checked_at": str | None,  # ISO timestamp of last status check
        "completed_at": str | None,       # ISO timestamp when job completed (SUCCEEDED/FAILED/CANCELLED)
    }
"""

import json
from datetime import UTC, datetime
from typing import Any

from google.cloud import storage

from .config import JobConfig


# Terminal statuses that indicate job completion
TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "CANCELLED"}


def get_run_details_path(userid: str, runid: str) -> str:
    """Get the GCS blob path for run_details.json.

    Args:
        userid: User identifier
        runid: Run identifier

    Returns:
        Blob path for run_details.json
    """
    return f"users/{userid}/jobs/{runid}/run_details.json"


def create_run_details(
    userid: str,
    runid: str,
    config: JobConfig | None = None,
) -> dict[str, Any]:
    """Create initial run_details.json file.

    Args:
        userid: User identifier
        runid: Run identifier
        config: Job configuration (uses default if None)

    Returns:
        The created run details dictionary
    """
    config = config or JobConfig.from_env()
    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)

    run_details = {
        "execution_id": None,
        "created_at": datetime.now(UTC).isoformat(),
        "status": "CREATED",
        "status_checked_at": None,
        "completed_at": None,
    }

    blob_path = get_run_details_path(userid, runid)
    blob = bucket.blob(blob_path)
    blob.upload_from_string(json.dumps(run_details, indent=2))

    return run_details


def get_run_details(
    userid: str,
    runid: str,
    config: JobConfig | None = None,
) -> dict[str, Any] | None:
    """Get run details from GCS.

    Args:
        userid: User identifier
        runid: Run identifier
        config: Job configuration (uses default if None)

    Returns:
        Run details dictionary, or None if not found
    """
    config = config or JobConfig.from_env()
    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)

    blob_path = get_run_details_path(userid, runid)
    blob = bucket.blob(blob_path)

    try:
        content = blob.download_as_text()
        return json.loads(content)
    except Exception:
        pass

    return None


def update_run_details(
    userid: str,
    runid: str,
    updates: dict[str, Any],
    config: JobConfig | None = None,
) -> dict[str, Any]:
    """Update run details in GCS.

    Automatically sets completed_at when status changes to a terminal status.

    Args:
        userid: User identifier
        runid: Run identifier
        updates: Dictionary of fields to update
        config: Job configuration (uses default if None)

    Returns:
        Updated run details dictionary
    """
    config = config or JobConfig.from_env()
    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)

    # Get existing details
    run_details = get_run_details(userid, runid, config)
    if not run_details:
        run_details = {
            "execution_id": None,
            "created_at": datetime.now(UTC).isoformat(),
            "status": "CREATED",
            "status_checked_at": None,
            "completed_at": None,
        }

    # Check if this update transitions to a terminal status
    old_status = run_details.get("status")
    new_status = updates.get("status")
    if (
        new_status
        and new_status in TERMINAL_STATUSES
        and old_status not in TERMINAL_STATUSES
        and not run_details.get("completed_at")
    ):
        updates["completed_at"] = datetime.now(UTC).isoformat()

    # Update fields
    run_details.update(updates)

    # Save back to GCS
    blob_path = get_run_details_path(userid, runid)
    blob = bucket.blob(blob_path)
    blob.upload_from_string(json.dumps(run_details, indent=2))

    return run_details


def is_completed(run_details: dict[str, Any] | None) -> bool:
    """Check if a run has completed (terminal status).

    Args:
        run_details: Run details dictionary

    Returns:
        True if the run has a terminal status
    """
    if not run_details:
        return False
    return run_details.get("status") in TERMINAL_STATUSES


def get_completed_at(run_details: dict[str, Any] | None) -> datetime | None:
    """Get the completion timestamp from run details.

    Args:
        run_details: Run details dictionary

    Returns:
        Completion datetime, or None if not completed or not recorded
    """
    if not run_details:
        return None
    completed_at = run_details.get("completed_at")
    if completed_at:
        return datetime.fromisoformat(completed_at)
    return None
