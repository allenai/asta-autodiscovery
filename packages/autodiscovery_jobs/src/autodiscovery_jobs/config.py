"""Configuration management for autodiscovery_jobs package."""

from __future__ import annotations

import os
from dataclasses import dataclass

# How many days uploaded datasets are retained before the cleanup cron deletes
# them from GCS.  Both the cleanup script and the API's expiry estimate read
# this value so they stay in sync.
DATASET_EXPIRY_DAYS: int = 7


@dataclass
class JobConfig:
    """Configuration for Cloud Run job management."""

    # Persistence backend selection: "local" (a directory on the host, default) or
    # "gcs" (a Cloud Storage bucket). Local is the default so the stack persists
    # data out of the box with no cloud account; deployments that keep data in GCS
    # must set STORAGE_BACKEND=gcs explicitly.
    storage_backend: str = "local"
    # Root directory for the local backend. In containers this is where the host
    # data directory is mounted (see docker-compose.yaml); ignored for gcs.
    storage_dir: str = "/mnt/data"

    # GCS Configuration (used when storage_backend == "gcs")
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
            storage_backend=os.environ.get("STORAGE_BACKEND", cls.storage_backend),
            storage_dir=os.environ.get("STORAGE_DIR", cls.storage_dir),
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
        )

        # Apply overrides
        for key, value in overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)

        return config
