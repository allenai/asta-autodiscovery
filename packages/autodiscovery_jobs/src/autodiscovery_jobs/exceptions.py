"""Custom exceptions for autodiscovery_jobs package."""


class AutodiscoveryJobError(Exception):
    """Base exception for autodiscovery_jobs package."""

    pass


class JobNotFoundError(AutodiscoveryJobError):
    """Raised when a job directory does not exist."""

    pass


class JobAlreadyExistsError(AutodiscoveryJobError):
    """Raised when attempting to create a job that already exists."""

    pass


class StorageError(AutodiscoveryJobError):
    """Raised when a persistence (object store) operation fails."""

    pass


# Historical name from when persistence was GCS-only. Retained as an alias so
# existing `except GCSError` / import sites keep working across both backends.
GCSError = StorageError


class ObjectNotFoundError(StorageError):
    """Raised when a specific object/key does not exist in the store."""

    pass


class StorageBackendError(AutodiscoveryJobError):
    """Raised when a storage backend is misconfigured or unknown."""

    pass


class JobBackendError(AutodiscoveryJobError):
    """Raised when a job backend (Cloud Run, Docker, ...) operation fails."""

    pass


class CloudRunError(JobBackendError):
    """Raised when Cloud Run operations fail."""

    pass


class DockerBackendError(JobBackendError):
    """Raised when local Docker backend operations fail."""

    pass


class DatasetExpiredError(AutodiscoveryJobError):
    """Raised when a run's dataset files have been deleted or expired."""

    pass
