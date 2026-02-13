"""Email sending utilities.

This module provides functions for sending emails via SMTP.
"""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

# Default SMTP server - Gmail SMTP Relay
DEFAULT_SMTP_SERVER = "smtp-relay.gmail.com"
DEFAULT_SMTP_PORT = 587

# Default sender email
DEFAULT_SENDER_EMAIL = "no-reply@allenai.org"


def send_email(
    recipient_email: str,
    subject: str,
    body_html: str,
    sender_email: str = DEFAULT_SENDER_EMAIL,
    smtp_server: str = DEFAULT_SMTP_SERVER,
    smtp_port: int = DEFAULT_SMTP_PORT,
    smtp_username: str | None = None,
    smtp_password: str | None = None,
) -> None:
    """Send an HTML email via SMTP.

    Args:
        recipient_email: Recipient email address
        subject: Email subject line
        body_html: HTML email body
        sender_email: Sender email address
        smtp_server: SMTP server hostname
        smtp_port: SMTP server port (default: 587)
        smtp_username: SMTP username (optional, from SMTP_USERNAME env var if not provided)
        smtp_password: SMTP password (optional, from SMTP_PASSWORD env var if not provided)

    Raises:
        smtplib.SMTPException: If email sending fails
    """
    # Check for credentials in environment if not provided
    if smtp_username is None:
        smtp_username = os.environ.get("SMTP_USERNAME")
    if smtp_password is None:
        smtp_password = os.environ.get("SMTP_PASSWORD")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = recipient_email

    msg.attach(MIMEText(body_html, "html"))

    with smtplib.SMTP(smtp_server, smtp_port) as conn:
        conn.starttls()  # Upgrade connection to secure

        # Authenticate if credentials are provided
        if smtp_username and smtp_password:
            conn.login(smtp_username, smtp_password)
            logger.info("SMTP authentication successful")

        conn.send_message(msg)
        logger.info(f"Email sent successfully to {recipient_email}")
