"""Replay module for simulating AutoDiscovery runs.

This module provides functionality to replay a completed AutoDiscovery run by
progressively copying output files from GCS with realistic timing delays. This is
useful for testing the webapp integration and polling behavior without running
expensive LLM calls.
"""

import re
import time
from typing import TypedDict

from google.cloud import storage


class TimingConfig(TypedDict):
    """Configuration for replay timing delays (in seconds)."""

    args_delay: float  # Delay before writing args.json (usually 0)
    node_delay_min: float  # Minimum delay between nodes
    node_delay_max: float  # Maximum delay between nodes
    finalization_delay: float  # Delay before writing final summary files


# Default timing configuration (in seconds)
DEFAULT_TIMING = TimingConfig(
    args_delay=0,  # Immediate
    node_delay_min=0.5,  # Nodes vary in complexity
    node_delay_max=2,
    finalization_delay=3,  # Final summary generation
)


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


class NodeFile:
    """Represents a node file with its metadata."""

    def __init__(self, filename: str):
        """Parse node filename to extract level and index.

        Args:
            filename: Filename like "mcts_node_2_3.json" or "node_2_3.json"
        """
        self.filename = filename
        self.is_mcts = filename.startswith("mcts_")

        # Extract level and node_idx from filename
        # Patterns: "mcts_node_{level}_{idx}.json" or "node_{level}_{idx}.json"
        pattern = r"(?:mcts_)?node_(\d+)_(\d+)\.json"
        match = re.match(pattern, filename)
        if match:
            self.level = int(match.group(1))
            self.node_idx = int(match.group(2))
        else:
            raise ValueError(f"Invalid node filename: {filename}")

    def __repr__(self):
        return f"NodeFile({self.filename}, level={self.level}, idx={self.node_idx})"

    @property
    def sort_key(self):
        """Key for sorting nodes in execution order."""
        return (self.level, self.node_idx, 0 if self.is_mcts else 1)


def discover_files(source_path: str, project_id: str | None = None) -> dict[str, list[NodeFile]]:
    """Discover all output files from a completed AutoDiscovery run in GCS.

    Args:
        source_path: GCS path like "gs://bucket/users/alice/jobs/123/output"
        project_id: Optional GCP project ID (auto-detected if None)

    Returns:
        Dictionary with keys:
            - "args": List containing args.json (if exists)
            - "nodes": List of NodeFile objects sorted by execution order
            - "final": List of finalization files (mcts_nodes.json, etc.)

    Raises:
        ValueError: If source_path is invalid or contains no valid output files

    Example:
        >>> files = discover_files("gs://my-bucket/users/alice/jobs/123/output")
        >>> print(f"Found {len(files['nodes'])} node files")
    """
    bucket_name, blob_prefix = parse_gcs_path(source_path)

    # Create GCS client
    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)

    # Discover files by category
    args_file = []
    node_files = []
    final_files = []

    # List all blobs with the given prefix
    blobs = bucket.list_blobs(prefix=blob_prefix)

    for blob in blobs:
        # Extract just the filename from the full blob path
        filename = blob.name[len(blob_prefix):]

        # Skip if this is a directory marker or empty
        if not filename or filename.endswith("/"):
            continue

        if filename == "args.json":
            args_file.append(filename)
        elif filename in ["mcts_nodes.json", "mcts_nodes_all.json", "mcts_nodes.csv"]:
            final_files.append(filename)
        elif re.match(r"(?:mcts_)?node_\d+_\d+\.json", filename):
            try:
                node_files.append(NodeFile(filename))
            except ValueError:
                print(f"Warning: Skipping invalid node file: {filename}")

    # Sort nodes by execution order (level, idx, mcts-before-node)
    node_files.sort(key=lambda n: n.sort_key)

    if not node_files:
        raise ValueError(f"No valid node files found in {source_path}")

    return {
        "args": args_file,
        "nodes": node_files,
        "final": sorted(final_files),  # Alphabetical order
    }


def replay_autodiscovery(
    source_path: str,
    target_path: str,
    timing_config: TimingConfig | None = None,
    project_id: str | None = None,
    verbose: bool = True,
) -> None:
    """Replay an AutoDiscovery run by progressively copying files from GCS.

    This simulates a real AutoDiscovery run by copying output files from a
    completed run in GCS to a target GCS location with realistic timing delays.

    Args:
        source_path: GCS path like "gs://bucket/users/alice/jobs/123/output"
        target_path: GCS path like "gs://bucket/users/alice/jobs/456/output"
        timing_config: Custom timing configuration (uses defaults if None)
        project_id: Optional GCP project ID (auto-detected if None)
        verbose: Print progress messages

    Raises:
        ValueError: If source_path or target_path are invalid or source contains no files

    Example:
        >>> replay_autodiscovery(
        ...     source_path="gs://my-bucket/users/alice/jobs/melanoma/output",
        ...     target_path="gs://my-bucket/users/alice/jobs/test-123/output",
        ...     timing_config={"node_delay_min": 10, "node_delay_max": 20}
        ... )
    """
    import random

    timing = timing_config or DEFAULT_TIMING

    # Track actual elapsed time
    start_time = time.time()

    # Parse GCS paths
    source_bucket_name, source_prefix = parse_gcs_path(source_path)
    target_bucket_name, target_prefix = parse_gcs_path(target_path)

    # Create GCS client
    client = storage.Client(project=project_id)
    source_bucket = client.bucket(source_bucket_name)
    target_bucket = client.bucket(target_bucket_name)

    # Discover all files from source
    files = discover_files(source_path, project_id)

    if verbose:
        print(f"Replay AutoDiscovery Run")
        print(f"  Source: {source_path}")
        print(f"  Target: {target_path}")
        print(f"  Nodes: {len(files['nodes'])} files")
        print(f"  Finalization: {len(files['final'])} files")
        print()

    def copy_blob(filename: str):
        """Copy a blob from source to target."""
        source_blob = source_bucket.blob(source_prefix + filename)
        target_blob = target_bucket.blob(target_prefix + filename)

        # Copy blob content
        target_blob.upload_from_string(source_blob.download_as_bytes())

    # Phase 1: Copy args.json
    if files["args"]:
        if timing["args_delay"] > 0:
            time.sleep(timing["args_delay"])

        if verbose:
            elapsed = time.time() - start_time
            print(f"[t={elapsed:.1f}s] Copying args.json...")

        for filename in files["args"]:
            copy_blob(filename)

    # Phase 2: Copy node files with delays
    for i, node in enumerate(files["nodes"]):
        # Determine delay between nodes
        if i == 0:
            # First node gets a random delay
            delay = random.uniform(timing["node_delay_min"], timing["node_delay_max"])
        else:
            # Check if this is the second file of a node pair (mcts_node_X_Y -> node_X_Y)
            prev_node = files["nodes"][i - 1]
            if node.level == prev_node.level and node.node_idx == prev_node.node_idx:
                # Same node pair, no delay
                delay = 0
            else:
                # Different node, add random delay
                delay = random.uniform(timing["node_delay_min"], timing["node_delay_max"])

        if delay > 0:
            time.sleep(delay)

        if verbose and delay > 0:
            elapsed = time.time() - start_time
            print(f"[t={elapsed:.1f}s] Node {node.level}_{node.node_idx}: {node.filename}")

        copy_blob(node.filename)

    # Phase 3: Copy finalization files
    if files["final"]:
        time.sleep(timing["finalization_delay"])

        if verbose:
            elapsed = time.time() - start_time
            print(f"\n[t={elapsed:.1f}s] Finalizing: Writing summary files...")

        for filename in files["final"]:
            if verbose:
                print(f"  - {filename}")
            copy_blob(filename)

    if verbose:
        total_elapsed = time.time() - start_time
        total_files = len(files['nodes']) + len(files['args']) + len(files['final'])
        print(f"\n[t={total_elapsed:.1f}s] Replay complete! {total_files} files copied.")


if __name__ == "__main__":
    # Example usage for testing
    import sys

    if len(sys.argv) < 3:
        print("Usage: python -m autodiscovery.replay <source_gcs_path> <target_gcs_path>")
        print("\nExample:")
        print("  python -m autodiscovery.replay \\")
        print("    gs://my-bucket/users/alice/jobs/melanoma/output \\")
        print("    gs://my-bucket/users/alice/jobs/test-123/output")
        sys.exit(1)

    source = sys.argv[1]
    target = sys.argv[2]

    replay_autodiscovery(source, target, verbose=True)
