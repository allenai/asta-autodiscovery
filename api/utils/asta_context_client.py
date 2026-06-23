"""Client for the Asta context service (artifact storage + metadata).

The context service uploads bytes to the Asta workspace bucket AND records a
metadata row so the object is tracked rather than an untracked blob.

Auth is a static service API key sent as a bearer token (see the service's
`check_bearer_token` middleware). This is NOT the user's Auth0 token.
"""

import json
import logging
import os

import requests

_log = logging.getLogger("api.asta_context_client")

# Base URL of the deployed asta-context-service. Routes are mounted under /api.
ASTA_CONTEXT_SERVICE_URL = os.environ.get("ASTA_CONTEXT_SERVICE_URL", "")
# Shared service API key; sent as `Authorization: Bearer <key>`.
ASTA_CONTEXT_SERVICE_API_KEY = os.environ.get("ASTA_CONTEXT_SERVICE_API_KEY", "")

# The service rejects direct uploads above this size (use a presigned URL instead).
MAX_DIRECT_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _base() -> str:
    if not ASTA_CONTEXT_SERVICE_URL:
        raise RuntimeError("ASTA_CONTEXT_SERVICE_URL is not configured")
    return f"{ASTA_CONTEXT_SERVICE_URL.rstrip('/')}/api"


def _headers() -> dict[str, str]:
    if not ASTA_CONTEXT_SERVICE_API_KEY:
        raise RuntimeError("ASTA_CONTEXT_SERVICE_API_KEY is not configured")
    return {"Authorization": f"Bearer {ASTA_CONTEXT_SERVICE_API_KEY}"}


def upload_json_artifact(
    owner_id: str,
    prefix: str,
    filename: str,
    content: dict,
    *,
    artifact_type: str | None = None,
    source: str = "autodiscovery",
    tags: list[str] | None = None,
) -> str:
    """Upload a small JSON artifact and record its metadata in one call.

    Uses POST /owners/{owner_id}/artifacts (direct upload, ≤ 10 MB). The service
    writes both the object and the metadata row, and returns the gs:// path.

    Args:
        owner_id: Asta user UUID (must be a valid UUID).
        prefix: Directory prefix under the owner folder (e.g. the thread_id).
        filename: File name including extension (e.g. "manifest.json").
        content: JSON-serializable dict to store as the file body.
        artifact_type: Optional type tag (e.g. "manifest").
        source: Source tag recorded on the artifact.
        tags: Optional free-form tags.

    Returns:
        The gs:// URI of the stored artifact (its `path`).

    Raises:
        requests.HTTPError: If the upload call fails.
        ValueError: If the serialized body exceeds the direct-upload limit.
    """
    body = json.dumps(content, indent=2)
    size = len(body.encode("utf-8"))
    if size > MAX_DIRECT_UPLOAD_BYTES:
        raise ValueError(
            f"Artifact {filename} is {size} bytes, exceeds the {MAX_DIRECT_UPLOAD_BYTES} "
            "byte direct-upload limit; a presigned-URL upload is required."
        )

    resp = requests.post(
        f"{_base()}/owners/{owner_id}/artifacts",
        json={
            "filename": filename,
            "content_type": "application/json",
            "file_size_bytes": size,
            "file_content": body,
            "prefix": prefix,
            "artifact_type": artifact_type,
            "source": source,
            "tags": tags or [],
        },
        headers=_headers(),
        timeout=60,
    )
    if not resp.ok:
        _log.error(
            "context-service upload_artifact failed: status=%s body=%s",
            resp.status_code,
            resp.text,
        )
    resp.raise_for_status()
    return resp.json()["path"]
