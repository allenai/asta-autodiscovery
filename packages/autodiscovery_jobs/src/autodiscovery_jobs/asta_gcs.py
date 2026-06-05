"""GCS operations for the Asta workspace bucket."""

import json
import logging

from google.cloud import storage

from .config import JobConfig

_log = logging.getLogger(__name__)

ASTA_BUCKET = "example-workspaces-project"


def get_manifest_gcs_uri(user_uuid: str, thread_id: str) -> str:
    """Return the GCS URI for a manifest.json file.

    Args:
        user_uuid: Asta user UUID
        thread_id: Thread UUID

    Returns:
        Full GCS URI string
    """
    return f"gs://{ASTA_BUCKET}/owners/{user_uuid}/{thread_id}/manifest.json"


def save_manifest_json(user_uuid: str, thread_id: str, manifest: dict) -> str:
    """Upload manifest.json to the Asta workspace bucket.

    Args:
        user_uuid: Asta user UUID
        thread_id: Pre-generated thread UUID
        manifest: Manifest data dict to serialize as JSON

    Returns:
        GCS URI of the uploaded manifest

    Raises:
        google.cloud.exceptions.GoogleCloudError: If the upload fails
    """
    client = storage.Client()
    bucket = client.bucket(ASTA_BUCKET)
    blob_path = f"owners/{user_uuid}/{thread_id}/manifest.json"
    blob = bucket.blob(blob_path)
    blob.upload_from_string(
        json.dumps(manifest, indent=2),
        content_type="application/json",
    )
    uri = f"gs://{ASTA_BUCKET}/{blob_path}"
    _log.info("Saved manifest to %s", uri)
    return uri


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