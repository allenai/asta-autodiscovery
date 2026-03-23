"""Cloud Run operations for executing replay jobs."""

import os

from google.cloud import run_v2


class ReplayJobError(Exception):
    """Exception raised when replay job operations fail."""

    pass


def run_replay_job(
    userid: str,
    jobid: str,
    source_path: str,
    target_bucket: str,
    time_scale: float = 0.1,
    project_id: str | None = None,
    region: str = "us-west1",
) -> str:
    """Execute the replay Cloud Run job to simulate an AutoDiscovery run.

    Args:
        userid: User identifier
        jobid: Job identifier
        source_path: Source GCS path containing template run files (e.g., gs://bucket/users/test/jobs/melanoma/output)
        target_bucket: Target GCS bucket name (e.g., "autodiscovery")
        time_scale: Time multiplier (0.1 = 10x faster, default=0.1)
        project_id: GCP project ID (auto-detected from environment if None)
        region: GCP region (default: us-west1)

    Returns:
        Execution ID from Cloud Run

    Raises:
        ReplayJobError: If job execution fails

    Example:
        >>> execution_id = run_replay_job(
        ...     userid="alice",
        ...     jobid="test-123",
        ...     source_path="gs://example-bucket/users/test/jobs/melanoma/output",
        ...     target_bucket="autodiscovery",
        ...     time_scale=0.1
        ... )
    """
    # Get project ID from environment if not provided
    if project_id is None:
        project_id = os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        raise ReplayJobError(
            "project_id must be provided or set via GCP_PROJECT or GOOGLE_CLOUD_PROJECT environment variable"
        )

    # Construct target path
    target_path = f"gs://{target_bucket}/users/{userid}/jobs/{jobid}/output"

    # Build arguments for replay job
    args = [
        f"--source={source_path}",
        f"--target={target_path}",
        f"--time-scale={time_scale}",
    ]

    # Build job resource name for replay job
    replay_job_name = f"projects/{project_id}/locations/{region}/jobs/autodiscovery-replay"

    try:
        # Create JobsClient and run the job
        client = run_v2.JobsClient()

        # Create request with container argument overrides
        request = run_v2.RunJobRequest(
            name=replay_job_name,
            overrides=run_v2.RunJobRequest.Overrides(
                container_overrides=[
                    run_v2.RunJobRequest.Overrides.ContainerOverride(
                        args=args,
                    )
                ]
            ),
        )

        # Execute the job (don't wait for completion)
        operation = client.run_job(request=request)

        # Get the execution name from operation metadata without waiting
        execution_name = operation.metadata.name

        # Extract just the execution ID from the full resource path
        # Format: projects/{project}/locations/{location}/jobs/{job}/executions/{execution}
        execution_id = execution_name.split("/")[-1]
        return execution_id

    except Exception as e:
        raise ReplayJobError(f"Failed to execute replay job: {e}")
