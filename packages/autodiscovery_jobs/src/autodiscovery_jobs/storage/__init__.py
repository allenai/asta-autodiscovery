"""Swappable persistence backends.

All AutoDiscovery state — run metadata, uploaded datasets, experiment results,
user profiles, the metrics cache — lives in one keyed object store. Which store
is a deployment choice, selected by :attr:`JobConfig.storage_backend`
(``STORAGE_BACKEND``):

- ``local`` (default) — a POSIX directory tree reachable by this process, in the
  default compose stack a host directory bind-mounted into the containers. No
  cloud account or credentials needed. Anything mountable as a directory (NFS,
  s3fs, ...) works here too.
- ``gcs`` — a Google Cloud Storage bucket, the hosted deployment's backend.

Call :func:`get_store` rather than constructing a backend directly, so the
selection stays in one place. Constructing a store is side-effect-free, so code
that only needs to know *which* backend is active can construct one and
``isinstance``-check it.

See ``docs/design/storage-backends.md`` for the design.
"""

from __future__ import annotations

from ..config import JobConfig
from ..exceptions import StorageBackendError
from .base import ObjectInfo, ObjectStore, glob_to_regex
from .gcs import GcsStore, split_gs_uri
from .local import FilesystemStore

#: Backend names accepted in ``STORAGE_BACKEND``.
STORAGE_BACKENDS = ("local", "gcs")


def get_store(config: JobConfig | None = None) -> ObjectStore:
    """Return the object store selected by configuration.

    Args:
        config: Job configuration (read from the environment when None).

    Returns:
        A ready-to-use :class:`ObjectStore`.

    Raises:
        StorageBackendError: If ``storage_backend`` is not a known backend.
    """
    config = config or JobConfig.from_env()
    backend = config.storage_backend

    if backend == "gcs":
        return GcsStore(bucket=config.bucket, project_id=config.project_id)
    if backend == "local":
        return FilesystemStore(root=config.storage_dir)

    raise StorageBackendError(
        f"Unknown storage_backend {backend!r}; expected one of {', '.join(STORAGE_BACKENDS)}"
    )


__all__ = [
    "STORAGE_BACKENDS",
    "FilesystemStore",
    "GcsStore",
    "ObjectInfo",
    "ObjectStore",
    "get_store",
    "glob_to_regex",
    "split_gs_uri",
]
