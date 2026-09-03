"""GCS operations for the Asta workspace bucket.

The manifest and dataset metadata writes now go through asta-context-service
(see api/utils/asta_context_client.py) so they are tracked. This module retains
only the server-side dataset copy.
"""

import logging
import os

from google.cloud import storage

from .config import JobConfig

_log = logging.getLogger(__name__)

ASTA_BUCKET = os.environ.get("ASTA_BUCKET", "example-workspaces-project")


def copy_dataset_to_asta_workspace(
    ad_userid: str,
    ad_runid: str,
    user_uuid: str,
    thread_id: str,
    ad_config: JobConfig,
) -> int:
    """Copy AD run dataset files into the Asta workspace bucket.

    Uses server-side GCS copy so no data flows through the API server.
    Copies everything under users/{ad_userid}/jobs/{ad_runid}/data/ into
    owners/{user_uuid}/{thread_id}/data/ in ASTA_BUCKET.

    Args:
        ad_userid: AD user identifier
        ad_runid: AD run/job identifier
        user_uuid: Asta user UUID
        thread_id: Pre-generated thread UUID
        ad_config: AD JobConfig (provides the source bucket name)

    Returns:
        List of GCS URIs of the copied dataset files

    Raises:
        google.cloud.exceptions.GoogleCloudError: If the copy fails
    """
    client = storage.Client()
    ad_bucket = client.bucket(ad_config.bucket)
    asta_bucket = client.bucket(ASTA_BUCKET)

    source_prefix = f"users/{ad_userid}/jobs/{ad_runid}/data/"
    dest_prefix = f"owners/{user_uuid}/{thread_id}/data/"

    uris: list[str] = []
    for blob in client.list_blobs(ad_config.bucket, prefix=source_prefix):
        filename = blob.name[len(source_prefix):]
        if not filename or filename == ".placeholder":
            continue
        dest_blob_name = f"{dest_prefix}{filename}"
        ad_bucket.copy_blob(blob, asta_bucket, dest_blob_name)
        uri = f"gs://{ASTA_BUCKET}/{dest_blob_name}"
        uris.append(uri)
        _log.info("Copied %s → %s", blob.name, uri)

    return uris


# ---------------------------------------------------------------------------
# Per-user erasure (maintainer-only)
#
# The copy step above leaves a second copy of a user's datasets in the Asta
# workspaces bucket, keyed by the Asta user UUID rather than the Auth0 sub. A
# right-to-be-forgotten purge has to reach both. As with the primary-bucket
# purge in gcs.py, these are called only from scripts/purge_user_data.py and are
# deliberately not exposed on any HTTP route.
# ---------------------------------------------------------------------------


def _validate_user_uuid(user_uuid: str) -> str:
    """Reject Asta user UUIDs that would widen a purge beyond one owner.

    Args:
        user_uuid: Candidate Asta user UUID.

    Returns:
        The validated UUID.

    Raises:
        ValueError: If the UUID is empty or contains a path separator.
    """
    if not user_uuid or not user_uuid.strip():
        raise ValueError("user_uuid must be a non-empty string")
    if "/" in user_uuid:
        raise ValueError(f"user_uuid must not contain '/': {user_uuid!r}")
    return user_uuid


def summarize_asta_workspace_data(user_uuid: str) -> dict[str, object]:
    """Inventory the workspace-bucket objects owned by an Asta user.

    Args:
        user_uuid: Asta user UUID (the ``owners/{uuid}/`` key, not the Auth0 sub).

    Returns:
        Dictionary with ``user_uuid``, ``bucket``, ``object_count``,
        ``total_bytes``, ``thread_ids`` and the full sorted ``object_paths``.

    Raises:
        ValueError: If ``user_uuid`` is empty or contains a path separator.
    """
    _validate_user_uuid(user_uuid)

    client = storage.Client()
    bucket = client.bucket(ASTA_BUCKET)
    prefix = f"owners/{user_uuid}/"

    object_paths: list[str] = []
    total_bytes = 0
    thread_ids: set[str] = set()

    for blob in bucket.list_blobs(prefix=prefix):
        object_paths.append(blob.name)
        total_bytes += blob.size or 0
        remainder = blob.name[len(prefix) :]
        thread_id = remainder.split("/", 1)[0]
        if thread_id:
            thread_ids.add(thread_id)

    return {
        "user_uuid": user_uuid,
        "bucket": ASTA_BUCKET,
        "object_count": len(object_paths),
        "total_bytes": total_bytes,
        "thread_ids": sorted(thread_ids),
        "object_paths": sorted(object_paths),
    }


def purge_asta_workspace_data(user_uuid: str, dry_run: bool = False) -> dict[str, object]:
    """Permanently delete everything under ``owners/{user_uuid}/`` in ASTA_BUCKET.

    Removes the dataset copies :func:`copy_dataset_to_asta_workspace` wrote.
    **There is no recovery path.** This does not touch artifacts registered with
    asta-context-service (``/owners/{owner_id}/artifacts``), which is a separate
    system with its own erasure path.

    Args:
        user_uuid: Asta user UUID (the ``owners/{uuid}/`` key, not the Auth0 sub).
        dry_run: If True, report what would be deleted without deleting it.

    Returns:
        Dictionary with ``user_uuid``, ``bucket``, ``dry_run``,
        ``deleted_objects`` and ``deleted_bytes``.

    Raises:
        ValueError: If ``user_uuid`` is empty or contains a path separator.
        google.cloud.exceptions.GoogleCloudError: If deletion fails.
    """
    _validate_user_uuid(user_uuid)

    client = storage.Client()
    bucket = client.bucket(ASTA_BUCKET)
    prefix = f"owners/{user_uuid}/"

    deleted_objects: list[str] = []
    deleted_bytes = 0

    for blob in bucket.list_blobs(prefix=prefix):
        deleted_objects.append(blob.name)
        deleted_bytes += blob.size or 0
        if not dry_run:
            blob.delete()
            _log.info("Purged gs://%s/%s", ASTA_BUCKET, blob.name)

    return {
        "user_uuid": user_uuid,
        "bucket": ASTA_BUCKET,
        "dry_run": dry_run,
        "deleted_objects": sorted(deleted_objects),
        "deleted_bytes": deleted_bytes,
    }
