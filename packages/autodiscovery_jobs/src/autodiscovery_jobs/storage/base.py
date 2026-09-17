"""Object-store interface shared by every persistence backend.

A *store* is a flat, keyed blob namespace rooted at one location: a GCS bucket,
or a directory on the host filesystem. Keys are ``/``-separated, relative, and
never start with ``/`` — e.g. ``users/<uid>/jobs/<jid>/metadata.json``. The
"directories" callers reason about are pure key prefixes; only
:meth:`ObjectStore.list_dirs` gives them any structure, and it derives that from
the keys themselves so both backends agree.

Everything the application persists (job data, run metadata, results, user
profiles, the metrics cache) goes through this interface, so the concrete
backend is a deployment choice rather than a code dependency. See
:mod:`autodiscovery_jobs.storage` for the factory and
``docs/design/storage-backends.md`` for the rationale.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import BinaryIO


class JobDataMount(Enum):
    """How a job container can be handed one run's subtree of a store as files.

    The AD job reads its inputs and writes its results as ordinary files, so every
    store must be presentable to a container as a filesystem mount. Only the job
    backend knows how to build a container, so a store declares *which mechanism*
    applies and the backend implements it.

    This deliberately enumerates the mechanisms this codebase implements rather
    than pretending to be open-ended: a new store either reuses one of them or is
    rejected with a clear error instead of silently getting the wrong mount.
    """

    #: The store is a POSIX directory tree on this host; bind-mount the run's
    #: subdirectory. Covers anything the operator has mounted locally — a plain
    #: directory, NFS, s3fs, JuiceFS — with no code and no credentials in the job.
    HOST_PATH = "host_path"

    #: The container mounts the bucket itself with gcsfuse, scoped to the run's
    #: prefix. Needs GCP credentials, `/dev/fuse`, and `CAP_SYS_ADMIN`.
    GCSFUSE = "gcsfuse"

    #: No known way to present this store to a job container.
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class ObjectInfo:
    """Metadata for one stored object.

    Attributes:
        key: Store-relative key (``users/<uid>/jobs/<jid>/metadata.json``).
        size: Size in bytes, when the backend reports it.
        created_at: Creation time, when the backend reports it. Used by dataset
            expiry, so a backend that cannot supply it disables age-based
            cleanup for its objects.
    """

    key: str
    size: int | None = None
    created_at: datetime | None = None


class ObjectStore(ABC):
    """Abstract keyed blob store backing all AutoDiscovery persistence.

    Implementations are safe to share across threads (the API scans jobs from a
    thread pool) and are expected to be cheap to construct after the first call,
    since helpers obtain one per operation.

    Reads of a missing key raise :class:`~autodiscovery_jobs.exceptions.ObjectNotFoundError`;
    any other failure raises :class:`~autodiscovery_jobs.exceptions.StorageError`.
    Deletes of a missing key are a no-op, so cleanup paths are idempotent.

    A subclass must implement the eight abstract members below. ``upload_file``,
    ``download_file``, and ``copy`` have working (if unoptimized) defaults derived
    from those, so a minimal backend can skip them and override only the ones its
    service can do better — GCS, for instance, copies server-side.

    The two class attributes are *capabilities*: they let the job backend and the
    startup validator ask what a store can do instead of comparing its name, so a
    third backend fails loudly rather than inheriting whichever branch happened to
    be the fallback.
    """

    #: How a job container can be given a run's data as files. Declaring
    #: :attr:`JobDataMount.UNSUPPORTED` (the default) means jobs cannot run against
    #: this store, and the job backend says so instead of guessing.
    job_data_mount: JobDataMount = JobDataMount.UNSUPPORTED

    #: Whether objects are addressable as ``gs://<bucket>/<key>``. This is narrower
    #: than "is remote" on purpose: the two consumers that read run data from off
    #: this host — Cloud Run's GCS volume mount and the Modal sandbox's
    #: ``--bucket_path`` — both understand Google Cloud Storage specifically, not
    #: object storage in general.
    gs_addressable: bool = False

    @property
    @abstractmethod
    def root_uri(self) -> str:
        """URI of the store root, without a trailing slash (``gs://bucket``)."""
        ...

    def uri(self, key: str) -> str:
        """Return the fully-qualified URI of a key, for display and logging.

        Args:
            key: Store-relative object key.

        Returns:
            An absolute URI such as ``gs://bucket/users/u/jobs/j/metadata.json``
            or ``file:///data/users/u/jobs/j/metadata.json``.
        """
        return f"{self.root_uri}/{key}"

    # Reads

    @abstractmethod
    def read_bytes(self, key: str) -> bytes:
        """Return the full contents of an object.

        Raises:
            ObjectNotFoundError: If the key does not exist.
            StorageError: If the read fails for any other reason.
        """
        ...

    def read_text(self, key: str) -> str:
        """Return the contents of an object decoded as UTF-8.

        Raises:
            ObjectNotFoundError: If the key does not exist.
            StorageError: If the read fails for any other reason.
        """
        return self.read_bytes(key).decode("utf-8")

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return whether an object exists at ``key``."""
        ...

    def download_file(self, key: str, local_path: Path) -> None:
        """Write an object's contents to a local file.

        The parent directory of ``local_path`` must already exist.

        Buffers the whole object in memory; override when the backend can stream
        or has a native download.

        Raises:
            ObjectNotFoundError: If the key does not exist.
            StorageError: If the download fails for any other reason.
        """
        local_path.write_bytes(self.read_bytes(key))

    # Writes

    @abstractmethod
    def write_bytes(self, key: str, data: bytes, content_type: str | None = None) -> None:
        """Write ``data`` to ``key``, replacing any existing object."""
        ...

    def write_text(self, key: str, text: str, content_type: str | None = None) -> None:
        """Write UTF-8 ``text`` to ``key``, replacing any existing object."""
        self.write_bytes(key, text.encode("utf-8"), content_type=content_type)

    @abstractmethod
    def write_stream(self, key: str, stream: BinaryIO, content_type: str | None = None) -> None:
        """Stream ``stream`` into ``key`` without buffering it all in memory.

        Used for user uploads, which can be very large.
        """
        ...

    def upload_file(self, key: str, local_path: Path) -> None:
        """Copy a local file's contents to ``key``.

        Streams through :meth:`write_stream`; override when the backend has a
        native upload-from-path.
        """
        with open(local_path, "rb") as fh:
            self.write_stream(key, fh)

    # Deletes, copies, listing

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete ``key``. Missing keys are not an error."""
        ...

    def copy(self, source_key: str, dest_key: str) -> None:
        """Copy ``source_key`` to ``dest_key`` within this store.

        Reads and re-writes the bytes. **Override this** if the backend can copy
        server-side: forking a run copies its whole dataset, so the default sends
        every byte through this process twice.

        Raises:
            ObjectNotFoundError: If ``source_key`` does not exist.
        """
        self.write_bytes(dest_key, self.read_bytes(source_key))

    @abstractmethod
    def list(
        self,
        prefix: str = "",
        *,
        limit: int | None = None,
    ) -> Iterator[ObjectInfo]:
        """Iterate over objects whose key starts with ``prefix``.

        There is deliberately no server-side pattern filter. GCS has one
        (``matchGlob``) and S3-compatible stores and filesystems do not, and every
        caller that wanted one is a rare operation — the metrics scan (once per five
        minutes) and the shared-run owner lookup's index-miss fallback. They filter
        the returned keys themselves, which costs a longer listing on a cold path in
        exchange for one less semantic every backend has to reproduce.

        Args:
            prefix: Key prefix to restrict the listing to (``""`` lists all).
            limit: Stop after this many objects. Callers that only need
                existence should pass ``limit=1``.

        Yields:
            One :class:`ObjectInfo` per matching object, in unspecified order.
        """
        ...

    @abstractmethod
    def list_dirs(self, prefix: str) -> list[str]:
        """List the immediate "directory" names directly under ``prefix``.

        ``prefix`` should end with ``/``. Given keys ``users/a/x`` and
        ``users/b/y``, ``list_dirs("users/")`` returns ``["a", "b"]``.

        Returns:
            Sorted child names (not full keys, no trailing slash).
        """
        ...

    # Direct browser uploads

    def signed_upload_url(
        self,
        key: str,
        content_type: str,
        expires_in_seconds: int,
    ) -> str | None:
        """Return a URL the browser can ``PUT`` a file to directly, if supported.

        Backends that can hand out capability URLs (GCS presigned URLs) return
        one so upload bytes bypass the API server entirely. Backends that cannot
        return ``None``, and the API falls back to receiving the upload itself.

        Args:
            key: Object key the upload should land at.
            content_type: MIME type the client will send.
            expires_in_seconds: Requested lifetime of the URL.

        Returns:
            An absolute upload URL, or None when the backend has no such notion.
        """
        return None
