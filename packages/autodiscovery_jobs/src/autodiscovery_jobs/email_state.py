"""Service for managing email_state.json documents.

This module tracks email notification state for completed runs in the configured
object store (:mod:`autodiscovery_jobs.storage`). Each run can have an
email_state.json object that records whether a completion email was sent and
what content was included.

Schema:
    {
        "sent": bool,                   # Whether email was sent
        "sent_at": str | None,          # ISO timestamp when sent
        "execution_id": str | None,     # Cloud Run execution ID at time of email
        "status": str | None,           # Job status at time of email (SUCCEEDED/FAILED)
        "subject": str | None,          # Email subject line
        "body_html": str | None,        # HTML email body
    }

Note: Recipient email is intentionally NOT stored for privacy.
"""

import json
from datetime import UTC, datetime
from typing import Any

from .config import JobConfig
from .storage import get_store


def get_email_state_path(userid: str, runid: str) -> str:
    """Get the object key for email_state.json.

    Args:
        userid: User identifier
        runid: Run identifier

    Returns:
        Object key for email_state.json
    """
    return f"users/{userid}/jobs/{runid}/email_state.json"


def get_email_state(
    userid: str,
    runid: str,
    config: JobConfig | None = None,
) -> dict[str, Any] | None:
    """Get email state from the object store.

    Args:
        userid: User identifier
        runid: Run identifier
        config: Job configuration (uses default if None)

    Returns:
        Email state dictionary, or None if not found
    """
    config = config or JobConfig.from_env()
    store = get_store(config)

    try:
        return json.loads(store.read_text(get_email_state_path(userid, runid)))
    except Exception:
        pass

    return None


def record_email_sent(
    userid: str,
    runid: str,
    execution_id: str | None,
    status: str,
    subject: str,
    body_html: str,
    config: JobConfig | None = None,
) -> dict[str, Any]:
    """Record that an email was sent for a run.

    Args:
        userid: User identifier
        runid: Run identifier
        execution_id: Cloud Run execution ID
        status: Job status (SUCCEEDED/FAILED/CANCELLED)
        subject: Email subject line
        body_html: HTML email body
        config: Job configuration (uses default if None)

    Returns:
        The created email state dictionary
    """
    config = config or JobConfig.from_env()
    store = get_store(config)

    email_state = {
        "sent": True,
        "sent_at": datetime.now(UTC).isoformat(),
        "execution_id": execution_id,
        "status": status,
        "subject": subject,
        "body_html": body_html,
    }

    store.write_text(
        get_email_state_path(userid, runid),
        json.dumps(email_state, indent=2),
        content_type="application/json",
    )

    return email_state


def was_email_sent(userid: str, runid: str, config: JobConfig | None = None) -> bool:
    """Check if a completion email was already sent for a run.

    Args:
        userid: User identifier
        runid: Run identifier
        config: Job configuration (uses default if None)

    Returns:
        True if email was sent, False otherwise
    """
    email_state = get_email_state(userid, runid, config)
    if email_state:
        return email_state.get("sent", False)
    return False
