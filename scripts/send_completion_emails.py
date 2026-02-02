#!/usr/bin/env python3
"""Send completion notification emails for finished AutoDiscovery runs.

This script scans for completed runs and sends email notifications to users.
It tracks sent emails in email_state.json to avoid duplicates.

Environment variables required:
    - GCS credentials (for reading/writing job state)
    - AUTH0_DOMAIN, AUTH0_MGMT_CLIENT_ID, AUTH0_MGMT_CLIENT_SECRET (for user email lookup)
"""

import argparse
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from autodiscovery_jobs import (
    Auth0Error,
    JobConfig,
    JobManager,
    get_user,
    record_email_sent,
    refresh_run_status,
    send_email,
    was_email_sent,
)

# Set up Jinja2 environment for email templates
TEMPLATES_DIR = Path(__file__).parent.parent / "packages" / "autodiscovery_jobs" / "src" / "autodiscovery_jobs" / "templates"
jinja_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=False)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


SUBJECT_VERBS = {"SUCCEEDED": "completed successfully", "FAILED": "failed", "CANCELLED": "was cancelled"}
STATUS_MESSAGES = {
    "SUCCEEDED": ("Your AutoDiscovery run has completed successfully.", "#28a745"),
    "FAILED": ("Your AutoDiscovery run has failed.", "#dc3545"),
    "CANCELLED": ("Your AutoDiscovery run was cancelled.", "#6c757d"),
}


def build_email_subject(status: str, run_name: str | None) -> str:
    """Build email subject line based on run status."""
    name_part = f'"{run_name}"' if run_name else "Your run"
    return f"AutoDiscovery: {name_part} {SUBJECT_VERBS.get(status, 'finished')}"


def build_email_body(
    runid: str,
    status: str,
    run_name: str | None,
    started_at: str | None,
    finished_at: datetime | None,
    origin_url: str | None = None,
    metadata: dict | None = None,
) -> str:
    """Build email body using Jinja2 template."""
    status_message, status_color = STATUS_MESSAGES.get(
        status, ("Your AutoDiscovery run has finished.", "#17a2b8")
    )
    base_url = origin_url or "https://asta.allenai.org"
    metadata = metadata or {}
    datasets = metadata.get("datasets", [])

    context = {
        "name": run_name or runid,
        "status": status,
        "status_message": status_message,
        "status_color": status_color,
        "run_url": f"{base_url}/runs/{runid}",
        "started_at": datetime.fromisoformat(started_at).strftime("%Y-%m-%d %H:%M:%S UTC") if started_at else "Unknown",
        "finished_at": finished_at.strftime("%Y-%m-%d %H:%M:%S UTC") if finished_at else "Unknown",
        "description": metadata.get("description", ""),
        "domain": metadata.get("domain", ""),
        "intent": metadata.get("intent", ""),
        "n_experiments": metadata.get("n_experiments", ""),
        "datasets": ", ".join(d.get("name", "") for d in datasets) if datasets else "",
    }
    template = jinja_env.get_template("completion_email.html")
    return template.render(**context).strip()


def send_completion_emails(
    config: JobConfig,
    max_age_hours: int = 24,
    dry_run: bool = False,
    userid: str | None = None,
) -> tuple[int, int, int]:
    """Send completion emails for recently finished runs.

    Args:
        config: Job configuration
        max_age_hours: Only process runs completed within this many hours
        dry_run: If True, don't actually send emails
        userid: If provided, only scan this user's runs

    Returns:
        Tuple of (emails_sent, already_sent, errors)
    """
    manager = JobManager(config)
    cutoff_time = datetime.now(UTC) - timedelta(hours=max_age_hours)

    logger.info(f"Scanning for runs completed after {cutoff_time.isoformat()}")

    # Get users to scan
    if userid:
        user_ids = [userid]
        logger.info(f"Scanning single user: {userid}")
    else:
        user_ids = manager.list_user_ids()
        logger.info(f"Found {len(user_ids)} users to scan")

    emails_sent = 0
    already_sent = 0
    errors = 0

    for userid in user_ids:
        try:
            job_ids = manager.list_jobs(userid)
        except Exception as e:
            logger.error(f"Failed to list jobs for user {userid}: {e}")
            errors += 1
            continue

        for runid in job_ids:
            try:
                # Get run details with refreshed status from Cloud Run
                run_details = refresh_run_status(userid, runid, config)
                if not run_details:
                    continue

                # Check if run is finished (status was refreshed above)
                if not run_details.is_finished:
                    continue

                # Check finish time
                if not run_details.finished_at:
                    # Run is finished but no timestamp - might be old
                    # Skip to avoid sending emails for ancient runs
                    logger.debug(f"Skipping {userid}/{runid}: finished but no timestamp")
                    continue

                if run_details.finished_at < cutoff_time:
                    # Too old, skip
                    continue

                # Check if email already sent
                if was_email_sent(userid, runid, config):
                    already_sent += 1
                    continue

                # Get user email from Auth0
                try:
                    recipient_email = get_user(userid).get("email")
                    if not recipient_email:
                        logger.warning(f"No email found for user {userid}")
                        errors += 1
                        continue
                except Auth0Error as e:
                    logger.error(f"Failed to get email for user {userid}: {e}")
                    errors += 1
                    continue

                # Get run metadata
                metadata = manager.get_metadata(userid, runid)
                run_name = metadata.get("name") if metadata else None
                status = run_details.status
                execution_id = run_details.execution_id
                origin_url = run_details.origin_url
                started_at = run_details.created_at

                # Build email content
                subject = build_email_subject(status, run_name)
                body_html = build_email_body(
                    runid, status, run_name, started_at, run_details.finished_at,
                    origin_url=origin_url, metadata=metadata,
                )

                if dry_run:
                    logger.info(f"[DRY RUN] Would send email to {recipient_email} for {userid}/{runid}")
                    logger.info(f"  Subject: {subject}")
                else:
                    # Send email
                    try:
                        send_email(
                            recipient_email=recipient_email,
                            subject=subject,
                            body_html=body_html,
                        )

                        # Record that email was sent
                        record_email_sent(
                            userid=userid,
                            runid=runid,
                            execution_id=execution_id,
                            status=status,
                            subject=subject,
                            body_html=body_html,
                            config=config,
                        )

                        logger.info(f"Sent completion email for {userid}/{runid}")
                        emails_sent += 1

                    except Exception as e:
                        logger.error(f"Failed to send email for {userid}/{runid}: {e}")
                        errors += 1

            except Exception as e:
                logger.error(f"Error processing {userid}/{runid}: {e}")
                errors += 1

    return emails_sent, already_sent, errors


def main():
    parser = argparse.ArgumentParser(
        description="Send completion notification emails for finished AutoDiscovery runs"
    )
    parser.add_argument(
        "--max-age-hours",
        type=int,
        default=24,
        help="Only process runs completed within N hours (default: 24)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be sent without actually sending emails",
    )
    parser.add_argument(
        "--userid",
        type=str,
        default=None,
        help="Only scan runs for this specific user ID",
    )
    args = parser.parse_args()

    config = JobConfig.from_env()

    logger.info("=" * 60)
    logger.info("Send Completion Emails Script")
    logger.info(f"Bucket: {config.bucket}")
    logger.info(f"Max age: {args.max_age_hours} hours")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"User filter: {args.userid or 'all users'}")
    logger.info("=" * 60)

    try:
        emails_sent, already_sent, errors = send_completion_emails(
            config,
            args.max_age_hours,
            args.dry_run,
            args.userid,
        )

        logger.info("=" * 60)
        logger.info("Summary:")
        logger.info(f"  Emails sent: {emails_sent}")
        logger.info(f"  Already sent: {already_sent}")
        logger.info(f"  Errors: {errors}")
        logger.info("=" * 60)

        return 0 if errors == 0 else 1

    except Exception as e:
        logger.error(f"Script failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
