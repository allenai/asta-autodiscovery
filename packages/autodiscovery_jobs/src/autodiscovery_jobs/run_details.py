"""Service for managing run_details.json files in GCS.

This module provides a RunDetails data class and functions for creating,
reading, and updating run details stored in GCS. Each run has a run_details.json
file that tracks execution state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from google.cloud import storage

from .config import JobConfig


# Terminal statuses that indicate job completion
TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "CANCELLED", "DELETED"}


@dataclass
class RunDetails:
    """Data class representing run details stored in GCS.

    Attributes:
        execution_id: Cloud Run execution ID
        created_at: ISO timestamp when run was created
        status: CREATED, PENDING, RUNNING, SUCCEEDED, FAILED, CANCELLED, DELETED
        status_checked_at: ISO timestamp of last status check
        finished_at_raw: ISO timestamp when job finished (terminal status)
        origin_url: Base URL where the run was submitted from (e.g., https://asta.allenai.org)
    """

    execution_id: str | None = None
    created_at: str = ""
    status: str = "CREATED"
    status_checked_at: str | None = None
    finished_at_raw: str | None = field(default=None, metadata={"json_key": "finished_at"})
    origin_url: str | None = None

    @property
    def finished_at(self) -> datetime | None:
        """Get the finish timestamp as a datetime object."""
        if self.finished_at_raw:
            return datetime.fromisoformat(self.finished_at_raw)
        return None

    @property
    def is_finished(self) -> bool:
        """Check if the run has finished (terminal status)."""
        return self.status in TERMINAL_STATUSES

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "execution_id": self.execution_id,
            "created_at": self.created_at,
            "status": self.status,
            "status_checked_at": self.status_checked_at,
            "finished_at": self.finished_at_raw,
            "origin_url": self.origin_url,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunDetails:
        """Create from dictionary (e.g., from JSON)."""
        return cls(
            execution_id=data.get("execution_id"),
            created_at=data.get("created_at", ""),
            status=data.get("status", "CREATED"),
            status_checked_at=data.get("status_checked_at"),
            finished_at_raw=data.get("finished_at"),
            origin_url=data.get("origin_url"),
        )

    @classmethod
    def create_new(cls) -> RunDetails:
        """Create a new RunDetails with current timestamp."""
        return cls(
            created_at=datetime.now(UTC).isoformat(),
            status="CREATED",
        )


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
) -> RunDetails:
    """Create initial run_details.json file.

    Args:
        userid: User identifier
        runid: Run identifier
        config: Job configuration (uses default if None)

    Returns:
        The created RunDetails object
    """
    config = config or JobConfig.from_env()
    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)

    run_details = RunDetails.create_new()

    blob_path = get_run_details_path(userid, runid)
    blob = bucket.blob(blob_path)
    blob.upload_from_string(json.dumps(run_details.to_dict(), indent=2))

    return run_details


def get_run_details(
    userid: str,
    runid: str,
    config: JobConfig | None = None,
) -> RunDetails | None:
    """Get run details from GCS.

    Args:
        userid: User identifier
        runid: Run identifier
        config: Job configuration (uses default if None)

    Returns:
        RunDetails object, or None if not found
    """
    config = config or JobConfig.from_env()
    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)

    blob_path = get_run_details_path(userid, runid)
    blob = bucket.blob(blob_path)

    try:
        content = blob.download_as_text()
        data = json.loads(content)
        return RunDetails.from_dict(data)
    except Exception:
        return None


def update_run_details(
    userid: str,
    runid: str,
    updates: dict[str, Any],
    config: JobConfig | None = None,
) -> RunDetails:
    """Update run details in GCS.

    Args:
        userid: User identifier
        runid: Run identifier
        updates: Dictionary of fields to update
        config: Job configuration (uses default if None)

    Returns:
        Updated RunDetails object
    """
    config = config or JobConfig.from_env()
    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)

    # Get existing details
    run_details = get_run_details(userid, runid, config)
    if not run_details:
        run_details = RunDetails.create_new()

    run_details_dict = run_details.to_dict()

    # Update fields
    run_details_dict.update(updates)

    # Save back to GCS
    blob_path = get_run_details_path(userid, runid)
    blob = bucket.blob(blob_path)
    blob.upload_from_string(json.dumps(run_details_dict, indent=2))

    return RunDetails.from_dict(run_details_dict)


def refresh_run_status(
    userid: str,
    runid: str,
    config: JobConfig | None = None,
) -> RunDetails | None:
    """Get run details, refreshing status from Cloud Run if not yet finished.

    This function:
    1. Fetches run details from GCS
    2. If the run is already finished (terminal status), returns as-is
    3. If not finished and has an execution_id, queries Cloud Run for current status
    4. Updates and persists the new status if changed

    Use this instead of get_run_details when you need the most up-to-date status.

    Args:
        userid: User identifier
        runid: Run identifier
        config: Job configuration (uses default if None)

    Returns:
        RunDetails object with refreshed status, or None if not found
    """
    from .cloudrun import get_job_status

    config = config or JobConfig.from_env()

    # Get current run details
    run_details = get_run_details(userid, runid, config)
    if not run_details:
        return None

    # If no execution_id, can't query Cloud Run
    if not run_details.execution_id:
        return run_details

    # Query Cloud Run for current status
    try:
        status_response = get_job_status(run_details.execution_id, config)
        phase = status_response.get("phase", status_response.get("status", "UNKNOWN"))
        created_at = status_response.get("create_time", run_details.created_at)
        finished_at = status_response.get("completion_time")

        # Build update dict
        updates = {
            "status": phase,
            "status_checked_at": datetime.now(UTC).isoformat(),
        }

        if created_at:
            if isinstance(created_at, datetime):
                updates["created_at"] = created_at.isoformat()
            else:
                updates["created_at"] = created_at


        # Only include finished_at if present and ensure it's formatted correctly
        if finished_at:
            if isinstance(finished_at, datetime):
                updates["finished_at"] = finished_at.isoformat()
            else:
                updates["finished_at"] = finished_at


        # Update run details with new status
        run_details = update_run_details(
            userid,
            runid,
            updates,
            config,
        )
    except Exception:
        # If we can't reach Cloud Run, return what we have
        pass

    return run_details
