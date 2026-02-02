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

from autodiscovery_jobs import (
    Auth0Error,
    JobConfig,
    JobManager,
    get_user_email,
    record_email_sent,
    refresh_run_status,
    send_email,
    was_email_sent,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def build_email_subject(status: str, run_name: str | None) -> str:
    """Build email subject line based on run status.

    Args:
        status: Run status (SUCCEEDED, FAILED, CANCELLED)
        run_name: Optional run name

    Returns:
        Email subject line
    """
    name_part = f'"{run_name}"' if run_name else "Your run"

    if status == "SUCCEEDED":
        return f"AutoDiscovery: {name_part} completed successfully"
    elif status == "FAILED":
        return f"AutoDiscovery: {name_part} failed"
    elif status == "CANCELLED":
        return f"AutoDiscovery: {name_part} was cancelled"
    else:
        return f"AutoDiscovery: {name_part} finished"


def build_email_body_text(
    userid: str,
    runid: str,
    status: str,
    run_name: str | None,
    finished_at: datetime | None,
    execution_id: str | None,
    origin_url: str | None = None,
    metadata: dict | None = None,
) -> str:
    """Build plain text email body.

    Args:
        userid: User identifier
        runid: Run identifier
        status: Run status
        run_name: Optional run name
        finished_at: Finish timestamp
        execution_id: Cloud Run execution ID
        origin_url: Base URL where run was submitted (for results link)
        metadata: Run metadata for additional context

    Returns:
        Plain text email body
    """
    name_display = run_name or runid
    finished_str = finished_at.strftime("%Y-%m-%d %H:%M:%S UTC") if finished_at else "Unknown"

    if status == "SUCCEEDED":
        status_message = "Your AutoDiscovery run has completed successfully."
    elif status == "FAILED":
        status_message = "Your AutoDiscovery run has failed."
    elif status == "CANCELLED":
        status_message = "Your AutoDiscovery run was cancelled."
    else:
        status_message = "Your AutoDiscovery run has finished."

    # Build the run URL using origin or default
    base_url = origin_url or "https://asta.allenai.org"
    run_url = f"{base_url}/runs/{runid}"

    # Build metadata section
    metadata = metadata or {}
    description = metadata.get("description", "")
    domain = metadata.get("domain", "")
    intent = metadata.get("intent", "")
    n_experiments = metadata.get("n_experiments", "")
    datasets = metadata.get("datasets", [])
    dataset_names = ", ".join(d.get("name", "") for d in datasets) if datasets else ""

    body = f"""
{status_message}

Run Details:
  Name: {name_display}
  Status: {status}
  Finished: {finished_str}
"""

    if description:
        body += f"  Description: {description}\n"
    if domain:
        body += f"  Domain: {domain}\n"
    if intent:
        body += f"  Intent: {intent}\n"
    if dataset_names:
        body += f"  Datasets: {dataset_names}\n"
    if n_experiments:
        body += f"  Experiments: {n_experiments}\n"

    body += f"""
View your results: {run_url}

---
This is an automated message from AutoDiscovery (ASTA).
"""

    return body.strip()


def build_email_body_html(
    userid: str,
    runid: str,
    status: str,
    run_name: str | None,
    finished_at: datetime | None,
    execution_id: str | None,
    origin_url: str | None = None,
    metadata: dict | None = None,
) -> str:
    """Build HTML email body.

    Args:
        userid: User identifier
        runid: Run identifier
        status: Run status
        run_name: Optional run name
        finished_at: Finish timestamp
        execution_id: Cloud Run execution ID
        origin_url: Base URL where run was submitted (for results link)
        metadata: Run metadata for additional context

    Returns:
        HTML email body
    """
    name_display = run_name or runid
    finished_str = finished_at.strftime("%Y-%m-%d %H:%M:%S UTC") if finished_at else "Unknown"

    if status == "SUCCEEDED":
        status_message = "Your AutoDiscovery run has completed successfully."
        status_color = "#28a745"
    elif status == "FAILED":
        status_message = "Your AutoDiscovery run has failed."
        status_color = "#dc3545"
    elif status == "CANCELLED":
        status_message = "Your AutoDiscovery run was cancelled."
        status_color = "#6c757d"
    else:
        status_message = "Your AutoDiscovery run has finished."
        status_color = "#17a2b8"

    # Build the run URL using origin or default
    base_url = origin_url or "https://asta.allenai.org"
    run_url = f"{base_url}/runs/{runid}"

    # Extract metadata fields
    metadata = metadata or {}
    description = metadata.get("description", "")
    domain = metadata.get("domain", "")
    intent = metadata.get("intent", "")
    n_experiments = metadata.get("n_experiments", "")
    datasets = metadata.get("datasets", [])
    dataset_names = ", ".join(d.get("name", "") for d in datasets) if datasets else ""

    # Build optional metadata rows
    metadata_rows = ""
    if description:
        metadata_rows += f"""
                <dt>Description</dt>
                <dd>{description}</dd>"""
    if domain:
        metadata_rows += f"""
                <dt>Domain</dt>
                <dd>{domain}</dd>"""
    if intent:
        metadata_rows += f"""
                <dt>Intent</dt>
                <dd>{intent}</dd>"""
    if dataset_names:
        metadata_rows += f"""
                <dt>Datasets</dt>
                <dd>{dataset_names}</dd>"""
    if n_experiments:
        metadata_rows += f"""
                <dt>Experiments</dt>
                <dd>{n_experiments}</dd>"""

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .status {{ color: {status_color}; font-weight: bold; }}
        .details {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .details dt {{ font-weight: bold; }}
        .details dd {{ margin-left: 0; margin-bottom: 10px; }}
        .button {{ display: inline-block; background: #007bff; color: white; padding: 10px 20px;
                   text-decoration: none; border-radius: 5px; margin-top: 15px; }}
        .footer {{ color: #6c757d; font-size: 12px; margin-top: 30px; border-top: 1px solid #dee2e6; padding-top: 15px; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>AutoDiscovery Run Complete</h2>
        <p class="status">{status_message}</p>

        <div class="details">
            <dl>
                <dt>Run Name</dt>
                <dd>{name_display}</dd>
                <dt>Status</dt>
                <dd>{status}</dd>
                <dt>Completed</dt>
                <dd>{finished_str}</dd>{metadata_rows}
            </dl>
        </div>

        <a href="{run_url}" class="button">View Results</a>

        <div class="footer">
            This is an automated message from AutoDiscovery (ASTA).
        </div>
    </div>
</body>
</html>
""".strip()

    return html


def get_run_metadata(manager: JobManager, userid: str, runid: str) -> dict | None:
    """Get run metadata.

    Args:
        manager: JobManager instance
        userid: User identifier
        runid: Run identifier

    Returns:
        Metadata dict or None if not found
    """
    try:
        return manager.get_metadata(userid, runid)
    except Exception:
        return None


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
                    recipient_email = get_user_email(userid)
                    if not recipient_email:
                        logger.warning(f"No email found for user {userid}")
                        errors += 1
                        continue
                except Auth0Error as e:
                    logger.error(f"Failed to get email for user {userid}: {e}")
                    errors += 1
                    continue

                # Get run metadata
                metadata = get_run_metadata(manager, userid, runid)
                run_name = metadata.get("name") if metadata else None
                status = run_details.status
                execution_id = run_details.execution_id
                origin_url = run_details.origin_url

                # Build email content
                subject = build_email_subject(status, run_name)
                body_text = build_email_body_text(
                    userid, runid, status, run_name, run_details.finished_at, execution_id,
                    origin_url=origin_url, metadata=metadata,
                )
                body_html = build_email_body_html(
                    userid, runid, status, run_name, run_details.finished_at, execution_id,
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
                            body_text=body_text,
                            body_html=body_html,
                        )

                        # Record that email was sent
                        record_email_sent(
                            userid=userid,
                            runid=runid,
                            execution_id=execution_id,
                            status=status,
                            subject=subject,
                            body_text=body_text,
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
