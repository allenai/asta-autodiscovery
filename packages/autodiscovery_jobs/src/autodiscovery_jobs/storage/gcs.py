"""Google Cloud Storage object store.

Wraps ``google-cloud-storage`` behind :class:`~autodiscovery_jobs.storage.base.ObjectStore`.
This is the backend the hosted deployment runs on, so its behavior is the
reference the filesystem backend matches (prefix listing, atomic writes,
presigned uploads).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO

from google.api_core.exceptions import PreconditionFailed
from google.cloud.exceptions import NotFound

from ..client import get_storage_client
from ..exceptions import ObjectNotFoundError, StorageError
from .base import ObjectInfo, ObjectStore

if TYPE_CHECKING:
    from google.cloud import storage


def split_gs_uri(uri: str) -> tuple[str, str]:
    """Split ``gs://bucket/path/to/object`` into ``(bucket, object_name)``.

    Raises:
        StorageError: If ``uri`` is not a ``gs://`` URI naming an object.
    """
    if not uri.startswith("gs://"):
        raise StorageError(f"Not a gs:// URI: {uri!r}")
    bucket, _, name = uri[len("gs://"):].partition("/")
    if not bucket or not name:
        raise StorageError(f"gs:// URI must name a bucket and an object: {uri!r}")
    return bucket, name


def gs_blob(uri: str, project_id: str | None = None) -> storage.Blob:
    """Return a blob handle for ``gs://bucket/name`` on the shared client."""
    bucket, name = split_gs_uri(uri)
    return get_storage_client(project_id).bucket(bucket).blob(name)


def _rewrite(source: storage.Blob, dest: storage.Blob) -> None:
    """Server-side copy via the rewrite API, which handles cross-bucket and large objects."""
    token = None
    while True:
        token, _, _ = dest.rewrite(source, token=token)
        if token is None:
            return


class GcsStore(ObjectStore):
    """:class:`ObjectStore` backed by a Google Cloud Storage bucket.

    Object keys map 1:1 onto blob names in ``bucket``.
    """

    def __init__(self, bucket: str, project_id: str | None = None):
        """Bind the store to a bucket.

        Args:
            bucket: Bucket name holding all AutoDiscovery data.
            project_id: GCP project to scope the client to (auto-detected when None).
        """
        self._bucket_name = bucket
        self._project_id = project_id

    @property
    def root_uri(self) -> str:
        """URI of the bucket root (``gs://<bucket>``)."""
        return f"gs://{self._bucket_name}"

    def _bucket(self) -> storage.Bucket:
        """Return the bucket handle, reusing the process-wide cached client."""
        return get_storage_client(self._project_id).bucket(self._bucket_name)

    # Reads

    def read_bytes(self, key: str) -> bytes:
        """Download an object's contents."""
        try:
            return self._bucket().blob(key).download_as_bytes()
        except NotFound:
            raise ObjectNotFoundError(f"{self.uri(key)} not found") from None
        except Exception as e:
            raise StorageError(f"Failed to read {self.uri(key)}: {e}") from e

    def exists(self, key: str) -> bool:
        """Return whether the blob exists."""
        try:
            return self._bucket().blob(key).exists()
        except Exception:
            return False

    def download_file(self, key: str, local_path: Path) -> None:
        """Download an object to a local file."""
        try:
            self._bucket().blob(key).download_to_filename(str(local_path))
        except NotFound:
            raise ObjectNotFoundError(f"{self.uri(key)} not found") from None
        except Exception as e:
            raise StorageError(f"Failed to download {self.uri(key)}: {e}") from e

    # Writes

    def write_bytes(self, key: str, data: bytes, content_type: str | None = None) -> None:
        """Upload ``data`` to ``key``."""
        blob = self._bucket().blob(key)
        try:
            # Omit content_type when unset so the client library's default applies.
            if content_type:
                blob.upload_from_string(data, content_type=content_type)
            else:
                blob.upload_from_string(data)
        except Exception as e:
            raise StorageError(f"Failed to write {self.uri(key)}: {e}") from e

    def write_stream(self, key: str, stream: BinaryIO, content_type: str | None = None) -> None:
        """Stream ``stream`` into ``key`` (resumable upload)."""
        try:
            self._bucket().blob(key).upload_from_file(stream, content_type=content_type)
        except Exception as e:
            raise StorageError(f"Failed to write {self.uri(key)}: {e}") from e

    def upload_file(self, key: str, local_path: Path) -> None:
        """Upload a local file to ``key``."""
        try:
            self._bucket().blob(key).upload_from_filename(str(local_path))
        except Exception as e:
            raise StorageError(f"Failed to upload {local_path} to {self.uri(key)}: {e}") from e

    # Deletes, copies, listing

    def delete(self, key: str) -> None:
        """Delete a blob, tolerating a missing key."""
        try:
            self._bucket().blob(key).delete()
        except NotFound:
            return
        except Exception as e:
            raise StorageError(f"Failed to delete {self.uri(key)}: {e}") from e

    def copy(self, source_key: str, dest_key: str) -> None:
        """Copy server-side, so the bytes never reach this process."""
        bucket = self._bucket()
        try:
            bucket.copy_blob(bucket.blob(source_key), bucket, dest_key)
        except NotFound:
            raise ObjectNotFoundError(f"{self.uri(source_key)} not found") from None
        except Exception as e:
            raise StorageError(
                f"Failed to copy {self.uri(source_key)} to {self.uri(dest_key)}: {e}"
            ) from e

    def list(
        self,
        prefix: str = "",
        *,
        match_glob: str | None = None,
        limit: int | None = None,
    ) -> Iterator[ObjectInfo]:
        """List blobs, pushing prefix, glob, and limit down to the GCS API."""
        try:
            blobs = self._bucket().list_blobs(
                prefix=prefix or None,
                match_glob=match_glob,
                max_results=limit,
            )
            for blob in blobs:
                yield ObjectInfo(key=blob.name, size=blob.size, created_at=blob.time_created)
        except Exception as e:
            raise StorageError(f"Failed to list {self.uri(prefix)}: {e}") from e

    def list_dirs(self, prefix: str) -> list[str]:
        """List common prefixes directly under ``prefix`` via a delimited list."""
        try:
            blobs = self._bucket().list_blobs(prefix=prefix, delimiter="/")
            # Consuming the iterator is what populates .prefixes.
            for _ in blobs:
                pass
            return sorted(p.rstrip("/").split("/")[-1] for p in blobs.prefixes)
        except Exception as e:
            raise StorageError(f"Failed to list directories under {self.uri(prefix)}: {e}") from e

    # Direct browser uploads

    def signed_upload_url(
        self,
        key: str,
        content_type: str,
        expires_in_seconds: int,
    ) -> str | None:
        """Return a v4 presigned ``PUT`` URL so the browser uploads straight to GCS."""
        try:
            return self._bucket().blob(key).generate_signed_url(
                version="v4",
                expiration=timedelta(seconds=expires_in_seconds),
                method="PUT",
                content_type=content_type,
            )
        except Exception as e:
            raise StorageError(f"Failed to sign upload URL for {self.uri(key)}: {e}") from e

    def create_exclusive(self, key: str, data: bytes, content_type: str | None = None) -> bool:
        """Create the blob only if absent, via a generation-0 precondition."""
        blob = self._bucket().blob(key)
        try:
            if content_type:
                blob.upload_from_string(data, content_type=content_type, if_generation_match=0)
            else:
                blob.upload_from_string(data, if_generation_match=0)
            return True
        except PreconditionFailed:
            return False
        except Exception as e:
            raise StorageError(f"Failed to create {self.uri(key)}: {e}") from e

    # Transfers to and from Google Cloud Storage

    def import_from_gs(self, source_uri: str, dest_key: str) -> None:
        """Server-side copy from another bucket; no bytes flow through this process."""
        try:
            _rewrite(gs_blob(source_uri, self._project_id), self._bucket().blob(dest_key))
        except NotFound:
            raise ObjectNotFoundError(f"{source_uri} not found") from None
        except Exception as e:
            raise StorageError(f"Failed to import {source_uri} to {self.uri(dest_key)}: {e}") from e

    def export_to_gs(self, key: str, dest_uri: str) -> None:
        """Server-side copy to another bucket; no bytes flow through this process."""
        try:
            _rewrite(self._bucket().blob(key), gs_blob(dest_uri, self._project_id))
        except NotFound:
            raise ObjectNotFoundError(f"{self.uri(key)} not found") from None
        except Exception as e:
            raise StorageError(f"Failed to export {self.uri(key)} to {dest_uri}: {e}") from e
