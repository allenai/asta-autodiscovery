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

import re
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Compile a key glob with GCS ``matchGlob`` semantics.

    ``*`` and ``?`` match within one path segment (they never cross ``/``);
    ``**`` matches across segments. Everything else is literal. This is *not*
    :mod:`fnmatch`, whose ``*`` crosses ``/`` and would make
    ``users/*/jobs/*/x.json`` match arbitrarily deep keys.

    Args:
        pattern: Glob over full keys, e.g. ``users/*/jobs/*/run_details.json``.

    Returns:
        A compiled pattern; use :meth:`re.Pattern.fullmatch` against the key.
    """
    out: list[str] = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
            continue
        if ch == "*":
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
        i += 1
    return re.compile("".join(out))


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
    thread pool) and must be cheap and side-effect-free to construct, since
    helpers obtain one per operation and configuration validation constructs one
    just to inspect it.

    Reads of a missing key raise :class:`~autodiscovery_jobs.exceptions.ObjectNotFoundError`;
    any other failure raises :class:`~autodiscovery_jobs.exceptions.StorageError`.
    Deletes of a missing key are a no-op, so cleanup paths are idempotent.
    """

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

    @abstractmethod
    def download_file(self, key: str, local_path: Path) -> None:
        """Write an object's contents to a local file.

        The parent directory of ``local_path`` must already exist.

        Raises:
            ObjectNotFoundError: If the key does not exist.
            StorageError: If the download fails for any other reason.
        """
        ...

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

    @abstractmethod
    def upload_file(self, key: str, local_path: Path) -> None:
        """Copy a local file's contents to ``key``."""
        ...

    # Deletes, copies, listing

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete ``key``. Missing keys are not an error."""
        ...

    @abstractmethod
    def copy(self, source_key: str, dest_key: str) -> None:
        """Copy ``source_key`` to ``dest_key`` within this store.

        Forking a run copies its whole dataset, so backends that can copy
        server-side should.

        Raises:
            ObjectNotFoundError: If ``source_key`` does not exist.
        """
        ...

    @abstractmethod
    def list(
        self,
        prefix: str = "",
        *,
        match_glob: str | None = None,
        limit: int | None = None,
    ) -> Iterator[ObjectInfo]:
        """Iterate over objects whose key starts with ``prefix``.

        Args:
            prefix: Key prefix to restrict the listing to (``""`` lists all).
            match_glob: Glob over the *full key* with :func:`glob_to_regex`
                semantics (``*`` does not cross ``/``). Backends push this to the
                service when they can (GCS ``matchGlob``), so callers that only
                want one file per run out of a large tree should use it rather
                than filter a full listing themselves.
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
