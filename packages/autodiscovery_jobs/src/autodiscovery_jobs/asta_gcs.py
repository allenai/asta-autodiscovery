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