"""Job backend interface and shared job-argument construction.

A *job backend* is responsible for launching an AutoDiscovery (AD) job process
and reporting on it (status / cancel / logs). The AD job itself — including its
Modal code-execution sandboxes — is identical regardless of backend; only the
mechanism that *launches* the job process differs (GCP Cloud Run vs local
Docker container).

The CLI arguments handed to the AD job image are backend-agnostic, so they are
built once here in :func:`build_job_args` and reused by every backend.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..config import JobConfig
from ..exceptions import JobBackendError


def build_job_args(
    userid: str,
    jobid: str,
    config: JobConfig,
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
    **kwargs: Any,
) -> list[str]:
    """Build the CLI argument list passed to the AD job container.

    These arguments are identical across backends. Paths use the ``/mnt/gcs``
    layout (the GCS bucket mounted into the job container) and the ``gs://``
    bucket path (consumed by the Modal sandbox), so a container launched by any
    backend behaves the same way.

    Args:
        userid: User identifier
        jobid: Job identifier
        config: Job configuration
        n_experiments: Number of experiments to run (required)
        model: Model to use (e.g., "gpt-4o"); uses args.py default when omitted
        belief_model: Model for belief distribution (optional)
        temperature: Temperature for agents (optional)
        belief_temperature: Temperature for belief agent (optional)
        k_experiments: Branching factor for experiments (optional)
        mcts_selection: Selection method (optional)
        reasoning_effort: Reasoning effort for o-series models (optional)
        exploration_weight: Exploration weight for UCB1 (optional)
        code_timeout: Timeout for code execution in seconds (optional)
        n_warmstart: Number of warmstart experiments (optional)
        **kwargs: Additional arguments to pass to the job

    Returns:
        The list of CLI arguments for ``python -m autodiscovery.run``.

    Raises:
        JobBackendError: If ``n_experiments`` is not provided.
    """
    if n_experiments is None:
        raise JobBackendError("n_experiments is required to run a job")

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
        "--work_dir=work",
        "--use_modal_sandbox",
        f"--bucket_path={bucket_path}",
        "--no-timestamp_dir",
    ]

    # Add optional explicit parameters if provided
    if belief_model is not None:
        args.append(f"--belief_model={belief_model}")
    if model is not None:
        args.append(f"--model={model}")
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

    return args


class JobBackend(ABC):
    """Abstract launcher for AutoDiscovery job processes.

    Implementations launch the AD job image and report on the resulting
    execution. ``execution_id`` is an opaque handle returned by ``run_job`` and
    passed back to the other methods; its format is backend-specific (a Cloud
    Run execution ID, a Docker container name, ...). Because the backend is
    chosen per deployment, the backend that created an ``execution_id`` is
    always the one queried with it.

    Every backend reports status using a shared phase vocabulary:
    ``PENDING``, ``RUNNING``, ``SUCCEEDED``, ``FAILED``, ``CANCELLED``.
    """

    def __init__(self, config: JobConfig):
        """Store the job configuration used to launch and query executions."""
        self.config = config

    @abstractmethod
    def run_job(
        self,
        userid: str,
        jobid: str,
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
        **kwargs: Any,
    ) -> str:
        """Launch a job and return its ``execution_id``."""
        ...

    @abstractmethod
    def get_job_status(self, execution_id: str) -> dict[str, Any]:
        """Return status info for an execution.

        The returned dict must include a ``phase`` key (one of the shared phase
        strings) and may include ``create_time`` / ``completion_time``.
        """
        ...

    @abstractmethod
    def cancel_job(self, execution_id: str) -> None:
        """Cancel a running execution."""
        ...

    @abstractmethod
    def get_job_logs(self, execution_id: str | None = None, limit: int = 50) -> list[str]:
        """Return recent log lines for an execution."""
        ...
