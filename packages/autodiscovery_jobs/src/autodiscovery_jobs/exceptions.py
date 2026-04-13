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


class GCSError(AutodiscoveryJobError):
    """Raised when GCS operations fail."""

    pass


class CloudRunError(AutodiscoveryJobError):
    """Raised when Cloud Run operations fail."""

    pass


class DatasetExpiredError(AutodiscoveryJobError):
    """Raised when a run's dataset files have been deleted or expired."""

    pass
