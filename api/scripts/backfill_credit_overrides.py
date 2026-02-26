#!/usr/bin/env python3
"""Backfill credit overrides for existing users.

This script creates credit overrides for all existing users based on their
current credit balance before the default is changed from 1000 to 500.

Rules applied:
- Users with more than 500 available credits get an override that preserves
  their current available balance.
- Users with 500 or fewer available credits get an override set such that
  they have exactly 500 available credits.

Usage:
    uv run python api/scripts/backfill_credit_overrides.py --dry-run
    uv run python api/scripts/backfill_credit_overrides.py
    uv run python api/scripts/backfill_credit_overrides.py --userid "google-oauth2|123"

Environment variables required:
    - GCS credentials (for reading/writing user profiles and job data)
"""

import argparse
import logging
import sys
from pathlib import Path

# Add api/ to path so we can import from utils
sys.path.insert(0, str(Path(__file__).parent.parent))

from autodiscovery_jobs import JobConfig, JobManager, update_user_profile
from utils.credits import get_user_credits

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

NEW_DEFAULT_CREDITS = 500


def compute_new_granted(consumed: int, pending: int, available: int) -> int:
    """Compute the new granted_credits value for a user.

    Ensures users with more than 500 available keep their current balance,
    and users with 500 or fewer are topped up to exactly 500 available.

    Args:
        consumed: Credits already consumed by completed experiments
        pending: Credits reserved for in-progress experiments
        available: Credits currently available for new experiments

    Returns:
        New granted_credits value to store in user profile
    """
    return consumed + pending + max(available, NEW_DEFAULT_CREDITS)


def backfill_credits(
    config: JobConfig,
    dry_run: bool = False,
    userid: str | None = None,
) -> tuple[int, int]:
    """Set credit overrides for existing users.

    Args:
        config: Job configuration
        dry_run: If True, log planned changes without writing to GCS
        userid: If provided, only process this specific user

    Returns:
        Tuple of (users_processed, errors)
    """
    manager = JobManager(config)

    if userid:
        user_ids = [userid]
        logger.info(f"Processing single user: {userid}")
    else:
        all_user_ids = manager.list_user_ids()
        # Only process real Auth0 users (they have '|' in their ID)
        user_ids = [uid for uid in all_user_ids if "|" in uid]
        skipped = len(all_user_ids) - len(user_ids)
        logger.info(f"Found {len(user_ids)} Auth0 users (skipped {skipped} non-Auth0 users)")

    users_processed = 0
    errors = 0

    for uid in user_ids:
        try:
            credits = get_user_credits(uid, config)
            new_granted = compute_new_granted(credits.consumed, credits.pending, credits.available)

            if dry_run:
                logger.info(
                    f"[DRY RUN] {uid}: granted={credits.granted}, consumed={credits.consumed}, "
                    f"pending={credits.pending}, available={credits.available} "
                    f"-> new_granted={new_granted}"
                )
            else:
                update_user_profile(uid, {"granted_credits": new_granted}, config)
                logger.info(
                    f"{uid}: set granted_credits={new_granted} "
                    f"(was granted={credits.granted}, available={credits.available})"
                )

            users_processed += 1

        except Exception as e:
            logger.error(f"Failed to process user {uid}: {e}")
            errors += 1

    return users_processed, errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill credit overrides for existing users before changing the default to 500"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without writing to GCS",
    )
    parser.add_argument(
        "--userid",
        type=str,
        default=None,
        help="Only process this specific user ID",
    )
    args = parser.parse_args()

    config = JobConfig.from_env()

    logger.info("=" * 60)
    logger.info("Credit Override Backfill Script")
    logger.info(f"Bucket: {config.bucket}")
    logger.info(f"New default credits: {NEW_DEFAULT_CREDITS}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"User filter: {args.userid or 'all users'}")
    logger.info("=" * 60)

    users_processed, errors = backfill_credits(
        config,
        dry_run=args.dry_run,
        userid=args.userid,
    )

    logger.info("=" * 60)
    logger.info("Summary:")
    logger.info(f"  Users processed: {users_processed}")
    logger.info(f"  Errors: {errors}")
    logger.info("=" * 60)

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
