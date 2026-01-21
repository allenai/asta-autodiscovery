"""High-level interface for managing Cloud Run jobs."""

from pathlib import Path
from typing import Any

from . import cloudrun, gcs
from .config import JobConfig


class JobManager:
    """High-level interface for managing Cloud Run jobs.

    This class provides a convenient way to manage jobs with persistent configuration.
    All operations delegate to the functional APIs in gcs and cloudrun modules.

    Example:
        >>> from autodiscovery_jobs import JobManager
        >>> manager = JobManager()  # Uses default config
        >>> manager.create_job("exampleuser", "experiment_1")
        >>> manager.upload_dataset("exampleuser", "experiment_1", Path("./data.csv"))
        >>> execution_id = manager.run_job("exampleuser", "experiment_1", n_experiments=4)
    """

    def __init__(self, config: JobConfig | None = None):
        """Initialize JobManager.

        Args:
            config: Configuration (uses default from environment if None)
        """
        self.config = config or JobConfig.from_env()

    # User operations

    def get_user_path(self, userid: str) -> str:
        """Get GCS path for a user.

        Args:
            userid: User identifier

        Returns:
            GCS path like "gs://bucket/users/{userid}/"
        """
        return gcs.get_user_path(userid, self.config)

    def list_user_ids(self) -> list[str]:
        """List all user IDs with job data.

        Returns:
            List of user IDs
        """
        return gcs.list_user_ids(self.config)

    # Job management

    def list_jobs(self, userid: str) -> list[str]:
        """List all jobs for a user.

        Args:
            userid: User identifier

        Returns:
            List of job IDs
        """
        return gcs.list_user_jobs(userid, self.config)

    def job_exists(self, userid: str, jobid: str) -> bool:
        """Check if a job exists.

        Args:
            userid: User identifier
            jobid: Job identifier

        Returns:
            True if job exists
        """
        return gcs.job_exists(userid, jobid, self.config)

    def create_job(self, userid: str, jobid: str, overwrite: bool = False) -> str:
        """Create a new job directory.

        Args:
            userid: User identifier
            jobid: Job identifier
            overwrite: If True, don't raise error if job exists

        Returns:
            GCS path to created job directory
        """
        return gcs.create_job_directory(userid, jobid, self.config, overwrite)

    def delete_job(self, userid: str, jobid: str) -> None:
        """Delete a job directory and all contents.

        Args:
            userid: User identifier
            jobid: Job identifier
        """
        gcs.delete_job_directory(userid, jobid, self.config)

    def get_job_path(self, userid: str, jobid: str) -> str:
        """Get GCS path for a job.

        Args:
            userid: User identifier
            jobid: Job identifier

        Returns:
            GCS path like "gs://bucket/users/{userid}/jobs/{jobid}/"
        """
        return gcs.get_job_path(userid, jobid, self.config)

    # Data operations

    def upload_dataset(
        self, userid: str, jobid: str, local_path: Path, remote_name: str | None = None
    ) -> str:
        """Upload dataset to job's data directory.

        Args:
            userid: User identifier
            jobid: Job identifier
            local_path: Local file or directory path
            remote_name: Optional remote filename (for single files only)

        Returns:
            GCS path where data was uploaded
        """
        return gcs.upload_dataset(userid, jobid, local_path, self.config, remote_name)

    def list_datasets(self, userid: str, jobid: str) -> list[str]:
        """List all dataset files in a job's data directory.

        Args:
            userid: User identifier
            jobid: Job identifier

        Returns:
            List of GCS paths to dataset files
        """
        return gcs.list_datasets(userid, jobid, self.config)

    def expire_datasets(self, userid: str, jobid: str) -> None:
        """Delete uploaded dataset files from job's data directory.

        This removes all files in the data/ directory to comply with data retention
        policies. Job metadata, results, and other files are preserved.

        Args:
            userid: User identifier
            jobid: Job identifier
        """
        gcs.expire_datasets(userid, jobid, self.config)

    def upload_metadata(self, userid: str, jobid: str, metadata: dict[str, Any]) -> str:
        """Upload metadata to job directory.

        Args:
            userid: User identifier
            jobid: Job identifier
            metadata: Metadata dictionary

        Returns:
            GCS path to uploaded metadata
        """
        return gcs.upload_metadata(userid, jobid, metadata, self.config)

    # Job execution

    def run_job(
        self,
        userid: str,
        jobid: str,
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
            n_experiments: Number of experiments to run
            model: Model to use (e.g., "gpt-4o", "o4-mini")
            belief_model: Model for belief distribution (optional)
            temperature: Temperature for agents (optional)
            belief_temperature: Temperature for belief agent (optional)
            k_experiments: Branching factor for experiments (optional)
            mcts_selection: Selection method (optional)
            reasoning_effort: Reasoning effort for o-series models (optional)
            exploration_weight: Exploration weight for UCB1 (optional)
            code_timeout: Timeout for code execution in seconds (optional)
            n_warmstart: Number of warmstart experiments (optional)
            **kwargs: Additional arguments

        Returns:
            Execution ID
        """
        return cloudrun.run_job(
            userid,
            jobid,
            self.config,
            n_experiments,
            model,
            belief_model,
            temperature,
            belief_temperature,
            k_experiments,
            mcts_selection,
            reasoning_effort,
            exploration_weight,
            code_timeout,
            n_warmstart,
            **kwargs,
        )

    def get_job_status(self, execution_id: str) -> dict[str, Any]:
        """Get status of a job execution.

        Args:
            execution_id: Execution ID from run_job()

        Returns:
            Dictionary with status information
        """
        return cloudrun.get_job_status(execution_id, self.config)

    def cancel_job(self, execution_id: str) -> None:
        """Cancel a running job execution.

        Args:
            execution_id: Execution ID from run_job()
        """
        cloudrun.cancel_job(execution_id, self.config)

    def get_job_logs(self, execution_id: str | None = None, limit: int = 50) -> list[str]:
        """Get logs for a job execution.

        Args:
            execution_id: Optional execution ID to filter logs
            limit: Maximum number of log entries to return

        Returns:
            List of log entries
        """
        return cloudrun.get_job_logs(execution_id, self.config, limit)

    # Results

    def get_results(self, userid: str, jobid: str) -> list[str]:
        """List all result files from a job.

        Args:
            userid: User identifier
            jobid: Job identifier

        Returns:
            List of GCS paths to result files
        """
        return gcs.get_job_results(userid, jobid, self.config)

    def download_results(self, userid: str, jobid: str, local_dir: Path) -> list[Path]:
        """Download all job results to local directory.

        Args:
            userid: User identifier
            jobid: Job identifier
            local_dir: Local directory to download to

        Returns:
            List of local file paths that were downloaded
        """
        return gcs.download_job_results(userid, jobid, local_dir, self.config)

    # Convenience methods

    def setup_and_run(
        self,
        userid: str,
        jobid: str,
        dataset_path: Path,
        metadata: dict[str, Any],
        n_experiments: int = 4,
        model: str = "gpt-4o",
        **kwargs,
    ) -> str:
        """Create job, upload data, and execute in one call.

        This is a convenience method that combines multiple operations:
        1. Create job directory
        2. Upload dataset
        3. Upload metadata
        4. Run job

        Args:
            userid: User identifier
            jobid: Job identifier
            dataset_path: Local path to dataset file or directory
            metadata: Metadata dictionary
            n_experiments: Number of experiments to run
            model: Model to use
            **kwargs: Additional arguments for run_job()

        Returns:
            Execution ID

        Example:
            >>> manager = JobManager()
            >>> execution_id = manager.setup_and_run(
            ...     "exampleuser", "quick_test",
            ...     Path("./data/"),
            ...     {"datasets": [{"name": "data.csv", "description": "Test"}]},
            ...     n_experiments=4
            ... )
        """
        # Create job (overwrite if exists)
        self.create_job(userid, jobid, overwrite=True)

        # Upload data and metadata
        self.upload_dataset(userid, jobid, dataset_path)
        self.upload_metadata(userid, jobid, metadata)

        # Run job
        return self.run_job(userid, jobid, n_experiments, model, **kwargs)
