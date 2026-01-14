"""
autodiscovery_jobs - Python package for managing Cloud Run jobs.

This package provides a clean API for managing Cloud Run jobs for the
autodiscovery system, including GCS operations, job execution, and result retrieval.

Example:
    Class-based usage:
        >>> from autodiscovery_jobs import JobManager
        >>> manager = JobManager()
        >>> manager.create_job("exampleuser", "experiment_1")
        >>> manager.upload_dataset("exampleuser", "experiment_1", Path("./data.csv"))
        >>> execution_id = manager.run_job("exampleuser", "experiment_1", n_experiments=4)

    Functional API:
        >>> from autodiscovery_jobs import create_job_directory, upload_dataset, run_job
        >>> create_job_directory("exampleuser", "test_1")
        >>> upload_dataset("exampleuser", "test_1", Path("./data.csv"))
        >>> run_job("exampleuser", "test_1", n_experiments=4)
"""

from .manager import JobManager
from .config import JobConfig
from .exceptions import (
    AutodiscoveryJobError,
    JobNotFoundError,
    JobAlreadyExistsError,
    GCSError,
    CloudRunError,
)

# Re-export functional APIs for direct use
from .gcs import (
    parse_gcs_path,
    get_user_path,
    get_job_path,
    list_user_jobs,
    job_exists,
    create_job_directory,
    delete_job_directory,
    upload_dataset,
    upload_metadata,
    get_job_results,
    download_job_results,
)

from .cloudrun import (
    run_job,
    get_job_status,
    cancel_job,
    get_job_logs,
)

__version__ = "0.1.0"

__all__ = [
    # Main class
    "JobManager",
    "JobConfig",
    # Exceptions
    "AutodiscoveryJobError",
    "JobNotFoundError",
    "JobAlreadyExistsError",
    "GCSError",
    "CloudRunError",
    # GCS functions
    "parse_gcs_path",
    "get_user_path",
    "get_job_path",
    "list_user_jobs",
    "job_exists",
    "create_job_directory",
    "delete_job_directory",
    "upload_dataset",
    "upload_metadata",
    "get_job_results",
    "download_job_results",
    # Cloud Run functions
    "run_job",
    "get_job_status",
    "cancel_job",
    "get_job_logs",
]
