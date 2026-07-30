r"""Filesystem object store — the default, vendor-neutral persistence backend.

Keys become paths under a single root directory. In the default compose stack
that root is a **host directory bind-mounted into the API container**, and the
docker job backend re-mounts the current run's subtree into the job container at
the same path the Cloud Run GCS FUSE volume would appear at. So the AD job reads
and writes ordinary files either way and needs no cloud credentials.

The root is just a POSIX tree, so this is also the zero-code path to running on
storage this package has never heard of: mount it (NFS, s3fs, Azure Files,
JuiceFS, ...) and point ``STORAGE_DIR`` at the mount. See
``docs/design/storage-backends.md`` for what that costs you versus a native
backend — chiefly presigned uploads, single-call globs, server-side copy, and the
cross-process lock's atomicity guarantee.

Two behaviors exist to match GCS closely enough that the rest of the codebase
cannot tell the difference:

- **Atomic replace.** Writes land in a temp file and are ``os.replace``\\ d into
  place, so a concurrent reader (the API polling a run the job container is
  writing) never observes a half-written JSON document.
- **No empty directories.** GCS has no directories, only key prefixes, so a
  prefix stops existing once its last object is deleted. Deletes here prune
  parent directories that they empty, and prefix listings ignore directories
  with no objects beneath them.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from ..exceptions import ObjectNotFoundError, StorageError
from .base import JobDataMount, ObjectInfo, ObjectStore, glob_to_regex

# Filename prefix for in-flight writes staged next to their destination. Listings
# skip these so a concurrent reader never sees a half-written object as an object
# in its own right — there is no such thing in GCS, where a write is atomic.
_STAGING_PREFIX = ".ad-staging."


class FilesystemStore(ObjectStore):
    """:class:`ObjectStore` backed by a directory tree on the local filesystem.

    "Local" means reachable as a path by *this* process, which includes a network
    filesystem the operator has mounted — not necessarily a physically local disk.
    """

    #: A job container gets the run's data as a plain bind mount of its directory:
    #: no FUSE, no credentials, no cloud dependency.
    job_data_mount = JobDataMount.HOST_PATH

    def __init__(self, root: str | Path):
        """Bind the store to a root directory, creating it if needed.

        Args:
            root: Directory that holds the whole key namespace. In containers
                this is the mount point of the host data directory.

        Raises:
            StorageError: If the directory cannot be created.
        """
        self._root = Path(root).expanduser()
        try:
            self._root.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise StorageError(f"Failed to create storage directory {self._root}: {e}") from e

    @property
    def root_uri(self) -> str:
        """URI of the root directory (``file:///abs/path``)."""
        return self._root.resolve().as_uri().rstrip("/")

    def _path(self, key: str) -> Path:
        """Resolve a key to an absolute path inside the root.

        Keys reach this method from user-controlled values (uploaded filenames),
        so escapes are rejected rather than normalized away.

        Raises:
            StorageError: If the key is empty, absolute, or escapes the root.
        """
        if not key or key.endswith("/"):
            raise StorageError(f"Invalid object key: {key!r}")
        path = (self._root / key).resolve()
        if self._root.resolve() not in path.parents:
            raise StorageError(f"Object key escapes the storage root: {key!r}")
        return path

    def _key(self, path: Path) -> str:
        """Convert an absolute path back into a store key."""
        return path.relative_to(self._root.resolve()).as_posix()

    def _info(self, path: Path) -> ObjectInfo:
        """Build an :class:`ObjectInfo` from a file's stat.

        ``st_mtime`` stands in for GCS's ``time_created``: POSIX exposes no
        portable creation time, and these objects are written once, so mtime is
        the same instant in practice.
        """
        stat = path.stat()
        return ObjectInfo(
            key=self._key(path),
            size=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
        )

    # Reads

    def read_bytes(self, key: str) -> bytes:
        """Read a file's contents."""
        path = self._path(key)
        try:
            return path.read_bytes()
        except FileNotFoundError:
            raise ObjectNotFoundError(f"{self.uri(key)} not found") from None
        except OSError as e:
            raise StorageError(f"Failed to read {self.uri(key)}: {e}") from e

    def exists(self, key: str) -> bool:
        """Return whether a regular file exists at ``key``."""
        try:
            return self._path(key).is_file()
        except StorageError:
            return False

    def download_file(self, key: str, local_path: Path) -> None:
        """Copy the stored file to ``local_path``."""
        path = self._path(key)
        try:
            shutil.copyfile(path, local_path)
        except FileNotFoundError:
            raise ObjectNotFoundError(f"{self.uri(key)} not found") from None
        except OSError as e:
            raise StorageError(f"Failed to download {self.uri(key)}: {e}") from e

    # Writes

    def _write(self, key: str, writer) -> None:
        """Write ``key`` atomically by staging into a temp file next to it.

        ``writer`` receives an open binary file object for the temp file. The temp
        file is created in the destination's own directory, both so the final
        rename stays within one filesystem (and is therefore atomic) and so
        concurrent writers of the same key get distinct staging files.
        """
        path = self._path(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                dir=path.parent, prefix=f"{_STAGING_PREFIX}{path.name}."
            )
            tmp = Path(tmp_name)
            try:
                with os.fdopen(fd, "wb") as fh:
                    writer(fh)
                os.replace(tmp, path)
            except BaseException:
                tmp.unlink(missing_ok=True)
                raise
        except OSError as e:
            raise StorageError(f"Failed to write {self.uri(key)}: {e}") from e

    def write_bytes(self, key: str, data: bytes, content_type: str | None = None) -> None:
        """Write ``data`` to ``key``. ``content_type`` has no meaning on a filesystem."""
        self._write(key, lambda fh: fh.write(data))

    def write_stream(self, key: str, stream: BinaryIO, content_type: str | None = None) -> None:
        """Copy ``stream`` into ``key`` without buffering it in memory."""
        self._write(key, lambda fh: shutil.copyfileobj(stream, fh))

    def upload_file(self, key: str, local_path: Path) -> None:
        """Copy a local file to ``key``."""
        try:
            with open(local_path, "rb") as fh:
                self.write_stream(key, fh)
        except OSError as e:
            raise StorageError(f"Failed to upload {local_path} to {self.uri(key)}: {e}") from e

    def create_exclusive(self, key: str, data: bytes) -> bool:
        """Create ``key`` with ``O_EXCL``, which is atomic on a local filesystem."""
        path = self._path(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            return False
        except OSError as e:
            raise StorageError(f"Failed to create {self.uri(key)}: {e}") from e
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
        except OSError as e:
            raise StorageError(f"Failed to create {self.uri(key)}: {e}") from e
        return True

    # Deletes, copies, listing

    def delete(self, key: str) -> None:
        """Delete a file and prune any directories the delete leaves empty."""
        path = self._path(key)
        try:
            path.unlink()
        except FileNotFoundError:
            return
        except OSError as e:
            raise StorageError(f"Failed to delete {self.uri(key)}: {e}") from e
        self._prune_empty_dirs(path.parent)

    def _prune_empty_dirs(self, directory: Path) -> None:
        """Remove now-empty directories up to (but excluding) the root."""
        root = self._root.resolve()
        current = directory
        while current != root and root in current.parents:
            try:
                current.rmdir()
            except OSError:
                return  # Not empty (or racing another writer) — stop climbing.
            current = current.parent

    def copy(self, source_key: str, dest_key: str) -> None:
        """Copy one stored file to another key."""
        source = self._path(source_key)
        if not source.is_file():
            raise ObjectNotFoundError(f"{self.uri(source_key)} not found")
        try:
            with open(source, "rb") as fh:
                self.write_stream(dest_key, fh)
        except OSError as e:
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
        """Walk the tree under ``prefix``, filtering like a GCS prefix listing.

        ``prefix`` is a key *prefix*, not necessarily a directory, so the walk
        starts at the nearest enclosing directory and re-checks each key.
        """
        root = self._root.resolve()
        # Start from the deepest directory the prefix definitely lives under.
        start = root / prefix.rsplit("/", 1)[0] if "/" in prefix else root
        if not start.is_dir():
            return

        pattern = glob_to_regex(match_glob) if match_glob else None
        emitted = 0
        for dirpath, dirnames, filenames in os.walk(start):
            dirnames.sort()
            for filename in sorted(filenames):
                if filename.startswith(_STAGING_PREFIX):
                    continue  # A write in flight; not an object yet.
                path = Path(dirpath) / filename
                try:
                    key = self._key(path)
                except ValueError:  # pragma: no cover - symlink pointing outside the root
                    continue
                if not key.startswith(prefix):
                    continue
                if pattern is not None and not pattern.match(key):
                    continue
                try:
                    info = self._info(path)
                except OSError:
                    continue  # Deleted mid-walk; treat as absent.
                yield info
                emitted += 1
                if limit is not None and emitted >= limit:
                    return

    def list_dirs(self, prefix: str) -> list[str]:
        """List child directories under ``prefix`` that contain at least one object.

        The emptiness check keeps parity with GCS, where a prefix with no objects
        beneath it simply does not exist.
        """
        base = self._root.resolve() / prefix if prefix else self._root.resolve()
        if not base.is_dir():
            return []
        names = []
        try:
            for child in sorted(base.iterdir()):
                if child.is_dir() and any(p.is_file() for p in child.rglob("*")):
                    names.append(child.name)
        except OSError as e:
            raise StorageError(f"Failed to list directories under {self.uri(prefix)}: {e}") from e
        return names
