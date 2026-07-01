"""GCP Cloud Run job backend.

Launches AutoDiscovery jobs as Cloud Run job executions (the production
default). The module-level functions preserve the historical functional API
and are re-exported by :mod:`autodiscovery_jobs.cloudrun` for backward
compatibility; :class:`CloudRunBackend` is the :class:`JobBackend` adapter used
by the backend factory.
"""

from __future__ import annotations

import re
from typing import Any

from google.cloud import logging as cloud_logging
from google.cloud import run_v2

from ..config import JobConfig
from ..exceptions import CloudRunError
from .base import JobBackend, build_job_args

# Pattern to extract job name from execution ID
# Execution IDs are formatted as {job-name}-{random-suffix} where suffix is 5 alphanumeric chars
_EXECUTION_ID_PATTERN = re.compile(r"^(.+)-[a-z0-9]{5}$")


def run_job(
    userid: str,
    jobid: str,
    config: JobConfig | None = None,
    n_experiments: int | None = None,
    model: str | None = None,
    belief_model: str | None = None,
    temperature: float | None = None,
    belief_temperature: float | None = None,
    k_experiments: int | None = None,
    mcts_selection: str | None = None,
    reasoning_effort: str | None = None,
    exploration_weight: float | None = None,
    code_timeout: int | None = None,
    n_warmstart: int | None = None,
    **kwargs,
) -> str:
    """Execute a Cloud Run job.

    Args:
        userid: User identifier
        jobid: Job identifier
        config: Configuration (uses default if None)
        n_experiments: Number of experiments to run (required)
        model: Model to use (e.g., "gpt-4o", "o4-mini"); uses args.py default when omitted
        belief_model: Model for belief distribution (optional)
        temperature: Temperature for agents (optional)
        belief_temperature: Temperature for belief agent (optional)
        k_experiments: Branching factor for experiments (optional)
        mcts_selection: Selection method (ucb1, beam_search, pw, pw_all, ucb1_recursive) (optional)
        reasoning_effort: Reasoning effort for o-series models (low, medium, high) (optional)
        exploration_weight: Exploration weight for UCB1 (optional)
        code_timeout: Timeout for code execution in seconds (optional)
        n_warmstart: Number of warmstart experiments (optional)
        **kwargs: Additional arguments to pass to the job

    Returns:
        Execution ID from Cloud Run

    Raises:
        CloudRunError: If job execution fails
    """
    config = config or JobConfig()

    # Build the (backend-agnostic) CLI arguments for the AD job image.
    args = build_job_args(
        userid,
        jobid,
        config,
        n_experiments=n_experiments,
        model=model,
        belief_model=belief_model,
        temperature=temperature,
        belief_temperature=belief_temperature,
        k_experiments=k_experiments,
        mcts_selection=mcts_selection,
        reasoning_effort=reasoning_effort,
        exploration_weight=exploration_weight,
        code_timeout=code_timeout,
        n_warmstart=n_warmstart,
        **kwargs,
    )

    # Get project ID (required for Cloud Run API)
    project_id = config.project_id
    if not project_id:
        raise CloudRunError(
            "project_id must be set in config. Set it via config.project_id or "
            "GCP_PROJECT environment variable."
        )

    # Build job resource name
    job_name = f"projects/{project_id}/locations/{config.region}/jobs/{config.job_name}"

    try:
        # Create JobsClient and run the job
        client = run_v2.JobsClient()

        # Create request with container argument overrides
        request = run_v2.RunJobRequest(
            name=job_name,
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
        # The operation metadata contains the execution resource name
        execution_name = operation.metadata.name

        # Extract just the execution ID from the full resource path
        # Format: projects/{project}/locations/{location}/jobs/{job}/executions/{execution}
        execution_id = execution_name.split("/")[-1]
        return execution_id

    except Exception as e:
        raise CloudRunError(f"Failed to execute job: {e}") from e


def get_job_status(execution_id: str, config: JobConfig | None = None) -> dict[str, Any]:
    """Get status of a Cloud Run job execution.

    Args:
        execution_id: Execution ID from run_job()
        config: Configuration (uses default if None)

    Returns:
        Dictionary with status information including phase, timestamps, and counts.

    Raises:
        CloudRunError: If status check fails
    """
    config = config or JobConfig()

    # Get project ID
    project_id = config.project_id
    if not project_id:
        raise CloudRunError(
            "project_id must be set in config. Set it via config.project_id or "
            "GCP_PROJECT environment variable."
        )

    # Infer job name from execution ID (supports multiple job types)
    job_name = _infer_job_name_from_execution_id(execution_id, config.job_name)

    # Build execution resource name
    execution_name = (
        f"projects/{project_id}/locations/{config.region}/jobs/{job_name}/executions/{execution_id}"
    )

    try:
        # Create ExecutionsClient and get execution details
        client = run_v2.ExecutionsClient()
        request = run_v2.GetExecutionRequest(name=execution_name)
        execution = client.get_execution(request=request)

        # Convert execution to dictionary for easier access
        return {
            "name": execution.name,
            "uid": execution.uid,
            "phase": _get_execution_phase(execution),
            "create_time": execution.create_time,
            "start_time": execution.start_time,
            "completion_time": execution.completion_time,
            "running_count": execution.running_count,
            "succeeded_count": execution.succeeded_count,
            "failed_count": execution.failed_count,
            "cancelled_count": execution.cancelled_count,
            "reconciling": execution.reconciling,
            "conditions": [
                {
                    "type": condition.type,
                    "state": condition.state.name if condition.state else None,
                    "message": condition.message,
                    "last_transition_time": condition.last_transition_time,
                }
                for condition in execution.conditions
            ],
        }

    except Exception as e:
        raise CloudRunError(f"Failed to get job status: {e}") from e


def _infer_job_name_from_execution_id(execution_id: str, default_job_name: str) -> str:
    """Infer the Cloud Run job name from an execution ID.

    Execution IDs are formatted as {job-name}-{random-suffix}, where the suffix
    is a 5-character alphanumeric string.

    Args:
        execution_id: The execution ID (e.g., "autodiscovery-replay-67d4p")
        default_job_name: Fallback job name if inference fails

    Returns:
        The inferred job name, or default_job_name if pattern doesn't match
    """
    match = _EXECUTION_ID_PATTERN.match(execution_id)
    if match:
        return match.group(1)
    return default_job_name


def _get_execution_phase(execution: run_v2.Execution) -> str:
    """Determine execution phase from execution state.

    Args:
        execution: Execution object

    Returns:
        Phase string: "PENDING", "RUNNING", "SUCCEEDED", "FAILED", or "CANCELLED"
    """
    if execution.cancelled_count > 0:
        return "CANCELLED"
    elif execution.failed_count > 0:
        return "FAILED"
    elif execution.succeeded_count > 0 and execution.running_count == 0:
        return "SUCCEEDED"
    elif execution.running_count > 0:
        return "RUNNING"
    else:
        return "PENDING"


def cancel_job(execution_id: str, config: JobConfig | None = None) -> None:
    """Cancel a running Cloud Run job execution.

    Args:
        execution_id: Execution ID from run_job()
        config: Configuration (uses default if None)

    Raises:
        CloudRunError: If cancellation fails
    """
    config = config or JobConfig()

    # Get project ID
    project_id = config.project_id
    if not project_id:
        raise CloudRunError(
            "project_id must be set in config. Set it via config.project_id or "
            "GCP_PROJECT environment variable."
        )

    # Infer job name from execution ID (supports multiple job types)
    job_name = _infer_job_name_from_execution_id(execution_id, config.job_name)

    # Build execution resource name
    execution_name = (
        f"projects/{project_id}/locations/{config.region}/jobs/{job_name}/executions/{execution_id}"
    )

    try:
        # Create ExecutionsClient and cancel the execution
        client = run_v2.ExecutionsClient()
        request = run_v2.CancelExecutionRequest(name=execution_name)
        operation = client.cancel_execution(request=request)
        # Wait for cancellation to complete
        operation.result()
    except Exception as e:
        raise CloudRunError(f"Failed to cancel job: {e}") from e


def get_job_logs(
    execution_id: str | None = None, config: JobConfig | None = None, limit: int = 50
) -> list[str]:
    """Get logs for a Cloud Run job execution.

    Args:
        execution_id: Optional execution ID to filter logs
        config: Configuration (uses default if None)
        limit: Maximum number of log entries to return

    Returns:
        List of log entries (text payloads)

    Raises:
        CloudRunError: If log retrieval fails
    """
    config = config or JobConfig()

    # Get project ID
    project_id = config.project_id
    if not project_id:
        raise CloudRunError(
            "project_id must be set in config. Set it via config.project_id or "
            "GCP_PROJECT environment variable."
        )

    try:
        # Create Cloud Logging client
        logging_client = cloud_logging.Client(project=project_id)

        # Build the filter query
        filter_str = (
            f'resource.type="cloud_run_job" AND resource.labels.job_name="{config.job_name}"'
        )
        if execution_id:
            filter_str += f' AND labels.execution_name="{execution_id}"'

        # List log entries with the filter
        entries = logging_client.list_entries(
            filter_=filter_str,
            page_size=limit,
            order_by=cloud_logging.DESCENDING,
        )

        # Extract text payloads from log entries
        log_messages = []
        for entry in entries:
            # Handle both text and structured payloads
            if hasattr(entry, "payload") and entry.payload:
                if isinstance(entry.payload, str):
                    log_messages.append(entry.payload)
                elif isinstance(entry.payload, dict):
                    # For structured logs, convert to string representation
                    log_messages.append(str(entry.payload))

        return log_messages

    except Exception as e:
        raise CloudRunError(f"Failed to get job logs: {e}") from e


class CloudRunBackend(JobBackend):
    """:class:`JobBackend` that launches jobs as GCP Cloud Run executions."""

    def run_job(self, userid: str, jobid: str, **kwargs) -> str:
        """Launch a Cloud Run job execution and return its execution ID."""
        return run_job(userid, jobid, self.config, **kwargs)

    def get_job_status(self, execution_id: str) -> dict[str, Any]:
        """Return status info for a Cloud Run job execution."""
        return get_job_status(execution_id, self.config)

    def cancel_job(self, execution_id: str) -> None:
        """Cancel a running Cloud Run job execution."""
        cancel_job(execution_id, self.config)

    def get_job_logs(self, execution_id: str | None = None, limit: int = 50) -> list[str]:
        """Return recent log lines for a Cloud Run job execution."""
        return get_job_logs(execution_id, self.config, limit)
