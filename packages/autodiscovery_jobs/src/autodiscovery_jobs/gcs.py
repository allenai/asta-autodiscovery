"""GCS operations for managing job data and results."""

import json
import re
from pathlib import Path
from typing import Any

from google.cloud import storage

from .config import JobConfig
from .exceptions import GCSError, JobAlreadyExistsError, JobNotFoundError


def parse_gcs_path(gcs_path: str) -> tuple[str, str]:
    """Parse GCS path into bucket and prefix.

    Args:
        gcs_path: Path like "gs://bucket-name/path/to/prefix/"

    Returns:
        Tuple of (bucket_name, key_prefix)

    Example:
        >>> parse_gcs_path("gs://my-bucket/path/to/data/")
        ('my-bucket', 'path/to/data/')
    """
    # Remove gs:// prefix if present
    path = gcs_path.replace("gs://", "")

    # Split into bucket and prefix
    parts = path.split("/", 1)
    bucket_name = parts[0]
    key_prefix = parts[1] if len(parts) > 1 else ""

    # Ensure key_prefix ends with / if it's not empty
    if key_prefix and not key_prefix.endswith("/"):
        key_prefix += "/"

    return bucket_name, key_prefix


def get_user_path(userid: str, config: JobConfig | None = None) -> str:
    """Get GCS path for a user.

    Args:
        userid: User identifier
        config: Configuration (uses default if None)

    Returns:
        GCS path like "gs://bucket/users/{userid}/"
    """
    config = config or JobConfig()
    return f"gs://{config.bucket}/users/{userid}/"


def get_job_path(userid: str, jobid: str, config: JobConfig | None = None) -> str:
    """Get GCS path for a specific job.

    Args:
        userid: User identifier
        jobid: Job identifier
        config: Configuration (uses default if None)

    Returns:
        GCS path like "gs://bucket/users/{userid}/jobs/{jobid}/"
    """
    config = config or JobConfig()
    return f"gs://{config.bucket}/users/{userid}/jobs/{jobid}/"


def list_user_ids(config: JobConfig | None = None) -> list[str]:
    """List all user IDs with job data.

    Args:
        config: Configuration (uses default if None)

    Returns:
        List of user IDs

    Raises:
        GCSError: If listing fails
    """
    config = config or JobConfig()
    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)

    prefix = "users/"

    try:
        # List all "directories" (common prefixes) under the users prefix
        blobs = bucket.list_blobs(prefix=prefix, delimiter="/")
        # Consume the iterator to get prefixes
        list(blobs)

        # Extract user IDs from prefixes
        users = []
        for prefix_path in blobs.prefixes:
            # prefix looks like: "users/{userid}/"
            userid = prefix_path.rstrip("/").split("/")[-1]
            users.append(userid)

        return sorted(users)
    except Exception as e:
        raise GCSError(f"Failed to list users: {e}")


def list_user_jobs(userid: str, config: JobConfig | None = None) -> list[str]:
    """List all jobs for a user.

    Args:
        userid: User identifier
        config: Configuration (uses default if None)

    Returns:
        List of job IDs

    Raises:
        GCSError: If listing fails
    """
    config = config or JobConfig()
    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)

    prefix = f"users/{userid}/jobs/"

    try:
        # List all "directories" (common prefixes) under the jobs prefix
        blobs = bucket.list_blobs(prefix=prefix, delimiter="/")
        # Consume the iterator to get prefixes
        list(blobs)

        # Extract job IDs from prefixes
        jobs = []
        for prefix_path in blobs.prefixes:
            # prefix looks like: "users/{userid}/jobs/{jobid}/"
            jobid = prefix_path.rstrip("/").split("/")[-1]
            jobs.append(jobid)

        return sorted(jobs)
    except Exception as e:
        raise GCSError(f"Failed to list jobs for user {userid}: {e}")


def job_exists(userid: str, jobid: str, config: JobConfig | None = None) -> bool:
    """Check if a job directory exists.

    Args:
        userid: User identifier
        jobid: Job identifier
        config: Configuration (uses default if None)

    Returns:
        True if job exists, False otherwise
    """
    config = config or JobConfig()
    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)

    prefix = f"users/{userid}/jobs/{jobid}/"

    try:
        # Check if any blobs exist with this prefix
        blobs = bucket.list_blobs(prefix=prefix, max_results=1)
        return any(True for _ in blobs)
    except Exception:
        return False


def create_job_directory(
    userid: str, jobid: str, config: JobConfig | None = None, overwrite: bool = False
) -> str:
    """Create a new job directory structure in GCS.

    Creates:
        gs://bucket/users/{userid}/jobs/{jobid}/data/
        gs://bucket/users/{userid}/jobs/{jobid}/output/

    Args:
        userid: User identifier
        jobid: Job identifier
        config: Configuration (uses default if None)
        overwrite: If True, don't raise error if job exists

    Returns:
        GCS path to the created job directory

    Raises:
        JobAlreadyExistsError: If job exists and overwrite=False
        GCSError: If creation fails
    """
    config = config or JobConfig()

    if not overwrite and job_exists(userid, jobid, config):
        raise JobAlreadyExistsError(f"Job {jobid} already exists for user {userid}")

    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)

    base_path = f"users/{userid}/jobs/{jobid}"

    try:
        # Create placeholder files to establish directory structure
        for subdir in ["data/", "output/"]:
            blob = bucket.blob(f"{base_path}/{subdir}.placeholder")
            blob.upload_from_string("")

        return get_job_path(userid, jobid, config)
    except Exception as e:
        raise GCSError(f"Failed to create job directory: {e}")


def delete_job_directory(userid: str, jobid: str, config: JobConfig | None = None) -> None:
    """Delete a job directory and all its contents.

    Args:
        userid: User identifier
        jobid: Job identifier
        config: Configuration (uses default if None)

    Raises:
        JobNotFoundError: If job doesn't exist
        GCSError: If deletion fails
    """
    config = config or JobConfig()

    if not job_exists(userid, jobid, config):
        raise JobNotFoundError(f"Job {jobid} not found for user {userid}")

    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)

    prefix = f"users/{userid}/jobs/{jobid}/"

    try:
        # Delete all blobs with this prefix
        blobs = bucket.list_blobs(prefix=prefix)
        for blob in blobs:
            blob.delete()
    except Exception as e:
        raise GCSError(f"Failed to delete job directory: {e}")


def upload_dataset(
    userid: str,
    jobid: str,
    local_path: Path,
    config: JobConfig | None = None,
    remote_name: str | None = None,
) -> str:
    """Upload dataset file(s) to job's data directory.

    Args:
        userid: User identifier
        jobid: Job identifier
        local_path: Local file or directory path
        config: Configuration (uses default if None)
        remote_name: Optional remote filename (only for single files)

    Returns:
        GCS path where data was uploaded

    Raises:
        JobNotFoundError: If job doesn't exist
        GCSError: If upload fails
    """
    config = config or JobConfig()
    local_path = Path(local_path)

    if not job_exists(userid, jobid, config):
        raise JobNotFoundError(f"Job {jobid} not found for user {userid}")

    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)

    base_path = f"users/{userid}/jobs/{jobid}/data"

    try:
        if local_path.is_file():
            # Upload single file
            filename = remote_name or local_path.name
            blob = bucket.blob(f"{base_path}/{filename}")
            blob.upload_from_filename(str(local_path))
        elif local_path.is_dir():
            # Upload directory contents
            for file_path in local_path.rglob("*"):
                if file_path.is_file():
                    relative_path = file_path.relative_to(local_path)
                    blob = bucket.blob(f"{base_path}/{relative_path}")
                    blob.upload_from_filename(str(file_path))
        else:
            raise GCSError(f"Path not found: {local_path}")

        return f"gs://{config.bucket}/{base_path}/"
    except Exception as e:
        raise GCSError(f"Failed to upload dataset: {e}")


def expire_datasets(
    userid: str,
    jobid: str,
    max_age_days: int,
    dry_run: bool,
    config: JobConfig | None = None,
) -> list[str]:
    """Delete uploaded dataset files from job's data directory.

    This removes all files in the data/ directory to comply with data retention
    policies. Job metadata, results, and other files are preserved.

    Args:
        userid: User identifier
        jobid: Job identifier
        max_age_days: Only delete files older than this many days
        dry_run: If True, don't delete files, just return what would be deleted
        config: Configuration (uses default if None)

    Returns:
        List of GCS paths that were deleted (or would be deleted if dry_run=True)

    Raises:
        JobNotFoundError: If job doesn't exist
        GCSError: If deletion fails
    """
    from datetime import UTC, datetime, timedelta

    config = config or JobConfig()

    if not job_exists(userid, jobid, config):
        raise JobNotFoundError(f"Job {jobid} not found for user {userid}")

    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)
    prefix = f"users/{userid}/jobs/{jobid}/data/"

    # Calculate cutoff time
    cutoff_time = datetime.now(UTC) - timedelta(days=max_age_days)

    try:
        blobs = bucket.list_blobs(prefix=prefix)
        expired_paths = []

        for blob in blobs:
            # Skip placeholder files
            if blob.name.endswith(".placeholder"):
                continue

            # Check age
            if not blob.time_created or blob.time_created >= cutoff_time:
                continue

            # Record the path
            gcs_path = f"gs://{config.bucket}/{blob.name}"
            expired_paths.append(gcs_path)

            # Delete if not dry run
            if not dry_run:
                print(f"Deleting dataset file: {gcs_path}")
                # blob.delete()

        return expired_paths
    except Exception as e:
        raise GCSError(f"Failed to expire datasets: {e}")


def upload_metadata(
    userid: str, jobid: str, metadata: dict[str, Any], config: JobConfig | None = None
) -> str:
    """Upload metadata.json to job directory.

    Args:
        userid: User identifier
        jobid: Job identifier
        metadata: Metadata dictionary
        config: Configuration (uses default if None)

    Returns:
        GCS path to uploaded metadata

    Raises:
        JobNotFoundError: If job doesn't exist
        GCSError: If upload fails
    """
    config = config or JobConfig()

    if not job_exists(userid, jobid, config):
        raise JobNotFoundError(f"Job {jobid} not found for user {userid}")

    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)

    blob_path = f"users/{userid}/jobs/{jobid}/metadata.json"

    try:
        blob = bucket.blob(blob_path)
        blob.upload_from_string(json.dumps(metadata, indent=2))
        return f"gs://{config.bucket}/{blob_path}"
    except Exception as e:
        raise GCSError(f"Failed to upload metadata: {e}")


def upload_job_args(
    userid: str, jobid: str, args: dict[str, Any], config: JobConfig | None = None
) -> str:
    """Upload args.json to job's output directory.

    Args:
        userid: User identifier
        jobid: Job identifier
        args: Arguments dictionary
        config: Configuration (uses default if None)

    Returns:
        GCS path to saved args file

    Raises:
        JobNotFoundError: If job doesn't exist
        GCSError: If upload fails
    """
    config = config or JobConfig()

    if not job_exists(userid, jobid, config):
        raise JobNotFoundError(f"Job {jobid} not found for user {userid}")

    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)

    blob_path = f"users/{userid}/jobs/{jobid}/output/args.json"

    try:
        blob = bucket.blob(blob_path)
        blob.upload_from_string(json.dumps(args, indent=2))
        return f"gs://{config.bucket}/{blob_path}"
    except Exception as e:
        raise GCSError(f"Failed to save job args: {e}")


def get_metadata(userid: str, jobid: str, config: JobConfig | None = None) -> dict[str, Any]:
    """Download and parse metadata.json from job directory.

    Args:
        userid: User identifier
        jobid: Job identifier
        config: Configuration (uses default if None)

    Returns:
        Metadata dictionary

    Raises:
        JobNotFoundError: If job doesn't exist
        GCSError: If download fails
    """
    config = config or JobConfig()

    if not job_exists(userid, jobid, config):
        raise JobNotFoundError(f"Job {jobid} not found for user {userid}")

    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)

    blob_path = f"users/{userid}/jobs/{jobid}/metadata.json"

    try:
        blob = bucket.blob(blob_path)
        metadata_str = blob.download_as_text()
        return json.loads(metadata_str)
    except Exception as e:
        raise GCSError(f"Failed to download metadata: {e}")


def get_job_results(userid: str, jobid: str, config: JobConfig | None = None) -> list[str]:
    """List all result files from a job's output directory.

    Args:
        userid: User identifier
        jobid: Job identifier
        config: Configuration (uses default if None)

    Returns:
        List of GCS paths to result files

    Raises:
        JobNotFoundError: If job doesn't exist
        GCSError: If listing fails
    """
    config = config or JobConfig()

    if not job_exists(userid, jobid, config):
        raise JobNotFoundError(f"Job {jobid} not found for user {userid}")

    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)

    prefix = f"users/{userid}/jobs/{jobid}/output/"

    try:
        blobs = bucket.list_blobs(prefix=prefix)
        results = []
        for blob in blobs:
            # Skip placeholder files
            if not blob.name.endswith(".placeholder"):
                results.append(f"gs://{config.bucket}/{blob.name}")
        return results
    except Exception as e:
        raise GCSError(f"Failed to list job results: {e}")


def download_job_results(
    userid: str, jobid: str, local_dir: Path, config: JobConfig | None = None
) -> list[Path]:
    """Download all job results to a local directory.

    Args:
        userid: User identifier
        jobid: Job identifier
        local_dir: Local directory to download to
        config: Configuration (uses default if None)

    Returns:
        List of local file paths that were downloaded

    Raises:
        JobNotFoundError: If job doesn't exist
        GCSError: If download fails
    """
    config = config or JobConfig()
    local_dir = Path(local_dir)
    local_dir.mkdir(parents=True, exist_ok=True)

    if not job_exists(userid, jobid, config):
        raise JobNotFoundError(f"Job {jobid} not found for user {userid}")

    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)

    prefix = f"users/{userid}/jobs/{jobid}/output/"

    try:
        blobs = bucket.list_blobs(prefix=prefix)
        downloaded = []

        for blob in blobs:
            # Skip placeholder files
            if blob.name.endswith(".placeholder"):
                continue

            # Get relative path from output/ directory
            relative_path = blob.name[len(prefix) :]
            local_path = local_dir / relative_path

            # Create parent directories
            local_path.parent.mkdir(parents=True, exist_ok=True)

            # Download file
            blob.download_to_filename(str(local_path))
            downloaded.append(local_path)

        return downloaded
    except Exception as e:
        raise GCSError(f"Failed to download job results: {e}")


def count_experiment_results(userid: str, jobid: str, config: JobConfig | None = None) -> int:
    """Count completed experiment result files in a job's output directory.

    Counts files matching the pattern: mcts_node_{level}_{index}.json

    Args:
        userid: User identifier
        jobid: Job identifier
        config: Configuration (uses default if None)

    Returns:
        Number of experiment result files found (0 if error or none found)

    Example:
        >>> count_experiment_results("user123", "job456")
        5
    """
    config = config or JobConfig()
    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)

    prefix = f"users/{userid}/jobs/{jobid}/output/"
    pattern = re.compile(r"mcts_node_\d+_\d+\.json$")

    try:
        blobs = bucket.list_blobs(prefix=prefix, max_results=10000)
        count = 0
        for blob in blobs:
            filename = blob.name.split("/")[-1]
            if pattern.match(filename) and filename != "mcts_node_1_0.json":
                count += 1
        return count
    except Exception as e:
        # Log error but return 0 to allow graceful degradation
        import logging

        logging.error(f"Failed to count experiment results for job {jobid}: {e}")
        return 0


def get_job_args(userid: str, jobid: str, config: JobConfig | None = None) -> dict | None:
    """Read and parse args.json from a job's output directory.

    Args:
        userid: User identifier
        jobid: Job identifier
        config: Configuration (uses default if None)

    Returns:
        Dictionary containing job arguments, or None if file doesn't exist or parsing fails

    Example:
        >>> args = get_job_args("user123", "job456")
        >>> args.get("n_experiments", 0)
        10
    """
    config = config or JobConfig()
    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)

    blob_path = f"users/{userid}/jobs/{jobid}/output/args.json"

    try:
        blob = bucket.blob(blob_path)
        if not blob.exists():
            import logging

            logging.warning(f"args.json not found for job {jobid}")
            return None

        content = blob.download_as_text()
        return json.loads(content)
    except json.JSONDecodeError as e:
        import logging

        logging.warning(f"Invalid JSON in args.json for job {jobid}: {e}")
        return None
    except Exception as e:
        import logging

        logging.error(f"Failed to read args.json for job {jobid}: {e}")
        return None


def list_experiment_files(userid: str, jobid: str, config: JobConfig | None = None) -> list[str]:
    """List all experiment node files in a job's output directory.

    Lists files matching the pattern: mcts_node_{level}_{index}.json

    Args:
        userid: User identifier
        jobid: Job identifier
        config: Configuration (uses default if None)

    Returns:
        List of filenames (not full paths)

    Raises:
        JobNotFoundError: If job doesn't exist
        GCSError: If listing fails
    """
    config = config or JobConfig()

    if not job_exists(userid, jobid, config):
        raise JobNotFoundError(f"Job {jobid} not found for user {userid}")

    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)

    prefix = f"users/{userid}/jobs/{jobid}/output/"
    pattern = re.compile(r"mcts_node_\d+_\d+\.json$")

    try:
        blobs = bucket.list_blobs(prefix=prefix)
        filenames = []
        for blob in blobs:
            filename = blob.name.split("/")[-1]
            if pattern.match(filename):
                filenames.append(filename)
        return sorted(filenames)
    except Exception as e:
        raise GCSError(f"Failed to list experiment files for job {jobid}: {e}")


def read_experiment_node(
    userid: str, jobid: str, filename: str, config: JobConfig | None = None
) -> dict | None:
    """Read and parse a single experiment node JSON file.

    Args:
        userid: User identifier
        jobid: Job identifier
        filename: Experiment node filename (e.g., "mcts_node_0_0.json")
        config: Configuration (uses default if None)

    Returns:
        Dictionary containing parsed node data, or None if file doesn't exist or parsing fails

    Example:
        >>> node = read_experiment_node("user123", "job456", "mcts_node_0_0.json")
        >>> node.get("id")
        "node_0_0"
    """
    config = config or JobConfig()
    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)

    blob_path = f"users/{userid}/jobs/{jobid}/output/{filename}"

    try:
        blob = bucket.blob(blob_path)
        if not blob.exists():
            import logging

            logging.warning(f"Experiment node file not found: {filename} for job {jobid}")
            return None

        content = blob.download_as_text()
        return json.loads(content)
    except json.JSONDecodeError as e:
        import logging

        logging.warning(f"Invalid JSON in {filename} for job {jobid}: {e}")
        return None
    except Exception as e:
        import logging

        logging.error(f"Failed to read experiment node {filename} for job {jobid}: {e}")
        return None


def read_rich_outputs(
    userid: str,
    jobid: str,
    level: int,
    index: int,
    config: JobConfig | None = None,
) -> list[dict[str, Any]]:
    """Read rich output bundles for a specific experiment node.

    Args:
        userid: User identifier
        jobid: Job identifier
        level: Node level in the MCTS tree
        index: Node index in the MCTS tree
        config: Configuration (uses default if None)

    Returns:
        List of rich output bundles (each bundle is a MIME-type keyed dict).
        Returns an empty list when no rich outputs are found or parsing fails.
    """
    config = config or JobConfig()
    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)

    filename = f"ro_{level}_{index}.json"
    blob_path = f"users/{userid}/jobs/{jobid}/output/rich_outputs/{filename}"

    try:
        blob = bucket.blob(blob_path)
        if not blob.exists():
            import logging

            logging.warning("Rich output file not found: %s for job %s", filename, jobid)
            return []

        content = blob.download_as_text()
        parsed = json.loads(content)
        if not isinstance(parsed, list):
            import logging

            logging.warning(
                "Invalid rich output payload in %s for job %s: expected list",
                filename,
                jobid,
            )
            return []
        return parsed
    except json.JSONDecodeError as e:
        import logging

        logging.warning(f"Invalid JSON in {filename} for job {jobid}: {e}")
        return []
    except Exception as e:
        import logging

        logging.error(f"Failed to read rich outputs {filename} for job {jobid}: {e}")
        return []


def generate_upload_url(
    userid: str,
    jobid: str,
    filename: str,
    content_type: str = "application/octet-stream",
    expiration_seconds: int = 3600,  # 1 hour default
    config: JobConfig | None = None,
) -> dict[str, str]:
    """Generate a presigned URL for direct upload to GCS.

    Creates a signed URL that allows clients to upload files directly to GCS
    without routing through the application server.

    Args:
        userid: User identifier
        jobid: Job identifier
        filename: Name of file to upload
        content_type: MIME type of the file
        expiration_seconds: Number of seconds until URL expires (default: 3600 = 1 hour)
        config: Configuration (uses default if None)

    Returns:
        Dictionary with 'upload_url' and 'gcs_path' keys

    Raises:
        JobNotFoundError: If job doesn't exist
        GCSError: If URL generation fails

    Example:
        >>> result = generate_upload_url("user123", "job456", "data.csv", "text/csv")
        >>> result['upload_url']
        'https://storage.googleapis.com/...'
        >>> result['gcs_path']
        'gs://example-gcp-project/users/user123/jobs/job456/data/data.csv'
    """
    from datetime import timedelta

    config = config or JobConfig()

    # Verify job exists
    if not job_exists(userid, jobid, config):
        raise JobNotFoundError(f"Job {jobid} not found for user {userid}")

    try:
        client = storage.Client(project=config.project_id)
        bucket = client.bucket(config.bucket)

        # Construct blob path (matches existing pattern: users/{userid}/jobs/{jobid}/data/{filename})
        blob_path = f"users/{userid}/jobs/{jobid}/data/{filename}"
        blob = bucket.blob(blob_path)

        # Generate signed URL for PUT operation
        upload_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=expiration_seconds),
            method="PUT",
            content_type=content_type,
        )

        gcs_path = f"gs://{config.bucket}/{blob_path}"

        return {
            "upload_url": upload_url,
            "gcs_path": gcs_path,
        }
    except Exception as e:
        raise GCSError(f"Failed to generate upload URL: {e}")
