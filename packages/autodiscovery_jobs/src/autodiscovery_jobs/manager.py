"""High-level interface for managing Cloud Run jobs."""

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

from . import cloudrun, gcs
from .config import JobConfig
from .exceptions import DatasetExpiredError
from .run_details import RunDetails, create_run_details, get_run_details


@dataclass
class ForkResult:
    """Result of forking a job."""

    new_run_id: str
    path: str
    run_details: RunDetails


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

    def copy_job_data(
        self,
        source_userid: str,
        source_jobid: str,
        dest_userid: str,
        dest_jobid: str,
    ) -> list[str]:
        """Copy dataset files from one job to another.

        Args:
            source_userid: User who owns the source job
            source_jobid: Source job identifier
            dest_userid: User who owns the destination job
            dest_jobid: Destination job identifier

        Returns:
            List of copied filenames
        """
        return gcs.copy_job_data_files(
            source_userid, source_jobid, dest_userid, dest_jobid, self.config
        )

    def fork_job(
        self, parent_run_id: str, parent_userid: str, user_id: str
    ) -> ForkResult:
        """Fork an existing run, copying its configuration and dataset files.

        Creates a new run pre-populated with the parent run's metadata
        and a server-side copy of the parent's dataset files.

        Permission checks are NOT performed here; callers are responsible
        for verifying access before calling this method.

        Args:
            parent_run_id: ID of the run to fork from
            parent_userid: User ID of the parent run's owner
            user_id: User ID of the user who will own the new run

        Returns:
            ForkResult with new_run_id, GCS path, and RunDetails

        Raises:
            ValueError: If parent run has no metadata or dataset files are gone
            GCSError: If any GCS operation fails
        """
        # Read parent metadata
        parent_metadata = self.get_metadata(parent_userid, parent_run_id)
        if not parent_metadata:
            raise ValueError(f"Parent run has no metadata: {parent_run_id}")

        # Create the child run
        new_run_id = str(uuid.uuid4())
        path = self.create_job(user_id, new_run_id)

        # Verify parent data files still exist
        if not self.has_data_files(parent_userid, parent_run_id):
            raise DatasetExpiredError(
                "The parent run's dataset has been deleted. "
                "To start a new run, please upload your data again."
            )

        # Copy dataset files from parent to child (server-side)
        self.copy_job_data(parent_userid, parent_run_id, user_id, new_run_id)

        # Build and upload child metadata
        child_metadata = self._build_fork_metadata(parent_metadata, parent_run_id)
        self.upload_metadata(user_id, new_run_id, child_metadata)

        # Create run_details.json
        run_details = create_run_details(user_id, new_run_id, self.config)

        return ForkResult(
            new_run_id=new_run_id,
            path=path,
            run_details=run_details,
        )

    @staticmethod
    def _build_fork_metadata(
        parent_metadata: dict[str, Any], parent_run_id: str
    ) -> dict[str, Any]:
        """Build child metadata from parent metadata for a fork operation."""
        parent_name = parent_metadata.get("name", "Untitled")
        return {
            # Descriptive fields from parent
            "name": f"Fork of {parent_name}",
            "description": parent_metadata.get("description", ""),
            "domain": parent_metadata.get("domain", ""),
            "intent": parent_metadata.get("intent", ""),
            "datasets": parent_metadata.get("datasets", []),
            # Advanced settings from parent
            "n_experiments": parent_metadata.get("n_experiments"),
            "exploration_weight": parent_metadata.get("exploration_weight"),
            "mcts_selection": parent_metadata.get("mcts_selection"),
            "surprisal_width": parent_metadata.get("surprisal_width"),
            "evidence_weight": parent_metadata.get("evidence_weight"),
            "warmstart_experiments": parent_metadata.get("warmstart_experiments"),
            "n_warmstart": parent_metadata.get("n_warmstart"),
            # Lineage
            "lineage": {
                "parent_run_id": parent_run_id,
                "parent_run_name": parent_name,
            },
            # Clear per-run state
            "is_bookmarked": None,
            "bookmarked_experiment_ids": None,
            "is_shared": None,
        }

    def delete_job(self, userid: str, jobid: str) -> None:
        """Delete a job directory and all contents.

        Args:
            userid: User identifier
            jobid: Job identifier
        """
        gcs.delete_job_directory(userid, jobid, self.config)
        gcs.delete_shared_run_index(jobid, self.config)

    def soft_delete_job(self, userid: str, jobid: str) -> dict[str, Any]:
        """Soft delete a job by stopping execution and removing user data.

        This performs a soft delete that:
        1. Cancels the Cloud Run execution if job is RUNNING
        2. Marks the job as DELETED in run_details.json
        3. Removes user-uploaded files from data/ directory
        4. Preserves metadata.json, run_details.json, and all output/ files

        This operation is idempotent and can be safely called multiple times.

        Args:
            userid: User identifier
            jobid: Job identifier

        Returns:
            Dictionary with deletion details including:
            - deleted_files: List of deleted file paths
            - preserved_files: Count of preserved files
            - status: "DELETED"
            - deleted_at: ISO timestamp
            - cancelled_execution: Boolean indicating if job was cancelled

        Raises:
            JobNotFoundError: If job doesn't exist
            GCSError: If soft delete fails
        """
        # Get current run details
        run_details = get_run_details(userid, jobid, self.config)
        cancelled_execution = False

        # Cancel execution if job is RUNNING
        if run_details and run_details.status == "RUNNING" and run_details.execution_id:
            try:
                cloudrun.cancel_execution(
                    execution_id=run_details.execution_id,
                    config=self.config
                )
                cancelled_execution = True
            except Exception:
                # Continue with soft delete even if cancellation fails
                pass

        # Perform soft delete
        result = gcs.soft_delete_job(userid, jobid, self.config)
        result["cancelled_execution"] = cancelled_execution

        gcs.delete_shared_run_index(jobid, self.config)

        return result

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

    def generate_upload_url(
        self,
        userid: str,
        jobid: str,
        filename: str,
        content_type: str = "application/octet-stream",
        expiration_seconds: int = 3600,
    ) -> dict[str, str]:
        """Generate a presigned URL for direct upload to GCS.

        Args:
            userid: User identifier
            jobid: Job identifier
            filename: Name of file to upload
            content_type: MIME type of the file
            expiration_seconds: Number of seconds until URL expires

        Returns:
            Dictionary with 'upload_url' and 'gcs_path' keys
        """
        return gcs.generate_upload_url(
            userid,
            jobid,
            filename,
            content_type,
            expiration_seconds,
            self.config,
        )

    def has_data_files(self, userid: str, jobid: str) -> bool:
        """Check if a job has any non-placeholder data files."""
        return gcs.has_data_files(userid, jobid, self.config)

    def expire_datasets(
        self,
        userid: str,
        jobid: str,
        max_age_days: int,
        dry_run: bool,
    ) -> list[str]:
        """Delete uploaded dataset files from job's data directory.

        This removes all files in the data/ directory to comply with data retention
        policies. Job metadata, results, and other files are preserved.

        Args:
            userid: User identifier
            jobid: Job identifier
            max_age_days: Only delete files older than this many days
            dry_run: If True, don't delete files, just return what would be deleted

        Returns:
            List of GCS paths that were deleted (or would be deleted if dry_run=True)
        """
        return gcs.expire_datasets(userid, jobid, max_age_days, dry_run, self.config)

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

    def upload_job_args(self, userid: str, jobid: str, args: dict[str, Any]) -> str:
        """Upload job arguments to output directory.

        Args:
            userid: User identifier
            jobid: Job identifier
            args: Arguments dictionary

        Returns:
            GCS path to saved args file
        """
        return gcs.upload_job_args(userid, jobid, args, self.config)

    def get_metadata(self, userid: str, jobid: str) -> dict[str, Any]:
        """Download metadata from job directory.

        Args:
            userid: User identifier
            jobid: Job identifier
        Returns:
            Metadata dictionary
        """
        return gcs.get_metadata(userid, jobid, self.config)

    def get_job_args(self, userid: str, jobid: str) -> dict[str, Any] | None:
        """Get job arguments from metadata.

        Args:
            userid: User identifier
            jobid: Job identifier

        Returns:
            Dictionary of job arguments, or None if not found
        """
        return gcs.get_job_args(userid, jobid, self.config)

    def get_shared_run_owner(self, runid: str) -> str | None:
        """Get the owner userid for a shared run.

        Uses a GCS index for O(1) lookups on warm paths. Falls back to a full
        glob scan on index misses, and lazily populates the index when a shared
        run is found so subsequent requests hit the fast path.

        Args:
            runid: Run identifier

        Returns:
            User ID if the run exists and is shared, None otherwise

        Note:
            Returns None for runs that don't exist OR exist but are not shared.
            This prevents information leakage about run existence.
        """
        # Fast path: check the shared-run index
        userid = gcs.get_shared_run_index(runid, self.config)
        if userid:
            return userid

        # Slow path: full glob scan across all users
        userid = gcs.get_userid_for_job(runid, self.config)
        if not userid:
            return None

        # Verify the run is marked as shared
        try:
            metadata = self.get_metadata(userid, runid)
            if metadata.get("is_shared"):
                # Lazily populate the index for next time
                gcs.write_shared_run_index(runid, userid, self.config)
                return userid
        except Exception:
            # If we can't read metadata, treat as not shared
            logger.warning("Failed to read metadata for run %s (user %s)", runid, userid, exc_info=True)

        return None

    def set_run_shared(self, runid: str, userid: str, is_shared: bool) -> None:
        """Update a run's shared state in metadata and keep the index in sync.

        Args:
            runid: Run identifier
            userid: User ID of the run owner
            is_shared: True to share, False to unshare
        """
        metadata = self.get_metadata(userid, runid) or {}
        metadata["is_shared"] = is_shared
        self.upload_metadata(userid, runid, metadata)

        if is_shared:
            gcs.write_shared_run_index(runid, userid, self.config)
        else:
            gcs.delete_shared_run_index(runid, self.config)

    # Job execution

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
        **kwargs,
    ) -> str:
        """Execute a Cloud Run job.

        Args:
            userid: User identifier
            jobid: Job identifier
            n_experiments: Number of experiments to run
            model: Model to use (e.g., "gpt-4o", "o4-mini"); uses args.py default when omitted
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
        n_experiments: int | None = None,
        model: str | None = None,
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
            model: Model to use; uses args.py default when omitted
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
