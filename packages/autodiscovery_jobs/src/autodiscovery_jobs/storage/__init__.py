"""Swappable persistence backends.

All AutoDiscovery state — run metadata, uploaded datasets, experiment results,
user profiles, the metrics cache — lives in one keyed object store. Which store
is a deployment choice, selected by :attr:`JobConfig.storage_backend`
(``STORAGE_BACKEND``):

- ``local`` (default) — a POSIX directory tree reachable by this process, in the
  default compose stack a host directory bind-mounted into the containers. No
  cloud account or credentials needed.
- ``gcs`` — a Google Cloud Storage bucket, the hosted deployment's backend.

Call :func:`get_store` rather than constructing a backend directly, so the
selection stays in one place, and :func:`get_store_class` when you only need a
store's declared capabilities (that avoids constructing one, which for the
filesystem store would create its root directory as a side effect).

**Adding a backend.** There are two levels of effort:

1. *No code.* Mount your storage and use ``local``. Anything presentable as a
   POSIX tree works — NFS, s3fs, Azure Files, JuiceFS.
2. *A subclass.* Implement :class:`ObjectStore` (nine abstract members; three more
   have derived defaults) and register it in :data:`_STORES` below. Worth it when
   you want the things a filesystem cannot express: presigned browser uploads,
   single-request prefix globs, server-side copy, and a lock whose atomicity holds
   across machines.

See ``docs/design/storage-backends.md`` for the trade-offs between the two.
"""

from __future__ import annotations

from ..config import JobConfig
from ..exceptions import StorageBackendError
from .base import JobDataMount, ObjectInfo, ObjectStore, glob_to_regex
from .gcs import GcsStore
from .local import FilesystemStore

#: Backend name (as given in ``STORAGE_BACKEND``) → implementation.
_STORES: dict[str, type[ObjectStore]] = {
    "local": FilesystemStore,
    "gcs": GcsStore,
}

#: Backend names accepted in ``STORAGE_BACKEND``.
STORAGE_BACKENDS = tuple(_STORES)


def get_store_class(name: str) -> type[ObjectStore]:
    """Return the store implementation registered under ``name``.

    Use this to inspect a backend's capabilities (:attr:`ObjectStore.job_data_mount`,
    :attr:`ObjectStore.gs_addressable`) without constructing it.

    Args:
        name: Backend name from ``STORAGE_BACKEND``.

    Returns:
        The :class:`ObjectStore` subclass for that backend.

    Raises:
        StorageBackendError: If ``name`` is not a known backend.
    """
    try:
        return _STORES[name]
    except KeyError:
        raise StorageBackendError(
            f"Unknown storage_backend {name!r}; expected one of {', '.join(STORAGE_BACKENDS)}"
        ) from None


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
    store_class = get_store_class(config.storage_backend)

    if store_class is GcsStore:
        return GcsStore(bucket=config.bucket, project_id=config.project_id)
    if store_class is FilesystemStore:
        return FilesystemStore(root=config.storage_dir)

    # A backend registered without a construction rule here; its own signature is
    # unknown to us, so try the config-free form rather than guessing.
    return store_class()  # type: ignore[call-arg]


__all__ = [
    "STORAGE_BACKENDS",
    "FilesystemStore",
    "GcsStore",
    "JobDataMount",
    "ObjectInfo",
    "ObjectStore",
    "get_store",
    "get_store_class",
    "glob_to_regex",
]
