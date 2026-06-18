"""Email sending utilities.

This module provides functions for sending emails via SMTP.

Required environment variables:
    SMTP_SERVER: Mail server hostname to send through
    SENDER_EMAIL: From address for outgoing email

Optional:
    SMTP_PORT: Mail server port (defaults to 25)
"""

import logging
import os
import smtplib
from email.message import EmailMessage
from email.policy import SMTP as SMTPPolicy

logger = logging.getLogger(__name__)

DEFAULT_SMTP_PORT = 25


class EmailError(Exception):
    """Raised when email configuration or sending fails."""

    pass


def _require_env(name: str) -> str:
    """Return the value of a required environment variable, or raise."""
    value = os.environ.get(name)
    if not value:
        raise EmailError(f"Missing required environment variable: {name}")
    return value


def send_email(
    recipient_email: str,
    subject: str,
    body_html: str,
    sender_email: str | None = None,
    smtp_server: str | None = None,
    smtp_port: int | None = None,
) -> None:
    """Send an HTML email via SMTP.

    Args:
        recipient_email: Recipient email address
        subject: Email subject line
        body_html: HTML email body
        sender_email: From address. Defaults to the SENDER_EMAIL env var.
        smtp_server: SMTP server hostname. Defaults to the SMTP_SERVER env var.
        smtp_port: SMTP server port. Defaults to the SMTP_PORT env var, then 25.

    Raises:
        EmailError: If a required value (SENDER_EMAIL, SMTP_SERVER) is missing.
        smtplib.SMTPException: If email sending fails.
    """
    if sender_email is None:
        sender_email = _require_env("SENDER_EMAIL")
    if smtp_server is None:
        smtp_server = _require_env("SMTP_SERVER")
    if smtp_port is None:
        smtp_port = int(os.environ.get("SMTP_PORT", DEFAULT_SMTP_PORT))

    msg = EmailMessage(policy=SMTPPolicy)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg.set_content(body_html, subtype="html", charset="utf-8")

    with smtplib.SMTP(smtp_server, smtp_port) as conn:
        conn.send_message(msg)
        logger.info(f"Email sent successfully to {recipient_email}")
