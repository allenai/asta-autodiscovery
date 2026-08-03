"""Job data persistence — the functional API over the configured object store.

This module owns the **key layout** for everything a run persists::

    users/<userid>/user.json                            # user profile
    users/<userid>/jobs/<jobid>/metadata.json           # run configuration
    users/<userid>/jobs/<jobid>/run_details.json        # execution state
    users/<userid>/jobs/<jobid>/email_state.json        # notification state
    users/<userid>/jobs/<jobid>/data/<filename>         # uploaded datasets
    users/<userid>/jobs/<jobid>/output/args.json        # resolved job args
    users/<userid>/jobs/<jobid>/output/mcts_node_*.json # experiment results
    index/shared-runs/<jobid>                           # shared-run owner index

Reads and writes go through a swappable :class:`~autodiscovery_jobs.storage.ObjectStore`
(:mod:`autodiscovery_jobs.storage`), so the same layout lives in a GCS bucket or
in a host directory depending on ``STORAGE_BACKEND``. The AD job container sees
the ``users/<userid>/jobs/<jobid>/`` subtree as a filesystem mount either way.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

from .config import JobConfig
from .exceptions import (
    JobAlreadyExistsError,
    JobNotFoundError,
    ObjectNotFoundError,
    StorageError,
)
from .storage import ObjectStore, get_store

logger = logging.getLogger(__name__)

# Root node filename - excluded from experiment counts and lists
# This is the initialization node that doesn't represent a real experiment
ROOT_NODE_FILENAME = "mcts_node_1_0.json"

# Experiment result files written by the MCTS search.
_EXPERIMENT_NODE_PATTERN = re.compile(r"mcts_node_\d+_\d+\.json$")

# Marker object used to materialize data/ and output/ for a new job. Object
# stores have no directories, so an empty placeholder is what makes the prefix
# (and therefore the job) exist. Excluded from every listing that callers see.
PLACEHOLDER_NAME = ".placeholder"


def _store(config: JobConfig | None) -> tuple[ObjectStore, JobConfig]:
    """Return the configured store alongside the config it came from.

    Falls back to the environment rather than bare dataclass defaults: with a
    swappable backend, defaulting silently would send writes to the local
    filesystem in a deployment configured for GCS.
    """
    config = config or JobConfig.from_env()
    return get_store(config), config


def _job_prefix(userid: str, jobid: str) -> str:
    """Key prefix holding everything for one run."""
    return f"users/{userid}/jobs/{jobid}/"


def parse_gcs_path(gcs_path: str) -> tuple[str, str]:
    """Parse a GCS URI into bucket and prefix.

    Retained for callers that handle ``gs://`` URIs directly (e.g. Ai2-preloaded
    dataset sources), which stay GCS-specific regardless of the active backend.

    Args:
        gcs_path: Path like "gs://bucket-name/path/to/prefix/"

    Returns:
        Tuple of (bucket_name, key_prefix)

    Example:
        >>> parse_gcs_path("gs://my-bucket/path/to/data/")
        ('my-bucket', 'path/to/data/')
    """
    # Remove gs:// prefix if present
    path = gcs_path.replace("gs://", "")

    # Split into bucket and prefix
    parts = path.split("/", 1)
    bucket_name = parts[0]
    key_prefix = parts[1] if len(parts) > 1 else ""

    # Ensure key_prefix ends with / if it's not empty
    if key_prefix and not key_prefix.endswith("/"):
        key_prefix += "/"

    return bucket_name, key_prefix


def get_user_path(userid: str, config: JobConfig | None = None) -> str:
    """Get the storage URI for a user.

    Args:
        userid: User identifier
        config: Configuration (uses default if None)

    Returns:
        URI like "gs://bucket/users/{userid}/" or "file:///data/users/{userid}/"
    """
    store, _ = _store(config)
    return store.uri(f"users/{userid}/")


def get_job_path(userid: str, jobid: str, config: JobConfig | None = None) -> str:
    """Get the storage URI for a specific job.

    Args:
        userid: User identifier
        jobid: Job identifier
        config: Configuration (uses default if None)

    Returns:
        URI like "gs://bucket/users/{userid}/jobs/{jobid}/"
    """
    store, _ = _store(config)
    return store.uri(_job_prefix(userid, jobid))


def list_user_ids(config: JobConfig | None = None) -> list[str]:
    """List all user IDs with job data.

    Args:
        config: Configuration (uses default if None)

    Returns:
        List of user IDs

    Raises:
        StorageError: If listing fails
    """
    store, _ = _store(config)
    try:
        return store.list_dirs("users/")
    except StorageError:
        raise
    except Exception as e:
        raise StorageError(f"Failed to list users: {e}")


def list_user_jobs(userid: str, config: JobConfig | None = None) -> list[str]:
    """List all jobs for a user.

    Args:
        userid: User identifier
        config: Configuration (uses default if None)

    Returns:
        List of job IDs

    Raises:
        StorageError: If listing fails
    """
    store, _ = _store(config)
    try:
        return store.list_dirs(f"users/{userid}/jobs/")
    except StorageError:
        raise
    except Exception as e:
        raise StorageError(f"Failed to list jobs for user {userid}: {e}")


def get_userid_for_job(jobid: str, config: JobConfig | None = None) -> str | None:
    """Find the user ID that owns a given job ID.

    Args:
        jobid: Job identifier
        config: Configuration (uses default if None)

    Returns:
        User ID if found, or None if not found

    Raises:
        StorageError: If listing fails
    """
    store, _ = _store(config)

    # Scans every key under users/. This is the index-miss fallback for shared-run
    # lookups (see JobManager.get_shared_run_owner), so it is a cold path; filtering
    # here rather than server-side keeps pattern matching out of the store interface.
    try:
        for info in store.list("users/"):
            # key looks like: "users/{userid}/jobs/{jobid}/metadata.json"
            parts = info.key.split("/")
            if len(parts) == 5 and parts[3] == jobid and parts[4] == "metadata.json":
                return parts[1]
        return None  # Not found
    except StorageError:
        raise
    except Exception as e:
        raise StorageError(f"Failed to find user for job {jobid}: {e}")


def _shared_run_index_key(jobid: str) -> str:
    """Return the object key for a shared run index entry."""
    return f"index/shared-runs/{jobid}"


def get_shared_run_index(jobid: str, config: JobConfig | None = None) -> str | None:
    """Look up the owner of a shared run from the index.

    Args:
        jobid: Job identifier
        config: Configuration (uses default if None)

    Returns:
        User ID if an index entry exists, None otherwise
    """
    store, _ = _store(config)
    try:
        data = json.loads(store.read_text(_shared_run_index_key(jobid)))
        return data["userid"]
    except Exception:
        return None


def write_shared_run_index(jobid: str, userid: str, config: JobConfig | None = None) -> None:
    """Write an index entry mapping a shared run to its owner.

    Args:
        jobid: Job identifier
        userid: User ID of the run owner
        config: Configuration (uses default if None)
    """
    store, _ = _store(config)
    try:
        store.write_text(
            _shared_run_index_key(jobid), json.dumps({"runid": jobid, "userid": userid})
        )
    except Exception:
        pass  # Best-effort; the glob fallback covers misses


def delete_shared_run_index(jobid: str, config: JobConfig | None = None) -> None:
    """Remove a shared run index entry.

    Args:
        jobid: Job identifier
        config: Configuration (uses default if None)
    """
    store, _ = _store(config)
    try:
        store.delete(_shared_run_index_key(jobid))
    except Exception:
        pass  # Best-effort; entry may not exist


def job_exists(userid: str, jobid: str, config: JobConfig | None = None) -> bool:
    """Check if a job directory exists.

    Args:
        userid: User identifier
        jobid: Job identifier
        config: Configuration (uses default if None)

    Returns:
        True if job exists, False otherwise
    """
    store, _ = _store(config)
    try:
        return any(store.list(_job_prefix(userid, jobid), limit=1))
    except Exception:
        return False


def create_job_directory(
    userid: str, jobid: str, config: JobConfig | None = None, overwrite: bool = False
) -> str:
    """Create a new job directory structure.

    Creates:
        users/{userid}/jobs/{jobid}/data/
        users/{userid}/jobs/{jobid}/output/

    Args:
        userid: User identifier
        jobid: Job identifier
        config: Configuration (uses default if None)
        overwrite: If True, don't raise error if job exists

    Returns:
        Storage URI of the created job directory

    Raises:
        JobAlreadyExistsError: If job exists and overwrite=False
        StorageError: If creation fails
    """
    store, config = _store(config)

    if not overwrite and job_exists(userid, jobid, config):
        raise JobAlreadyExistsError(f"Job {jobid} already exists for user {userid}")

    base = _job_prefix(userid, jobid)

    try:
        # Create placeholder files to establish directory structure
        for subdir in ["data", "output"]:
            store.write_bytes(f"{base}{subdir}/{PLACEHOLDER_NAME}", b"")

        return store.uri(base)
    except Exception as e:
        raise StorageError(f"Failed to create job directory: {e}")


def copy_job_data_files(
    source_userid: str,
    source_jobid: str,
    dest_userid: str,
    dest_jobid: str,
    config: JobConfig | None = None,
) -> list[str]:
    """Copy dataset files from one job's data/ directory to another.

    Copies within the store, so on GCS the data never flows through the API
    server.

    Args:
        source_userid: User who owns the source job
        source_jobid: Source job identifier
        dest_userid: User who owns the destination job
        dest_jobid: Destination job identifier
        config: Configuration (uses default if None)

    Returns:
        List of copied filenames

    Raises:
        StorageError: If copy fails
    """
    store, _ = _store(config)

    source_prefix = f"{_job_prefix(source_userid, source_jobid)}data/"
    dest_prefix = f"{_job_prefix(dest_userid, dest_jobid)}data/"

    copied_files: list[str] = []

    try:
        for info in store.list(source_prefix):
            filename = info.key[len(source_prefix):]
            if not filename or filename == PLACEHOLDER_NAME:
                continue
            store.copy(info.key, f"{dest_prefix}{filename}")
            copied_files.append(filename)

        return copied_files
    except Exception as e:
        raise StorageError(f"Failed to copy job data files: {e}")


def has_data_files(
    userid: str,
    jobid: str,
    config: JobConfig | None = None,
) -> bool:
    """Check if a job has any non-placeholder data files.

    Args:
        userid: User identifier
        jobid: Job identifier
        config: Configuration (uses default if None)

    Returns:
        True if the job's data/ directory contains at least one real file
    """
    store, _ = _store(config)
    prefix = f"{_job_prefix(userid, jobid)}data/"

    for info in store.list(prefix, limit=10):
        filename = info.key[len(prefix):]
        if filename and filename != PLACEHOLDER_NAME:
            return True
    return False


def delete_job_directory(userid: str, jobid: str, config: JobConfig | None = None) -> None:
    """Delete a job directory and all its contents.

    Args:
        userid: User identifier
        jobid: Job identifier
        config: Configuration (uses default if None)

    Raises:
        JobNotFoundError: If job doesn't exist
        StorageError: If deletion fails
    """
    store, config = _store(config)

    if not job_exists(userid, jobid, config):
        raise JobNotFoundError(f"Job {jobid} not found for user {userid}")

    prefix = _job_prefix(userid, jobid)

    try:
        # Materialize the listing before deleting, so mutation can't disturb it.
        for key in [info.key for info in store.list(prefix)]:
            store.delete(key)
    except Exception as e:
        raise StorageError(f"Failed to delete job directory: {e}")


def soft_delete_job(userid: str, jobid: str, config: JobConfig | None = None) -> dict[str, Any]:
    """Soft delete a job by removing user data but preserving results and metadata.

    This function:
    1. Deletes all files in data/ directory except .placeholder files
    2. Updates run_details.json to mark status as DELETED with timestamp
    3. Preserves metadata.json, run_details.json, and all output/ files

    This operation is idempotent - can be called multiple times safely.

    Args:
        userid: User identifier
        jobid: Job identifier
        config: Configuration (uses default if None)

    Returns:
        Dictionary with keys:
        - deleted_files: List of storage URIs that were deleted
        - preserved_files: Count of preserved files
        - status: "DELETED"
        - deleted_at: ISO timestamp

    Raises:
        JobNotFoundError: If job doesn't exist
        StorageError: If deletion or status update fails
    """
    from datetime import UTC, datetime

    store, config = _store(config)

    if not job_exists(userid, jobid, config):
        raise JobNotFoundError(f"Job {jobid} not found for user {userid}")

    job_prefix = _job_prefix(userid, jobid)
    data_prefix = f"{job_prefix}data/"
    deleted_files = []

    try:
        for key in [info.key for info in store.list(data_prefix)]:
            # Skip placeholder files
            if key.endswith(PLACEHOLDER_NAME):
                continue

            deleted_files.append(store.uri(key))
            store.delete(key)

        # Count preserved files (metadata.json, run_details.json, output/*)
        preserved_count = sum(1 for _ in store.list(job_prefix))

        # Update run_details.json to mark as DELETED
        from .run_details import update_run_details

        deleted_at = datetime.now(UTC).isoformat()
        update_run_details(
            userid,
            jobid,
            {
                "status": "DELETED",
                "status_checked_at": deleted_at,
            },
            config,
        )

        return {
            "deleted_files": deleted_files,
            "preserved_files": preserved_count,
            "status": "DELETED",
            "deleted_at": deleted_at,
        }

    except Exception as e:
        raise StorageError(f"Failed to soft delete job: {e}")


def upload_dataset(
    userid: str,
    jobid: str,
    local_path: Path,
    config: JobConfig | None = None,
    remote_name: str | None = None,
) -> str:
    """Upload dataset file(s) to job's data directory.

    Args:
        userid: User identifier
        jobid: Job identifier
        local_path: Local file or directory path
        config: Configuration (uses default if None)
        remote_name: Optional remote filename (only for single files)

    Returns:
        Storage URI of the data directory

    Raises:
        JobNotFoundError: If job doesn't exist
        StorageError: If upload fails
    """
    store, config = _store(config)
    local_path = Path(local_path)

    if not job_exists(userid, jobid, config):
        raise JobNotFoundError(f"Job {jobid} not found for user {userid}")

    data_prefix = f"{_job_prefix(userid, jobid)}data/"

    try:
        if local_path.is_file():
            # Upload single file
            filename = remote_name or local_path.name
            store.upload_file(f"{data_prefix}{filename}", local_path)
        elif local_path.is_dir():
            # Upload directory contents
            for file_path in local_path.rglob("*"):
                if file_path.is_file():
                    relative_path = file_path.relative_to(local_path)
                    store.upload_file(f"{data_prefix}{relative_path.as_posix()}", file_path)
        else:
            raise StorageError(f"Path not found: {local_path}")

        return store.uri(data_prefix)
    except Exception as e:
        raise StorageError(f"Failed to upload dataset: {e}")


def expire_datasets(
    userid: str,
    jobid: str,
    max_age_days: int,
    dry_run: bool,
    config: JobConfig | None = None,
) -> list[str]:
    """Delete uploaded dataset files from job's data directory.

    This removes all files in the data/ directory to comply with data retention
    policies. Job metadata, results, and other files are preserved.

    Args:
        userid: User identifier
        jobid: Job identifier
        max_age_days: Only delete files older than this many days
        dry_run: If True, don't delete files, just return what would be deleted
        config: Configuration (uses default if None)

    Returns:
        List of storage URIs that were deleted (or would be deleted if dry_run=True)

    Raises:
        JobNotFoundError: If job doesn't exist
        StorageError: If deletion fails
    """
    from datetime import UTC, datetime, timedelta

    store, config = _store(config)

    if not job_exists(userid, jobid, config):
        raise JobNotFoundError(f"Job {jobid} not found for user {userid}")

    prefix = f"{_job_prefix(userid, jobid)}data/"

    # Calculate cutoff time
    cutoff_time = datetime.now(UTC) - timedelta(days=max_age_days)

    try:
        expired_paths = []

        for info in list(store.list(prefix)):
            # Skip placeholder files
            if info.key.endswith(PLACEHOLDER_NAME):
                continue

            # Check age
            if not info.created_at or info.created_at >= cutoff_time:
                continue

            # Record the path
            expired_paths.append(store.uri(info.key))

            # Delete if not dry run
            if not dry_run:
                logger.info("Deleting dataset file: %s", store.uri(info.key))
                store.delete(info.key)

        return expired_paths
    except Exception as e:
        raise StorageError(f"Failed to expire datasets: {e}")


def upload_metadata(
    userid: str, jobid: str, metadata: dict[str, Any], config: JobConfig | None = None
) -> str:
    """Upload metadata.json to job directory.

    Args:
        userid: User identifier
        jobid: Job identifier
        metadata: Metadata dictionary
        config: Configuration (uses default if None)

    Returns:
        Storage URI of the uploaded metadata

    Raises:
        JobNotFoundError: If job doesn't exist
        StorageError: If upload fails
    """
    store, config = _store(config)

    if not job_exists(userid, jobid, config):
        raise JobNotFoundError(f"Job {jobid} not found for user {userid}")

    key = f"{_job_prefix(userid, jobid)}metadata.json"

    try:
        store.write_text(key, json.dumps(metadata, indent=2), content_type="application/json")
        return store.uri(key)
    except Exception as e:
        raise StorageError(f"Failed to upload metadata: {e}")


def upload_job_args(
    userid: str, jobid: str, args: dict[str, Any], config: JobConfig | None = None
) -> str:
    """Upload args.json to job's output directory.

    Args:
        userid: User identifier
        jobid: Job identifier
        args: Arguments dictionary
        config: Configuration (uses default if None)

    Returns:
        Storage URI of the saved args file

    Raises:
        JobNotFoundError: If job doesn't exist
        StorageError: If upload fails
    """
    store, config = _store(config)

    if not job_exists(userid, jobid, config):
        raise JobNotFoundError(f"Job {jobid} not found for user {userid}")

    key = f"{_job_prefix(userid, jobid)}output/args.json"

    try:
        store.write_text(key, json.dumps(args, indent=2), content_type="application/json")
        return store.uri(key)
    except Exception as e:
        raise StorageError(f"Failed to save job args: {e}")


def get_metadata(userid: str, jobid: str, config: JobConfig | None = None) -> dict[str, Any]:
    """Download and parse metadata.json from job directory.

    Args:
        userid: User identifier
        jobid: Job identifier
        config: Configuration (uses default if None)

    Returns:
        Metadata dictionary

    Raises:
        JobNotFoundError: If job doesn't exist
        StorageError: If download fails
    """
    store, config = _store(config)

    key = f"{_job_prefix(userid, jobid)}metadata.json"

    # Read directly instead of pre-checking existence with a separate list
    # request. On a miss we fall back to job_exists() only to preserve the
    # historical exception contract (JobNotFoundError vs StorageError); the common
    # case where metadata.json exists costs a single round-trip.
    try:
        return json.loads(store.read_text(key))
    except ObjectNotFoundError:
        if not job_exists(userid, jobid, config):
            raise JobNotFoundError(f"Job {jobid} not found for user {userid}") from None
        raise StorageError(
            f"Failed to download metadata: metadata.json not found for job {jobid}"
        ) from None
    except Exception as e:
        raise StorageError(f"Failed to download metadata: {e}")


def get_job_results(userid: str, jobid: str, config: JobConfig | None = None) -> list[str]:
    """List all result files from a job's output directory.

    Args:
        userid: User identifier
        jobid: Job identifier
        config: Configuration (uses default if None)

    Returns:
        List of storage URIs of result files

    Raises:
        JobNotFoundError: If job doesn't exist
        StorageError: If listing fails
    """
    store, config = _store(config)

    if not job_exists(userid, jobid, config):
        raise JobNotFoundError(f"Job {jobid} not found for user {userid}")

    prefix = f"{_job_prefix(userid, jobid)}output/"

    try:
        return [
            store.uri(info.key)
            for info in store.list(prefix)
            if not info.key.endswith(PLACEHOLDER_NAME)
        ]
    except Exception as e:
        raise StorageError(f"Failed to list job results: {e}")


def download_job_results(
    userid: str, jobid: str, local_dir: Path, config: JobConfig | None = None
) -> list[Path]:
    """Download all job results to a local directory.

    Args:
        userid: User identifier
        jobid: Job identifier
        local_dir: Local directory to download to
        config: Configuration (uses default if None)

    Returns:
        List of local file paths that were downloaded

    Raises:
        JobNotFoundError: If job doesn't exist
        StorageError: If download fails
    """
    store, config = _store(config)
    local_dir = Path(local_dir)
    local_dir.mkdir(parents=True, exist_ok=True)

    if not job_exists(userid, jobid, config):
        raise JobNotFoundError(f"Job {jobid} not found for user {userid}")

    prefix = f"{_job_prefix(userid, jobid)}output/"

    try:
        downloaded = []

        for info in store.list(prefix):
            # Skip placeholder files
            if info.key.endswith(PLACEHOLDER_NAME):
                continue

            # Get relative path from output/ directory
            local_path = local_dir / info.key[len(prefix):]

            # Create parent directories
            local_path.parent.mkdir(parents=True, exist_ok=True)

            store.download_file(info.key, local_path)
            downloaded.append(local_path)

        return downloaded
    except Exception as e:
        raise StorageError(f"Failed to download job results: {e}")


def count_experiment_results(userid: str, jobid: str, config: JobConfig | None = None) -> int:
    """Count completed experiment result files in a job's output directory.

    Counts files matching the pattern: mcts_node_{level}_{index}.json

    Args:
        userid: User identifier
        jobid: Job identifier
        config: Configuration (uses default if None)

    Returns:
        Number of experiment result files found (0 if error or none found)

    Example:
        >>> count_experiment_results("user123", "job456")
        5
    """
    store, _ = _store(config)

    prefix = f"{_job_prefix(userid, jobid)}output/"

    try:
        count = 0
        for info in store.list(prefix, limit=10000):
            filename = info.key.split("/")[-1]
            if _EXPERIMENT_NODE_PATTERN.match(filename) and filename != ROOT_NODE_FILENAME:
                count += 1
        return count
    except Exception as e:
        # Log error but return 0 to allow graceful degradation
        logging.error(f"Failed to count experiment results for job {jobid}: {e}")
        return 0


def get_job_args(userid: str, jobid: str, config: JobConfig | None = None) -> dict | None:
    """Read and parse args.json from a job's output directory.

    Args:
        userid: User identifier
        jobid: Job identifier
        config: Configuration (uses default if None)

    Returns:
        Dictionary containing job arguments, or None if file doesn't exist or parsing fails

    Example:
        >>> args = get_job_args("user123", "job456")
        >>> args.get("n_experiments", 0)
        10
    """
    store, _ = _store(config)

    key = f"{_job_prefix(userid, jobid)}output/args.json"

    # Read directly rather than pre-checking existence with a separate
    # request; a miss surfaces as ObjectNotFoundError and is handled like before.
    try:
        return json.loads(store.read_text(key))
    except ObjectNotFoundError:
        logging.warning(f"args.json not found for job {jobid}")
        return None
    except json.JSONDecodeError as e:
        logging.warning(f"Invalid JSON in args.json for job {jobid}: {e}")
        return None
    except Exception as e:
        logging.error(f"Failed to read args.json for job {jobid}: {e}")
        return None


def list_experiment_files(userid: str, jobid: str, config: JobConfig | None = None) -> list[str]:
    """List all experiment node files in a job's output directory.

    Lists files matching the pattern: mcts_node_{level}_{index}.json

    Args:
        userid: User identifier
        jobid: Job identifier
        config: Configuration (uses default if None)

    Returns:
        List of filenames (not full paths)

    Raises:
        JobNotFoundError: If job doesn't exist
        StorageError: If listing fails
    """
    store, config = _store(config)

    if not job_exists(userid, jobid, config):
        raise JobNotFoundError(f"Job {jobid} not found for user {userid}")

    prefix = f"{_job_prefix(userid, jobid)}output/"

    try:
        filenames = []
        for info in store.list(prefix):
            filename = info.key.split("/")[-1]
            if _EXPERIMENT_NODE_PATTERN.match(filename) and filename != ROOT_NODE_FILENAME:
                filenames.append(filename)
        return sorted(filenames)
    except Exception as e:
        raise StorageError(f"Failed to list experiment files for job {jobid}: {e}")


def read_experiment_node(
    userid: str, jobid: str, filename: str, config: JobConfig | None = None
) -> dict | None:
    """Read and parse a single experiment node JSON file.

    Args:
        userid: User identifier
        jobid: Job identifier
        filename: Experiment node filename (e.g., "mcts_node_0_0.json")
        config: Configuration (uses default if None)

    Returns:
        Dictionary containing parsed node data, or None if file doesn't exist or parsing fails

    Example:
        >>> node = read_experiment_node("user123", "job456", "mcts_node_0_0.json")
        >>> node.get("id")
        "node_0_0"
    """
    store, _ = _store(config)

    key = f"{_job_prefix(userid, jobid)}output/{filename}"

    try:
        return json.loads(store.read_text(key))
    except ObjectNotFoundError:
        logging.warning(f"Experiment node file not found: {filename} for job {jobid}")
        return None
    except json.JSONDecodeError as e:
        logging.warning(f"Invalid JSON in {filename} for job {jobid}: {e}")
        return None
    except Exception as e:
        logging.error(f"Failed to read experiment node {filename} for job {jobid}: {e}")
        return None


def read_rich_outputs(
    userid: str,
    jobid: str,
    level: int,
    index: int,
    config: JobConfig | None = None,
) -> list[dict[str, Any]]:
    """Read rich output bundles for a specific experiment node.

    Args:
        userid: User identifier
        jobid: Job identifier
        level: Node level in the MCTS tree
        index: Node index in the MCTS tree
        config: Configuration (uses default if None)

    Returns:
        List of rich output bundles (each bundle is a MIME-type keyed dict).
        Returns an empty list when no rich outputs are found or parsing fails.
    """
    store, _ = _store(config)

    filename = f"ro_{level}_{index}.json"
    key = f"{_job_prefix(userid, jobid)}output/rich_outputs/{filename}"

    try:
        parsed = json.loads(store.read_text(key))
        if not isinstance(parsed, list):
            logging.warning(
                "Invalid rich output payload in %s for job %s: expected list",
                filename,
                jobid,
            )
            return []
        return parsed
    except ObjectNotFoundError:
        logging.warning("Rich output file not found: %s for job %s", filename, jobid)
        return []
    except json.JSONDecodeError as e:
        logging.warning(f"Invalid JSON in {filename} for job {jobid}: {e}")
        return []
    except Exception as e:
        logging.error(f"Failed to read rich outputs {filename} for job {jobid}: {e}")
        return []


def dataset_key(userid: str, jobid: str, filename: str) -> str:
    """Return the object key an uploaded dataset file lands at.

    Exposed so the API can accept a browser upload itself (for backends without
    presigned URLs) and write it to exactly the same key.

    Args:
        userid: User identifier
        jobid: Job identifier
        filename: Uploaded file's name

    Returns:
        Object key under the job's data/ prefix.
    """
    return f"{_job_prefix(userid, jobid)}data/{filename}"


def generate_upload_url(
    userid: str,
    jobid: str,
    filename: str,
    content_type: str = "application/octet-stream",
    expiration_seconds: int = 3600,  # 1 hour default
    config: JobConfig | None = None,
) -> dict[str, Any]:
    """Generate a URL the browser can upload a dataset file directly to.

    Backends that support capability URLs (GCS presigned URLs) return one, so the
    bytes never touch the application server. Backends without that notion (the
    filesystem store) return ``upload_url=None``, and the caller is responsible
    for receiving the upload itself and writing it to ``storage_path``.

    Args:
        userid: User identifier
        jobid: Job identifier
        filename: Name of file to upload
        content_type: MIME type of the file
        expiration_seconds: Number of seconds until URL expires (default: 3600 = 1 hour)
        config: Configuration (uses default if None)

    Returns:
        Dictionary with:
        - upload_url: Direct-upload URL, or None if the backend has none
        - storage_path: URI the file will be stored at
        - key: Object key the file will be stored at

    Raises:
        JobNotFoundError: If job doesn't exist
        StorageError: If URL generation fails

    Example:
        >>> result = generate_upload_url("user123", "job456", "data.csv", "text/csv")
        >>> result['upload_url']
        'https://storage.googleapis.com/...'
        >>> result['storage_path']
        'gs://example-bucket/users/user123/jobs/job456/data/data.csv'
    """
    store, config = _store(config)

    # Verify job exists
    if not job_exists(userid, jobid, config):
        raise JobNotFoundError(f"Job {jobid} not found for user {userid}")

    key = dataset_key(userid, jobid, filename)

    try:
        upload_url = store.signed_upload_url(key, content_type, expiration_seconds)
    except Exception as e:
        raise StorageError(f"Failed to generate upload URL: {e}")

    return {
        "upload_url": upload_url,
        "storage_path": store.uri(key),
        "key": key,
    }
