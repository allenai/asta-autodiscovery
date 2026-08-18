"""Configuration management for autodiscovery_jobs package."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# How many days uploaded datasets are retained before the cleanup cron deletes
# them from GCS.  Both the cleanup script and the API's expiry estimate read
# this value so they stay in sync.
DATASET_EXPIRY_DAYS: int = 7


@dataclass
class JobConfig:
    """Configuration for Cloud Run job management."""

    # GCS Configuration
    bucket: str = "autodiscovery"
    project_id: str | None = None  # Auto-detect from gcloud if None

    # Cloud Run Configuration
    region: str = "us-west1"
    job_name: str = "autodiscovery-job"

    # Job backend selection: "docker" (local containers, default) or "gcp" (Cloud Run).
    # Docker is the default to keep the out-of-the-box experience infra-agnostic;
    # deployments that run jobs on Cloud Run must set JOB_BACKEND=gcp explicitly.
    backend: str = "docker"
    # AD job image reference used by the Docker backend (ignored for gcp)
    job_image: str | None = None

    # Code-execution backend the AD job uses for LLM-generated code, forwarded to
    # the job's --backend flag. "process" (default): isolated subprocess inside the
    # job container (no cloud dependency); "local": in-process, no isolation;
    # "modal": remote Modal sandbox with a scoped, read-only per-job data mount.
    # See docs/configuration.md for the safe-combination matrix (this interacts with
    # the job backend and auth/tenancy — untrusted code runs where the data is mounted).
    code_execution_backend: str = "process"

    # Modal Configuration (for sandbox execution)
    modal_app_name: str = "asta-autodiscovery"
    modal_bucket_secret: str = "example-bucket-secret"

    # Single-user local process backend configuration (ignored by other backends).
    local_root: str = str(Path.home() / "AutoDiscovery")
    local_user_id: str = "local"
    local_max_concurrent_jobs: int = 1

    @classmethod
    def from_env(cls, **overrides) -> JobConfig:
        """Create configuration from environment variables with optional overrides.

        Args:
            **overrides: Override specific config values

        Returns:
            JobConfig instance

        Example:
            config = JobConfig.from_env(bucket="my-custom-bucket")
        """
        config = cls(
            bucket=os.environ.get("GCS_BUCKET")
            or os.environ.get("AUTODISCOVERY_BUCKET", cls.bucket),
            project_id=os.environ.get("GCP_PROJECT"),
            region=os.environ.get("GCP_REGION", cls.region),
            job_name=os.environ.get("CLOUDRUN_JOB_NAME", cls.job_name),
            backend=os.environ.get("JOB_BACKEND", cls.backend),
            job_image=os.environ.get("AUTODISCOVERY_IMAGE"),
            code_execution_backend=os.environ.get(
                "CODE_EXECUTION_BACKEND", cls.code_execution_backend
            ),
            modal_app_name=os.environ.get("MODAL_APP_NAME", cls.modal_app_name),
            modal_bucket_secret=os.environ.get("MODAL_BUCKET_SECRET", cls.modal_bucket_secret),
            local_root=os.environ.get("AUTODISCOVERY_LOCAL_ROOT", cls.local_root),
            local_user_id=os.environ.get("AUTODISCOVERY_LOCAL_USER_ID", cls.local_user_id),
            local_max_concurrent_jobs=int(
                os.environ.get(
                    "AUTODISCOVERY_LOCAL_MAX_CONCURRENT_JOBS",
                    cls.local_max_concurrent_jobs,
                )
            ),
        )

        # Apply overrides
        for key, value in overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)

        return config
