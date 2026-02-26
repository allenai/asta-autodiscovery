#!/usr/bin/env python3
"""Generate a CSV of all users in the system.

Exports one row per user with the following fields:
    - userid: Auth0 user ID
    - email: Email address (fetched from Auth0)
    - credits_granted: Total credits granted, including any overrides
    - credits_used: Total completed experiments across all jobs

With --daily-activity, additional columns are appended:
    - experiments_YYYY-MM-DD: Experiments completed on each day (one column per day)

Environment variables required:
    AUTH0_MGMT_CLIENT_ID, AUTH0_MGMT_CLIENT_SECRET (for email lookup)
    GCS credentials (for reading job/user state)

Usage:
    python export_users_csv.py --output users.csv
    python export_users_csv.py --output users.csv --daily-activity
    python export_users_csv.py --userid auth0|123 --daily-activity

    # From the project root with uv:
    uv run --env-file .env api/scripts/export_users_csv.py --output users.csv
    uv run --env-file .env api/scripts/export_users_csv.py --output users.csv --daily-activity
    uv run --env-file .env api/scripts/export_users_csv.py --userid auth0|123 --daily-activity
"""

import argparse
import csv
import logging
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from autodiscovery_jobs import (
    Auth0Error,
    JobConfig,
    get_user,
)
from autodiscovery_jobs.gcs import (
    count_experiment_results,
    list_user_ids,
    list_user_jobs,
)
from autodiscovery_jobs.run_details import get_run_details
from autodiscovery_jobs.user_profile import get_user_granted_credits

DEFAULT_CREDITS_GRANTED = 1000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def get_user_stats(
    userid: str,
    config: JobConfig,
    include_daily: bool = False,
) -> dict:
    """Collect credit usage and optional daily activity stats for a user.

    Makes one GCS read per job (run_details + experiment count), parallelised
    across jobs with a thread pool.

    Args:
        userid: User identifier
        config: Job configuration
        include_daily: When True, also return experiments grouped by date

    Returns:
        Dict with keys:
            credits_granted (int)
            credits_used (int)
            daily (dict[str, int], only when include_daily=True)
    """
    custom_credits = get_user_granted_credits(userid, config)
    credits_granted = custom_credits if custom_credits is not None else DEFAULT_CREDITS_GRANTED

    job_ids = list_user_jobs(userid=userid, config=config)

    total_consumed = 0
    daily: dict[str, int] = defaultdict(int)

    def _scan_job(job_id: str) -> tuple[int, str | None] | None:
        """Return (experiments_completed, YYYY-MM-DD date) for one job.

        Returns None when the job should be excluded from counts (e.g. not
        yet started, or an error occurred).
        """
        try:
            run_details = get_run_details(userid=userid, runid=job_id, config=config)
            if run_details is None or run_details.status == "CREATED":
                return None
            completed = count_experiment_results(userid=userid, jobid=job_id, config=config)
            date = run_details.created_at[:10] if run_details.created_at else None
            return (completed, date)
        except Exception:
            return None

    if job_ids:
        max_workers = min(16, len(job_ids))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for result in executor.map(_scan_job, job_ids):
                if result is not None:
                    completed, date = result
                    total_consumed += completed
                    if include_daily and date:
                        daily[date] += completed

    stats: dict = {
        "credits_granted": credits_granted,
        "credits_used": total_consumed,
    }
    if include_daily:
        stats["daily"] = dict(daily)
    return stats


def generate_user_csv(
    config: JobConfig,
    output_file: str | None = None,
    daily_activity: bool = False,
    userid_filter: str | None = None,
) -> None:
    """Generate a CSV of all users and write it to a file or stdout.

    Args:
        config: Job configuration
        output_file: Destination file path; writes to stdout when None
        daily_activity: When True, include one column per day with experiment counts
        userid_filter: When set, only include this single user in the output
    """
    # Resolve user list
    if userid_filter:
        user_ids = [userid_filter]
    else:
        all_ids = list_user_ids(config=config)
        # Only real Auth0 users have a pipe in their ID (e.g. "auth0|…", "google-oauth2|…")
        user_ids = [uid for uid in all_ids if "|" in uid]
        logger.info(
            f"Found {len(user_ids)} Auth0 users "
            f"(skipped {len(all_ids) - len(user_ids)} non-Auth0 IDs)"
        )

    rows: list[dict] = []
    all_dates: set[str] = set()

    total = len(user_ids)
    for i, userid in enumerate(user_ids, 1):
        logger.info(f"[{i}/{total}] Processing {userid}")

        # Email from Auth0
        try:
            email = get_user(userid).get("email", "")
        except Auth0Error as e:
            logger.warning(f"Auth0 lookup failed for {userid}: {e}")
            email = ""

        # Credits and (optionally) daily activity
        try:
            stats = get_user_stats(userid, config, include_daily=daily_activity)
        except Exception as e:
            logger.error(f"Failed to get stats for {userid}: {e}")
            stats = {
                "credits_granted": DEFAULT_CREDITS_GRANTED,
                "credits_used": 0,
            }
            if daily_activity:
                stats["daily"] = {}

        row: dict = {
            "userid": userid,
            "email": email,
            "credits_granted": stats["credits_granted"],
            "credits_used": stats["credits_used"],
        }
        if daily_activity:
            daily = stats.get("daily", {})
            row["_daily"] = daily
            all_dates.update(daily.keys())

        rows.append(row)

    # Build column list
    fieldnames = ["userid", "email", "credits_granted", "credits_used"]
    sorted_dates: list[str] = []
    if daily_activity:
        sorted_dates = sorted(all_dates)
        fieldnames += [f"experiments_{d}" for d in sorted_dates]

    # Write CSV
    out = open(output_file, "w", newline="") if output_file else sys.stdout
    try:
        writer = csv.DictWriter(out, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            csv_row: dict = {
                "userid": row["userid"],
                "email": row["email"],
                "credits_granted": row["credits_granted"],
                "credits_used": row["credits_used"],
            }
            if daily_activity:
                daily = row.get("_daily", {})
                for date in sorted_dates:
                    csv_row[f"experiments_{date}"] = daily.get(date, 0)
            writer.writerow(csv_row)
    finally:
        if output_file:
            out.close()

    destination = output_file or "stdout"
    logger.info(f"Wrote {len(rows)} users to {destination}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a CSV of all users in the system"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--daily-activity",
        action="store_true",
        help="Add one column per calendar day with the number of experiments run",
    )
    parser.add_argument(
        "--userid",
        type=str,
        default=None,
        help="Process only this specific user ID",
    )
    args = parser.parse_args()

    config = JobConfig.from_env()

    logger.info("=" * 60)
    logger.info("User CSV Export")
    logger.info(f"Bucket:         {config.bucket}")
    logger.info(f"Daily activity: {args.daily_activity}")
    logger.info(f"User filter:    {args.userid or 'all users'}")
    logger.info(f"Output:         {args.output or 'stdout'}")
    logger.info("=" * 60)

    try:
        generate_user_csv(
            config=config,
            output_file=args.output,
            daily_activity=args.daily_activity,
            userid_filter=args.userid,
        )
        return 0
    except Exception as e:
        logger.error(f"Script failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
