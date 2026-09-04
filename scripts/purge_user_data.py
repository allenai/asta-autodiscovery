#!/usr/bin/env python3
"""Permanently erase one user's AutoDiscovery data (GDPR right to be forgotten).

MAINTAINER-ONLY. This is the only caller of the purge helpers in
autodiscovery_jobs.gcs; they are intentionally not reachable from any HTTP
route. The script prints an inventory of the subject's data, requires the
operator to retype the subject identifier, and only then deletes. Deletion is
immediate and unrecoverable.

Scope is the AutoDiscovery bucket. Data AutoDiscovery hands to other systems --
the dataset copies in the Asta workspaces bucket, the Asta user record, Auth0 --
is erased by those systems; see UNCOVERED_SURFACES below.

Usage:
    # Inventory only -- deletes nothing, no confirmation needed
    uv run python scripts/purge_user_data.py --sub 'google-oauth2|123' --dry-run

    # Real purge (interactive confirmation required)
    uv run python scripts/purge_user_data.py --sub 'google-oauth2|123'
"""

import argparse
import logging
import sys

from autodiscovery_jobs import JobConfig, gcs

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Data surfaces this script cannot reach. Printed with every run so the operator
# knows what still needs a separate erasure request to close out a subject.
UNCOVERED_SURFACES = (
    "Dataset copies handed to the Asta workspaces bucket under owners/{uuid}/, "
    "and the asta-context-service artifacts registered from them -- once the "
    "session there is started that data is Asta's, with its own erasure path",
    "The Asta user record itself (created by Asta's /api/chat/login) and any "
    "Asta threads -- owned by Asta, not AutoDiscovery",
    "Auth0 profile (name, email) for the subject -- erase via Auth0",
    "Application logs and their retention window",
)

# Surfaces that need no action because they are derived and self-healing.
SELF_HEALING_SURFACES = (
    "The metrics dashboard's job snapshot: it is rebuilt by rescanning the job "
    "directories, so the subject's rows disappear on the next refresh",
)


def _format_bytes(num_bytes: int) -> str:
    """Render a byte count in the largest unit that keeps it readable."""
    size = float(num_bytes)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if size < 1024 or unit == "GiB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GiB"


def print_summary(summary: gcs.UserDataSummary, show_paths: bool) -> None:
    """Print the primary-bucket inventory for a subject."""
    print("")
    print("=" * 72)
    print(f"AutoDiscovery data for sub: {summary.userid}")
    print("=" * 72)
    print(f"  Bucket:              gs://{summary.bucket}/users/{summary.userid}/")
    print(f"  Objects:             {summary.object_count} ({_format_bytes(summary.total_bytes)})")
    print(f"  Jobs:                {len(summary.job_ids)}")
    print(f"  Credits profile:     {'present' if summary.has_user_profile else 'absent'}")
    print(f"  Shared-run index:    {len(summary.shared_run_ids)} entries")

    if summary.job_ids:
        print("  Job IDs:")
        for jobid in summary.job_ids:
            marker = "  [ACTIVE]" if jobid in summary.active_job_ids else ""
            print(f"    - {jobid}{marker}")

    if show_paths and summary.object_paths:
        print("  Objects:")
        for path in summary.object_paths:
            print(f"    - gs://{summary.bucket}/{path}")


def print_uncovered() -> None:
    """Print the data surfaces this script does not erase."""
    print("")
    print("NOT erased by this script -- close these out separately:")
    for surface in UNCOVERED_SURFACES:
        print(f"  * {surface}")
    print("")
    print("No action needed:")
    for surface in SELF_HEALING_SURFACES:
        print(f"  * {surface}")


def confirm(sub: str) -> bool:
    """Ask the operator to retype the subject before an irreversible delete.

    Args:
        sub: The subject identifier that must be retyped exactly.

    Returns:
        True if the operator typed the subject back exactly.
    """
    if not sys.stdin.isatty():
        print("")
        print("Refusing to purge: stdin is not a terminal and this step is interactive.")
        print("Run the script attached to a TTY (e.g. `docker run -it ...`), or use")
        print("--dry-run for a non-interactive inventory.")
        return False

    print("")
    print("This deletes the data listed above permanently. There is no undo, no")
    print("soft-delete, and no backup restore path.")
    print("")
    try:
        typed = input(f"Retype the sub exactly to confirm ({sub}): ")
    except (EOFError, KeyboardInterrupt):
        print("")
        return False
    return typed.strip() == sub


def main() -> int:
    """Run the inventory-then-purge flow for one subject."""
    parser = argparse.ArgumentParser(
        description="Permanently erase one user's AutoDiscovery data (maintainer-only)",
    )
    parser.add_argument(
        "--sub",
        required=True,
        help="Auth0 subject identifier, e.g. 'google-oauth2|123456789'",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the inventory and exit without deleting or prompting",
    )
    parser.add_argument(
        "--show-paths",
        action="store_true",
        help="List every object path in the inventory, not just the counts",
    )
    args = parser.parse_args()

    config = JobConfig.from_env()

    try:
        summary = gcs.summarize_user_data(args.sub, config)
    except ValueError as e:
        print(f"error: {e}")
        return 2
    except Exception as e:
        logger.error(f"Failed to inventory data for {args.sub}: {e}")
        return 1

    print_summary(summary, args.show_paths)
    print_uncovered()

    if summary.is_empty:
        print("")
        print("Nothing to purge.")
        return 0

    if args.dry_run:
        print("")
        print("Dry run: nothing was deleted.")
        return 0

    if summary.active_job_ids:
        print("")
        print("Refusing to purge: these jobs are not in a terminal state and can")
        print("still write to GCS after deletion, which would leave data behind:")
        for jobid in summary.active_job_ids:
            print(f"  - {jobid}")
        print("Cancel them first, then re-run.")
        return 1

    if not confirm(args.sub):
        print("Aborted. Nothing was deleted.")
        return 1

    try:
        result = gcs.purge_user_data(args.sub, config)
    except Exception as e:
        logger.error(f"Purge failed for {args.sub}: {e}")
        return 1

    print("")
    print(
        f"Deleted {len(result['deleted_objects'])} objects "
        f"({_format_bytes(result['deleted_bytes'])}) from gs://{result['bucket']}/"
    )
    print(f"Deleted {len(result['deleted_shared_run_ids'])} shared-run index entries")

    print("")
    print("Purge complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
