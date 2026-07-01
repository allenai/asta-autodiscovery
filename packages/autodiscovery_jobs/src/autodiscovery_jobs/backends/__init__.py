"""Swappable job backends for launching AutoDiscovery job processes.

A backend launches the AD job image and reports on the resulting execution.
The concrete backend is selected per deployment via ``config.backend``
(``JOB_BACKEND`` env var): ``gcp`` (Cloud Run, the production default) or
``docker`` (local containers). Use :func:`get_backend` to obtain the configured
implementation.
"""

from __future__ import annotations

from ..config import JobConfig
from ..exceptions import JobBackendError
from .base import JobBackend, build_job_args
from .gcp import CloudRunBackend


def get_backend(config: JobConfig | None = None) -> JobBackend:
    """Return the job backend selected by ``config.backend``.

    Args:
        config: Job configuration (loaded from environment if None).

    Returns:
        A :class:`JobBackend` instance.

    Raises:
        JobBackendError: If ``config.backend`` is not a recognized value.
    """
    config = config or JobConfig.from_env()
    backend = (config.backend or "gcp").lower()

    if backend == "gcp":
        return CloudRunBackend(config)
    if backend == "docker":
        # Imported lazily so the docker SDK is only required when actually used.
        from .docker import DockerBackend

        return DockerBackend(config)

    raise JobBackendError(f"Unknown job backend '{config.backend}'. Expected 'gcp' or 'docker'.")


__all__ = [
    "JobBackend",
    "CloudRunBackend",
    "build_job_args",
    "get_backend",
]
