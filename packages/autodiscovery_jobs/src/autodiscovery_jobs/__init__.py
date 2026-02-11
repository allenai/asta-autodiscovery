"""autodiscovery_jobs - Python package for managing Cloud Run jobs.

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

from .cloudrun import (
    cancel_job,
    get_job_logs,
    get_job_status,
    run_job,
)
from .config import JobConfig
from .exceptions import (
    AutodiscoveryJobError,
    CloudRunError,
    GCSError,
    JobAlreadyExistsError,
    JobNotFoundError,
)

# Re-export functional APIs for direct use
from .gcs import (
    create_job_directory,
    delete_job_directory,
    download_job_results,
    expire_datasets,
    get_job_path,
    get_job_results,
    get_user_path,
    job_exists,
    list_user_ids,
    list_user_jobs,
    parse_gcs_path,
    soft_delete_job,
    upload_dataset,
    upload_metadata,
)
from .manager import JobManager

# Run details management
from .run_details import (
    RunDetails,
    TERMINAL_STATUSES,
    create_run_details,
    get_run_details,
    get_run_details_path,
    refresh_run_status,
    update_run_details,
)

# Email state management
from .email_state import (
    get_email_state,
    get_email_state_path,
    record_email_sent,
    was_email_sent,
)

# User profile management
from .user_profile import (
    UserProfile,
    create_user_profile,
    get_user_granted_credits,
    get_user_profile,
    get_user_profile_path,
    update_user_profile,
)

# Auth0 client
from .auth0 import (
    Auth0Error,
    get_user,
)

# Email sending
from .email import (
    send_email,
    DEFAULT_SENDER_EMAIL,
    DEFAULT_SMTP_SERVER,
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
    "Auth0Error",
    # GCS functions
    "parse_gcs_path",
    "get_user_path",
    "get_job_path",
    "list_user_ids",
    "list_user_jobs",
    "job_exists",
    "create_job_directory",
    "delete_job_directory",
    "soft_delete_job",
    "upload_dataset",
    "expire_datasets",
    "upload_metadata",
    "get_job_results",
    "download_job_results",
    # Cloud Run functions
    "run_job",
    "get_job_status",
    "cancel_job",
    "get_job_logs",
    # Run details
    "RunDetails",
    "TERMINAL_STATUSES",
    "get_run_details_path",
    "create_run_details",
    "get_run_details",
    "refresh_run_status",
    "update_run_details",
    # Email state functions
    "get_email_state_path",
    "get_email_state",
    "record_email_sent",
    "was_email_sent",
    # User profile functions
    "UserProfile",
    "get_user_profile_path",
    "get_user_profile",
    "create_user_profile",
    "update_user_profile",
    "get_user_granted_credits",
    # Auth0 functions
    "get_user",
    # Email functions
    "send_email",
    "DEFAULT_SENDER_EMAIL",
    "DEFAULT_SMTP_SERVER",
]
