#!/usr/bin/env python3
"""Clean up uploaded dataset files older than 7 days.

This script deletes user-uploaded datasets from GCS after 7 days to comply
with data retention policies. It only targets files in the data/ directory,
preserving job results and metadata.
"""

import argparse
import logging
import sys
from datetime import UTC, datetime, timedelta

from google.cloud import storage

try:
    from autodiscovery_jobs import JobConfig, JobManager
except ImportError:
    print("Error: autodiscovery_jobs package not found")
    print("Run: uv sync --all-packages")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def cleanup_old_datasets(
    config: JobConfig,
    max_age_days: int = 7,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Delete dataset files older than max_age_days.

    Args:
        config: Job configuration with bucket name
        max_age_days: Delete files older than this many days
        dry_run: If True, only log what would be deleted

    Returns:
        Tuple of (jobs_processed, error_count)
    """
    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)
    manager = JobManager(config)

    cutoff_time = datetime.now(UTC) - timedelta(days=max_age_days)
    logger.info(f"Scanning for dataset files older than {cutoff_time.isoformat()}")

    # Get all users from the manager
    user_ids = manager.list_user_ids()
    logger.info(f"Found {len(user_ids)} users to scan")

    # Track which jobs have old datasets
    jobs_with_old_data = set()

    # For each user, list their jobs using the manager
    for userid in user_ids:
        try:
            job_ids = manager.list_jobs(userid)
        except Exception as e:
            logger.error(f"Failed to list jobs for user {userid}: {e}")
            continue

        # For each job, check if it has old datasets
        for jobid in job_ids:
            data_prefix = f"users/{userid}/jobs/{jobid}/data/"
            data_blobs = bucket.list_blobs(prefix=data_prefix)

            # Check if any data files are old
            for blob in data_blobs:
                if blob.time_created and blob.time_created < cutoff_time:
                    jobs_with_old_data.add((userid, jobid))
                    break  # Found old data, no need to check more files

    logger.info(f"Found {len(jobs_with_old_data)} jobs with datasets to expire")

    # Use the manager to expire datasets for each job
    jobs_processed = 0
    error_count = 0

    for userid, jobid in jobs_with_old_data:
        if dry_run:
            logger.info(f"[DRY RUN] Would expire datasets for: {userid}/{jobid}")
            jobs_processed += 1
        else:
            try:
                manager.expire_datasets(userid, jobid)
                logger.info(f"Expired datasets for: {userid}/{jobid}")
                jobs_processed += 1
            except Exception as e:
                logger.error(f"Failed to expire datasets for {userid}/{jobid}: {e}")
                error_count += 1

    return jobs_processed, error_count


def main():
    parser = argparse.ArgumentParser(
        description="Clean up uploaded dataset files older than 7 days"
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=7,
        help="Delete files older than N days (default: 7)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    args = parser.parse_args()

    config = JobConfig.from_env()

    logger.info("=" * 60)
    logger.info("Dataset Cleanup Script")
    logger.info(f"Bucket: {config.bucket}")
    logger.info(f"Max age: {args.max_age_days} days")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info("=" * 60)

    try:
        jobs_processed, error_count = cleanup_old_datasets(
            config,
            args.max_age_days,
            args.dry_run,
        )

        logger.info("=" * 60)
        logger.info("Cleanup Summary:")
        logger.info(f"  Jobs processed: {jobs_processed}")
        logger.info(f"  Errors: {error_count}")
        logger.info("=" * 60)

        return 0 if error_count == 0 else 1

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
