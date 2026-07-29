"""Swappable persistence backends.

All AutoDiscovery state — run metadata, uploaded datasets, experiment results,
user profiles, the metrics cache — lives in one keyed object store. Which store
is a deployment choice, selected by :attr:`JobConfig.storage_backend`
(``STORAGE_BACKEND``):

- ``local`` (default) — a directory on the host, bind-mounted into the
  containers. No cloud account or credentials needed.
- ``gcs`` — a Google Cloud Storage bucket, the hosted deployment's backend.

Call :func:`get_store` rather than constructing a backend directly, so the
selection stays in one place.
"""

from __future__ import annotations

from ..config import JobConfig
from ..exceptions import StorageBackendError
from .base import ObjectInfo, ObjectStore, glob_to_regex
from .gcs import GcsStore
from .local import LocalStore

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

    if config.storage_backend == "gcs":
        return GcsStore(bucket=config.bucket, project_id=config.project_id)
    if config.storage_backend == "local":
        return LocalStore(root=config.storage_dir)

    raise StorageBackendError(
        f"Unknown storage_backend {config.storage_backend!r}; "
        f"expected one of {', '.join(STORAGE_BACKENDS)}"
    )


__all__ = [
    "STORAGE_BACKENDS",
    "GcsStore",
    "LocalStore",
    "ObjectInfo",
    "ObjectStore",
    "get_store",
    "glob_to_regex",
]
