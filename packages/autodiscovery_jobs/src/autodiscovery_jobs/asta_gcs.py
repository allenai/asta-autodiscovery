"""Dataset handoff into the Asta workspace bucket.

The manifest and dataset metadata writes now go through asta-context-service
(see api/utils/asta_context_client.py) so they are tracked. This module retains
only the dataset copy.

The destination is always GCS — it is Asta's workspace bucket, not ours — so this
is one of the few places that stays vendor-specific no matter which
``STORAGE_BACKEND`` holds the AD run data. Only the *source* side varies: a GCS
store copies server-side, while any other store streams the bytes up.
"""

import logging
import os

from google.cloud import storage

from .config import JobConfig
from .storage import GcsStore, get_store

_log = logging.getLogger(__name__)

ASTA_BUCKET = os.environ.get("ASTA_BUCKET", "example-workspaces-project")


def copy_dataset_to_asta_workspace(
    ad_userid: str,
    ad_runid: str,
    user_uuid: str,
    thread_id: str,
    ad_config: JobConfig,
) -> list[str]:
    """Copy AD run dataset files into the Asta workspace bucket.

    Copies everything under users/{ad_userid}/jobs/{ad_runid}/data/ in the AD
    store into owners/{user_uuid}/{thread_id}/data/ in ASTA_BUCKET. When AD data
    already lives in GCS the copy is server-side, so no data flows through the
    API server.

    Args:
        ad_userid: AD user identifier
        ad_runid: AD run/job identifier
        user_uuid: Asta user UUID
        thread_id: Pre-generated thread UUID
        ad_config: AD JobConfig (selects the source store)

    Returns:
        List of GCS URIs of the copied dataset files

    Raises:
        google.cloud.exceptions.GoogleCloudError: If the copy fails
    """
    source_store = get_store(ad_config)
    client = storage.Client()
    asta_bucket = client.bucket(ASTA_BUCKET)

    source_prefix = f"users/{ad_userid}/jobs/{ad_runid}/data/"
    dest_prefix = f"owners/{user_uuid}/{thread_id}/data/"

    uris: list[str] = []
    for info in source_store.list(source_prefix):
        filename = info.key[len(source_prefix):]
        if not filename or filename == ".placeholder":
            continue

        dest_blob_name = f"{dest_prefix}{filename}"
        if isinstance(source_store, GcsStore):
            ad_bucket = client.bucket(ad_config.bucket)
            ad_bucket.copy_blob(ad_bucket.blob(info.key), asta_bucket, dest_blob_name)
        else:
            # No cross-vendor server-side copy exists; stream the object up.
            asta_bucket.blob(dest_blob_name).upload_from_string(
                source_store.read_bytes(info.key)
            )

        uri = f"gs://{ASTA_BUCKET}/{dest_blob_name}"
        uris.append(uri)
        _log.info("Copied %s → %s", source_store.uri(info.key), uri)

    return uris
