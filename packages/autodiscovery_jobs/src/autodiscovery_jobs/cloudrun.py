"""Cloud Run operations for executing and managing jobs."""

from typing import Any

from google.cloud import logging as cloud_logging
from google.cloud import run_v2

from .config import JobConfig
from .exceptions import CloudRunError


def run_job(
    userid: str,
    jobid: str,
    config: JobConfig | None = None,
    n_experiments: int = 4,
    model: str = "gpt-4o",
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
        model: Model to use (e.g., "gpt-4o", "o4-mini") (required)
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

    Example:
        >>> execution_id = run_job(
        ...     "exampleuser", "exp1",
        ...     n_experiments=8,
        ...     model="gpt-4o",
        ...     belief_model="gpt-4o",
        ...     temperature=1.0
        ... )
    """
    config = config or JobConfig()

    # Construct paths
    job_base = f"users/{userid}/jobs/{jobid}"
    metadata_path = f"/mnt/gcs/{job_base}/metadata.json"
    output_path = f"/mnt/gcs/{job_base}/output"
    bucket_path = f"gs://{config.bucket}/{job_base}/data"

    # Build arguments - required ones first
    args = [
        f"--dataset_metadata={metadata_path}",
        f"--out_dir={output_path}",
        f"--n_experiments={n_experiments}",
        f"--model={model}",
        "--work_dir=work",
        "--use_modal_sandbox",
        f"--bucket_path={bucket_path}",
        "--no-timestamp_dir",
    ]

    # Add optional explicit parameters if provided
    if belief_model is not None:
        args.append(f"--belief_model={belief_model}")
    if temperature is not None:
        args.append(f"--temperature={temperature}")
    if belief_temperature is not None:
        args.append(f"--belief_temperature={belief_temperature}")
    if k_experiments is not None:
        args.append(f"--k_experiments={k_experiments}")
    if mcts_selection is not None:
        args.append(f"--mcts_selection={mcts_selection}")
    if reasoning_effort is not None:
        args.append(f"--reasoning_effort={reasoning_effort}")
    if exploration_weight is not None:
        args.append(f"--exploration_weight={exploration_weight}")
    if code_timeout is not None:
        args.append(f"--code_timeout={code_timeout}")
    if n_warmstart is not None:
        args.append(f"--n_warmstart={n_warmstart}")

    # Add additional kwargs
    for key, value in kwargs.items():
        # Handle boolean flags
        if isinstance(value, bool):
            if value:
                args.append(f"--{key}")
            else:
                args.append(f"--no-{key}")
        else:
            args.append(f"--{key}={value}")

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
        raise CloudRunError(f"Failed to execute job: {e}")


def get_job_status(execution_id: str, config: JobConfig | None = None) -> dict[str, Any]:
    """Get status of a Cloud Run job execution.

    Args:
        execution_id: Execution ID from run_job()
        config: Configuration (uses default if None)

    Returns:
        Dictionary with status information including:
            - name: Execution resource name
            - status: Execution status (phase, completion_time, etc.)
            - metadata: Execution metadata

    Raises:
        CloudRunError: If status check fails

    Example:
        >>> status = get_job_status("autodiscovery-job-abc123")
        >>> print(status["phase"])  # "RUNNING", "SUCCEEDED", "FAILED", etc.
    """
    config = config or JobConfig()

    # Get project ID
    project_id = config.project_id
    if not project_id:
        raise CloudRunError(
            "project_id must be set in config. Set it via config.project_id or "
            "GCP_PROJECT environment variable."
        )

    # Build execution resource name
    execution_name = f"projects/{project_id}/locations/{config.region}/jobs/{config.job_name}/executions/{execution_id}"

    try:
        # Create ExecutionsClient and get execution details
        client = run_v2.ExecutionsClient()
        request = run_v2.GetExecutionRequest(name=execution_name)
        execution = client.get_execution(request=request)

        # Convert execution to dictionary for easier access
        # Key fields: name, uid, generation, labels, annotations, create_time,
        # start_time, completion_time, update_time, delete_time, expire_time,
        # launch_stage, job, execution, reconciling, conditions, observed_generation,
        # running_count, succeeded_count, failed_count, cancelled_count, etag
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
        raise CloudRunError(f"Failed to get job status: {e}")


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

    # Build execution resource name
    execution_name = f"projects/{project_id}/locations/{config.region}/jobs/{config.job_name}/executions/{execution_id}"

    try:
        # Create ExecutionsClient and cancel the execution
        client = run_v2.ExecutionsClient()
        request = run_v2.CancelExecutionRequest(name=execution_name)
        operation = client.cancel_execution(request=request)
        # Wait for cancellation to complete
        operation.result()
    except Exception as e:
        raise CloudRunError(f"Failed to cancel job: {e}")


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

    Example:
        >>> logs = get_job_logs("autodiscovery-job-abc123", limit=100)
        >>> for log in logs:
        ...     print(log)
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
        raise CloudRunError(f"Failed to get job logs: {e}")
