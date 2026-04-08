#!/usr/bin/env python3
"""Clean up uploaded dataset files past the retention window.

This script deletes user-uploaded datasets from GCS after DATASET_EXPIRY_DAYS
to comply with data retention policies. It only targets files in the data/
directory, preserving job results and metadata.
"""

import argparse
import logging
import sys

from autodiscovery_jobs import DATASET_EXPIRY_DAYS, JobConfig, JobManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def cleanup_old_datasets(
    config: JobConfig,
    max_age_days: int = DATASET_EXPIRY_DAYS,
    dry_run: bool = False,
) -> tuple[int, int, int]:
    """Delete dataset files older than max_age_days.

    Args:
        config: Job configuration with bucket name
        max_age_days: Delete files older than this many days
        dry_run: If True, only log what would be deleted

    Returns:
        Tuple of (jobs_processed, files_expired, error_count)
    """
    manager = JobManager(config)

    logger.info(f"Scanning for dataset files older than {max_age_days} days")

    # Get all users from the manager
    user_ids = manager.list_user_ids()
    logger.info(f"Found {len(user_ids)} users to scan")

    # Track statistics
    jobs_processed = 0
    files_expired = 0
    error_count = 0

    # For each user, process their jobs
    for userid in user_ids:
        try:
            job_ids = manager.list_jobs(userid)
        except Exception as e:
            logger.error(f"Failed to list jobs for user {userid}: {e}")
            error_count += 1
            continue

        # For each job, expire old datasets
        for jobid in job_ids:
            try:
                expired_paths = manager.expire_datasets(
                    userid, jobid, max_age_days=max_age_days, dry_run=dry_run
                )

                if expired_paths:
                    jobs_processed += 1
                    files_expired += len(expired_paths)

                    if dry_run:
                        logger.info(
                            f"[DRY RUN] Would expire {len(expired_paths)} datasets for: {userid}/{jobid}"
                        )
                        for path in expired_paths:
                            logger.info(f"  {path}")
                    else:
                        logger.info(f"Expired {len(expired_paths)} datasets for: {userid}/{jobid}")
                        for path in expired_paths:
                            logger.info(f"  {path}")

            except Exception as e:
                logger.error(f"Failed to expire datasets for {userid}/{jobid}: {e}")
                error_count += 1

    return jobs_processed, files_expired, error_count


def main():
    parser = argparse.ArgumentParser(
        description="Clean up uploaded dataset files past the retention window"
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=DATASET_EXPIRY_DAYS,
        help=f"Delete files older than N days (default: {DATASET_EXPIRY_DAYS})",
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
        jobs_processed, files_expired, error_count = cleanup_old_datasets(
            config,
            args.max_age_days,
            args.dry_run,
        )

        logger.info("=" * 60)
        logger.info("Cleanup Summary:")
        logger.info(f"  Jobs processed: {jobs_processed}")
        logger.info(f"  Files expired: {files_expired}")
        logger.info(f"  Errors: {error_count}")
        logger.info("=" * 60)

        return 0 if error_count == 0 else 1

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
