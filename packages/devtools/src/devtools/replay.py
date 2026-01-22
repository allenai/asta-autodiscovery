"""Replay module for simulating AutoDiscovery runs.

This module provides functionality to replay a completed AutoDiscovery run by
progressively copying output files from GCS with the same timing as the original
run. This is useful for testing the webapp integration and polling behavior without
running expensive LLM calls.
"""

import time
from datetime import datetime

from google.cloud import storage


def parse_gcs_path(gcs_path: str) -> tuple[str, str]:
    """Parse a GCS path into bucket and blob prefix.

    Args:
        gcs_path: GCS path like "gs://bucket-name/path/to/dir"

    Returns:
        Tuple of (bucket_name, blob_prefix)

    Raises:
        ValueError: If path is not a valid GCS path

    Example:
        >>> parse_gcs_path("gs://my-bucket/users/alice/jobs/123/output")
        ('my-bucket', 'users/alice/jobs/123/output')
    """
    if not gcs_path.startswith("gs://"):
        raise ValueError(f"Invalid GCS path (must start with gs://): {gcs_path}")

    # Remove gs:// prefix and split on first /
    path_without_scheme = gcs_path[5:]  # Remove "gs://"
    parts = path_without_scheme.split("/", 1)

    bucket_name = parts[0]
    blob_prefix = parts[1] if len(parts) > 1 else ""

    # Ensure blob_prefix ends with / if it's a directory path
    if blob_prefix and not blob_prefix.endswith("/"):
        blob_prefix += "/"

    return bucket_name, blob_prefix


class BlobInfo:
    """Represents a GCS blob with its metadata."""

    def __init__(self, filename: str, time_created: datetime):
        """Create blob info.

        Args:
            filename: Blob filename
            time_created: GCS blob creation timestamp
        """
        self.filename = filename
        self.time_created = time_created

    def __repr__(self):
        return f"BlobInfo({self.filename}, created={self.time_created})"


def discover_files(source_path: str, project_id: str | None = None) -> list[BlobInfo]:
    """Discover all output files from a completed AutoDiscovery run in GCS.

    Args:
        source_path: GCS path like "gs://bucket/users/alice/jobs/123/output"
        project_id: Optional GCP project ID (auto-detected if None)

    Returns:
        List of BlobInfo objects sorted by creation timestamp

    Raises:
        ValueError: If source_path is invalid or contains no valid output files

    Example:
        >>> files = discover_files("gs://my-bucket/users/alice/jobs/123/output")
        >>> print(f"Found {len(files)} files")
    """
    bucket_name, blob_prefix = parse_gcs_path(source_path)

    # Create GCS client
    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)

    # Discover all files with timestamps
    blob_infos = []

    # List all blobs with the given prefix
    blobs = bucket.list_blobs(prefix=blob_prefix)

    for blob in blobs:
        # Extract just the filename from the full blob path
        filename = blob.name[len(blob_prefix):]

        # Skip if this is a directory marker or empty
        if not filename or filename.endswith("/"):
            continue

        blob_infos.append(BlobInfo(filename, blob.time_created))

    if not blob_infos:
        raise ValueError(f"No valid output files found in {source_path}")

    # Sort by creation timestamp
    blob_infos.sort(key=lambda b: b.time_created)

    return blob_infos


def replay_autodiscovery(
    source_path: str,
    target_path: str,
    project_id: str | None = None,
    time_scale: float = 1.0,
    verbose: bool = True,
) -> None:
    """Replay an AutoDiscovery run by copying files with the same timing as the original.

    This simulates a real AutoDiscovery run by copying output files from a
    completed run in GCS to a target GCS location, preserving the original timing
    delays between file writes based on GCS blob creation timestamps.

    Args:
        source_path: GCS path like "gs://bucket/users/alice/jobs/123/output"
        target_path: GCS path like "gs://bucket/users/alice/jobs/456/output"
        project_id: Optional GCP project ID (auto-detected if None)
        time_scale: Multiply all delays by this factor (e.g., 0.1 for 10x faster, 2.0 for 2x slower)
        verbose: Print progress messages

    Raises:
        ValueError: If source_path or target_path are invalid or source contains no files

    Example:
        >>> replay_autodiscovery(
        ...     source_path="gs://my-bucket/users/alice/jobs/melanoma/output",
        ...     target_path="gs://my-bucket/users/alice/jobs/test-123/output",
        ...     time_scale=0.1  # 10x faster replay
        ... )
    """
    # Track actual elapsed time
    start_time = time.time()

    # Parse GCS paths
    source_bucket_name, source_prefix = parse_gcs_path(source_path)
    target_bucket_name, target_prefix = parse_gcs_path(target_path)

    # Create GCS client
    client = storage.Client(project=project_id)
    source_bucket = client.bucket(source_bucket_name)
    target_bucket = client.bucket(target_bucket_name)

    # Discover all files from source (sorted by creation timestamp)
    blob_infos = discover_files(source_path, project_id)

    if verbose:
        print(f"Replay AutoDiscovery Run")
        print(f"  Source: {source_path}")
        print(f"  Target: {target_path}")
        print(f"  Files: {len(blob_infos)}")
        print(f"  Time scale: {time_scale}x")
        print()

    def copy_blob(filename: str):
        """Copy a blob from source to target."""
        source_blob = source_bucket.blob(source_prefix + filename)
        target_blob = target_bucket.blob(target_prefix + filename)

        # Copy blob content
        target_blob.upload_from_string(source_blob.download_as_bytes())

    # Copy files with delays based on original timestamps
    for i, blob_info in enumerate(blob_infos):
        if i > 0:
            # Calculate delay from previous file's timestamp
            prev_timestamp = blob_infos[i - 1].time_created
            curr_timestamp = blob_info.time_created
            delay_seconds = (curr_timestamp - prev_timestamp).total_seconds()

            # Apply time scale
            delay_seconds *= time_scale

            if delay_seconds > 0:
                time.sleep(delay_seconds)

        if verbose:
            elapsed = time.time() - start_time
            print(f"[t={elapsed:.1f}s] {blob_info.filename}")

        copy_blob(blob_info.filename)

    if verbose:
        total_elapsed = time.time() - start_time
        print(f"\n[t={total_elapsed:.1f}s] Replay complete! {len(blob_infos)} files copied.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Replay an AutoDiscovery run by copying files with original timing"
    )
    parser.add_argument(
        "--source",
        type=str,
        required=True,
        help="Source GCS path (e.g., gs://bucket/users/alice/jobs/123/output)",
    )
    parser.add_argument(
        "--target",
        type=str,
        required=True,
        help="Target GCS path (e.g., gs://bucket/users/bob/jobs/456/output)",
    )
    parser.add_argument(
        "--time-scale",
        type=float,
        default=1.0,
        help="Time scale multiplier (0.1 = 10x faster, 2.0 = 2x slower)",
    )
    parser.add_argument(
        "--project-id",
        type=str,
        default=None,
        help="GCP project ID (auto-detected if not provided)",
    )

    args = parser.parse_args()

    replay_autodiscovery(
        source_path=args.source,
        target_path=args.target,
        project_id=args.project_id,
        time_scale=args.time_scale,
        verbose=True,
    )
