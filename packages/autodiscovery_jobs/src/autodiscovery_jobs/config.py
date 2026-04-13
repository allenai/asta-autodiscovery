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

    # GCS Configuration
    bucket: str = "autodiscovery"
    project_id: str | None = None  # Auto-detect from gcloud if None

    # Cloud Run Configuration
    region: str = "us-west1"
    job_name: str = "autodiscovery-job"

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
            bucket=os.environ.get("GCS_BUCKET")
            or os.environ.get("AUTODISCOVERY_BUCKET", cls.bucket),
            project_id=os.environ.get("GCP_PROJECT"),
            region=os.environ.get("GCP_REGION", cls.region),
            job_name=os.environ.get("CLOUDRUN_JOB_NAME", cls.job_name),
            modal_app_name=os.environ.get("MODAL_APP_NAME", cls.modal_app_name),
            modal_bucket_secret=os.environ.get("MODAL_BUCKET_SECRET", cls.modal_bucket_secret),
        )

        # Apply overrides
        for key, value in overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)

        return config
